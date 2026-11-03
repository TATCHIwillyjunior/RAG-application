# V1 and V2 report

> The final report must reflect the project's own decisions and writing. Assistant-drafted V2 descriptions, diagnoses, and grade proposals below require team verification and rewriting before submission.

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
| V2 corpora | Keep the provided fictional Kestrel KB for comparable challenge cases and use the selected Vellora Duo manual as a second product-focused corpus whose facts can be checked against its source. |
| V2 retrieval comparison | Keep both question sets fixed; compare 800-character/10%-overlap and 400-character/10%-overlap runs so chunk-size changes are isolated. |
| Words analysis | Count case-folded alphanumeric tokens; question coverage omits common stop words and shows corpus frequency and distinct matching-chunk count to expose missing or non-discriminative terms. |
| No-context judge | Pass each question's corpus-answerability flag to the judge; an abstention is incorrect for a corpus-answerable question and required for an unanswerable one. |

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

### Per-type retrieval results

Each cell is Hit Rate / Mean Evidence Recall, in percent. Unanswerable `not_in_corpus` questions are excluded.

| Corpus | Configuration | Type | @1 | @3 | @5 | @10 |
|---|---|---|---:|---:|---:|---:|
| Kestrel KB | 800 / 10% | exact_identifier | 50 / 25 | 50 / 50 | 50 / 50 | 100 / 100 |
| Kestrel KB | 800 / 10% | split_answer | 100 / 62.5 | 100 / 100 | 100 / 100 | 100 / 100 |
| Kestrel KB | 800 / 10% | two_hop | 100 / 50 | 100 / 50 | 100 / 50 | 100 / 50 |
| Kestrel KB | 800 / 10% | versions | 0 / 0 | 100 / 100 | 100 / 100 | 100 / 100 |
| Kestrel KB | 800 / 10% | vocabulary | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| Kestrel KB | 400 / 10% | exact_identifier | 50 / 25 | 50 / 50 | 50 / 50 | 50 / 50 |
| Kestrel KB | 400 / 10% | split_answer | 0 / 0 | 100 / 62.5 | 100 / 87.5 | 100 / 87.5 |
| Kestrel KB | 400 / 10% | two_hop | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Kestrel KB | 400 / 10% | versions | 0 / 0 | 100 / 100 | 100 / 100 | 100 / 100 |
| Kestrel KB | 400 / 10% | vocabulary | 100 / 50 | 100 / 100 | 100 / 100 | 100 / 100 |
| Vellora Duo | 800 / 10% | exact_identifier | 50 / 50 | 50 / 50 | 50 / 50 | 50 / 50 |
| Vellora Duo | 800 / 10% | split_answer | 25 / 25 | 75 / 75 | 75 / 75 | 75 / 75 |
| Vellora Duo | 800 / 10% | vocabulary | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| Vellora Duo | 400 / 10% | exact_identifier | 50 / 50 | 50 / 50 | 50 / 50 | 50 / 50 |
| Vellora Duo | 400 / 10% | split_answer | 50 / 37.5 | 75 / 62.5 | 75 / 62.5 | 100 / 100 |
| Vellora Duo | 400 / 10% | vocabulary | 0 / 0 | 100 / 100 | 100 / 100 | 100 / 100 |

The smaller chunks help Vellora's split-answer and vocabulary questions at larger cutoffs, but hurt Kestrel's two-hop case at every cutoff. The detailed per-type metrics remain in each retrieval JSONL.

### Words-mode retrieval diagnoses

The following observations come from `/api/words/coverage` and `/api/words/search` at 400 / 10%, then comparison with the saved ranked passages. This is an assistant-assisted draft; the project team must verify the observations and rewrite the final report in its own words.

| Corpus | Run ID/configuration | Missed question | Retrieved evidence and observed failure | Evidence-based diagnosis and candidate change (team review required) |
|---|---|---|---|---|
| Kestrel KB | `20261103T105209Z-a5b19862`, 400 / 10% | q08: KST-5031 two-hop escalation question | No question terms are absent, but `support` occurs in 30 chunks and `team` in 12; `KST-5031` occurs once (in two overlapping chunks). The top ten retrieve the error-code passage at rank 1, but not the Service Catalog mapping. At 800 / 10%, only one of two expected evidence quotes is found even at k=10. | The question requires KST-5031 → postroom → Messaging/channel, but does not name the bridge term `postroom`; the 400-character split also separates part of the runbook evidence across chunks 16–17. A follow-up retrieval using the first-hop service name, or a hybrid/entity-aware retrieval step, is a candidate change to test. |
| Vellora Duo | `20261103T105307Z-0517ed24`, 400 / 10% (also missed at 800 / 10%) | v01: water tank capacity | The question term `capacity` is absent from the corpus. `water` appears in 42 chunks and `tank` in 20; `litres` appears in only 3 chunks but is not in the question. Neither configuration retrieves the expected chunk in its top ten; the 400 / 10% top ten focus on troubleshooting and maintenance. | The query uses broad, frequent terms and does not use the manual's `1.8 litres` wording. Test a controlled synonym/query expansion for capacity/volume/litres or hybrid lexical retrieval; do not silently change the fixed evaluation question. |

