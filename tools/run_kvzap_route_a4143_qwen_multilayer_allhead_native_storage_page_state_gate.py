"""A4.1.3.8 budget-512 three-layer all-head Qwen page-state semantic gate."""

from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import main


A4143_SCHEMA = "kvzap-route-a4143-qwen-multilayer-allhead-native-storage-page-state-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4143_SCHEMA,
        phase="A4.1.3.8",
        artifact_stem="a4143_qwen_multilayer_allhead_native_storage_page_state",
        required_admission_budget=512,
        required_state_flags=("require_any_full_multi_tail_packed",),
    )
