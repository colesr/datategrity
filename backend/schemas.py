from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class ProjectRead(ProjectCreate):
    id: int
    dataset_path: Optional[str] = None
    dataset_filename: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class UploadResponse(BaseModel):
    success: bool
    message: str
    dataset_path: Optional[str] = None
    dataset_filename: Optional[str] = None


class AnalyzeRequest(BaseModel):
    columns: Optional[List[str]] = None


class AnomalyRequest(BaseModel):
    column: str
    method: str = "zscore"


class ValidationRequest(BaseModel):
    rules: str


class CleanRequest(BaseModel):
    operations: str


class ReportRequest(BaseModel):
    report_type: str


class ChatRequest(BaseModel):
    message: str
    hf_token: Optional[str] = None


class DatasetPreview(BaseModel):
    rows: int
    columns: int
    column_names: List[str]
    data_types: dict
    preview: List[dict]
    memory_mb: float


class AnalysisHistoryRead(BaseModel):
    id: int
    project_id: int
    operation_type: str
    parameters: str
    results: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class AnalysisHistoryList(BaseModel):
    total: int
    items: List[AnalysisHistoryRead]
