import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend import evaluation, rag


class EvaluationTests(unittest.TestCase):
    def test_retrieval_results_keep_passage_ids_for_citation_review(self) -> None:
        question = {
            "id": "q1",
            "question": "What is the fact?",
            "type": "exact_identifier",
            "answerable": True,
            "evidence": [{"source": "guide.md", "quote": "fact"}],
            "expected_answer": "The fact is seven.",
        }
        passage = rag.Passage(
            id="chunk-1",
            filename="guide.md",
            chunk_index=0,
            start_char=0,
            end_char=14,
            text="The fact is seven.",
            distance=0.1,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "results"
            with (
                patch.object(evaluation, "load_questions", return_value=[question]),
                patch.object(
                    rag, "list_corpus_documents", return_value=[Path("guide.md")]
                ),
                patch.object(evaluation, "RESULTS_DIR", output_dir),
            ):
                result = evaluation.run_retrieval_evaluation(
                    "kestrel",
                    {"name": "test", "chunk_size": 800, "overlap_percent": 10},
                    lambda _: [passage],
                )

            self.assertEqual(
                result["questions"][0]["retrieved_passages"][0]["id"], "chunk-1"
            )
            saved_rows = [
                json.loads(line)
                for line in next(output_dir.glob("*.jsonl"))
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(
                saved_rows[1]["retrieved_passages"][0]["id"], "chunk-1"
            )

    def test_no_context_evaluation_passes_question_answerability_to_judge(self) -> None:
        question = {
            "id": "q1",
            "question": "What is the fact?",
            "type": "exact_identifier",
            "answerable": True,
            "evidence": [{"source": "guide.md", "quote": "fact"}],
            "expected_answer": "The fact is seven.",
        }
        judge = Mock(return_value={"correct": False, "reason": "Abstained."})
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(evaluation, "load_questions", return_value=[question]),
                patch.object(
                    rag, "generate_no_context_answer", return_value="I do not know."
                ),
                patch.object(rag, "judge_no_context_answer", judge),
                patch.object(evaluation, "NO_CONTEXT_DIR", Path(temp_dir)),
            ):
                evaluation.run_no_context_evaluation("kestrel")

        judge.assert_called_once_with(
            "What is the fact?",
            "I do not know.",
            "The fact is seven.",
            True,
        )


if __name__ == "__main__":
    unittest.main()
