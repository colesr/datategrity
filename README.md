# datategrity
An all-in-one solution for data quality analysis, validation, and AI-powered insights.

## Architecture
- `backend/` — Python FastAPI backend, dataset persistence, analysis endpoints, local SQLite metadata.
- `frontend/` — Next.js React app for project, upload, analysis, and reporting workflows.
- `docker-compose.yml` — Local container setup for frontend and backend.

## Getting Started
### Backend
```bash
git clone <repo>
cd datategrity/backend
python -m pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd datategrity/frontend
npm install
npm run dev
```

### Docker
```bash
docker compose up --build
```

## Notes
- Projects and uploaded datasets are persisted in `backend/data/`.
- Authentication is local and token-based.
- The backend exposes analysis, anomaly detection, validation, cleaning, and reporting endpoints.
