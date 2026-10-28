import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import rag
from backend.rag import split_into_chunks


class RAGCoreTests(unittest.TestCase):
    def test_chunks_have_configured_overlap_and_source_offsets(self) -> None:
        text = "a" * 250
        chunks = split_into_chunks(text, chunk_size=100, overlap_percent=20)

        self.assertEqual([start for start, _, _ in chunks], [0, 80, 160, 240])
        self.assertTrue(all(end - start <= 100 for start, end, _ in chunks))
        self.assertEqual(chunks[0][1], chunks[1][0] + 20)
        self.assertEqual(chunks[-1][2], "a" * 10)

    def test_empty_text_returns_no_chunks(self) -> None:
        self.assertEqual(split_into_chunks("", chunk_size=800, overlap_percent=10), [])

    def test_rejects_invalid_chunk_settings(self) -> None:
        with self.assertRaises(ValueError):
            split_into_chunks("text", chunk_size=50, overlap_percent=10)
        with self.assertRaises(ValueError):
            split_into_chunks("text", chunk_size=800, overlap_percent=51)

    def test_embedding_import_failure_becomes_a_clear_retrieval_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            documents_dir = Path(temp_dir)
            (documents_dir / "manual.txt").write_text("Manual text.", encoding="utf-8")
            with self.assertLogs(rag.logger, level="ERROR"):
                with (
                    patch.object(rag, "DOCUMENTS_DIR", documents_dir),
                    patch.object(
                        rag,
                        "_load_or_create_collection",
                        side_effect=ImportError("Embedding dependency is blocked."),
                    ),
                    self.assertRaises(rag.RetrievalUnavailable),
                ):
                    rag.retrieve_passages(
                        question="Question?",
                        filenames=["manual.txt"],
                        chunk_size=800,
                        overlap_percent=10,
                        top_k=5,
                    )


if __name__ == "__main__":
    unittest.main()
