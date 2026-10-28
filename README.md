# Grounded RAG application

A V1 document-question-answering application with a Next.js UI and FastAPI backend. It indexes local `.txt` and `.md` files with ChromaDB's local ONNX implementation of `all-MiniLM-L6-v2`, stores and searches chunks in ChromaDB, and uses Gemini through Google's OpenAI-compatible API for grounded answers.

## Requirements

- Python 3.10+
- Node.js 20+
- A Google AI Studio API key for answer generation

The initial library is the text files in `docs/`. You can add or remove `.txt` and `.md` files in the UI. Files are stored locally in `docs/`; the persistent vector index is stored in `chroma_db/v1_app/`.

## Setup (Windows PowerShell)

From the repository root. Because this repository path is long, a virtual environment outside the repository is the safer Windows choice:

```powershell
if (-not (Test-Path C:\rag-v1-venv)) { py -m venv C:\rag-v1-venv }
& C:\rag-v1-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` and set `GOOGLE_API_KEY` to your Google AI Studio key. `.env` is ignored by Git. Alternatively, move or clone the repository to a shorter path such as `C:\RAG-application` and create `.venv` inside it.

Install the frontend dependencies:

```powershell
Set-Location .\frontend
npm install
Set-Location ..
```

## Run the application

Open two PowerShell terminals at the repository root and activate the environment you created in each:

Terminal 1 — API:

```powershell
& C:\rag-v1-venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload
```

The API is at `http://localhost:8000`; its interactive API reference is at `http://localhost:8000/docs`.

Terminal 2 — web UI:

```powershell
Set-Location .\frontend
npm run dev
```

Open `http://localhost:3000`. Add or select documents, adjust chunk size/overlap/top-k, ask a question, and open cited passages to verify the answer.

The default Gemini model is `gemini-3.5-flash-lite`. Set `GEMINI_MODEL` in `.env` to override it. Set `NEXT_PUBLIC_API_URL` before starting Next.js if the API is hosted at a different address; set `FRONTEND_ORIGINS` for the allowed frontend origins.

## Retrieval evaluation baseline

Run from the repository root with the documented `C:\rag-v1-venv` environment active:

```powershell
& C:\rag-v1-venv\Scripts\Activate.ps1
python -m backend.evaluate_retrieval
```

The baseline question set is `backend/evaluation_set.json`. Each question searches the full current document library. The script reports Recall@5 for answerable questions and Abstention@5 for questions whose answers are absent from the corpus. It uses chunk size 800 characters and 10% overlap so it can be repeated after changing retrieval in a later version. The first run downloads the local ONNX embedding model and builds the persistent index.

The app also applies a cosine-distance cutoff of `0.75` as a conservative starting heuristic: if no retrieved chunk passes it, the user sees that the selected documents did not yield relevant passages and Gemini is not asked to invent an answer. This is a retrieval heuristic, not a confidence score; measure and tune it against your corpus.

## API overview

- `GET /api/health` — liveness check
- `GET /api/documents` — list available text and Markdown documents
- `POST /api/documents` — add or replace a document
- `DELETE /api/documents/{filename}` — remove a document and its stored indexes
- `POST /api/ask` — retrieve passages and generate an answer with validated citations

Document edits are indexed on the next query because the index identity includes the document content and chunking settings. The response schema rejects invalid model output and citations that do not refer to retrieved passages. Provider, empty-result, and validation errors are returned as actionable API errors rather than silently treated as success.

## Project files

- `backend/main.py` — FastAPI routes and request/response validation
- `backend/rag.py` — chunking, ChromaDB ONNX indexing/retrieval, and Gemini grounding
- `backend/evaluation_set.json` — repeatable retrieval baseline questions and expected passages
- `frontend/app/` — Next.js interface
- `ask_norag_google.py`, `ask_rag_google.py` — original console experiments

## V1 report and team submission

See `REPORT.md` for the required team details, decision log, and known-failure record. Team identities and measured observations need to be completed by the project team; they are not guessed here.

# Free books from Project Gutenberg

- https://www.gutenberg.org/
- Crime and Punishment by Fyodor Dostoevsky: https://www.gutenberg.org/ebooks/2554
- Huckleberry Finn by Mark Twain: https://www.gutenberg.org/ebooks/76
