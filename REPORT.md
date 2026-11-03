# V1 and V2 report

> This is an individual project.

## Team details

| Member | Contribution |
|---|---|
| Willy | Sole contributor |

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
| Ask with Gemini unavailable or the API key invalid. | Return an actionable provider error; the UI remains usable. | With `GOOGLE_API_KEY` blank, `POST /api/ask` returned HTTP 503 with “Gemini is not configured. Add a valid GOOGLE_API_KEY to the project .env file.” No Gemini request was sent. The browser UI was not exercised. |
| Run the original `ask_rag_google.py` console demo where Windows Application Control blocks the SciPy DLL used by Sentence Transformers. | The original console script cannot initialize its embedding model; the V1 web app can use its Chroma ONNX embedding implementation instead. | This environment blocked SciPy `_flapack` with an Application Control policy error in the original console dependency. V1 API retrieval using Chroma ONNX succeeded for both 800- and 400-character chunk settings. |
| Change chunk settings or edit a source file. | Build/use the index for the new content/settings; older indexes must not be mistaken for the current one. | `POST /api/search` succeeded at chunk sizes 800 and 400. Chroma stored separate collections with the corresponding chunk-size metadata. Source-file edits were not exercised. |
| Upload an unsupported file or attempt a path-like filename. | Reject the input and keep files confined to the document library. | Upload attempts for `not-supported.pdf` and `..\\escape.txt` both returned HTTP 400. |
| Delete a document after indexing it. | Remove the document and its vector indexes together. | A temporary validation document indexed successfully. DELETE returned HTTP 204, removed the file, and removed its indexes. The first check exposed a Chroma `list_collections()` compatibility issue (the installed version returns collection objects); this was fixed and the check then passed. |

## Submission checklist

- [x] Record the sole contributor and contribution.
- [x] Run and record the retrieval baseline.
- [x] Run and record the authorized local API failure checks.
- [ ] Review the final report with every team member.
- [ ] Commit and create the required `v1` Git tag after the team approves the submission.

## V2 implementation and evidence

V2 implementation includes two selectable course corpora (Kestrel KB and Vellora Duo), JSONL question sets in the Kestrel record format, a retrieval-only `/api/search` endpoint, repeatable retrieval evaluation, optional grounded-answer generation, optional Gemini no-context answers and judge predictions, persisted manual grades, and a Words view for corpus frequencies, word-to-chunk browsing, and question-term coverage. The original project document library remains available as a separate corpus.

Run both V2 corpora and the two default chunk configurations from the repository root:

```powershell
python -m backend.evaluate_retrieval --corpus all
```

Result JSONL files are saved in `evaluation/results/`. Each run records its configuration, retrieved chunks, per-question evidence match metrics, overall metrics, and metrics by question type. Retrieval hit rate and mean evidence recall are reported at k=1, 3, 5, and 10; unanswerable cases are omitted from those retrieval scores. The frontend can run the same configurations and save manual grades (`correct`, `partial`, `wrong`, or `unsupported`) back into the corresponding result file.

The retrieval evaluation was run on 2026-11-03 for both corpora using the default 800-character/10%-overlap configuration and a 400-character/10%-overlap comparison. The four saved JSONL files contain each question, its ranked retrieved passages, evidence matches, and per-type scores. The table reports the aggregate Hit Rate / Mean Evidence Recall at each cutoff:

| Corpus | Configuration | Run ID | @1 | @3 | @5 | @10 |
|---|---|---|---|---|---|---|
| Kestrel KB | 800 / 10% | `20261103T105117Z-e79e26b4` | 62.5% / 40.6% | 87.5% / 81.3% | 87.5% / 81.3% | 100.0% / 93.8% |
| Kestrel KB | 400 / 10% | `20261103T105209Z-a5b19862` | 25.0% / 12.5% | 75.0% / 65.6% | 75.0% / 71.9% | 75.0% / 71.9% |
| Vellora Duo | 800 / 10% | `20261103T105255Z-13971cd6` | 44.4% / 44.4% | 66.7% / 66.7% | 66.7% / 66.7% | 66.7% / 66.7% |
| Vellora Duo | 400 / 10% | `20261103T105307Z-0517ed24` | 44.4% / 38.9% | 66.7% / 61.1% | 66.7% / 61.1% | 77.8% / 77.8% |

Unanswerable questions are excluded from these scores. The `by_type` section in each JSONL run contains the breakdown by question type. The measurements show that chunk configuration changes results; neither configuration dominates at every cutoff on both corpora.

The retrieval runs expose candidate misses, but the project team should inspect the saved passages and supply its own diagnosis and proposed change before submission. Two observed cases to review:

| Corpus | Run ID/configuration | Missed question | Retrieved evidence and observed failure | Team diagnosis and proposed change |
|---|---|---|---|---|
| Kestrel KB | `20261103T105209Z-a5b19862`, 400 / 10% | q08: KST-5031 two-hop escalation question | Evidence recall is 0 at k=10; retrieved passages include the error-code runbook entry but do not match either expected evidence quote. | [Team: inspect saved passages and record diagnosis/change.] |
| Vellora Duo | `20261103T105307Z-0517ed24`, 400 / 10% | v01: water tank capacity | Evidence recall is 0 at k=10; retrieved top passages concern troubleshooting, warranty, filter, and descaling, not the 1.8-litre capacity fact. | [Team: inspect saved passages and record diagnosis/change.] |

Gemini-backed evaluations were run on 2026-11-03 using `gemini-3.5-flash-lite`. Grounded-answer generation completed for all ten questions under both chunk configurations for both corpora:

| Corpus | Configuration | Run ID |
|---|---|---|
| Kestrel KB | 800 / 10% | `20261103T122933Z-79d8bf99` |
| Kestrel KB | 400 / 10% | `20261103T123029Z-e38d3762` |
| Vellora Duo | 800 / 10% | `20261103T123336Z-4c69f0c2` |
| Vellora Duo | 400 / 10% | `20261103T123509Z-9a78ef72` |

The JSONL results contain the generated answers and validated citation IDs; they have not been manually graded. No-context answer-and-judge checks also completed for all ten questions in each corpus:

| Corpus | Run ID | Model-judged correct |
|---|---|---|
| Kestrel KB | `20261103T123132Z-3b5ba05c` | 7/10 (70%) |
| Vellora Duo | `20261103T123627Z-e39b5db6` | 7/10 (70%) |

Model-judged correctness is a prediction, not a human assessment. Review each result against its reference and record representative manual grades before submission. No manual grades have been recorded yet.

### V2 submission checklist

- [x] Confirm at least 10 questions are present in each V2 corpus JSONL set.
- [x] Run retrieval evaluation on both corpora using at least two configurations.
- [x] Save overall and per-question-type metrics and retrieved evidence under `evaluation/results/`.
- [ ] Team review and diagnosis of the recorded retrieval misses.
- [x] Run no-context checks for each question in both sets.
- [x] Generate grounded answers for both corpora under both chunk configurations.
- [ ] Review model-judged no-context checks and manually grade representative generated answers.
- [ ] Record and diagnose one retrieval miss per V2 corpus in the table above.
- [ ] Review the final V2 report before submission.
- [ ] Create the required `v2` Git tag after the team approves the submission.
