import re
from collections import Counter
from typing import Any

from . import evaluation, rag


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
STOP_WORDS = {
    "a", "about", "after", "again", "all", "also", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "between", "both",
    "but", "by", "can", "could", "did", "do", "does", "during", "each", "for",
    "from", "further", "had", "has", "have", "he", "her", "here", "hers", "him",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "may", "might",
    "more", "most", "must", "my", "no", "nor", "not", "of", "on", "once", "only",
    "or", "other", "our", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "us", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your",
}


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_PATTERN.finditer(text)]


def analyze_corpus(
    corpus_id: str, chunk_size: int = 800, overlap_percent: int = 10
) -> dict[str, Any]:
    filenames = [path.name for path in rag.list_corpus_documents(corpus_id)]
    if not filenames:
        raise ValueError(f"No documents are available in the {corpus_id} corpus.")
    frequencies: Counter[str] = Counter()
    for path in rag.list_corpus_documents(corpus_id):
        frequencies.update(_tokens(path.read_text(encoding="utf-8")))
    chunks = rag.get_document_chunks(
        filenames, chunk_size, overlap_percent, corpus_id
    )
    word_chunks: dict[str, set[tuple[str, int]]] = {}
    for chunk in chunks:
        tokens = _tokens(chunk["text"])
        for token in set(tokens):
            word_chunks.setdefault(token, set()).add(
                (chunk["filename"], chunk["chunk_index"])
            )
    vocabulary = [
        {
            "word": word,
            "frequency": frequency,
            "chunk_count": len(word_chunks[word]),
        }
        for word, frequency in sorted(
            frequencies.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    return {
        "corpus_id": corpus_id,
        "chunk_size": chunk_size,
        "overlap_percent": overlap_percent,
        "document_count": len(filenames),
        "chunk_count": len(chunks),
        "total_word_count": sum(frequencies.values()),
        "unique_word_count": len(vocabulary),
        "vocabulary": vocabulary,
        "_chunks": chunks,
    }


def find_word_chunks(
    corpus_id: str,
    word: str,
    chunk_size: int = 800,
    overlap_percent: int = 10,
) -> dict[str, Any]:
    word = word.strip().casefold()
    if not word or len(word) > 80 or not TOKEN_PATTERN.fullmatch(word):
        raise ValueError("Enter one word or identifier (up to 80 characters).")
    analysis = analyze_corpus(corpus_id, chunk_size, overlap_percent)
    matches = [
        chunk
        for chunk in analysis["_chunks"]
        if word in _tokens(chunk["text"])
    ]
    return {
        "corpus_id": corpus_id,
        "word": word,
        "frequency": next(
            (
                entry["frequency"]
                for entry in analysis["vocabulary"]
                if entry["word"] == word
            ),
            0,
        ),
        "chunk_count": len(matches),
        "chunks": matches,
    }


def question_coverage(
    corpus_id: str,
    question_set_id: str,
    chunk_size: int = 800,
    overlap_percent: int = 10,
) -> list[dict[str, Any]]:
    if question_set_id not in evaluation.QUESTION_SETS:
        raise ValueError(f"Unknown question set '{question_set_id}'.")
    questions = evaluation.load_questions(question_set_id)
    analysis = analyze_corpus(corpus_id, chunk_size, overlap_percent)
    frequencies = {
        entry["word"]: entry for entry in analysis["vocabulary"]
    }
    results = []
    for question in questions:
        words = sorted(
            {
                token
                for token in _tokens(question["question"])
                if token not in STOP_WORDS and len(token) > 1
            }
        )
        results.append(
            {
                "question_id": question["id"],
                "question": question["question"],
                "type": question["type"],
                "words": [
                    {
                        "word": word,
                        "present": word in frequencies,
                        "frequency": frequencies.get(word, {}).get("frequency", 0),
                        "chunk_count": frequencies.get(word, {}).get("chunk_count", 0),
                    }
                    for word in words
                ],
                "missing_words": [word for word in words if word not in frequencies],
            }
        )
    return results
