"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type DocumentInfo = { filename: string; size_bytes: number };
type CorpusInfo = { id: string; name: string; documents: DocumentInfo[] };
type Reference = {
  id: string;
  filename: string;
  chunk_index: number;
  start_char: number;
  end_char: number;
  text: string;
};
type AskResult = {
  answer: string;
  references: Reference[];
  retrieved_count: number;
  model: string;
};

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(" ")
      : body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type WordEntry = { word: string; frequency: number; chunk_count: number };
type WordChunk = {
  filename: string;
  chunk_index: number;
  start_char: number;
  end_char: number;
  text: string;
};
type CoverageEntry = {
  question_id: string;
  question: string;
  type: string;
  words: { word: string; present: boolean; frequency: number; chunk_count: number }[];
  missing_words: string[];
};
type QuestionSetInfo = { corpus_id: string; question_count: number };

function WordsPanel({ corpusId }: { corpusId: string }) {
  const [vocabulary, setVocabulary] = useState<WordEntry[]>([]);
  const [coverage, setCoverage] = useState<CoverageEntry[]>([]);
  const [questionSets, setQuestionSets] = useState<QuestionSetInfo[]>([]);
  const [questionSetId, setQuestionSetId] = useState(corpusId);
  const [selectedWord, setSelectedWord] = useState("");
  const [chunks, setChunks] = useState<WordChunk[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setQuestionSetId(corpusId);
  }, [corpusId]);

  useEffect(() => {
    apiRequest<QuestionSetInfo[]>("/api/evaluations/question-sets")
      .then(setQuestionSets)
      .catch((caught: Error) => setError(caught.message));
  }, []);

  useEffect(() => {
    setError("");
    setSelectedWord("");
    setChunks([]);
    Promise.all([
      apiRequest<{ vocabulary: WordEntry[] }>(`/api/words?corpus_id=${encodeURIComponent(corpusId)}`),
      apiRequest<CoverageEntry[]>("/api/words/coverage", {
        method: "POST",
        body: JSON.stringify({ corpus_id: corpusId, question_set_id: questionSetId }),
      }),
    ])
      .then(([analysis, questionCoverage]) => {
        setVocabulary(analysis.vocabulary);
        setCoverage(questionCoverage);
      })
      .catch((caught: Error) => setError(caught.message));
  }, [corpusId, questionSetId]);

  async function showWord(word: string) {
    setError("");
    setSelectedWord(word);
    try {
      const result = await apiRequest<{ chunks: WordChunk[] }>("/api/words/search", {
        method: "POST",
        body: JSON.stringify({ corpus_id: corpusId, word }),
      });
      setChunks(result.chunks);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load matching chunks.");
    }
  }

  return (
    <section className="analytics-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">CORPUS ANALYTICS</p><h2>Words and coverage</h2></div>
        <span className="model-badge">{vocabulary.length} unique words</span>
      </div>
      {error && <div className="notice error-notice" role="alert">{error}</div>}
      <p className="analytics-summary">Select a word to inspect the chunks where it appears. Coverage shows question terms found in the selected corpus and terms that are absent.</p>
      <label className="question-set-picker">Question set
        <select value={questionSetId} onChange={(event) => setQuestionSetId(event.target.value)}>
          {questionSets.map((set) => <option key={set.corpus_id} value={set.corpus_id}>{set.corpus_id} · {set.question_count} questions</option>)}
        </select>
      </label>
      <div className="analytics-grid">
        <section className="analytics-card">
          <h3>Vocabulary frequency</h3>
          <div className="scroll-table">
            <table>
              <thead><tr><th>Word</th><th>Occurrences</th><th>Chunks</th></tr></thead>
              <tbody>
                {vocabulary.map((entry) => (
                  <tr key={entry.word} className={entry.word === selectedWord ? "selected-word" : ""}>
                    <td><button className="word-link" onClick={() => showWord(entry.word)}>{entry.word}</button></td>
                    <td>{entry.frequency}</td><td>{entry.chunk_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="analytics-card">
          <h3>{selectedWord ? `Chunks containing “${selectedWord}”` : "Word-to-chunk lookup"}</h3>
          {!selectedWord && <p className="empty-library">Choose a vocabulary item to browse its source chunks.</p>}
          {chunks.map((chunk) => (
            <article className="word-chunk" key={`${chunk.filename}:${chunk.chunk_index}`}>
              <strong>{chunk.filename} · chunk {chunk.chunk_index + 1}</strong>
              <p>{chunk.text}</p>
            </article>
          ))}
        </section>
      </div>
      <section className="analytics-card coverage-card">
        <h3>Question-to-corpus word coverage</h3>
        <div className="coverage-list">
          {coverage.map((entry) => (
            <article className="coverage-question" key={entry.question_id}>
              <div><strong>{entry.question_id} · {entry.type}</strong><p>{entry.question}</p></div>
              <div className="coverage-words">
                {entry.words.map((word) => (
                  <span className={`coverage-word ${word.present ? "present" : "missing"}`} key={word.word} title={word.present ? `${word.frequency} occurrences in ${word.chunk_count} chunks` : "Not present in the corpus"}>
                    {word.word}{word.present ? ` · ${word.chunk_count}` : " · absent"}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

type EvaluationQuestion = {
  question_id: string;
  question: string;
  type: string;
  answerable: boolean;
  expected_answer: string;
  generated_answer?: string;
  manual_grade: string | null;
  retrieved_passages?: WordChunk[];
  no_context_answer?: string;
  no_context_correct?: boolean;
};
type EvaluationResult = {
  summary: {
    run_id: string;
    corpus_id: string;
    configuration?: { name: string; chunk_size: number; overlap_percent: number };
    overall?: Record<string, { hit_rate: number | null; mean_evidence_recall: number | null }>;
    by_type?: Record<string, Record<string, { hit_rate: number | null; mean_evidence_recall: number | null }>>;
    correct_rate?: number;
  };
  questions: EvaluationQuestion[];
};

function EvaluationPanel({ corpusId }: { corpusId: string }) {
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [includeAnswers, setIncludeAnswers] = useState(false);
  const [includeNoContext, setIncludeNoContext] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    setResults([]);
    setError("");
    setStatus("");
  }, [corpusId]);

  async function runEvaluation() {
    setError("");
    setStatus("");
    setBusy(true);
    try {
      const retrieval = await apiRequest<EvaluationResult[]>("/api/evaluations", {
        method: "POST",
        body: JSON.stringify({
          corpus_id: corpusId,
          configurations: [
            { name: "baseline-800", chunk_size: 800, overlap_percent: 10 },
            { name: "small-400", chunk_size: 400, overlap_percent: 10 },
          ],
          include_answers: includeAnswers,
        }),
      });
      setResults(retrieval);
      if (includeNoContext) {
        const noContext = await apiRequest<EvaluationResult>("/api/evaluations/no-context", {
          method: "POST",
          body: JSON.stringify({ corpus_id: corpusId }),
        });
        setResults((current) => [...current, noContext]);
      }
      setStatus("Evaluation complete. Results were saved on the backend.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Evaluation could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveGrade(runId: string, questionId: string, grade: string) {
    setError("");
    try {
      await apiRequest(`/api/evaluations/runs/${encodeURIComponent(runId)}/grades`, {
        method: "POST",
        body: JSON.stringify({ question_id: questionId, grade }),
      });
      setResults((current) => current.map((result) => result.summary.run_id !== runId ? result : ({
        ...result,
        questions: result.questions.map((question) => question.question_id === questionId ? { ...question, manual_grade: grade } : question),
      })));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The grade could not be saved.");
    }
  }

  return (
    <section className="analytics-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">REPEATABLE MEASUREMENT</p><h2>Retrieval evaluation</h2></div>
        <span className="model-badge">{corpusId} question set</span>
      </div>
      <p className="analytics-summary">Runs the corpus question set through the app’s retrieval route. Relevance is measured at k=1, 3, 5, and 10; unanswerable questions are excluded from retrieval scores.</p>
      <div className="evaluation-controls">
        <label><input type="checkbox" checked={includeAnswers} onChange={(event) => setIncludeAnswers(event.target.checked)} /> Generate grounded answers too (uses Gemini API quota)</label>
        <label><input type="checkbox" checked={includeNoContext} onChange={(event) => setIncludeNoContext(event.target.checked)} /> Run no-context Gemini checks (uses Gemini API quota)</label>
        <button className="ask-button" type="button" disabled={busy} onClick={runEvaluation}>{busy ? "Running…" : "Run evaluation"} <span aria-hidden="true">↗</span></button>
      </div>
      {error && <div className="notice error-notice" role="alert">{error}</div>}
      {status && <div className="notice success-notice" role="status">{status}</div>}
      {results.map((result) => (
        <section className="evaluation-result" key={result.summary.run_id}>
          <div className="evaluation-result-heading">
            <h3>{result.summary.configuration?.name ?? "No-context check"} · {result.summary.run_id}</h3>
            {result.summary.correct_rate !== undefined && <span>{Math.round(result.summary.correct_rate * 100)}% judged correct</span>}
          </div>
          {result.summary.overall && (
            <div className="scroll-table">
              <table>
                <thead><tr><th>k</th><th>Hit rate</th><th>Mean evidence recall</th></tr></thead>
                <tbody>{[1, 3, 5, 10].map((cutoff) => (
                  <tr key={cutoff}><td>{cutoff}</td><td>{formatMetric(result.summary.overall?.[String(cutoff)]?.hit_rate)}</td><td>{formatMetric(result.summary.overall?.[String(cutoff)]?.mean_evidence_recall)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {result.summary.by_type && Object.entries(result.summary.by_type).map(([type, metrics]) => (
            <details className="type-metrics" key={type}>
              <summary>{type}</summary>
              <span>{[1, 3, 5, 10].map((cutoff) => `@${cutoff} hit ${formatMetric(metrics[String(cutoff)]?.hit_rate)}, recall ${formatMetric(metrics[String(cutoff)]?.mean_evidence_recall)}`).join(" · ")}</span>
            </details>
          ))}
          <div className="evaluation-questions">
            {result.questions.map((question) => (
              <article className="evaluation-question" key={question.question_id}>
                <div className="evaluation-question-heading">
                  <strong>{question.question_id} · {question.type}{!question.answerable ? " · unanswerable" : ""}</strong>
                  {result.summary.overall && (
                    <label className="grade-picker">Manual grade
                      <select value={question.manual_grade ?? ""} onChange={(event) => event.target.value && saveGrade(result.summary.run_id, question.question_id, event.target.value)}>
                        <option value="">Not graded</option>
                        <option value="correct">Correct</option><option value="partial">Partial</option>
                        <option value="wrong">Wrong</option><option value="unsupported">Unsupported</option>
                      </select>
                    </label>
                  )}
                  {question.no_context_correct !== undefined && <span>{question.no_context_correct ? "Judge: correct" : "Judge: incorrect"}</span>}
                </div>
                <p>{question.question}</p>
                <p className="expected-answer"><strong>Expected:</strong> {question.expected_answer}</p>
                {question.generated_answer && <p className="expected-answer"><strong>Generated:</strong> {question.generated_answer}</p>}
                {question.no_context_answer && <p className="expected-answer"><strong>No-context answer:</strong> {question.no_context_answer}</p>}
                {question.retrieved_passages?.map((passage) => (
                  <blockquote className="evaluation-passage" key={`${passage.filename}:${passage.chunk_index}`}>{passage.filename} · chunk {passage.chunk_index + 1}: {passage.text}</blockquote>
                ))}
              </article>
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}

function formatMetric(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

export default function Home() {
  const [corpora, setCorpora] = useState<CorpusInfo[]>([]);
  const [corpusId, setCorpusId] = useState("vellora");
  const [activeTab, setActiveTab] = useState<"ask" | "words" | "evaluation">("ask");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [chunkSize, setChunkSize] = useState(800);
  const [overlap, setOverlap] = useState(10);
  const [topK, setTopK] = useState(5);
  const [result, setResult] = useState<AskResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [openReference, setOpenReference] = useState<string | null>(null);

  const refreshDocuments = useCallback(async () => {
    const files = await apiRequest<DocumentInfo[]>(`/api/documents?corpus_id=${encodeURIComponent(corpusId)}`);
    setDocuments(files);
    setSelected((current) => current.filter((name) => files.some((file) => file.filename === name)));
  }, [corpusId]);

  useEffect(() => {
    refreshDocuments().catch((caught: Error) => setError(caught.message));
  }, [refreshDocuments]);

  useEffect(() => {
    apiRequest<CorpusInfo[]>("/api/corpora")
      .then(setCorpora)
      .catch((caught: Error) => setError(caught.message));
  }, []);

  const selectedSize = useMemo(
    () => documents
      .filter((document) => selected.includes(document.filename))
      .reduce((total, document) => total + document.size_bytes, 0),
    [documents, selected],
  );

  function toggleDocument(filename: string) {
    setSelected((current) => current.includes(filename)
      ? current.filter((name) => name !== filename)
      : [...current, filename]);
    setResult(null);
  }

  async function addDocument(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    setStatus("");
    try {
      const content = await file.text();
      const saved = await apiRequest<DocumentInfo>("/api/documents", {
        method: "POST",
        body: JSON.stringify({ filename: file.name, content, corpus_id: corpusId }),
      });
      await refreshDocuments();
      setSelected((current) => current.includes(saved.filename) ? current : [...current, saved.filename]);
      setStatus(`${saved.filename} added to your document library.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add that document.");
    }
  }

  async function removeDocument(filename: string) {
    if (!window.confirm(`Delete ${filename} from the document library?`)) return;
    setError("");
    setStatus("");
    try {
      await apiRequest<void>(`/api/documents/${encodeURIComponent(filename)}?corpus_id=${encodeURIComponent(corpusId)}`, { method: "DELETE" });
      await refreshDocuments();
      setResult(null);
      setStatus(`${filename} deleted.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete that document.");
    }
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    setResult(null);
    if (!selected.length) {
      setError("Select at least one document first.");
      return;
    }
    setBusy(true);
    try {
      const response = await apiRequest<AskResult>("/api/ask", {
        method: "POST",
        body: JSON.stringify({
          question,
          document_names: selected,
          corpus_id: corpusId,
          chunk_size: chunkSize,
          overlap_percent: overlap,
          top_k: topK,
        }),
      });
      setResult(response);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The question could not be answered.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="Grounded home">
          <span className="brand-mark">G</span>
          <span>grounded<span className="brand-dot">.</span></span>
        </a>
        <span className="topbar-note"><span className="status-dot" /> Local document library</span>
      </header>

      <section className="hero">
        <p className="eyebrow">YOUR KNOWLEDGE, WITH SOURCES</p>
        <h1>Answers you can <em>trace.</em></h1>
        <p className="hero-copy">
          Ask questions across your documents. Every answer is grounded in retrieved passages you can open and verify.
        </p>
      </section>

      <nav className="workspace-tabs" aria-label="RAG workspace views">
        {([
          ["ask", "Ask"],
          ["words", "Words"],
          ["evaluation", "Evaluation"],
        ] as const).map(([tab, label]) => (
          <button
            key={tab}
            className={`workspace-tab ${activeTab === tab ? "active" : ""}`}
            onClick={() => setActiveTab(tab)}
            type="button"
            aria-pressed={activeTab === tab}
          >
            {label}
          </button>
        ))}
        <label className="corpus-picker">
          Corpus
          <select
            value={corpusId}
            onChange={(event) => {
              setCorpusId(event.target.value);
              setDocuments([]);
              setSelected([]);
              setResult(null);
              setError("");
            }}
          >
            {corpora.map((corpus) => (
              <option key={corpus.id} value={corpus.id}>{corpus.name}</option>
            ))}
          </select>
        </label>
      </nav>

      {activeTab === "words" && <WordsPanel corpusId={corpusId} />}
      {activeTab === "evaluation" && <EvaluationPanel corpusId={corpusId} />}

      {activeTab === "ask" && <div className="workspace">
        <aside className="sidebar">
          <div className="section-heading">
            <div>
              <p className="eyebrow">YOUR LIBRARY</p>
              <h2>Documents <span className="count-pill">{documents.length}</span></h2>
            </div>
            <label className="add-button" title="Add a .txt or .md document">
              <span aria-hidden="true">＋</span> Add
              <input type="file" accept=".txt,.md,text/plain,text/markdown" onChange={addDocument} />
            </label>
          </div>
          <p className="sidebar-hint">Choose which files the assistant can search.</p>

          <div className="document-list">
            {documents.map((document) => (
              <div className={`document-row ${selected.includes(document.filename) ? "selected" : ""}`} key={document.filename}>
                <label className="document-select">
                  <input
                    type="checkbox"
                    checked={selected.includes(document.filename)}
                    onChange={() => toggleDocument(document.filename)}
                  />
                  <span className="file-icon">{document.filename.toLowerCase().endsWith(".md") ? "MD" : "TXT"}</span>
                  <span className="document-meta">
                    <span className="document-name" title={document.filename}>{document.filename}</span>
                    <span className="document-size">{formatSize(document.size_bytes)}</span>
                  </span>
                </label>
                <button className="icon-button delete-button" onClick={() => removeDocument(document.filename)} aria-label={`Delete ${document.filename}`} title="Delete document">
                  ×
                </button>
              </div>
            ))}
            {!documents.length && <p className="empty-library">No .txt or .md documents yet. Add one to get started.</p>}
          </div>

          <div className="selection-summary">
            <span className="status-dot" /> {selected.length} selected
            <span className="summary-size">{formatSize(selectedSize)}</span>
          </div>

          <div className="settings-card">
            <div className="settings-title">
              <div>
                <p className="eyebrow">RETRIEVAL</p>
                <h3>Search settings</h3>
              </div>
              <span className="settings-icon">⌘</span>
            </div>
            <label className="setting-field">
              <span>Chunk size <small>characters</small></span>
              <input type="number" min={100} max={2000} step={100} value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value))} />
            </label>
            <label className="setting-field">
              <span>Overlap <small>percent</small></span>
              <input type="number" min={0} max={50} step={5} value={overlap} onChange={(event) => setOverlap(Number(event.target.value))} />
            </label>
            <label className="setting-field">
              <span>Retrieved passages <small>top-k</small></span>
              <input type="number" min={1} max={10} value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
            </label>
            <p className="settings-footnote">Changing chunk settings builds a matching local index.</p>
          </div>
        </aside>

        <section className="main-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">DOCUMENT Q&amp;A</p>
              <h2>What would you like to know?</h2>
            </div>
            <span className="model-badge"><span className="model-spark">✳</span> Gemini</span>
          </div>

          <form className="question-form" onSubmit={submitQuestion}>
            <label className="sr-only" htmlFor="question">Ask your documents a question</label>
            <textarea
              id="question"
              placeholder="Ask a question about your selected documents…"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={2000}
              rows={3}
              required
            />
            <div className="form-bottom">
              <span className="form-hint">{selected.length ? `Searching ${selected.length} ${selected.length === 1 ? "document" : "documents"}` : "Select documents to begin"}</span>
              <button className="ask-button" type="submit" disabled={busy || !question.trim()}>
                {busy ? <><span className="spinner" /> Searching…</> : <>Ask question <span aria-hidden="true">↗</span></>}
              </button>
            </div>
          </form>

          <div className="sample-row">
            <span>TRY</span>
            {["What is S3?", "How do I troubleshoot an error?", "Summarize the key points"].map((sample) => (
              <button key={sample} type="button" className="sample-chip" onClick={() => setQuestion(sample)}>{sample}</button>
            ))}
          </div>

          {error && <div className="notice error-notice" role="alert"><span>!</span>{error}</div>}
          {status && <div className="notice success-notice" role="status"><span>✓</span>{status}</div>}

          {!result && !busy && (
            <div className="welcome-card">
              <div className="welcome-art" aria-hidden="true">
                <span className="art-page page-back" />
                <span className="art-page page-mid" />
                <span className="art-page page-front"><i /><i /><i /></span>
                <span className="art-search">⌕</span>
              </div>
              <h3>Your documents, in conversation.</h3>
              <p>Select documents, ask a question, and inspect the passages behind the answer.</p>
            </div>
          )}

          {busy && <div className="loading-card"><span className="spinner large-spinner" />Finding passages and checking the answer…</div>}

          {result && (
            <article className="answer-card">
              <div className="answer-topline">
                <span className="answer-label"><span className="answer-spark">✳</span> GROUNDED ANSWER</span>
                <span className="answer-model">{result.model}</span>
              </div>
              <p className="answer-text">{result.answer}</p>
              <div className="references-header">
                <div>
                  <p className="eyebrow">SOURCE TRAIL</p>
                  <h3>Retrieved passages <span className="count-pill">{result.references.length}</span></h3>
                </div>
                <span className="retrieved-total">{result.retrieved_count} found</span>
              </div>
              {!result.references.length ? (
                <p className="no-references">No retrieved passages were cited. Check the selected documents or try a more specific question.</p>
              ) : (
                <div className="reference-list">
                  {result.references.map((reference) => (
                    <div className="reference" key={reference.id}>
                      <button className="reference-toggle" onClick={() => setOpenReference(openReference === reference.id ? null : reference.id)} aria-expanded={openReference === reference.id}>
                        <span className="reference-number">↗</span>
                        <span className="reference-name">{reference.filename}</span>
                        <span className="reference-chunk">Chunk {reference.chunk_index + 1} · chars {reference.start_char}–{reference.end_char}</span>
                        <span className="reference-chevron">{openReference === reference.id ? "−" : "+"}</span>
                      </button>
                      {openReference === reference.id && <blockquote className="reference-text">{reference.text}</blockquote>}
                    </div>
                  ))}
                </div>
              )}
            </article>
          )}
          <footer className="disclaimer">AI-generated answers can be wrong. Always verify important details against the source passages.</footer>
        </section>
      </div>}
    </main>
  );
}
