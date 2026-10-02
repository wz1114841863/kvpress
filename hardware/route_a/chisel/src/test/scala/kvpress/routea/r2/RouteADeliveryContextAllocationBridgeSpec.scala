package kvpress.routea.r2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.Valid
import kvpress.routea.common.RouteADeliveryContextAllocationBridge
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL2.2.2 bridge tests: allocation serialization only, never R2 arbitration. */
final class RouteADeliveryContextAllocationBridgeHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val r3_in = Flipped(RouteAChannels.source_candidate(p))
    val append_in = Flipped(RouteAChannels.source_candidate(p))
    val reclaim_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_out = RouteAChannels.source_candidate(p)
    val append_out = RouteAChannels.source_candidate(p)
    val reclaim_out = RouteAChannels.source_candidate(p)
    val allocate = RouteAChannels.delivery_context_allocate(p)
    val ack = Flipped(RouteAChannels.delivery_context_allocation_ack(p))
    val release_event = Input(Valid(new DeliveryContextRelease(p)))
  })
  val bridge = Module(new RouteADeliveryContextAllocationBridge(p))
  bridge.io.r3_in <> io.r3_in; bridge.io.r5_append_in <> io.append_in; bridge.io.r5_reclaim_in <> io.reclaim_in
  io.r3_out <> bridge.io.r3_out; io.append_out <> bridge.io.r5_append_out; io.reclaim_out <> bridge.io.r5_reclaim_out
  io.allocate <> bridge.io.registry_allocate_out; bridge.io.registry_allocation_ack_in <> io.ack
  bridge.io.release_event_in := io.release_event
}

final class RouteADeliveryContextAllocationBridgeSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 3, candidateIdWidth = 3, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def driveCandidate(c: SourceCandidate, cls: Int, ordinal: Int, id: Int, rid: Int, inc: Int, endpoint: Int): Unit = {
    c.candidate_class.poke(cls.U); c.arrival_ordinal.poke(ordinal.U); c.candidate_id.poke(id.U); c.eligibility_snapshot.poke(0.U)
    c.delivery_context_ref.poke(0.U); c.delivery_target_descriptor.write_endpoint.poke(endpoint.U)
    c.delivery_target_descriptor.p3_layer.poke(0.U); c.delivery_target_descriptor.p3_stage_generation.poke(0.U)
    c.delivery_target_descriptor.transaction_group_tag.poke(0.U); c.delivery_target_descriptor.descriptor_kind.poke(0.U)
    c.delivery_target_descriptor.descriptor_page_ref.page_id.poke(0.U); c.delivery_target_descriptor.descriptor_page_ref.generation.poke(0.U)
    c.delivery_target_descriptor.descriptor_line.poke(0.U); c.delivery_target_descriptor.s2_slot.poke(0.U)
    c.delivery_target_descriptor.source_generation.poke(0.U); c.delivery_target_descriptor.requires_sidecar.poke(false.B)
    c.delivery_target_descriptor.pending_ordinal.poke(0.U); c.delivery_target_descriptor.pending_explicit_empty.poke(false.B)
    c.r1_request.transaction_identity.request_id.poke(rid.U); c.r1_request.transaction_identity.incarnation.poke(inc.U)
    c.r1_request.request_kind.poke(p.coreMemoryWriteRequestCode.U); c.r1_request.destination.poke(0.U); c.r1_request.address_ref.poke(0.U)
    c.r1_request.expected_fragment_count.poke(1.U); c.r1_request.fragment_index.poke(0.U); c.r1_request.last.poke(true.B); c.r1_request.data.poke(0.U)
  }
  private def init(d: RouteADeliveryContextAllocationBridgeHarness): Unit = {
    d.io.r3_in.valid.poke(false.B); d.io.append_in.valid.poke(false.B); d.io.reclaim_in.valid.poke(false.B)
    d.io.r3_out.ready.poke(false.B); d.io.append_out.ready.poke(false.B); d.io.reclaim_out.ready.poke(false.B)
    d.io.allocate.ready.poke(true.B); d.io.ack.valid.poke(false.B); d.io.release_event.valid.poke(false.B)
    driveCandidate(d.io.r3_in.bits, p.r2PackWriteClassCode, 0, 0, 0, 0, RouteAWriteDeliveryEndpoint.P3PackedWrite)
    driveCandidate(d.io.append_in.bits, p.r2DescriptorMaintenanceClassCode, 0, 0, 0, 0, RouteAWriteDeliveryEndpoint.R5Append)
    driveCandidate(d.io.reclaim_in.bits, p.r2DescriptorMaintenanceClassCode, 0, 0, 0, 0, RouteAWriteDeliveryEndpoint.R5Reclaim)
    d.io.ack.bits.delivery_context_ref.poke(0.U); driveAppendAllocation(d.io.ack.bits.allocation)
    d.io.release_event.bits.delivery_context_ref.poke(0.U); driveAppendAllocation(d.io.release_event.bits.allocation)
  }
  private def driveAppendAllocation(a: DeliveryContextAllocation): Unit = {
    a.candidate_class.poke(p.r2DescriptorMaintenanceClassCode.U)
    a.transaction_identity.request_id.poke(2.U); a.transaction_identity.incarnation.poke(0.U)
    a.target_kind.poke(RouteADeliveryTargetKind.DescriptorMaintenanceTerminal.U); a.target_identity_generation.poke(0.U)
    a.target_descriptor.write_endpoint.poke(RouteAWriteDeliveryEndpoint.R5Append.U)
    a.target_descriptor.p3_layer.poke(0.U); a.target_descriptor.p3_stage_generation.poke(0.U)
    a.target_descriptor.transaction_group_tag.poke(0.U); a.target_descriptor.descriptor_kind.poke(0.U)
    a.target_descriptor.descriptor_page_ref.page_id.poke(0.U); a.target_descriptor.descriptor_page_ref.generation.poke(0.U)
    a.target_descriptor.descriptor_line.poke(0.U); a.target_descriptor.s2_slot.poke(0.U); a.target_descriptor.source_generation.poke(0.U)
    a.target_descriptor.requires_sidecar.poke(false.B); a.target_descriptor.pending_ordinal.poke(0.U); a.target_descriptor.pending_explicit_empty.poke(false.B)
  }
  private def acknowledge(d: RouteADeliveryContextAllocationBridgeHarness, ref: Int): Unit = {
    d.io.ack.bits.delivery_context_ref.poke(ref.U)
    driveAppendAllocation(d.io.ack.bits.allocation)
    d.io.ack.valid.poke(true.B); d.io.ack.ready.expect(true.B); d.clock.step(); d.io.ack.valid.poke(false.B)
  }
  private def driveAppendRelease(d: RouteADeliveryContextAllocationBridgeHarness, ref: Int): Unit = {
    d.io.release_event.bits.delivery_context_ref.poke(ref.U)
    driveAppendAllocation(d.io.release_event.bits.allocation)
  }

  it("allocates the oldest offered producer before R2 exposure and holds its bound ref until release") {
    simulate(new RouteADeliveryContextAllocationBridgeHarness(p)) { d =>
      init(d)
      driveCandidate(d.io.r3_in.bits, p.r2PackWriteClassCode, 5, 5, 1, 0, RouteAWriteDeliveryEndpoint.P3PackedWrite)
      driveCandidate(d.io.append_in.bits, p.r2DescriptorMaintenanceClassCode, 2, 2, 2, 0, RouteAWriteDeliveryEndpoint.R5Append)
      d.io.r3_in.valid.poke(true.B); d.io.append_in.valid.poke(true.B)
      d.io.allocate.valid.expect(true.B); d.io.allocate.bits.transaction_identity.request_id.expect(2.U)
      d.io.append_out.valid.expect(false.B); d.clock.step(); acknowledge(d, 3)
      d.io.append_out.valid.expect(true.B); d.io.append_out.bits.delivery_context_ref.expect(3.U)
      d.io.append_out.ready.poke(false.B); d.clock.step(); d.io.append_out.valid.expect(true.B); d.io.append_out.bits.candidate_id.expect(2.U)
      d.io.append_out.ready.poke(true.B); d.clock.step(); d.io.append_out.ready.poke(false.B)
      // The next R3 allocation may proceed, while the append producer lane is
      // still unavailable until its exact terminal release event.
      d.io.append_in.ready.expect(false.B)
      driveAppendRelease(d, 3)
      d.io.release_event.valid.poke(true.B); d.clock.step(); d.io.release_event.valid.poke(false.B)
      d.io.append_in.ready.expect(false.B)
    }
  }
}
