import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi as fastapi_get_openapi
from fastapi.responses import JSONResponse

from app.api.dependencies import build_pipeline
from app.api.routes import router
from app.config import settings
from app.exceptions import RAGException, generic_exception_handler, rag_exception_handler

# Only a dev environment (APP_ENV=dev) loads the local .env into the process
# environment; in production we rely solely on injected env vars. This also
# populates os.environ for any library that reads keys directly.
if settings.is_dev:
    from dotenv import load_dotenv

    load_dotenv()

logging.basicConfig(
    level=settings.log_level.upper(),
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
# OpenAPI 3.1 (FastAPI's default) describes file fields with contentMediaType,
# which Swagger UI doesn't render as a file picker — it falls back to a text
# input. Pin to 3.0.2 so UploadFile fields use format: binary instead.
app.openapi_version = "3.0.2"


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = fastapi_get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        routes=app.routes,
    )
    # FastAPI's UploadFile always reports its OpenAPI 3.1 `contentMediaType`
    # shape regardless of openapi_version, and Swagger UI doesn't render
    # array-of-contentMediaType items as file pickers — only the classic
    # OpenAPI 3.0 `format: binary` shape. Rewrite it in place.
    for component_schema in schema.get("components", {}).get("schemas", {}).values():
        for prop in component_schema.get("properties", {}).values():
            items = prop.get("items")
            if isinstance(items, dict) and items.get("contentMediaType"):
                items.pop("contentMediaType")
                items["format"] = "binary"
            if prop.get("contentMediaType"):
                prop.pop("contentMediaType")
                prop["format"] = "binary"
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


# Browsers reject "*" origins together with credentials, so force credentials
# off whenever any origin is the wildcard.
_cors_origins = settings.cors_allow_origins_list
_cors_credentials = settings.cors_allow_credentials and "*" not in _cors_origins
if settings.cors_allow_credentials and not _cors_credentials:
    logger.warning(
        "CORS_ALLOW_CREDENTIALS ignored because CORS_ALLOW_ORIGINS includes '*' "
        "(browsers forbid this combination)."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RAGException, rag_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.include_router(router)
