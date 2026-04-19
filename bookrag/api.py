"""FastAPI application for BookRAG."""

from __future__ import annotations

from typing import Annotated, Any

import uvicorn
from fastapi import Cookie, Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from bookrag.services import BookRAGService
from bookrag.settings import AppSettings
from bookrag.web import render_dashboard, render_login_page, render_setup_page


class LoginRequest(BaseModel):
    username: str
    password: str


class ProviderCreateRequest(BaseModel):
    name: str
    provider_type: str
    api_key: str
    base_url: str | None = None
    default_embedding_model: str | None = None
    default_chat_model: str | None = None
    default_ocr_model: str | None = None


class LibraryCreateRequest(BaseModel):
    name: str
    description: str | None = None


class SeriesCreateRequest(BaseModel):
    library_id: int
    name: str


class IngestRequest(BaseModel):
    embedding_provider_id: int
    embedding_model: str
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    ocr_provider_id: int | None = None
    ocr_model: str | None = None
    ocr_mode: str = "disabled"
    confirm_ocr_cost: bool = False


class BoundaryRequest(BaseModel):
    library_id: int
    scope_type: str
    scope_id: int
    boundary_type: str
    active_book_id: int | None = None
    active_chapter_index: int | None = None


class QueryRequest(BaseModel):
    library_id: int
    question: str
    top_k: int | None = None
    spoiler_mode: str = "full_context"
    context_mode: str | None = None
    active_book_id: int | None = None
    active_chapter_index: int | None = None


class AnswerRequest(QueryRequest):
    chat_provider_id: int
    chat_model: str
    temperature: float = 0.2
    max_tokens: int = 1200


