# Copilot Instructions for datategrity

## Project Overview

**datategrity** is a full-stack data quality analysis platform with:
- **Backend**: FastAPI (Python) REST API with SQLAlchemy ORM for data analysis, validation, anomaly detection, and AI-powered insights
- **Frontend**: Next.js 14 (React + TypeScript) single-page application
- **Data Layer**: SQLite database for metadata; CSV/Excel files stored in `backend/data/`
- **AI Integration**: Hugging Face Inference API for chat-based insights

## Build, Test, and Run Commands

### Backend (Python/FastAPI)
```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run development server (auto-reload on changes)
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Production server
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Frontend (Next.js)
```bash
# Install dependencies
cd frontend
npm install

# Development server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Run production build locally
npm start
```

### Docker
```bash
# Build and run both services
docker compose up --build

# Run without rebuilding
docker compose up

# Stop services
docker compose down
```

### Health Checks
- Backend API: `GET http://localhost:8000/health`
- Frontend: `http://localhost:3000`

## Project Structure

### Backend (`/backend`)
- **app.py** (324 lines) — Main FastAPI application with all endpoint routes
- **analysis.py** (268 lines) — Core data analysis functions using pandas/numpy
- **models.py** — SQLAlchemy ORM models: `User`, `Project`, `AnalysisHistory`
- **schemas.py** — Pydantic request/response schemas for all API endpoints
- **database.py** — SQLite database setup and session management
- **storage.py** — File I/O utilities for dataset upload/retrieval
- **data/** — Runtime directory where uploaded datasets and database are persisted

### Frontend (`/frontend`)
- **pages/_app.tsx** — Next.js App wrapper with global context
- **pages/index.tsx** — Main dashboard and UI (18+ KB: projects, uploads, analysis workflows)
- **styles/globals.css** — Global CSS styling
- **next.config.mjs** — Next.js configuration
- **tsconfig.json** — TypeScript configuration

### Docker & Deployment
- **docker-compose.yml** — Multi-container orchestration (backend on 8000, frontend on 3000)
- **backend/Dockerfile.backend** — Backend container (FastAPI + Python)
- **frontend/Dockerfile.frontend** — Frontend container (Node.js + Next.js)

## API Architecture & Key Endpoints

### Authentication
- **POST /auth/register** — Create new user (username/password)
- **POST /auth/login** — Returns JWT token

### Projects (user-scoped)
- **POST /projects** — Create project
- **GET /projects** — List all user projects
- **GET /projects/{project_id}** — Get project details

### Dataset Operations
- **POST /projects/{project_id}/upload** — Upload CSV/Excel file
- **GET /projects/{project_id}/preview** — Get dataset preview (first N rows, schema, memory usage)

### Analysis Endpoints (all return JSON results stored in `AnalysisHistory`)
- **POST /projects/{project_id}/analyze** — General data quality analysis (null %, duplicates, statistics)
- **POST /projects/{project_id}/anomalies** — Detect anomalies by column (zscore/isolation forest)
- **POST /projects/{project_id}/validate** — Run validation rules on dataset
- **POST /projects/{project_id}/clean** — Apply data cleaning operations
- **POST /projects/{project_id}/report** — Generate HTML/JSON reports

### History & Chat
- **GET /projects/{project_id}/history** — Retrieve previous analysis results with pagination
- **POST /projects/{project_id}/chat** — AI chat endpoint (Hugging Face) for natural language insights

## Key Conventions & Patterns

### Backend
- **Authentication**: JWT tokens with bcrypt password hashing (passlib)
- **Request/Response Pattern**: All endpoints use Pydantic schemas for validation
- **Error Handling**: FastAPI automatic validation errors (422) and HTTP exceptions (400/401/404/500)
- **Database Transactions**: SQLAlchemy sessions managed per-request
- **Analysis Results Storage**: All analysis results stored as JSON strings in `AnalysisHistory.results`
- **Pandas DataFrames**: Analysis functions work with in-memory DataFrames loaded from disk

### Frontend
- **Framework**: Next.js 14 with React 18 and TypeScript
- **API Communication**: Likely fetch-based HTTP calls to `process.env.NEXT_PUBLIC_API_URL` (or fallback to `http://localhost:8000`)
- **State Management**: Check `pages/index.tsx` for context/state patterns
- **Build Target**: `npm run build` outputs to `.next/` directory

### Database Schema
- **users** → relationships to projects
- **projects** → relationships to analysis_history
- **analysis_history** → stores operation type, parameters (JSON string), and results (JSON string)

### File Organization
- Datasets uploaded to `backend/data/projects/{project_id}/`
- Database file: `backend/data/datategrity.db` (SQLite)
- Analysis operations persist via `AnalysisHistory` ORM model

## Environment Variables

### Backend
- `DATABASE_URL` — SQLite connection string (default: `sqlite:///./data/datategrity.db`)
- `SECRET_KEY` — JWT signing secret (for security, use strong random value in production)
- Hugging Face API token passed via request header in chat endpoint

### Frontend
- `NEXT_PUBLIC_API_URL` — Backend API base URL (e.g., `http://localhost:8000`)

## Common Development Tasks

### Adding a New Analysis Endpoint
1. Create analysis function in `analysis.py` following pandas pattern (input: DataFrame, columns; output: dict)
2. Add Pydantic schema in `schemas.py` for request/response
3. Add route in `app.py` with `@app.post("/projects/{project_id}/<operation>")`
4. Endpoint retrieves dataset from disk, calls analysis function, stores result in `AnalysisHistory`

### Adding Database Fields
1. Update `models.py` SQLAlchemy class
2. Create migration (if using Alembic) or recreate database for development
3. Update corresponding schema in `schemas.py`

### Frontend Component Updates
- Main UI in `pages/index.tsx` (single-page app)
- API calls use backend endpoints; manage state locally or with context
- CSS in `styles/globals.css` (global scope)

## Known Limitations & Notes
- SQLite for metadata (not suitable for large-scale production deployments)
- Analysis functions load entire dataset into memory (DataFrames)
- No built-in API rate limiting or request logging
- Frontend authentication token management likely handled in `_app.tsx` context
