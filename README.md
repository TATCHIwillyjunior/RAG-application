# Grounded RAG application

A document-question-answering application with a Next.js UI and FastAPI backend. V2 adds selectable Kestrel KB and Vellora Duo corpora, repeatable retrieval and no-context evaluations, answer grading, and corpus word analytics. It indexes local `.txt` and `.md` files with ChromaDB's local ONNX implementation of `all-MiniLM-L6-v2` and uses Gemini through Google's OpenAI-compatible API for grounded answers.

## Requirements

- Python 3.10+
- Node.js 20+
- A Google AI Studio API key for answer generation

The original V1 document library is `docs/`. V2 also includes the Kestrel KB in `corpora/kestrel/docs/` and the Vellora Duo corpus in `corpora/vellora/docs/`. Uploads and removals are scoped to the currently selected corpus. V2 stores its persistent vector index separately in `chroma_db/v2_app/`, leaving any existing V1 index untouched.

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

Open `http://localhost:3000`. Select a corpus and use the Ask, Words, or Evaluation workspace tabs. Add or select documents, adjust chunk size/overlap/top-k, ask questions, inspect corpus vocabulary and question-term coverage, or run the repeatable evaluation.

The default Gemini model is `gemini-3.5-flash-lite`. Set `GEMINI_MODEL` in `.env` to override it. Set `NEXT_PUBLIC_API_URL` before starting Next.js if the API is hosted at a different address; set `FRONTEND_ORIGINS` for the allowed frontend origins.

## V2 retrieval evaluation

Run from the repository root with the documented `C:\rag-v1-venv` environment active:

```powershell
& C:\rag-v1-venv\Scripts\Activate.ps1
python -m backend.evaluate_retrieval --corpus all
```

The CLI calls the same FastAPI `/api/search` route as the app and runs each corpus question set with two default chunk configurations: 800 characters/10% overlap and 400 characters/10% overlap. It saves JSONL result files under `evaluation/results/`. Each record includes the retrieved passages, evidence matches, and hit rate and mean evidence recall at k=1, 3, 5, and 10; the summary is broken down by question type. Unanswerable questions remain in the saved run but are excluded from those retrieval scores.

To reproduce the original V1 Recall@5/Abstention@5 check against the project document library:

```powershell
python -m backend.evaluate_retrieval --v1-baseline
```

Choose one corpus with `--corpus kestrel` or `--corpus vellora`. Override or add configurations using repeatable `--configuration NAME:CHUNK_SIZE:OVERLAP` options, for example `--configuration narrow:300:15`. Optional `--generate-answers` generates grounded answers for retrieved passages. Optional `--no-context` asks Gemini each question without retrieval and has Gemini judge whether the response matches the reference; these options make external Gemini calls and use API quota. They are off by default. The Words tab shows full-corpus word frequency and distinct chunk counts, opens matching chunks, and reports question terms that do not occur in the corpus.

The app also applies a cosine-distance cutoff of `0.75` as a conservative starting heuristic: if no retrieved chunk passes it, the user sees that the selected documents did not yield relevant passages and Gemini is not asked to invent an answer. This is a retrieval heuristic, not a confidence score; measured evaluation runs should inform future tuning.

## API overview

- `GET /api/health` — liveness check
- `GET /api/corpora` — list the V1 library and V2 corpora
- `GET /api/documents?corpus_id=vellora` — list documents in a corpus (omitting the parameter retains V1 behavior)
- `POST /api/documents` — add or replace a document in the specified corpus
- `DELETE /api/documents/{filename}?corpus_id=vellora` — remove a corpus document and its stored indexes
- `POST /api/search` — retrieve ranked passages without generating an answer
- `POST /api/ask` — retrieve passages and generate an answer with validated citations
- `POST /api/evaluations` — run one or more chunking configurations and save JSONL output
- `POST /api/evaluations/no-context` — run optional Gemini no-context answer and judge checks
- `POST /api/evaluations/runs/{run_id}/grades` — persist a manual grade in a retrieval result
- `GET /api/words` — return corpus frequency and chunk statistics
- `POST /api/words/search` and `/api/words/coverage` — inspect matching chunks and question-term coverage

Document edits are indexed on the next query because the index identity includes the document content and chunking settings. The response schema rejects invalid model output and citations that do not refer to retrieved passages. Provider, empty-result, and validation errors are returned as actionable API errors rather than silently treated as success.

## Project files

- `backend/main.py` — FastAPI routes and request/response validation
- `backend/rag.py` — chunking, ChromaDB ONNX indexing/retrieval, and Gemini grounding
- `backend/evaluation.py` — V2 question sets, metrics, JSONL result persistence, and grades
- `backend/words.py` — vocabulary, word-to-chunk, and question coverage analytics
- `corpora/` — selected V2 corpus source documents
- `evaluation/question_sets/` — V2 JSONL question sets matching the Kestrel schema
- `evaluation/results/` — generated local evaluation outputs (not pre-populated with fabricated measurements)
- `backend/evaluation_set.json` — repeatable retrieval baseline questions and expected passages
- `frontend/app/` — Next.js interface
- `ask_norag_google.py`, `ask_rag_google.py` — original console experiments

## V1 report and team submission

See `REPORT.md` for the required team details, decision log, and known-failure record. Team identities and measured observations need to be completed by the project team; they are not guessed here.

# Free books from Project Gutenberg

- https://www.gutenberg.org/
- Crime and Punishment by Fyodor Dostoevsky: https://www.gutenberg.org/ebooks/2554
- Huckleberry Finn by Mark Twain: https://www.gutenberg.org/ebooks/76