def create_app(service: BookRAGService | None = None) -> FastAPI:
    """Create the FastAPI app."""
    service = service or BookRAGService()
    app = FastAPI(title=service.settings.app_name)

    def current_user(
        authorization: Annotated[str | None, Header()] = None,
        bookrag_session: Annotated[str | None, Cookie()] = None,
    ) -> dict[str, Any]:
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        elif bookrag_session:
            token = bookrag_session
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            return service.authenticate_token(token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    def dashboard_html(flash: str | None = None, answer: str | None = None) -> str:
        libraries = service.list_libraries() or [service.ensure_default_library()]
        providers = service.list_providers()
        books_by_library = {library["id"]: service.list_books(library["id"]) for library in libraries}
        series_by_library = {library["id"]: service.list_series(library["id"]) for library in libraries}
        jobs = service.list_jobs()
        return render_dashboard(libraries, providers, books_by_library, series_by_library, jobs, flash=flash, answer=answer)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def home(bookrag_session: Annotated[str | None, Cookie()] = None) -> str:
        if not service.admin_exists():
            return render_setup_page()
        if not bookrag_session:
            return render_login_page()
        try:
            service.authenticate_token(bookrag_session)
        except ValueError:
            return render_login_page("Session expired. Please sign in again.")
        return dashboard_html()

    @app.post("/setup")
    async def setup(username: Annotated[str, Form()], password: Annotated[str, Form()]) -> Response:
        try:
            service.setup_admin(username, password)
            login_result = service.login(username, password)
            response = RedirectResponse("/", status_code=303)
            response.set_cookie("bookrag_session", login_result["token"], httponly=True, samesite="lax")
            return response
        except ValueError as exc:
            return HTMLResponse(render_setup_page(str(exc)), status_code=400)

    @app.post("/login")
    async def login(username: Annotated[str, Form()], password: Annotated[str, Form()]) -> Response:
        try:
            result = service.login(username, password)
            response = RedirectResponse("/", status_code=303)
            response.set_cookie("bookrag_session", result["token"], httponly=True, samesite="lax")
            return response
        except ValueError as exc:
            return HTMLResponse(render_login_page(str(exc)), status_code=400)

    @app.post("/logout")
    async def logout() -> Response:
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie("bookrag_session")
        return response

    @app.post("/auth/setup")
    async def api_setup(request: LoginRequest) -> dict[str, Any]:
        return service.setup_admin(request.username, request.password)

    @app.post("/auth/login")
    async def api_login(request: LoginRequest) -> dict[str, Any]:
        return service.login(request.username, request.password, token_name="api-token")

    @app.get("/providers")
    async def api_list_providers(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
        return service.list_providers()

    @app.post("/providers")
    async def api_create_provider(
        request: ProviderCreateRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.create_provider(**request.model_dump())

    @app.post("/web/providers")
    async def web_create_provider(
        name: Annotated[str, Form()],
        provider_type: Annotated[str, Form()],
        api_key: Annotated[str, Form()],
        base_url: Annotated[str | None, Form()] = None,
        default_embedding_model: Annotated[str | None, Form()] = None,
        default_chat_model: Annotated[str | None, Form()] = None,
        default_ocr_model: Annotated[str | None, Form()] = None,
        user: dict[str, Any] = Depends(current_user),
    ) -> HTMLResponse:
        service.create_provider(
            name=name,
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            default_embedding_model=default_embedding_model,
            default_chat_model=default_chat_model,
            default_ocr_model=default_ocr_model,
        )
        return HTMLResponse(dashboard_html(flash="Provider saved."))

    @app.get("/libraries")
    async def api_list_libraries(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
        return service.list_libraries()

    @app.post("/libraries")
    async def api_create_library(
        request: LibraryCreateRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.create_library(request.name, request.description)

    @app.post("/web/libraries")
    async def web_create_library(
        name: Annotated[str, Form()],
        description: Annotated[str | None, Form()] = None,
        user: dict[str, Any] = Depends(current_user),
    ) -> HTMLResponse:
        service.create_library(name, description)
        return HTMLResponse(dashboard_html(flash="Library created."))

    @app.get("/libraries/{library_id}")
    async def api_get_library(
        library_id: int,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        library = service.get_library(library_id)
        library["books"] = service.list_books(library_id)
        library["series"] = service.list_series(library_id)
        return library

    @app.get("/libraries/{library_id}/books")
    async def api_list_books(
        library_id: int,
        user: dict[str, Any] = Depends(current_user),
    ) -> list[dict[str, Any]]:
        return service.list_books(library_id)

    @app.post("/libraries/{library_id}/books/upload")
    async def api_upload_book(
        library_id: int,
        file: UploadFile = File(...),
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        contents = await file.read()
        return service.upload_book(library_id, file.filename, contents)

    @app.post("/web/libraries/{library_id}/books/upload")
    async def web_upload_book(
        library_id: int,
        file: UploadFile = File(...),
        user: dict[str, Any] = Depends(current_user),
    ) -> HTMLResponse:
        contents = await file.read()
        service.upload_book(library_id, file.filename, contents)
        return HTMLResponse(dashboard_html(flash="Book uploaded."))

    @app.post("/books/{book_id}/ingest")
    async def api_ingest_book(
        book_id: int,
        request: IngestRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.ingest_book(book_id=book_id, **request.model_dump())

    @app.post("/web/books/{book_id}/ingest")
    async def web_ingest_book(
        book_id: int,
        embedding_provider_id: Annotated[int, Form()],
        embedding_model: Annotated[str, Form()],
        ocr_mode: Annotated[str, Form()] = "disabled",
        ocr_provider_id: Annotated[str | None, Form()] = None,
        ocr_model: Annotated[str | None, Form()] = None,
        confirm_ocr_cost: Annotated[str | None, Form()] = None,
        user: dict[str, Any] = Depends(current_user),
    ) -> HTMLResponse:
        service.ingest_book(
            book_id=book_id,
            embedding_provider_id=embedding_provider_id,
            embedding_model=embedding_model,
            ocr_mode=ocr_mode,
            ocr_provider_id=int(ocr_provider_id) if ocr_provider_id else None,
            ocr_model=ocr_model,
            confirm_ocr_cost=confirm_ocr_cost == "yes",
        )
        return HTMLResponse(dashboard_html(flash=f"Book {book_id} indexed."))

    @app.get("/jobs")
    async def api_list_jobs(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
        return service.list_jobs()

    @app.get("/jobs/{job_id}")
    async def api_get_job(job_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        return service.get_job(job_id)

    @app.post("/series")
    async def api_create_series(
        request: SeriesCreateRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.create_series(request.library_id, request.name)

    @app.post("/web/series")
    async def web_create_series(
        library_id: Annotated[int, Form()],
        name: Annotated[str, Form()],
        user: dict[str, Any] = Depends(current_user),
    ) -> HTMLResponse:
        service.create_series(library_id, name)
        return HTMLResponse(dashboard_html(flash="Series created."))

    @app.post("/series/{series_id}/books/reorder")
    async def api_reorder_series(
        series_id: int,
        payload: list[dict[str, int]],
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.reorder_series_books(series_id, payload)

    @app.post("/web/series/{series_id}/reorder")
    async def web_reorder_series(
        series_id: int,
        ordered_book_ids: Annotated[str, Form()],
        user: dict[str, Any] = Depends(current_user),
    ) -> HTMLResponse:
        items = [
            {"book_id": int(book_id.strip()), "sort_order": index}
            for index, book_id in enumerate(ordered_book_ids.split(","), start=1)
            if book_id.strip()
        ]
        service.reorder_series_books(series_id, items)
        return HTMLResponse(dashboard_html(flash="Series order updated."))

    @app.put("/boundaries")
    async def api_set_boundary(
        request: BoundaryRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.set_boundary(**request.model_dump())

    @app.post("/query/context")
    async def api_query_context(
        request: QueryRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.query_context(**request.model_dump())

    @app.post("/chat/answer")
    async def api_answer_question(
        request: AnswerRequest,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        return service.answer_question(**request.model_dump())

    @app.post("/web/chat")
    async def web_chat(
        library_id: Annotated[int, Form()],
        question: Annotated[str, Form()],
        chat_provider_id: Annotated[int, Form()],
        chat_model: Annotated[str, Form()],
        spoiler_mode: Annotated[str, Form()] = "full_context",
        context_mode: Annotated[str | None, Form()] = None,
        active_book_id: Annotated[str | None, Form()] = None,
        active_chapter_index: Annotated[str | None, Form()] = None,
        user: dict[str, Any] = Depends(current_user),
    ) -> HTMLResponse:
        result = service.answer_question(
            library_id=library_id,
            question=question,
            chat_provider_id=chat_provider_id,
            chat_model=chat_model,
            spoiler_mode=spoiler_mode,
            context_mode=context_mode,
            active_book_id=int(active_book_id) if active_book_id else None,
            active_chapter_index=int(active_chapter_index) if active_chapter_index else None,
        )
        answer = result["answer"] + "\n\nCitations:\n" + "\n".join(
            f"- {item['book_title']} / {item.get('chapter_title') or 'Unknown'} "
            f"(chapter {item.get('chapter_index')}, page {item.get('page_number')})"
            for item in result["context"]["citations"]
        )
        return HTMLResponse(dashboard_html(answer=answer))

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return app


def main() -> None:
    """Run the API server."""
    settings = AppSettings.load()
    uvicorn.run("bookrag.api:create_app", host=settings.api_host, port=settings.api_port, factory=True)
