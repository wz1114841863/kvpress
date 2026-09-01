"""Create an immutable, single-lifecycle A2 hash boundary for Route-A3.15.

The existing Route-A2 freeze is intentionally not edited. This utility
validates one newly collected A2 directory and writes a separate compatible
freeze file that downstream A3.10/A3.11 tools can verify.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_trace import get_git_commit
from tools.validate_kvzap_decode_lifecycle_trace import validate


ARTIFACTS = ("lifecycle_events.csv", "lifecycle_final_state.csv", "lifecycle_manifest.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a new hash freeze for one validated Route-A2 lifecycle; never loads a model.")
    parser.add_argument("--lifecycle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; writes route_a315_lifecycle_freeze.json.")
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(lifecycle_dir: Path) -> dict[str, Any]:
    validate(lifecycle_dir)
    manifest = json.loads((lifecycle_dir / "lifecycle_manifest.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "kvzap-route-a2-lifecycle-freeze-1.0",
        "freeze_status": "completed_evidence_boundary",
        "scope": "One validated Route-A3.15 high-cap lifecycle. This is read-only Full-KV observation, not KVzap-pruned generation or a hardware measurement.",
        "created_by": "tools/freeze_kvzap_route_a315_lifecycle.py",
        "git_commit": get_git_commit(),
        "source_lifecycle_dir": str(lifecycle_dir),
        "fixed_configuration": {key: manifest[key] for key in ("model", "model_revision", "predictor_checkpoint", "predictor_revision", "threshold", "sliding_window", "page_tokens", "kv_bytes_per_layer_head_token", "metadata_bytes_per_cold_page")},
        "validated_samples": [{"experiment": lifecycle_dir.name, "request_id": manifest["request_id"], "decode_model_call_count": manifest["decode_lifecycle_observation"]["decode_model_call_count"], "max_new_tokens": manifest["config"]["max_new_tokens"]}],
        "artifact_sha256": {lifecycle_dir.name: {name: sha256(lifecycle_dir / name) for name in ARTIFACTS}},
    }


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.output_dir}")
    freeze = build(args.lifecycle_dir)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    path = args.output_dir / "route_a315_lifecycle_freeze.json"
    path.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Route-A3.15 lifecycle freeze written: {path}")


if __name__ == "__main__":
    main()
