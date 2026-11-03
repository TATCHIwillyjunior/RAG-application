# V1 and V2 report

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

Run `python -m backend.evaluate_retrieval --v1-baseline` and record the date, settings, result, and environment below. It reports Recall@5 for answerable questions and Abstention@5 for unanswerable questions in the project document library. Do not copy a result from another machine without verifying it.

- Date/environment: 2026-11-03; Windows, Python 3.12.10, `C:\rag-v1-venv`; local Chroma ONNX `all-MiniLM-L6-v2` embedding.
- Baseline settings: chunk size 800, overlap 10%, top-k 5
- Recall@5: 5/7 answerable questions (71.4%)
- Abstention@5: 1/1 unanswerable questions (100.0%)

The run found two answerable-question retrieval misses: the water-tank capacity question and the E36 troubleshooting question. Their expected evidence chunks were ranked 11th (cosine distance 0.8073) and 20th (distance 0.7195), respectively; neither was in the top five. The water-tank evidence also exceeded the configured 0.75 distance cutoff.

## Known failures and observations

| Question/test | Expected behavior | Observed result |
|---|---|---|
| Ask about a fact absent from the selected corpus (for example, “What is S3?” against the current documents). | Say the selected documents do not provide relevant evidence; do not make a factual claim without support. | In the retrieval baseline, no passages survived the 0.75 distance cutoff for “What is S3?” (abstention pass). The Gemini answer path was not exercised. |
| Ask a question whose expected passage is not among the top five. | Return relevant evidence when available, or abstain rather than rely on unrelated chunks. | “How much water does the Vellora Duo water tank hold?”: the expected chunk ranked 11th at distance 0.8073, beyond the 0.75 cutoff. “What does error E36 mean and how do I fix it?”: the expected chunk ranked 20th at distance 0.7195, so it was below the top-five retrieval limit despite passing the cutoff. Both were Recall@5 misses. |
| Ask with Gemini unavailable or the API key invalid. | Return an actionable provider error; the UI remains usable. | Not exercised in this baseline run. |
| Run the original `ask_rag_google.py` console demo where Windows Application Control blocks the SciPy DLL used by Sentence Transformers. | The original console script cannot initialize its embedding model; use an approved Python environment. The V1 web app uses Chroma's ONNX `all-MiniLM-L6-v2` embedding implementation instead. | This environment blocked SciPy `_flapack` with an Application Control policy error in the original console dependency. The V1 app's ONNX runtime behavior has not been measured here. |
| Change chunk settings or edit a source file. | Build/use the index for the new content/settings; older indexes must not be mistaken for the current one. | Not exercised in this baseline run. |
| Upload an unsupported file or attempt a path-like filename. | Reject the input and keep files confined to the document library. | Not exercised in this baseline run. |

## Submission checklist

- [ ] Fill in team member names and contributions.
- [x] Run and record the retrieval baseline.
- [ ] Test and record anticipated failure cases.
- [ ] Review the final report with every team member.
- [ ] Commit and create the required `v1` Git tag after the team approves the submission.

## V2 implementation and evidence

V2 implementation includes two selectable course corpora (Kestrel KB and Vellora Duo), JSONL question sets in the Kestrel record format, a retrieval-only `/api/search` endpoint, repeatable retrieval evaluation, optional grounded-answer generation, optional Gemini no-context answers and judge predictions, persisted manual grades, and a Words view for corpus frequencies, word-to-chunk browsing, and question-term coverage. The original project document library remains available as a separate corpus.

Run both V2 corpora and the two default chunk configurations from the repository root:

```powershell
python -m backend.evaluate_retrieval --corpus all
```

Result JSONL files are saved in `evaluation/results/`. Each run records its configuration, retrieved chunks, per-question evidence match metrics, overall metrics, and metrics by question type. Retrieval hit rate and mean evidence recall are reported at k=1, 3, 5, and 10; unanswerable cases are omitted from those retrieval scores. The frontend can run the same configurations and save manual grades (`correct`, `partial`, `wrong`, or `unsupported`) back into the corresponding result file.

No measured V2 results or team-authored miss diagnoses are filled in here. Run the evaluations, inspect the saved chunks, then have the team record and diagnose at least one retrieval miss for each of the two V2 corpora:

| Corpus | Run ID/configuration | Missed question | Retrieved evidence and observed failure | Team diagnosis and proposed change |
|---|---|---|---|---|
| Kestrel KB | [Run and fill in] | [Fill in] | [Inspect result JSONL and fill in] | [Team diagnosis] |
| Vellora Duo | [Run and fill in] | [Fill in] | [Inspect result JSONL and fill in] | [Team diagnosis] |

No-context checks and generated answers issue Gemini API requests. Use the UI checkbox or the CLI `--no-context` / `--generate-answers` option only when ready to consume API quota. Model-judged correctness is a prediction; review it against each reference and record the team’s assessment.

### V2 submission checklist

- [ ] Confirm at least 10 questions are present in each V2 corpus JSONL set.
- [ ] Run retrieval evaluation on both corpora using at least two configurations.
- [ ] Review saved overall and per-question-type metrics and retrieve evidence for misses.
- [ ] Run and review no-context checks for each question in both sets.
- [ ] Generate answers where desired and manually grade representative results.
- [ ] Record and diagnose one retrieval miss per V2 corpus in the table above.
- [ ] Review the final report with every team member.
- [ ] Create the required `v2` Git tag after the team approves the submission.
