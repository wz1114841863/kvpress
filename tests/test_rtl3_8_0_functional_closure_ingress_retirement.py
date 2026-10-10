from pathlib import Path

from tools.validate_rtl3_8_0_functional_closure_ingress_retirement import main


def test_rtl3_8_0_ingress_retirement_manifest_is_hash_bound():
    root = Path(__file__).resolve().parents[1]
    assert main(["--repository-root", str(root)]) == 0
