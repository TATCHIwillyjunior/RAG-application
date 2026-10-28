# V1 report

> Complete the team fields and record observed evaluation/failure results before submission. No team identities or unrun test results are filled in on the team's behalf.

## Team details

| Member | Contribution |
|---|---|
| [Fill in] | [Fill in] |

## Decision log

| Decision | Choice and rationale |
|---|---|
| Frontend/backend | Next.js UI with a FastAPI API, matching the requested stack and keeping retrieval logic in Python. |
| Embeddings/vector store | ChromaDB's local ONNX implementation of `all-MiniLM-L6-v2` and persistent ChromaDB, consistent with the course baseline and local corpus. The original console demo retains its Sentence Transformers dependency. |
| Generation | Gemini via Google's OpenAI-compatible endpoint, using `gemini-3.5-flash-lite` by default. |
| Chunking | Fixed windows measured in characters, default 800 characters with 10% overlap; UI settings permit comparison without editing code. |
| Retrieval | Cosine-distance search, configurable top-k (default 5), plus an initial 0.75 maximum-distance heuristic. The cutoff is not a confidence score and needs evaluation/tuning on the chosen corpus. |
| Grounding and references | Ask the model for structured answer/citation IDs, validate the response, and display only citations pointing to retrieved chunks. Documents are treated as untrusted data. |
| Evaluation | Repeatable expected-source/passage checks across the full corpus, reported as Recall@5 for answerable questions and Abstention@5 for the no-evidence case. |

## Retrieval baseline

Run `python -m backend.evaluate_retrieval` and record the date, settings, result, and environment below. It reports Recall@5 for answerable questions and Abstention@5 for unanswerable questions. Do not copy a result from another machine without verifying it.

- Date/environment: [Run and fill in]
- Baseline settings: chunk size 800, overlap 10%, top-k 5
- Recall@5: [Run and fill in]
- Abstention@5: [Run and fill in]

## Known failures and observations

| Question/test | Expected behavior | Observed result |
|---|---|---|
| Ask about a fact absent from the selected corpus (for example, “What is S3?” against the current documents). | Say the selected documents do not provide relevant evidence; do not make a factual claim without support. | [Run in the app and record the actual output.] |
| Ask a question with a relevant passage below the cosine-distance cutoff. | Explain that no sufficiently relevant passage was found; do not send unrelated retrieved text for generation. | [Choose a question, measure the retrieval distance, and record the result.] |
| Ask with Gemini unavailable or the API key invalid. | Return an actionable provider error; the UI remains usable. | [Test and record the actual result.] |
| Run the original `ask_rag_google.py` console demo where Windows Application Control blocks the SciPy DLL used by Sentence Transformers. | The original console script cannot initialize its embedding model; use an approved Python environment. The V1 web app uses Chroma's ONNX `all-MiniLM-L6-v2` embedding implementation instead. | This environment blocked SciPy `_flapack` with an Application Control policy error in the original console dependency. The V1 app's ONNX runtime behavior has not been measured here. |
| Change chunk settings or edit a source file. | Build/use the index for the new content/settings; older indexes must not be mistaken for the current one. | [Run and record the actual result.] |
| Upload an unsupported file or attempt a path-like filename. | Reject the input and keep files confined to the document library. | [Test and record the actual result.] |

## Submission checklist

- [ ] Fill in team member names and contributions.
- [ ] Run and record the retrieval baseline.
- [ ] Test and record anticipated failure cases.
- [ ] Review the final report with every team member.
- [ ] Commit and create the required `v1` Git tag after the team approves the submission.
