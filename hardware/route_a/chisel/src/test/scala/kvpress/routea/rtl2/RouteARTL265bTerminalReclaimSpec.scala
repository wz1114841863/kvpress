package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteAS2GqaSourceWrapper, RouteASourceServicePacketAdapter}
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAMergeBoundary, RouteAPageManager}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.RouteAComponentStatusCollector
import org.scalatest.funspec.AnyFunSpec

/**
  * Verification-only identity association between an already accepted R6
  * attention terminal and the environment-owned runtime-retire request.  It
  * deliberately does not claim that a terminal autonomously initiates
  * retirement: it merely rejects a mismatched or premature environment
  * request before it can reach the existing R6 owner.
  */
final class RouteATerminalRetireAssociation extends Module {
  val io = IO(new Bundle {
    val terminal_in = Flipped(RouteAChannels.attention_terminal_rsp)
    val terminal_out = RouteAChannels.attention_terminal_rsp
    val runtime_retire_in = Flipped(RouteAChannels.runtime_retire_req)
    val runtime_retire_out = RouteAChannels.runtime_retire_req
  })

  val terminalSeen = RegInit(false.B)
  val terminalIdentity = Reg(new TransactionIdentity)
  io.terminal_out.valid := io.terminal_in.valid && !terminalSeen
  io.terminal_out.bits := io.terminal_in.bits
  io.terminal_in.ready := !terminalSeen && io.terminal_out.ready
  when(io.terminal_in.fire) {
    terminalSeen := true.B
    terminalIdentity := io.terminal_in.bits.transaction_identity
  }

  val identityMatches = io.runtime_retire_in.bits.transaction_identity.asUInt === terminalIdentity.asUInt
  io.runtime_retire_out.valid := terminalSeen && identityMatches && io.runtime_retire_in.valid
  io.runtime_retire_out.bits := io.runtime_retire_in.bits
  io.runtime_retire_in.ready := terminalSeen && identityMatches && io.runtime_retire_out.ready
  when(io.runtime_retire_out.fire) { terminalSeen := false.B }
}

/**
  * RTL2.6.5b test-only same-instance terminal-to-reclaim composition.  R6,
  * R5, R2, R1, S2, and R4 retain their existing owner-local behavior.  The
  * only new child is the verification association above; it neither produces
  * a terminal nor a reclaim permit, and it cannot turn terminal completion
  * into an implicit production retirement policy.
  */
