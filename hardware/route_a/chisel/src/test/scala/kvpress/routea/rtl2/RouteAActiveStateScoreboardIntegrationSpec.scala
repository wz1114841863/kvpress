package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.Decoupled
import kvpress.routea.integration.RouteARetirementDrainClosureHarness
import kvpress.routea.incremental.RouteAPageManager
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** Actual R5 release-carrier composition for RTL2.5.5-I only. */
private final class RouteAR5ScoreboardBindingHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool()); val reclaim_permit = Flipped(RouteAChannels.reclaim_permit)
    val allocation = Flipped(RouteAChannels.page_allocation_req(p)); val allocation_rsp = RouteAChannels.page_allocation_rsp(p)
    val descriptor_terminal = Flipped(RouteAChannels.descriptor_maintenance_terminal(p))
    val visibility = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val reclaim_candidate = RouteAChannels.source_candidate(p); val reclaim_delivery = Flipped(RouteAChannels.source_delivery(p))
    val descriptor_event = Decoupled(new DescriptorInvalidateScoreboardEvent(p)); val page_free_event = Decoupled(new PageFreeScoreboardEvent)
  })
  val r5 = Module(new RouteAPageManager(p)); val adapter = Module(new RouteAReclaimScoreboardAdapter(p))
  r5.io.mem_init_done := io.mem_init_done; r5.io.drain_collection_enable := false.B
  r5.io.reclaim_permit_in <> io.reclaim_permit; r5.io.page_allocation_req_in <> io.allocation; io.allocation_rsp <> r5.io.page_allocation_rsp
  r5.io.descriptor_maintenance_terminal_in <> io.descriptor_terminal; r5.io.metadata_publish_visibility_in <> io.visibility
  r5.io.metadata_publish_visibility_ack.ready := true.B; io.reclaim_candidate <> r5.io.reclaim_candidate_out; r5.io.reclaim_delivery_in <> io.reclaim_delivery
  StructuralTieOff.sink(r5.io.append_candidate_out); StructuralTieOff.source(r5.io.append_delivery_in); StructuralTieOff.source(r5.io.p3_payload_durable_in)
  StructuralTieOff.sink(r5.io.descriptor_durability_prerequisite_out); r5.io.component_status_out.ready := true.B
  adapter.io.allocator_release_in <> r5.io.allocator_release_out; adapter.io.allocator_release_out.ready := true.B
  io.descriptor_event <> adapter.io.descriptor_invalidate_event_out; io.page_free_event <> adapter.io.page_free_event_out
  StructuralTieOff.source(adapter.io.retire_ack_in); adapter.io.retire_ack_out.ready := true.B; adapter.io.retire_ack_event_out.ready := true.B
}

/** Actual R6 plus the fixed-membership collector feeding the observation adapter. */
private final class RouteAR6ScoreboardBindingHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p)); val retire = Flipped(RouteAChannels.runtime_retire_req)
    val status_sources = Flipped(Vec(8, RouteAChannels.component_status(p))); val r5_reclaim_complete = Input(Bool())
    val reclaim_permit = RouteAChannels.reclaim_permit; val retire_ack = RouteAChannels.session_retire_ack
    val retire_ack_event = Decoupled(new RetireAckScoreboardEvent)
  })
  val r6 = Module(new RouteARetirementDrainClosureHarness(p)); val adapter = Module(new RouteAReclaimScoreboardAdapter(p))
  r6.io.frontend <> io.frontend; r6.io.retire <> io.retire; r6.io.status_sources <> io.status_sources; r6.io.r5_reclaim_complete := io.r5_reclaim_complete; io.reclaim_permit <> r6.io.reclaim_permit
  adapter.io.retire_ack_in <> r6.io.retire_ack; io.retire_ack <> adapter.io.retire_ack_out; io.retire_ack_event <> adapter.io.retire_ack_event_out
  StructuralTieOff.source(adapter.io.allocator_release_in); adapter.io.allocator_release_out.ready := true.B; adapter.io.descriptor_invalidate_event_out.ready := true.B; adapter.io.page_free_event_out.ready := true.B
}

