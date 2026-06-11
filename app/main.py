import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dependencies import build_pipeline
from app.api.routes import router
from app.exceptions import RAGException, generic_exception_handler, rag_exception_handler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline = build_pipeline()
    pipeline._vector_store.load()
    logger.info("Startup complete — index loaded: %s", pipeline._vector_store.is_loaded())
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="LedgerLens RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RAGException, rag_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.include_router(router)
