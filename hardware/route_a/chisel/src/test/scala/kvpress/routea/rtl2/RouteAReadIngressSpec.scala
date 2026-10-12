package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.Valid
import kvpress.routea.common.{RouteADeliveryContextRegistry, RouteAR2ReadIngressMerge, RouteAUnifiedDeliveryContextAllocationBridge}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL2.3.2 isolated allocation/merge harness; no core arbiter or R1 launch. */
final class RouteAReadIngressHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val r3_pack = Flipped(RouteAChannels.source_candidate(p))
    val r3_direct = Flipped(RouteAChannels.source_candidate(p))
    val r5_packed = Flipped(RouteAChannels.source_candidate(p))
    val r3_write = Flipped(RouteAChannels.source_candidate(p))
    val candidate = RouteAChannels.source_candidate(p)
    val write_candidate = RouteAChannels.source_candidate(p)
    val release_event = Input(Valid(new DeliveryContextRelease(p)))
  })
  val bridge = Module(new RouteAUnifiedDeliveryContextAllocationBridge(p))
  StructuralTieOff.source(bridge.io.packed_association_allocate_in)
  bridge.io.packed_association_arrival_ordinal_in := 0.U
  bridge.io.packed_association_candidate_id_in := 0.U
  StructuralTieOff.sink(bridge.io.packed_association_allocation_ack_out)
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val merge = Module(new RouteAR2ReadIngressMerge(p))
  bridge.io.r3_pack_read_in <> io.r3_pack
  bridge.io.r3_direct_pending_in <> io.r3_direct
  bridge.io.r5_s2_packed_in <> io.r5_packed
  bridge.io.r3_packed_write_in <> io.r3_write
  StructuralTieOff.source(bridge.io.r5_append_in)
  StructuralTieOff.source(bridge.io.r5_reclaim_in)
  merge.io.r3_pack_read_in <> bridge.io.r3_pack_read_out
  merge.io.r3_direct_pending_in <> bridge.io.r3_direct_pending_out
  merge.io.r5_s2_packed_in <> bridge.io.r5_s2_packed_out
  io.candidate <> merge.io.candidate_out
  io.write_candidate <> bridge.io.r3_packed_write_out
  StructuralTieOff.sink(bridge.io.r5_append_out)
  StructuralTieOff.sink(bridge.io.r5_reclaim_out)
  registry.io.mem_init_done := io.mem_init_done
  registry.io.allocation_in <> bridge.io.registry_allocate_out
  bridge.io.registry_allocation_ack_in <> registry.io.allocation_ack_out
  bridge.io.release_event_in := io.release_event
  registry.io.release_in.valid := io.release_event.valid
  registry.io.release_in.bits := io.release_event.bits
  registry.io.resolve_in.valid := false.B
  registry.io.resolve_in.bits := 0.U.asTypeOf(new SourceDelivery(p))
  registry.io.resolved_out.ready := true.B
}

final class RouteAReadIngressSpec extends AnyFunSpec with ChiselSim {
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

  private def driveCandidate(c: SourceCandidate, cls: Int, ordinal: Int, id: Int, rid: Int, sourceGen: Int = 1): Unit = {
    c.candidate_class.poke(cls.U); c.arrival_ordinal.poke(ordinal.U); c.candidate_id.poke(id.U)
    c.eligibility_snapshot.poke("h3F".U); c.delivery_context_ref.poke(0.U)
    c.delivery_target_descriptor.write_endpoint.poke(0.U); c.delivery_target_descriptor.p3_layer.poke(2.U)
    c.delivery_target_descriptor.p3_stage_generation.poke(1.U); c.delivery_target_descriptor.transaction_group_tag.poke(1.U)
    c.delivery_target_descriptor.descriptor_kind.poke(0.U); c.delivery_target_descriptor.descriptor_page_ref.page_id.poke(9.U)
    c.delivery_target_descriptor.descriptor_page_ref.generation.poke(2.U); c.delivery_target_descriptor.descriptor_line.poke(7.U)
    c.delivery_target_descriptor.s2_slot.poke(1.U); c.delivery_target_descriptor.source_generation.poke(sourceGen.U)
    c.delivery_target_descriptor.requires_sidecar.poke(true.B); c.delivery_target_descriptor.pending_ordinal.poke(4.U)
    c.delivery_target_descriptor.pending_explicit_empty.poke(false.B)
    c.r1_request.transaction_identity.request_id.poke(rid.U); c.r1_request.transaction_identity.incarnation.poke(0.U)
    c.r1_request.request_kind.poke(p.coreMemoryReadRequestCode.U); c.r1_request.destination.poke(1.U)
    c.r1_request.address_ref.poke((0x40 + rid).U); c.r1_request.expected_fragment_count.poke(3.U)
    c.r1_request.fragment_index.poke(0.U); c.r1_request.last.poke(false.B); c.r1_request.data.poke(0.U)
  }

