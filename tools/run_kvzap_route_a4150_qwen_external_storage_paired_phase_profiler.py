"""A4.1.6.1 paired phase-profiler coverage repair."""

from tools.run_kvzap_route_a4149_qwen_external_storage_phase_profiler import main


if __name__ == "__main__":
    main(
        schema_version="kvzap-route-a4150-qwen-external-storage-paired-phase-profiler-1.0",
        phase="A4.1.6.1",
        artifact_stem="a4150_external_storage_paired_phase_profiler",
        coalesce_rows=True,
        require_phase_coverage=True,
    )
