from pathlib import Path

from tools.validate_rtl3_8_3_source_partial_boundary_isolation import main


def test_rtl3_8_3_source_partial_boundary_manifest_is_hash_bound():
    root = Path(__file__).resolve().parents[1]
    assert main(["--repository-root", str(root)]) == 0
