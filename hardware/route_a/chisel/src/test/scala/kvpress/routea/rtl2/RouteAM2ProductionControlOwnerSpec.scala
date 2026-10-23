package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAM2ProductionControlOwner
import kvpress.routea.params.{RouteAM2GroupMember, RouteAPublicationStatus, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** MR-2 production M2-control-owner protocol checks; no macro/PPA model. */
final class RouteAM2ProductionControlOwnerSpec extends AnyFunSpec with ChiselSim {
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
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(dut: RouteAM2ProductionControlOwner): Unit = {
    dut.io.group_prepare_in.valid.poke(false.B)
    dut.io.metadata_append_operand_in.valid.poke(false.B)
    dut.io.member_request_in.valid.poke(false.B)
    dut.io.member_response_out.ready.poke(false.B)
    dut.io.publication_candidate_in.valid.poke(false.B)
    dut.io.publication_request_out.ready.poke(false.B)
    dut.io.publication_resolution_in.valid.poke(false.B)
    dut.io.publication_resolution_in.bits.p3_layer.poke(0.U)
    dut.io.publication_resolution_in.bits.p3_stage_generation.poke(0.U)
    dut.io.publication_resolution_in.bits.transaction_group_tag.poke(0.U)
    dut.io.publication_resolution_in.bits.status.poke(RouteAPublicationStatus.Fault.U)
    dut.io.metadata_membership_handoff_in.valid.poke(false.B)
    dut.io.metadata_membership_handoff_in.bits.p3_layer.poke(0.U)
    dut.io.metadata_membership_handoff_in.bits.p3_stage_generation.poke(0.U)
    dut.io.metadata_membership_handoff_in.bits.transaction_group_tag.poke(0.U)
    dut.io.metadata_membership_handoff_in.bits.valid_records.poke(0.U)
  }

  private def driveOperand(dut: RouteAM2ProductionControlOwner, tag: Int): Unit = {
    val operand = dut.io.metadata_append_operand_in.bits
    operand.p3_layer.poke(0.U); operand.kv_head.poke(3.U); operand.p3_stage_generation.poke(1.U)
    operand.transaction_group_tag.poke(tag.U); operand.opaque_mapping_ref.poke("h5a".U); operand.mapping_owner.poke(6.U)
    operand.valid_records.poke(1.U); operand.member_mask.poke(1.U); operand.credit_pool.poke(0.U)
    operand.append_sequence.poke(0.U); operand.predecessor_valid.poke(false.B); operand.predecessor_sequence.poke(0.U)
    val member = operand.members(0)
    member.transaction_identity.request_id.poke(1.U); member.transaction_identity.incarnation.poke(0.U)
    member.entry_id.poke(17.U); member.layer.poke(0.U); member.kv_head.poke(3.U)
    member.logical_position.poke(7.U); member.payload_ref.poke(11.U)
    member.transaction_group_tag.poke(tag.U); member.group_member_ordinal.poke(0.U); member.group_valid_records.poke(1.U)
    member.payload_handle_or_address.poke(0x40.U); member.source_generation.poke(1.U)
    member.destination_endpoint.poke(0.U); member.m2_group_opaque_address_ref.poke("h5a".U); member.m2_group_owner.poke(6.U)
  }

  private def issuePrepare(dut: RouteAM2ProductionControlOwner, tag: Int = 2): Unit = {
    val prepare = dut.io.group_prepare_in.bits
    prepare.p3_layer.poke(0.U); prepare.kv_head.poke(3.U); prepare.p3_stage_generation.poke(1.U)
    prepare.transaction_group_tag.poke(tag.U); prepare.valid_records.poke(1.U)
    prepare.opaque_address_ref.poke("h5a".U); prepare.owner.poke(6.U)
    driveOperand(dut, tag)
    dut.io.group_prepare_in.valid.poke(true.B); dut.io.metadata_append_operand_in.valid.poke(true.B)
    dut.io.group_prepare_in.ready.expect(true.B); dut.io.metadata_append_operand_in.ready.expect(true.B)
    dut.clock.step(); dut.io.group_prepare_in.valid.poke(false.B); dut.io.metadata_append_operand_in.valid.poke(false.B)
  }

  private def issueMember(dut: RouteAM2ProductionControlOwner, member: Int): Unit = {
    val request = dut.io.member_request_in.bits
    request.layer.poke(0.U); request.kv_head.poke(3.U); request.stage_generation.poke(1.U)
    request.transaction_group_tag.poke(2.U); request.member.poke(member.U)
    request.opaque_address_ref.poke("h5a".U); request.owner.poke(6.U)
    dut.io.member_request_in.valid.poke(true.B); dut.io.member_request_in.ready.expect(true.B)
    dut.clock.step(); dut.io.member_request_in.valid.poke(false.B)

    dut.io.member_response_out.valid.expect(true.B)
    dut.io.member_response_out.bits.layer.expect(0.U); dut.io.member_response_out.bits.kv_head.expect(3.U)
    dut.io.member_response_out.bits.stage_generation.expect(1.U); dut.io.member_response_out.bits.transaction_group_tag.expect(2.U)
    dut.io.member_response_out.bits.member.expect(member.U); dut.io.member_response_out.bits.opaque_address_ref.expect("h5a".U)
    dut.io.member_response_out.bits.owner.expect(6.U); dut.io.member_response_out.bits.status.expect(p.coreMemoryOkStatusCode.U)
    // A backpressured response may not mutate or lose its exact carrier.
    dut.clock.step(); dut.io.member_response_out.bits.opaque_address_ref.expect("h5a".U)
    dut.io.member_response_out.ready.poke(true.B); dut.clock.step(); dut.io.member_response_out.ready.poke(false.B)
  }

  private def issueFaultMember(dut: RouteAM2ProductionControlOwner, member: Int): Unit = {
    val request = dut.io.member_request_in.bits
    request.layer.poke(0.U); request.kv_head.poke(3.U); request.stage_generation.poke(1.U)
    request.transaction_group_tag.poke(2.U); request.member.poke(member.U)
    request.opaque_address_ref.poke("h5a".U); request.owner.poke(6.U)
    dut.io.member_request_in.valid.poke(true.B); dut.io.member_request_in.ready.expect(true.B)
    dut.clock.step(); dut.io.member_request_in.valid.poke(false.B)
    dut.io.member_response_out.valid.expect(true.B)
    dut.io.member_response_out.bits.status.expect(p.coreMemoryFaultStatusCode.U)
    dut.io.member_response_out.ready.poke(true.B); dut.clock.step(); dut.io.member_response_out.ready.poke(false.B)
  }

  private def drivePublicationCandidate(dut: RouteAM2ProductionControlOwner, tag: Int): Unit = {
    dut.io.publication_candidate_in.bits.transaction_group_tag.poke(tag.U)
    dut.io.publication_candidate_in.bits.p3_layer.poke(0.U)
    dut.io.publication_candidate_in.bits.p3_stage_generation.poke(1.U)
  }

  private def resolvePublication(dut: RouteAM2ProductionControlOwner, status: Int): Unit = {
    val resolution = dut.io.publication_resolution_in.bits
    resolution.p3_layer.poke(0.U); resolution.p3_stage_generation.poke(1.U)
    resolution.transaction_group_tag.poke(2.U); resolution.status.poke(status.U)
    dut.io.publication_resolution_in.valid.poke(true.B); dut.clock.step(); dut.io.publication_resolution_in.valid.poke(false.B)
  }

  private def handoff(dut: RouteAM2ProductionControlOwner): Unit = {
    val h = dut.io.metadata_membership_handoff_in.bits
    h.p3_layer.poke(0.U); h.p3_stage_generation.poke(1.U)
    h.transaction_group_tag.poke(2.U); h.valid_records.poke(1.U)
    dut.io.metadata_membership_handoff_in.valid.poke(true.B)
    dut.clock.step()
    dut.io.metadata_membership_handoff_in.valid.poke(false.B)
  }

  it("commits the two exact semantic members before reflecting one publication request") {
    simulate(new RouteAM2ProductionControlOwner(p)) { dut =>
      init(dut)
      dut.io.metadata_visible_span_count.expect(0.U)
      issuePrepare(dut)
      // Joint preparation reserves a private slot but has no visible entry.
      dut.io.metadata_private_reservation_count.expect(1.U)
      dut.io.metadata_visible_span_count.expect(0.U)
      issueMember(dut, RouteAM2GroupMember.HeadControlRmw)
      drivePublicationCandidate(dut, tag = 2)
      dut.io.publication_candidate_in.valid.poke(true.B); dut.io.publication_candidate_in.ready.expect(false.B)
      dut.io.publication_candidate_in.valid.poke(false.B)

      issueMember(dut, RouteAM2GroupMember.SpanOwnerRmw)
      drivePublicationCandidate(dut, tag = 3)
      dut.io.publication_candidate_in.valid.poke(true.B); dut.io.publication_candidate_in.ready.expect(false.B)
      dut.io.publication_candidate_in.valid.poke(false.B)

      drivePublicationCandidate(dut, tag = 2)
      dut.io.publication_candidate_in.valid.poke(true.B); dut.io.publication_candidate_in.ready.expect(true.B)
      dut.clock.step(); dut.io.publication_candidate_in.valid.poke(false.B)
      dut.io.publication_request_out.valid.expect(true.B)
      dut.io.publication_request_out.bits.transaction_group_tag.expect(2.U)
      dut.io.publication_request_out.bits.p3_layer.expect(0.U)
      dut.io.publication_request_out.bits.p3_stage_generation.expect(1.U)
      dut.clock.step(); dut.io.publication_request_out.valid.expect(true.B)
      dut.io.publication_request_out.ready.poke(true.B); dut.clock.step(); dut.io.publication_request_out.ready.poke(false.B)
      dut.io.publication_request_out.valid.expect(false.B)
      // The original request handshake is not publication visibility. The
      // control reservation remains private until an accepted resolution.
      val blockedPrepare = dut.io.group_prepare_in.bits
      blockedPrepare.p3_layer.poke(0.U); blockedPrepare.kv_head.poke(3.U); blockedPrepare.p3_stage_generation.poke(1.U)
      blockedPrepare.transaction_group_tag.poke(2.U); blockedPrepare.valid_records.poke(1.U)
      blockedPrepare.opaque_address_ref.poke("h5a".U); blockedPrepare.owner.poke(6.U)
      dut.io.group_prepare_in.valid.poke(true.B)
      dut.io.group_prepare_in.ready.expect(false.B)
      dut.io.group_prepare_in.valid.poke(false.B)
      resolvePublication(dut, RouteAPublicationStatus.Published)
      dut.io.metadata_private_reservation_count.expect(0.U)
      dut.io.metadata_visible_span_count.expect(1.U)
      // A second group cannot overwrite a published head before the precise
      // all-member handoff returns its real old state to the free pool.
      issuePrepare(dut)
      issueFaultMember(dut, RouteAM2GroupMember.HeadControlRmw)
      dut.io.metadata_visible_span_count.expect(1.U)
      // Only the exact completed all-member R6 handoff releases production
      // entry state; it is independent of the earlier publication resolution.
      handoff(dut)
      dut.io.metadata_visible_span_count.expect(0.U)
      issuePrepare(dut)
    }
  }

  it("never combines members from distinct immutable groups in one layer") {
    simulate(new RouteAM2ProductionControlOwner(p)) { dut =>
      init(dut)
      issuePrepare(dut)
      issueMember(dut, RouteAM2GroupMember.HeadControlRmw)

      val request = dut.io.member_request_in.bits
      request.layer.poke(0.U); request.kv_head.poke(4.U); request.stage_generation.poke(1.U)
      request.transaction_group_tag.poke(2.U); request.member.poke(RouteAM2GroupMember.SpanOwnerRmw.U)
      request.opaque_address_ref.poke("h5a".U); request.owner.poke(6.U)
      dut.io.member_request_in.valid.poke(true.B)
      dut.io.member_request_in.ready.expect(false.B)
      dut.clock.step()
      dut.io.member_request_in.valid.poke(false.B)

      drivePublicationCandidate(dut, tag = 2)
      dut.io.publication_candidate_in.valid.poke(true.B)
      dut.io.publication_candidate_in.ready.expect(false.B)
      dut.io.publication_candidate_in.valid.poke(false.B)
    }
  }

  it("fails closed for an out-of-range layer and destructive reset clears member completion") {
    simulate(new RouteAM2ProductionControlOwner(p)) { dut =>
      init(dut)
      val request = dut.io.member_request_in.bits
      request.layer.poke(36.U); request.kv_head.poke(0.U); request.stage_generation.poke(1.U)
      request.transaction_group_tag.poke(1.U); request.member.poke(RouteAM2GroupMember.HeadControlRmw.U)
      request.opaque_address_ref.poke(1.U); request.owner.poke(1.U)
      dut.io.member_request_in.valid.poke(true.B); dut.io.member_request_in.ready.expect(false.B)
      dut.io.member_request_in.valid.poke(false.B)

      issuePrepare(dut)
      issueMember(dut, RouteAM2GroupMember.HeadControlRmw)
      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B); dut.clock.step()
      dut.io.metadata_private_reservation_count.expect(0.U)
      dut.io.metadata_visible_span_count.expect(0.U)
      drivePublicationCandidate(dut, tag = 2)
      dut.io.publication_candidate_in.valid.poke(true.B); dut.io.publication_candidate_in.ready.expect(false.B)
      dut.io.publication_candidate_in.valid.poke(false.B)
      dut.io.member_response_out.valid.expect(false.B); dut.io.publication_request_out.valid.expect(false.B)
    }
  }

  it("requires a prior prepared group and frees the private reservation after a publication fault") {
    simulate(new RouteAM2ProductionControlOwner(p)) { dut =>
      init(dut)
      val request = dut.io.member_request_in.bits
      request.layer.poke(0.U); request.kv_head.poke(3.U); request.stage_generation.poke(1.U)
      request.transaction_group_tag.poke(2.U); request.member.poke(RouteAM2GroupMember.HeadControlRmw.U)
      request.opaque_address_ref.poke("h5a".U); request.owner.poke(6.U)
      dut.io.member_request_in.valid.poke(true.B)
      dut.io.member_request_in.ready.expect(false.B)
      dut.io.member_request_in.valid.poke(false.B)

      issuePrepare(dut)
      issueMember(dut, RouteAM2GroupMember.HeadControlRmw)
      issueMember(dut, RouteAM2GroupMember.SpanOwnerRmw)
      drivePublicationCandidate(dut, tag = 2)
      dut.io.publication_candidate_in.valid.poke(true.B); dut.io.publication_candidate_in.ready.expect(true.B)
      dut.clock.step(); dut.io.publication_candidate_in.valid.poke(false.B)
      dut.io.publication_request_out.ready.poke(true.B); dut.clock.step(); dut.io.publication_request_out.ready.poke(false.B)

      resolvePublication(dut, RouteAPublicationStatus.Fault)
      dut.io.metadata_private_reservation_count.expect(0.U)
      dut.io.metadata_visible_span_count.expect(0.U)
      // The failed R3/R5 publication consumes the private control reservation;
      // a later group may prepare, but no member was made externally visible.
      issuePrepare(dut)
    }
  }

  it("returns a typed member fault and aborts private state when the exact operand is semantically invalid") {
    simulate(new RouteAM2ProductionControlOwner(p)) { dut =>
      init(dut)
      val prepare = dut.io.group_prepare_in.bits
      prepare.p3_layer.poke(0.U); prepare.kv_head.poke(3.U); prepare.p3_stage_generation.poke(1.U)
      prepare.transaction_group_tag.poke(2.U); prepare.valid_records.poke(1.U)
      prepare.opaque_address_ref.poke("h5a".U); prepare.owner.poke(6.U)
      driveOperand(dut, tag = 2)
      // The identity still matches, but this cannot represent the one accepted
      // member, so M2 accepts the group only to return a real fault rather
      // than committing a partial head/span update.
      dut.io.metadata_append_operand_in.bits.member_mask.poke(0.U)
      dut.io.group_prepare_in.valid.poke(true.B); dut.io.metadata_append_operand_in.valid.poke(true.B)
      dut.io.group_prepare_in.ready.expect(true.B); dut.io.metadata_append_operand_in.ready.expect(true.B)
      dut.clock.step(); dut.io.group_prepare_in.valid.poke(false.B); dut.io.metadata_append_operand_in.valid.poke(false.B)
      dut.io.metadata_private_reservation_count.expect(1.U)

      issueFaultMember(dut, RouteAM2GroupMember.HeadControlRmw)
      dut.io.metadata_private_reservation_count.expect(0.U)
      dut.io.metadata_visible_span_count.expect(0.U)
      // Abort makes the exact layer reusable; it never promotes a faulted
      // declaration into a publication candidate.
      issuePrepare(dut)
    }
  }
}