final class RouteARTL265bTerminalReclaimHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val r3_status = Flipped(RouteAChannels.component_status(p))
    val direct_status = Flipped(RouteAChannels.component_status(p))
    val runtime_retire = Flipped(RouteAChannels.runtime_retire_req)
    val attention_terminal = RouteAChannels.attention_terminal_rsp
    val retire_ack = RouteAChannels.session_retire_ack

    val allocation = Flipped(RouteAChannels.page_allocation_req(p))
    val descriptor_terminal = Flipped(RouteAChannels.descriptor_maintenance_terminal(p))
    val visibility = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val external = new CoreMemoryExternalPort(p)

    val source_plan = Flipped(RouteAChannels.source_completion_plan(p))
    val s2_service = Flipped(RouteAChannels.s2_service_req)
    val s2_fill_open = Flipped(RouteAChannels.s2_fill_open(p))
    val s2_payload = Flipped(RouteAChannels.s2_payload_fragment(p))
    val s2_terminal = Flipped(RouteAChannels.s2_fill_terminal(p))
    val packed_offer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packed_fragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val numeric_fault = Flipped(RouteAChannels.r4_numeric_fault)
  })

  val r6 = Module(new RouteALifecycleAdapter(p))
  val r5 = Module(new RouteAPageManager(p))
  StructuralTieOff.source(r5.io.descriptor_location_request_in)
  StructuralTieOff.sink(r5.io.descriptor_location_grant_out)
  val r2 = Module(new RouteACoreSideArbiter(p))
  val r1 = Module(new RouteACoreMemIfV1(p))
  val collector = Module(new RouteAComponentStatusCollector(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  StructuralTieOff.source(s2.io.s2_fill_lease_request_in)
  StructuralTieOff.sink(s2.io.s2_fill_lease_out)
  val packets = Module(new RouteASourceServicePacketAdapter(p))
  val merge = Module(new RouteAMergeBoundary(p))
  val association = Module(new RouteATerminalRetireAssociation)

  r6.io.frontend_lifecycle_req <> io.frontend
  r6.io.component_status_in <> collector.io.component_status_out
  collector.io.drain_collection_enable := r6.io.drain_collection_enable
  collector.io.reclaim_drain_restart := r6.io.reclaim_drain_restart
  collector.io.reclaim_final_drain_enable := r6.io.reclaim_final_drain_enable
  association.io.runtime_retire_in <> io.runtime_retire
  r6.io.runtime_retire_req <> association.io.runtime_retire_out
  association.io.terminal_in <> r6.io.attention_terminal_rsp
  io.attention_terminal <> association.io.terminal_out
  io.retire_ack <> r6.io.session_retire_ack
  r6.io.source_completion_plan_in <> io.source_plan
  packets.io.accepted_plan_in <> r6.io.source_completion_plan_copy_out
  r6.io.hot_control_out.ready := true.B
  r6.io.authority_transition_out.ready := true.B
  r6.io.admission_context_out.ready := true.B
  StructuralTieOff.source(r6.io.authority_transition_in)
  StructuralTieOff.source(r6.io.merge_ready_in)
  StructuralTieOff.source(r6.io.hot_source_release_in)
  StructuralTieOff.source(r6.io.pending_source_release_in)
  r6.io.packed_source_release_in <> s2.io.s2_release_out
  StructuralTieOff.sink(r6.io.s2_service_req)
  StructuralTieOff.sink(r6.io.direct_pending_open)
  StructuralTieOff.sink(r6.io.metadata_publish_req)
  StructuralTieOff.source(r6.io.metadata_publish_ack_in)

  r5.io.mem_init_done := r1.io.r1_init_complete
  r5.io.drain_collection_enable := r6.io.drain_collection_enable
  r5.io.reclaim_permit_in <> r6.io.reclaim_permit_out
  r6.io.r5_reclaim_complete_in := r5.io.reclaim_complete
  r5.io.allocator_release_out.ready := true.B
  r5.io.page_allocation_req_in <> io.allocation
  r5.io.page_allocation_rsp.ready := true.B
  r5.io.descriptor_maintenance_terminal_in <> io.descriptor_terminal
  r5.io.metadata_publish_visibility_in <> io.visibility
  r5.io.metadata_publish_visibility_ack.ready := true.B
  StructuralTieOff.sink(r5.io.append_candidate_out)
  StructuralTieOff.source(r5.io.append_delivery_in)
  StructuralTieOff.source(r5.io.p3_payload_durable_in)
  StructuralTieOff.sink(r5.io.descriptor_durability_prerequisite_out)

  r2.io.candidate_in <> r5.io.reclaim_candidate_out
  StructuralTieOff.source(r2.io.read_candidate_in)
  r2.io.drain_collection_enable := r6.io.drain_collection_enable
  r2.io.reclaim_maintenance_enable := r6.io.reclaim_maintenance_enable
  r5.io.reclaim_delivery_in <> r2.io.source_delivery_out
  r1.io.core_mem_req_in <> r2.io.core_mem_req
  r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
  io.external <> r1.io.external_core_mem_if_v1
  r1.io.r1_drain_permitted := collector.io.r1_drain_permitted

  // Only R3/direct remain intentionally deferred owners in this harness; all
  // other lifecycle facts come from the actual instantiated owner outputs.
  collector.io.status_sources(0) <> r1.io.component_status_out
  collector.io.status_sources(1) <> r2.io.payload_drain_status_out
  collector.io.status_sources(2) <> r2.io.descriptor_drain_status_out
  collector.io.status_sources(3) <> io.r3_status
  collector.io.status_sources(4) <> r5.io.component_status_out
  collector.io.status_sources(5) <> s2.io.component_status_out
  collector.io.status_sources(6) <> io.direct_status
  collector.io.status_sources(7) <> merge.io.component_status_out

  s2.io.mem_init_done := r1.io.r1_init_complete
  s2.io.drain_collection_enable := r6.io.drain_collection_enable
  s2.io.service_req_in <> io.s2_service
  s2.io.s2_fill_open_in <> io.s2_fill_open
  s2.io.s2_payload_fragment_in <> io.s2_payload
  StructuralTieOff.source(s2.io.s2_sidecar_fragment_in)
  s2.io.s2_fill_terminal_in <> io.s2_terminal
  StructuralTieOff.source(s2.io.s2_sidecar_complete_in)
  StructuralTieOff.source(s2.io.s2_payload_read_req_in)
  StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
  StructuralTieOff.source(s2.io.s2_sidecar_read_req_in)
  StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
  s2.io.s2_observe_slot := 0.U

  packets.io.hot_available_in.valid := false.B
  packets.io.hot_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  packets.io.hot_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  packets.io.pending_available_in.valid := false.B
  packets.io.pending_available_in.transaction_identity := 0.U.asTypeOf(new TransactionIdentity)
  packets.io.pending_available_in.source_instance := 0.U.asTypeOf(new SourceInstance(p))
  packets.io.packed_available_in.valid := s2.io.s2_observe_available
  packets.io.packed_available_in.transaction_identity := s2.io.s2_observe_identity
  packets.io.packed_available_in.source_instance := s2.io.s2_observe_instance
  StructuralTieOff.source(packets.io.hot_offer_in)
  StructuralTieOff.source(packets.io.pending_offer_in)
  packets.io.packed_offer_in <> io.packed_offer
  StructuralTieOff.source(packets.io.hot_fragment_in)
  StructuralTieOff.source(packets.io.pending_fragment_in)
  packets.io.packed_fragment_in <> io.packed_fragment

  merge.io.drain_collection_enable := r6.io.drain_collection_enable
  StructuralTieOff.source(merge.io.source_partial_in)
  merge.io.r4_partial_header_in <> packets.io.r4_partial_header_out
  merge.io.r4_source_instance_in <> packets.io.r4_source_instance_out
  merge.io.r4_value_fragment_in <> packets.io.r4_value_fragment_out
  merge.io.r4_accepted_partial_packet_out.ready := true.B
  StructuralTieOff.source(merge.io.r4_result_stub_in)
  merge.io.r4_numeric_fault_in <> io.numeric_fault
  merge.io.merge_req_in <> r6.io.merge_req
  r6.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
  s2.io.gqa_consumer_commit_in.valid := merge.io.consumer_partial_commit.valid &&
    merge.io.consumer_partial_commit.bits.source_instance.source_kind === RouteASourceKind.Packed.U
  s2.io.gqa_consumer_commit_in.bits := merge.io.consumer_partial_commit.bits
  merge.io.consumer_partial_commit.ready := s2.io.gqa_consumer_commit_in.ready
}

/** RTL2.6.5b no-model terminal/reclaim composition evidence. */
final class RouteARTL265bTerminalReclaimSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=8, coreMemoryFragmentCountWidth=3, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=1, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def id(x: TransactionIdentity, request: Int): Unit = { x.request_id.poke(request.U); x.incarnation.poke(0.U) }
  private def instance(x: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = { x.source_kind.poke(kind.U); x.instance_coordinate.poke(coordinate.U); x.generation.poke(generation.U) }
  private def init(d: RouteARTL265bTerminalReclaimHarness): Unit = {
    d.io.frontend.valid.poke(false.B); d.io.r3_status.valid.poke(false.B); d.io.direct_status.valid.poke(false.B); d.io.runtime_retire.valid.poke(false.B); d.io.attention_terminal.ready.poke(false.B); d.io.retire_ack.ready.poke(false.B)
    d.io.allocation.valid.poke(false.B); d.io.descriptor_terminal.valid.poke(false.B); d.io.visibility.valid.poke(false.B)
    d.io.source_plan.valid.poke(false.B); d.io.s2_service.valid.poke(false.B); d.io.s2_fill_open.valid.poke(false.B); d.io.s2_payload.valid.poke(false.B); d.io.s2_terminal.valid.poke(false.B); d.io.packed_offer.valid.poke(false.B); d.io.packed_fragment.valid.poke(false.B); d.io.numeric_fault.valid.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B); d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B)
    id(d.io.external.response.bits.transaction_identity, 0); d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B); d.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.external.response.bits.data.poke(0.U)
    d.io.r3_status.bits.acknowledgement_name.poke(0.U); d.io.r3_status.bits.asserted.poke(true.B); d.io.direct_status.bits.acknowledgement_name.poke(0.U); d.io.direct_status.bits.asserted.poke(true.B)
  }
  private def externalStatus(d: RouteARTL265bTerminalReclaimHarness, r3: Boolean, code: Int): Unit = {
    val status = if (r3) d.io.r3_status else d.io.direct_status
    status.bits.acknowledgement_name.poke(code.U); status.bits.asserted.poke(true.B); status.valid.poke(true.B)
    var waited = 0; while (!status.ready.peek().litToBoolean && waited < 64) { d.clock.step(); waited += 1 }
    require(waited < 64, s"timed out waiting for external status $code")
    d.clock.step(); status.valid.poke(false.B); d.clock.step()
  }
  private def frontend(d: RouteARTL265bTerminalReclaimHarness, event: Int, request: Int): Unit = {
    val x=d.io.frontend.bits; x.event_kind.poke(event.U); x.session_id.poke(false.B); x.context_tokens.poke(32768.U); x.entry_id.poke(0.U); x.layer.poke(0.U); x.kv_head.poke(0.U); x.logical_position.poke(0.U); x.payload_ref.poke(0.U); x.disposition.poke(false.B); id(x.transaction_identity,request); x.admission_group_tag.poke(0.U); x.admission_member_ordinal.poke(0.U); x.admission_group_valid_records.poke(1.U)
    d.io.frontend.valid.poke(true.B); var waited=0; while(!d.io.frontend.ready.peek().litToBoolean && waited<64){d.clock.step();waited+=1}; require(waited<64,"timed out waiting for frontend")
    d.clock.step(); d.io.frontend.valid.poke(false.B)
  }
  private def initializeAndStart(d: RouteARTL265bTerminalReclaimHarness): Unit = {
    d.io.external.init_ack.valid.poke(true.B); d.io.external.init_ack.ready.expect(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B); d.clock.step(3)
    externalStatus(d, r3=true, p.r6.m2P3InitDoneStatusCode)
    frontend(d,p.r6.sessionStartEventCode,0)
  }
  private def publishPage(d: RouteARTL265bTerminalReclaimHarness): Unit = {
    val a=d.io.allocation.bits; a.layer.poke(0.U); a.kv_head.poke(0.U); a.valid_records.poke(1.U); a.transaction_group_tag.poke(1.U); d.io.allocation.valid.poke(true.B); d.io.allocation.ready.expect(true.B); d.clock.step(); d.io.allocation.valid.poke(false.B)
    val t=d.io.descriptor_terminal.bits; t.kind.poke(RouteADescriptorOperationKind.NewPage.U); t.page_ref.page_id.poke(0.U); t.page_ref.generation.poke(0.U); t.transaction_group_tag.poke(1.U); t.status.poke(p.coreMemoryOkStatusCode.U); t.r1_descriptor_durable.poke(true.B); d.io.descriptor_terminal.valid.poke(true.B); d.io.descriptor_terminal.ready.expect(true.B); d.clock.step(); d.io.descriptor_terminal.valid.poke(false.B)
    val v=d.io.visibility.bits; v.page_ref.page_id.poke(0.U); v.page_ref.generation.poke(0.U); v.transaction_group_tag.poke(1.U); d.io.visibility.valid.poke(true.B); d.io.visibility.ready.expect(true.B); d.clock.step(); d.io.visibility.valid.poke(false.B); d.clock.step()
  }
  private def fillAndTerminate(d: RouteARTL265bTerminalReclaimHarness, request: Int): Unit = {
    frontend(d,p.r6.attentionServiceEventCode,request)
    val s=d.io.s2_service.bits; id(s.transaction_identity,request); s.page_ref.page_id.poke(0.U); s.page_ref.generation.poke(0.U); s.s2_slot.poke(0.U); d.io.s2_service.valid.poke(true.B); d.io.s2_service.ready.expect(true.B); d.clock.step(); d.io.s2_service.valid.poke(false.B)
    val o=d.io.s2_fill_open.bits; id(o.transaction_identity,request); o.page_ref.page_id.poke(0.U); o.page_ref.generation.poke(0.U); o.s2_slot.poke(0.U); o.source_generation.poke(1.U); o.expected_fragment_count.poke(1.U); o.expected_sidecar_records.poke(0.U); o.requires_sidecar.poke(false.B); d.io.s2_fill_open.valid.poke(true.B); d.io.s2_fill_open.ready.expect(true.B); d.clock.step(); d.io.s2_fill_open.valid.poke(false.B)
    val q=d.io.s2_payload.bits; id(q.transaction_identity,request); q.s2_slot.poke(0.U); q.source_generation.poke(1.U); q.fragment_index.poke(0.U); q.last.poke(true.B); q.data.poke(0.U); d.io.s2_payload.valid.poke(true.B); d.io.s2_payload.ready.expect(true.B); d.clock.step(); d.io.s2_payload.valid.poke(false.B)
    val t=d.io.s2_terminal.bits; id(t.transaction_identity,request); t.s2_slot.poke(0.U); t.source_generation.poke(1.U); t.fragment_index.poke(0.U); t.last.poke(true.B); t.status.poke(p.coreMemoryOkStatusCode.U); d.io.s2_terminal.valid.poke(true.B); d.io.s2_terminal.ready.expect(true.B); d.clock.step(); d.io.s2_terminal.valid.poke(false.B)
    val plan=d.io.source_plan.bits; id(plan.transaction_identity,request); plan.source_presence.poke(4.U); instance(plan.hot_instance,0,0,0); instance(plan.pending_instance,1,0,0); instance(plan.packed_instance,2,0,1); d.io.source_plan.valid.poke(true.B); d.io.source_plan.ready.expect(true.B); d.clock.step(); d.io.source_plan.valid.poke(false.B); d.clock.step()
    (0 until 4).foreach { consumer =>
      val header=(BigInt(2)<<64)|(BigInt(consumer)<<66)|(BigInt(1)<<69)|(BigInt(8)<<70)
      val offer=d.io.packed_offer.bits; id(offer.transaction_identity,request); instance(offer.source_instance,2,0,1); offer.consumer_id.poke(consumer.U); offer.r4_header.poke(header.U); offer.partial_present.poke(true.B); d.io.packed_offer.valid.poke(true.B); d.io.packed_offer.ready.expect(true.B); d.clock.step(); d.io.packed_offer.valid.poke(false.B); d.clock.step()
      (0 until 8).foreach { index => val f=d.io.packed_fragment.bits; id(f.transaction_identity,request); instance(f.source_instance,2,0,1); f.consumer_id.poke(consumer.U); f.fragment_index.poke(index.U); f.last.poke((index==7).B); f.data.poke((consumer*8+index).U); d.io.packed_fragment.valid.poke(true.B); d.io.packed_fragment.ready.expect(true.B); d.clock.step(); d.io.packed_fragment.valid.poke(false.B) }
      d.clock.step(2)
    }
    id(d.io.numeric_fault.bits.transaction_identity,request); d.io.numeric_fault.valid.poke(true.B); var waited=0; while(!d.io.numeric_fault.ready.peek().litToBoolean && waited<64){d.clock.step();waited+=1}; require(waited<64,"timed out waiting for numeric fault"); d.clock.step(); d.io.numeric_fault.valid.poke(false.B)
    waited=0; while(!d.io.attention_terminal.valid.peek().litToBoolean && waited<64){d.clock.step();waited+=1}; require(waited<64,"timed out waiting for terminal"); d.io.attention_terminal.bits.transaction_identity.request_id.expect(request.U); d.io.attention_terminal.ready.poke(true.B); d.clock.step(); d.io.attention_terminal.ready.poke(false.B)
  }
  private def retire(d: RouteARTL265bTerminalReclaimHarness, request: Int): Unit = {
    d.io.runtime_retire.bits.session_id.poke(false.B); id(d.io.runtime_retire.bits.transaction_identity,request); d.io.runtime_retire.valid.poke(true.B); var waited=0; while(!d.io.runtime_retire.ready.peek().litToBoolean && waited<64){d.clock.step();waited+=1}; require(waited<64,"timed out waiting for matched runtime retire"); d.clock.step(); d.io.runtime_retire.valid.poke(false.B)
  }
  private def reclaimRequest(d: RouteARTL265bTerminalReclaimHarness): Unit = {
    var waited=0; while(!d.io.external.request.valid.peek().litToBoolean && waited<256){d.clock.step();waited+=1}; require(waited<256,"timed out waiting for reclaim request")
    d.io.external.request.bits.request_kind.expect(p.coreMemoryWriteRequestCode.U); d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B)
    waited=0; while(!d.io.external.request.valid.peek().litToBoolean && waited<128){d.clock.step();waited+=1}; require(waited<128,"timed out waiting for reclaim data")
    d.io.external.request.bits.request_kind.expect(p.coreMemoryWriteDataCode.U); d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B)
  }
  private def reclaimTerminal(d: RouteARTL265bTerminalReclaimHarness, fault: Boolean): Unit = {
    id(d.io.external.response.bits.transaction_identity,0); d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B); d.io.external.response.bits.status.poke((if(fault) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U); d.io.external.response.valid.poke(true.B); var waited=0; while(!d.io.external.response.ready.peek().litToBoolean && waited<64){d.clock.step();waited+=1}; require(waited<64,"timed out waiting for reclaim terminal"); d.clock.step(); d.io.external.response.valid.poke(false.B)
  }

  it("requires an accepted terminal and matching retire identity before real R5 durable reclaim reaches retire acknowledgement") {
    simulate(new RouteARTL265bTerminalReclaimHarness(p)) { d =>
      init(d); initializeAndStart(d); publishPage(d); fillAndTerminate(d,request=3)
      d.io.runtime_retire.bits.session_id.poke(false.B); id(d.io.runtime_retire.bits.transaction_identity,2); d.io.runtime_retire.valid.poke(true.B); d.io.runtime_retire.ready.expect(false.B); d.io.runtime_retire.valid.poke(false.B)
      retire(d,3)
      externalStatus(d,r3=true,p.r6.r3M2P3DrainedStatusCode); externalStatus(d,r3=false,p.r6.directPendingDrainedStatusCode)
      reclaimRequest(d); reclaimTerminal(d,fault=false)
      var waited=0; while(!d.io.retire_ack.valid.peek().litToBoolean && waited<256){d.clock.step();waited+=1}; require(waited<256,"timed out waiting for retire ack")
      d.io.retire_ack.bits.transaction_identity.request_id.expect(3.U); d.io.retire_ack.ready.poke(true.B); d.clock.step(); d.io.retire_ack.ready.poke(false.B)
    }
  }

  it("keeps retirement incomplete when the matching R1 reclaim terminal faults") {
    simulate(new RouteARTL265bTerminalReclaimHarness(p)) { d =>
      init(d); initializeAndStart(d); publishPage(d); fillAndTerminate(d,request=3); retire(d,3)
      externalStatus(d,r3=true,p.r6.r3M2P3DrainedStatusCode); externalStatus(d,r3=false,p.r6.directPendingDrainedStatusCode)
      reclaimRequest(d); reclaimTerminal(d,fault=true); d.clock.step(8)
      d.io.retire_ack.valid.expect(false.B)
    }
  }
}
