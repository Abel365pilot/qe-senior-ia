import csv
from pathlib import Path

import yaml

import analyze_results
import load_profile


ROOT = Path(__file__).resolve().parents[1]


def test_prompts_are_varied_and_keep_concurrency_as_first_ceiling():
    with (ROOT / "prompts.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 12
    assert len({row["prompt"] for row in rows}) == 12
    assert {row["size"] for row in rows} == {"short", "medium", "long"}

    average_input_tokens = sum(len(row["prompt"]) // 4 for row in rows) / len(rows)
    average_total_tokens = 128 + average_input_tokens
    service_seconds = (250 + 128 * 8) / 1000
    concurrency_capacity_rps = 4 / service_seconds
    tpm_capacity_rps = 34000 / (average_total_tokens * 60)

    assert 35 <= average_input_tokens <= 45
    assert concurrency_capacity_rps < tpm_capacity_rps


def test_saturation_shape_crosses_the_concurrency_limit():
    stages = load_profile.build_stages("saturation", stage_seconds=60)
    assert [stage["users"] for stage in stages] == [1, 2, 4, 6, 10, 20, 40, 60]
    assert [stage["duration"] for stage in stages] == [60, 120, 180, 240, 300, 360, 420, 480]
    assert load_profile.stage_at(stages, 179)["users"] == 4
    assert load_profile.stage_at(stages, 480) is None


def test_control_shape_is_short_and_repeatable():
    stages = load_profile.build_stages("control")
    assert stages == [
        {"duration": 10, "users": 40, "spawn_rate": 4},
        {"duration": 70, "users": 40, "spawn_rate": 4},
    ]


def test_azure_configuration_references_all_required_artifacts_and_gates():
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    assert config["version"] == "v0.1"
    assert config["testType"] == "Locust"
    assert config["testPlan"] == "locustfile.py"
    assert config["engineInstances"] == 1
    assert config["properties"]["userPropertyFile"] == "locust.conf"
    assert "prompts.csv" in config["configurationFiles"]
    criteria = "\n".join(config["failureCriteria"])
    assert "p95(response_time_ms)" in criteria
    assert "percentage(error)" in criteria
    assert config["autoStop"]["errorPercentage"] > 0
    assert config["autoStop"]["timeWindow"] >= 10
    assert all(item["name"] != "TARGET_HOST" for item in config["env"])
    for filename in (config["testPlan"], config["properties"]["userPropertyFile"], *config["configurationFiles"]):
        assert (ROOT / filename).is_file()


def test_saturation_baseline_uses_stable_four_user_stage():
    history = analyze_results._history(
        ROOT / "results" / "saturation-20260824-171114" / "locust_stats_history.csv",
        "saturation",
    )

    assert history["first_sample_p95_ms"] == 1200.0
    assert history["reference_baseline_users"] == 4
    assert history["reference_baseline_p95_ms"] == 1500.0
    assert history["reference_baseline_method"] == "median_last_30_samples"
    assert history["first_p95_at_least_2x_reference_baseline"]["users"] == 10
