"""A4.1.3.6 budget-512 all-KV-head Qwen native-storage page-state gate."""

from tools.run_kvzap_route_a4140_qwen_allhead_native_storage_gate import main


A4141_SCHEMA = "kvzap-route-a4141-qwen-allhead-native-storage-page-state-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4141_SCHEMA,
        phase="A4.1.3.6",
        artifact_stem="a4141_qwen_allhead_native_storage_page_state",
        required_admission_budget=512,
        required_state_flags=("require_any_full_multi_tail_packed",),
    )
