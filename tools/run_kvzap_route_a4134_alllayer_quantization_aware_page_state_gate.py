"""A4.1.2.14 all-layer multi-page state gate with hard cast envelope."""

from tools.run_kvzap_route_a4129_multilayer_continuation_diagnostic import main


A4134_SCHEMA = "kvzap-route-a4134-alllayer-quantization-aware-page-state-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4134_SCHEMA,
        phase="A4.1.2.14",
        scope="all_layers",
        artifact_stem="a4134_alllayer_quantization_aware_page_state",
        execution_dtype_ulp_mode="record_only",
        execution_dtype_close_mode="quantization_aware_enforce",
        required_admission_budget=512,
        required_state_flags=(
            "require_any_multi_page_packed",
            "require_any_full_packed_page",
            "require_any_tail_packed_page",
        ),
    )
