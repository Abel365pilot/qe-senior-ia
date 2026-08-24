import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_full_dataset_has_required_distribution_and_seeded_responses():
    rows = read_jsonl(ROOT / "data" / "evaluation_cases.jsonl")
    assert len(rows) == 6
    assert Counter(row["segment"] for row in rows) == {
        "answerable": 2,
        "unanswerable": 1,
        "adversarial": 3,
    }
    assert len({row["case_id"] for row in rows}) == 6
    assert all(row["response"].strip() and row["response_bad"].strip() for row in rows)


def test_debug_dataset_has_two_rows():
    assert len(read_jsonl(ROOT / "data" / "debug_2rows.jsonl")) == 2
