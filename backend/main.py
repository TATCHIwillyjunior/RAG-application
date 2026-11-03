import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from . import evaluation, rag, words


PROJECT_DIR = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = rag.DOCUMENTS_DIR
MAX_DOCUMENT_BYTES = rag.MAX_DOCUMENT_BYTES
logger = logging.getLogger(__name__)

load_dotenv(PROJECT_DIR / ".env")

app = FastAPI(title="RAG Application API", version="2.0.0")
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
    corpus_id: str = "project-docs"


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    document_names: list[str] = Field(min_length=1)
    corpus_id: str = "project-docs"
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


class SearchPassage(BaseModel):
    id: str
    filename: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    distance: float


class SearchResponse(BaseModel):
    passages: list[SearchPassage]
    retrieved_count: int


class EvaluationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap_percent: int = Field(default=10, ge=0, le=50)


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corpus_id: str
    configurations: list[EvaluationConfiguration] = Field(min_length=1, max_length=4)
    include_answers: bool = False


class NoContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corpus_id: str


class GradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=80)
    grade: str
    comment: str | None = None


class WordQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corpus_id: str
    word: str = Field(min_length=1, max_length=80)
    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap_percent: int = Field(default=10, ge=0, le=50)


class WordCoverageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corpus_id: str
    question_set_id: str
    chunk_size: int = Field(default=800, ge=100, le=2000)
    overlap_percent: int = Field(default=10, ge=0, le=50)


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


