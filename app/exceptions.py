from fastapi import Request
from fastapi.responses import JSONResponse


class RAGException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class IndexNotFoundError(RAGException):
    def __init__(self, message: str = "Vector index is empty or not loaded"):
        super().__init__("INDEX_NOT_FOUND", message, 404)


class ProviderUnavailableError(RAGException):
    def __init__(self, message: str = "Embedding or LLM provider is unreachable"):
        super().__init__("PROVIDER_UNAVAILABLE", message, 503)


class ValidationError(RAGException):
    def __init__(self, message: str):
        super().__init__("VALIDATION_ERROR", message, 400)


class UnsupportedFileTypeError(RAGException):
    def __init__(self, ext: str):
        supported = "pdf, docx, xlsx, xls, txt, csv, md, xml"
        msg = f"File type '{ext}' is not supported. Supported: {supported}" if ext else f"No file extension detected. Supported: {supported}"
        super().__init__("UNSUPPORTED_FILE_TYPE", msg, 400)


class FileParseError(RAGException):
    def __init__(self, filename: str, reason: str):
        super().__init__("FILE_PARSE_ERROR", f"Could not parse '{filename}': {reason}", 422)


class EmptyFileError(RAGException):
    def __init__(self, filename: str):
        super().__init__("EMPTY_FILE", f"File '{filename}' produced no extractable text", 400)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def rag_exception_handler(request: Request, exc: RAGException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_error_body("INTERNAL_ERROR", "An unexpected error occurred"),
    )
