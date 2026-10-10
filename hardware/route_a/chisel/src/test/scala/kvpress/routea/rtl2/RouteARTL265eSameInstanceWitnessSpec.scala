package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter, RouteADeliveryContextRegistry, RouteAPackedS2ReadEndpoint, RouteAPackedS2ReadProducer, RouteAReadEndpointDemultiplexer, RouteAReadIssueCandidateAdapter, RouteAR2ReadIngressMerge, RouteAS2GqaSourceWrapper, RouteASourceServicePacketAdapter, RouteATypedDeliveryRouter}
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAMergeBoundary, RouteAPackedReadAssociationOwner}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAM2GroupMember, RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.rtl3.{RouteARTL36bFixture, RouteARTL36bFunctionalTerminalFixture, RouteARTL36bPackedFixtureProvider, RouteARTL36cAllocationSidecarTap, RouteARTL36cSidecarFixture, RouteARTL36cSidecarFixtureTransport}
import kvpress.routea.top.RouteAComponentStatusCollector
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.6.5e's single-instance, verification-only retained-path witness.
  *
  * The R3/R5/R2/R1 publication child is the RTL2.6.5a.2 real pack-read path.
  * Its accepted publication and pending->packed observation are joined only by
  * the existing explicit verification association to an actual S2 owner.  The
  * outer R6 owns terminal/retirement and returns its reclaim permit to that
  * same child R5 instance.  No top-level source plan, metadata authority,
  * terminal, or reclaim result is manufactured here.
  */
