"""Pure-software R1--R6 cross-closure bindings for Gate-A Reviewer 02.

This module has only event-level ownership/transport meaning.  It adds no
HBM controller, burst policy, scheduler, cycle, timing, PPA, RTL, or workload
claim.  In particular, ``line_data`` is opaque to this bridge: descriptor
format/update semantics stay owned by R5, while R1 owns its 64-B transport
terminal semantics and R2 owns descriptor-maintenance eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from kvpress.route_a_arbitration_reference import (
    DescriptorMaintenanceCandidate,
    RouteAArbitrationReference,
)
from kvpress.route_a_core_memory_reference import (
    CORE_MEM_FRAGMENT_BYTES,
    CoreMemoryWrapperReference,
    CoreWriteData,
    MemoryStatus,
    TransactionIdentity,
)
from kvpress.route_a_page_manager_reference import DescriptorOperation, RouteAPageManagerReference
from kvpress.route_a_m2_p3_reference import RouteAM2P3Reference
from kvpress.route_a_rtl_profile import PageRef


class CrossClosureViolation(AssertionError):
    """A cross-module Gate-A event has no single permitted meaning."""


@dataclass(frozen=True)
class DescriptorMaintenanceBinding:
    """One R5 descriptor operation bound to exactly one R1 write identity."""

    operation: DescriptorOperation
    identity: TransactionIdentity
    line_data: bytes
    arrival_ordinal: int


class DescriptorMaintenanceTransportReference:
    """Bind R5 descriptor lines to the R2 -> R1 unique HBM-facing path."""

    def __init__(
        self,
        *,
        arbitration: RouteAArbitrationReference,
        memory: CoreMemoryWrapperReference,
        page_manager: RouteAPageManagerReference,
    ) -> None:
        self._arbitration = arbitration
        self._memory = memory
        self._page_manager = page_manager
        self._bindings: dict[str, DescriptorMaintenanceBinding] = {}

    def bind(self, binding: DescriptorMaintenanceBinding) -> None:
        """Register an unissued R5 operation with the shared R2/R1 path."""
        self._require(binding.operation.operation_id not in self._bindings, "descriptor operation is already bound")
        self._require(len(binding.line_data) == CORE_MEM_FRAGMENT_BYTES, "descriptor maintenance is exactly one R1 64-B fragment")
        self._require(binding.arrival_ordinal >= 0, "descriptor maintenance ordinal is invalid")
        operation = binding.operation
        address_ref = f"descriptor-line:{operation.location.core_fragment_index}"
        self._arbitration.register_descriptor_maintenance(
            DescriptorMaintenanceCandidate(operation.operation_id, binding.identity, address_ref, binding.arrival_ordinal)
        )
        self._arbitration.mark_descriptor_maintenance_ready(
            operation.operation_id,
            fifo_ready=True,
            ownership_ready=True,
            credit_ready=True,
        )
        self._bindings[operation.operation_id] = binding

    def grant_next(self) -> str | None:
        """Attempt R2 eligibility grant; R1 ready-low causes no mutation."""
        return self._arbitration.grant_next_descriptor_maintenance(self._memory)

    def send_line_data(self, operation_id: str) -> None:
        binding = self._binding(operation_id)
        self._memory.accept_write_data(CoreWriteData(binding.identity, 0, True, binding.line_data))

    def terminal(self, operation_id: str, *, status: MemoryStatus, adapter_epoch: int) -> str:
        """Propagate the one R1 terminal result to R2 and then the owning R5 op.

        A successful descriptor line is durable only; it does not publish M2,
        expose a packed descriptor, or transfer pending authority.
        """
        binding = self._binding(operation_id)
        result = self._memory.receive_write_commit(binding.identity, status=status, adapter_epoch=adapter_epoch)
        self._require(result in {"payload_durable_only", "fault"}, "descriptor terminal was not live at R1")
        self._arbitration.record_descriptor_maintenance_terminal(
            operation_id,
            wrapper=self._memory,
            status=status,
        )
        self._page_manager.complete_descriptor_operation(operation_id, success=status is MemoryStatus.OK)
        return "descriptor_durable_only" if status is MemoryStatus.OK else "fault"

    def _binding(self, operation_id: str) -> DescriptorMaintenanceBinding:
        binding = self._bindings.get(operation_id)
        self._require(binding is not None, "descriptor operation has no transport binding")
        return binding

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise CrossClosureViolation(message)


def metadata_publish_commit(
    *,
    m2_p3: RouteAM2P3Reference,
    group_id: str,
    page_manager: RouteAPageManagerReference,
    page_ref: PageRef,
    lifecycle_publication: Callable[[], None],
) -> bool:
    """Execute the one shared publication linearization event.

    R3 is the outer commit owner. R5 descriptor/stream visibility and the
    lifecycle authority action occur inside its one accepted commit action;
    therefore neither a descriptor durable write nor an R3 private state can
    create a second path to packed visibility.
    """
    return m2_p3.metadata_publish_commit(
        group_id,
        publication_action=lambda: page_manager.metadata_publish_commit(
            page_ref, publication_action=lifecycle_publication
        ),
    )
