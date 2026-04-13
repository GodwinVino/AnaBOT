# AnaBOT Version 2

Production-grade portable RAG-based AI assistant with multi-application support and AI CAFE integration.

## Quick Start

### First Time (Dev Machine)
```
1. Edit .env — add your AI_CAFE_API_KEY
2. Double-click setup.bat   (creates venv, installs deps, downloads model)
3. Add documents to data/applications/<AppName>/
4. Double-click run.bat
5. Open http://localhost:8000
```

### Target Machine (after zip transfer)
```
1. Unzip the project
2. Edit .env — add your AI_CAFE_API_KEY
3. Double-click run.bat
4. Open http://localhost:8000
```

## Folder Structure
```
/backend          FastAPI application
/frontend         Static HTML/JS UI
/data/applications/<AppName>/   Source documents (PDF, DOCX, XLSX)
/vectorstore/<AppName>/         FAISS indexes (auto-generated)
/venv             Python virtual environment
.env              API keys and config
run.bat           Start the server
setup.bat         First-time setup
ingest.bat        Manual ingestion CLI
```

## Adding a New Application
1. Create folder: `data/applications/MyApp/`
2. Drop PDF/DOCX/XLSX files inside
3. Start server and select "MyApp" from dropdown
4. Click "Load KB" — it auto-ingests on first load

## Environment Variables
```
AI_CAFE_API_KEY=your_key
DEPLOYMENT_NAME=gpt-4.1
API_VERSION=2024-12-01-preview
```

## API Endpoints
- `GET  /api/applications`       — list available apps
- `GET  /api/status/{app}`       — check if vectorstore exists
- `POST /api/ingest`             — ingest documents
- `POST /api/load/{app}`         — load FAISS index into memory
- `POST /api/chat`               — RAG chat query