def _document_path(filename: str, corpus_id: str = "project-docs") -> Path:
    _validate_filename(filename)
    try:
        return rag.get_corpus_dir(corpus_id) / filename
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _search_passages(
    question: str,
    document_names: list[str],
    corpus_id: str,
    chunk_size: int,
    overlap_percent: int,
    top_k: int,
) -> list[rag.Passage]:
    selected_names = list(dict.fromkeys(document_names))
    if not selected_names:
        raise HTTPException(status_code=422, detail="Select at least one document.")
    if len(selected_names) != len(document_names):
        raise HTTPException(
            status_code=422, detail="A document was selected more than once."
        )
    for filename in selected_names:
        if not _document_path(filename, corpus_id).is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Document '{filename}' was not found in '{corpus_id}'.",
            )
    try:
        return rag.retrieve_passages(
            question=question,
            filenames=selected_names,
            chunk_size=chunk_size,
            overlap_percent=overlap_percent,
            top_k=top_k,
            corpus_id=corpus_id,
        )
    except rag.RetrievalUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _evaluation_search(payload: dict[str, Any]) -> list[rag.Passage]:
    return _search_passages(
        question=payload["question"],
        document_names=payload["document_names"],
        corpus_id=payload["corpus_id"],
        chunk_size=payload["chunk_size"],
        overlap_percent=payload["overlap_percent"],
        top_k=payload["top_k"],
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/corpora")
def list_corpora() -> list[dict[str, Any]]:
    names = {
        "kestrel": "Kestrel KB",
        "vellora": "Vellora Duo",
        "project-docs": "Project document library (V1)",
    }
    return [
        {
            "id": corpus_id,
            "name": label,
            "documents": [
                {"filename": path.name, "size_bytes": path.stat().st_size}
                for path in rag.list_corpus_documents(corpus_id)
            ],
        }
        for corpus_id, label in names.items()
    ]


@app.get("/api/documents", response_model=list[DocumentInfo])
def list_documents(corpus_id: str = "project-docs") -> list[DocumentInfo]:
    directory = _document_path("placeholder.txt", corpus_id).parent
    directory.mkdir(parents=True, exist_ok=True)
    documents = [
        DocumentInfo(filename=path.name, size_bytes=path.stat().st_size)
        for path in rag.list_corpus_documents(corpus_id)
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

    directory = _document_path(filename, upload.corpus_id).parent
    directory.mkdir(parents=True, exist_ok=True)
    path = _document_path(filename, upload.corpus_id)
    try:
        path.write_bytes(content_bytes)
    except OSError as error:
        logger.exception("Could not save uploaded document %s", filename)
        raise HTTPException(
            status_code=500, detail="The document could not be saved to the local library."
        ) from error
    return DocumentInfo(filename=filename, size_bytes=len(content_bytes))


@app.delete("/api/documents/{filename}", status_code=204)
def delete_document(filename: str, corpus_id: str = "project-docs") -> Response:
    path = _document_path(filename, corpus_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        rag.delete_document_indexes(filename, corpus_id)
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


def search(request: AskRequest) -> SearchResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question.")
    passages = _search_passages(
        question,
        request.document_names,
        request.corpus_id,
        request.chunk_size,
        request.overlap_percent,
        request.top_k,
    )
    return SearchResponse(
        passages=[
            SearchPassage(
                id=passage.id,
                filename=passage.filename,
                chunk_index=passage.chunk_index,
                start_char=passage.start_char,
                end_char=passage.end_char,
                text=passage.text,
                distance=passage.distance,
            )
            for passage in passages
        ],
        retrieved_count=len(passages),
    )


@app.post("/api/search", response_model=SearchResponse)
def search_route(request: AskRequest) -> SearchResponse:
    return search(request)


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question.")
    passages = _search_passages(
        question,
        request.document_names,
        request.corpus_id,
        request.chunk_size,
        request.overlap_percent,
        request.top_k,
    )
    try:
        answer = rag.generate_grounded_answer(question, passages)
    except rag.ModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except rag.InvalidModelResponse as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

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


@app.get("/api/evaluations/question-sets")
def question_sets() -> list[dict[str, Any]]:
    return [
        {
            "corpus_id": corpus_id,
            "question_count": len(evaluation.load_questions(corpus_id)),
            "questions": evaluation.load_questions(corpus_id),
        }
        for corpus_id in evaluation.QUESTION_SETS
    ]


@app.post("/api/evaluations")
def run_evaluation(request: EvaluationRequest) -> list[dict[str, Any]]:
    try:
        results = []
        for configuration in request.configurations:
            results.append(
                evaluation.run_retrieval_evaluation(
                    request.corpus_id,
                    configuration.model_dump(),
                    _evaluation_search,
                    request.include_answers,
                )
            )
        return results
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except rag.ModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except rag.InvalidModelResponse as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/evaluations/no-context")
def run_no_context(request: NoContextRequest) -> dict[str, Any]:
    try:
        return evaluation.run_no_context_evaluation(request.corpus_id)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except rag.ModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except rag.InvalidModelResponse as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/evaluations/runs")
def list_evaluation_runs() -> list[dict[str, Any]]:
    try:
        return evaluation.list_runs()
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/api/evaluations/runs/{run_id}")
def get_evaluation_run(run_id: str) -> list[dict[str, Any]]:
    try:
        return evaluation.get_run(run_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/api/evaluations/runs/{run_id}/grades")
def grade_evaluation_question(run_id: str, request: GradeRequest) -> dict[str, Any]:
    try:
        return evaluation.save_grade(
            run_id, request.question_id, request.grade, request.comment
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/api/words")
def corpus_words(
    corpus_id: str = "vellora",
    chunk_size: int = Query(default=800, ge=100, le=2000),
    overlap_percent: int = Query(default=10, ge=0, le=50),
) -> dict[str, Any]:
    try:
        result = words.analyze_corpus(corpus_id, chunk_size, overlap_percent)
        result.pop("_chunks")
        return result
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/words/search")
def search_word(request: WordQuery) -> dict[str, Any]:
    try:
        return words.find_word_chunks(
            request.corpus_id,
            request.word,
            request.chunk_size,
            request.overlap_percent,
        )
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/words/coverage")
def word_coverage(request: WordCoverageRequest) -> list[dict[str, Any]]:
    try:
        return words.question_coverage(
            request.corpus_id,
            request.question_set_id,
            request.chunk_size,
            request.overlap_percent,
        )
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