final class RouteARTL265eSameInstanceWitnessHarness(
    p: RouteASkeletonParameters,
    useRtl36bFunctionalFixtures: Boolean = false,
    useRtl36c2FunctionalSource: Boolean = false,
) extends Module {
  val io = IO(new Bundle {
    val memInitDone = Input(Bool())
    val r5Allocate = Flipped(RouteAChannels.page_allocation_req(p))
    val r5AllocationRsp = RouteAChannels.page_allocation_rsp(p)
    val p3Claim = Flipped(RouteAChannels.p3_claim(p))
    val admissionContext = Flipped(RouteAChannels.admission_context(p))
    val admissionAuthority = Flipped(RouteAChannels.r6_authority_transition(p))
    val packReadWork = Flipped(RouteAChannels.p3_pack_read_work(p))
    val p3Sidecar = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val external = new CoreMemoryExternalPort(p)
    // RTL3.6-C2 test-only post-publication packed-read path.  These are
    // immutable verification facts, not a replacement R3/R5 scheduler or
    // descriptor owner.  They are present only to join the real publication
    // observation to the existing RTL3.2 association owner.
    val c2Demand = Flipped(RouteAChannels.packed_source_demand(p))
    val c2Publication = Flipped(RouteAChannels.publication_read_authorization(p))
    val c2Descriptor = Flipped(RouteAChannels.descriptor_location_grant(p))
    val c2Lease = Flipped(RouteAChannels.s2_fill_lease(p))
    val c2External = new CoreMemoryExternalPort(p)
    val m2MemberRequest = RouteAChannels.m2_group_member_req(p)
    val m2MemberResponse = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val m2PublicationCandidate = RouteAChannels.metadata_publish_req(p)
    val m2PublicationRequest = Flipped(RouteAChannels.metadata_publish_req(p))
    val verificationAssociation = Flipped(chisel3.util.Decoupled(new VerificationPackedS2Association(p)))

    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val directStatus = Flipped(RouteAChannels.component_status(p))
    val runtimeRetire = Flipped(RouteAChannels.runtime_retire_req)
    val sourcePlan = Flipped(RouteAChannels.source_completion_plan(p))
    val s2FillOpen = Flipped(RouteAChannels.s2_fill_open(p))
    val s2Payload = Flipped(RouteAChannels.s2_payload_fragment(p))
    val s2Terminal = Flipped(RouteAChannels.s2_fill_terminal(p))
    val packedOffer = Flipped(RouteAChannels.source_service_partial_offer(p))
    val packedFragment = Flipped(RouteAChannels.source_service_value_fragment(p))
    val resultStub = Flipped(RouteAChannels.r4_result_stub)
    val numericFault = Flipped(RouteAChannels.r4_numeric_fault)
    val attentionTerminal = RouteAChannels.attention_terminal_rsp
    val retireAck = RouteAChannels.session_retire_ack
    val p3State = Output(UInt(3.W))
    val s2Ready = Output(Bool())
    // Test-only observability for RTL3.6-B.  It neither contributes to an
    // architecture owner nor exists in the production composition top.
    val functionalFixturePacketsAccepted = Output(Bool())
    val functionalFixtureProviderComplete = Output(Bool())
    val c2SidecarFixtureComplete = Output(Bool())
    val c2SidecarFixtureFaulted = Output(Bool())
  })

  val publication = Module(new RouteARTL265a2PackReadPublicationHarness(p))
  val r6 = Module(new RouteALifecycleAdapter(p))
  val collector = Module(new RouteAComponentStatusCollector(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  val packets = Module(new RouteASourceServicePacketAdapter(p))
  val merge = Module(new RouteAMergeBoundary(p))
  val publicationAssociation = Module(new RouteARTL26PublicationS2Association(p))
  val terminalAssociation = Module(new RouteATerminalRetireAssociation)
  val fixture = if (useRtl36bFunctionalFixtures) Some(RouteARTL36bFixture.load) else None
  val packetFixtureProvider = fixture.map(value => Module(new RouteARTL36bPackedFixtureProvider(p, value)))
  val terminalFixtureProvider = fixture.map(value => Module(new RouteARTL36bFunctionalTerminalFixture(p, value)))
  val c2Association = if (useRtl36c2FunctionalSource) Some(Module(new RouteAPackedReadAssociationOwner(p))) else None
  val c2Producer = if (useRtl36c2FunctionalSource) Some(Module(new RouteAPackedS2ReadProducer(p))) else None
  val c2IssueAdapter = if (useRtl36c2FunctionalSource) Some(Module(new RouteAReadIssueCandidateAdapter(p))) else None
  val c2ReadIngress = if (useRtl36c2FunctionalSource) Some(Module(new RouteAR2ReadIngressMerge(p))) else None
  val c2R2 = if (useRtl36c2FunctionalSource) Some(Module(new RouteACoreSideArbiter(p))) else None
  val c2R1 = if (useRtl36c2FunctionalSource) Some(Module(new RouteACoreMemIfV1(p))) else None
  val c2Registry = if (useRtl36c2FunctionalSource) Some(Module(new RouteADeliveryContextRegistry(p))) else None
  val c2Router = if (useRtl36c2FunctionalSource) Some(Module(new RouteATypedDeliveryRouter(p))) else None
  val c2EndpointDemux = if (useRtl36c2FunctionalSource) Some(Module(new RouteAReadEndpointDemultiplexer(p))) else None
  val c2Endpoint = if (useRtl36c2FunctionalSource) Some(Module(new RouteAPackedS2ReadEndpoint(p))) else None
  val c2SidecarTap = if (useRtl36c2FunctionalSource) Some(Module(new RouteARTL36cAllocationSidecarTap(p))) else None
  val c2SidecarTransport = if (useRtl36c2FunctionalSource) Some(Module(new RouteARTL36cSidecarFixtureTransport(
    p, RouteARTL36cSidecarFixture(BigInt(0xaa), Vector(BigInt(0x900)))))) else None

  publication.io.mem_init_done := io.memInitDone
  publication.io.r5_allocate <> io.r5Allocate
  io.r5AllocationRsp <> publication.io.r5_allocation_rsp
  publication.io.p3_claim <> io.p3Claim
  publication.io.admission_context <> io.admissionContext
  publication.io.admission_authority <> io.admissionAuthority
  publication.io.pack_read_work <> io.packReadWork
  publication.io.p3_sidecar <> io.p3Sidecar
  publication.io.external <> io.external
  io.m2MemberRequest <> publication.io.m2_member_request
  publication.io.m2_member_response <> io.m2MemberResponse
  io.m2PublicationCandidate <> publication.io.m2_publication_candidate
  publication.io.m2_publication_request <> io.m2PublicationRequest
  publication.io.publication_member.ready := true.B
  publication.io.publication_ack.ready := true.B
  io.p3State := publication.io.p3_state

  r6.io.frontend_lifecycle_req <> io.frontend
  r6.io.component_status_in <> collector.io.component_status_out
  collector.io.drain_collection_enable := r6.io.drain_collection_enable
  collector.io.reclaim_drain_restart := r6.io.reclaim_drain_restart
  collector.io.reclaim_final_drain_enable := r6.io.reclaim_final_drain_enable
  publication.io.drain_collection_enable := r6.io.drain_collection_enable
  publication.io.reclaim_maintenance_enable := r6.io.reclaim_maintenance_enable
  publication.io.r1_drain_permitted := collector.io.r1_drain_permitted
  publication.io.reclaim_permit <> r6.io.reclaim_permit_out
  r6.io.r5_reclaim_complete_in := publication.io.reclaim_complete
  terminalAssociation.io.runtime_retire_in <> io.runtimeRetire
  r6.io.runtime_retire_req <> terminalAssociation.io.runtime_retire_out
  terminalAssociation.io.terminal_in <> r6.io.attention_terminal_rsp
  io.attentionTerminal <> terminalAssociation.io.terminal_out
  io.retireAck <> r6.io.session_retire_ack
  r6.io.source_completion_plan_in <> io.sourcePlan
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

  collector.io.status_sources(0) <> publication.io.r1_status
  collector.io.status_sources(1) <> publication.io.r2_payload_status
  collector.io.status_sources(2) <> publication.io.r2_descriptor_status
  collector.io.status_sources(3) <> publication.io.r3_status
  collector.io.status_sources(4) <> publication.io.r5_status
  collector.io.status_sources(5) <> s2.io.component_status_out
  collector.io.status_sources(6) <> io.directStatus
  collector.io.status_sources(7) <> merge.io.component_status_out

  publicationAssociation.io.publicationCommitIn <> publication.io.publication_commit
  publicationAssociation.io.authorityTransitionIn <> publication.io.authority_transition
  publicationAssociation.io.verificationAssociationIn <> io.verificationAssociation
  s2.io.mem_init_done := io.memInitDone
  s2.io.drain_collection_enable := r6.io.drain_collection_enable
  s2.io.service_req_in <> publicationAssociation.io.s2ServiceOut
  if (useRtl36c2FunctionalSource) {
    val association = c2Association.get
    val producer = c2Producer.get
    val issueAdapter = c2IssueAdapter.get
    val readIngress = c2ReadIngress.get
    val r2 = c2R2.get
    val r1 = c2R1.get
    val registry = c2Registry.get
    val router = c2Router.get
    val endpointDemux = c2EndpointDemux.get
    val endpoint = c2Endpoint.get
    val tap = c2SidecarTap.get
    val sidecar = c2SidecarTransport.get

    association.io.mem_init_done := r1.io.r1_init_complete
    association.io.demand_in <> io.c2Demand
    association.io.publication_authorization_in <> io.c2Publication
    association.io.descriptor_grant_in <> io.c2Descriptor
    association.io.s2_fill_lease_in <> io.c2Lease
    association.io.invalidation_in.valid := false.B
    association.io.invalidation_in.bits := 0.U.asTypeOf(new PackedReadInvalidation)
    association.io.registry_allocate_out <> tap.io.allocation_in
    tap.io.registry_allocation_out <> registry.io.allocation_in
    tap.io.sidecar_obligation_out <> sidecar.io.obligation_in
    association.io.registry_allocation_ack_in <> registry.io.allocation_ack_out
    association.io.packed_s2_work_out <> producer.io.work_in
    StructuralTieOff.source(association.io.terminal_in)
    StructuralTieOff.sink(association.io.release_observation_out)

    producer.io.s2_fill_open_out <> s2.io.s2_fill_open_in
    producer.io.read_issue_out <> issueAdapter.io.read_issue_in
    readIngress.io.r5_s2_packed_in <> issueAdapter.io.candidate_out
    StructuralTieOff.source(readIngress.io.r3_pack_read_in)
    StructuralTieOff.source(readIngress.io.r3_direct_pending_in)
    r2.io.read_candidate_in <> readIngress.io.candidate_out
    StructuralTieOff.source(r2.io.candidate_in)
    r2.io.drain_collection_enable := false.B
    r2.io.reclaim_maintenance_enable := false.B
    r1.io.core_mem_req_in <> r2.io.core_mem_req
    r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
    r1.io.external_core_mem_if_v1 <> io.c2External
    r1.io.r1_drain_permitted := false.B
    StructuralTieOff.sink(r1.io.component_status_out)
    StructuralTieOff.sink(r2.io.payload_drain_status_out)
    StructuralTieOff.sink(r2.io.descriptor_drain_status_out)

    registry.io.mem_init_done := r1.io.r1_init_complete
    registry.io.resolve_in <> r2.io.source_delivery_out
    router.io.resolved_in <> registry.io.resolved_out
    registry.io.release_in <> router.io.release_out
    endpointDemux.io.resolved_in <> router.io.read_fragment_out
    endpoint.io.resolved_fragment_in <> endpointDemux.io.packed_s2_out
    StructuralTieOff.sink(endpointDemux.io.p3_pack_read_out)
    StructuralTieOff.sink(endpointDemux.io.direct_pending_out)
    StructuralTieOff.sink(router.io.r3_packed_write_out)
    StructuralTieOff.sink(router.io.r5_append_out)
    StructuralTieOff.sink(router.io.r5_reclaim_out)

    endpoint.io.endpoint_filling_in := s2.io.s2_observe_filling
    endpoint.io.endpoint_fill_open_in := s2.io.s2_observe_fill_open
    endpoint.io.endpoint_slot_in := 0.U
    endpoint.io.endpoint_identity_in := s2.io.s2_observe_identity
    endpoint.io.endpoint_page_ref_in := s2.io.s2_observe_page_ref
    endpoint.io.endpoint_generation_in := s2.io.s2_observe_generation
    s2.io.s2_payload_fragment_in <> endpoint.io.s2_payload_fragment_out
    s2.io.s2_fill_terminal_in <> endpoint.io.s2_fill_terminal_out
    sidecar.io.observed_filling := s2.io.s2_observe_filling
    sidecar.io.observed_fill_open := s2.io.s2_observe_fill_open
    sidecar.io.observed_identity := s2.io.s2_observe_identity
    sidecar.io.observed_page_ref := s2.io.s2_observe_page_ref
    sidecar.io.observed_generation := s2.io.s2_observe_generation
    s2.io.s2_sidecar_fragment_in <> sidecar.io.sidecar_fragment_out
    s2.io.s2_sidecar_complete_in <> sidecar.io.sidecar_complete_out
    io.s2FillOpen.ready := false.B
    io.s2Payload.ready := false.B
    io.s2Terminal.ready := false.B
    io.c2SidecarFixtureComplete := sidecar.io.complete
    io.c2SidecarFixtureFaulted := sidecar.io.faulted
  } else {
    s2.io.s2_fill_open_in <> io.s2FillOpen
    s2.io.s2_payload_fragment_in <> io.s2Payload
    StructuralTieOff.source(s2.io.s2_sidecar_fragment_in)
    s2.io.s2_fill_terminal_in <> io.s2Terminal
    StructuralTieOff.source(s2.io.s2_sidecar_complete_in)
    io.c2Demand.ready := false.B
    io.c2Publication.ready := false.B
    io.c2Descriptor.ready := false.B
    io.c2Lease.ready := false.B
    io.c2External.init_ack.ready := false.B
    io.c2External.request.valid := false.B
    io.c2External.request.bits := 0.U.asTypeOf(new CoreMemoryRequest(p))
    io.c2External.response.ready := false.B
    io.c2SidecarFixtureComplete := false.B
    io.c2SidecarFixtureFaulted := false.B
  }
  StructuralTieOff.source(s2.io.s2_payload_read_req_in)
  StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
  StructuralTieOff.source(s2.io.s2_sidecar_read_req_in)
  StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
  s2.io.s2_observe_slot := 0.U
  io.s2Ready := s2.io.s2_observe_available

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
  StructuralTieOff.source(packets.io.hot_fragment_in)
  StructuralTieOff.source(packets.io.pending_fragment_in)
  if (useRtl36bFunctionalFixtures) {
    val provider = packetFixtureProvider.get
    provider.io.availability_in := packets.io.packed_available_in
    packets.io.packed_offer_in <> provider.io.packed_offer_out
    packets.io.packed_fragment_in <> provider.io.packed_fragment_out
    // The legacy manual ingress remains an IO for the historical witness but
    // is explicitly unavailable in this fixture-selected elaboration.
    io.packedOffer.ready := false.B
    io.packedFragment.ready := false.B
    io.functionalFixtureProviderComplete := provider.io.complete
  } else {
    packets.io.packed_offer_in <> io.packedOffer
    packets.io.packed_fragment_in <> io.packedFragment
    io.functionalFixtureProviderComplete := false.B
  }

  merge.io.drain_collection_enable := r6.io.drain_collection_enable
  StructuralTieOff.source(merge.io.source_partial_in)
  merge.io.r4_partial_header_in <> packets.io.r4_partial_header_out
  merge.io.r4_source_instance_in <> packets.io.r4_source_instance_out
  merge.io.r4_value_fragment_in <> packets.io.r4_value_fragment_out
  if (useRtl36bFunctionalFixtures) {
    val provider = terminalFixtureProvider.get
    merge.io.r4_accepted_partial_packet_out <> provider.io.accepted_packet_in
    provider.io.active_merge_observation := merge.io.r4_active_merge_observation
    merge.io.r4_result_stub_in <> provider.io.r4_result_stub_out
    merge.io.r4_numeric_fault_in <> provider.io.r4_numeric_fault_out
    io.resultStub.ready := false.B
    io.numericFault.ready := false.B
    io.functionalFixturePacketsAccepted := provider.io.all_packets_accepted
  } else {
    merge.io.r4_accepted_partial_packet_out.ready := true.B
    merge.io.r4_result_stub_in <> io.resultStub
    merge.io.r4_numeric_fault_in <> io.numericFault
    io.functionalFixturePacketsAccepted := false.B
  }
  merge.io.merge_req_in <> r6.io.merge_req
  r6.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
  s2.io.gqa_consumer_commit_in.valid := merge.io.consumer_partial_commit.valid &&
    merge.io.consumer_partial_commit.bits.source_instance.source_kind === RouteASourceKind.Packed.U
  s2.io.gqa_consumer_commit_in.bits := merge.io.consumer_partial_commit.bits
  merge.io.consumer_partial_commit.ready := s2.io.gqa_consumer_commit_in.ready
}

final class RouteARTL265eSameInstanceWitnessSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=32, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)
  private val packReadEligibility = (1 << RouteAR2PredicateBits.FifoPredecessor) | (1 << RouteAR2PredicateBits.Ownership) | (1 << RouteAR2PredicateBits.SourceCredit) | (1 << RouteAR2PredicateBits.DestinationReady) | (1 << RouteAR2PredicateBits.PendingAuthoritative) | (1 << RouteAR2PredicateBits.P3StageReadyOwned)
  private def id(x: TransactionIdentity, request: Int): Unit = { x.request_id.poke(request.U); x.incarnation.poke(0.U) }
  private def instance(x: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = { x.source_kind.poke(kind.U); x.instance_coordinate.poke(coordinate.U); x.generation.poke(generation.U) }

  private def init(d: RouteARTL265eSameInstanceWitnessHarness): Unit = {
    d.io.memInitDone.poke(false.B); d.io.r5Allocate.valid.poke(false.B); d.io.r5AllocationRsp.ready.poke(true.B); d.io.p3Claim.valid.poke(false.B); d.io.admissionContext.valid.poke(false.B); d.io.admissionAuthority.valid.poke(false.B); d.io.packReadWork.valid.poke(false.B); d.io.p3Sidecar.valid.poke(false.B)
    d.io.m2MemberRequest.ready.poke(false.B); d.io.m2MemberResponse.valid.poke(false.B); d.io.m2PublicationCandidate.ready.poke(false.B); d.io.m2PublicationRequest.valid.poke(false.B); d.io.verificationAssociation.valid.poke(false.B)
    d.io.frontend.valid.poke(false.B); d.io.directStatus.valid.poke(false.B); d.io.runtimeRetire.valid.poke(false.B); d.io.sourcePlan.valid.poke(false.B); d.io.s2FillOpen.valid.poke(false.B); d.io.s2Payload.valid.poke(false.B); d.io.s2Terminal.valid.poke(false.B); d.io.packedOffer.valid.poke(false.B); d.io.packedFragment.valid.poke(false.B); d.io.resultStub.valid.poke(false.B); d.io.numericFault.valid.poke(false.B); d.io.resultStub.bits.consumer_id.poke(0.U); d.io.numericFault.bits.consumer_id.poke(0.U); d.io.attentionTerminal.ready.poke(false.B); d.io.retireAck.ready.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B); d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B); id(d.io.external.response.bits.transaction_identity,0); d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B); d.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.external.response.bits.data.poke(0.U)
    d.io.c2Demand.valid.poke(false.B); d.io.c2Publication.valid.poke(false.B); d.io.c2Descriptor.valid.poke(false.B); d.io.c2Lease.valid.poke(false.B)
    d.io.c2External.init_ack.valid.poke(false.B); d.io.c2External.request.ready.poke(false.B); d.io.c2External.response.valid.poke(false.B); d.io.c2External.init_ack.bits.adapter_epoch_ready.poke(true.B); id(d.io.c2External.response.bits.transaction_identity,0); d.io.c2External.response.bits.fragment_index.poke(0.U); d.io.c2External.response.bits.last.poke(true.B); d.io.c2External.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.c2External.response.bits.data.poke(0.U)
    d.io.directStatus.bits.acknowledgement_name.poke(0.U); d.io.directStatus.bits.asserted.poke(true.B)
    d.io.memInitDone.poke(true.B); d.io.external.init_ack.valid.poke(true.B); d.io.c2External.init_ack.valid.poke(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B); d.io.c2External.init_ack.valid.poke(false.B)
  }

  private def waitRequest(d: RouteARTL265eSameInstanceWitnessHarness, kind: Int, index: Int): Unit = { var n=0; while(!d.io.external.request.valid.peek().litToBoolean && n<128){d.clock.step();n+=1}; require(n<128,s"timed out waiting for request kind=$kind index=$index"); d.io.external.request.bits.request_kind.expect(kind.U); d.io.external.request.bits.fragment_index.expect(index.U); d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B) }
  private def response(d: RouteARTL265eSameInstanceWitnessHarness, request: Int, fragment: Int, last: Boolean, fault: Boolean=false): Unit = { val x=d.io.external.response.bits; id(x.transaction_identity,request); x.fragment_index.poke(fragment.U); x.last.poke(last.B); x.status.poke((if(fault)p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U); x.data.poke((0x100+fragment).U); d.io.external.response.valid.poke(true.B); var n=0; while(!d.io.external.response.ready.peek().litToBoolean&&n<128){d.clock.step();n+=1}; require(n<128,"timed out waiting for response"); d.clock.step(); d.io.external.response.valid.poke(false.B); d.clock.step(2) }
  private def waitC2Request(d: RouteARTL265eSameInstanceWitnessHarness, index: Int): Unit = { var n=0; while(!d.io.c2External.request.valid.peek().litToBoolean && n<128){d.clock.step();n+=1}; require(n<128,s"timed out waiting for C2 read index=$index"); d.io.c2External.request.bits.request_kind.expect(p.coreMemoryReadRequestCode.U); d.io.c2External.request.bits.fragment_index.expect(index.U); d.io.c2External.request.ready.poke(true.B); d.clock.step(); d.io.c2External.request.ready.poke(false.B) }
  private def c2Response(d: RouteARTL265eSameInstanceWitnessHarness, fragment: Int, last: Boolean): Unit = { val x=d.io.c2External.response.bits; id(x.transaction_identity,3); x.fragment_index.poke(fragment.U); x.last.poke(last.B); x.status.poke(p.coreMemoryOkStatusCode.U); x.data.poke((0x400+fragment).U); d.io.c2External.response.valid.poke(true.B); var n=0; while(!d.io.c2External.response.ready.peek().litToBoolean&&n<128){d.clock.step();n+=1}; require(n<128,"timed out waiting for C2 response"); d.clock.step(); d.io.c2External.response.valid.poke(false.B); d.clock.step(2) }
  private def admitAndRead(d: RouteARTL265eSameInstanceWitnessHarness): Unit = {
    val a=d.io.r5Allocate.bits; a.layer.poke(0.U);a.kv_head.poke(0.U);a.valid_records.poke(1.U);a.transaction_group_tag.poke(1.U);d.io.r5Allocate.valid.poke(true.B);d.io.r5Allocate.ready.expect(true.B);d.clock.step();d.io.r5Allocate.valid.poke(false.B)
    val c=d.io.p3Claim.bits;c.layer.poke(0.U);c.kv_head.poke(0.U);c.owner.poke(0.U);c.page_ref.page_id.poke(0.U);c.page_ref.generation.poke(0.U);c.valid_records.poke(1.U);c.requires_tail_link.poke(false.B);c.transaction_group_tag.poke(1.U);d.io.p3Claim.valid.poke(true.B);d.io.p3Claim.ready.expect(true.B);d.clock.step();d.io.p3Claim.valid.poke(false.B)
    val x=d.io.admissionContext.bits;x.entry_id.poke(0.U);x.layer.poke(0.U);x.kv_head.poke(0.U);x.logical_position.poke(0.U);x.payload_ref.poke(55.U);x.transaction_group_tag.poke(1.U);x.group_member_ordinal.poke(0.U);x.group_valid_records.poke(1.U)
    val h=d.io.admissionAuthority.bits;h.entry_id.poke(0.U);h.from_authority.poke(RouteAAuthorityStateCode.Hot.U);h.to_authority.poke(RouteAAuthorityStateCode.Pending.U);h.transaction_group_tag.poke(1.U);d.io.admissionContext.valid.poke(true.B);d.io.admissionAuthority.valid.poke(true.B);d.io.admissionContext.ready.expect(true.B);d.clock.step();d.io.admissionContext.valid.poke(false.B);d.io.admissionAuthority.valid.poke(false.B)
    val s=d.io.p3Sidecar.bits;s.layer.poke(0.U);s.stage_generation.poke(1.U);s.record_ordinal.poke(0.U);s.payload_ref.poke(55.U);s.logical_position.poke(0.U);d.io.p3Sidecar.valid.poke(true.B);d.io.p3Sidecar.ready.expect(true.B);d.clock.step();d.io.p3Sidecar.valid.poke(false.B)
    val w=d.io.packReadWork.bits;w.layer.poke(0.U);w.stage_generation.poke(1.U);w.member_ordinal.poke(0.U);w.payload_ref.poke(55.U);id(w.transaction_identity,3);w.arrival_ordinal.poke(0.U);w.candidate_id.poke(0.U);w.eligibility_snapshot.poke(packReadEligibility.U);w.payload_handle_or_address.poke(55.U);w.destination_endpoint.poke(0.U);w.source_generation.poke(1.U);d.io.packReadWork.valid.poke(true.B);waitRequest(d,p.coreMemoryReadRequestCode,0);d.io.packReadWork.valid.poke(false.B)
    (0 until 8).foreach(i=>response(d,3,i,i==7));d.io.p3State.expect(3.U);waitRequest(d,p.coreMemoryWriteRequestCode,0);(0 until 8).foreach(i=>waitRequest(d,p.coreMemoryWriteDataCode,i));response(d,0,0,last=true);d.io.p3State.expect(5.U);waitRequest(d,p.coreMemoryWriteRequestCode,0);waitRequest(d,p.coreMemoryWriteDataCode,0);response(d,0,0,last=true)
  }
  private def publish(d: RouteARTL265eSameInstanceWitnessHarness): Unit = { def member(m:Int):Unit={var n=0;while(!d.io.m2MemberRequest.valid.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,"timed out M2 member");d.io.m2MemberRequest.bits.member.expect(m.U);d.io.m2MemberRequest.ready.poke(true.B);d.clock.step();d.io.m2MemberRequest.ready.poke(false.B);val r=d.io.m2MemberResponse.bits;r.layer.poke(0.U);r.stage_generation.poke(1.U);r.transaction_group_tag.poke(1.U);r.member.poke(m.U);r.status.poke(p.coreMemoryOkStatusCode.U);d.io.m2MemberResponse.valid.poke(true.B);d.io.m2MemberResponse.ready.expect(true.B);d.clock.step();d.io.m2MemberResponse.valid.poke(false.B)};member(RouteAM2GroupMember.HeadControlRmw);member(RouteAM2GroupMember.SpanOwnerRmw);var n=0;while(!d.io.m2PublicationCandidate.valid.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,"timed out publication candidate");d.io.m2PublicationCandidate.ready.poke(true.B);d.clock.step();d.io.m2PublicationCandidate.ready.poke(false.B);val r=d.io.m2PublicationRequest.bits;r.transaction_group_tag.poke(1.U);r.p3_layer.poke(0.U);r.p3_stage_generation.poke(1.U);d.io.m2PublicationRequest.valid.poke(true.B);d.io.m2PublicationRequest.ready.expect(true.B);d.clock.step();d.io.m2PublicationRequest.valid.poke(false.B) }
  private def frontend(d: RouteARTL265eSameInstanceWitnessHarness,event:Int,request:Int):Unit={val x=d.io.frontend.bits;x.event_kind.poke(event.U);x.session_id.poke(false.B);x.context_tokens.poke(32768.U);x.entry_id.poke(0.U);x.layer.poke(0.U);x.kv_head.poke(0.U);x.logical_position.poke(0.U);x.payload_ref.poke(0.U);x.disposition.poke(false.B);id(x.transaction_identity,request);x.admission_group_tag.poke(0.U);x.admission_member_ordinal.poke(0.U);x.admission_group_valid_records.poke(1.U);d.io.frontend.valid.poke(true.B);var n=0;while(!d.io.frontend.ready.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,"timed out frontend");d.clock.step();d.io.frontend.valid.poke(false.B)}
  private def directStatus(d: RouteARTL265eSameInstanceWitnessHarness, code:Int):Unit={d.io.directStatus.bits.acknowledgement_name.poke(code.U);d.io.directStatus.bits.asserted.poke(true.B);d.io.directStatus.valid.poke(true.B);var n=0;while(!d.io.directStatus.ready.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,s"timed out direct status $code");d.clock.step();d.io.directStatus.valid.poke(false.B)}
  private def serviceAndTerminal(d: RouteARTL265eSameInstanceWitnessHarness, rtl36bFunctionalFixtures:Boolean=false, rtl36c2FunctionalSource:Boolean=false):Unit={
    frontend(d,p.r6.sessionStartEventCode,0);frontend(d,p.r6.attentionServiceEventCode,3)
    val plan=d.io.sourcePlan.bits;id(plan.transaction_identity,3);plan.source_presence.poke(4.U);instance(plan.hot_instance,0,0,0);instance(plan.pending_instance,1,0,0);instance(plan.packed_instance,2,0,1);d.io.sourcePlan.valid.poke(true.B);var n=0;while(!d.io.sourcePlan.ready.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,"timed out plan");d.clock.step();d.io.sourcePlan.valid.poke(false.B)
    val a=d.io.verificationAssociation.bits;id(a.transaction_identity,3);a.page_ref.page_id.poke(1.U);a.page_ref.generation.poke(0.U);a.transaction_group_tag.poke(1.U);a.valid_records.poke(1.U);a.s2_slot.poke(0.U);a.source_generation.poke(1.U);d.io.verificationAssociation.valid.poke(true.B);d.io.verificationAssociation.ready.expect(false.B);d.io.verificationAssociation.valid.poke(false.B)
    a.page_ref.page_id.poke(0.U);d.io.verificationAssociation.valid.poke(true.B);n=0;while(!d.io.verificationAssociation.ready.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,"timed out association");d.clock.step();d.io.verificationAssociation.valid.poke(false.B);d.clock.step(2)
    if (rtl36c2FunctionalSource) {
      // This is an already-published S2-packed read, not the earlier R3
      // pending-to-P3 pack_read class.  Its R2 class contract therefore uses
      // the common read bits plus PackedMetadataPublished (bits 0..4).
      val demand = d.io.c2Demand.bits; id(demand.transaction_identity,3); demand.page_ref.page_id.poke(0.U); demand.page_ref.generation.poke(0.U); demand.arrival_ordinal.poke(0.U); demand.candidate_id.poke(0.U); demand.eligibility_snapshot.poke(0x1f.U); demand.destination_endpoint.poke(0.U)
      d.io.c2Demand.valid.poke(true.B); d.io.c2Demand.ready.expect(true.B); d.clock.step(); d.io.c2Demand.valid.poke(false.B)
      val publication = d.io.c2Publication.bits; id(publication.transaction_identity,3); publication.page_ref.page_id.poke(0.U); publication.page_ref.generation.poke(0.U); publication.transaction_group_tag.poke(1.U); publication.valid_records.poke(1.U); publication.packed_authoritative.poke(true.B)
      d.io.c2Publication.valid.poke(true.B); d.io.c2Publication.ready.expect(true.B); d.clock.step(); d.io.c2Publication.valid.poke(false.B)
      val descriptor = d.io.c2Descriptor.bits; id(descriptor.transaction_identity,3); descriptor.page_ref.page_id.poke(0.U); descriptor.page_ref.generation.poke(0.U); descriptor.payload_handle_or_address.poke(0x99.U); descriptor.sidecar_handle_or_address.poke(0xaa.U); descriptor.valid_records.poke(1.U); descriptor.sidecar_records.poke(1.U); descriptor.live_reference_held.poke(true.B)
      d.io.c2Descriptor.valid.poke(true.B); d.io.c2Descriptor.ready.expect(true.B); d.clock.step(); d.io.c2Descriptor.valid.poke(false.B)
      val lease = d.io.c2Lease.bits; id(lease.transaction_identity,3); lease.page_ref.page_id.poke(0.U); lease.page_ref.generation.poke(0.U); lease.s2_slot.poke(0.U); lease.source_generation.poke(1.U); lease.requires_sidecar.poke(true.B)
      d.io.c2Lease.valid.poke(true.B); d.io.c2Lease.ready.expect(true.B); d.clock.step(); d.io.c2Lease.valid.poke(false.B)
      waitC2Request(d, 0); (0 until 8).foreach(i => c2Response(d, i, i == 7))
      var readyWait=0; while(!d.io.s2Ready.peek().litToBoolean && readyWait<128){d.clock.step();readyWait+=1}; require(readyWait<128,"timed out C2 S2 READY"); d.io.c2SidecarFixtureFaulted.expect(false.B); d.io.c2SidecarFixtureComplete.expect(true.B)
    } else {
      val o=d.io.s2FillOpen.bits;id(o.transaction_identity,3);o.page_ref.page_id.poke(0.U);o.page_ref.generation.poke(0.U);o.s2_slot.poke(0.U);o.source_generation.poke(1.U);o.expected_fragment_count.poke(1.U);o.expected_sidecar_records.poke(0.U);o.requires_sidecar.poke(false.B);d.io.s2FillOpen.valid.poke(true.B);d.io.s2FillOpen.ready.expect(true.B);d.clock.step();d.io.s2FillOpen.valid.poke(false.B)
      val q=d.io.s2Payload.bits;id(q.transaction_identity,3);q.s2_slot.poke(0.U);q.source_generation.poke(1.U);q.fragment_index.poke(0.U);q.last.poke(true.B);q.data.poke(0.U);d.io.s2Payload.valid.poke(true.B);d.io.s2Payload.ready.expect(true.B);d.clock.step();d.io.s2Payload.valid.poke(false.B);val t=d.io.s2Terminal.bits;id(t.transaction_identity,3);t.s2_slot.poke(0.U);t.source_generation.poke(1.U);t.fragment_index.poke(0.U);t.last.poke(true.B);t.status.poke(p.coreMemoryOkStatusCode.U);d.io.s2Terminal.valid.poke(true.B);d.io.s2Terminal.ready.expect(true.B);d.clock.step();d.io.s2Terminal.valid.poke(false.B);d.io.s2Ready.expect(true.B)
    }
    if (!rtl36bFunctionalFixtures) {
      (0 until 4).foreach{c=>val header=(BigInt(2)<<64)|(BigInt(c)<<66)|(BigInt(1)<<69)|(BigInt(8)<<70);val offer=d.io.packedOffer.bits;id(offer.transaction_identity,3);instance(offer.source_instance,2,0,1);offer.consumer_id.poke(c.U);offer.r4_header.poke(header.U);offer.partial_present.poke(true.B);d.io.packedOffer.valid.poke(true.B);d.io.packedOffer.ready.expect(true.B);d.clock.step();d.io.packedOffer.valid.poke(false.B);d.clock.step();(0 until 8).foreach{i=>val f=d.io.packedFragment.bits;id(f.transaction_identity,3);instance(f.source_instance,2,0,1);f.consumer_id.poke(c.U);f.fragment_index.poke(i.U);f.last.poke((i==7).B);f.data.poke((c*8+i).U);d.io.packedFragment.valid.poke(true.B);d.io.packedFragment.ready.expect(true.B);d.clock.step();d.io.packedFragment.valid.poke(false.B)};d.clock.step(2)}
      (0 until 4).foreach { consumer =>
        id(d.io.resultStub.bits.transaction_identity, 3)
        d.io.resultStub.bits.consumer_id.poke(consumer.U)
        d.io.resultStub.bits.normalized_value.poke(0.U)
        d.io.resultStub.valid.poke(true.B)
        n = 0
        while (!d.io.resultStub.ready.peek().litToBoolean && n < 128) { d.clock.step(); n += 1 }
        require(n < 128, s"timed out result stub consumer=$consumer")
        d.clock.step()
        d.io.resultStub.valid.poke(false.B)
      }
    }
    n=0;while(!d.io.attentionTerminal.valid.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,"timed out terminal");if(rtl36bFunctionalFixtures){d.io.functionalFixtureProviderComplete.expect(true.B);d.io.functionalFixturePacketsAccepted.expect(true.B)};d.io.attentionTerminal.bits.transaction_identity.request_id.expect(3.U);d.io.attentionTerminal.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U);d.clock.step();d.io.attentionTerminal.valid.expect(true.B);d.io.attentionTerminal.bits.transaction_identity.request_id.expect(3.U);d.io.attentionTerminal.ready.poke(true.B);d.clock.step();d.io.attentionTerminal.ready.poke(false.B)
  }
  private def retireAndReclaim(d: RouteARTL265eSameInstanceWitnessHarness):Unit={val r=d.io.runtimeRetire.bits;r.session_id.poke(false.B);id(r.transaction_identity,3);d.io.runtimeRetire.valid.poke(true.B);var n=0;while(!d.io.runtimeRetire.ready.peek().litToBoolean&&n<128){d.clock.step();n+=1};require(n<128,"timed out retire");d.clock.step();d.io.runtimeRetire.valid.poke(false.B);directStatus(d,p.r6.directPendingDrainedStatusCode);waitRequest(d,p.coreMemoryWriteRequestCode,0);waitRequest(d,p.coreMemoryWriteDataCode,0);response(d,0,0,last=true);n=0;while(!d.io.retireAck.valid.peek().litToBoolean&&n<256){d.clock.step();n+=1};require(n<256,"timed out retire ack");d.io.retireAck.bits.transaction_identity.request_id.expect(3.U);d.io.retireAck.ready.poke(true.B);d.clock.step();d.io.retireAck.ready.poke(false.B)}

  private def resetAndReinitializeC2(d: RouteARTL265eSameInstanceWitnessHarness): Unit = {
    d.io.memInitDone.poke(false.B)
    d.reset.poke(true.B); d.clock.step(); d.reset.poke(false.B)
    // A response from the old C2 R1 epoch is never an initialization fact.
    // R1 may consume an unmatched external carrier to drain it, but it must
    // suppress it rather than emit a core response or mutate new-epoch state.
    id(d.io.c2External.response.bits.transaction_identity, 3)
    d.io.c2External.response.bits.fragment_index.poke(0.U); d.io.c2External.response.bits.last.poke(true.B)
    d.io.c2External.response.bits.status.poke(p.coreMemoryOkStatusCode.U); d.io.c2External.response.bits.data.poke(0xdead.U)
    d.io.c2External.response.valid.poke(true.B); d.io.c2External.response.ready.expect(true.B)
    d.clock.step(); d.io.c2External.response.valid.poke(false.B)
    d.io.memInitDone.poke(true.B)
    d.io.external.init_ack.valid.poke(true.B); d.io.c2External.init_ack.valid.poke(true.B)
    d.io.external.init_ack.ready.expect(true.B); d.io.c2External.init_ack.ready.expect(true.B)
    d.clock.step(); d.io.external.init_ack.valid.poke(false.B); d.io.c2External.init_ack.valid.poke(false.B)
  }

  it("keeps one real R3 pack-read/publication, S2 terminal, and same-R5 durable reclaim in one Chisel instance") { simulate(new RouteARTL265eSameInstanceWitnessHarness(p)) { d => init(d); admitAndRead(d); publish(d); serviceAndTerminal(d); retireAndReclaim(d) } }
  it("replays the static Python functional-provider/R4-oracle fixture through the same R3, R4, R6, and R5 instance") { simulate(new RouteARTL265eSameInstanceWitnessHarness(p, useRtl36bFunctionalFixtures=true)) { d => init(d); admitAndRead(d); publish(d); serviceAndTerminal(d, rtl36bFunctionalFixtures=true); retireAndReclaim(d) } }
  it("composes real publication, C1 typed source delivery, static functional terminal, and same-R5 reclaim in one instance") { simulate(new RouteARTL265eSameInstanceWitnessHarness(p, useRtl36bFunctionalFixtures=true, useRtl36c2FunctionalSource=true)) { d => init(d); admitAndRead(d); publish(d); serviceAndTerminal(d, rtl36bFunctionalFixtures=true, rtl36c2FunctionalSource=true); retireAndReclaim(d) } }
  it("rejects a stale C2 response until both post-reset R1 epochs reinitialize before the composed path restarts") { simulate(new RouteARTL265eSameInstanceWitnessHarness(p, useRtl36bFunctionalFixtures=true, useRtl36c2FunctionalSource=true)) { d => init(d); resetAndReinitializeC2(d); admitAndRead(d); publish(d); serviceAndTerminal(d, rtl36bFunctionalFixtures=true, rtl36c2FunctionalSource=true); retireAndReclaim(d) } }
}
