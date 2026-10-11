from pathlib import Path

from tools.validate_rtl3_8_1_packed_activation_binding import main


def test_rtl3_8_1_packed_activation_binding_manifest_is_hash_bound():
    root = Path(__file__).resolve().parents[1]
    assert main(["--repository-root", str(root)]) == 0
