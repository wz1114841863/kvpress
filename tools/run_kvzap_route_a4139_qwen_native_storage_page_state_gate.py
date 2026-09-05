"""A4.1.3.4 budget-512 Qwen native-storage page-state semantic gate."""

from tools.run_kvzap_route_a4138_qwen_native_storage_replacement_gate import main


A4139_SCHEMA = "kvzap-route-a4139-qwen-native-storage-page-state-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4139_SCHEMA,
        phase="A4.1.3.4",
        artifact_stem="a4139_qwen_native_storage_page_state",
        required_admission_budget=512,
        required_state_flags=("require_multi_page_packed", "require_tail_packed"),
    )
