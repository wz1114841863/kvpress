"""A4.1.3.9 budget-one all-layer/all-head Qwen native-storage semantic gate."""

from tools.run_kvzap_route_a4142_qwen_multilayer_allhead_native_storage_gate import main


A4144_SCHEMA = "kvzap-route-a4144-qwen-alllayer-allhead-native-storage-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4144_SCHEMA,
        phase="A4.1.3.9",
        artifact_stem="a4144_qwen_alllayer_allhead_native_storage",
        required_admission_budget=1,
        required_state_flags=("require_any_pending",),
        scope="all_layers",
    )
