import hashlib
import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from hardware.route_a.mem.cacti_runner import (
    CactiMacroRunner,
    MacroSpec,
    ToolchainError,
    materialize_cacti_config,
    parse_cacti_stdout,
)


TEMPLATE = '''-size (bytes) 131072
-block size (bytes) 64
-associativity 2
-read-write port 1
-exclusive read port 0
-exclusive write port 0
-single ended read ports 0
-UCA bank count 1
-technology (u) 0.090
-output/input bus width 512
-cache type "cache"
'''


def test_macro_spec_requires_explicit_nonzero_port_and_byte_alignment():
    with pytest.raises(ValueError, match="at least one explicit port"):
        MacroSpec("no_ports", 1, 64, readwrite_ports=0)
    with pytest.raises(ValueError, match="byte aligned"):
        MacroSpec("odd_width", 1, 7)


def test_config_preserves_requested_capacity_padding_and_explicit_ports():
    spec = MacroSpec("metadata", depth=29, width_bits=64, instances=8, read_ports=1, write_ports=1, readwrite_ports=0)
    config, capacity = materialize_cacti_config(TEMPLATE, spec, 0.032)
    assert capacity == {
        "requested_bytes_per_instance": 232,
        "modeled_bytes_per_instance": 1024,
        "minimum_array_padding_bytes_per_instance": 792,
        "line_size_bytes": 8,
    }
    assert "-exclusive read port 1" in config
    assert "-exclusive write port 1" in config
    assert "-read-write port 0" in config
    assert '-cache type "ram"' in config


def test_stdout_parser_retains_only_macro_characterization_values():
    parsed = parse_cacti_stdout(
        "Access time (ns): 0.15\nCycle time (ns): 0.12\n"
        "Total dynamic read energy per access (nJ): 0.001\n"
        "Total dynamic write energy per access (nJ): 0.002\n"
        "Data array: Area (mm2): 0.003\n"
    )
    assert parsed["dynamic_read_energy_pj"] == 1.0
    assert parsed["dynamic_write_energy_pj"] == 2.0
    assert parsed["data_array_area_mm2"] == 0.003


def make_toolchain(tmp_path: Path) -> Path:
    root = tmp_path / "toolchain"
    source, binary_dir = root / "src" / "cacti", root / "bin"
    source.mkdir(parents=True)
    binary_dir.mkdir()
    (source / "cache.cfg").write_text(TEMPLATE, encoding="utf-8")
    (source / ".git").mkdir()
    binary = binary_dir / "cacti"
    binary.write_text("mock", encoding="utf-8")
    binary.chmod(0o755)
    source_url, source_commit = "https://github.com/HewlettPackard/cacti.git", "1ffd8dfb10303d306ecd8d215320aea07651e878"
    (root / "source_lock.json").write_text(json.dumps({
        "lock_schema_version": "route-a-cacti-toolchain-lock-1.0",
        "source_url": source_url,
        "source_commit": source_commit,
        "build_command": ["make", "-j2"],
        "technology_proxy_default_um": .032,
        "use_boundary": "test boundary",
    }), encoding="utf-8")
    (root / "toolchain_manifest.json").write_text(json.dumps({
        "manifest_schema_version": "route-a-cacti-toolchain-manifest-1.0",
        "source_url": source_url,
        "source_commit": source_commit,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "template_sha256": hashlib.sha256((source / "cache.cfg").read_bytes()).hexdigest(),
    }), encoding="utf-8")
    return root


def test_runner_executes_from_source_checkout_and_saves_raw_artifacts(tmp_path, monkeypatch):
    root = make_toolchain(tmp_path)
    runner = CactiMacroRunner(root)
    source = root / "src" / "cacti"
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "git":
            response = "1ffd8dfb10303d306ecd8d215320aea07651e878\n" if args[-1] == "HEAD" else "https://github.com/HewlettPackard/cacti.git\n"
            return CompletedProcess(args, 0, stdout=response)
        return CompletedProcess(args, 0, stdout=(
            "Access time (ns): 0.15\nCycle time (ns): 0.12\n"
            "Total dynamic read energy per access (nJ): 0.001\n"
            "Total dynamic write energy per access (nJ): 0.002\n"
            "Data array: Area (mm2): 0.003\n"
        ), stderr="")

    import hardware.route_a.mem.cacti_runner as runner_module
    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)
    output = tmp_path / "new_output"
    record = runner.run(MacroSpec("unit", 128, 64), output)
    cacti_call = calls[-1]
    assert cacti_call[1]["cwd"] == source
    assert Path(cacti_call[0][-1]).is_absolute()
    assert (output / "cache.cfg").is_file()
    assert (output / "cacti.stdout.log").is_file()
    assert record["aggregate_data_array_area_mm2"] == .003


def test_runner_requires_new_output_directory(tmp_path, monkeypatch):
    root = make_toolchain(tmp_path)
    runner = CactiMacroRunner(root)
    output = tmp_path / "already_exists"
    output.mkdir()
    with pytest.raises(FileExistsError):
        runner.run(MacroSpec("unit", 128, 64), output)
