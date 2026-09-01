"""Confirm or reject a high-cap, natural-early-stop Route-A counterexample.

This tool compares two validated Route-A2 lifecycle collections for exactly
the same request. The only intentionally different request parameter is
``max_new_tokens``. It answers a narrow question: did the higher-cap run
terminate before consuming its advertised cap? A confirmed result is direct
evidence that a caller's *upper bound* alone cannot protect every short
request from unnecessary admission. It does not model hardware costs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.validate_kvzap_decode_lifecycle_trace import validate as validate_lifecycle


SUMMARY_COLUMNS = (
    "request_id", "request_content_hash", "reference_max_new_tokens",
    "reference_decode_model_calls", "high_cap_max_new_tokens",
    "high_cap_decode_model_calls", "high_cap_unused_decode_budget",
    "same_answer_sha256", "high_cap_naturally_stopped_before_cap",
    "counterexample_confirmed", "interpretation",
)
COMPARABLE_TOP_LEVEL = (
    "request_id", "model", "model_revision", "predictor_checkpoint",
    "predictor_revision", "threshold", "sliding_window", "page_tokens",
    "kv_bytes_per_layer_head_token", "metadata_bytes_per_cold_page",
)
COMPARABLE_CONFIG = (
    "request_id", "request_content_hash", "model", "model_revision",
    "predictor", "predictor_revision", "threshold", "sliding_window",
    "page_tokens", "kv_bytes_per_token", "metadata_bytes_per_page", "seed",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Route-A3.15 high-cap/natural-early-stop counterexample check; never loads a model.")
    parser.add_argument("--reference-lifecycle-dir", type=Path, required=True, help="Validated A2 run at the original lower caller cap.")
    parser.add_argument("--high-cap-lifecycle-dir", type=Path, required=True, help="Validated A2 rerun of the same request at a higher caller cap.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory only.")
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(directory: Path) -> dict[str, Any]:
    path = directory / "lifecycle_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing lifecycle manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kvzap-route-a2-readonly-lifecycle-1.0":
        raise ValueError("A3.15 requires Route-A2 lifecycle schema 1.0")
    return manifest


def decode_calls(manifest: dict[str, Any]) -> int:
    calls = manifest.get("decode_lifecycle_observation", {}).get("decode_model_call_count")
    if not isinstance(calls, int) or calls < 0:
        raise ValueError("A2 lifecycle has no valid decode_model_call_count")
    return calls


def answer_hash(manifest: dict[str, Any]) -> str:
    value = manifest.get("trace_equivalence", {}).get("normal_observer_record_answer_sha256")
    if not isinstance(value, str) or not value:
        raise ValueError("A2 lifecycle has no normal/observer/record answer hash")
    return value


def assert_comparable(reference: dict[str, Any], high: dict[str, Any]) -> None:
    for key in COMPARABLE_TOP_LEVEL:
        if reference.get(key) != high.get(key):
            raise ValueError(f"A3.15 inputs differ in required top-level field: {key}")
    reference_config, high_config = reference.get("config", {}), high.get("config", {})
    for key in COMPARABLE_CONFIG:
        if reference_config.get(key) != high_config.get(key):
            raise ValueError(f"A3.15 inputs differ in required config field: {key}")
    if not isinstance(reference_config.get("max_new_tokens"), int) or not isinstance(high_config.get("max_new_tokens"), int):
        raise ValueError("A3.15 inputs require integer config.max_new_tokens")
    if int(high_config["max_new_tokens"]) <= int(reference_config["max_new_tokens"]):
        raise ValueError("high-cap max_new_tokens must be strictly larger than the reference cap")


def summarize(reference: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    assert_comparable(reference, high)
    ref_cap, high_cap = int(reference["config"]["max_new_tokens"]), int(high["config"]["max_new_tokens"])
    ref_calls, high_calls = decode_calls(reference), decode_calls(high)
    stopped = high_calls < high_cap
    same_answer = answer_hash(reference) == answer_hash(high)
    confirmed = stopped and same_answer
    return {
        "request_id": reference["request_id"], "request_content_hash": reference["config"]["request_content_hash"],
        "reference_max_new_tokens": ref_cap, "reference_decode_model_calls": ref_calls,
        "high_cap_max_new_tokens": high_cap, "high_cap_decode_model_calls": high_calls,
        "high_cap_unused_decode_budget": high_cap - high_calls, "same_answer_sha256": same_answer,
        "high_cap_naturally_stopped_before_cap": stopped, "counterexample_confirmed": confirmed,
        "interpretation": (
            "Confirmed same-input high-cap early-stop counterexample: a max_new_tokens-only gate would activate admission despite unused caller budget; a lower-bound continuation contract or safe fallback is required."
            if confirmed else "Not a confirmed counterexample: either the high-cap run consumed its cap or its answer hash differs. Do not infer a continuation-contract requirement from this pair alone."
        ),
    }


def write_csv(path: Path, row: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader(); writer.writerow(row)


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    validate_lifecycle(args.reference_lifecycle_dir)
    validate_lifecycle(args.high_cap_lifecycle_dir)
    reference, high = load_manifest(args.reference_lifecycle_dir), load_manifest(args.high_cap_lifecycle_dir)
    row = summarize(reference, high)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "cap_mismatch_summary.csv", row)
    manifest = {
        "schema_version": "kvzap-route-a315-cap-mismatch-1.0", "git_commit": get_git_commit(),
        "reference_lifecycle_dir": str(args.reference_lifecycle_dir), "high_cap_lifecycle_dir": str(args.high_cap_lifecycle_dir),
        "source_sha256": {"reference_lifecycle_manifest": sha256(args.reference_lifecycle_dir / "lifecycle_manifest.json"), "reference_lifecycle_events": sha256(args.reference_lifecycle_dir / "lifecycle_events.csv"), "high_cap_lifecycle_manifest": sha256(args.high_cap_lifecycle_dir / "lifecycle_manifest.json"), "high_cap_lifecycle_events": sha256(args.high_cap_lifecycle_dir / "lifecycle_events.csv")},
        "result": row,
        "boundaries": ["This compares validated Full-KV read-only lifecycle observations; it does not change KVzap masks or execute sparse attention.", "A confirmed pair proves only that this same request naturally ended before a higher advertised max_new_tokens cap.", "It is not a hardware measurement, HBM/DRAM traffic measurement, allocator measurement, latency/throughput result, or a general output-length predictor evaluation."],
    }
    (args.output_dir / "cap_mismatch_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.15 high-cap early-stop counterexample {'CONFIRMED' if row['counterexample_confirmed'] else 'not confirmed'}: {args.output_dir}")


if __name__ == "__main__":
    main()
