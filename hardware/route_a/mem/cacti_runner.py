"""Verified public-CACTI runner for one explicit Route-A SRAM proxy macro.

This refactors the useful safety properties of the former ignored ``tmp/mem``
wrapper: one physical macro per invocation, explicit ports, generated config,
raw stdout/stderr preservation, and no silent width/capacity rounding.  Unlike
that legacy archive it requires a tracked upstream source lock and validates a
locally rebuilt binary before use.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


LOCK_SCHEMA = "route-a-cacti-toolchain-lock-1.0"
MANIFEST_SCHEMA = "route-a-cacti-toolchain-manifest-1.0"


class ToolchainError(RuntimeError):
    """The local CACTI toolchain does not match its tracked provenance lock."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class MacroSpec:
    """One physical CACTI proxy macro, with no implicit port selection."""

    name: str
    depth: int
    width_bits: int
    instances: int = 1
    read_ports: int = 0
    write_ports: int = 0
    readwrite_ports: int = 1
    role: str = "unspecified"

    def __post_init__(self) -> None:
        if not self.name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in self.name):
            raise ValueError("MacroSpec.name must be a non-empty filesystem-safe slug")
        for name, value in (
            ("depth", self.depth),
            ("width_bits", self.width_bits),
            ("instances", self.instances),
            ("read_ports", self.read_ports),
            ("write_ports", self.write_ports),
            ("readwrite_ports", self.readwrite_ports),
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"MacroSpec.{name} must be a non-negative integer")
        if self.depth <= 0 or self.width_bits <= 0 or self.instances <= 0:
            raise ValueError("MacroSpec depth, width_bits, and instances must be positive")
        if self.width_bits % 8:
            raise ValueError("MacroSpec.width_bits must be byte aligned for this SRAM proxy runner")
        if self.read_ports + self.write_ports + self.readwrite_ports <= 0:
            raise ValueError("MacroSpec must declare at least one explicit port")

    @property
    def requested_bytes_per_instance(self) -> int:
        return self.depth * (self.width_bits // 8)


def _replace_one(template: str, pattern: str, replacement: str) -> str:
    mutated, count = re.subn(pattern, replacement, template)
    if count != 1:
        raise ToolchainError(f"CACTI template does not contain exactly one expected setting: {pattern}")
    return mutated


def materialize_cacti_config(template: str, spec: MacroSpec, technology_node_um: float) -> tuple[str, dict[str, int]]:
    """Create an explicit single-bank RAM config and report CACTI padding.

    CACTI uses a minimum 1-KiB proxy array in this workspace, matching A4.12.1.
    The useful requested capacity and any padding remain separate in the record.
    """
    if technology_node_um <= 0:
        raise ValueError("technology_node_um must be positive")
    line_size_bytes = max(8, 1 << max(0, math.ceil(math.log2(spec.width_bits // 8))))
    requested = spec.requested_bytes_per_instance
    modeled = max(1024, math.ceil(requested / line_size_bytes) * line_size_bytes)
    replacements = (
        (r"(?m)^-size \(bytes\) .*$", f"-size (bytes) {modeled}"),
        (r"(?m)^-block size \(bytes\) .*$", f"-block size (bytes) {line_size_bytes}"),
        (r"(?m)^-associativity .*$", "-associativity 1"),
        (r"(?m)^-read-write port .*$", f"-read-write port {spec.readwrite_ports}"),
        (r"(?m)^-exclusive read port .*$", f"-exclusive read port {spec.read_ports}"),
        (r"(?m)^-exclusive write port .*$", f"-exclusive write port {spec.write_ports}"),
        (r"(?m)^-single ended read ports .*$", "-single ended read ports 0"),
        (r"(?m)^-UCA bank count .*$", "-UCA bank count 1"),
        (r"(?m)^-technology \(u\) .*$", f"-technology (u) {technology_node_um:.3f}"),
        (r"(?m)^-output/input bus width .*$", f"-output/input bus width {spec.width_bits}"),
        (r'(?m)^-cache type "cache"$', '-cache type "ram"'),
    )
    for pattern, replacement in replacements:
        template = _replace_one(template, pattern, replacement)
    return template, {
        "requested_bytes_per_instance": requested,
        "modeled_bytes_per_instance": modeled,
        "minimum_array_padding_bytes_per_instance": modeled - requested,
        "line_size_bytes": line_size_bytes,
    }


def parse_cacti_stdout(text: str) -> dict[str, float]:
    patterns = {
        "access_time_ns": r"Access time \(ns\):\s*([0-9.eE+-]+)",
        "cycle_time_ns": r"Cycle time \(ns\):\s*([0-9.eE+-]+)",
        "dynamic_read_energy_nj": r"Total dynamic read energy per access \(nJ\):\s*([0-9.eE+-]+)",
        "dynamic_write_energy_nj": r"Total dynamic write energy per access \(nJ\):\s*([0-9.eE+-]+)",
        "data_array_area_mm2": r"Data array: Area \(mm2\):\s*([0-9.eE+-]+)",
    }
    parsed: dict[str, float] = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text)
        if match is None:
            raise ToolchainError(f"CACTI stdout lacks {name}")
        parsed[name] = float(match.group(1))
    parsed["dynamic_read_energy_pj"] = parsed["dynamic_read_energy_nj"] * 1000.0
    parsed["dynamic_write_energy_pj"] = parsed["dynamic_write_energy_nj"] * 1000.0
    return parsed


class CactiMacroRunner:
    """Validate the pinned toolchain and run an explicitly described macro."""

    def __init__(self, toolchain_root: Path, technology_node_um: float = 0.032) -> None:
        self.toolchain_root = toolchain_root.resolve()
        self.technology_node_um = technology_node_um

    @property
    def lock_path(self) -> Path:
        return self.toolchain_root / "source_lock.json"

    @property
    def manifest_path(self) -> Path:
        return self.toolchain_root / "toolchain_manifest.json"

    def validate_toolchain(self) -> dict[str, Any]:
        if not self.lock_path.is_file():
            raise ToolchainError(f"missing tracked source lock: {self.lock_path}")
        if not self.manifest_path.is_file():
            raise ToolchainError("missing local CACTI manifest; run cacti_toolchain/build_cacti.sh")
        lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if lock.get("lock_schema_version") != LOCK_SCHEMA or manifest.get("manifest_schema_version") != MANIFEST_SCHEMA:
            raise ToolchainError("CACTI lock or manifest schema is incompatible")
        for key in ("source_url", "source_commit"):
            if manifest.get(key) != lock.get(key):
                raise ToolchainError(f"CACTI manifest {key} differs from tracked source lock")
        source_dir = self.toolchain_root / "src" / "cacti"
        binary = self.toolchain_root / "bin" / "cacti"
        template = source_dir / "cache.cfg"
        if not source_dir.is_dir() or not binary.is_file() or not binary.stat().st_mode & 0o111 or not template.is_file():
            raise ToolchainError("CACTI local source, executable, or template is missing; rebuild the toolchain")
        actual_commit = subprocess.run(["git", "-C", str(source_dir), "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
        actual_origin = subprocess.run(["git", "-C", str(source_dir), "config", "--get", "remote.origin.url"], check=True, text=True, capture_output=True).stdout.strip()
        if actual_commit != lock["source_commit"] or actual_origin != lock["source_url"]:
            raise ToolchainError("local CACTI source checkout differs from tracked source lock")
        actual_binary_sha = sha256_file(binary)
        actual_template_sha = sha256_file(template)
        if actual_binary_sha != manifest.get("binary_sha256") or actual_template_sha != manifest.get("template_sha256"):
            raise ToolchainError("local CACTI binary or template SHA differs from its build manifest")
        return {
            "source_url": lock["source_url"],
            "source_commit": lock["source_commit"],
            "build_command": lock["build_command"],
            "technology_proxy_default_um": lock["technology_proxy_default_um"],
            "binary_sha256": actual_binary_sha,
            "template_sha256": actual_template_sha,
            "source_dir": source_dir,
            "binary": binary,
            "template": template,
            "technology_boundary": lock["use_boundary"],
        }

    def run(self, spec: MacroSpec, output_dir: Path) -> dict[str, Any]:
        output_dir = output_dir.resolve()
        if output_dir.exists():
            raise FileExistsError(f"CACTI macro output directory must be new: {output_dir}")
        toolchain = self.validate_toolchain()
        output_dir.mkdir(parents=True)
        config, capacity = materialize_cacti_config(
            Path(toolchain["template"]).read_text(encoding="utf-8"), spec, self.technology_node_um
        )
        config_path = output_dir / "cache.cfg"
        config_path.write_text(config, encoding="utf-8")
        completed = subprocess.run(
            [str(Path(toolchain["binary"])), "-infile", str(config_path)],
            cwd=Path(toolchain["source_dir"]),
            check=False,
            text=True,
            capture_output=True,
        )
        stdout_path, stderr_path = output_dir / "cacti.stdout.log", output_dir / "cacti.stderr.log"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "no CACTI diagnostics").strip()
            raise ToolchainError(f"CACTI failed (exit={completed.returncode}): {detail}")
        metrics = parse_cacti_stdout(completed.stdout)
        record = {
            "schema_version": "route-a-cacti-macro-run-1.0",
            "classification": "single explicit public-CACTI SRAM proxy macro; not a PDK, physical macro, cycle/throughput, workload-energy, architecture, or RTL result",
            "macro_spec": asdict(spec),
            "capacity": capacity,
            "technology_proxy_node_um": self.technology_node_um,
            "toolchain": {key: value for key, value in toolchain.items() if key not in {"source_dir", "binary", "template"}},
            "raw_artifacts": {
                "config_filename": config_path.name,
                "config_sha256": sha256_file(config_path),
                "stdout_filename": stdout_path.name,
                "stdout_sha256": sha256_file(stdout_path),
                "stderr_filename": stderr_path.name,
                "stderr_sha256": sha256_file(stderr_path),
            },
            "per_instance_cacti_proxy": metrics,
            "aggregate_data_array_area_mm2": metrics["data_array_area_mm2"] * spec.instances,
            "energy_boundary": "Per-access CACTI values are macro characterization inputs only. Do not multiply them into workload energy before an explicit cycle/access model.",
        }
        record_path = output_dir / "macro_record.json"
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return record
