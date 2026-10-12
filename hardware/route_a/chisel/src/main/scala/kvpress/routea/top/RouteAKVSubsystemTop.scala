package kvpress.routea.top

import chisel3._
import kvpress.routea.common._
import kvpress.routea.incremental._
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * Composition-only RTL1.0 skeleton for the frozen Route-A hierarchy.
  *
  * All non-environment cross-owner channels exist and are connected. Channels
  * without a functional producer/consumer are structurally tied inactive. No
  * mutable architecture state, protocol transition, publication, arbitration,
  * source release, retry, fallback, or numeric behavior is implemented here.
  */
final class RouteAKVSubsystemTop(p: RouteASkeletonParameters) extends RawModule {
  override def desiredName: String = "route_a_kv_subsystem_top"

  val core_clk = IO(Input(Clock()))
  // A Bool carrier avoids selecting synchronous versus asynchronous reset at
  // RTL1.0. This shell contains no sequential state or reset behavior.
  val destructive_reset = IO(Input(Bool()))

  val frontend_lifecycle_req = IO(Flipped(RouteAChannels.frontend_lifecycle_req(p)))
  val runtime_retire_req = IO(Flipped(RouteAChannels.runtime_retire_req))
  val attention_terminal_rsp = IO(RouteAChannels.attention_terminal_rsp)
  val session_retire_ack = IO(RouteAChannels.session_retire_ack)
  // C6 consumes an immutable, already-selected source declaration through a
  // named binder. The top only composes this boundary and never creates a plan.
  val source_plan_declaration_in = IO(Flipped(RouteAChannels.source_plan_declaration(p)))
  // Hot-owner egress into R3's replaceable functional P3 backing. These are
  // environment-owned payload/sidecar inputs; the composition top creates no
  // data, address, admission, authority, or delivery-context fact.
  val hot_payload_fragment_in = IO(Flipped(RouteAChannels.p3_pending_fragment(p)))
  val hot_position_sidecar_in = IO(Flipped(RouteAChannels.p3_sidecar_bind(p)))
  // RTL2.3-C9 verification-environment ingress.  These carriers make the
  // already specified C2/C3/C4 endpoint paths observable from the composed
  // top while assigning no source-plan, admission, ownership, scheduling, or
  // numeric responsibility to this top.  Production realization replaces
  // these explicit harness ingress points with their separately-authorized
  // owners; opaque source-service packets remain inactive below.
  val verification_p3_pack_read_work_in = IO(Flipped(RouteAChannels.p3_pack_read_work(p)))
  val verification_direct_pending_open_in = IO(Flipped(RouteAChannels.direct_pending_open(p)))
  val verification_direct_pending_read_work_in = IO(Flipped(RouteAChannels.direct_pending_read_work(p)))
  val verification_s2_sidecar_fragment_in = IO(Flipped(RouteAChannels.s2_sidecar_fragment(p)))
  val verification_s2_sidecar_complete_in = IO(Flipped(RouteAChannels.s2_sidecar_complete(p)))
  val verification_direct_pending_payload_fragment_out = IO(RouteAChannels.direct_pending_payload_fragment(p))
  val external_core_mem_if_v1 = IO(new CoreMemoryExternalPort(p))

