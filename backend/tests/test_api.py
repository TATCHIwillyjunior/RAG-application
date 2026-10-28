import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main, rag


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.documents_dir = Path(self.temp_dir.name)
        self.documents_patch = patch.object(main, "DOCUMENTS_DIR", self.documents_dir)
        self.documents_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.documents_patch.stop()
        self.temp_dir.cleanup()

    def test_lists_text_and_markdown_documents(self) -> None:
        (self.documents_dir / "guide.md").write_text("# Guide", encoding="utf-8")
        (self.documents_dir / "notes.txt").write_text("Notes", encoding="utf-8")
        (self.documents_dir / "ignore.pdf").write_bytes(b"not indexed")

        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [document["filename"] for document in response.json()],
            ["guide.md", "notes.txt"],
        )

    def test_upload_and_delete_document(self) -> None:
        upload = self.client.post(
            "/api/documents",
            json={"filename": "new-note.txt", "content": "Local content."},
        )

        self.assertEqual(upload.status_code, 201)
        self.assertEqual(
            (self.documents_dir / "new-note.txt").read_text(encoding="utf-8"),
            "Local content.",
        )

        with patch.object(rag, "delete_document_indexes") as delete_indexes:
            deleted = self.client.delete("/api/documents/new-note.txt")

        self.assertEqual(deleted.status_code, 204)
        delete_indexes.assert_called_once_with("new-note.txt")
        self.assertFalse((self.documents_dir / "new-note.txt").exists())

    def test_rejects_path_like_and_unsupported_filenames(self) -> None:
        for filename in (
            "../outside.txt",
            r"..\outside.txt",
            "report.pdf",
            "bad:name.txt",
            "NUL.txt",
        ):
            with self.subTest(filename=filename):
                response = self.client.post(
                    "/api/documents",
                    json={"filename": filename, "content": "No write"},
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.documents_dir.iterdir()), [])

    def test_ask_returns_only_model_cited_retrieved_passages(self) -> None:
        (self.documents_dir / "manual.txt").write_text("Manual text.", encoding="utf-8")
        passage = rag.Passage(
            id="chunk-1",
            filename="manual.txt",
            chunk_index=0,
            start_char=0,
            end_char=12,
            text="Manual text.",
            distance=0.1,
        )
        answer = rag.GroundedAnswer(answer="A grounded answer.", citation_ids=["chunk-1"])
        with (
            patch.object(rag, "retrieve_passages", return_value=[passage]),
            patch.object(rag, "generate_grounded_answer", return_value=answer),
        ):
            response = self.client.post(
                "/api/ask",
                json={
                    "question": "What does the manual say?",
                    "document_names": ["manual.txt"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "A grounded answer.")
        self.assertEqual(response.json()["references"][0]["id"], "chunk-1")

    def test_missing_document_is_a_handled_not_found(self) -> None:
        response = self.client.post(
            "/api/ask",
            json={"question": "Question?", "document_names": ["missing.txt"]},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])

    def test_model_setup_error_is_a_handled_service_unavailable(self) -> None:
        (self.documents_dir / "manual.txt").write_text("Manual text.", encoding="utf-8")
        with (
            patch.object(rag, "retrieve_passages", return_value=[]),
            patch.object(
                rag,
                "generate_grounded_answer",
                side_effect=rag.ModelUnavailable("Configure the API key."),
            ),
        ):
            response = self.client.post(
                "/api/ask",
                json={"question": "Question?", "document_names": ["manual.txt"]},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Configure the API key.")

    def test_local_retrieval_error_is_a_handled_service_unavailable(self) -> None:
        (self.documents_dir / "manual.txt").write_text("Manual text.", encoding="utf-8")
        with patch.object(
            rag,
            "retrieve_passages",
            side_effect=rag.RetrievalUnavailable("Local embedding is unavailable."),
        ):
            response = self.client.post(
                "/api/ask",
                json={"question": "Question?", "document_names": ["manual.txt"]},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Local embedding is unavailable.")

    def test_no_relevant_passages_returns_a_grounded_abstention(self) -> None:
        (self.documents_dir / "manual.txt").write_text("Manual text.", encoding="utf-8")
        with patch.object(rag, "retrieve_passages", return_value=[]):
            response = self.client.post(
                "/api/ask",
                json={"question": "What is S3?", "document_names": ["manual.txt"]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["references"], [])
        self.assertIn("couldn't find relevant passages", response.json()["answer"])

    def test_invalid_model_citations_are_a_handled_bad_gateway(self) -> None:
        (self.documents_dir / "manual.txt").write_text("Manual text.", encoding="utf-8")
        passage = rag.Passage(
            id="chunk-1",
            filename="manual.txt",
            chunk_index=0,
            start_char=0,
            end_char=12,
            text="Manual text.",
            distance=0.1,
        )
        with (
            patch.object(rag, "retrieve_passages", return_value=[passage]),
            patch.object(
                rag,
                "generate_grounded_answer",
                side_effect=rag.InvalidModelResponse("Citation was not retrieved."),
            ),
        ):
            response = self.client.post(
                "/api/ask",
                json={"question": "What does the manual say?", "document_names": ["manual.txt"]},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Citation was not retrieved.")


if __name__ == "__main__":
    unittest.main()
