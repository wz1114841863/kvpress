"""A4.1.2.13 all-layer hard quantization-aware execution-dtype gate."""

from tools.run_kvzap_route_a4129_multilayer_continuation_diagnostic import main


A4133_SCHEMA = "kvzap-route-a4133-alllayer-quantization-aware-continuation-gate-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4133_SCHEMA,
        phase="A4.1.2.13",
        scope="all_layers",
        artifact_stem="a4133_alllayer_quantization_aware_continuation",
        execution_dtype_ulp_mode="record_only",
        execution_dtype_close_mode="quantization_aware_enforce",
    )
