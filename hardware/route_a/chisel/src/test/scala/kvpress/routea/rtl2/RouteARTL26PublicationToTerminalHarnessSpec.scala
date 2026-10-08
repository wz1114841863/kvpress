package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAM2GroupMember, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.6.4 single-instance, test-only composition.  The R3/R5 publication
  * child and the S2/source/R4/R6 child remain their real owners.  The only
  * join is RouteARTL26PublicationS2Association, which requires the explicit
  * verification association because R3 publication intentionally lacks the
  * attention request identity and selected S2 slot.
  */
final class RouteARTL26PublicationToTerminalHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val pubMemInitDone = Input(Bool())
    val pubAllocate = Flipped(RouteAChannels.page_allocation_req(p))
    val pubClaim = Flipped(RouteAChannels.p3_claim(p))
    val pubAdmissionContext = Flipped(RouteAChannels.admission_context(p))
    val pubAdmissionAuthority = Flipped(RouteAChannels.r6_authority_transition(p))
    val pubPayload = Flipped(RouteAChannels.p3_pending_fragment(p))
    val pubSidecar = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val pubExternal = new CoreMemoryExternalPort(p)
    val m2MemberRequest = RouteAChannels.m2_group_member_req(p)
    val m2MemberResponse = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val m2PublicationCandidate = RouteAChannels.metadata_publish_req(p)
    val m2PublicationRequest = Flipped(RouteAChannels.metadata_publish_req(p))
    val verificationAssociation = Flipped(chisel3.util.Decoupled(new VerificationPackedS2Association(p)))

    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val status = Flipped(RouteAChannels.component_status(p))
    val sourcePlan = Flipped(RouteAChannels.source_completion_plan(p))
    val s2FillOpen = Flipped(RouteAChannels.s2_fill_open(p))
    val s2Payload = Flipped(RouteAChannels.s2_payload_fragment(p))
    val s2Terminal = Flipped(RouteAChannels.s2_fill_terminal(p))
    val packedOffer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packedFragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val numericFault = Flipped(RouteAChannels.r4_numeric_fault)
    val attentionTerminal = RouteAChannels.attention_terminal_rsp
    val p3State = Output(UInt(3.W))
    val s2Ready = Output(Bool())
  })

  val publication = Module(new RouteA2_1cAtomicPublicationHarness(p))
  val association = Module(new RouteARTL26PublicationS2Association(p))
  val sourceTerminal = Module(new RouteARTL26ComposedPackedSourceHarness(p))

  publication.io.mem_init_done := io.pubMemInitDone
  publication.io.r5_allocate <> io.pubAllocate
  publication.io.r5_allocation_rsp.ready := true.B
  publication.io.p3_claim <> io.pubClaim
  publication.io.admission_context <> io.pubAdmissionContext
  publication.io.admission_authority <> io.pubAdmissionAuthority
  publication.io.hot_payload <> io.pubPayload
  publication.io.hot_sidecar <> io.pubSidecar
  publication.io.external <> io.pubExternal
  io.m2MemberRequest <> publication.io.m2_member_request
  publication.io.m2_member_response <> io.m2MemberResponse
  io.m2PublicationCandidate <> publication.io.m2_publication_candidate
  publication.io.m2_publication_request <> io.m2PublicationRequest
  publication.io.publication_member.ready := true.B
  publication.io.publication_ack.ready := true.B
  association.io.publicationCommitIn <> publication.io.publication_commit
  association.io.authorityTransitionIn <> publication.io.authority_transition
  association.io.verificationAssociationIn <> io.verificationAssociation
  io.p3State := publication.io.p3_state

  sourceTerminal.io.frontend <> io.frontend
  sourceTerminal.io.status <> io.status
  sourceTerminal.io.sourcePlan <> io.sourcePlan
  sourceTerminal.io.s2Service <> association.io.s2ServiceOut
  sourceTerminal.io.s2FillOpen <> io.s2FillOpen
  sourceTerminal.io.s2Payload <> io.s2Payload
  sourceTerminal.io.s2Terminal <> io.s2Terminal
  sourceTerminal.io.packedOffer <> io.packedOffer
  sourceTerminal.io.packedFragment <> io.packedFragment
  sourceTerminal.io.numericFault <> io.numericFault
  io.attentionTerminal <> sourceTerminal.io.attentionTerminal
  io.s2Ready := sourceTerminal.io.s2Ready
}

/**
  * No-model functional witness: publication is real R3/R5/R2/R1 behavior;
  * association is explicit verification scope; source completion and terminal
  * are real S2/R4/R6 behavior.  It does not claim a production top bridge.
  */
