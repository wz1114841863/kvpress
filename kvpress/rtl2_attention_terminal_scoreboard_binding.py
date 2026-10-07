"""RTL2.4.3 testbench-only attention-terminal event/oracle binding.

This module validates one named owner/carrier event and dispatches it to the
existing R6 lifecycle reference. It is not a waveform reader, RTL model,
numeric R4 implementation, cycle model, or performance/PPA estimator.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from kvpress.route_a_core_memory_reference import TransactionIdentity
from kvpress.route_a_lifecycle_adapter_reference import (
    INIT_ACKS,
    AttentionServiceRequest,
    LifecycleAdapterViolation,
    RouteALifecycleAdapterReference,
    SessionStart,
)


BINDING_SCHEMA_VERSION = "kvzap-route-a-rtl2-4-3-attention-terminal-binding-1.0"
BINDING_STATUS = "active_testbench_attention_terminal_bound"
EVENT_NAME = "attention_terminal"
REQUIRED_FIELDS = frozenset({"request_id", "incarnation", "terminal_status"})
SUCCESS_STATUS = 0
NUMERIC_FAULT_STATUS = 1


class AttentionTerminalScoreboardBindingError(ValueError):
    """Raised when the narrow RTL2.4.3 event binding is malformed or illegal."""


@dataclass(frozen=True)
class AttentionTerminalObservation:
    """One accepted testbench terminal event, not a cycle annotation."""

    event: str
    fields: Mapping[str, Any]


def load_binding(path: str | Path) -> dict[str, Any]:
    """Load the explicit RTL2.4.3 binding without synthesizing defaults."""
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AttentionTerminalScoreboardBindingError("binding root must be a JSON object")
    return loaded


def validate_binding(binding: Mapping[str, Any], schema: Mapping[str, Any], phase_overlay: Mapping[str, Any]) -> None:
    """Validate only the frozen event/oracle association for RTL2.4.3."""
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        raise AttentionTerminalScoreboardBindingError("unexpected RTL2.4.3 binding schema_version")
    if binding.get("status") != BINDING_STATUS:
        raise AttentionTerminalScoreboardBindingError("attention-terminal binding must be active testbench-bound")
    if binding.get("base_schema") != "analysis/rtl2_scoreboard_event_schema.json":
        raise AttentionTerminalScoreboardBindingError("binding must name the immutable RTL2 event schema")
    if binding.get("phase_overlay") != "analysis/rtl2_scoreboard_event_phase_reconciliation_01.json":
        raise AttentionTerminalScoreboardBindingError("binding must name the active phase overlay")

    records = schema.get("event_records")
    if not isinstance(records, list):
        raise AttentionTerminalScoreboardBindingError("RTL2 schema lacks event records")
    record = next((item for item in records if isinstance(item, dict) and item.get("event") == EVENT_NAME), None)
    if record is None:
        raise AttentionTerminalScoreboardBindingError("RTL2 schema lacks attention_terminal")
    if set(record.get("required_fields", ())) != REQUIRED_FIELDS:
        raise AttentionTerminalScoreboardBindingError("attention_terminal required fields drift")
    if set(record.get("emitter_owners", ())) != {"route_a_merge_boundary"}:
        raise AttentionTerminalScoreboardBindingError("attention_terminal owner drift")
    if set(record.get("carrier_ids", ())) != {"r4_to_r6_terminal"}:
        raise AttentionTerminalScoreboardBindingError("attention_terminal origin carrier drift")

    overrides = phase_overlay.get("overrides")
    if not isinstance(overrides, list):
        raise AttentionTerminalScoreboardBindingError("phase overlay lacks overrides")
    override = next((item for item in overrides if isinstance(item, dict) and item.get("event") == EVENT_NAME), None)
    if override is None or override.get("active_activation_phase") != "rtl2_4":
        raise AttentionTerminalScoreboardBindingError("attention_terminal is not active in RTL2.4")

    event = binding.get("event")
    if not isinstance(event, dict):
        raise AttentionTerminalScoreboardBindingError("binding event must be an object")
    if event.get("name") != EVENT_NAME:
        raise AttentionTerminalScoreboardBindingError("binding must name attention_terminal")
    if set(event.get("required_fields", ())) != REQUIRED_FIELDS:
        raise AttentionTerminalScoreboardBindingError("binding required fields drift")
    if event.get("origin_owner") != "route_a_merge_boundary" or event.get("origin_carrier") != "r4_to_r6_terminal":
        raise AttentionTerminalScoreboardBindingError("binding must preserve the R4 origin owner/carrier")
    if event.get("observation_owner") != "route_a_lifecycle_adapter" or event.get("observation_carrier") != "r6_outward_attention_terminal_rsp":
        raise AttentionTerminalScoreboardBindingError("binding must name the R6 outward observation carrier")
    status = event.get("terminal_status_encoding")
    if status != {"success": SUCCESS_STATUS, "numeric_fault": NUMERIC_FAULT_STATUS}:
        raise AttentionTerminalScoreboardBindingError("binding terminal status encoding drift")


def validate_source_hashes(binding: Mapping[str, Any], repo_root: Path) -> None:
    """Verify every explicitly hash-bound RTL2.4.3 source before use."""
    sources = binding.get("source_sha256")
    if not isinstance(sources, dict) or not sources:
        raise AttentionTerminalScoreboardBindingError("binding must contain nonempty source_sha256")
    root = Path(repo_root).resolve()
    for relative_path, expected_digest in sorted(sources.items()):
        if not isinstance(relative_path, str) or not isinstance(expected_digest, str):
            raise AttentionTerminalScoreboardBindingError("source_sha256 entries must be string path/digest pairs")
        path = (root / relative_path).resolve()
        if root not in path.parents or not path.is_file():
            raise AttentionTerminalScoreboardBindingError(f"hash-bound source is unavailable: {relative_path}")
        observed_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed_digest != expected_digest:
            raise AttentionTerminalScoreboardBindingError(f"hash-bound source drift: {relative_path}")


class RouteARTL2AttentionTerminalScoreboardAdapter:
    """Dispatch exact accepted terminal events to the existing R6 reference."""

    def __init__(self, repo_root: Path, binding_path: Path | None = None) -> None:
        root = Path(repo_root)
        binding = load_binding(binding_path or root / "analysis" / "rtl2_4_3_attention_terminal_scoreboard_binding.json")
        schema = json.loads((root / "analysis" / "rtl2_scoreboard_event_schema.json").read_text(encoding="utf-8"))
        overlay = json.loads((root / "analysis" / "rtl2_scoreboard_event_phase_reconciliation_01.json").read_text(encoding="utf-8"))
        validate_binding(binding, schema, overlay)
        validate_source_hashes(binding, root)
        self._lifecycle = RouteALifecycleAdapterReference()
        self._session_started = False

    @property
    def lifecycle(self) -> RouteALifecycleAdapterReference:
        """Expose the existing reference only for test assertions."""
        return self._lifecycle

    def arm_attention(self, identity: TransactionIdentity) -> None:
        """Mirror accepted pre-terminal R6 facts without emitting a schema event."""
        self._start_session_if_needed()
        try:
            self._lifecycle.attention_service_request(
                AttentionServiceRequest(identity=identity, layer=0, kv_head=0, query_position=1),
            )
            self._lifecycle.mark_gqa_updates_committed(identity)
        except LifecycleAdapterViolation as error:
            raise AttentionTerminalScoreboardBindingError(str(error)) from error

    def dispatch(self, observation: AttentionTerminalObservation) -> str:
        """Consume exactly one accepted R6-outward event using its R4 provenance."""
        if observation.event != EVENT_NAME:
            raise AttentionTerminalScoreboardBindingError("unknown RTL2.4.3 scoreboard event")
        if frozenset(observation.fields) != REQUIRED_FIELDS:
            raise AttentionTerminalScoreboardBindingError("attention_terminal fields differ from the frozen schema")
        try:
            identity = TransactionIdentity(
                request_id=int(observation.fields["request_id"]),
                incarnation=int(observation.fields["incarnation"]),
            )
            status = int(observation.fields["terminal_status"])
        except (KeyError, TypeError, ValueError) as error:
            raise AttentionTerminalScoreboardBindingError("attention_terminal fields are not integer identity/status values") from error
        if status not in {SUCCESS_STATUS, NUMERIC_FAULT_STATUS}:
            raise AttentionTerminalScoreboardBindingError("unknown terminal_status")
        # ``merge_numeric_fault`` checks merge eligibility before its terminal
        # helper checks lifecycle state.  Keep a pre-init/reset-era R6 event
        # fail-closed at this testbench boundary instead of taking that
        # implementation-detail error path.
        if not self._session_started:
            raise AttentionTerminalScoreboardBindingError("terminal attention requires active or retiring session")
        try:
            if status == SUCCESS_STATUS:
                return self._lifecycle.terminal_attention(identity, success=True)
            if status == NUMERIC_FAULT_STATUS:
                return self._lifecycle.merge_numeric_fault(identity)
        except LifecycleAdapterViolation as error:
            raise AttentionTerminalScoreboardBindingError(str(error)) from error
        raise AssertionError("validated terminal status must have a dispatch path")

    def destructive_reset(self) -> None:
        """Mirror destructive reset; later pre-reset terminal events are stale."""
        self._lifecycle.destructive_reset()
        self._session_started = False

    def _start_session_if_needed(self) -> None:
        if self._session_started:
            return
        try:
            for acknowledgement in sorted(INIT_ACKS):
                self._lifecycle.acknowledge_init(acknowledgement)
            self._lifecycle.session_start(SessionStart(session_id=0, context_tokens=32_768))
            # One causal hot record makes the fixed query-position-one setup
            # legal. It is setup state, not an emitted RTL2 event.
            from kvpress.route_a_lifecycle_adapter_reference import KVArrival

            self._lifecycle.kv_arrival(KVArrival(entry_id=0, layer=0, kv_head=0, logical_position=0, payload_ref=0))
        except LifecycleAdapterViolation as error:
            raise AttentionTerminalScoreboardBindingError(str(error)) from error
        self._session_started = True
