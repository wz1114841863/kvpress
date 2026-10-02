package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.interfaces.RouteAAuthorityStateCode
import kvpress.routea.params.{RouteAM2GroupMember, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL2.1c functional protocol tests; no cycle, throughput, or PPA claim. */
final class RouteA2_1cAtomicPublicationHarnessSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=32, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def init(d: RouteA2_1cAtomicPublicationHarness): Unit = {
    d.io.mem_init_done.poke(false.B); d.io.r5_allocate.valid.poke(false.B); d.io.r5_allocation_rsp.ready.poke(true.B)
    d.io.p3_claim.valid.poke(false.B); d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B)
    d.io.hot_payload.valid.poke(false.B); d.io.hot_sidecar.valid.poke(false.B)
    d.io.m2_member_request.ready.poke(false.B); d.io.m2_member_response.valid.poke(false.B)
    d.io.m2_publication_candidate.ready.poke(false.B); d.io.m2_publication_request.valid.poke(false.B)
    d.io.authority_transition.ready.poke(false.B); d.io.publication_commit.ready.poke(false.B); d.io.publication_member.ready.poke(false.B); d.io.publication_ack.ready.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B)
    d.io.external.response.bits.transaction_identity.request_id.poke(0.U); d.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B); d.io.external.response.bits.status.poke(0.U); d.io.external.response.bits.data.poke(0.U)
    d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.mem_init_done.poke(true.B); d.io.external.init_ack.valid.poke(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B)
  }

  private def acceptReq(d: RouteA2_1cAtomicPublicationHarness, kind: Int, index: Int): Unit = {
    var waited = 0
    while (d.io.external.request.valid.peek().litValue == 0 && waited < 32) { d.clock.step(); waited += 1 }
    require(waited < 32, s"timed out waiting for request kind=$kind index=$index")
    d.io.external.request.valid.expect(true.B); d.io.external.request.bits.request_kind.expect(kind.U)
    d.io.external.request.bits.fragment_index.expect(index.U)
    d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B)
  }

  private def terminal(d: RouteA2_1cAtomicPublicationHarness, requestId: Int = 0, fault: Boolean = false): Unit = {
    d.io.external.response.bits.transaction_identity.request_id.poke(requestId.U)
    d.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    d.io.external.response.bits.status.poke((if (fault) 1 else 0).U)
    d.io.external.response.valid.poke(true.B); d.io.external.response.ready.expect(true.B)
    d.clock.step(); d.io.external.response.valid.poke(false.B)
  }

  private def admitAndMakePayloadDurable(d: RouteA2_1cAtomicPublicationHarness, tag: Int, position: Int, payloadRef: Int, pageId: Int): Unit = {
    val a=d.io.r5_allocate.bits; a.layer.poke(0.U); a.kv_head.poke(0.U); a.valid_records.poke(1.U); a.transaction_group_tag.poke(tag.U)
    d.io.r5_allocate.valid.poke(true.B); d.io.r5_allocate.ready.expect(true.B); d.clock.step(); d.io.r5_allocate.valid.poke(false.B)
    val c=d.io.p3_claim.bits; c.layer.poke(0.U); c.kv_head.poke(0.U); c.owner.poke(0.U); c.page_ref.page_id.poke(pageId.U); c.page_ref.generation.poke(0.U); c.valid_records.poke(1.U); c.requires_tail_link.poke((pageId != 0).B); c.transaction_group_tag.poke(tag.U)
    d.io.p3_claim.valid.poke(true.B)
    var claimWait = 0
    while (d.io.p3_claim.ready.peek().litValue == 0 && claimWait < 32) { d.clock.step(); claimWait += 1 }
    d.io.p3_claim.ready.expect(true.B); d.clock.step(); d.io.p3_claim.valid.poke(false.B)
    val x=d.io.admission_context.bits; x.entry_id.poke((position * 288).U); x.layer.poke(0.U); x.kv_head.poke(0.U); x.logical_position.poke(position.U); x.payload_ref.poke(payloadRef.U); x.transaction_group_tag.poke(tag.U); x.group_member_ordinal.poke(0.U); x.group_valid_records.poke(1.U)
    val h=d.io.admission_authority.bits; h.entry_id.poke((position * 288).U); h.from_authority.poke(RouteAAuthorityStateCode.Hot.U); h.to_authority.poke(RouteAAuthorityStateCode.Pending.U); h.transaction_group_tag.poke(tag.U)
    d.io.admission_context.valid.poke(true.B); d.io.admission_authority.valid.poke(true.B); d.io.admission_context.ready.expect(true.B); d.clock.step(); d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B)
    val f=d.io.hot_payload.bits; f.layer.poke(0.U); f.stage_generation.poke((pageId + 1).U); f.status.poke(0.U); f.payload_ref.poke(payloadRef.U)
    (0 until 8).foreach { i => f.fragment_index.poke(i.U); f.last.poke((i==7).B); f.data.poke((0x100 + pageId * 16 + i).U); d.io.hot_payload.valid.poke(true.B); d.io.hot_payload.ready.expect(true.B); d.clock.step() }; d.io.hot_payload.valid.poke(false.B)
    val s=d.io.hot_sidecar.bits; s.layer.poke(0.U); s.stage_generation.poke((pageId + 1).U); s.record_ordinal.poke(0.U); s.payload_ref.poke(payloadRef.U); s.logical_position.poke(position.U); d.io.hot_sidecar.valid.poke(true.B); d.io.hot_sidecar.ready.expect(true.B); d.clock.step(); d.io.hot_sidecar.valid.poke(false.B)
    d.clock.step(); acceptReq(d,p.coreMemoryWriteRequestCode,0); (0 until 8).foreach(i=>acceptReq(d,p.coreMemoryWriteDataCode,i))
    // R1 consumes an unmatched external terminal at its boundary, but it must
    // not emit it into the core path or mutate the R3 write association.
    d.io.external.response.bits.transaction_identity.request_id.poke(pageId.U)
    d.io.external.response.bits.transaction_identity.incarnation.poke(1.U)
    d.io.external.response.bits.status.poke(0.U); d.io.external.response.valid.poke(true.B)
    d.io.external.response.ready.expect(true.B); d.clock.step(); d.io.external.response.valid.poke(false.B)
    d.io.p3_state.expect(4.U) // WRITE_ISSUED: stale response did not complete it.
    terminal(d, requestId=pageId)
  }

  private def finishDescriptorWrites(d: RouteA2_1cAtomicPublicationHarness, firstRequestId: Int, tail: Boolean, fault: Boolean = false): Unit = {
    acceptReq(d,p.coreMemoryWriteRequestCode,0); acceptReq(d,p.coreMemoryWriteDataCode,0); terminal(d, requestId=firstRequestId, fault=fault)
    if (tail && !fault) { acceptReq(d,p.coreMemoryWriteRequestCode,0); acceptReq(d,p.coreMemoryWriteDataCode,0); terminal(d, requestId=firstRequestId + 1) }
  }

  private def takeMemberRequest(d: RouteA2_1cAtomicPublicationHarness, member: Int): Unit = {
    var waited = 0
    while (d.io.m2_member_request.valid.peek().litValue == 0 && waited < 32) { d.clock.step(); waited += 1 }
    d.io.m2_member_request.valid.expect(true.B); d.io.m2_member_request.bits.member.expect(member.U)
    d.io.m2_member_request.ready.poke(true.B); d.clock.step(); d.io.m2_member_request.ready.poke(false.B)
  }
  private def memberResponse(d: RouteA2_1cAtomicPublicationHarness, member: Int, generation: Int = 1, status: Int = 0): Unit = {
    val r=d.io.m2_member_response.bits; r.layer.poke(0.U); r.stage_generation.poke(generation.U); r.transaction_group_tag.poke(1.U); r.member.poke(member.U); r.status.poke(status.U)
    d.io.m2_member_response.valid.poke(true.B); d.io.m2_member_response.ready.expect(true.B); d.clock.step(); d.io.m2_member_response.valid.poke(false.B)
  }

  it("publishes only after exact M2 members and nested R5 acknowledgement, including a tail-link append") {
    simulate(new RouteA2_1cAtomicPublicationHarness(p)) { d =>
      init(d)
      // First page makes the stream tail visible only after atomic publication.
      admitAndMakePayloadDurable(d, 1, 0, 55, 0); finishDescriptorWrites(d, firstRequestId=0, tail=false)
      takeMemberRequest(d, RouteAM2GroupMember.HeadControlRmw); memberResponse(d, RouteAM2GroupMember.HeadControlRmw)
      takeMemberRequest(d, RouteAM2GroupMember.SpanOwnerRmw)
      // Old member 0 and wrong stage generation are both fail-closed.
      val stale=d.io.m2_member_response.bits; stale.layer.poke(0.U); stale.stage_generation.poke(1.U); stale.transaction_group_tag.poke(1.U); stale.member.poke(RouteAM2GroupMember.HeadControlRmw.U); stale.status.poke(0.U)
      d.io.m2_member_response.valid.poke(true.B); d.io.m2_member_response.ready.expect(false.B); d.clock.step(); d.io.m2_member_response.valid.poke(false.B)
      memberResponse(d, RouteAM2GroupMember.SpanOwnerRmw)
      var waited = 0; while (d.io.m2_publication_candidate.valid.peek().litValue == 0 && waited < 32) { d.clock.step(); waited += 1 }
      d.io.m2_publication_candidate.valid.expect(true.B)
      // A publication request is invalid until the exact R3 candidate has fired.
      d.io.m2_publication_request.bits.transaction_group_tag.poke(1.U); d.io.m2_publication_request.bits.p3_layer.poke(0.U); d.io.m2_publication_request.bits.p3_stage_generation.poke(0.U)
      d.io.m2_publication_request.valid.poke(true.B); d.io.m2_publication_request.ready.expect(false.B); d.clock.step(); d.io.m2_publication_request.valid.poke(false.B)
      d.io.m2_publication_candidate.ready.poke(true.B); d.clock.step(); d.io.m2_publication_candidate.ready.poke(false.B)
      d.io.m2_publication_request.bits.p3_stage_generation.poke(1.U); d.io.m2_publication_request.valid.poke(true.B); d.io.m2_publication_request.ready.expect(true.B); d.clock.step(); d.io.m2_publication_request.valid.poke(false.B)
      var ackWait = 0; while (d.io.publication_ack.valid.peek().litValue == 0 && ackWait < 32) { d.clock.step(); ackWait += 1 }
      d.io.publication_ack.valid.expect(true.B); d.io.p3_state.expect(5.U)
      d.io.authority_transition.ready.poke(true.B); d.io.publication_commit.ready.poke(true.B); d.io.publication_member.ready.poke(true.B); d.io.publication_ack.ready.poke(true.B); d.clock.step()
      d.io.publication_ack.ready.poke(false.B); d.io.p3_state.expect(0.U)

      // The second allocation needs the first published tail and therefore
      // emits the separate new-page and tail-link descriptor writes.
      admitAndMakePayloadDurable(d, 2, 1, 66, 1); finishDescriptorWrites(d, firstRequestId=1, tail=true)
      takeMemberRequest(d, RouteAM2GroupMember.HeadControlRmw)
    }
  }

  it("fails closed on an R1 descriptor terminal fault before any M2/publication carrier") {
    simulate(new RouteA2_1cAtomicPublicationHarness(p)) { d =>
      init(d)
      admitAndMakePayloadDurable(d, 1, 0, 55, 0)
      finishDescriptorWrites(d, firstRequestId=0, tail=false, fault=true)
      d.clock.step(2)
      d.io.p3_state.expect(6.U)
      d.io.m2_member_request.valid.expect(false.B); d.io.m2_publication_candidate.valid.expect(false.B); d.io.publication_ack.valid.expect(false.B)
    }
  }

  it("fails closed on the exact outstanding M2 member fault") {
    simulate(new RouteA2_1cAtomicPublicationHarness(p)) { d =>
      init(d)
      admitAndMakePayloadDurable(d, 1, 0, 55, 0); finishDescriptorWrites(d, firstRequestId=0, tail=false)
      takeMemberRequest(d, RouteAM2GroupMember.HeadControlRmw)
      memberResponse(d, RouteAM2GroupMember.HeadControlRmw, status=1)
      d.clock.step(); d.io.p3_state.expect(6.U)
      d.io.m2_member_request.valid.expect(false.B); d.io.m2_publication_candidate.valid.expect(false.B)
    }
  }
}
