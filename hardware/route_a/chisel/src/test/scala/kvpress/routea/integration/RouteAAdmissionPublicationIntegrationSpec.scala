package kvpress.routea.integration

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAM2P3Wrapper}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAM2GroupMember, RouteAPublicationStatus, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Test-only composition of the exact I2 R6--R3 carrier edges.  The P3/M2
  * ingress is deliberately exposed as a stimulus: production top integration
  * still awaits the later R2/R1/P3 producer path.
  */
private final class RouteAAdmissionPublicationHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val lifecycle_status = Flipped(RouteAChannels.component_status(p))
    val p3_claim = Flipped(RouteAChannels.p3_claim(p))
    val p3_fragment = Flipped(RouteAChannels.p3_pending_fragment(p))
    val p3_sidecar = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val p3_write_issue = Flipped(RouteAChannels.p3_packed_write_issue(p))
    val p3_write_terminal = Flipped(RouteAChannels.p3_packed_write_terminal(p))
    val m2_member = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val m2_publish = Flipped(RouteAChannels.metadata_publish_req(p))
    val visibility_ack = Flipped(RouteAChannels.metadata_publish_visibility_ack)
    val visibility_apply_ready = Input(Bool())
    val commit_observation = RouteAChannels.publication_commit_observation(p)
    val member_observation = RouteAChannels.publication_member_observation(p)
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val r3 = Module(new RouteAM2P3Wrapper(p))
  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.component_status_in <> io.lifecycle_status
  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.attention_terminal_rsp)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  lifecycle.io.hot_control_out.ready := true.B
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.merge_req)
  StructuralTieOff.source(lifecycle.io.merge_terminal_in)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)

  r3.io.mem_init_done := io.mem_init_done
  r3.io.drain_collection_enable := false.B
  r3.io.p3_claim_in <> io.p3_claim
  StructuralTieOff.sink(r3.io.p3_claim_ack)
  r3.io.p3_pending_fragment_in <> io.p3_fragment
  r3.io.p3_sidecar_bind_in <> io.p3_sidecar
  r3.io.p3_packed_write_issue_in <> io.p3_write_issue
  r3.io.p3_packed_write_terminal_in <> io.p3_write_terminal
  r3.io.m2_group_member_rsp_in <> io.m2_member
  r3.io.p3_observe_layer := 0.U
  r3.io.m2_publish_req_in <> io.m2_publish
  r3.io.metadata_publish_visibility_apply.ready := io.visibility_apply_ready
  r3.io.metadata_publish_visibility_ack_in <> io.visibility_ack
  lifecycle.io.metadata_publish_ack_in <> r3.io.m2_publish_ack
  StructuralTieOff.sink(r3.io.component_status_out)

  val r6ToPending = lifecycle.io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Hot.U &&
    lifecycle.io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Pending.U
  r3.io.admission_authority_in.valid := lifecycle.io.authority_transition_out.valid && r6ToPending
  r3.io.admission_authority_in.bits := lifecycle.io.authority_transition_out.bits
  lifecycle.io.authority_transition_out.ready := Mux(r6ToPending, r3.io.admission_authority_in.ready, true.B)
  r3.io.admission_context_in <> lifecycle.io.admission_context_out
  lifecycle.io.authority_transition_in <> r3.io.authority_transition_out
  io.commit_observation <> r3.io.publication_commit_observation
  io.member_observation <> r3.io.publication_member_observation
}

/** RTL1-I2 cross-owner directed control check; no payload/HBM/controller/PPA model. */
final class RouteAAdmissionPublicationIntegrationSpec extends AnyFunSpec with ChiselSim {
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

  private def clearIngress(dut: RouteAAdmissionPublicationHarness): Unit = {
    dut.io.frontend.valid.poke(false.B); dut.io.lifecycle_status.valid.poke(false.B)
    dut.io.p3_claim.valid.poke(false.B); dut.io.p3_fragment.valid.poke(false.B); dut.io.p3_sidecar.valid.poke(false.B)
    dut.io.p3_write_issue.valid.poke(false.B); dut.io.p3_write_terminal.valid.poke(false.B); dut.io.m2_member.valid.poke(false.B)
    dut.io.m2_publish.valid.poke(false.B); dut.io.visibility_ack.valid.poke(false.B)
    dut.io.visibility_apply_ready.poke(true.B); dut.io.commit_observation.ready.poke(true.B); dut.io.member_observation.ready.poke(true.B)
  }

  private def status(dut: RouteAAdmissionPublicationHarness, code: Int): Unit = {
    dut.io.lifecycle_status.bits.acknowledgement_name.poke(code.U); dut.io.lifecycle_status.bits.asserted.poke(true.B)
    dut.io.lifecycle_status.valid.poke(true.B); dut.io.lifecycle_status.ready.expect(true.B); dut.clock.step(); dut.io.lifecycle_status.valid.poke(false.B)
  }

