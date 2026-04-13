from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.rag_service import RAGService
from app.services.ingest_service import IngestService
from app.services.quiz_service import QuizService
from app.utils.app_discovery import get_available_applications
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
rag_service = RAGService()
ingest_service = IngestService()
quiz_service = QuizService()


class ChatRequest(BaseModel):
    application: str
    question: str


class IngestRequest(BaseModel):
    application: str


class QuizRequest(BaseModel):
    application: str
    level: str  # Beginner | Novice | Expert


@router.get("/applications")
async def list_applications():
    apps = get_available_applications()
    return {"applications": apps}


@router.get("/status/{application}")
async def get_status(application: str):
    exists = rag_service.vectorstore_exists(application)
    return {"application": application, "vectorstore_ready": exists}


@router.post("/ingest")
async def ingest_documents(request: IngestRequest):
    try:
        result = ingest_service.ingest(request.application)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        result = await rag_service.chat(request.application, request.question)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load/{application}")
async def load_knowledge_base(application: str):
    try:
        result = rag_service.load_index(application, force_reload=True)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Load KB error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh/{application}")
async def refresh_knowledge_base(application: str):
    """Force re-ingest + evict cache + reload fresh index."""
    try:
        ingest_result = ingest_service.ingest(application, force=True)
        rag_service.evict_cache(application)
        load_result = rag_service.load_index(application, force_reload=True)
        return {**ingest_result, **load_result, "refreshed": True}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quiz/generate")
async def generate_quiz(request: QuizRequest):
    valid_levels = {"Beginner", "Novice", "Expert"}
    if request.level not in valid_levels:
        raise HTTPException(status_code=400, detail=f"Level must be one of: {valid_levels}")
    try:
        questions = await quiz_service.generate_quiz(request.application, request.level)
        return {"questions": questions, "level": request.level, "application": request.application}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Quiz generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
