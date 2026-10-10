from pathlib import Path

from tools.validate_rtl3_completion_cross_owner_review_03 import main


def test_rtl3_completion_cross_owner_review_03_manifest_is_hash_bound():
    root = Path(__file__).resolve().parents[1]
    assert main(["--repository-root", str(root)]) == 0
