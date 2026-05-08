import os
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import analysis
import database
import models
import schemas
import storage

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Datategrity Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_user(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=username)
    if user is None:
        raise credentials_exception
    return user


@app.get("/health")
def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/auth/register", response_model=schemas.UserRead)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = get_user(db, user_in.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed_password = get_password_hash(user_in.password)
    user = models.User(username=user_in.username, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token)
def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_in.username, user_in.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/projects", response_model=schemas.ProjectRead)
def create_project(project_in: schemas.ProjectCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = models.Project(
        user_id=current_user.id,
        name=project_in.name,
        description=project_in.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/projects", response_model=List[schemas.ProjectRead])
def list_projects(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Project).filter(models.Project.user_id == current_user.id).all()


def get_project(project_id: int, current_user: models.User, db: Session):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.get("/projects/{project_id}", response_model=schemas.ProjectRead)
def read_project(project_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_project(project_id, current_user, db)


@app.post("/projects/{project_id}/upload", response_model=schemas.UploadResponse)
async def upload_dataset(project_id: int, file: UploadFile = File(...), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    saved_path = await storage.save_upload_file(project_id, file)

    try:
        df = analysis.load_dataset(str(saved_path))
        project.dataset_path = str(saved_path)
        project.dataset_filename = file.filename
        project.updated_at = datetime.utcnow()
        db.add(project)
        db.commit()
        db.refresh(project)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}")

    return {
        "success": True,
        "message": f"Dataset uploaded to project {project.name}",
        "dataset_path": project.dataset_path,
        "dataset_filename": project.dataset_filename,
    }


@app.post("/projects/{project_id}/analyze")
def analyze_project(project_id: int, body: schemas.AnalyzeRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    if not project.dataset_path:
        raise HTTPException(status_code=400, detail="No dataset attached to project")
    df = analysis.load_dataset(project.dataset_path)
    result = analysis.analyze_data_quality(df, body.columns)
    
    # Save to history
    history = models.AnalysisHistory(
        project_id=project_id,
        operation_type="analyze",
        parameters=json.dumps({"columns": body.columns}),
        results=json.dumps(result),
    )
    db.add(history)
    db.commit()
    
    return result


@app.post("/projects/{project_id}/anomalies")
def anomalies_project(project_id: int, body: schemas.AnomalyRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    if not project.dataset_path:
        raise HTTPException(status_code=400, detail="No dataset attached to project")
    df = analysis.load_dataset(project.dataset_path)
    result = analysis.detect_anomalies(df, body.column, body.method)
    
    # Save to history
    history = models.AnalysisHistory(
        project_id=project_id,
        operation_type="anomaly",
        parameters=json.dumps({"column": body.column, "method": body.method}),
        results=json.dumps(result),
    )
    db.add(history)
    db.commit()
    
    return result


@app.post("/projects/{project_id}/validate")
def validate_project(project_id: int, body: schemas.ValidationRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    if not project.dataset_path:
        raise HTTPException(status_code=400, detail="No dataset attached to project")
    df = analysis.load_dataset(project.dataset_path)
    result = analysis.validate_data_integrity(df, body.rules)
    
    # Save to history
    history = models.AnalysisHistory(
        project_id=project_id,
        operation_type="validate",
        parameters=json.dumps({"rules": body.rules}),
        results=json.dumps(result),
    )
    db.add(history)
    db.commit()
    
    return result


@app.post("/projects/{project_id}/clean")
def clean_project(project_id: int, body: schemas.CleanRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    if not project.dataset_path:
        raise HTTPException(status_code=400, detail="No dataset attached to project")
    df = analysis.load_dataset(project.dataset_path)
    result = analysis.clean_data(df, body.operations)
    
    # Save to history
    history = models.AnalysisHistory(
        project_id=project_id,
        operation_type="clean",
        parameters=json.dumps({"operations": body.operations}),
        results=json.dumps(result),
    )
    db.add(history)
    db.commit()
    
    return result


@app.post("/projects/{project_id}/report")
def report_project(project_id: int, body: schemas.ReportRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    if not project.dataset_path:
        raise HTTPException(status_code=400, detail="No dataset attached to project")
    df = analysis.load_dataset(project.dataset_path)
    if body.report_type == "Quality Report":
        return {"report": analysis.generate_data_quality_report(df)}
    if body.report_type == "Anomaly Summary":
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        anomalies = {col: analysis.detect_anomalies(df, col) for col in numeric_cols[:5]}
        return {"report": {"anomalies": anomalies}}
    return {"report": "Validation Summary requires running validation first."}


@app.get("/projects/{project_id}/preview", response_model=schemas.DatasetPreview)
def preview_dataset(project_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    if not project.dataset_path:
        raise HTTPException(status_code=400, detail="No dataset attached to project")
    df = analysis.load_dataset(project.dataset_path)
    return analysis.get_dataset_preview(df)


@app.get("/projects/{project_id}/history", response_model=schemas.AnalysisHistoryList)
def get_project_history(project_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    history_items = (
        db.query(models.AnalysisHistory)
        .filter(models.AnalysisHistory.project_id == project_id)
        .order_by(models.AnalysisHistory.created_at.desc())
        .all()
    )
    return {"total": len(history_items), "items": history_items}


@app.post("/projects/{project_id}/chat")
def chat_project(project_id: int, body: schemas.ChatRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, current_user, db)
    if not project.dataset_path:
        raise HTTPException(status_code=400, detail="No dataset attached to project")
    if not body.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    df = analysis.load_dataset(project.dataset_path)

    if body.hf_token:
        try:
            from huggingface_hub import InferenceClient

            client = InferenceClient(token=body.hf_token.strip(), model="openai/gpt-oss-20b")
            context = f"Dataset columns: {list(df.columns)}\nRows: {len(df)}"
            messages = [
                {"role": "system", "content": "You are a data quality assistant."},
                {"role": "user", "content": f"{context}\n\n{body.message}"},
            ]
            response = client.chat_completion(messages=messages, max_tokens=512, temperature=0.7)
            if hasattr(response, "generations"):
                text = response.generations[0][0].text
            else:
                text = str(response)
            return {"response": text}
        except Exception as exc:
            return {"response": f"AI assistant error: {exc}"}

    return {
        "response": (
            "AI assistant is not configured. Supply a Hugging Face token to enable chat, "
            "or use the data quality and validation endpoints for analysis."
        )
    }
