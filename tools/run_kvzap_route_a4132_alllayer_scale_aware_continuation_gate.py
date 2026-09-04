"""A4.1.2.12 all-layer hard scale-aware execution-dtype continuation gate."""

from tools.run_kvzap_route_a4129_multilayer_continuation_diagnostic import main


A4132_SCHEMA = "kvzap-route-a4132-alllayer-scale-aware-continuation-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4132_SCHEMA,
        phase="A4.1.2.12",
        scope="all_layers",
        artifact_stem="a4132_alllayer_scale_aware_continuation",
        execution_dtype_ulp_mode="record_only",
        execution_dtype_close_mode="enforce",
    )
