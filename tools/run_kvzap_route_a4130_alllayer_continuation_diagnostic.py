"""A4.1.2.10 all-36-layer entrypoint for the shared continuation gate."""

from tools.run_kvzap_route_a4129_multilayer_continuation_diagnostic import main


A4130_SCHEMA = "kvzap-route-a4130-alllayer-continuation-diagnostic-1.0"


if __name__ == "__main__":
    main(
        schema_version=A4130_SCHEMA,
        phase="A4.1.2.10",
        scope="all_layers",
        artifact_stem="a4130_alllayer_continuation",
    )
