import json
from pathlib import Path

from . import rag


def main() -> None:
    evaluation_file = Path(__file__).with_name("evaluation_set.json")
    cases = json.loads(evaluation_file.read_text(encoding="utf-8"))
    hits = 0
    answerable_cases = [case for case in cases if case["expected_source"]]
    unanswerable_cases = [case for case in cases if not case["expected_source"]]
    abstentions = 0
    filenames = [
        path.name
        for path in rag.DOCUMENTS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}
    ]
    if not filenames:
        raise RuntimeError(f"No .txt or .md evaluation documents found in {rag.DOCUMENTS_DIR}.")

    for case in cases:
        passages = rag.retrieve_passages(
            question=case["question"],
            filenames=filenames,
            chunk_size=800,
            overlap_percent=10,
            top_k=5,
        )
        if not case["expected_source"]:
            abstained = not passages
            abstentions += int(abstained)
            print(f"{'ABSTAIN PASS' if abstained else 'ABSTAIN FAIL'}: {case['question']}")
            continue

        expected_text = case["expected_text"].casefold()
        found = any(
            passage.filename == case["expected_source"]
            and expected_text in passage.text.casefold()
            for passage in passages
        )
        hits += int(found)
        print(f"{'HIT' if found else 'MISS'}: {case['question']}")
        if not found:
            print(f"  Expected passage: {case['expected_text']}")

    recall_at_5 = hits / len(answerable_cases) if answerable_cases else 0.0
    abstain_rate = abstentions / len(unanswerable_cases) if unanswerable_cases else 0.0
    print(
        f"\nRecall@5: {hits}/{len(answerable_cases)} ({recall_at_5:.1%})"
    )
    print(
        f"Abstention@5: {abstentions}/{len(unanswerable_cases)} ({abstain_rate:.1%})"
    )
    print("Baseline settings: chunk_size=800, overlap=10%, top_k=5")


if __name__ == "__main__":
    main()
