package kvpress.routea.rtl3

import chisel3._
import kvpress.routea.incremental.RouteAM2P3Wrapper
import kvpress.routea.interfaces.{RouteAChannels, RouteAWriteDeliveryEndpoint, StructuralTieOff}
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * Simulator-facing, flat observation harness for the full production R3/P3
  * owner.  It changes no RouteAM2P3Wrapper port or connection: rich unused
  * candidate/issue carriers stay below the simulation root, while every field
  * asserted by RouteARTL39AMaterializationSpec is exposed independently.
  *
  * ChiselSim's generated C++ DPI bridge cannot presently compile a root port
  * containing B2c's unused nested direct_pending_association leaf.  This
  * harness is therefore a test-observation adapter, not a production tie-off
  * or a replacement for the R2/R1 delivery path.
  */
final class RouteARTL39AMaterializationHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val p3_observe_layer = Input(UInt(RouteAAnchorWidths.LayerWidth.W))
    val p3_claim_in = Flipped(RouteAChannels.p3_claim(p))
    val admission_context_in = Flipped(RouteAChannels.admission_context(p))
    val admission_authority_in = Flipped(RouteAChannels.r6_authority_transition(p))
    val pending_payload_binding_in = Flipped(RouteAChannels.pending_payload_read_binding(p))
    val p3_pending_fragment_in = Flipped(RouteAChannels.p3_pending_fragment(p))
    val p3_sidecar_bind_in = Flipped(RouteAChannels.p3_sidecar_bind(p))

    val materialized_work_ready = Input(Bool())
    val materialized_work_valid = Output(Bool())
    val materialized_work_layer = Output(UInt(RouteAAnchorWidths.LayerWidth.W))
    val materialized_work_stage_generation = Output(UInt(p.p3StageGenerationWidth.W))
    val materialized_work_member_ordinal = Output(UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W))
    val materialized_work_payload_ref = Output(UInt(RouteAAnchorWidths.PayloadRefWidth.W))
    val materialized_work_request_id = Output(UInt(RouteAAnchorWidths.RequestIdWidth.W))
    val materialized_work_incarnation = Output(UInt(RouteAAnchorWidths.IncarnationWidth.W))
    val materialized_work_payload_handle = Output(UInt(p.coreMemoryAddressRefWidth.W))
    val materialized_work_source_generation = Output(UInt(p.sourceGenerationWidth.W))
    val materialized_work_destination_endpoint = Output(UInt(p.coreMemoryDestinationWidth.W))
    val materialized_work_eligibility = Output(UInt(p.candidatePredicateWidth.W))

    val materialized_sidecar_ready = Input(Bool())
    val materialized_sidecar_valid = Output(Bool())
    val materialized_sidecar_logical_position = Output(UInt(RouteAAnchorWidths.LogicalPositionWidth.W))
    val materialized_sidecar_payload_ref = Output(UInt(RouteAAnchorWidths.PayloadRefWidth.W))
    val p3_pack_fill_reservation_out = Output(Bool())

    val p3_candidate_ready = Input(Bool())
    val p3_candidate_valid = Output(Bool())
    val p3_candidate_class = Output(UInt(p.candidateClassWidth.W))
    val p3_candidate_request_kind = Output(UInt(p.coreMemoryRequestKindWidth.W))
    val p3_candidate_fragment_index = Output(UInt(p.coreMemoryFragmentIndexWidth.W))
    val p3_candidate_last = Output(Bool())
    val p3_candidate_data = Output(UInt(RouteAAnchorWidths.CoreDataWidth.W))
    val p3_candidate_id = Output(UInt(p.candidateIdWidth.W))
    val p3_candidate_arrival_ordinal = Output(UInt(p.candidateOrdinalWidth.W))
    val p3_candidate_write_endpoint = Output(UInt(RouteAWriteDeliveryEndpoint.Width.W))
    val p3_candidate_layer = Output(UInt(RouteAAnchorWidths.LayerWidth.W))
    val p3_candidate_stage_generation = Output(UInt(p.p3StageGenerationWidth.W))
    val p3_candidate_group_tag = Output(UInt(p.transactionGroupTagWidth.W))
    val p3_candidate_request_id = Output(UInt(RouteAAnchorWidths.RequestIdWidth.W))
    val p3_candidate_incarnation = Output(UInt(RouteAAnchorWidths.IncarnationWidth.W))
    val p3_candidate_expected_fragments = Output(UInt(p.coreMemoryFragmentCountWidth.W))
    val p3_candidate_address_ref = Output(UInt(p.coreMemoryAddressRefWidth.W))

    val p3_delivery_valid = Input(Bool())
    val p3_delivery_ready = Output(Bool())
    val p3_delivery_candidate_id = Input(UInt(p.candidateIdWidth.W))
    val p3_delivery_destination = Input(UInt(p.coreMemoryDestinationWidth.W))
    val p3_delivery_context_ref = Input(UInt(p.sourceDeliveryOpaqueWidth.W))
    val p3_delivery_request_id = Input(UInt(RouteAAnchorWidths.RequestIdWidth.W))
    val p3_delivery_incarnation = Input(UInt(RouteAAnchorWidths.IncarnationWidth.W))
    val p3_delivery_status = Input(UInt(RouteAAnchorWidths.TerminalStatusWidth.W))
    val p3_delivery_fragment_index = Input(UInt(p.coreMemoryFragmentIndexWidth.W))
    val p3_delivery_last = Input(Bool())
    val p3_delivery_data = Input(UInt(RouteAAnchorWidths.CoreDataWidth.W))

    val p3_payload_durable_ready = Input(Bool())
    val p3_payload_durable_valid = Output(Bool())
    val p3_payload_durable_layer = Output(UInt(RouteAAnchorWidths.LayerWidth.W))
    val p3_payload_durable_page_id = Output(UInt(RouteAAnchorWidths.PageIdWidth.W))
    val p3_payload_durable_page_generation = Output(UInt(RouteAAnchorWidths.PageGenerationWidth.W))
    val p3_payload_durable_stage_generation = Output(UInt(p.p3StageGenerationWidth.W))
    val p3_payload_durable_group_tag = Output(UInt(p.transactionGroupTagWidth.W))
    val p3_observe_state = Output(UInt(RouteAAnchorWidths.P3StateWidth.W))
  })

  val r3 = Module(new RouteAM2P3Wrapper(p))
  r3.io.mem_init_done := io.mem_init_done
  r3.io.drain_collection_enable := io.drain_collection_enable
  r3.io.p3_observe_layer := io.p3_observe_layer
  r3.io.p3_claim_in <> io.p3_claim_in
  r3.io.p3_claim_ack.ready := true.B
  r3.io.admission_context_in <> io.admission_context_in
  r3.io.admission_authority_in <> io.admission_authority_in
  r3.io.pending_payload_binding_in <> io.pending_payload_binding_in
  r3.io.p3_pending_fragment_in <> io.p3_pending_fragment_in
  r3.io.p3_sidecar_bind_in <> io.p3_sidecar_bind_in

  io.materialized_work_valid := r3.io.p3_pack_read_materialized_work_out.valid
  io.materialized_work_layer := r3.io.p3_pack_read_materialized_work_out.bits.layer
  io.materialized_work_stage_generation := r3.io.p3_pack_read_materialized_work_out.bits.stage_generation
  io.materialized_work_member_ordinal := r3.io.p3_pack_read_materialized_work_out.bits.member_ordinal
  io.materialized_work_payload_ref := r3.io.p3_pack_read_materialized_work_out.bits.payload_ref
  io.materialized_work_request_id := r3.io.p3_pack_read_materialized_work_out.bits.transaction_identity.request_id
  io.materialized_work_incarnation := r3.io.p3_pack_read_materialized_work_out.bits.transaction_identity.incarnation
  io.materialized_work_payload_handle := r3.io.p3_pack_read_materialized_work_out.bits.payload_handle_or_address
  io.materialized_work_source_generation := r3.io.p3_pack_read_materialized_work_out.bits.source_generation
  io.materialized_work_destination_endpoint := r3.io.p3_pack_read_materialized_work_out.bits.destination_endpoint
  io.materialized_work_eligibility := r3.io.p3_pack_read_materialized_work_out.bits.eligibility_snapshot
  r3.io.p3_pack_read_materialized_work_out.ready := io.materialized_work_ready

  io.materialized_sidecar_valid := r3.io.p3_materialized_sidecar_out.valid
  io.materialized_sidecar_logical_position := r3.io.p3_materialized_sidecar_out.bits.logical_position
  io.materialized_sidecar_payload_ref := r3.io.p3_materialized_sidecar_out.bits.payload_ref
  r3.io.p3_materialized_sidecar_out.ready := io.materialized_sidecar_ready
  io.p3_pack_fill_reservation_out := r3.io.p3_pack_fill_reservation_out

  io.p3_candidate_valid := r3.io.p3_packed_write_candidate_out.valid
  io.p3_candidate_class := r3.io.p3_packed_write_candidate_out.bits.candidate_class
  io.p3_candidate_request_kind := r3.io.p3_packed_write_candidate_out.bits.r1_request.request_kind
  io.p3_candidate_fragment_index := r3.io.p3_packed_write_candidate_out.bits.r1_request.fragment_index
  io.p3_candidate_last := r3.io.p3_packed_write_candidate_out.bits.r1_request.last
  io.p3_candidate_data := r3.io.p3_packed_write_candidate_out.bits.r1_request.data
  io.p3_candidate_id := r3.io.p3_packed_write_candidate_out.bits.candidate_id
  io.p3_candidate_arrival_ordinal := r3.io.p3_packed_write_candidate_out.bits.arrival_ordinal
  io.p3_candidate_write_endpoint := r3.io.p3_packed_write_candidate_out.bits.delivery_target_descriptor.write_endpoint
  io.p3_candidate_layer := r3.io.p3_packed_write_candidate_out.bits.delivery_target_descriptor.p3_layer
  io.p3_candidate_stage_generation := r3.io.p3_packed_write_candidate_out.bits.delivery_target_descriptor.p3_stage_generation
  io.p3_candidate_group_tag := r3.io.p3_packed_write_candidate_out.bits.delivery_target_descriptor.transaction_group_tag
  io.p3_candidate_request_id := r3.io.p3_packed_write_candidate_out.bits.r1_request.transaction_identity.request_id
  io.p3_candidate_incarnation := r3.io.p3_packed_write_candidate_out.bits.r1_request.transaction_identity.incarnation
  io.p3_candidate_expected_fragments := r3.io.p3_packed_write_candidate_out.bits.r1_request.expected_fragment_count
  io.p3_candidate_address_ref := r3.io.p3_packed_write_candidate_out.bits.r1_request.address_ref
  r3.io.p3_packed_write_candidate_out.ready := io.p3_candidate_ready

  r3.io.p3_packed_write_delivery_in.valid := io.p3_delivery_valid
  r3.io.p3_packed_write_delivery_in.bits := 0.U.asTypeOf(r3.io.p3_packed_write_delivery_in.bits)
  r3.io.p3_packed_write_delivery_in.bits.candidate_class := p.r2PackWriteClassCode.U
  r3.io.p3_packed_write_delivery_in.bits.candidate_id := io.p3_delivery_candidate_id
  r3.io.p3_packed_write_delivery_in.bits.destination := io.p3_delivery_destination
  r3.io.p3_packed_write_delivery_in.bits.delivery_context_ref := io.p3_delivery_context_ref
  r3.io.p3_packed_write_delivery_in.bits.r1_response.transaction_identity.request_id := io.p3_delivery_request_id
  r3.io.p3_packed_write_delivery_in.bits.r1_response.transaction_identity.incarnation := io.p3_delivery_incarnation
  r3.io.p3_packed_write_delivery_in.bits.r1_response.status := io.p3_delivery_status
  r3.io.p3_packed_write_delivery_in.bits.r1_response.fragment_index := io.p3_delivery_fragment_index
  r3.io.p3_packed_write_delivery_in.bits.r1_response.last := io.p3_delivery_last
  r3.io.p3_packed_write_delivery_in.bits.r1_response.data := io.p3_delivery_data
  io.p3_delivery_ready := r3.io.p3_packed_write_delivery_in.ready

  io.p3_payload_durable_valid := r3.io.p3_payload_durable_out.valid
  io.p3_payload_durable_layer := r3.io.p3_payload_durable_out.bits.layer
  io.p3_payload_durable_page_id := r3.io.p3_payload_durable_out.bits.page_ref.page_id
  io.p3_payload_durable_page_generation := r3.io.p3_payload_durable_out.bits.page_ref.generation
  io.p3_payload_durable_stage_generation := r3.io.p3_payload_durable_out.bits.stage_generation
  io.p3_payload_durable_group_tag := r3.io.p3_payload_durable_out.bits.transaction_group_tag
  r3.io.p3_payload_durable_out.ready := io.p3_payload_durable_ready
  io.p3_observe_state := r3.io.p3_observe_state

  StructuralTieOff.source(r3.io.pending_packing_reconciliation_lookup_in)
  StructuralTieOff.sink(r3.io.pending_packing_reconciliation_result_out)
  r3.io.p3_pack_read_issue_out.ready := true.B
  StructuralTieOff.source(r3.io.p3_pack_read_work_in)
  StructuralTieOff.source(r3.io.p3_packed_write_issue_in)
  StructuralTieOff.source(r3.io.p3_packed_write_terminal_in)
  StructuralTieOff.source(r3.io.descriptor_durability_prerequisite_in)
  StructuralTieOff.sink(r3.io.m2_group_member_req_out)
  StructuralTieOff.source(r3.io.m2_group_member_rsp_in)
  StructuralTieOff.sink(r3.io.m2_publish_candidate_out)
  StructuralTieOff.source(r3.io.m2_publish_req_in)
  r3.io.metadata_publish_visibility_apply.ready := true.B
  StructuralTieOff.source(r3.io.metadata_publish_visibility_ack_in)
  r3.io.m2_publish_ack.ready := true.B
  r3.io.authority_transition_out.ready := true.B
  r3.io.publication_commit_observation.ready := true.B
  r3.io.publication_member_observation.ready := true.B
  r3.io.post_r6_packed_page_ready_observation.ready := true.B
  r3.io.component_status_out.ready := true.B
}
