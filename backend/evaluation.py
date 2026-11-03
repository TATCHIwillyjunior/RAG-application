import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from . import rag


PROJECT_DIR = Path(__file__).resolve().parents[1]
QUESTION_SETS = {
    "kestrel": PROJECT_DIR / "evaluation" / "question_sets" / "kestrel.jsonl",
    "vellora": PROJECT_DIR / "evaluation" / "question_sets" / "vellora.jsonl",
    "project-docs": PROJECT_DIR / "evaluation" / "question_sets" / "project-docs.jsonl",
}
RESULTS_DIR = PROJECT_DIR / "evaluation" / "results"
NO_CONTEXT_DIR = PROJECT_DIR / "evaluation" / "no_context"
METRIC_CUTOFFS = (1, 3, 5, 10)
MANUAL_GRADES = {"correct", "partial", "wrong", "unsupported"}
logger = logging.getLogger(__name__)
_results_lock = threading.Lock()


def load_questions(corpus_id: str) -> list[dict[str, Any]]:
    try:
        question_file = QUESTION_SETS[corpus_id]
    except KeyError as error:
        raise ValueError(f"No evaluation question set for corpus '{corpus_id}'.") from error
    try:
        records = [
            json.loads(line)
            for line in question_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as error:
        logger.exception("Could not load evaluation questions for %s", corpus_id)
        raise ValueError(f"The {corpus_id} evaluation question set is invalid.") from error
    if not records:
        raise ValueError(f"The {corpus_id} evaluation question set is empty.")
    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"The {corpus_id} question set has an incomplete record.")
        if (
            not isinstance(record.get("id"), str)
            or not record["id"].strip()
            or record["id"] in seen_ids
            or not isinstance(record.get("question"), str)
            or not record["question"].strip()
            or not isinstance(record.get("type"), str)
            or not record["type"].strip()
            or not isinstance(record.get("answerable"), bool)
            or not isinstance(record.get("expected_answer"), str)
            or not record["expected_answer"].strip()
            or not isinstance(record.get("evidence"), list)
        ):
            raise ValueError(f"The {corpus_id} question set has an invalid record.")
        seen_ids.add(record["id"])
        if not record["answerable"] and record["evidence"]:
            raise ValueError(
                f"Unanswerable question '{record['id']}' must not include evidence."
            )
        for item in record["evidence"]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("source"), str)
                or not item["source"].strip()
                or not isinstance(item.get("quote"), str)
                or not item["quote"].strip()
            ):
                raise ValueError(
                    f"Question '{record['id']}' has an invalid evidence item."
                )
        if record["answerable"] and not record["evidence"]:
            raise ValueError(
                f"Answerable question '{record['id']}' must include evidence."
            )
    return records


def _metric_values(
    question: dict[str, Any], passages: list[rag.Passage]
) -> dict[str, dict[str, float | int | None]]:
    evidence = question["evidence"] if question["answerable"] else []
    values: dict[str, dict[str, float | int | None]] = {}
    for cutoff in METRIC_CUTOFFS:
        top_passages = passages[:cutoff]
        matched = sum(
            any(
                item["source"] == passage.filename
                and item["quote"].casefold() in passage.text.casefold()
                for passage in top_passages
            )
            for item in evidence
        )
        values[str(cutoff)] = {
            "hit": int(matched > 0) if question["answerable"] else None,
            "evidence_recall": matched / len(evidence) if evidence else None,
        }
    return values


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["answerable"]]
    result: dict[str, Any] = {}
    for cutoff in METRIC_CUTOFFS:
        hit_values = [row["metrics"][str(cutoff)]["hit"] for row in eligible]
        recall_values = [
            row["metrics"][str(cutoff)]["evidence_recall"] for row in eligible
        ]
        result[str(cutoff)] = {
            "answerable_questions": len(eligible),
            "hit_rate": sum(hit_values) / len(hit_values) if hit_values else None,
            "mean_evidence_recall": (
                sum(recall_values) / len(recall_values) if recall_values else None
            ),
        }
    return result


def _result_path(run_id: str, no_context: bool = False) -> Path:
    directory = NO_CONTEXT_DIR if no_context else RESULTS_DIR
    return directory / f"{run_id}.jsonl"


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _results_lock:
        try:
            with path.open("a", encoding="utf-8", newline="\n") as result_file:
                for record in records:
                    result_file.write(
                        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                    )
        except OSError as error:
            logger.exception("Could not save evaluation output to %s", path)
            raise RuntimeError("The evaluation results could not be saved.") from error


