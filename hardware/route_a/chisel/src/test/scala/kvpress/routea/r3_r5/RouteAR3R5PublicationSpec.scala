package kvpress.routea.r3_r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.interfaces.{RouteAChannels, StructuralTieOff}
import kvpress.routea.incremental.{RouteAM2P3Wrapper, RouteAPageManager}
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAM2GroupMember, RouteAPublicationStatus, RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.r5.RouteAReclaimHarness
import org.scalatest.funspec.AnyFunSpec

/**
  * Narrow simulator-facing view of the production R3 owner.
  *
  * The publication checks never observe an R2 candidate or a pack-read issue.
  * Keeping those rich carriers below this probe avoids the remote ChiselSim
  * DPI generator's nested-direct-association limitation without changing R3.
  */
final class RouteAR3PublicationHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val p3_claim_in = Flipped(RouteAChannels.p3_claim(p))
    val p3_claim_ack = RouteAChannels.p3_claim_ack(p)
    val admission_context_in = Flipped(RouteAChannels.admission_context(p))
    val admission_authority_in = Flipped(RouteAChannels.r6_authority_transition(p))
    val pending_payload_binding_in = Flipped(RouteAChannels.pending_payload_read_binding(p))
    val authority_transition_out = RouteAChannels.r6_authority_transition(p)
    val pending_to_packed_withdrawal_valid = Output(Bool())
    val publication_commit_observation = RouteAChannels.publication_commit_observation(p)
    val publication_member_observation = RouteAChannels.publication_member_observation(p)
    val post_r6_packed_page_ready_observation = RouteAChannels.post_r6_packed_page_ready_observation(p)
    val p3_pending_fragment_in = Flipped(RouteAChannels.p3_pending_fragment(p))
    val p3_sidecar_bind_in = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val p3_packed_write_issue_in = Flipped(RouteAChannels.p3_packed_write_issue(p))
    val p3_packed_write_terminal_in = Flipped(RouteAChannels.p3_packed_write_terminal(p))
    // Flattened, simulator-facing probe of the existing R3-owned candidate.
    // Keeping the deep delivery descriptor below this harness avoids the
    // known remote ChiselSim DPI generator defect; this does not alter the
    // production R2/R1 connection in RouteAMeasurementDut.
    val p3_candidate_valid = Output(Bool())
    val p3_candidate_ready = Input(Bool())
    val p3_candidate_request_kind = Output(UInt(p.coreMemoryRequestKindWidth.W))
    val p3_candidate_fragment_index = Output(UInt(p.coreMemoryFragmentIndexWidth.W))
    val p3_candidate_last = Output(Bool())
    val p3_candidate_data = Output(UInt(kvpress.routea.params.RouteAAnchorWidths.CoreDataWidth.W))
    val p3_candidate_id = Output(UInt(p.candidateIdWidth.W))
    val p3_delivery_valid = Input(Bool())
    val p3_delivery_ready = Output(Bool())
    val p3_delivery_candidate_id = Input(UInt(p.candidateIdWidth.W))
    val p3_delivery_status = Input(UInt(kvpress.routea.params.RouteAAnchorWidths.TerminalStatusWidth.W))
    val descriptor_durability_prerequisite_in = Flipped(RouteAChannels.descriptor_durability_prerequisite(p))
    val m2_group_member_req_out = RouteAChannels.m2_group_member_req(p)
    val m2_group_member_rsp_in = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val p3_observe_layer = Input(UInt(kvpress.routea.params.RouteAAnchorWidths.LayerWidth.W))
    val p3_observe_state = Output(UInt(kvpress.routea.params.RouteAAnchorWidths.P3StateWidth.W))
    val p3_observe_generation = Output(UInt(p.p3StageGenerationWidth.W))
    val m2_publish_candidate_out = RouteAChannels.metadata_publish_req(p)
    val m2_publish_req_in = Flipped(RouteAChannels.metadata_publish_req(p))
    val metadata_publish_visibility_apply = RouteAChannels.metadata_publish_visibility(p)
    val metadata_publish_visibility_ack_in = Flipped(RouteAChannels.metadata_publish_visibility_ack)
    val m2_publish_ack = RouteAChannels.metadata_publish_ack(p)
    val component_status_out = RouteAChannels.component_status(p)
  })

  private val r3 = Module(new RouteAM2P3Wrapper(p))
  r3.io.mem_init_done := io.mem_init_done
  r3.io.drain_collection_enable := io.drain_collection_enable
  r3.io.p3_claim_in <> io.p3_claim_in; io.p3_claim_ack <> r3.io.p3_claim_ack
  r3.io.admission_context_in <> io.admission_context_in; r3.io.admission_authority_in <> io.admission_authority_in
  r3.io.pending_payload_binding_in <> io.pending_payload_binding_in
  io.authority_transition_out <> r3.io.authority_transition_out
  io.pending_to_packed_withdrawal_valid := r3.io.pending_to_packed_read_eligibility_withdrawal.valid
  io.publication_commit_observation <> r3.io.publication_commit_observation
  io.publication_member_observation <> r3.io.publication_member_observation
  io.post_r6_packed_page_ready_observation <> r3.io.post_r6_packed_page_ready_observation
  r3.io.p3_pending_fragment_in <> io.p3_pending_fragment_in; r3.io.p3_sidecar_bind_in <> io.p3_sidecar_bind_in
  r3.io.p3_packed_write_issue_in <> io.p3_packed_write_issue_in
  r3.io.p3_packed_write_terminal_in <> io.p3_packed_write_terminal_in
  r3.io.descriptor_durability_prerequisite_in <> io.descriptor_durability_prerequisite_in
  io.m2_group_member_req_out <> r3.io.m2_group_member_req_out; r3.io.m2_group_member_rsp_in <> io.m2_group_member_rsp_in
  r3.io.p3_observe_layer := io.p3_observe_layer; io.p3_observe_state := r3.io.p3_observe_state
  io.p3_observe_generation := r3.io.p3_observe_generation
  io.m2_publish_candidate_out <> r3.io.m2_publish_candidate_out; r3.io.m2_publish_req_in <> io.m2_publish_req_in
  io.metadata_publish_visibility_apply <> r3.io.metadata_publish_visibility_apply
  r3.io.metadata_publish_visibility_ack_in <> io.metadata_publish_visibility_ack_in; io.m2_publish_ack <> r3.io.m2_publish_ack
  io.component_status_out <> r3.io.component_status_out

  StructuralTieOff.source(r3.io.pending_packing_reconciliation_lookup_in)
  StructuralTieOff.sink(r3.io.pending_packing_reconciliation_result_out)
  StructuralTieOff.sink(r3.io.p3_pack_read_materialized_work_out)
  StructuralTieOff.sink(r3.io.p3_materialized_sidecar_out)
  r3.io.p3_pack_read_work_in.valid := false.B
  r3.io.p3_pack_read_work_in.bits := 0.U.asTypeOf(r3.io.p3_pack_read_work_in.bits)
  StructuralTieOff.sink(r3.io.p3_pack_read_issue_out)
  io.p3_candidate_valid := r3.io.p3_packed_write_candidate_out.valid
  r3.io.p3_packed_write_candidate_out.ready := io.p3_candidate_ready
  io.p3_candidate_request_kind := r3.io.p3_packed_write_candidate_out.bits.r1_request.request_kind
  io.p3_candidate_fragment_index := r3.io.p3_packed_write_candidate_out.bits.r1_request.fragment_index
  io.p3_candidate_last := r3.io.p3_packed_write_candidate_out.bits.r1_request.last
  io.p3_candidate_data := r3.io.p3_packed_write_candidate_out.bits.r1_request.data
  io.p3_candidate_id := r3.io.p3_packed_write_candidate_out.bits.candidate_id
  r3.io.p3_packed_write_delivery_in.valid := io.p3_delivery_valid
  r3.io.p3_packed_write_delivery_in.bits := 0.U.asTypeOf(r3.io.p3_packed_write_delivery_in.bits)
  r3.io.p3_packed_write_delivery_in.bits.candidate_class := p.r2PackWriteClassCode.U
  r3.io.p3_packed_write_delivery_in.bits.candidate_id := io.p3_delivery_candidate_id
  r3.io.p3_packed_write_delivery_in.bits.r1_response.status := io.p3_delivery_status
  r3.io.p3_packed_write_delivery_in.bits.r1_response.last := true.B
  io.p3_delivery_ready := r3.io.p3_packed_write_delivery_in.ready
  StructuralTieOff.sink(r3.io.p3_payload_durable_out)
}

