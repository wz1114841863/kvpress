"""A4.1.3.11 all-layer/all-head Qwen native-storage page-state semantic gate."""

from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import main


A4146_SCHEMA = "kvzap-route-a4146-qwen-alllayer-allhead-quantization-aware-native-storage-page-state-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4146_SCHEMA,
        phase="A4.1.3.11",
        artifact_stem="a4146_qwen_alllayer_allhead_quantization_aware_native_storage_page_state",
        required_admission_budget=512,
        required_state_flags=("require_any_full_multi_tail_packed",),
        scope="all_layers",
        execution_dtype_ulp_mode="record_only",
        execution_dtype_close_mode="quantization_aware_enforce",
    )
