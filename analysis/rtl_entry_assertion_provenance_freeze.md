# Gate-RTL0.3 assertion-planning provenance freeze

**Status:** `complete_non_implementational_assertion_planning; rtl_entry_review_pending`.

| Material | SHA-256 |
|---|---|
| `analysis/rtl_entry_assertion_matrix.json` | `0bcc9263c0c5e8c80af90b28872653d587e35f2f04256bbdcf4139aff47bcfc2` |
| `analysis/rtl_entry_assertion_verification_contract.md` | `a65bd24658f53d8607128316470209be30c60b7eb194b1fec828807566b7868c` |
| `tools/validate_rtl_entry_assertion_matrix.py` | `63397ec704e4294d4ed0aee7a1b2016bc0aa23de73b701fa3fd08d4a9428de76` |
| `tests/test_rtl_entry_assertion_matrix.py` | `e0d8029e997df5933f48ebe06c9087b12f73b84e5767f8c11c118e15a23e7d08` |

Completed no-model command:

```text
.venv/bin/python tools/validate_rtl_entry_assertion_matrix.py --help
.venv/bin/python tools/validate_rtl_entry_assertion_matrix.py
.venv/bin/python -m pytest -q tests/test_rtl_entry_assertion_matrix.py tests/test_rtl_entry_interface_manifest.py
```

Result: 8 passed. This freeze is assertion/testbench planning only: it makes no
SVA/RTL correctness, formal-proof, timing, throughput, controller, PPA, model,
GPU, or new-A4-DSE claim. Progress obligations remain conditional on the matrix
environment assumptions and finite verification abstraction.
