package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.Valid
import kvpress.routea.common.RouteAUnifiedDeliveryContextAllocationBridge
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL3.8.1 check that the prebuilt association allocation reuses the existing
  * packed lane.  It is not a second registry owner or an R2 arbiter test.
  */
final class RouteAPackedAssociationAllocationBridgeHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val packed_association_in = Flipped(RouteAChannels.delivery_context_allocate(p))
    val packed_arrival_ordinal_in = Input(UInt(p.candidateOrdinalWidth.W))
    val packed_candidate_id_in = Input(UInt(p.candidateIdWidth.W))
    val packed_ack_out = RouteAChannels.delivery_context_allocation_ack(p)
    val registry_allocate_out = RouteAChannels.delivery_context_allocate(p)
    val registry_ack_in = Flipped(RouteAChannels.delivery_context_allocation_ack(p))
  })

  val bridge = Module(new RouteAUnifiedDeliveryContextAllocationBridge(p))
  StructuralTieOff.source(bridge.io.r3_pack_read_in)
  StructuralTieOff.source(bridge.io.r3_direct_pending_in)
  StructuralTieOff.source(bridge.io.r5_s2_packed_in)
  StructuralTieOff.source(bridge.io.r3_packed_write_in)
  StructuralTieOff.source(bridge.io.r5_append_in)
  StructuralTieOff.source(bridge.io.r5_reclaim_in)
  StructuralTieOff.sink(bridge.io.r3_pack_read_out)
  StructuralTieOff.sink(bridge.io.r3_direct_pending_out)
  StructuralTieOff.sink(bridge.io.r5_s2_packed_out)
  StructuralTieOff.sink(bridge.io.r3_packed_write_out)
  StructuralTieOff.sink(bridge.io.r5_append_out)
  StructuralTieOff.sink(bridge.io.r5_reclaim_out)
  bridge.io.packed_association_allocate_in <> io.packed_association_in
  bridge.io.packed_association_arrival_ordinal_in := io.packed_arrival_ordinal_in
  bridge.io.packed_association_candidate_id_in := io.packed_candidate_id_in
  io.packed_ack_out <> bridge.io.packed_association_allocation_ack_out
  io.registry_allocate_out <> bridge.io.registry_allocate_out
  bridge.io.registry_allocation_ack_in <> io.registry_ack_in
  bridge.io.release_event_in.valid := false.B
  bridge.io.release_event_in.bits := 0.U.asTypeOf(new DeliveryContextRelease(p))
}

final class RouteAPackedAssociationAllocationBridgeSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4,
    candidatePredicateWidth = 10, r2S2FullClassCode = 0, r2S2PackedClassCode = 1,
    r2DirectPendingClassCode = 2, r2PackReadClassCode = 3, r2PackWriteClassCode = 4,
    r2DescriptorMaintenanceClassCode = 5, r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8, coreMemoryFragmentCountWidth = 10,
    coreMemoryFragmentIndexWidth = 10, coreMemoryReadRequestCode = 0,
    coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 3,
    p3StageGenerationWidth = 2, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 3, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def allocation(a: DeliveryContextAllocation): Unit = {
    a.candidate_class.poke(p.r2S2PackedClassCode.U)
    a.transaction_identity.request_id.poke(6.U)
    a.transaction_identity.incarnation.poke(1.U)
    a.target_kind.poke(RouteADeliveryTargetKind.S2PackedFill.U)
    a.target_identity_generation.poke(3.U)
    a.expected_fragment_count.poke(16.U)
    a.target_descriptor.write_endpoint.poke(0.U)
    a.target_descriptor.p3_layer.poke(0.U)
    a.target_descriptor.p3_stage_generation.poke(0.U)
    a.target_descriptor.transaction_group_tag.poke(2.U)
    a.target_descriptor.descriptor_kind.poke(0.U)
    a.target_descriptor.descriptor_page_ref.page_id.poke(9.U)
    a.target_descriptor.descriptor_page_ref.generation.poke(1.U)
    a.target_descriptor.descriptor_line.poke(0x55.U)
    a.target_descriptor.s2_slot.poke(1.U)
    a.target_descriptor.source_generation.poke(3.U)
    a.target_descriptor.requires_sidecar.poke(true.B)
    a.target_descriptor.pending_ordinal.poke(0.U)
    a.target_descriptor.p3_member_payload_ref.poke(0.U)
    a.target_descriptor.direct_source_last.poke(false.B)
    a.target_descriptor.pending_explicit_empty.poke(false.B)
  }

  it("allocates and acknowledges the owner-built record through the existing packed lane") {
    simulate(new RouteAPackedAssociationAllocationBridgeHarness(p)) { d =>
      d.io.packed_association_in.valid.poke(false.B)
      d.io.packed_arrival_ordinal_in.poke(3.U)
      d.io.packed_candidate_id_in.poke(2.U)
      d.io.registry_allocate_out.ready.poke(false.B)
      d.io.registry_ack_in.valid.poke(false.B)
      d.io.packed_ack_out.ready.poke(false.B)
      allocation(d.io.packed_association_in.bits)
      allocation(d.io.registry_ack_in.bits.allocation)
      d.io.registry_ack_in.bits.delivery_context_ref.poke(1.U)
      d.clock.step()

      d.io.packed_association_in.valid.poke(true.B)
      d.io.registry_allocate_out.valid.expect(true.B)
      d.io.registry_allocate_out.bits.transaction_identity.request_id.expect(6.U)
      d.io.registry_allocate_out.bits.target_descriptor.descriptor_page_ref.page_id.expect(9.U)
      d.io.packed_association_in.ready.expect(false.B)
      d.io.registry_allocate_out.ready.poke(true.B)
      d.clock.step()
      d.io.registry_allocate_out.ready.poke(false.B)
      d.io.packed_association_in.valid.poke(false.B)

      d.io.registry_ack_in.valid.poke(true.B)
      d.io.packed_ack_out.valid.expect(true.B)
      d.io.packed_ack_out.bits.delivery_context_ref.expect(1.U)
      d.io.packed_ack_out.ready.poke(true.B)
      d.clock.step()
      d.io.registry_ack_in.valid.poke(false.B)
      d.io.packed_ack_out.ready.poke(false.B)
      d.io.packed_ack_out.valid.expect(false.B)
    }
  }
}