Gemini-backed evaluations were run on 2026-11-03 using `gemini-3.5-flash-lite`. Grounded-answer generation completed for all ten questions under both chunk configurations for both corpora:

| Corpus | Configuration | Run ID |
|---|---|---|
| Kestrel KB | 800 / 10% | `20261103T122933Z-79d8bf99` |
| Kestrel KB | 400 / 10% | `20261103T123029Z-e38d3762` |
| Vellora Duo | 800 / 10% | `20261103T123336Z-4c69f0c2` |
| Vellora Duo | 400 / 10% | `20261103T123509Z-9a78ef72` |

The JSONL results contain the generated answers, validated citation IDs, and the passage IDs needed to map citations back to retrieved chunks. The selected Kestrel run has assistant-assisted grading proposals below. The initial no-context judge omitted the question's answerability flag and incorrectly accepted abstentions on answerable questions; the judge was corrected and the saved answers were re-judged. The corrected checks cover all ten questions in each corpus:

| Corpus | Run ID | Correct overall | Answerable questions answered correctly without retrieval |
|---|---|---|---|
| Kestrel KB | `20261103T123132Z-3b5ba05c` | 1/10 (q10 abstained on an unanswerable question) | 0/8 |
| Vellora Duo | `20261103T123627Z-e39b5db6` | 1/10 (v10 abstained on an unanswerable question) | 0/9 |

The answerability-aware judge flagged no answerable question as correctly answered from general knowledge. The single correct item in each set is an abstention on its unanswerable control, not a prior-knowledge answer. Keep both fixed question sets; there is no answerable item to replace based on these checks. These are model-judged predictions, not proof of answer quality.

### Manual answer-grading rules

The Kestrel KB 800 / 10% run (`20261103T122933Z-79d8bf99`) is selected for hand grading because it has higher aggregate hit rate and evidence recall than the 400 / 10% run at every measured cutoff. These rules were recorded before reviewing its generated answers:

- **correct**: gives the expected answer without a material error, and its cited retrieved passages support the factual claims.
- **partial**: gives the central answer correctly but omits one or more required details, with no material contradiction.
- **wrong**: gives a materially incorrect or contradictory answer.
- **unsupported**: makes a material factual claim that its cited/retrieved passages do not support, even if the claim sounds plausible.
- For an unanswerable question, only a clear statement that the answer is not in the documents is correct; an invented answer is wrong or unsupported.

The grading review is assistant-assisted and must be checked by the project team before submission; the persistent `manual_grade` fields and comments identify the proposed result for each question.

| Selected run | Correct | Partial | Wrong | Unsupported |
|---|---:|---:|---:|---:|
| Kestrel KB, 800 / 10%, `20261103T122933Z-79d8bf99` | 4 | 6 | 0 | 0 |

These are pre-grades, not a substitute for the team's hand review. The JSONL comments explain each proposed label; confirm or change them before submission.

### V2 submission checklist

- [x] Confirm at least 10 questions are present in each V2 corpus JSONL set.
- [x] Run retrieval evaluation on both corpora using at least two configurations.
- [x] Save overall and per-question-type metrics and retrieved evidence under `evaluation/results/`.
- [x] Inspect and draft a Words-based diagnosis for one retrieval miss per corpus.
- [ ] Team verify and own the final miss diagnoses.
- [x] Run no-context checks for each question in both sets.
- [x] Generate grounded answers for both corpora under both chunk configurations.
- [x] Review answerability-aware no-context predictions and record the keep decision.
- [x] Record assistant-assisted answer-grade proposals for the selected configuration.
- [ ] Team hand-review and confirm or replace the proposed grades.
- [ ] Review the final V2 report before submission.
- [ ] Create the required `v2` Git tag after the team approves the submission.