final class RouteARTL26PublicationToTerminalHarnessSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=32, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def id(x: TransactionIdentity, rid: Int, inc: Int = 0): Unit = { x.request_id.poke(rid.U); x.incarnation.poke(inc.U) }
  private def inst(x: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = { x.source_kind.poke(kind.U); x.instance_coordinate.poke(coordinate.U); x.generation.poke(generation.U) }
  private def init(d: RouteARTL26PublicationToTerminalHarness): Unit = {
    d.io.pubMemInitDone.poke(false.B); d.io.pubAllocate.valid.poke(false.B); d.io.pubClaim.valid.poke(false.B); d.io.pubAdmissionContext.valid.poke(false.B); d.io.pubAdmissionAuthority.valid.poke(false.B); d.io.pubPayload.valid.poke(false.B); d.io.pubSidecar.valid.poke(false.B)
    d.io.pubExternal.init_ack.valid.poke(false.B); d.io.pubExternal.request.ready.poke(false.B); d.io.pubExternal.response.valid.poke(false.B); d.io.pubExternal.init_ack.bits.adapter_epoch_ready.poke(true.B); id(d.io.pubExternal.response.bits.transaction_identity,0); d.io.pubExternal.response.bits.fragment_index.poke(0.U); d.io.pubExternal.response.bits.last.poke(true.B); d.io.pubExternal.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.pubExternal.response.bits.data.poke(0.U)
    d.io.m2MemberRequest.ready.poke(false.B); d.io.m2MemberResponse.valid.poke(false.B); d.io.m2PublicationCandidate.ready.poke(false.B); d.io.m2PublicationRequest.valid.poke(false.B); d.io.verificationAssociation.valid.poke(false.B)
    d.io.frontend.valid.poke(false.B); d.io.status.valid.poke(false.B); d.io.sourcePlan.valid.poke(false.B); d.io.s2FillOpen.valid.poke(false.B); d.io.s2Payload.valid.poke(false.B); d.io.s2Terminal.valid.poke(false.B); d.io.packedOffer.valid.poke(false.B); d.io.packedFragment.valid.poke(false.B); d.io.numericFault.valid.poke(false.B); d.io.attentionTerminal.ready.poke(false.B)
    d.io.pubMemInitDone.poke(true.B); d.io.pubExternal.init_ack.valid.poke(true.B); d.clock.step(); d.io.pubExternal.init_ack.valid.poke(false.B)
  }
  private def acceptReq(d: RouteARTL26PublicationToTerminalHarness, kind: Int, index: Int): Unit = { var n=0; while(!d.io.pubExternal.request.valid.peek().litToBoolean && n<32){d.clock.step();n+=1}; d.io.pubExternal.request.valid.expect(true.B); d.io.pubExternal.request.bits.request_kind.expect(kind.U); d.io.pubExternal.request.bits.fragment_index.expect(index.U); d.io.pubExternal.request.ready.poke(true.B); d.clock.step(); d.io.pubExternal.request.ready.poke(false.B) }
  private def terminal(d: RouteARTL26PublicationToTerminalHarness, rid: Int): Unit = { id(d.io.pubExternal.response.bits.transaction_identity,rid); d.io.pubExternal.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.pubExternal.response.valid.poke(true.B); d.io.pubExternal.response.ready.expect(true.B); d.clock.step(); d.io.pubExternal.response.valid.poke(false.B) }
  private def publish(d: RouteARTL26PublicationToTerminalHarness): Unit = {
    val a=d.io.pubAllocate.bits; a.layer.poke(0.U); a.kv_head.poke(0.U); a.valid_records.poke(1.U); a.transaction_group_tag.poke(1.U); d.io.pubAllocate.valid.poke(true.B); d.io.pubAllocate.ready.expect(true.B); d.clock.step(); d.io.pubAllocate.valid.poke(false.B)
    val c=d.io.pubClaim.bits; c.layer.poke(0.U); c.kv_head.poke(0.U); c.owner.poke(0.U); c.page_ref.page_id.poke(0.U); c.page_ref.generation.poke(0.U); c.valid_records.poke(1.U); c.requires_tail_link.poke(false.B); c.transaction_group_tag.poke(1.U); d.io.pubClaim.valid.poke(true.B); d.io.pubClaim.ready.expect(true.B); d.clock.step(); d.io.pubClaim.valid.poke(false.B)
    val x=d.io.pubAdmissionContext.bits; x.entry_id.poke(0.U); x.layer.poke(0.U); x.kv_head.poke(0.U); x.logical_position.poke(0.U); x.payload_ref.poke(55.U); x.transaction_group_tag.poke(1.U); x.group_member_ordinal.poke(0.U); x.group_valid_records.poke(1.U)
    val h=d.io.pubAdmissionAuthority.bits; h.entry_id.poke(0.U); h.from_authority.poke(RouteAAuthorityStateCode.Hot.U); h.to_authority.poke(RouteAAuthorityStateCode.Pending.U); h.transaction_group_tag.poke(1.U)
    d.io.pubAdmissionContext.valid.poke(true.B); d.io.pubAdmissionAuthority.valid.poke(true.B); d.io.pubAdmissionContext.ready.expect(true.B); d.clock.step(); d.io.pubAdmissionContext.valid.poke(false.B); d.io.pubAdmissionAuthority.valid.poke(false.B)
    val f=d.io.pubPayload.bits; f.layer.poke(0.U); f.stage_generation.poke(1.U); f.status.poke(p.coreMemoryOkStatusCode.U); f.payload_ref.poke(55.U); (0 until 8).foreach { i => f.fragment_index.poke(i.U); f.last.poke((i==7).B); f.data.poke((0x100+i).U); d.io.pubPayload.valid.poke(true.B); d.io.pubPayload.ready.expect(true.B); d.clock.step() }; d.io.pubPayload.valid.poke(false.B)
    val s=d.io.pubSidecar.bits; s.layer.poke(0.U); s.stage_generation.poke(1.U); s.record_ordinal.poke(0.U); s.payload_ref.poke(55.U); s.logical_position.poke(0.U); d.io.pubSidecar.valid.poke(true.B); d.io.pubSidecar.ready.expect(true.B); d.clock.step(); d.io.pubSidecar.valid.poke(false.B)
    d.clock.step(); acceptReq(d,p.coreMemoryWriteRequestCode,0); (0 until 8).foreach(i=>acceptReq(d,p.coreMemoryWriteDataCode,i)); terminal(d,0)
    acceptReq(d,p.coreMemoryWriteRequestCode,0); acceptReq(d,p.coreMemoryWriteDataCode,0); terminal(d,0)
    def member(m: Int): Unit = { var n=0; while(!d.io.m2MemberRequest.valid.peek().litToBoolean && n<32){d.clock.step();n+=1}; d.io.m2MemberRequest.bits.member.expect(m.U); d.io.m2MemberRequest.ready.poke(true.B); d.clock.step(); d.io.m2MemberRequest.ready.poke(false.B); val r=d.io.m2MemberResponse.bits; r.layer.poke(0.U); r.stage_generation.poke(1.U); r.transaction_group_tag.poke(1.U); r.member.poke(m.U); r.status.poke(p.coreMemoryOkStatusCode.U); d.io.m2MemberResponse.valid.poke(true.B); d.io.m2MemberResponse.ready.expect(true.B); d.clock.step(); d.io.m2MemberResponse.valid.poke(false.B) }
    member(RouteAM2GroupMember.HeadControlRmw); member(RouteAM2GroupMember.SpanOwnerRmw)
    var n=0; while(!d.io.m2PublicationCandidate.valid.peek().litToBoolean && n<32){d.clock.step();n+=1}; d.io.m2PublicationCandidate.valid.expect(true.B); d.io.m2PublicationCandidate.ready.poke(true.B); d.clock.step(); d.io.m2PublicationCandidate.ready.poke(false.B)
    val r=d.io.m2PublicationRequest.bits; r.transaction_group_tag.poke(1.U); r.p3_layer.poke(0.U); r.p3_stage_generation.poke(1.U); d.io.m2PublicationRequest.valid.poke(true.B); d.io.m2PublicationRequest.ready.expect(true.B); d.clock.step(); d.io.m2PublicationRequest.valid.poke(false.B)
  }
  private def startAttention(d: RouteARTL26PublicationToTerminalHarness): Unit = { Seq(p.r6.memInitDoneStatusCode,p.r6.m2P3InitDoneStatusCode,p.r6.pageManagerInitDoneStatusCode).foreach { code => d.io.status.bits.acknowledgement_name.poke(code.U); d.io.status.bits.asserted.poke(true.B); d.io.status.valid.poke(true.B); d.io.status.ready.expect(true.B); d.clock.step(); d.io.status.valid.poke(false.B) }; def front(e:Int,r:Int):Unit={val x=d.io.frontend.bits;x.event_kind.poke(e.U);x.session_id.poke(false.B);x.context_tokens.poke(32768.U);x.entry_id.poke(0.U);x.layer.poke(0.U);x.kv_head.poke(0.U);x.logical_position.poke(0.U);x.payload_ref.poke(0.U);x.disposition.poke(false.B);id(x.transaction_identity,r);x.admission_group_tag.poke(0.U);x.admission_member_ordinal.poke(0.U);x.admission_group_valid_records.poke(1.U);d.io.frontend.valid.poke(true.B);d.io.frontend.ready.expect(true.B);d.clock.step();d.io.frontend.valid.poke(false.B)};front(p.r6.sessionStartEventCode,0);front(p.r6.attentionServiceEventCode,3); val q=d.io.sourcePlan.bits;id(q.transaction_identity,3);q.source_presence.poke(4.U);inst(q.hot_instance,0,0,0);inst(q.pending_instance,1,0,0);inst(q.packed_instance,2,0,1);d.io.sourcePlan.valid.poke(true.B);d.io.sourcePlan.ready.expect(true.B);d.clock.step();d.io.sourcePlan.valid.poke(false.B);d.clock.step() }
  private def associateAndFill(d: RouteARTL26PublicationToTerminalHarness): Unit = { val a=d.io.verificationAssociation.bits;id(a.transaction_identity,3);a.page_ref.page_id.poke(0.U);a.page_ref.generation.poke(0.U);a.transaction_group_tag.poke(1.U);a.valid_records.poke(1.U);a.s2_slot.poke(0.U);a.source_generation.poke(1.U);d.io.verificationAssociation.valid.poke(true.B);var n=0;while(!d.io.verificationAssociation.ready.peek().litToBoolean&&n<32){d.clock.step();n+=1};d.io.verificationAssociation.ready.expect(true.B);d.clock.step();d.io.verificationAssociation.valid.poke(false.B);d.clock.step(2)
    val o=d.io.s2FillOpen.bits;id(o.transaction_identity,3);o.page_ref.page_id.poke(0.U);o.page_ref.generation.poke(0.U);o.s2_slot.poke(0.U);o.source_generation.poke(1.U);o.expected_fragment_count.poke(1.U);o.expected_sidecar_records.poke(0.U);o.requires_sidecar.poke(false.B);d.io.s2FillOpen.valid.poke(true.B);d.io.s2FillOpen.ready.expect(true.B);d.clock.step();d.io.s2FillOpen.valid.poke(false.B)
    val q=d.io.s2Payload.bits;id(q.transaction_identity,3);q.s2_slot.poke(0.U);q.source_generation.poke(1.U);q.fragment_index.poke(0.U);q.last.poke(true.B);q.data.poke(0.U);d.io.s2Payload.valid.poke(true.B);d.io.s2Payload.ready.expect(true.B);d.clock.step();d.io.s2Payload.valid.poke(false.B)
    val t=d.io.s2Terminal.bits;id(t.transaction_identity,3);t.s2_slot.poke(0.U);t.source_generation.poke(1.U);t.fragment_index.poke(0.U);t.last.poke(true.B);t.status.poke(p.coreMemoryOkStatusCode.U);d.io.s2Terminal.valid.poke(true.B);d.io.s2Terminal.ready.expect(true.B);d.clock.step();d.io.s2Terminal.valid.poke(false.B);d.io.s2Ready.expect(true.B) }
  private def packet(d: RouteARTL26PublicationToTerminalHarness,c:Int): Unit = { def header= (BigInt(2)<<64)|(BigInt(c)<<66)|(BigInt(1)<<69)|(BigInt(8)<<70); val o=d.io.packedOffer.bits;id(o.transaction_identity,3);inst(o.source_instance,2,0,1);o.consumer_id.poke(c.U);o.r4_header.poke(header.U);o.partial_present.poke(true.B);d.io.packedOffer.valid.poke(true.B);d.io.packedOffer.ready.expect(true.B);d.clock.step();d.io.packedOffer.valid.poke(false.B);d.clock.step();(0 until 8).foreach{i=>val f=d.io.packedFragment.bits;id(f.transaction_identity,3);inst(f.source_instance,2,0,1);f.consumer_id.poke(c.U);f.fragment_index.poke(i.U);f.last.poke((i==7).B);f.data.poke((c*8+i).U);d.io.packedFragment.valid.poke(true.B);d.io.packedFragment.ready.expect(true.B);d.clock.step();d.io.packedFragment.valid.poke(false.B)};d.clock.step(2) }

  it("composes R3/R5 publication through explicit association into S2, four commits, and one R4/R6 fault terminal") { simulate(new RouteARTL26PublicationToTerminalHarness(p)) { d =>
    init(d); startAttention(d); publish(d); associateAndFill(d); d.io.p3State.expect(0.U); (0 until 4).foreach(packet(d,_)); id(d.io.numericFault.bits.transaction_identity,3); var n=0;while(!d.io.numericFault.ready.peek().litToBoolean&&n<16){d.clock.step();n+=1};d.io.numericFault.ready.expect(true.B);d.io.numericFault.valid.poke(true.B);d.clock.step();d.io.numericFault.valid.poke(false.B);n=0;while(!d.io.attentionTerminal.valid.peek().litToBoolean&&n<16){d.clock.step();n+=1};d.io.attentionTerminal.valid.expect(true.B);d.io.attentionTerminal.bits.transaction_identity.request_id.expect(3.U);d.io.attentionTerminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U);d.io.attentionTerminal.ready.poke(true.B);d.clock.step();d.io.attentionTerminal.ready.poke(false.B)
  } }
}
