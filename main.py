"""
SSE Delta Log Aggregator - FastAPI Server

Provides web interface for parsing SSE delta logs.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.auth.jwt import get_optional_user
from app.config import get_settings
from app.database import close_db, get_db, init_db
from app.history import router as history_router
from app.history.service import HistoryService
from app.models import User
from app.schemas import ParseHistoryCreate
from parser_logic import (
    CustomExtractor,
    StreamFormat,
    format_json,
    get_supported_formats,
    parse_sse_logs,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="SSE Delta Log Aggregator",
    description="Parse and combine fragmented SSE delta logs into complete text and JSON",
    version="0.2.0",
    lifespan=lifespan,
)

# Session middleware for OAuth state
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret_key,
)

# Include routers
app.include_router(auth_router)
app.include_router(history_router)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


class ParseRequest(BaseModel):
    """Request body for parse endpoint."""

    raw_logs: str
    format_type: str = "auto"  # auto, orchestrator, anthropic, gemini, playground, mas_response, custom
    custom_extractor: dict | None = None  # Custom extraction rules (for format_type="custom")


class ParseResponse(BaseModel):
    """Response from parse endpoint."""

    raw_text: str
    json_data: dict | None
    json_formatted: str | None
    usage: dict | None
    usage_formatted: str | None
    metadata: dict | None
    metadata_formatted: str | None
    chunk_count: int
    errors: list[str]
    history_id: str | None = None  # ID of saved history (if logged in)
    detected_format: str | None = None  # Auto-detected format (when format_type="auto")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main UI page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/parse", response_model=ParseResponse)
async def parse_logs(
    req: ParseRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
):
    """
    Parse SSE delta logs and return combined result.

    Supports formats:
    - auto: Auto-detect format from log content
    - orchestrator: OpenAI/LLM Orchestrator (choices[0].delta.content)
    - anthropic: Anthropic Claude (content_block_delta)
    - gemini: Google Gemini (candidates[].content.parts[])
    - playground: Playground (JSON Patch op: add/append)
    - mas_response: MAS Response (multi-agent workflow with content[].text)
    - custom: User-defined JSONPath extraction rules

    Only extracts data actually present in the logs.
    No fabrication of missing fields.

    If user is logged in, saves the result to history.
    """
    format_mapping = {
        "auto": StreamFormat.AUTO,
        "orchestrator": StreamFormat.ORCHESTRATOR,
        "anthropic": StreamFormat.ANTHROPIC,
        "gemini": StreamFormat.GEMINI,
        "playground": StreamFormat.PLAYGROUND,
        "mas_response": StreamFormat.MAS_RESPONSE,
        "custom": StreamFormat.CUSTOM,
    }
    format_enum = format_mapping.get(req.format_type, StreamFormat.AUTO)

    # Parse with custom extractor if provided
    custom_ext = None
    if format_enum == StreamFormat.CUSTOM and req.custom_extractor:
        custom_ext = CustomExtractor.from_dict(req.custom_extractor)

    result = parse_sse_logs(req.raw_logs, format_enum, custom_extractor=custom_ext)

    # Save to history if user is logged in
    history_id = None
    user = await get_optional_user(db, access_token)
    if user:
        service = HistoryService(db)
        history = await service.create(
            user=user,
            data=ParseHistoryCreate(
                format_type=req.format_type,
                input_logs=req.raw_logs,
                raw_text=result.raw_text,
                json_data=result.json_data,
                usage_data=result.usage,
                metadata_info=result.metadata,
                chunk_count=result.chunk_count,
            ),
        )
        history_id = str(history.id)

    return ParseResponse(
        raw_text=result.raw_text,
        json_data=result.json_data,
        json_formatted=format_json(result.json_data) if result.json_data else None,
        usage=result.usage,
        usage_formatted=format_json(result.usage) if result.usage else None,
        metadata=result.metadata,
        metadata_formatted=format_json(result.metadata) if result.metadata else None,
        chunk_count=result.chunk_count,
        errors=result.errors,
        history_id=history_id,
        detected_format=result.detected_format,
    )


@app.get("/formats")
async def list_formats():
    """Get list of supported SSE formats."""
    return {"formats": get_supported_formats()}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
