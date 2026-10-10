from pathlib import Path

from tools.validate_rtl3_7b_terminal_release_global_drain import validate


def test_rtl3_7b_terminal_release_global_drain_manifest_is_hash_bound() -> None:
    root = Path(__file__).resolve().parents[1]
    validate(root / "analysis/rtl3_7b_terminal_release_global_drain_manifest.json", root)
