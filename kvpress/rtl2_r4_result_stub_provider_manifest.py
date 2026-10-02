"""No-model validation for the RTL2.0g R4 result-stub provider."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "kvzap-route-a-rtl2-0g-r4-result-stub-provider-1.0"
STATUS = "rtl2_0g_r4_result_stub_interface_owner_closed_testbench_behavior_pending"


class RTL2R4ResultStubProviderError(ValueError):
    """Raised when the R4 testbench-only result-stub boundary drifts."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL2R4ResultStubProviderError("manifest root must be object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != STATUS:
        raise RTL2R4ResultStubProviderError("unexpected RTL2.0g manifest identity")
    if "Verification-only R4 result/fault stub-provider contract" not in str(manifest.get("scope")):
        raise RTL2R4ResultStubProviderError("scope must retain verification-only boundary")
    for path in _strings(manifest, "contract_references"):
        if not Path(path).is_file():
            raise RTL2R4ResultStubProviderError(f"missing contract reference: {path}")

    provider = _object(manifest, "provider")
    if provider.get("name") != "testbench_route_a_r4_result_stub_provider" or provider.get("classification") != "testbench_only_verification_endpoint":
        raise RTL2R4ResultStubProviderError("R4 stub provider identity differs")
    if set(_strings(provider, "produces")) != {"R4ResultStub", "R4NumericFault"}:
        raise RTL2R4ResultStubProviderError("R4 stub provider result inventory differs")
    forbidden = set(_strings(provider, "forbidden"))
    required_forbidden = {
        "outcome inference from packet data or internal R4 state",
        "offer before accepted merge_req",
        "empty-source merge acceptance",
        "simultaneous success and numeric_fault",
        "duplicate outcome for one merge identity",
        "outward terminal bypass",
        "retry or Full-KV fallback",
        "numeric implementation claim",
    }
    if not required_forbidden.issubset(forbidden):
        raise RTL2R4ResultStubProviderError("R4 stub provider prohibitions incomplete")
    does_not_own = set(_strings(provider, "does_not_own"))
    if not {
        "R6 merge request production",
        "source packet or ConsumerPartialCommit processing",
        "source release",
        "R4 numeric arithmetic or binary32 validation",
        "R6 outward terminal consumption",
    }.issubset(does_not_own):
        raise RTL2R4ResultStubProviderError("R4 stub provider ownership boundary incomplete")

    scenario = _object(manifest, "scenario")
    if scenario.get("name") != "R4StubScenario" or scenario.get("dispositions") != ["success", "numeric_fault"]:
        raise RTL2R4ResultStubProviderError("scenario type or disposition differs")
    if not {"transaction_identity", "disposition", "normalized_value_4096b_when_success"}.issubset(_strings(scenario, "fields")):
        raise RTL2R4ResultStubProviderError("scenario fields incomplete")
    if "explicit testbench input, not inferred" not in str(scenario.get("selection_rule")):
        raise RTL2R4ResultStubProviderError("scenario selection must remain explicit")
    if "R4ResultStub" not in str(scenario.get("success_rule")) or "R4NumericFault" not in str(scenario.get("fault_rule")) or "no normalized result" not in str(scenario.get("fault_rule")):
        raise RTL2R4ResultStubProviderError("success/fault carrier mapping differs")

    binding = _object(manifest, "merge_binding")
    if binding.get("producer") != "route_a_lifecycle_adapter" or binding.get("consumer") != "route_a_merge_boundary":
        raise RTL2R4ResultStubProviderError("R6-to-R4 merge binding differs")
    if not {"transaction_identity", "source_presence"}.issubset(_strings(binding, "fields")):
        raise RTL2R4ResultStubProviderError("merge binding fields incomplete")
    if "exact nonempty merge_req" not in str(binding.get("acceptance_rule")) or "R6 alone consumes the outward attention terminal" not in str(binding.get("terminal_chain")):
        raise RTL2R4ResultStubProviderError("merge/terminal ownership boundary differs")

    lifetime = set(_strings(manifest, "mutual_exclusion_and_lifetime"))
    for required in (
        "success and numeric_fault valid signals are never asserted together",
        "provider holds its selected carrier unchanged until R4 accepts it",
        "destructive reset invalidates every live scenario",
    ):
        if not any(required in item for item in lifetime):
            raise RTL2R4ResultStubProviderError(f"result lifetime rule missing: {required}")

    assumptions = set(_strings(manifest, "environment_assumptions"))
    if not any("eventually offers the selected scenario" in item for item in assumptions):
        raise RTL2R4ResultStubProviderError("bounded-progress environment assumption missing")
    guarantees = set(_strings(manifest, "dut_guarantees_to_observe"))
    if not any("exactly one outward terminal" in item for item in guarantees):
        raise RTL2R4ResultStubProviderError("R6 terminal guarantee missing")

    rejection = _object(manifest, "rejection_and_stall")
    rejected = set(_strings(rejection, "reject_without_mutation"))
    if not {
        "scenario before merge_req acceptance",
        "unknown stale or reset identity",
        "duplicate scenario or outcome",
        "simultaneous success and numeric_fault",
        "fault carrying a normalized value",
    }.issubset(rejected):
        raise RTL2R4ResultStubProviderError("R4 stub rejection boundary incomplete")
    ready_low = str(rejection.get("ready_low_rule"))
    if "every held identity, disposition, and normalized value field remains unchanged" not in ready_low:
        raise RTL2R4ResultStubProviderError("ready-low nonmutation differs")

    excluded = set(_strings(manifest, "excluded_paths"))
    if not {
        "R4 numeric arithmetic binary32 validation or normalized-value calculation",
        "R6 outward terminal production",
        "retry Full-KV fallback or admission/mask change",
        "physical numeric storage pipeline or timing realization",
    }.issubset(excluded):
        raise RTL2R4ResultStubProviderError("R4 stub excluded paths incomplete")
    follow = _object(manifest, "required_follow_on")
    if follow.get("behavioral_phase") != "rtl2_5_verification_only" or "testbench/harness scope" not in str(follow.get("requires")):
        raise RTL2R4ResultStubProviderError("R4 stub follow-on scope differs")
    labels = set(_strings(manifest, "evidence_labels"))
    if not {"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"}.issubset(labels):
        raise RTL2R4ResultStubProviderError("evidence labels incomplete")


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL2R4ResultStubProviderError(f"{key} must be object")
    return value


def _strings(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL2R4ResultStubProviderError(f"{key} must be string list")
    return value
