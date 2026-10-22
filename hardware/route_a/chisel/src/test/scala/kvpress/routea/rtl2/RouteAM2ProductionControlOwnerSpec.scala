package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAM2ProductionControlOwner
import kvpress.routea.params.{RouteAM2GroupMember, RouteAR6Encoding, RouteASkeletonParameters}
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
    dut.io.member_request_in.valid.poke(false.B)
    dut.io.member_response_out.ready.poke(false.B)
    dut.io.publication_candidate_in.valid.poke(false.B)
    dut.io.publication_request_out.ready.poke(false.B)
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

  private def drivePublicationCandidate(dut: RouteAM2ProductionControlOwner, tag: Int): Unit = {
    dut.io.publication_candidate_in.bits.transaction_group_tag.poke(tag.U)
    dut.io.publication_candidate_in.bits.p3_layer.poke(0.U)
    dut.io.publication_candidate_in.bits.p3_stage_generation.poke(1.U)
  }

  it("commits the two exact semantic members before reflecting one publication request") {
    simulate(new RouteAM2ProductionControlOwner(p)) { dut =>
      init(dut)
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
    }
  }

  it("never combines members from distinct immutable groups in one layer") {
    simulate(new RouteAM2ProductionControlOwner(p)) { dut =>
      init(dut)
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

      issueMember(dut, RouteAM2GroupMember.HeadControlRmw)
      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B); dut.clock.step()
      drivePublicationCandidate(dut, tag = 2)
      dut.io.publication_candidate_in.valid.poke(true.B); dut.io.publication_candidate_in.ready.expect(false.B)
      dut.io.publication_candidate_in.valid.poke(false.B)
      dut.io.member_response_out.valid.expect(false.B); dut.io.publication_request_out.valid.expect(false.B)
    }
  }
}
