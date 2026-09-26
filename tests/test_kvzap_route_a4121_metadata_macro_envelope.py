from pathlib import Path
from subprocess import CompletedProcess

import tools.run_kvzap_route_a4121_metadata_macro_envelope as a4121
from tools.run_kvzap_route_a4121_metadata_macro_envelope import candidate_templates, mutate_cacti_config, parse_cacti_output


def a4120_stub():
    return {"interface_inventory": {"frozen_service_requirement": {"bank_count": 8, "mapping": "head_affine_v1"}, "logical_resource_contract": {"local_queue_capacity_per_bank_transaction_groups": 32, "shared_overflow_capacity_per_layer_transaction_groups": 256, "staging_capacity_per_layer_transaction_groups": 512}, "metadata_entry_accounting": {"declared_word_padded_width_bits": {"head_control": 64, "span_owner": 64}, "joint_safe_modeled_object_counts": {"head_control": 225, "span_owner": 614}}}}


def test_three_representative_candidates_keep_logical_contract_and_do_not_estimate_m3_register_area():
    rows = candidate_templates(a4120_stub())
    assert [row["name"] for row in rows] == ["M1_banked_sram_pipelined_rmw", "M2_replicated_or_duplicated_control_storage", "M3_register_hot_state_with_sram_backing"]
    assert all(row["logical_contract_entries_per_layer"] == 1024 for row in rows)
    assert rows[2]["non_cacti_state"][0]["area_status"] == "not_estimated_without_library_or_synthesis"


def test_cacti_config_is_single_rw_ram_proxy_with_fixed_public_node():
    template = "-size (bytes) 131072\n-block size (bytes) 64\n-associativity 2\n-read-write port 1\n-exclusive read port 0\n-exclusive write port 0\n-single ended read ports 0\n-UCA bank count 1\n-technology (u) 0.090\n-output/input bus width 512\n-cache type \"cache\"\n"
    config = mutate_cacti_config(template, 1024, .032)
    assert "-size (bytes) 1024" in config and "-cache type \"ram\"" in config
    assert "-technology (u) 0.032" in config and "-read-write port 1" in config


def test_cacti_output_parser_keeps_energy_as_macro_characterization_only():
    output = "Access time (ns): 0.15\nCycle time (ns): 0.12\nTotal dynamic read energy per access (nJ): 0.001\nTotal dynamic write energy per access (nJ): 0.002\nData array: Area (mm2): 0.003\n"
    parsed = parse_cacti_output(output)
    assert parsed["dynamic_read_energy_pj"] == 1.0
    assert parsed["data_array_area_mm2"] == .003


def test_cacti_runner_uses_source_checkout_cwd_and_absolute_generated_config(tmp_path, monkeypatch):
    source = tmp_path / "cacti"
    source.mkdir()
    template = "-size (bytes) 131072\n-block size (bytes) 64\n-associativity 2\n-read-write port 1\n-exclusive read port 0\n-exclusive write port 0\n-single ended read ports 0\n-UCA bank count 1\n-technology (u) 0.090\n-output/input bus width 512\n-cache type \"cache\"\n"
    (source / "cache.cfg").write_text(template, encoding="utf-8")
    binary = source / "cacti"
    binary.write_text("", encoding="utf-8")
    binary.chmod(0o755)
    output = tmp_path / "result"
    output.mkdir()
    called = {}
    def fake_run(args, **kwargs):
        called.update(args=args, **kwargs)
        return CompletedProcess(args, 0, stdout="Access time (ns): 0.15\nCycle time (ns): 0.12\nTotal dynamic read energy per access (nJ): 0.001\nTotal dynamic write energy per access (nJ): 0.002\nData array: Area (mm2): 0.003\n")
    monkeypatch.setattr(a4121.subprocess, "run", fake_run)
    a4121.run_cacti(binary, source, output, {"role": "unit", "instances": 1, "bytes_per_instance": 1024}, .032)
    assert called["cwd"] == source.resolve()
    assert Path(called["args"][-1]).is_absolute()