/** RTL2.5.5-I: real R5 carrier -> adapter; no allocator implementation claim. */
final class RouteAActiveStateScoreboardIntegrationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3,candidateOrdinalWidth=4,candidateIdWidth=4,candidatePredicateWidth=10,r2S2FullClassCode=0,r2S2PackedClassCode=1,r2DirectPendingClassCode=2,r2PackReadClassCode=3,r2PackWriteClassCode=4,r2DescriptorMaintenanceClassCode=5,r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3,coreMemoryDestinationWidth=2,coreMemoryAddressRefWidth=8,coreMemoryFragmentCountWidth=3,coreMemoryFragmentIndexWidth=3,coreMemoryReadRequestCode=0,coreMemoryWriteRequestCode=1,coreMemoryWriteDataCode=2,coreMemoryOkStatusCode=0,coreMemoryFaultStatusCode=1,sourceDeliveryOpaqueWidth=1,transactionGroupTagWidth=2,p3StageGenerationWidth=2,r5AllocatorEntries=8,r5StreamSlots=8,sourceGenerationWidth=2,r6=RouteAR6Encoding.testOnlyAnchor)
  private def init(d: RouteAR5ScoreboardBindingHarness): Unit = {
    d.io.mem_init_done.poke(false.B); d.io.reclaim_permit.valid.poke(false.B); d.io.allocation.valid.poke(false.B); d.io.descriptor_terminal.valid.poke(false.B); d.io.visibility.valid.poke(false.B); d.io.reclaim_delivery.valid.poke(false.B)
    d.io.allocation_rsp.ready.poke(true.B); d.io.visibility.bits.page_ref.page_id.poke(0.U); d.io.visibility.bits.page_ref.generation.poke(0.U); d.io.visibility.bits.transaction_group_tag.poke(1.U)
    d.io.reclaim_candidate.ready.poke(true.B); d.io.descriptor_event.ready.poke(false.B); d.io.page_free_event.ready.poke(false.B)
    d.io.reclaim_permit.bits.transaction_identity.request_id.poke(0.U); d.io.reclaim_permit.bits.transaction_identity.incarnation.poke(0.U); d.io.mem_init_done.poke(true.B); d.clock.step(2)
  }
  private def publish(d: RouteAR5ScoreboardBindingHarness): Unit = {
    d.io.allocation.bits.layer.poke(0.U); d.io.allocation.bits.kv_head.poke(0.U); d.io.allocation.bits.valid_records.poke(1.U); d.io.allocation.bits.transaction_group_tag.poke(1.U); d.io.allocation.valid.poke(true.B); d.io.allocation.ready.expect(true.B); d.clock.step(); d.io.allocation.valid.poke(false.B)
    val t=d.io.descriptor_terminal.bits; t.kind.poke(RouteADescriptorOperationKind.NewPage.U); t.page_ref.page_id.poke(0.U); t.page_ref.generation.poke(0.U); t.transaction_group_tag.poke(1.U); t.status.poke(p.coreMemoryOkStatusCode.U); t.r1_descriptor_durable.poke(true.B); d.io.descriptor_terminal.valid.poke(true.B); d.io.descriptor_terminal.ready.expect(true.B); d.clock.step(); d.io.descriptor_terminal.valid.poke(false.B)
    d.io.visibility.valid.poke(true.B); d.io.visibility.ready.expect(true.B); d.clock.step(); d.io.visibility.valid.poke(false.B); d.clock.step()
  }
  private def startReclaim(d: RouteAR5ScoreboardBindingHarness): Unit = {
    d.io.reclaim_permit.valid.poke(true.B); d.io.reclaim_permit.ready.expect(true.B); d.clock.step(); d.io.reclaim_permit.valid.poke(false.B); d.clock.step(1)
    d.io.reclaim_candidate.bits.r1_request.request_kind.expect(p.coreMemoryWriteRequestCode.U); d.clock.step(); d.io.reclaim_candidate.bits.r1_request.request_kind.expect(p.coreMemoryWriteDataCode.U); d.clock.step()
  }
  private def terminal(d: RouteAR5ScoreboardBindingHarness): Unit = {
    val r=d.io.reclaim_delivery.bits; r.candidate_id.poke(0.U); r.candidate_class.poke(p.r2DescriptorMaintenanceClassCode.U); r.destination.poke(0.U); r.delivery_context_ref.poke(0.U); r.r1_response.transaction_identity.request_id.poke(0.U); r.r1_response.transaction_identity.incarnation.poke(0.U); r.r1_response.fragment_index.poke(0.U); r.r1_response.last.poke(true.B); r.r1_response.status.poke(p.coreMemoryOkStatusCode.U); r.r1_response.data.poke(0.U)
    d.io.reclaim_delivery.valid.poke(true.B); d.io.reclaim_delivery.ready.expect(true.B); d.clock.step(); d.io.reclaim_delivery.valid.poke(false.B)
  }
  it("carries the real R5 old PageRef atomically into both events and reset drops a blocked observation") {
    simulate(new RouteAR5ScoreboardBindingHarness(p)) { d =>
      init(d); publish(d); startReclaim(d); terminal(d)
      d.io.descriptor_event.valid.expect(false.B); d.io.page_free_event.valid.expect(false.B)
      d.io.descriptor_event.ready.poke(true.B); d.io.page_free_event.ready.poke(true.B)
      d.io.descriptor_event.valid.expect(true.B); d.io.page_free_event.valid.expect(true.B); d.io.descriptor_event.bits.page_ref.page_id.expect(0.U); d.io.descriptor_event.bits.page_ref.generation.expect(0.U); d.io.descriptor_event.bits.descriptor_operation.expect(RouteADescriptorOperationKind.Invalidate.U); d.io.page_free_event.bits.page_ref.page_id.expect(0.U); d.clock.step()
      d.io.descriptor_event.ready.poke(false.B); d.io.page_free_event.ready.poke(false.B); d.reset.poke(true.B); d.clock.step(); d.reset.poke(false.B)
      d.io.descriptor_event.valid.expect(false.B); d.io.page_free_event.valid.expect(false.B)
    }
  }

  private val R1=0; private val R2Payload=1; private val R2Descriptor=2; private val R3=3; private val R5=4; private val S2=5; private val Direct=6; private val R4=7
  private def driveR6Zero(d: RouteAR6ScoreboardBindingHarness): Unit = { val f=d.io.frontend.bits; f.event_kind.poke(0.U); f.session_id.poke(false.B); f.context_tokens.poke(0.U); f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U); f.payload_ref.poke(0.U); f.disposition.poke(false.B); f.transaction_identity.request_id.poke(0.U); f.transaction_identity.incarnation.poke(0.U); f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(0.U) }
  private def status(d: RouteAR6ScoreboardBindingHarness, source:Int, code:Int): Unit = { d.io.status_sources(source).bits.acknowledgement_name.poke(code.U); d.io.status_sources(source).bits.asserted.poke(true.B); d.io.status_sources(source).valid.poke(true.B); d.io.status_sources(source).ready.expect(true.B); d.clock.step(); d.io.status_sources(source).valid.poke(false.B); d.clock.step() }
  private def initR6(d: RouteAR6ScoreboardBindingHarness): Unit = { driveR6Zero(d); d.io.frontend.valid.poke(false.B); d.io.retire.valid.poke(false.B); d.io.retire.bits.session_id.poke(false.B); d.io.retire.bits.transaction_identity.request_id.poke(0.U); d.io.retire.bits.transaction_identity.incarnation.poke(0.U); (0 until 8).foreach(i => { d.io.status_sources(i).valid.poke(false.B); d.io.status_sources(i).bits.acknowledgement_name.poke(0.U); d.io.status_sources(i).bits.asserted.poke(true.B) }); d.io.r5_reclaim_complete.poke(false.B); d.io.reclaim_permit.ready.poke(false.B); d.io.retire_ack.ready.poke(false.B); d.io.retire_ack_event.ready.poke(false.B) }
  it("carries the real R6 fixed-membership acknowledgement atomically into retire_ack event") {
    simulate(new RouteAR6ScoreboardBindingHarness(p)) { d =>
      initR6(d); status(d,R1,p.r6.memInitDoneStatusCode); status(d,R3,p.r6.m2P3InitDoneStatusCode); status(d,R5,p.r6.pageManagerInitDoneStatusCode)
      d.io.frontend.bits.event_kind.poke(p.r6.sessionStartEventCode.U); d.io.frontend.bits.context_tokens.poke(32768.U); d.io.frontend.valid.poke(true.B); d.io.frontend.ready.expect(true.B); d.clock.step(); d.io.frontend.valid.poke(false.B)
      d.io.retire.bits.transaction_identity.request_id.poke(3.U); d.io.retire.bits.transaction_identity.incarnation.poke(1.U); d.io.retire.valid.poke(true.B); d.io.retire.ready.expect(true.B); d.clock.step(); d.io.retire.valid.poke(false.B)
      Seq((R2Payload,p.r6.r2PayloadDrainedStatusCode),(R2Descriptor,p.r6.r2DescriptorDrainedStatusCode),(R1,p.r6.r1MemoryDrainedStatusCode),(R3,p.r6.r3M2P3DrainedStatusCode),(S2,p.r6.s2GqaDrainedStatusCode),(Direct,p.r6.directPendingDrainedStatusCode),(R4,p.r6.mergeDrainedStatusCode)).foreach { case (s,c) => status(d,s,c) }; d.clock.step(2)
      d.io.reclaim_permit.valid.expect(true.B); d.io.reclaim_permit.ready.poke(true.B); d.clock.step(); d.io.reclaim_permit.ready.poke(false.B)
      d.io.r5_reclaim_complete.poke(true.B); d.clock.step(); d.io.r5_reclaim_complete.poke(false.B); status(d,R2Descriptor,p.r6.r2DescriptorDrainedStatusCode); status(d,R1,p.r6.r1MemoryDrainedStatusCode); status(d,R5,p.r6.r5PageManagerDrainedStatusCode)
      d.io.retire_ack.valid.expect(false.B); d.io.retire_ack_event.valid.expect(false.B)
      d.io.retire_ack.ready.poke(true.B); d.io.retire_ack_event.ready.poke(true.B); d.io.retire_ack.valid.expect(true.B); d.io.retire_ack_event.valid.expect(true.B); d.io.retire_ack_event.bits.acknowledgement.transaction_identity.request_id.expect(3.U); d.io.retire_ack_event.bits.acknowledgement.transaction_identity.incarnation.expect(1.U); d.clock.step(); d.io.retire_ack.ready.poke(false.B); d.io.retire_ack_event.ready.poke(false.B); d.io.retire_ack.valid.expect(false.B); d.io.retire_ack_event.valid.expect(false.B)
    }
  }
}
