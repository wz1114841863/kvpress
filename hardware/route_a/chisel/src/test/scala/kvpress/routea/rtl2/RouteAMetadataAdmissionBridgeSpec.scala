package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAMetadataAdmissionBridge
import kvpress.routea.params.{RouteAPublicationStatus, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** Directed production-carrier tests for MR-2 admission-to-metadata state. */
final class RouteAMetadataAdmissionBridgeSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 3, p3StageGenerationWidth = 3,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 3,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(dut: RouteAMetadataAdmissionBridge): Unit = {
    dut.io.member_in.valid.poke(false.B)
    dut.io.group_prepare_in.valid.poke(false.B)
    dut.io.group_prepare_out.ready.poke(false.B)
    dut.io.publication_resolution_in.valid.poke(false.B)
    dut.io.membership_handoff_in.valid.poke(false.B)
  }

  private def driveMember(
    dut: RouteAMetadataAdmissionBridge,
    layer: Int,
    head: Int,
    tag: Int,
    ordinal: Int,
    records: Int,
    position: Int,
  ): Unit = {
    val b = dut.io.member_in.bits.payload_binding
    b.transaction_identity.request_id.poke((position & 7).U)
    b.transaction_identity.incarnation.poke(0.U)
    b.entry_id.poke((position * 288 + layer * 8 + head).U)
    b.layer.poke(layer.U); b.kv_head.poke(head.U)
    b.logical_position.poke(position.U); b.payload_ref.poke((position + 10).U)
    b.transaction_group_tag.poke(tag.U); b.group_member_ordinal.poke(ordinal.U); b.group_valid_records.poke(records.U)
    b.payload_handle_or_address.poke((0x40 + position).U); b.source_generation.poke(1.U)
    b.destination_endpoint.poke(0.U); b.m2_group_opaque_address_ref.poke(0.U); b.m2_group_owner.poke(0.U)
  }

  private def offerMember(
    dut: RouteAMetadataAdmissionBridge,
    layer: Int,
    head: Int,
    tag: Int,
    ordinal: Int,
    records: Int,
    position: Int,
  ): Unit = {
    driveMember(dut, layer, head, tag, ordinal, records, position)
    dut.io.member_in.valid.poke(true.B)
    dut.io.member_in.ready.expect(true.B)
    dut.clock.step()
    dut.io.member_in.valid.poke(false.B)
  }

  private def prepare(dut: RouteAMetadataAdmissionBridge, layer: Int, head: Int, tag: Int, records: Int, generation: Int): Unit = {
    val g = dut.io.group_prepare_in.bits
    g.p3_layer.poke(layer.U); g.kv_head.poke(head.U); g.p3_stage_generation.poke(generation.U)
    g.transaction_group_tag.poke(tag.U); g.valid_records.poke(records.U)
    g.opaque_address_ref.poke(0.U); g.owner.poke(0.U)
    dut.io.group_prepare_in.valid.poke(true.B)
    dut.io.group_prepare_in.ready.expect(true.B)
    dut.clock.step()
    dut.io.group_prepare_in.valid.poke(false.B)
  }

  it("records non-contiguous real members, holds preparation privately, and releases credit only after all-member handoff") {
    simulate(new RouteAMetadataAdmissionBridge(p)) { dut =>
      init(dut)
      offerMember(dut, layer = 0, head = 0, tag = 1, ordinal = 1, records = 2, position = 7)
      offerMember(dut, layer = 0, head = 0, tag = 1, ordinal = 0, records = 2, position = 2)
      dut.io.active_group_count.expect(1.U)
      dut.io.local_credit_in_use(0).expect(1.U)

      // A replay cannot allocate a second append sequence or credit.
      driveMember(dut, 0, 0, 1, 0, 2, 2)
      dut.io.member_in.valid.poke(true.B); dut.io.member_in.ready.expect(false.B); dut.io.member_in.valid.poke(false.B)

      prepare(dut, layer = 0, head = 0, tag = 1, records = 2, generation = 3)
      dut.io.group_prepare_out.valid.expect(true.B)
      dut.io.group_prepare_out.bits.transaction_group_tag.expect(1.U)
      dut.io.group_prepare_out.ready.poke(true.B); dut.clock.step(); dut.io.group_prepare_out.ready.poke(false.B)

      val r = dut.io.publication_resolution_in.bits
      r.p3_layer.poke(0.U); r.p3_stage_generation.poke(3.U); r.transaction_group_tag.poke(1.U)
      r.status.poke(RouteAPublicationStatus.Published.U)
      dut.io.publication_resolution_in.valid.poke(true.B); dut.clock.step(); dut.io.publication_resolution_in.valid.poke(false.B)
      // Publication is visible, but the pending credit remains until every R6
      // authority transition has actually fired.
      dut.io.local_credit_in_use(0).expect(1.U)
      val h = dut.io.membership_handoff_in.bits
      h.p3_layer.poke(0.U); h.p3_stage_generation.poke(3.U); h.transaction_group_tag.poke(1.U); h.valid_records.poke(2.U)
      dut.io.membership_handoff_in.valid.poke(true.B); dut.clock.step(); dut.io.membership_handoff_in.valid.poke(false.B)
      dut.io.local_credit_in_use(0).expect(0.U)
      dut.io.active_group_count.expect(0.U)
    }
  }

  it("falls through from a full local credit pool to the bounded shared pool") {
    simulate(new RouteAMetadataAdmissionBridge(p)) { dut =>
      init(dut)
      for (layer <- 0 until 32) {
        offerMember(dut, layer = layer, head = 0, tag = layer & 7, ordinal = 0, records = 1, position = layer)
      }
      dut.io.local_credit_in_use(0).expect(32.U)
      driveMember(dut, layer = 32, head = 0, tag = 0, ordinal = 0, records = 1, position = 40)
      dut.io.member_in.valid.poke(true.B)
      // Shared credit remains available, so the frozen ladder accepts this
      // group into the real per-layer entry rather than dropping or changing it.
      dut.io.member_in.ready.expect(true.B)
      dut.clock.step()
      dut.io.member_in.valid.poke(false.B)
      dut.io.shared_credit_in_use(32).expect(1.U)
    }
  }
}