  private def frontend(dut: RouteAAdmissionPublicationHarness, event: Int, retain: Boolean = false): Unit = {
    val in = dut.io.frontend.bits
    in.event_kind.poke(event.U); in.session_id.poke(false.B); in.context_tokens.poke(32768.U)
    in.entry_id.poke(0.U); in.layer.poke(0.U); in.kv_head.poke(0.U); in.logical_position.poke(0.U); in.payload_ref.poke(55.U)
    in.disposition.poke(retain.B); in.transaction_identity.request_id.poke(0.U); in.transaction_identity.incarnation.poke(0.U)
    in.admission_group_tag.poke(1.U); in.admission_member_ordinal.poke(0.U); in.admission_group_valid_records.poke(1.U)
    dut.io.frontend.valid.poke(true.B); dut.io.frontend.ready.expect(true.B); dut.clock.step(); dut.io.frontend.valid.poke(false.B)
  }

  it("carries one retained maturity through R6/R3 and reports packed authority only after publication") {
    simulate(new RouteAAdmissionPublicationHarness(p)) { dut =>
      clearIngress(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step()
      Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(dut, _))
      frontend(dut, p.r6.sessionStartEventCode)
      val claim = dut.io.p3_claim.bits
      claim.layer.poke(0.U); claim.kv_head.poke(0.U); claim.owner.poke(0.U); claim.page_ref.page_id.poke(0.U); claim.page_ref.generation.poke(0.U)
      claim.valid_records.poke(1.U); claim.transaction_group_tag.poke(1.U); dut.io.p3_claim.valid.poke(true.B); dut.io.p3_claim.ready.expect(true.B); dut.clock.step(); dut.io.p3_claim.valid.poke(false.B); dut.clock.step()
      frontend(dut, p.r6.maturityDispositionEventCode, retain = true)
      val fragment = dut.io.p3_fragment.bits
      fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.status.poke(p.coreMemoryOkStatusCode.U)
      for (index <- 0 until 8) { fragment.fragment_index.poke(index.U); fragment.last.poke((index == 7).B); dut.io.p3_fragment.valid.poke(true.B); dut.io.p3_fragment.ready.expect(true.B); dut.clock.step() }
      dut.io.p3_fragment.valid.poke(false.B)
      dut.io.p3_sidecar.bits.layer.poke(0.U); dut.io.p3_sidecar.bits.stage_generation.poke(1.U); dut.io.p3_sidecar.bits.record_ordinal.poke(0.U); dut.io.p3_sidecar.valid.poke(true.B); dut.io.p3_sidecar.ready.expect(true.B); dut.clock.step(); dut.io.p3_sidecar.valid.poke(false.B)
      dut.io.p3_write_issue.bits.layer.poke(0.U); dut.io.p3_write_issue.bits.stage_generation.poke(1.U); dut.io.p3_write_issue.bits.transaction_group_tag.poke(1.U); dut.io.p3_write_issue.valid.poke(true.B); dut.io.p3_write_issue.ready.expect(true.B); dut.clock.step(); dut.io.p3_write_issue.valid.poke(false.B)
      dut.io.p3_write_terminal.bits.layer.poke(0.U); dut.io.p3_write_terminal.bits.stage_generation.poke(1.U); dut.io.p3_write_terminal.bits.transaction_group_tag.poke(1.U); dut.io.p3_write_terminal.bits.status.poke(p.coreMemoryOkStatusCode.U); dut.io.p3_write_terminal.bits.r1_payload_durable.poke(true.B); dut.io.p3_write_terminal.valid.poke(true.B); dut.io.p3_write_terminal.ready.expect(true.B); dut.clock.step(); dut.io.p3_write_terminal.valid.poke(false.B)
      for (member <- Seq(RouteAM2GroupMember.HeadControlRmw, RouteAM2GroupMember.SpanOwnerRmw)) { dut.io.m2_member.bits.layer.poke(0.U); dut.io.m2_member.bits.stage_generation.poke(1.U); dut.io.m2_member.bits.transaction_group_tag.poke(1.U); dut.io.m2_member.bits.member.poke(member.U); dut.io.m2_member.bits.status.poke(p.coreMemoryOkStatusCode.U); dut.io.m2_member.valid.poke(true.B); dut.io.m2_member.ready.expect(true.B); dut.clock.step(); dut.io.m2_member.valid.poke(false.B) }
      dut.io.m2_publish.bits.transaction_group_tag.poke(1.U); dut.io.m2_publish.bits.p3_layer.poke(0.U); dut.io.m2_publish.bits.p3_stage_generation.poke(1.U); dut.io.m2_publish.valid.poke(true.B); dut.io.m2_publish.ready.expect(true.B); dut.clock.step(); dut.io.m2_publish.valid.poke(false.B)
      dut.io.visibility_ack.bits.page_ref.page_id.poke(0.U); dut.io.visibility_ack.bits.page_ref.generation.poke(0.U); dut.io.visibility_ack.bits.status.poke(RouteAPublicationStatus.Published.U)
      dut.io.visibility_ack.valid.poke(true.B); dut.clock.step(); dut.io.visibility_ack.ready.expect(true.B); dut.clock.step(); dut.io.visibility_ack.valid.poke(false.B)
      dut.clock.step() // lifecycle consumes the existing R3 publish acknowledgement.
      dut.io.commit_observation.valid.expect(true.B); dut.io.commit_observation.bits.valid_records.expect(1.U); dut.clock.step()
      dut.io.member_observation.valid.expect(true.B); dut.io.member_observation.bits.entry_id.expect(0.U); dut.io.member_observation.bits.payload_ref.expect(55.U)
      dut.clock.step(); dut.io.member_observation.valid.expect(false.B)
    }
  }
}
