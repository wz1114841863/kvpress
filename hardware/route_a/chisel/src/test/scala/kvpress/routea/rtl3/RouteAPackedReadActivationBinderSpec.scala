package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAPackedReadActivationBinder
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL3.8.1 exact owner-fact materialization; no memory, model, or PPA claim. */
final class RouteAPackedReadActivationBinderSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8, coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 10,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 2,
    transactionGroupTagWidth = 3, p3StageGenerationWidth = 2, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 3, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def identity(id: TransactionIdentity, rid: Int = 3, incarnation: Int = 1): Unit = {
    id.request_id.poke(rid.U); id.incarnation.poke(incarnation.U)
  }
  private def page(ref: PageRef, id: Int = 5, generation: Int = 2): Unit = {
    ref.page_id.poke(id.U); ref.generation.poke(generation.U)
  }
  private def source(instance: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = {
    instance.source_kind.poke(kind.U); instance.instance_coordinate.poke(coordinate.U); instance.generation.poke(generation.U)
  }

  private def init(dut: RouteAPackedReadActivationBinder): Unit = {
    dut.io.mem_init_done.poke(false.B)
    dut.io.accepted_plan_in.valid.poke(false.B)
    dut.io.publication_member_in.valid.poke(false.B)
    dut.io.post_r6_page_ready_in.valid.poke(false.B)
    dut.io.descriptor_grant_in.valid.poke(false.B)
    dut.io.s2_fill_lease_in.valid.poke(false.B)
    dut.io.demand_out.ready.poke(false.B)
    dut.io.publication_authorization_out.ready.poke(false.B)
    dut.io.descriptor_grant_out.ready.poke(false.B)
    dut.io.s2_fill_lease_out.ready.poke(false.B)
    dut.clock.step()
    dut.io.mem_init_done.poke(true.B)
  }

  private def drivePlan(dut: RouteAPackedReadActivationBinder, packedPresent: Boolean = true, slot: Int = 1, gen: Int = 3): Unit = {
    val bits = dut.io.accepted_plan_in.bits
    identity(bits.transaction_identity); bits.source_presence.poke((if (packedPresent) 4 else 1).U)
    source(bits.hot_instance, 0, 0, 0); source(bits.pending_instance, 1, 0, 0); source(bits.packed_instance, 2, slot, gen)
  }
  private def drivePublication(dut: RouteAPackedReadActivationBinder, pageId: Int = 5, generation: Int = 2, records: Int = 2): Unit = {
    val bits = dut.io.post_r6_page_ready_in.bits
    bits.p3_layer.poke(0.U); bits.p3_stage_generation.poke(1.U); page(bits.page_ref, pageId, generation)
    bits.transaction_group_tag.poke(6.U); bits.valid_records.poke(records.U)
  }
  private def driveMember(dut: RouteAPackedReadActivationBinder, ordinal: Int, records: Int = 2): Unit = {
    val bits = dut.io.publication_member_in.bits
    bits.entry_id.poke((0x20 + ordinal).U); bits.layer.poke(0.U); bits.kv_head.poke(0.U)
    bits.logical_position.poke((0x40 + ordinal).U); bits.payload_ref.poke((0x60 + ordinal).U)
    bits.transaction_group_tag.poke(6.U); bits.group_member_ordinal.poke(ordinal.U)
  }
  private def driveDescriptor(dut: RouteAPackedReadActivationBinder, pageId: Int = 5, generation: Int = 2, records: Int = 2, rid: Int = 3): Unit = {
    val bits = dut.io.descriptor_grant_in.bits
    identity(bits.transaction_identity, rid); page(bits.page_ref, pageId, generation)
    bits.payload_handle_or_address.poke(0x32.U); bits.sidecar_handle_or_address.poke(0x55.U)
    bits.valid_records.poke(records.U); bits.sidecar_records.poke(records.U); bits.live_reference_held.poke(true.B)
  }
  private def driveLease(dut: RouteAPackedReadActivationBinder, pageId: Int = 5, generation: Int = 2, slot: Int = 1, sourceGen: Int = 3, rid: Int = 3): Unit = {
    val bits = dut.io.s2_fill_lease_in.bits
    identity(bits.transaction_identity, rid); page(bits.page_ref, pageId, generation)
    bits.s2_slot.poke(slot.U); bits.source_generation.poke(sourceGen.U); bits.requires_sidecar.poke(true.B)
  }
  private def send(valid: Bool, ready: Bool, clock: Clock): Unit = {
    valid.poke(true.B); ready.expect(true.B); clock.step(); valid.poke(false.B)
  }

  private def loadExactFacts(dut: RouteAPackedReadActivationBinder): Unit = {
    drivePlan(dut); send(dut.io.accepted_plan_in.valid, dut.io.accepted_plan_in.ready, dut.clock)
    (0 until 2).foreach { ordinal =>
      driveMember(dut, ordinal); send(dut.io.publication_member_in.valid, dut.io.publication_member_in.ready, dut.clock)
    }
    drivePublication(dut); send(dut.io.post_r6_page_ready_in.valid, dut.io.post_r6_page_ready_in.ready, dut.clock)
    driveDescriptor(dut); send(dut.io.descriptor_grant_in.valid, dut.io.descriptor_grant_in.ready, dut.clock)
    driveLease(dut); send(dut.io.s2_fill_lease_in.valid, dut.io.s2_fill_lease_in.ready, dut.clock)
    dut.clock.step() // Collect -> Evaluate
  }

  it("materializes one exact packed association only after R6/R3/R5/S2 facts join") {
    simulate(new RouteAPackedReadActivationBinder(p)) { dut =>
      init(dut); loadExactFacts(dut); dut.clock.step() // Evaluate -> Emit
      dut.io.demand_out.valid.expect(true.B); dut.io.publication_authorization_out.valid.expect(true.B)
      dut.io.descriptor_grant_out.valid.expect(true.B); dut.io.s2_fill_lease_out.valid.expect(true.B)
      dut.io.demand_out.bits.transaction_identity.request_id.expect(3.U)
      dut.io.demand_out.bits.page_ref.page_id.expect(5.U)
      dut.io.demand_out.bits.arrival_ordinal.expect(0.U)
      dut.io.publication_authorization_out.bits.transaction_group_tag.expect(6.U)
      dut.io.publication_authorization_out.bits.packed_authoritative.expect(true.B)
      dut.io.descriptor_grant_out.bits.payload_handle_or_address.expect(0x32.U)
      dut.io.s2_fill_lease_out.bits.s2_slot.expect(1.U)
      // The four independent ready/valid carriers are stable under a legal stall.
      dut.clock.step(); dut.io.demand_out.bits.page_ref.page_id.expect(5.U)
      dut.io.demand_out.ready.poke(true.B); dut.io.publication_authorization_out.ready.poke(true.B)
      dut.io.descriptor_grant_out.ready.poke(true.B); dut.io.s2_fill_lease_out.ready.poke(true.B)
      dut.clock.step() // Evaluate -> Emit
      dut.clock.step() // accept all four materialized carriers -> Collect
      dut.io.demand_out.valid.expect(false.B)
    }
  }

  it("fails closed for a descriptor/page mismatch and never manufactures a demand") {
    simulate(new RouteAPackedReadActivationBinder(p)) { dut =>
      init(dut)
      drivePlan(dut); send(dut.io.accepted_plan_in.valid, dut.io.accepted_plan_in.ready, dut.clock)
      (0 until 2).foreach { ordinal =>
        driveMember(dut, ordinal); send(dut.io.publication_member_in.valid, dut.io.publication_member_in.ready, dut.clock)
      }
      drivePublication(dut); send(dut.io.post_r6_page_ready_in.valid, dut.io.post_r6_page_ready_in.ready, dut.clock)
      driveDescriptor(dut, pageId = 6); send(dut.io.descriptor_grant_in.valid, dut.io.descriptor_grant_in.ready, dut.clock)
      // A mismatched R5 fact must be rejected before any scarce S2 lease is
      // requested; the test therefore does not manufacture a lease response.
      dut.io.s2_fill_lease_request_out.valid.expect(false.B)
      dut.clock.step()
      dut.io.demand_out.valid.expect(false.B); dut.io.publication_authorization_out.valid.expect(false.B)
      dut.io.rejected_observation.valid.expect(true.B); dut.io.rejected_observation.bits.request_id.expect(3.U)
    }
  }

  it("never begins first use from a committed page whose R3 member stream is incomplete") {
    simulate(new RouteAPackedReadActivationBinder(p)) { dut =>
      init(dut)
      drivePlan(dut); send(dut.io.accepted_plan_in.valid, dut.io.accepted_plan_in.ready, dut.clock)
      driveMember(dut, ordinal = 0); send(dut.io.publication_member_in.valid, dut.io.publication_member_in.ready, dut.clock)
      // This malformed test-only sequence represents a missing R6-accepted
      // ordinal.  It must not issue even the address-free R5 query.
      drivePublication(dut); send(dut.io.post_r6_page_ready_in.valid, dut.io.post_r6_page_ready_in.ready, dut.clock)
      dut.io.descriptor_location_request_out.valid.expect(false.B)
      dut.clock.step()
      dut.io.descriptor_location_request_out.valid.expect(false.B)
      dut.io.demand_out.valid.expect(false.B)
      dut.io.rejected_observation.valid.expect(true.B)
    }
  }

  it("refuses a plan without a selected packed source") {
    simulate(new RouteAPackedReadActivationBinder(p)) { dut =>
      init(dut)
      drivePlan(dut, packedPresent = false)
      dut.io.accepted_plan_in.valid.poke(true.B); dut.io.accepted_plan_in.ready.expect(false.B); dut.io.accepted_plan_in.valid.poke(false.B)
      dut.io.demand_out.valid.expect(false.B)
    }
  }

  it("fails closed when the owner-local lease disagrees with R6 packed SourceInstance") {
    simulate(new RouteAPackedReadActivationBinder(p)) { dut =>
      init(dut)
      drivePlan(dut, slot = 1, gen = 3); send(dut.io.accepted_plan_in.valid, dut.io.accepted_plan_in.ready, dut.clock)
      (0 until 2).foreach { ordinal =>
        driveMember(dut, ordinal); send(dut.io.publication_member_in.valid, dut.io.publication_member_in.ready, dut.clock)
      }
      drivePublication(dut); send(dut.io.post_r6_page_ready_in.valid, dut.io.post_r6_page_ready_in.ready, dut.clock)
      driveDescriptor(dut); send(dut.io.descriptor_grant_in.valid, dut.io.descriptor_grant_in.ready, dut.clock)
      driveLease(dut, slot = 0, sourceGen = 2); send(dut.io.s2_fill_lease_in.valid, dut.io.s2_fill_lease_in.ready, dut.clock)
      dut.clock.step(); dut.clock.step()
      dut.io.demand_out.valid.expect(false.B); dut.io.rejected_observation.valid.expect(true.B)
    }
  }
}