  withClockAndReset(core_clk, destructive_reset) {
    val lifecycle = Module(new RouteALifecycleAdapter(p))
    val hot = Module(new RouteAHotSourcePath(p))
    val s2 = Module(new RouteAS2GqaSourceWrapper(p))
    val direct_pending = Module(new RouteADirectPendingEndpointV1(p))
    val arbiter = Module(new RouteACoreSideArbiter(p))
    val core_memory = Module(new RouteACoreMemIfV1(p))
    val m2_p3 = Module(new RouteAM2P3Wrapper(p))
    val m2_reference_protocol = Module(new RouteAM2ReferenceProtocolProvider(p))
    val page_manager = Module(new RouteAPageManager(p))
    val packed_activation_binder = Module(new RouteAPackedReadActivationBinder(p))
    val packed_association_owner = Module(new RouteAPackedReadAssociationOwner(p))
    val packed_plan_fork = Module(new RouteASourceCompletionPlanActivationFork(p))
    val packed_terminal_bridge = Module(new RouteAPackedReadTerminalBridge(p))
    val admission_group_builder = Module(new RouteAAdmissionPublicationIngressAdapter(p))
    val r2_write_ingress = Module(new RouteAR2WriteIngressMerge(p))
    val r2_read_ingress = Module(new RouteAR2ReadIngressMerge(p))
    val delivery_context_registry = Module(new RouteADeliveryContextRegistry(p))
    val delivery_context_composition = Module(new RouteAUnifiedDeliveryContextAllocationBridge(p))
    val typed_delivery_router = Module(new RouteATypedDeliveryRouter(p))
    val read_endpoint_demultiplexer = Module(new RouteAReadEndpointDemultiplexer(p))
    val p3_pending_ingress = Module(new RouteAExclusiveP3PendingIngress(p))
    val p3_pack_read_issue_adapter = Module(new RouteAReadIssueCandidateAdapter(p))
    val direct_pending_read_producer = Module(new RouteAR3DirectPendingReadProducer(p))
    val direct_pending_read_issue_adapter = Module(new RouteAReadIssueCandidateAdapter(p))
    val packed_s2_read_producer = Module(new RouteAPackedS2ReadProducer(p))
    val packed_s2_read_issue_adapter = Module(new RouteAReadIssueCandidateAdapter(p))
    val p3_pack_read_endpoint = Module(new RouteAR3PackReadEndpoint(p))
    val direct_pending_read_endpoint = Module(new RouteADirectPendingReadEndpoint(p))
    val packed_s2_read_endpoint = Module(new RouteAPackedS2ReadEndpoint(p))
    val source_plan_binder = Module(new RouteASourcePlanBinder(p))
    val source_packet_adapter = Module(new RouteASourceServicePacketAdapter(p))
    val source_commit_demultiplexer = Module(new RouteASourceCommitDemultiplexer(p))
    val merge = Module(new RouteAMergeBoundary(p))
    val status_collector = Module(new RouteAComponentStatusCollector(p))

    lifecycle.io.frontend_lifecycle_req <> frontend_lifecycle_req
    lifecycle.io.runtime_retire_req <> runtime_retire_req
    attention_terminal_rsp <> lifecycle.io.attention_terminal_rsp
    session_retire_ack <> lifecycle.io.session_retire_ack

    lifecycle.io.component_status_in <> status_collector.io.component_status_out

    hot.io.lifecycle_control_in <> lifecycle.io.hot_control_out
    val hot_source_open = Wire(RouteAChannels.hot_source_open(p)); StructuralTieOff.source(hot_source_open)
    val hot_release = Wire(RouteAChannels.source_release(p))
    hot.io.hot_source_open_in <> hot_source_open
    hot_release <> hot.io.hot_release_out
    val r6_merge_ready = Wire(RouteAChannels.r6_merge_ready); StructuralTieOff.source(r6_merge_ready)
    lifecycle.io.merge_ready_in <> r6_merge_ready
    source_plan_binder.io.declaration_in <> source_plan_declaration_in
    lifecycle.io.source_completion_plan_in <> source_plan_binder.io.completion_plan_out
    // R6 retains plan ownership.  The exact-copy fork delivers every plan to
    // the packet path and only a packed-present copy to the activation binder;
    // it makes no source selection and tolerates independent backpressure.
    packed_plan_fork.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out
    source_packet_adapter.io.accepted_plan_in <> packed_plan_fork.io.packet_plan_out
    packed_activation_binder.io.accepted_plan_in <> packed_plan_fork.io.packed_activation_plan_out
    lifecycle.io.hot_source_release_in <> hot_release
    s2.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    // Packed S2 reservation is now owner-local through the binder lease
    // request.  The historical verification service request is retired.
    s2.io.service_req_in <> lifecycle.io.s2_service_req
    val s2_fill_open = packed_s2_read_producer.io.s2_fill_open_out
    val s2_payload_fragment = packed_s2_read_endpoint.io.s2_payload_fragment_out
    val s2_sidecar_fragment = verification_s2_sidecar_fragment_in
    val s2_fill_terminal = packed_terminal_bridge.io.s2_terminal_out
    val s2_sidecar_complete = verification_s2_sidecar_complete_in
    val s2_payload_read_req = Wire(RouteAChannels.s2_payload_read_req(p)); StructuralTieOff.source(s2_payload_read_req)
    val s2_sidecar_read_req = Wire(RouteAChannels.s2_sidecar_read_req(p)); StructuralTieOff.source(s2_sidecar_read_req)
    val s2_release = Wire(RouteAChannels.source_release(p))
    s2.io.s2_fill_open_in <> s2_fill_open
    s2.io.s2_payload_fragment_in <> s2_payload_fragment
    s2.io.s2_sidecar_fragment_in <> s2_sidecar_fragment
    s2.io.s2_fill_terminal_in <> s2_fill_terminal
    s2.io.s2_sidecar_complete_in <> s2_sidecar_complete
    s2.io.s2_payload_read_req_in <> s2_payload_read_req
    s2.io.s2_sidecar_read_req_in <> s2_sidecar_read_req
    StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
    StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
    s2_release <> s2.io.s2_release_out
    lifecycle.io.packed_source_release_in <> s2_release
    // The adapter's active accepted plan selects only which S2 owner-local
    // state is observed.  Exact identity/instance matching remains in the
    // adapter, and an out-of-range coordinate fails closed there.
    s2.io.s2_observe_slot := source_packet_adapter.io.packed_observe_slot_out

    packed_activation_binder.io.mem_init_done := core_memory.io.r1_init_complete
    packed_association_owner.io.mem_init_done := core_memory.io.r1_init_complete
    page_manager.io.descriptor_location_request_in <>
      packed_activation_binder.io.descriptor_location_request_out
    packed_activation_binder.io.descriptor_grant_in <>
      page_manager.io.descriptor_location_grant_out
    s2.io.s2_fill_lease_request_in <> packed_activation_binder.io.s2_fill_lease_request_out
    packed_activation_binder.io.s2_fill_lease_in <> s2.io.s2_fill_lease_out
    packed_association_owner.io.demand_in <> packed_activation_binder.io.demand_out
    packed_association_owner.io.publication_authorization_in <>
      packed_activation_binder.io.publication_authorization_out
    packed_association_owner.io.descriptor_grant_in <> packed_activation_binder.io.descriptor_grant_out
    packed_association_owner.io.s2_fill_lease_in <> packed_activation_binder.io.s2_fill_lease_out
    packed_association_owner.io.invalidation_in.valid := false.B
    packed_association_owner.io.invalidation_in.bits := 0.U.asTypeOf(new PackedReadInvalidation)
    packed_association_owner.io.release_observation_out.ready := true.B
    direct_pending.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    val directOpenIngress = Wire(RouteAChannels.direct_pending_open(p))
    val simultaneousDirectOpen = lifecycle.io.direct_pending_open.valid && verification_direct_pending_open_in.valid
    directOpenIngress.valid := (lifecycle.io.direct_pending_open.valid || verification_direct_pending_open_in.valid) && !simultaneousDirectOpen
    directOpenIngress.bits := Mux(lifecycle.io.direct_pending_open.valid,
      lifecycle.io.direct_pending_open.bits, verification_direct_pending_open_in.bits)
    lifecycle.io.direct_pending_open.ready := !verification_direct_pending_open_in.valid && directOpenIngress.ready
    verification_direct_pending_open_in.ready := !lifecycle.io.direct_pending_open.valid && directOpenIngress.ready
    assert(!simultaneousDirectOpen, "C9 direct-pending open requires one declared producer")
    direct_pending.io.pending_source_open_in <> directOpenIngress
    val direct_record_terminal = direct_pending_read_endpoint.io.record_terminal_out
    val direct_release = Wire(RouteAChannels.source_release(p))
    direct_pending.io.direct_pending_record_terminal_in <> direct_record_terminal
    verification_direct_pending_payload_fragment_out <> direct_pending_read_endpoint.io.payload_fragment_out
    direct_release <> direct_pending.io.direct_release_out
    lifecycle.io.pending_source_release_in <> direct_release

    val source_partial_to_merge = Wire(RouteAChannels.source_partial)
    StructuralTieOff.source(source_partial_to_merge)
    merge.io.source_partial_in <> source_partial_to_merge

    // C7 connects the already accepted plan and exact owner observations into
    // the C5 packet adapter.  Current owners still have no numeric partial
    // producer, so their packet ingress remains explicitly inactive until the
    // later source-service closure; this top manufactures no packet.
    source_packet_adapter.io.hot_available_in.valid := hot.io.hot_observe_active
    source_packet_adapter.io.hot_available_in.transaction_identity := hot.io.hot_observe_identity
    source_packet_adapter.io.hot_available_in.source_instance := hot.io.hot_observe_instance
    source_packet_adapter.io.pending_available_in.valid := direct_pending.io.direct_observe_deliverable
    source_packet_adapter.io.pending_available_in.transaction_identity := direct_pending.io.direct_observe_identity
    source_packet_adapter.io.pending_available_in.source_instance := direct_pending.io.direct_observe_instance
    source_packet_adapter.io.packed_available_in.valid := s2.io.s2_observe_available
    source_packet_adapter.io.packed_available_in.transaction_identity := s2.io.s2_observe_identity
    source_packet_adapter.io.packed_available_in.source_instance := s2.io.s2_observe_instance
    StructuralTieOff.source(source_packet_adapter.io.hot_offer_in)
    StructuralTieOff.source(source_packet_adapter.io.pending_offer_in)
    StructuralTieOff.source(source_packet_adapter.io.packed_offer_in)
    StructuralTieOff.source(source_packet_adapter.io.hot_fragment_in)
    StructuralTieOff.source(source_packet_adapter.io.pending_fragment_in)
    StructuralTieOff.source(source_packet_adapter.io.packed_fragment_in)

    val r4_result_stub = Wire(RouteAChannels.r4_result_stub); StructuralTieOff.source(r4_result_stub)
    val r4_numeric_fault = Wire(RouteAChannels.r4_numeric_fault); StructuralTieOff.source(r4_numeric_fault)
    merge.io.r4_partial_header_in <> source_packet_adapter.io.r4_partial_header_out
    merge.io.r4_source_instance_in <> source_packet_adapter.io.r4_source_instance_out
    merge.io.r4_value_fragment_in <> source_packet_adapter.io.r4_value_fragment_out
    // RTL3.4-B functional-provider observation remains unbound in the
    // production composition top.  Dropping it here cannot create a result
    // or terminal; the functional-provider harness binds it explicitly.
    merge.io.r4_accepted_partial_packet_out.ready := true.B
    merge.io.r4_result_stub_in <> r4_result_stub
    merge.io.r4_numeric_fault_in <> r4_numeric_fault

    // C8 keeps the top composition-only: the named child rejects a mismatch
    // between R4's header source ordinal and sideband SourceInstance, then
    // forwards the exact commit to one owner-local four-consumer tracker.
    source_commit_demultiplexer.io.commit_in <> merge.io.consumer_partial_commit
    hot.io.gqa_consumer_commit_in <> source_commit_demultiplexer.io.hot_commit_out
    direct_pending.io.gqa_consumer_commit_in <> source_commit_demultiplexer.io.pending_commit_out
    s2.io.gqa_consumer_commit_in <> source_commit_demultiplexer.io.packed_commit_out

    merge.io.merge_req_in <> lifecycle.io.merge_req
    lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault

    // R2 alone accepts its two logical ingress carriers. The producer-local
    // merges merely present ref-bound records; this top does not select one.
    arbiter.io.candidate_in <> r2_write_ingress.io.candidate_out
    arbiter.io.read_candidate_in <> r2_read_ingress.io.candidate_out

    core_memory.io.core_mem_req_in <> arbiter.io.core_mem_req
    arbiter.io.core_mem_rsp_in <> core_memory.io.core_mem_rsp
    external_core_mem_if_v1 <> core_memory.io.external_core_mem_if_v1
    arbiter.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    arbiter.io.reclaim_maintenance_enable := lifecycle.io.reclaim_maintenance_enable
    core_memory.io.r1_drain_permitted := status_collector.io.r1_drain_permitted

    // The R1 reset-epoch acknowledgement is the sole local init fanout. It
    // enables no data source path by itself and ordinary R1 responses are not
    // interpreted as init acknowledgements.
    s2.io.mem_init_done := core_memory.io.r1_init_complete
    direct_pending.io.mem_init_done := core_memory.io.r1_init_complete
    delivery_context_registry.io.mem_init_done := core_memory.io.r1_init_complete

    delivery_context_registry.io.resolve_in <> arbiter.io.source_delivery_out
    typed_delivery_router.io.resolved_in <> delivery_context_registry.io.resolved_out
    delivery_context_registry.io.release_in <> typed_delivery_router.io.release_out
    delivery_context_composition.io.release_event_in := typed_delivery_router.io.release_event_out
    page_manager.io.reclaim_delivery_in <> typed_delivery_router.io.r5_reclaim_out
    page_manager.io.append_delivery_in <> typed_delivery_router.io.r5_append_out
    // The composed production top does not instantiate a scoreboard.  Consume
    // R5's post-durable observation locally; the RTL2.5.5 test-only adapter
    // is the sole event binding and may backpressure this carrier there.
    page_manager.io.allocator_release_out.ready := true.B
    // C9: one descriptor-selected, fail-closed top composition point replaces
    // the isolated C2/C3/C4 endpoint harness routers.  It has no response
    // field inference and no scheduler/producer policy.
    read_endpoint_demultiplexer.io.resolved_in <> typed_delivery_router.io.read_fragment_out
    p3_pack_read_endpoint.io.resolved_fragment_in <> read_endpoint_demultiplexer.io.p3_pack_read_out
    direct_pending_read_endpoint.io.resolved_fragment_in <> read_endpoint_demultiplexer.io.direct_pending_out
    packed_s2_read_endpoint.io.resolved_fragment_in <> read_endpoint_demultiplexer.io.packed_s2_out

    m2_p3.io.mem_init_done := core_memory.io.r1_init_complete
    m2_p3.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    // RTL2.1a: only the admitted hot->pending pair enters the dedicated
    // one-group protocol owner. Arrival/drop edges remain local hot control
    // facts; the top creates neither admission context nor authority state.
    val r6ToPending = lifecycle.io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Hot.U &&
      lifecycle.io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Pending.U
    admission_group_builder.io.r6_admission_context_in <> lifecycle.io.admission_context_out
    admission_group_builder.io.r6_authority_in.valid := lifecycle.io.authority_transition_out.valid && r6ToPending
    admission_group_builder.io.r6_authority_in.bits := lifecycle.io.authority_transition_out.bits
    lifecycle.io.authority_transition_out.ready := Mux(r6ToPending, admission_group_builder.io.r6_authority_in.ready, true.B)
    admission_group_builder.io.r5_allocation_req <> page_manager.io.page_allocation_req_in
    admission_group_builder.io.r5_allocation_rsp_in <> page_manager.io.page_allocation_rsp
    admission_group_builder.io.r3_p3_claim <> m2_p3.io.p3_claim_in
    admission_group_builder.io.r3_p3_claim_ack_in <> m2_p3.io.p3_claim_ack
    admission_group_builder.io.r3_admission_context_out <> m2_p3.io.admission_context_in
    admission_group_builder.io.r3_admission_authority_out <> m2_p3.io.admission_authority_in
    p3_pending_ingress.io.hot_in <> hot_payload_fragment_in
    p3_pending_ingress.io.pack_read_in <> p3_pack_read_endpoint.io.p3_pending_fragment_out
    val p3_fragment = p3_pending_ingress.io.out
    val p3_sidecar = hot_position_sidecar_in
    // C9 activates the already-frozen C2 work/issue carrier only through an
    // explicit verification environment ingress.  R3 validates the immutable
    // member association before the sole bridge allocates a delivery context.
    val p3_pack_read_work = verification_p3_pack_read_work_in
    val p3_pack_read_issue = p3_pack_read_issue_adapter.io.read_issue_in
    val p3_write_issue = Wire(RouteAChannels.p3_packed_write_issue(p)); StructuralTieOff.source(p3_write_issue)
    val p3_write_terminal = Wire(RouteAChannels.p3_packed_write_terminal(p)); StructuralTieOff.source(p3_write_terminal)
    m2_p3.io.p3_pending_fragment_in <> p3_fragment
    m2_p3.io.p3_sidecar_bind_in <> p3_sidecar
    m2_p3.io.p3_pack_read_work_in <> p3_pack_read_work
    p3_pack_read_issue <> m2_p3.io.p3_pack_read_issue_out
    p3_pack_read_issue_adapter.io.candidate_out <> delivery_context_composition.io.r3_pack_read_in
    m2_p3.io.p3_packed_write_issue_in <> p3_write_issue
    m2_p3.io.p3_packed_write_terminal_in <> p3_write_terminal
    m2_reference_protocol.io.member_request_in <> m2_p3.io.m2_group_member_req_out
    m2_p3.io.m2_group_member_rsp_in <> m2_reference_protocol.io.member_response_out
    m2_p3.io.p3_observe_layer := 0.U
    m2_reference_protocol.io.publication_candidate_in <> m2_p3.io.m2_publish_candidate_out
    m2_p3.io.m2_publish_req_in <> m2_reference_protocol.io.publication_request_out
    // R6 observes the completed R3/R5 commit acknowledgement; it is not a
    // second publication initiator.  R3 owns the issued candidate above.
    StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
    lifecycle.io.authority_transition_in <> m2_p3.io.authority_transition_out
    // R3's post-atomic observation is the sole publication fact consumed by
    // the activation binder.  No second publication/authority edge is made.
    packed_activation_binder.io.publication_commit_in <> m2_p3.io.publication_commit_observation
    m2_p3.io.publication_member_observation.ready := true.B
    page_manager.io.mem_init_done := core_memory.io.r1_init_complete
    page_manager.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    page_manager.io.reclaim_permit_in <> lifecycle.io.reclaim_permit_out
    lifecycle.io.r5_reclaim_complete_in := page_manager.io.reclaim_complete
    val descriptor_maintenance_terminal = Wire(RouteAChannels.descriptor_maintenance_terminal(p)); StructuralTieOff.source(descriptor_maintenance_terminal)
    page_manager.io.descriptor_maintenance_terminal_in <> descriptor_maintenance_terminal
    // Existing direct-pending work remains a verification ingress.  Packed
    // S2 work now comes only from the exact association owner.
    direct_pending_read_producer.io.work_in <> verification_direct_pending_read_work_in
    direct_pending_read_issue_adapter.io.read_issue_in <> direct_pending_read_producer.io.read_issue_out
    delivery_context_composition.io.r3_direct_pending_in <> direct_pending_read_issue_adapter.io.candidate_out
    packed_terminal_bridge.io.work_in <> packed_association_owner.io.packed_s2_work_out
    packed_s2_read_producer.io.work_in <> packed_terminal_bridge.io.work_out
    packed_s2_read_issue_adapter.io.read_issue_in <> packed_s2_read_producer.io.read_issue_out
    StructuralTieOff.source(delivery_context_composition.io.r5_s2_packed_in)
    delivery_context_composition.io.packed_association_allocate_in <>
      packed_association_owner.io.registry_allocate_out
    delivery_context_composition.io.packed_association_arrival_ordinal_in :=
      packed_association_owner.io.registry_allocation_arrival_ordinal_out
    delivery_context_composition.io.packed_association_candidate_id_in :=
      packed_association_owner.io.registry_allocation_candidate_id_out
    packed_association_owner.io.registry_allocation_ack_in <>
      delivery_context_composition.io.packed_association_allocation_ack_out
    delivery_context_composition.io.r3_packed_write_in <> m2_p3.io.p3_packed_write_candidate_out
    delivery_context_composition.io.r5_append_in <> page_manager.io.append_candidate_out
    delivery_context_composition.io.r5_reclaim_in <> page_manager.io.reclaim_candidate_out
    r2_read_ingress.io.r3_pack_read_in <> delivery_context_composition.io.r3_pack_read_out
    r2_read_ingress.io.r3_direct_pending_in <> delivery_context_composition.io.r3_direct_pending_out
    StructuralTieOff.sink(delivery_context_composition.io.r5_s2_packed_out)
    r2_read_ingress.io.r5_s2_packed_in <> packed_s2_read_issue_adapter.io.candidate_out
    r2_write_ingress.io.r3_packed_write_in <> delivery_context_composition.io.r3_packed_write_out
    r2_write_ingress.io.r5_append_in <> delivery_context_composition.io.r5_append_out
    r2_write_ingress.io.r5_reclaim_in <> delivery_context_composition.io.r5_reclaim_out
    delivery_context_registry.io.allocation_in <> delivery_context_composition.io.registry_allocate_out
    delivery_context_composition.io.registry_allocation_ack_in <> delivery_context_registry.io.allocation_ack_out
    m2_p3.io.p3_packed_write_delivery_in <> typed_delivery_router.io.r3_packed_write_out
    direct_pending_read_endpoint.io.endpoint_active_in := direct_pending.io.direct_observe_active
    direct_pending_read_endpoint.io.endpoint_identity_in := direct_pending.io.direct_observe_identity
    direct_pending_read_endpoint.io.endpoint_generation_in := direct_pending.io.direct_observe_generation
    packed_s2_read_endpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
    packed_s2_read_endpoint.io.endpoint_fill_open_in := s2.io.s2_observe_fill_open
    // The producer's immutable work item owns the slot association; C9 uses
    // the same slot only as an owner-local observation coordinate.
    packed_s2_read_endpoint.io.endpoint_slot_in := packed_s2_read_producer.io.s2_fill_open_out.bits.s2_slot
    packed_s2_read_endpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
    packed_s2_read_endpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
    packed_s2_read_endpoint.io.endpoint_generation_in := s2.io.s2_observe_generation
    packed_terminal_bridge.io.endpoint_terminal_in <> packed_s2_read_endpoint.io.s2_fill_terminal_out
    packed_association_owner.io.terminal_in <> packed_terminal_bridge.io.association_terminal_out
    page_manager.io.p3_payload_durable_in <> m2_p3.io.p3_payload_durable_out
    m2_p3.io.descriptor_durability_prerequisite_in <> page_manager.io.descriptor_durability_prerequisite_out
    page_manager.io.metadata_publish_visibility_in <> m2_p3.io.metadata_publish_visibility_apply
    m2_p3.io.metadata_publish_visibility_ack_in <> page_manager.io.metadata_publish_visibility_ack
    lifecycle.io.metadata_publish_ack_in <> m2_p3.io.m2_publish_ack

    merge.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    status_collector.io.drain_collection_enable := lifecycle.io.drain_collection_enable
    status_collector.io.reclaim_drain_restart := lifecycle.io.reclaim_drain_restart
    status_collector.io.reclaim_final_drain_enable := lifecycle.io.reclaim_final_drain_enable
    status_collector.io.status_sources(0) <> core_memory.io.component_status_out
    status_collector.io.status_sources(1) <> arbiter.io.payload_drain_status_out
    status_collector.io.status_sources(2) <> arbiter.io.descriptor_drain_status_out
    status_collector.io.status_sources(3) <> m2_p3.io.component_status_out
    status_collector.io.status_sources(4) <> page_manager.io.component_status_out
    status_collector.io.status_sources(5) <> s2.io.component_status_out
    status_collector.io.status_sources(6) <> direct_pending.io.component_status_out
    status_collector.io.status_sources(7) <> merge.io.component_status_out
  }
}