def run_retrieval_evaluation(
    corpus_id: str,
    configuration: dict[str, Any],
    search: Callable[[dict[str, Any]], list[rag.Passage]],
    include_answers: bool = False,
) -> dict[str, Any]:
    questions = load_questions(corpus_id)
    filenames = [path.name for path in rag.list_corpus_documents(corpus_id)]
    if not filenames:
        raise ValueError(f"No documents are available in the {corpus_id} corpus.")
    config = {
        "name": configuration.get("name", "baseline"),
        "chunk_size": configuration.get("chunk_size", 800),
        "overlap_percent": configuration.get("overlap_percent", 10),
    }
    if not 100 <= config["chunk_size"] <= 2000:
        raise ValueError("Chunk size must be between 100 and 2000 characters.")
    if not 0 <= config["overlap_percent"] <= 50:
        raise ValueError("Overlap must be between 0 and 50 percent.")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    question_rows: list[dict[str, Any]] = []
    for question in questions:
        query = {
            "corpus_id": corpus_id,
            "question": question["question"],
            "document_names": filenames,
            "chunk_size": config["chunk_size"],
            "overlap_percent": config["overlap_percent"],
            "top_k": 10,
        }
        passages = search(query)
        row: dict[str, Any] = {
            "record_type": "question",
            "run_id": run_id,
            "corpus_id": corpus_id,
            "configuration": config,
            "question_id": question["id"],
            "question": question["question"],
            "type": question["type"],
            "answerable": question["answerable"],
            "evidence": question["evidence"],
            "expected_answer": question["expected_answer"],
            "metrics": _metric_values(question, passages),
            "retrieved_passages": [
                {
                    "id": passage.id,
                    "filename": passage.filename,
                    "chunk_index": passage.chunk_index,
                    "start_char": passage.start_char,
                    "end_char": passage.end_char,
                    "text": passage.text,
                    "distance": passage.distance,
                }
                for passage in passages
            ],
            "manual_grade": None,
            "grade_comment": None,
        }
        if include_answers:
            generated = rag.generate_grounded_answer(question["question"], passages)
            row["generated_answer"] = generated.answer
            row["citation_ids"] = generated.citation_ids
        question_rows.append(row)

    by_type: dict[str, Any] = {}
    for question_type in sorted({row["type"] for row in question_rows}):
        by_type[question_type] = _aggregate(
            [row for row in question_rows if row["type"] == question_type]
        )
    summary = {
        "record_type": "summary",
        "run_id": run_id,
        "corpus_id": corpus_id,
        "configuration": config,
        "question_count": len(question_rows),
        "answerable_count": sum(row["answerable"] for row in question_rows),
        "overall": _aggregate(question_rows),
        "by_type": by_type,
    }
    _write_jsonl(_result_path(run_id), [summary, *question_rows])
    return {"summary": summary, "questions": question_rows}


def run_no_context_evaluation(corpus_id: str) -> dict[str, Any]:
    questions = load_questions(corpus_id)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    rows = []
    for question in questions:
        answer = rag.generate_no_context_answer(question["question"])
        judgment = rag.judge_no_context_answer(
            question["question"],
            answer,
            question["expected_answer"],
            question["answerable"],
        )
        rows.append(
            {
                "record_type": "no_context",
                "run_id": run_id,
                "corpus_id": corpus_id,
                "question_id": question["id"],
                "question": question["question"],
                "type": question["type"],
                "answerable": question["answerable"],
                "expected_answer": question["expected_answer"],
                "no_context_answer": answer,
                "no_context_correct": judgment["correct"],
                "judge_reason": judgment["reason"],
            }
        )
    summary = {
        "record_type": "summary",
        "run_id": run_id,
        "corpus_id": corpus_id,
        "question_count": len(rows),
        "correct_count": sum(row["no_context_correct"] for row in rows),
        "correct_rate": sum(row["no_context_correct"] for row in rows) / len(rows),
    }
    _write_jsonl(_result_path(run_id, no_context=True), [summary, *rows])
    return {"summary": summary, "questions": rows}


def list_runs() -> list[dict[str, Any]]:
    runs = []
    for directory in (RESULTS_DIR, NO_CONTEXT_DIR):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.jsonl"), reverse=True):
            try:
                records = [
                    json.loads(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except (OSError, json.JSONDecodeError) as error:
                logger.exception("Could not read evaluation result %s", path)
                raise RuntimeError(f"Could not read evaluation run '{path.stem}'.") from error
            if records and records[0].get("record_type") == "summary":
                runs.append(records[0])
    return sorted(runs, key=lambda run: run["run_id"], reverse=True)


def get_run(run_id: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", run_id):
        raise ValueError("Invalid run ID.")
    path = _result_path(run_id)
    if not path.is_file():
        path = _result_path(run_id, no_context=True)
    if not path.is_file():
        raise FileNotFoundError(f"Evaluation run '{run_id}' was not found.")
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as error:
        logger.exception("Could not read evaluation run %s", run_id)
        raise RuntimeError(f"Could not read evaluation run '{run_id}'.") from error


def save_grade(
    run_id: str, question_id: str, grade: str, comment: str | None
) -> dict[str, Any]:
    if grade not in MANUAL_GRADES:
        raise ValueError(f"Grade must be one of: {', '.join(sorted(MANUAL_GRADES))}.")
    if len(comment or "") > 2000:
        raise ValueError("Grade comments must be 2000 characters or fewer.")
    path = _result_path(run_id)
    if not path.is_file():
        raise FileNotFoundError(f"Retrieval evaluation run '{run_id}' was not found.")
    with _results_lock:
        records = get_run(run_id)
        updated = False
        for record in records:
            if (
                record.get("record_type") == "question"
                and record.get("question_id") == question_id
            ):
                record["manual_grade"] = grade
                record["grade_comment"] = comment
                record["graded_at"] = datetime.now(timezone.utc).isoformat()
                updated = True
                break
        if not updated:
            raise FileNotFoundError(
                f"Question '{question_id}' was not found in run '{run_id}'."
            )
        temporary = path.with_suffix(".jsonl.tmp")
        try:
            temporary.write_text(
                "".join(
                    json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                    for record in records
                ),
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as error:
            logger.exception("Could not save evaluation grade to %s", path)
            raise RuntimeError("The evaluation grade could not be saved.") from error
    return next(
        record
        for record in records
        if record.get("record_type") == "question"
        and record.get("question_id") == question_id
    )
