import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from . import rag


PROJECT_DIR = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = rag.DOCUMENTS_DIR
MAX_DOCUMENT_BYTES = rag.MAX_DOCUMENT_BYTES
logger = logging.getLogger(__name__)

load_dotenv(PROJECT_DIR / ".env")

app = FastAPI(title="RAG Application API", version="1.0.0")
origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


class DocumentUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content: str


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    document_names: list[str] = Field(min_length=1)
    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap_percent: int = Field(default=10, ge=0, le=50)
    top_k: int = Field(default=5, ge=1, le=10)


class DocumentInfo(BaseModel):
    filename: str
    size_bytes: int


class Reference(BaseModel):
    id: str
    filename: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str


class AskResponse(BaseModel):
    answer: str
    references: list[Reference]
    retrieved_count: int
    model: str


def _validate_filename(filename: str) -> str:
    windows_reserved_names = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
    stem = Path(filename).stem.casefold()
    invalid_characters = '<>:"|?*'
    if (
        filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or any(
            ord(character) < 32 or character in invalid_characters
            for character in filename
        )
        or filename.endswith((" ", "."))
        or Path(filename).name != filename
        or Path(filename).suffix.lower() not in {".txt", ".md"}
        or filename.startswith(".")
        or stem in windows_reserved_names
    ):
        raise HTTPException(
            status_code=400, detail="Use a plain .txt or .md filename without folders."
        )
    return filename


def _document_path(filename: str) -> Path:
    _validate_filename(filename)
    return DOCUMENTS_DIR / filename


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/documents", response_model=list[DocumentInfo])
def list_documents() -> list[DocumentInfo]:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    documents = [
        DocumentInfo(filename=path.name, size_bytes=path.stat().st_size)
        for path in DOCUMENTS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}
    ]
    return sorted(documents, key=lambda document: document.filename.casefold())


@app.post("/api/documents", response_model=DocumentInfo, status_code=201)
def upload_document(upload: DocumentUpload) -> DocumentInfo:
    filename = _validate_filename(upload.filename.strip())
    content_bytes = upload.content.encode("utf-8")
    if not content_bytes.strip():
        raise HTTPException(status_code=400, detail="The document cannot be empty.")
    if len(content_bytes) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413, detail="Documents must be 5 MB or smaller."
        )

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _document_path(filename)
    try:
        path.write_bytes(content_bytes)
    except OSError as error:
        logger.exception("Could not save uploaded document %s", filename)
        raise HTTPException(
            status_code=500, detail="The document could not be saved to the local library."
        ) from error
    return DocumentInfo(filename=filename, size_bytes=len(content_bytes))


@app.delete("/api/documents/{filename}", status_code=204)
def delete_document(filename: str) -> Response:
    path = _document_path(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        rag.delete_document_indexes(filename)
    except rag.RetrievalUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    try:
        path.unlink()
    except OSError as error:
        logger.exception("Could not delete document %s", filename)
        raise HTTPException(
            status_code=500, detail="The document could not be removed from the local library."
        ) from error
    return Response(status_code=204)


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question.")
    selected_names = list(dict.fromkeys(request.document_names))
    if len(selected_names) != len(request.document_names):
        raise HTTPException(
            status_code=422, detail="A document was selected more than once."
        )
    for filename in selected_names:
        path = _document_path(filename)
        if not path.is_file():
            raise HTTPException(
                status_code=404, detail=f"Document '{filename}' was not found."
            )

    try:
        passages = rag.retrieve_passages(
            question=question,
            filenames=selected_names,
            chunk_size=request.chunk_size,
            overlap_percent=request.overlap_percent,
            top_k=request.top_k,
        )
        answer = rag.generate_grounded_answer(question, passages)
    except rag.ModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except rag.RetrievalUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except rag.InvalidModelResponse as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    references = [
        Reference(
            id=passage.id,
            filename=passage.filename,
            chunk_index=passage.chunk_index,
            start_char=passage.start_char,
            end_char=passage.end_char,
            text=passage.text,
        )
        for passage in passages
        if passage.id in answer.citation_ids
    ]
    return AskResponse(
        answer=answer.answer,
        references=references,
        retrieved_count=len(passages),
        model=os.getenv("GEMINI_MODEL", rag.DEFAULT_MODEL),
    )
