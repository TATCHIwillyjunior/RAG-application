import argparse
import json
from typing import Any

from fastapi.testclient import TestClient

from . import evaluation, rag
from .main import app


def _configuration(value: str) -> dict[str, Any]:
    try:
        name, chunk_size, overlap = value.split(":")
        return {
            "name": name,
            "chunk_size": int(chunk_size),
            "overlap_percent": int(overlap),
        }
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(
            "Use CONFIG_NAME:CHUNK_SIZE:OVERLAP, for example small:400:10."
        ) from error


def _search_via_api(client: TestClient):
    def search(payload: dict[str, Any]) -> list[rag.Passage]:
        response = client.post("/api/search", json=payload)
        if response.is_error:
            raise RuntimeError(
                f"/api/search returned {response.status_code}: {response.text}"
            )
        return [rag.Passage(**passage) for passage in response.json()["passages"]]

    return search


def _run_v1_baseline(search) -> None:
    evaluation_file = rag.PROJECT_DIR / "backend" / "evaluation_set.json"
    cases = json.loads(evaluation_file.read_text(encoding="utf-8"))
    filenames = [path.name for path in rag.list_corpus_documents("project-docs")]
    answerable = [case for case in cases if case["expected_source"]]
    unanswerable = [case for case in cases if not case["expected_source"]]
    hits = 0
    abstentions = 0
    for case in cases:
        passages = search(
            {
                "corpus_id": "project-docs",
                "question": case["question"],
                "document_names": filenames,
                "chunk_size": 800,
                "overlap_percent": 10,
                "top_k": 5,
            }
        )
        if case["expected_source"]:
            found = any(
                passage.filename == case["expected_source"]
                and case["expected_text"].casefold() in passage.text.casefold()
                for passage in passages
            )
            hits += int(found)
            print(f"{'HIT' if found else 'MISS'}: {case['question']}")
        else:
            abstained = not passages
            abstentions += int(abstained)
            print(
                f"{'ABSTAIN PASS' if abstained else 'ABSTAIN FAIL'}: {case['question']}"
            )
    print(
        f"\nV1 Recall@5: {hits}/{len(answerable)} "
        f"({hits / len(answerable):.1%})"
    )
    print(
        f"V1 Abstention@5: {abstentions}/{len(unanswerable)} "
        f"({abstentions / len(unanswerable):.1%})"
    )
    print("V1 settings: chunk_size=800, overlap=10%, top_k=5")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate repeatable retrieval runs against the local FastAPI /api/search route."
    )
    parser.add_argument(
        "--corpus",
        choices=["kestrel", "vellora", "project-docs", "all"],
        default="all",
    )
    parser.add_argument(
        "--configuration",
        action="append",
        type=_configuration,
        dest="configurations",
        help="Repeatable CONFIG_NAME:CHUNK_SIZE:OVERLAP setting. Defaults to two settings.",
    )
    parser.add_argument(
        "--generate-answers",
        action="store_true",
        help="Also call Gemini with retrieved passages (uses API quota).",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Call Gemini without retrieval and ask Gemini to judge each answer (uses API quota).",
    )
    parser.add_argument(
        "--v1-baseline",
        action="store_true",
        help="Run the original V1 question set and Recall@5/Abstention@5 against project-docs.",
    )
    args = parser.parse_args()
    if args.v1_baseline and (
        args.configurations or args.generate_answers or args.no_context
    ):
        parser.error("--v1-baseline cannot be combined with V2 evaluation options.")
    configurations = args.configurations or [
        {"name": "baseline-800", "chunk_size": 800, "overlap_percent": 10},
        {"name": "small-400", "chunk_size": 400, "overlap_percent": 10},
    ]
    corpus_ids = ["kestrel", "vellora"] if args.corpus == "all" else [args.corpus]
    with TestClient(app) as client:
        search = _search_via_api(client)
        if args.v1_baseline:
            _run_v1_baseline(search)
            return
        for corpus_id in corpus_ids:
            for config in configurations:
                results = evaluation.run_retrieval_evaluation(
                    corpus_id,
                    config,
                    search,
                    include_answers=args.generate_answers,
                )
                print(
                    json.dumps(
                        {
                            "corpus_id": corpus_id,
                            "configuration": config,
                            "run_id": results["summary"]["run_id"],
                            "overall": results["summary"]["overall"],
                            "by_type": results["summary"]["by_type"],
                        },
                        indent=2,
                    )
                )
            if args.no_context:
                no_context_results = evaluation.run_no_context_evaluation(corpus_id)
                print(json.dumps(no_context_results["summary"], indent=2))


if __name__ == "__main__":
    main()
