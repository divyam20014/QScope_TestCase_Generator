from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import ai, coverage, documents, exports, generation, projects, quality, rag, requirements, system
from app.core.config import get_settings
from app.core.paths import PathTraversalError

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PathTraversalError)
def _handle_path_traversal(request: Request, exc: PathTraversalError) -> JSONResponse:
    # Never echo exc's message back - it contains a resolved filesystem path.
    return JSONResponse(status_code=400, content={"detail": "Invalid id"})

app.include_router(system.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(ai.router)
app.include_router(requirements.router)
app.include_router(generation.router)
app.include_router(coverage.router)
app.include_router(quality.router)
app.include_router(exports.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