/** RTL1.3 directed control-contract checks; no payload macro/controller/PPA model. */
final class RouteAR3R5PublicationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    // The production P3 pack writer emits up to 512 logical fragments.  Its
    // existing legal activation guard requires these anchor widths; using the
    // old 3-bit legacy-direct-test values would correctly keep it fail-closed.
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8,
    r5StreamSlots = 8,
    sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def initR3(dut: RouteAR3PublicationHarness): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.p3_observe_layer.poke(0.U)
    dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.p3_claim_in.valid.poke(false.B); dut.io.p3_claim_ack.ready.poke(true.B)
    dut.io.admission_context_in.valid.poke(false.B); dut.io.admission_authority_in.valid.poke(false.B)
    // This legacy hot-payload-only R3 test intentionally does not authorize a
    // pending-memory pack read.  Keep the RTL3.9-A0 binding ingress inactive.
    dut.io.pending_payload_binding_in.valid.poke(false.B)
    dut.io.authority_transition_out.ready.poke(true.B)
    dut.io.publication_commit_observation.ready.poke(true.B); dut.io.publication_member_observation.ready.poke(true.B)
    dut.io.post_r6_packed_page_ready_observation.ready.poke(true.B)
    dut.io.p3_pending_fragment_in.valid.poke(false.B); dut.io.p3_sidecar_bind_in.valid.poke(false.B)
    dut.io.p3_packed_write_issue_in.valid.poke(false.B); dut.io.p3_packed_write_terminal_in.valid.poke(false.B)
    dut.io.p3_candidate_ready.poke(false.B); dut.io.p3_delivery_valid.poke(false.B)
    dut.io.p3_delivery_candidate_id.poke(0.U); dut.io.p3_delivery_status.poke(p.coreMemoryOkStatusCode.U)
    dut.io.descriptor_durability_prerequisite_in.valid.poke(false.B)
    dut.io.m2_group_member_req_out.ready.poke(false.B)
    dut.io.m2_group_member_rsp_in.valid.poke(false.B); dut.io.m2_publish_req_in.valid.poke(false.B)
    dut.io.m2_publish_candidate_out.ready.poke(false.B)
    dut.io.metadata_publish_visibility_apply.ready.poke(true.B)
    dut.io.metadata_publish_visibility_ack_in.valid.poke(false.B); dut.io.m2_publish_ack.ready.poke(true.B)
    dut.io.mem_init_done.poke(true.B); dut.clock.step()
  }

  private def claimOneRecord(dut: RouteAR3PublicationHarness): Unit = {
    val claim = dut.io.p3_claim_in.bits
    claim.layer.poke(0.U); claim.kv_head.poke(0.U); claim.owner.poke(0.U)
    claim.page_ref.page_id.poke(0.U); claim.page_ref.generation.poke(0.U)
    claim.valid_records.poke(1.U); claim.requires_tail_link.poke(false.B); claim.transaction_group_tag.poke(1.U)
    claim.m2_group_opaque_address_ref.poke("h5a".U); claim.m2_group_owner.poke(6.U)
    dut.io.p3_claim_in.valid.poke(true.B); dut.io.p3_claim_in.ready.expect(true.B); dut.clock.step()
    dut.io.p3_claim_in.valid.poke(false.B); dut.clock.step()
    dut.io.p3_observe_generation.expect(1.U)
    dut.io.p3_observe_state.expect(1.U)
    val context = dut.io.admission_context_in.bits
    context.entry_id.poke(0.U); context.layer.poke(0.U); context.kv_head.poke(0.U); context.logical_position.poke(0.U)
    context.payload_ref.poke(9.U); context.transaction_group_tag.poke(1.U); context.group_member_ordinal.poke(0.U); context.group_valid_records.poke(1.U)
    val authority = dut.io.admission_authority_in.bits
    authority.entry_id.poke(0.U); authority.from_authority.poke(1.U); authority.to_authority.poke(2.U); authority.transaction_group_tag.poke(1.U)
    dut.io.admission_context_in.valid.poke(true.B); dut.io.admission_authority_in.valid.poke(true.B)
    dut.io.admission_context_in.ready.expect(true.B); dut.io.admission_authority_in.ready.expect(true.B)
    dut.clock.step(); dut.io.admission_context_in.valid.poke(false.B); dut.io.admission_authority_in.valid.poke(false.B)
  }

  private def fillOneP3Record(dut: RouteAR3PublicationHarness, base: Int = 0): Unit = {
    val fragment = dut.io.p3_pending_fragment_in.bits
    fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U)
    fragment.status.poke(p.coreMemoryOkStatusCode.U); fragment.payload_ref.poke(9.U)
    for (fragmentIndex <- 0 until 8) {
      fragment.fragment_index.poke(fragmentIndex.U); fragment.last.poke((fragmentIndex == 7).B)
      fragment.data.poke((base + fragmentIndex).U); dut.io.p3_pending_fragment_in.valid.poke(true.B)
      var wait = 0; while (!dut.io.p3_pending_fragment_in.ready.peek().litToBoolean && wait < 8) { dut.clock.step(); wait += 1 }
      require(wait < 8, "timed out waiting for P3 payload-write acceptance")
      dut.clock.step(); dut.io.p3_pending_fragment_in.valid.poke(false.B); dut.clock.step()
    }
    val sidecar = dut.io.p3_sidecar_bind_in.bits
    sidecar.layer.poke(0.U); sidecar.stage_generation.poke(1.U); sidecar.record_ordinal.poke(0.U)
    sidecar.payload_ref.poke(9.U); sidecar.logical_position.poke(0.U); dut.io.p3_sidecar_bind_in.valid.poke(true.B)
    var wait = 0; while (!dut.io.p3_sidecar_bind_in.ready.peek().litToBoolean && wait < 8) { dut.clock.step(); wait += 1 }
    require(wait < 8, "timed out waiting for P3 sidecar-write acceptance")
    dut.clock.step(); dut.io.p3_sidecar_bind_in.valid.poke(false.B); dut.clock.step()
    dut.io.p3_observe_state.expect(3.U)
  }

  private def finishP3AndM2(dut: RouteAR3PublicationHarness): Unit = {
    val fragment = dut.io.p3_pending_fragment_in.bits
    fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.status.poke(p.coreMemoryOkStatusCode.U); fragment.payload_ref.poke(9.U)
    for (fragmentIndex <- 0 until 8) {
      fragment.fragment_index.poke(fragmentIndex.U); fragment.last.poke((fragmentIndex == 7).B); fragment.data.poke(fragmentIndex.U)
      dut.io.p3_pending_fragment_in.valid.poke(true.B)
      var wait = 0; while (!dut.io.p3_pending_fragment_in.ready.peek().litToBoolean && wait < 8) { dut.clock.step(); wait += 1 }
      require(wait < 8, "timed out waiting for P3 payload-write acceptance")
      dut.clock.step(); dut.io.p3_pending_fragment_in.valid.poke(false.B); dut.clock.step()
    }
    dut.io.p3_pending_fragment_in.valid.poke(false.B)
    val sidecar = dut.io.p3_sidecar_bind_in.bits
    sidecar.layer.poke(0.U); sidecar.stage_generation.poke(1.U); sidecar.record_ordinal.poke(0.U); sidecar.payload_ref.poke(9.U); sidecar.logical_position.poke(0.U)
    dut.io.p3_sidecar_bind_in.valid.poke(true.B)
    var sidecarWait = 0; while (!dut.io.p3_sidecar_bind_in.ready.peek().litToBoolean && sidecarWait < 8) { dut.clock.step(); sidecarWait += 1 }
    require(sidecarWait < 8, "timed out waiting for P3 sidecar-write acceptance")
    dut.clock.step(); dut.io.p3_sidecar_bind_in.valid.poke(false.B); dut.clock.step()
    dut.io.p3_packed_write_terminal_in.bits.layer.poke(0.U); dut.io.p3_packed_write_terminal_in.bits.stage_generation.poke(1.U)
    dut.io.p3_packed_write_terminal_in.bits.transaction_group_tag.poke(1.U); dut.io.p3_packed_write_terminal_in.bits.status.poke(p.coreMemoryOkStatusCode.U)
    dut.io.p3_packed_write_terminal_in.bits.r1_payload_durable.poke(true.B)
    dut.io.p3_packed_write_terminal_in.valid.poke(true.B); dut.io.p3_packed_write_terminal_in.ready.expect(false.B); dut.io.p3_packed_write_terminal_in.valid.poke(false.B)
    dut.io.p3_packed_write_issue_in.bits.layer.poke(0.U); dut.io.p3_packed_write_issue_in.bits.stage_generation.poke(1.U); dut.io.p3_packed_write_issue_in.bits.transaction_group_tag.poke(1.U)
    dut.io.p3_packed_write_issue_in.valid.poke(true.B); dut.io.p3_packed_write_issue_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_packed_write_issue_in.valid.poke(false.B)
    dut.io.p3_packed_write_terminal_in.valid.poke(true.B); dut.io.p3_packed_write_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_packed_write_terminal_in.valid.poke(false.B)
    offerDescriptorPrerequisite(dut)
    for (member <- Seq(RouteAM2GroupMember.HeadControlRmw, RouteAM2GroupMember.SpanOwnerRmw)) {
      dut.io.m2_group_member_req_out.valid.expect(true.B)
      dut.io.m2_group_member_req_out.bits.member.expect(member.U)
      dut.io.m2_group_member_req_out.bits.kv_head.expect(0.U)
      dut.io.m2_group_member_req_out.bits.opaque_address_ref.expect("h5a".U)
      dut.io.m2_group_member_req_out.bits.owner.expect(6.U)
      dut.io.m2_group_member_req_out.ready.poke(true.B); dut.clock.step(); dut.io.m2_group_member_req_out.ready.poke(false.B)
      val response = dut.io.m2_group_member_rsp_in.bits
      response.layer.poke(0.U); response.stage_generation.poke(1.U); response.transaction_group_tag.poke(1.U)
      response.member.poke(member.U); response.kv_head.poke(0.U)
      if (member == RouteAM2GroupMember.HeadControlRmw) {
        response.opaque_address_ref.poke("h5a".U); response.owner.poke(5.U); response.status.poke(p.coreMemoryOkStatusCode.U)
        dut.io.m2_group_member_rsp_in.valid.poke(true.B); dut.io.m2_group_member_rsp_in.ready.expect(false.B)
        dut.io.m2_group_member_rsp_in.valid.poke(false.B)
      }
      response.opaque_address_ref.poke("h5a".U); response.owner.poke(6.U); response.status.poke(p.coreMemoryOkStatusCode.U)
      dut.io.m2_group_member_rsp_in.valid.poke(true.B); dut.io.m2_group_member_rsp_in.ready.expect(true.B); dut.clock.step(); dut.io.m2_group_member_rsp_in.valid.poke(false.B)
    }
  }

  private def acceptPublicationCandidate(dut: RouteAR3PublicationHarness): Unit = {
    dut.io.m2_publish_candidate_out.valid.expect(true.B)
    dut.io.m2_publish_candidate_out.bits.transaction_group_tag.expect(1.U)
    dut.io.m2_publish_candidate_out.bits.p3_layer.expect(0.U)
    dut.io.m2_publish_candidate_out.bits.p3_stage_generation.expect(1.U)
    dut.io.m2_publish_candidate_out.ready.poke(true.B); dut.clock.step(); dut.io.m2_publish_candidate_out.ready.poke(false.B)
  }

  private def offerDescriptorPrerequisite(dut: RouteAR3PublicationHarness): Unit = {
    val prerequisite = dut.io.descriptor_durability_prerequisite_in.bits
    prerequisite.layer.poke(0.U); prerequisite.kv_head.poke(0.U)
    prerequisite.page_ref.page_id.poke(0.U); prerequisite.page_ref.generation.poke(0.U)
    prerequisite.transaction_group_tag.poke(1.U)
    prerequisite.required_descriptor_operation_mask.poke(1.U)
    prerequisite.durable_descriptor_operation_mask.poke(1.U)
    prerequisite.descriptor_prepared.poke(true.B); prerequisite.status.poke(p.coreMemoryOkStatusCode.U)
    dut.io.descriptor_durability_prerequisite_in.valid.poke(true.B)
    dut.io.descriptor_durability_prerequisite_in.ready.expect(true.B)
    dut.clock.step(); dut.io.descriptor_durability_prerequisite_in.valid.poke(false.B)
  }

  private def admitMember(dut: RouteAR3PublicationHarness, ordinal: Int, position: Int, groupRecords: Int = 3): Unit = {
    val context = dut.io.admission_context_in.bits
    context.entry_id.poke((position * 288).U); context.layer.poke(0.U); context.kv_head.poke(0.U)
    context.logical_position.poke(position.U); context.payload_ref.poke((100 + position).U)
    context.transaction_group_tag.poke(1.U); context.group_member_ordinal.poke(ordinal.U); context.group_valid_records.poke(groupRecords.U)
    val authority = dut.io.admission_authority_in.bits
    authority.entry_id.poke((position * 288).U); authority.from_authority.poke(1.U); authority.to_authority.poke(2.U)
    authority.transaction_group_tag.poke(1.U)
    dut.io.admission_context_in.valid.poke(true.B); dut.io.admission_authority_in.valid.poke(true.B)
    dut.io.admission_context_in.ready.expect(true.B); dut.io.admission_authority_in.ready.expect(true.B)
    dut.clock.step(); dut.io.admission_context_in.valid.poke(false.B); dut.io.admission_authority_in.valid.poke(false.B)
  }

  private def finishGroupP3AndM2(dut: RouteAR3PublicationHarness, records: Int): Unit = {
    val fragment = dut.io.p3_pending_fragment_in.bits
    fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.status.poke(p.coreMemoryOkStatusCode.U)
    for (fragmentIndex <- 0 until records * 8) {
      fragment.fragment_index.poke(fragmentIndex.U); fragment.last.poke((fragmentIndex == records * 8 - 1).B)
      fragment.payload_ref.poke(Seq(103, 107, 111)(fragmentIndex / 8).U); fragment.data.poke(fragmentIndex.U)
      dut.io.p3_pending_fragment_in.valid.poke(true.B)
      var wait = 0; while (!dut.io.p3_pending_fragment_in.ready.peek().litToBoolean && wait < 8) { dut.clock.step(); wait += 1 }
      require(wait < 8, "timed out waiting for P3 payload-write acceptance")
      dut.clock.step(); dut.io.p3_pending_fragment_in.valid.poke(false.B); dut.clock.step()
    }
    dut.io.p3_pending_fragment_in.valid.poke(false.B)
    val sidecar = dut.io.p3_sidecar_bind_in.bits
    sidecar.layer.poke(0.U); sidecar.stage_generation.poke(1.U)
    for (ordinal <- 0 until records) {
      sidecar.record_ordinal.poke(ordinal.U); sidecar.payload_ref.poke(Seq(103, 107, 111)(ordinal).U)
      sidecar.logical_position.poke(Seq(3, 7, 11)(ordinal).U); dut.io.p3_sidecar_bind_in.valid.poke(true.B)
      var sidecarWait = 0; while (!dut.io.p3_sidecar_bind_in.ready.peek().litToBoolean && sidecarWait < 8) { dut.clock.step(); sidecarWait += 1 }
      require(sidecarWait < 8, "timed out waiting for P3 sidecar-write acceptance")
      dut.clock.step(); dut.io.p3_sidecar_bind_in.valid.poke(false.B); dut.clock.step()
    }
    dut.io.p3_sidecar_bind_in.valid.poke(false.B)
    dut.io.p3_packed_write_issue_in.bits.layer.poke(0.U); dut.io.p3_packed_write_issue_in.bits.stage_generation.poke(1.U)
    dut.io.p3_packed_write_issue_in.bits.transaction_group_tag.poke(1.U); dut.io.p3_packed_write_issue_in.valid.poke(true.B)
    dut.io.p3_packed_write_issue_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_packed_write_issue_in.valid.poke(false.B)
    dut.io.p3_packed_write_terminal_in.bits.layer.poke(0.U); dut.io.p3_packed_write_terminal_in.bits.stage_generation.poke(1.U)
    dut.io.p3_packed_write_terminal_in.bits.transaction_group_tag.poke(1.U); dut.io.p3_packed_write_terminal_in.bits.status.poke(p.coreMemoryOkStatusCode.U)
    dut.io.p3_packed_write_terminal_in.bits.r1_payload_durable.poke(true.B); dut.io.p3_packed_write_terminal_in.valid.poke(true.B)
    dut.io.p3_packed_write_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_packed_write_terminal_in.valid.poke(false.B)
    offerDescriptorPrerequisite(dut)
    for (member <- Seq(RouteAM2GroupMember.HeadControlRmw, RouteAM2GroupMember.SpanOwnerRmw)) {
      dut.io.m2_group_member_req_out.valid.expect(true.B)
      dut.io.m2_group_member_req_out.bits.member.expect(member.U)
      dut.io.m2_group_member_req_out.bits.kv_head.expect(0.U)
      dut.io.m2_group_member_req_out.bits.opaque_address_ref.expect(0.U)
      dut.io.m2_group_member_req_out.bits.owner.expect(0.U)
      dut.io.m2_group_member_req_out.ready.poke(true.B); dut.clock.step(); dut.io.m2_group_member_req_out.ready.poke(false.B)
      val response = dut.io.m2_group_member_rsp_in.bits
      response.layer.poke(0.U); response.stage_generation.poke(1.U); response.transaction_group_tag.poke(1.U)
      response.member.poke(member.U); response.kv_head.poke(0.U)
      response.opaque_address_ref.poke(0.U); response.owner.poke(0.U); response.status.poke(p.coreMemoryOkStatusCode.U)
      dut.io.m2_group_member_rsp_in.valid.poke(true.B); dut.io.m2_group_member_rsp_in.ready.expect(true.B); dut.clock.step(); dut.io.m2_group_member_rsp_in.valid.poke(false.B)
    }
  }

  it("uses the P3 parent read response before each R3-owned packed-write data beat") {
    simulate(new RouteAR3PublicationHarness(p)) { dut =>
      initR3(dut); claimOneRecord(dut); fillOneP3Record(dut, base = 0x40)

      // The first candidate is the request phase; data cannot appear until
      // the parent has issued a tagged P3 array read and accepted its response.
      var wait = 0; while (!dut.io.p3_candidate_valid.peek().litToBoolean && wait < 8) { dut.clock.step(); wait += 1 }
      require(wait < 8, "timed out waiting for P3 packed-write request")
      dut.io.p3_candidate_request_kind.expect(p.coreMemoryWriteRequestCode.U)
      dut.io.p3_candidate_fragment_index.expect(0.U)
      dut.io.p3_candidate_ready.poke(true.B); dut.clock.step()

      for (fragment <- 0 until 8) {
        wait = 0
        while (!dut.io.p3_candidate_valid.peek().litToBoolean && wait < 8) { dut.clock.step(); wait += 1 }
        require(wait < 8, "timed out waiting for P3 parent read/response")
        dut.io.p3_candidate_request_kind.expect(p.coreMemoryWriteDataCode.U)
        dut.io.p3_candidate_fragment_index.expect(fragment.U)
        dut.io.p3_candidate_data.expect((0x40 + fragment).U)
        dut.io.p3_candidate_last.expect((fragment == 7).B)
        dut.clock.step()
      }
      dut.io.p3_candidate_ready.poke(false.B)
      dut.io.p3_observe_state.expect(4.U)
      dut.io.p3_delivery_candidate_id.poke(0.U); dut.io.p3_delivery_status.poke(p.coreMemoryOkStatusCode.U)
      dut.io.p3_delivery_valid.poke(true.B)
      wait = 0; while (!dut.io.p3_delivery_ready.peek().litToBoolean && wait < 8) { dut.clock.step(); wait += 1 }
      require(wait < 8, "timed out waiting for matching P3 packed-write terminal")
      dut.clock.step(); dut.io.p3_delivery_valid.poke(false.B)
      dut.io.p3_observe_state.expect(5.U)
    }
  }

  it("publishes exactly once only after durable P3 and both private M2 members") {
    simulate(new RouteAR3PublicationHarness(p)) { dut =>
      initR3(dut); claimOneRecord(dut)
      val publish = dut.io.m2_publish_req_in.bits
      publish.transaction_group_tag.poke(1.U); publish.p3_layer.poke(0.U); publish.p3_stage_generation.poke(1.U)
      dut.io.m2_publish_req_in.valid.poke(true.B); dut.io.m2_publish_req_in.ready.expect(false.B); dut.io.m2_publish_req_in.valid.poke(false.B)
      finishP3AndM2(dut)
      acceptPublicationCandidate(dut)
      dut.io.m2_publish_req_in.valid.poke(true.B); dut.io.m2_publish_req_in.ready.expect(true.B); dut.clock.step(); dut.io.m2_publish_req_in.valid.poke(false.B)
      dut.io.metadata_publish_visibility_apply.ready.poke(false.B)
      dut.io.metadata_publish_visibility_apply.valid.expect(true.B)
      dut.clock.step(); dut.io.metadata_publish_visibility_apply.valid.expect(true.B)
      dut.io.metadata_publish_visibility_apply.ready.poke(true.B); dut.clock.step()
      dut.io.metadata_publish_visibility_ack_in.bits.page_ref.page_id.poke(0.U); dut.io.metadata_publish_visibility_ack_in.bits.page_ref.generation.poke(0.U)
      dut.io.metadata_publish_visibility_ack_in.bits.status.poke(RouteAPublicationStatus.Published.U)
      dut.io.metadata_publish_visibility_ack_in.valid.poke(true.B); dut.io.metadata_publish_visibility_ack_in.ready.expect(true.B); dut.clock.step(); dut.io.metadata_publish_visibility_ack_in.valid.poke(false.B)
      dut.io.m2_publish_ack.valid.expect(true.B); dut.io.m2_publish_ack.bits.status.expect(RouteAPublicationStatus.Published.U)
      dut.clock.step(); dut.io.p3_observe_state.expect(0.U)
    }
  }

  it("fails closed on a P3 fault and never accepts publication") {
    simulate(new RouteAR3PublicationHarness(p)) { dut =>
      initR3(dut); claimOneRecord(dut)
      val fragment = dut.io.p3_pending_fragment_in.bits
      fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.fragment_index.poke(0.U); fragment.payload_ref.poke(9.U); fragment.data.poke(0.U)
      fragment.last.poke(true.B); fragment.status.poke(p.coreMemoryFaultStatusCode.U)
      dut.io.p3_pending_fragment_in.valid.poke(true.B); dut.io.p3_pending_fragment_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_pending_fragment_in.valid.poke(false.B)
      dut.io.m2_publish_req_in.bits.transaction_group_tag.poke(1.U); dut.io.m2_publish_req_in.bits.p3_layer.poke(0.U); dut.io.m2_publish_req_in.bits.p3_stage_generation.poke(1.U)
      dut.io.m2_publish_req_in.valid.poke(true.B); dut.io.m2_publish_req_in.ready.expect(false.B)
    }
  }

  it("records non-contiguous retained members and reports them only after the one atomic publish") {
    simulate(new RouteAR3PublicationHarness(p)) { dut =>
      initR3(dut)
      val claim = dut.io.p3_claim_in.bits
      claim.layer.poke(0.U); claim.kv_head.poke(0.U); claim.owner.poke(0.U)
      claim.page_ref.page_id.poke(0.U); claim.page_ref.generation.poke(0.U); claim.valid_records.poke(3.U); claim.requires_tail_link.poke(false.B); claim.transaction_group_tag.poke(1.U)
      dut.io.p3_claim_in.valid.poke(true.B); dut.io.p3_claim_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_claim_in.valid.poke(false.B); dut.clock.step()
      // Ordinal order and logical positions are deliberately different: no span inference is legal.
      admitMember(dut, ordinal = 2, position = 11); admitMember(dut, ordinal = 0, position = 3); admitMember(dut, ordinal = 1, position = 7)
      // A duplicate ordinal is rejected before durability/publication.
      val duplicate = dut.io.admission_context_in.bits
      duplicate.entry_id.poke((19 * 288).U); duplicate.layer.poke(0.U); duplicate.kv_head.poke(0.U); duplicate.logical_position.poke(19.U)
      duplicate.payload_ref.poke(119.U); duplicate.transaction_group_tag.poke(1.U); duplicate.group_member_ordinal.poke(1.U); duplicate.group_valid_records.poke(3.U)
      dut.io.admission_authority_in.bits.entry_id.poke((19 * 288).U); dut.io.admission_authority_in.bits.from_authority.poke(1.U); dut.io.admission_authority_in.bits.to_authority.poke(2.U); dut.io.admission_authority_in.bits.transaction_group_tag.poke(1.U)
      dut.io.admission_context_in.valid.poke(true.B); dut.io.admission_authority_in.valid.poke(true.B); dut.io.admission_context_in.ready.expect(false.B); dut.io.admission_authority_in.ready.expect(false.B)
      dut.io.admission_context_in.valid.poke(false.B); dut.io.admission_authority_in.valid.poke(false.B)
      finishGroupP3AndM2(dut, 3)
      acceptPublicationCandidate(dut)
      val publish = dut.io.m2_publish_req_in.bits
      publish.transaction_group_tag.poke(1.U); publish.p3_layer.poke(0.U); publish.p3_stage_generation.poke(1.U)
      dut.io.m2_publish_req_in.valid.poke(true.B); dut.io.m2_publish_req_in.ready.expect(true.B); dut.clock.step(); dut.io.m2_publish_req_in.valid.poke(false.B)
      dut.io.metadata_publish_visibility_ack_in.bits.page_ref.page_id.poke(0.U); dut.io.metadata_publish_visibility_ack_in.bits.page_ref.generation.poke(0.U); dut.io.metadata_publish_visibility_ack_in.bits.status.poke(RouteAPublicationStatus.Published.U)
      dut.io.metadata_publish_visibility_ack_in.valid.poke(true.B); dut.io.metadata_publish_visibility_ack_in.ready.expect(false.B)
      dut.clock.step() // visibility application fires
      dut.io.metadata_publish_visibility_ack_in.ready.expect(true.B); dut.clock.step(); dut.io.metadata_publish_visibility_ack_in.valid.poke(false.B)
      dut.io.m2_publish_ack.valid.expect(true.B); dut.clock.step() // sole atomic publication acknowledgement
      dut.io.publication_commit_observation.valid.expect(true.B)
      dut.io.publication_commit_observation.ready.poke(false.B); dut.clock.step(); dut.io.publication_commit_observation.valid.expect(true.B)
      dut.io.publication_commit_observation.ready.poke(true.B); dut.clock.step()
      Seq(3, 7, 11).zipWithIndex.foreach { case (position, ordinal) =>
        dut.io.publication_member_observation.valid.expect(true.B); dut.io.authority_transition_out.valid.expect(true.B)
        dut.io.publication_member_observation.bits.logical_position.expect(position.U)
        dut.io.publication_member_observation.bits.group_member_ordinal.expect(ordinal.U)
        dut.io.authority_transition_out.bits.entry_id.expect((position * 288).U)
        dut.io.authority_transition_out.bits.from_authority.expect(2.U); dut.io.authority_transition_out.bits.to_authority.expect(3.U)
        // These retained members carry no accepted pending-payload binding:
        // their authority transition remains legal, but cannot withdraw a
        // nonexistent direct-pending association.
        dut.io.pending_to_packed_withdrawal_valid.expect(false.B)
        dut.clock.step()
      }
      dut.io.publication_member_observation.valid.expect(false.B); dut.io.authority_transition_out.valid.expect(false.B)
      // C0 page readiness is withheld until every exact member transition has
      // actually fired into the R6-facing authority channel, then remains
      // stable under consumer ready-low.
      dut.io.post_r6_packed_page_ready_observation.valid.expect(true.B)
      dut.io.post_r6_packed_page_ready_observation.bits.valid_records.expect(3.U)
      dut.io.post_r6_packed_page_ready_observation.ready.poke(false.B); dut.clock.step()
      dut.io.post_r6_packed_page_ready_observation.valid.expect(true.B)
      dut.io.post_r6_packed_page_ready_observation.ready.poke(true.B); dut.clock.step()
    }
  }

  private def initR5(dut: RouteAReclaimHarness): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.page_allocation_req_in.valid.poke(false.B)
    dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.reclaim_permit_in.valid.poke(false.B); dut.io.reclaim_permit_in.bits.transaction_identity.request_id.poke(0.U)
    dut.io.reclaim_permit_in.bits.transaction_identity.incarnation.poke(0.U); dut.io.reclaim_candidate_out.ready.poke(false.B)
    dut.io.reclaim_delivery_in.valid.poke(false.B)
    dut.io.page_allocation_rsp.ready.poke(true.B); dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B)
    dut.io.metadata_publish_visibility_in.valid.poke(false.B); dut.io.metadata_publish_visibility_ack.ready.poke(true.B)
    dut.io.mem_init_done.poke(true.B); dut.clock.step()
  }

  private def allocate(dut: RouteAReclaimHarness, tag: Int): Unit = {
    val alloc = dut.io.page_allocation_req_in.bits
    alloc.layer.poke(0.U); alloc.kv_head.poke(0.U); alloc.valid_records.poke(1.U); alloc.transaction_group_tag.poke(tag.U)
    dut.io.page_allocation_req_in.valid.poke(true.B)
    var waitCycles = 0
    while (!dut.io.page_allocation_req_in.ready.peek().litToBoolean && waitCycles < 32) {
      dut.clock.step(); waitCycles += 1
    }
    dut.io.page_allocation_req_in.ready.expect(true.B); dut.clock.step(); dut.io.page_allocation_req_in.valid.poke(false.B)
    waitCycles = 0
    while (!dut.io.page_allocation_rsp.valid.peek().litToBoolean && waitCycles < 8) {
      dut.clock.step(); waitCycles += 1
    }
    // Leave the response asserted for the caller's original PageRef/tail-link
    // assertions; its ready is high, so an extra helper clock would consume it.
    dut.io.page_allocation_rsp.valid.expect(true.B)
  }

  private def descriptorTerminal(dut: RouteAReclaimHarness, page: Int, tag: Int, kind: Int, fault: Boolean = false): Unit = {
    val terminal = dut.io.descriptor_maintenance_terminal_in.bits
    terminal.kind.poke(kind.U); terminal.page_ref.page_id.poke(page.U); terminal.page_ref.generation.poke(0.U)
    terminal.transaction_group_tag.poke(tag.U); terminal.status.poke((if (fault) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U)
    terminal.r1_descriptor_durable.poke((!fault).B)
    dut.io.descriptor_maintenance_terminal_in.valid.poke(true.B); dut.io.descriptor_maintenance_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B)
  }

  it("keeps descriptor-private pages unreachable until publication and requires a tail link on append") {
    simulate(new RouteAReclaimHarness(p)) { dut =>
      initR5(dut); allocate(dut, 1); dut.io.page_allocation_rsp.valid.expect(true.B); dut.io.page_allocation_rsp.bits.requires_tail_link.expect(false.B); dut.clock.step()
      dut.io.metadata_publish_visibility_in.bits.page_ref.page_id.poke(0.U); dut.io.metadata_publish_visibility_in.bits.page_ref.generation.poke(0.U); dut.io.metadata_publish_visibility_in.bits.transaction_group_tag.poke(1.U)
      dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(false.B); dut.io.metadata_publish_visibility_in.valid.poke(false.B)
      descriptorTerminal(dut, 0, 1, RouteADescriptorOperationKind.NewPage)
      dut.io.metadata_publish_visibility_ack.ready.poke(false.B)
      dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(true.B); dut.clock.step(); dut.io.metadata_publish_visibility_in.valid.poke(false.B)
      dut.io.metadata_publish_visibility_ack.valid.expect(true.B); dut.clock.step(); dut.io.metadata_publish_visibility_ack.valid.expect(true.B)
      dut.io.metadata_publish_visibility_ack.ready.poke(true.B); dut.clock.step()
      allocate(dut, 2); dut.io.page_allocation_rsp.valid.expect(true.B); dut.io.page_allocation_rsp.bits.requires_tail_link.expect(true.B); dut.clock.step()
      descriptorTerminal(dut, 1, 2, RouteADescriptorOperationKind.NewPage)
      dut.io.metadata_publish_visibility_in.bits.page_ref.page_id.poke(1.U); dut.io.metadata_publish_visibility_in.bits.transaction_group_tag.poke(2.U)
      dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(false.B); dut.io.metadata_publish_visibility_in.valid.poke(false.B)
      descriptorTerminal(dut, 1, 2, RouteADescriptorOperationKind.TailLink)
      dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(true.B)
    }
  }

  it("fails closed on descriptor fault and rejects premature invalidation") {
    simulate(new RouteAReclaimHarness(p)) { dut =>
      initR5(dut); allocate(dut, 1); dut.clock.step()
      val terminal = dut.io.descriptor_maintenance_terminal_in.bits
      terminal.kind.poke(RouteADescriptorOperationKind.Invalidate.U); terminal.page_ref.page_id.poke(0.U)
      terminal.page_ref.generation.poke(0.U); terminal.transaction_group_tag.poke(1.U)
      terminal.status.poke(p.coreMemoryOkStatusCode.U); terminal.r1_descriptor_durable.poke(true.B)
      dut.io.descriptor_maintenance_terminal_in.valid.poke(true.B); dut.io.descriptor_maintenance_terminal_in.ready.expect(false.B)
      dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B)
      descriptorTerminal(dut, 0, 1, RouteADescriptorOperationKind.NewPage, fault = true)
      dut.io.metadata_publish_visibility_in.bits.page_ref.page_id.poke(0.U); dut.io.metadata_publish_visibility_in.bits.page_ref.generation.poke(0.U)
      dut.io.metadata_publish_visibility_in.bits.transaction_group_tag.poke(1.U)
      dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(false.B)
    }
  }

}
