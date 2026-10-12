from pathlib import Path

from tools.validate_rtl3_8_2_functional_sidecar_delivery import main


def test_rtl3_8_2_functional_sidecar_delivery_manifest_is_hash_bound():
    root = Path(__file__).resolve().parents[1]
    assert main(["--repository-root", str(root)]) == 0
