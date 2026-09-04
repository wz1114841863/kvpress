"""A4.1.2.11 record-only all-layer execution-dtype ULP diagnostic.

The shared runner continues to enforce the FP32 packed/pending/hot same-mask
guard.  This entrypoint only changes the executed-dtype ULP response from a
hard failure into bounded scalar evidence, so it is deliberately not an A4.1
semantic acceptance or measurement gate.
"""

from tools.run_kvzap_route_a4129_multilayer_continuation_diagnostic import main


A4131_SCHEMA = "kvzap-route-a4131-alllayer-ulp-distribution-diagnostic-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4131_SCHEMA,
        phase="A4.1.2.11",
        scope="all_layers",
        artifact_stem="a4131_alllayer_ulp_distribution",
        execution_dtype_ulp_mode="record_only",
    )
