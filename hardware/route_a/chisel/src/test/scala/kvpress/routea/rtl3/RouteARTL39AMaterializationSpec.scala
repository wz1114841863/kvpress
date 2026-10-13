package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAM2P3Wrapper
import kvpress.routea.params.{RouteAAnchorWidths, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL3.9-A directed, no-model evidence for R3-owned work/sidecar
  * materialization. This isolates functional protocol behavior only; R2/R1,
  * a memory controller, numeric logic, timing, and PPA are not evaluated.
  */
final class RouteARTL39AMaterializationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=16, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def init(d: RouteAM2P3Wrapper): Unit = {
    d.io.mem_init_done.poke(false.B); d.io.drain_collection_enable.poke(false.B); d.io.p3_observe_layer.poke(0.U)
    d.io.p3_claim_in.valid.poke(false.B); d.io.p3_claim_ack.ready.poke(true.B)
    d.io.admission_context_in.valid.poke(false.B); d.io.admission_authority_in.valid.poke(false.B); d.io.pending_payload_binding_in.valid.poke(false.B)
    d.io.p3_pack_read_materialized_work_out.ready.poke(false.B); d.io.p3_materialized_sidecar_out.ready.poke(false.B)
    d.io.p3_pack_read_work_in.valid.poke(false.B); d.io.p3_pack_read_issue_out.ready.poke(true.B)
    d.io.p3_pending_fragment_in.valid.poke(false.B); d.io.p3_sidecar_bind_in.valid.poke(false.B)
    d.io.p3_packed_write_issue_in.valid.poke(false.B); d.io.p3_packed_write_terminal_in.valid.poke(false.B)
    d.io.p3_packed_write_candidate_out.ready.poke(true.B); d.io.p3_packed_write_delivery_in.valid.poke(false.B)
    d.io.p3_payload_durable_out.ready.poke(true.B); d.io.descriptor_durability_prerequisite_in.valid.poke(false.B)
    d.io.m2_group_member_req_out.ready.poke(false.B); d.io.m2_group_member_rsp_in.valid.poke(false.B)
    d.io.m2_publish_candidate_out.ready.poke(false.B); d.io.m2_publish_req_in.valid.poke(false.B)
    d.io.metadata_publish_visibility_apply.ready.poke(true.B); d.io.metadata_publish_visibility_ack_in.valid.poke(false.B)
    d.io.m2_publish_ack.ready.poke(true.B); d.io.authority_transition_out.ready.poke(true.B)
    d.io.publication_commit_observation.ready.poke(true.B); d.io.publication_member_observation.ready.poke(true.B)
    d.io.post_r6_packed_page_ready_observation.ready.poke(true.B)
    d.io.component_status_out.ready.poke(true.B)
    d.io.mem_init_done.poke(true.B); d.clock.step()
  }

  private def claimAndAdmitBoundMember(d: RouteAM2P3Wrapper): Unit = {
    val claim = d.io.p3_claim_in.bits
    claim.layer.poke(0.U); claim.kv_head.poke(0.U); claim.owner.poke(0.U)
    claim.page_ref.page_id.poke(1.U); claim.page_ref.generation.poke(0.U)
    claim.valid_records.poke(1.U); claim.requires_tail_link.poke(false.B); claim.transaction_group_tag.poke(1.U)
    d.io.p3_claim_in.valid.poke(true.B); d.io.p3_claim_in.ready.expect(true.B); d.clock.step(); d.io.p3_claim_in.valid.poke(false.B)

    val context = d.io.admission_context_in.bits
    context.entry_id.poke((7 * 288).U); context.layer.poke(0.U); context.kv_head.poke(0.U); context.logical_position.poke(7.U)
    context.payload_ref.poke(99.U); context.transaction_group_tag.poke(1.U); context.group_member_ordinal.poke(0.U); context.group_valid_records.poke(1.U)
    val authority = d.io.admission_authority_in.bits
    authority.entry_id.poke((7 * 288).U); authority.from_authority.poke(1.U); authority.to_authority.poke(2.U); authority.transaction_group_tag.poke(1.U)
    val binding = d.io.pending_payload_binding_in.bits
    binding.transaction_identity.request_id.poke(5.U); binding.transaction_identity.incarnation.poke(1.U)
    binding.entry_id.poke((7 * 288).U); binding.layer.poke(0.U); binding.kv_head.poke(0.U); binding.logical_position.poke(7.U)
    binding.payload_ref.poke(99.U); binding.transaction_group_tag.poke(1.U); binding.group_member_ordinal.poke(0.U); binding.group_valid_records.poke(1.U)
    binding.payload_handle_or_address.poke("h55".U); binding.source_generation.poke(2.U); binding.destination_endpoint.poke(1.U)
    d.io.admission_context_in.valid.poke(true.B); d.io.admission_authority_in.valid.poke(true.B); d.io.pending_payload_binding_in.valid.poke(true.B)
    d.io.admission_context_in.ready.expect(true.B); d.io.admission_authority_in.ready.expect(true.B); d.io.pending_payload_binding_in.ready.expect(true.B)
    d.clock.step(); d.io.admission_context_in.valid.poke(false.B); d.io.admission_authority_in.valid.poke(false.B); d.io.pending_payload_binding_in.valid.poke(false.B)
  }

  it("materializes exact A0-bound work and sidecar, then releases its reservation only after the complete record") {
    simulate(new RouteAM2P3Wrapper(p)) { d =>
      init(d); claimAndAdmitBoundMember(d)
      d.io.p3_pack_read_materialized_work_out.valid.expect(true.B)
      val work = d.io.p3_pack_read_materialized_work_out.bits
      work.layer.expect(0.U); work.stage_generation.expect(1.U); work.member_ordinal.expect(0.U); work.payload_ref.expect(99.U)
      work.transaction_identity.request_id.expect(5.U); work.transaction_identity.incarnation.expect(1.U)
      work.payload_handle_or_address.expect("h55".U); work.source_generation.expect(2.U); work.destination_endpoint.expect(1.U)
      work.eligibility_snapshot.expect(((1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 5) | (1 << 6)).U)
      d.clock.step(); d.io.p3_pack_read_materialized_work_out.bits.payload_ref.expect(99.U)
      d.io.p3_pack_read_materialized_work_out.ready.poke(true.B); d.clock.step(); d.io.p3_pack_read_materialized_work_out.ready.poke(false.B)
      d.io.p3_pack_fill_reservation_out.expect(true.B)
      d.io.p3_materialized_sidecar_out.valid.expect(true.B)
      d.io.p3_materialized_sidecar_out.bits.logical_position.expect(7.U); d.io.p3_materialized_sidecar_out.bits.payload_ref.expect(99.U)
      // Mirror the production-shaped top connection for this isolated R3
      // check: an accepted generated sidecar must also traverse the existing
      // checked P3 sidecar input before the stage can become COMPLETE.
      val sidecar = d.io.p3_sidecar_bind_in.bits
      sidecar.layer.poke(0.U); sidecar.stage_generation.poke(1.U); sidecar.record_ordinal.poke(0.U)
      sidecar.payload_ref.poke(99.U); sidecar.logical_position.poke(7.U)
      d.io.p3_sidecar_bind_in.valid.poke(true.B)
      d.io.p3_materialized_sidecar_out.ready.poke(true.B); d.clock.step(); d.io.p3_materialized_sidecar_out.ready.poke(false.B)
      d.io.p3_sidecar_bind_in.valid.poke(false.B)
      val fragment = d.io.p3_pending_fragment_in.bits
      fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.status.poke(p.coreMemoryOkStatusCode.U); fragment.payload_ref.poke(99.U)
      for (index <- 0 until 8) {
        fragment.fragment_index.poke(index.U); fragment.last.poke((index == 7).B); fragment.data.poke(index.U)
        d.io.p3_pending_fragment_in.valid.poke(true.B); d.io.p3_pending_fragment_in.ready.expect(true.B); d.clock.step()
      }
      d.io.p3_pending_fragment_in.valid.poke(false.B)
      d.io.p3_pack_fill_reservation_out.expect(false.B)
      d.io.p3_observe_state.expect(3.U)
    }
  }

  it("releases the materializer reservation on a matching fault without producing another member work") {
    simulate(new RouteAM2P3Wrapper(p)) { d =>
      init(d); claimAndAdmitBoundMember(d)
      d.io.p3_pack_read_materialized_work_out.ready.poke(true.B); d.clock.step(); d.io.p3_pack_read_materialized_work_out.ready.poke(false.B)
      d.io.p3_pack_fill_reservation_out.expect(true.B)
      val fragment = d.io.p3_pending_fragment_in.bits
      fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.fragment_index.poke(0.U); fragment.last.poke(true.B)
      fragment.status.poke(p.coreMemoryFaultStatusCode.U); fragment.payload_ref.poke(99.U); fragment.data.poke(0.U)
      d.io.p3_pending_fragment_in.valid.poke(true.B); d.io.p3_pending_fragment_in.ready.expect(true.B); d.clock.step(); d.io.p3_pending_fragment_in.valid.poke(false.B)
      d.io.p3_pack_fill_reservation_out.expect(false.B)
      d.io.p3_pack_read_materialized_work_out.valid.expect(false.B)
      d.io.p3_observe_state.expect(6.U)
    }
  }

  it("automatically emits the exact packed-write sequence after a complete materialized P3 record and accepts only its matching terminal") {
    simulate(new RouteAM2P3Wrapper(p)) { d =>
      init(d); claimAndAdmitBoundMember(d)

      // Complete the RTL3.9-A materialized member, but hold the next R3-owned
      // write candidate.  This makes the pre-R2 producer descriptor observable
      // without replacing the production R2/R1/registry/router transport.
      d.io.p3_packed_write_candidate_out.ready.poke(false.B)
      d.io.p3_pack_read_materialized_work_out.ready.poke(true.B); d.clock.step()
      d.io.p3_pack_read_materialized_work_out.ready.poke(false.B)
      val sidecar = d.io.p3_sidecar_bind_in.bits
      sidecar.layer.poke(0.U); sidecar.stage_generation.poke(1.U); sidecar.record_ordinal.poke(0.U)
      sidecar.payload_ref.poke(99.U); sidecar.logical_position.poke(7.U)
      d.io.p3_sidecar_bind_in.valid.poke(true.B); d.io.p3_materialized_sidecar_out.ready.poke(true.B); d.clock.step()
      d.io.p3_sidecar_bind_in.valid.poke(false.B); d.io.p3_materialized_sidecar_out.ready.poke(false.B)
      val fragment = d.io.p3_pending_fragment_in.bits
      fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.status.poke(p.coreMemoryOkStatusCode.U); fragment.payload_ref.poke(99.U)
      for (index <- 0 until 8) {
        fragment.fragment_index.poke(index.U); fragment.last.poke((index == 7).B); fragment.data.poke((0x40 + index).U)
        d.io.p3_pending_fragment_in.valid.poke(true.B); d.io.p3_pending_fragment_in.ready.expect(true.B); d.clock.step()
      }
      d.io.p3_pending_fragment_in.valid.poke(false.B)
      d.io.p3_observe_state.expect(3.U) // COMPLETE, not durable or published.

      // The local functional sequencer may only select the completed stage;
      // it is neither an R2 arbitration result nor a service-rate claim.
      d.clock.step()
      d.io.p3_packed_write_candidate_out.valid.expect(true.B)
      val candidate = d.io.p3_packed_write_candidate_out.bits
      candidate.candidate_class.expect(p.r2PackWriteClassCode.U)
      candidate.candidate_id.expect(0.U); candidate.arrival_ordinal.expect(0.U)
      candidate.delivery_target_descriptor.write_endpoint.expect(0.U) // P3PackedWrite
      candidate.delivery_target_descriptor.p3_layer.expect(0.U)
      candidate.delivery_target_descriptor.p3_stage_generation.expect(1.U)
      candidate.delivery_target_descriptor.transaction_group_tag.expect(1.U)
      candidate.r1_request.request_kind.expect(p.coreMemoryWriteRequestCode.U)
      candidate.r1_request.transaction_identity.request_id.expect(0.U)
      candidate.r1_request.transaction_identity.incarnation.expect(0.U)
      candidate.r1_request.expected_fragment_count.expect(8.U)
      candidate.r1_request.fragment_index.expect(0.U); candidate.r1_request.last.expect(false.B)
      candidate.r1_request.address_ref.expect((1 * 33280).U)
      d.clock.step()
      candidate.candidate_id.expect(0.U); candidate.r1_request.fragment_index.expect(0.U)

      d.io.p3_packed_write_candidate_out.ready.poke(true.B); d.clock.step()
      for (index <- 0 until 8) {
        d.io.p3_packed_write_candidate_out.valid.expect(true.B)
        candidate.r1_request.request_kind.expect(p.coreMemoryWriteDataCode.U)
        candidate.r1_request.fragment_index.expect(index.U)
        candidate.r1_request.last.expect((index == 7).B)
        candidate.r1_request.data.expect((0x40 + index).U)
        d.clock.step()
      }
      d.io.p3_packed_write_candidate_out.valid.expect(false.B)
      d.io.p3_observe_state.expect(4.U) // WRITE_ISSUED, awaiting the typed terminal.

      val terminal = d.io.p3_packed_write_delivery_in.bits
      terminal.candidate_class.poke(p.r2PackWriteClassCode.U); terminal.candidate_id.poke(1.U)
      terminal.destination.poke(0.U); terminal.delivery_context_ref.poke(0.U)
      terminal.r1_response.transaction_identity.request_id.poke(0.U); terminal.r1_response.transaction_identity.incarnation.poke(0.U)
      terminal.r1_response.status.poke(p.coreMemoryOkStatusCode.U); terminal.r1_response.fragment_index.poke(7.U)
      terminal.r1_response.last.poke(true.B); terminal.r1_response.data.poke(0.U)
      d.io.p3_packed_write_delivery_in.valid.poke(true.B)
      d.io.p3_packed_write_delivery_in.ready.expect(false.B)
      d.clock.step()
      d.io.p3_observe_state.expect(4.U)

      terminal.candidate_id.poke(0.U)
      d.io.p3_packed_write_delivery_in.ready.expect(true.B)
      d.clock.step(); d.io.p3_packed_write_delivery_in.valid.poke(false.B)
      d.io.p3_observe_state.expect(5.U) // DURABLE only after the exact terminal.
      d.io.p3_payload_durable_out.valid.expect(true.B)
      d.io.p3_payload_durable_out.bits.layer.expect(0.U)
      d.io.p3_payload_durable_out.bits.page_ref.page_id.expect(1.U)
      d.io.p3_payload_durable_out.bits.stage_generation.expect(1.U)
      d.io.p3_payload_durable_out.bits.transaction_group_tag.expect(1.U)
    }
  }
}
