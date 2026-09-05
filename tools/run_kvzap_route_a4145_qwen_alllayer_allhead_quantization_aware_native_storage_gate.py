"""A4.1.3.10 all-layer/all-head Qwen native-storage gate with hard cast envelope."""

from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import main


A4145_SCHEMA = "kvzap-route-a4145-qwen-alllayer-allhead-quantization-aware-native-storage-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4145_SCHEMA,
        phase="A4.1.3.10",
        artifact_stem="a4145_qwen_alllayer_allhead_quantization_aware_native_storage",
        required_admission_budget=1,
        required_state_flags=("require_any_pending",),
        scope="all_layers",
        execution_dtype_ulp_mode="record_only",
        execution_dtype_close_mode="quantization_aware_enforce",
    )
