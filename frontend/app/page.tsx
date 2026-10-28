"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type DocumentInfo = { filename: string; size_bytes: number };
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

export default function Home() {
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
    const files = await apiRequest<DocumentInfo[]>("/api/documents");
    setDocuments(files);
    setSelected((current) => current.filter((name) => files.some((file) => file.filename === name)));
  }, []);

  useEffect(() => {
    refreshDocuments().catch((caught: Error) => setError(caught.message));
  }, [refreshDocuments]);

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
        body: JSON.stringify({ filename: file.name, content }),
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
      await apiRequest<void>(`/api/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
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

      <div className="workspace">
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
      </div>
    </main>
  );
}
