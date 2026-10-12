package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAS2PackedSidecarReadEndpoint
import kvpress.routea.incremental.RouteAFunctionalSidecarDeliveryAdapter
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL3.8.2 isolated protocol tests; no controller, macro, timing, or PPA model. */
final class RouteAFunctionalSidecarDeliverySpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 12,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def identity(bits: TransactionIdentity, rid: Int = 3): Unit = {
    bits.request_id.poke(rid.U); bits.incarnation.poke(1.U)
  }
  private def page(bits: PageRef, id: Int = 7): Unit = {
    bits.page_id.poke(id.U); bits.generation.poke(1.U)
  }
  private def descriptor(bits: DeliveryTargetDescriptor): Unit = {
    bits.write_endpoint.poke(0.U); bits.p3_layer.poke(0.U); bits.p3_stage_generation.poke(0.U)
    bits.transaction_group_tag.poke(0.U); bits.descriptor_kind.poke(0.U); page(bits.descriptor_page_ref)
    bits.descriptor_line.poke(0xaa.U); bits.s2_slot.poke(0.U); bits.source_generation.poke(1.U)
    bits.requires_sidecar.poke(true.B); bits.pending_ordinal.poke(0.U)
    bits.p3_member_payload_ref.poke(0.U); bits.direct_source_last.poke(false.B); bits.pending_explicit_empty.poke(false.B)
  }

  private def sidecarWork(d: RouteAFunctionalSidecarDeliveryAdapter, records: Int = 2): Unit = {
    val w = d.io.work_in.bits
    identity(w.transaction_identity); page(w.page_ref); w.s2_slot.poke(0.U); w.source_generation.poke(1.U)
    w.sidecar_handle_or_address.poke(0xaa.U); w.valid_records.poke(records.U)
    w.arrival_ordinal.poke(2.U); w.candidate_id.poke(1.U); w.eligibility_snapshot.poke("h1f".U)
    w.destination_endpoint.poke(0.U)
  }
  private def release(d: RouteAFunctionalSidecarDeliveryAdapter, status: Int, rid: Int = 3): Unit = {
    val r = d.io.payload_release_in.bits
    identity(r.transaction_identity, rid); page(r.page_ref); r.s2_slot.poke(0.U); r.source_generation.poke(1.U)
    r.delivery_context_ref.poke(1.U); r.status.poke(status.U)
  }
  private def sidecarAck(d: RouteAFunctionalSidecarDeliveryAdapter, rid: Int = 3): Unit = {
    val a = d.io.registry_allocation_ack_in.bits
    a.delivery_context_ref.poke(2.U); a.allocation.candidate_class.poke(p.r2S2PackedClassCode.U)
    identity(a.allocation.transaction_identity, rid); a.allocation.target_kind.poke(RouteADeliveryTargetKind.S2PackedSidecar.U)
    a.allocation.target_identity_generation.poke(1.U); a.allocation.expected_fragment_count.poke(2.U)
    descriptor(a.allocation.target_descriptor)
  }

  it("issues exactly one typed sidecar read only after the matching successful payload terminal") {
    simulate(new RouteAFunctionalSidecarDeliveryAdapter(p)) { d =>
      d.io.work_in.valid.poke(false.B); d.io.payload_release_in.valid.poke(false.B)
      d.io.registry_allocate_out.ready.poke(false.B); d.io.registry_allocation_ack_in.valid.poke(false.B)
      d.io.read_issue_out.ready.poke(false.B); sidecarWork(d); release(d, p.coreMemoryOkStatusCode); sidecarAck(d)
      d.clock.step()

      d.io.work_in.valid.poke(true.B); d.io.work_in.ready.expect(true.B); d.clock.step(); d.io.work_in.valid.poke(false.B)
      // Work alone cannot make a sidecar memory request or allocation.
      d.io.registry_allocate_out.valid.expect(false.B)
      d.io.payload_release_in.valid.poke(true.B); d.io.payload_release_in.ready.expect(true.B); d.clock.step()
      d.io.payload_release_in.valid.poke(false.B)
      d.io.registry_allocate_out.valid.expect(true.B)
      d.io.registry_allocate_out.bits.target_kind.expect(RouteADeliveryTargetKind.S2PackedSidecar.U)
      d.io.registry_allocate_out.bits.expected_fragment_count.expect(2.U)
      d.io.registry_allocate_out.bits.target_descriptor.descriptor_line.expect(0xaa.U)
      d.io.registry_allocate_out.ready.poke(true.B); d.clock.step(); d.io.registry_allocate_out.ready.poke(false.B)

      sidecarAck(d); d.io.registry_allocation_ack_in.valid.poke(true.B)
      d.io.read_issue_out.ready.poke(true.B); d.io.read_issue_out.valid.expect(true.B)
      d.io.read_issue_out.bits.delivery_context_ref.expect(2.U)
      d.io.read_issue_out.bits.payload_handle_or_address.expect(0xaa.U)
      d.io.read_issue_out.bits.expected_fragment_count.expect(2.U)
      d.io.read_issue_out.bits.target_descriptor.requires_sidecar.expect(true.B)
      d.clock.step(); d.io.registry_allocation_ack_in.valid.poke(false.B)
      d.io.read_issue_out.valid.expect(false.B)
    }
  }

  it("fails closed on a payload fault or mismatched payload release") {
    simulate(new RouteAFunctionalSidecarDeliveryAdapter(p)) { d =>
      d.io.work_in.valid.poke(false.B); d.io.payload_release_in.valid.poke(false.B)
      d.io.registry_allocate_out.ready.poke(true.B); d.io.registry_allocation_ack_in.valid.poke(false.B)
      d.io.read_issue_out.ready.poke(true.B); sidecarWork(d); release(d, p.coreMemoryFaultStatusCode); sidecarAck(d)
      d.clock.step()
      d.io.work_in.valid.poke(true.B); d.clock.step(); d.io.work_in.valid.poke(false.B)
      d.io.payload_release_in.valid.poke(true.B); d.io.payload_release_in.ready.expect(true.B); d.clock.step()
      d.io.payload_release_in.valid.poke(false.B); d.io.registry_allocate_out.valid.expect(false.B)

      sidecarWork(d); d.io.work_in.valid.poke(true.B); d.io.work_in.ready.expect(true.B); d.clock.step(); d.io.work_in.valid.poke(false.B)
      release(d, p.coreMemoryOkStatusCode, rid = 4); d.io.payload_release_in.valid.poke(true.B)
      d.io.payload_release_in.ready.expect(false.B); d.io.registry_allocate_out.valid.expect(false.B)
    }
  }

  private def resolvedSidecar(d: RouteAS2PackedSidecarReadEndpoint, fragment: Int, last: Boolean, status: Int): Unit = {
    val r = d.io.resolved_fragment_in.bits
    r.source_delivery.candidate_id.poke(1.U); r.source_delivery.candidate_class.poke(p.r2S2PackedClassCode.U)
    r.source_delivery.destination.poke(0.U); r.source_delivery.delivery_context_ref.poke(2.U)
    identity(r.source_delivery.r1_response.transaction_identity); r.source_delivery.r1_response.fragment_index.poke(fragment.U)
    r.source_delivery.r1_response.last.poke(last.B); r.source_delivery.r1_response.status.poke(status.U)
    r.source_delivery.r1_response.data.poke((0x900 + fragment).U)
    r.allocation.candidate_class.poke(p.r2S2PackedClassCode.U); identity(r.allocation.transaction_identity)
    r.allocation.target_kind.poke(RouteADeliveryTargetKind.S2PackedSidecar.U)
    r.allocation.target_identity_generation.poke(1.U); r.allocation.expected_fragment_count.poke(2.U)
    descriptor(r.allocation.target_descriptor)
  }
  private def endpointInputs(d: RouteAS2PackedSidecarReadEndpoint): Unit = {
    d.io.endpoint_filling_in.poke(true.B); identity(d.io.endpoint_identity_in); page(d.io.endpoint_page_ref_in)
    d.io.endpoint_generation_in.poke(1.U); d.io.sidecar_fragment_out.ready.poke(true.B)
    d.io.sidecar_complete_out.ready.poke(true.B); d.io.s2_fault_terminal_out.ready.poke(true.B)
  }

  it("serializes final sidecar fragment before complete and maps terminal fault fail-closed") {
    simulate(new RouteAS2PackedSidecarReadEndpoint(p)) { d =>
      endpointInputs(d); d.io.resolved_fragment_in.valid.poke(false.B); d.clock.step()
      resolvedSidecar(d, 0, last = false, p.coreMemoryOkStatusCode)
      d.io.resolved_fragment_in.valid.poke(true.B); d.io.resolved_fragment_in.ready.expect(true.B); d.clock.step()
      d.io.resolved_fragment_in.valid.poke(false.B); d.io.sidecar_fragment_out.valid.expect(true.B)
      d.io.sidecar_fragment_out.bits.record_ordinal.expect(0.U); d.io.sidecar_complete_out.valid.expect(false.B)
      d.clock.step()
      resolvedSidecar(d, 1, last = true, p.coreMemoryOkStatusCode)
      d.io.resolved_fragment_in.valid.poke(true.B); d.io.resolved_fragment_in.ready.expect(true.B); d.clock.step()
      d.io.resolved_fragment_in.valid.poke(false.B); d.io.sidecar_fragment_out.valid.expect(true.B)
      d.io.sidecar_fragment_out.bits.record_ordinal.expect(1.U); d.io.sidecar_complete_out.valid.expect(false.B)
      d.clock.step(); d.io.sidecar_complete_out.valid.expect(true.B)
      d.io.sidecar_complete_out.bits.s2_slot.expect(0.U); d.clock.step(); d.io.sidecar_complete_out.valid.expect(false.B)

      resolvedSidecar(d, 0, last = true, p.coreMemoryFaultStatusCode)
      d.io.resolved_fragment_in.valid.poke(true.B); d.io.resolved_fragment_in.ready.expect(true.B); d.clock.step()
      d.io.resolved_fragment_in.valid.poke(false.B); d.io.s2_fault_terminal_out.valid.expect(true.B)
      d.io.sidecar_fragment_out.valid.expect(false.B); d.io.sidecar_complete_out.valid.expect(false.B)
    }
  }
}