  private def driveRelease(r: DeliveryContextRelease, ref: Int, cls: Int, rid: Int, sourceGen: Int = 1): Unit = {
    r.delivery_context_ref.poke(ref.U); r.allocation.candidate_class.poke(cls.U)
    r.allocation.transaction_identity.request_id.poke(rid.U); r.allocation.transaction_identity.incarnation.poke(0.U)
    val target = if (cls == p.r2PackReadClassCode) RouteADeliveryTargetKind.P3PendingRead
      else if (cls == p.r2DirectPendingClassCode) RouteADeliveryTargetKind.DirectPendingRead
      else RouteADeliveryTargetKind.S2PackedFill
    r.allocation.target_kind.poke(target.U); r.allocation.target_identity_generation.poke(sourceGen.U)
    r.allocation.expected_fragment_count.poke(3.U)
    r.allocation.target_descriptor.write_endpoint.poke(0.U); r.allocation.target_descriptor.p3_layer.poke(2.U)
    r.allocation.target_descriptor.p3_stage_generation.poke(1.U); r.allocation.target_descriptor.transaction_group_tag.poke(1.U)
    r.allocation.target_descriptor.descriptor_kind.poke(0.U); r.allocation.target_descriptor.descriptor_page_ref.page_id.poke(9.U)
    r.allocation.target_descriptor.descriptor_page_ref.generation.poke(2.U); r.allocation.target_descriptor.descriptor_line.poke(7.U)
    r.allocation.target_descriptor.s2_slot.poke(1.U); r.allocation.target_descriptor.source_generation.poke(sourceGen.U)
    r.allocation.target_descriptor.requires_sidecar.poke(true.B); r.allocation.target_descriptor.pending_ordinal.poke(4.U)
    r.allocation.target_descriptor.pending_explicit_empty.poke(false.B)
  }

  private def init(d: RouteAReadIngressHarness): Unit = {
    d.io.mem_init_done.poke(false.B); d.io.r3_pack.valid.poke(false.B); d.io.r3_direct.valid.poke(false.B); d.io.r5_packed.valid.poke(false.B); d.io.r3_write.valid.poke(false.B)
    d.io.candidate.ready.poke(false.B); d.io.write_candidate.ready.poke(false.B); d.io.release_event.valid.poke(false.B)
    driveCandidate(d.io.r3_pack.bits, p.r2PackReadClassCode, 2, 2, 1)
    driveCandidate(d.io.r3_direct.bits, p.r2DirectPendingClassCode, 0, 0, 2)
    driveCandidate(d.io.r5_packed.bits, p.r2S2PackedClassCode, 1, 1, 3)
    driveCandidate(d.io.r3_write.bits, p.r2PackWriteClassCode, 4, 4, 4)
    d.io.r3_write.bits.r1_request.request_kind.poke(p.coreMemoryWriteRequestCode.U)
    driveRelease(d.io.release_event.bits, 0, p.r2DirectPendingClassCode, 2)
  }

  it("allocates named read lanes before pre-R2 ordinal/id merge and preserves the bound reference under backpressure") {
    simulate(new RouteAReadIngressHarness(p)) { dut =>
      init(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step()
      dut.io.r3_pack.valid.poke(true.B); dut.io.r3_direct.valid.poke(true.B); dut.io.r5_packed.valid.poke(true.B)
      dut.clock.step(3)
      dut.io.candidate.valid.expect(true.B)
      dut.io.candidate.bits.candidate_class.expect(p.r2DirectPendingClassCode.U)
      dut.io.candidate.bits.candidate_id.expect(0.U)
      val directRef = dut.io.candidate.bits.delivery_context_ref.peek().litValue.toInt
      dut.clock.step(); dut.io.candidate.valid.expect(true.B); dut.io.candidate.bits.delivery_context_ref.expect(directRef.U)
      dut.io.candidate.ready.poke(true.B); dut.clock.step(); dut.io.candidate.ready.poke(false.B)
      dut.io.r3_direct.valid.poke(false.B)
      driveRelease(dut.io.release_event.bits, directRef, p.r2DirectPendingClassCode, 2)
      dut.io.release_event.valid.poke(true.B); dut.clock.step(); dut.io.release_event.valid.poke(false.B)
      dut.clock.step(3)
      dut.io.candidate.valid.expect(true.B)
      dut.io.candidate.bits.candidate_class.expect(p.r2S2PackedClassCode.U)
      dut.io.candidate.bits.candidate_id.expect(1.U)
    }
  }

  it("fails closed before registry allocation when a named read lane supplies a write-class candidate") {
    simulate(new RouteAReadIngressHarness(p)) { dut =>
      init(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step()
      driveCandidate(dut.io.r3_pack.bits, p.r2PackWriteClassCode, 0, 0, 1)
      dut.io.r3_pack.valid.poke(true.B); dut.clock.step(2)
      dut.io.candidate.valid.expect(false.B); dut.io.r3_pack.ready.expect(false.B)
    }
  }

  it("serializes a lower-ordinal write and read offer through one shared registry-allocation owner") {
    simulate(new RouteAReadIngressHarness(p)) { dut =>
      init(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step()
      driveCandidate(dut.io.r3_direct.bits, p.r2DirectPendingClassCode, 3, 3, 2)
      driveCandidate(dut.io.r3_write.bits, p.r2PackWriteClassCode, 0, 0, 4)
      dut.io.r3_direct.valid.poke(true.B); dut.io.r3_write.valid.poke(true.B)
      dut.clock.step(3)
      dut.io.write_candidate.valid.expect(true.B)
      dut.io.write_candidate.bits.candidate_class.expect(p.r2PackWriteClassCode.U)
      dut.io.write_candidate.bits.candidate_id.expect(0.U)
      dut.io.candidate.valid.expect(false.B)
    }
  }
}
