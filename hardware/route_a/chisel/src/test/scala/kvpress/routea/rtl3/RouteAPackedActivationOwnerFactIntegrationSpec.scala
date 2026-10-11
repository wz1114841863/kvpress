package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAS2GqaSourceWrapper
import kvpress.routea.incremental.{RouteAPackedReadActivationBinder, RouteAPageManager}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL3.8.1 owner-fact integration only.  R5 and S2 produce their real local
  * grants; the harness exposes no descriptor-address or lease stimulus.
  */
private final class RouteAPackedActivationOwnerFactHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val allocation = Flipped(RouteAChannels.page_allocation_req(p))
    val descriptor_terminal = Flipped(RouteAChannels.descriptor_maintenance_terminal(p))
    val visibility = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val accepted_plan = Flipped(RouteAChannels.source_completion_plan(p))
    val publication = Flipped(RouteAChannels.publication_commit_observation(p))
    val demand = RouteAChannels.packed_source_demand(p)
    val authorization = RouteAChannels.publication_read_authorization(p)
    val descriptor = RouteAChannels.descriptor_location_grant(p)
    val lease = RouteAChannels.s2_fill_lease(p)
    val s2_selected_state = Output(UInt(3.W))
  })

  val r5 = Module(new RouteAPageManager(p))
  val s2 = Module(new RouteAS2GqaSourceWrapper(p))
  val binder = Module(new RouteAPackedReadActivationBinder(p))

  r5.io.mem_init_done := io.mem_init_done
  r5.io.drain_collection_enable := false.B
  StructuralTieOff.source(r5.io.reclaim_permit_in)
  StructuralTieOff.sink(r5.io.reclaim_candidate_out)
  StructuralTieOff.source(r5.io.reclaim_delivery_in)
  StructuralTieOff.sink(r5.io.allocator_release_out)
  r5.io.page_allocation_req_in <> io.allocation
  r5.io.page_allocation_rsp.ready := true.B
  StructuralTieOff.sink(r5.io.append_candidate_out)
  StructuralTieOff.source(r5.io.append_delivery_in)
  StructuralTieOff.source(r5.io.p3_payload_durable_in)
  StructuralTieOff.sink(r5.io.descriptor_durability_prerequisite_out)
  r5.io.descriptor_maintenance_terminal_in <> io.descriptor_terminal
  r5.io.metadata_publish_visibility_in <> io.visibility
  r5.io.metadata_publish_visibility_ack.ready := true.B
  StructuralTieOff.sink(r5.io.component_status_out)

  s2.io.mem_init_done := io.mem_init_done
  s2.io.drain_collection_enable := false.B
  StructuralTieOff.source(s2.io.service_req_in)
  StructuralTieOff.source(s2.io.s2_fill_open_in)
  StructuralTieOff.source(s2.io.s2_payload_fragment_in)
  StructuralTieOff.source(s2.io.s2_sidecar_fragment_in)
  StructuralTieOff.source(s2.io.s2_fill_terminal_in)
  StructuralTieOff.source(s2.io.s2_sidecar_complete_in)
  StructuralTieOff.source(s2.io.s2_payload_read_req_in)
  StructuralTieOff.sink(s2.io.s2_payload_read_rsp_out)
  StructuralTieOff.source(s2.io.s2_sidecar_read_req_in)
  StructuralTieOff.sink(s2.io.s2_sidecar_read_rsp_out)
  StructuralTieOff.source(s2.io.gqa_consumer_commit_in)
  StructuralTieOff.sink(s2.io.s2_release_out)
  StructuralTieOff.sink(s2.io.component_status_out)

  binder.io.mem_init_done := io.mem_init_done
  binder.io.accepted_plan_in <> io.accepted_plan
  binder.io.publication_commit_in <> io.publication
  r5.io.descriptor_location_request_in <> binder.io.descriptor_location_request_out
  binder.io.descriptor_grant_in <> r5.io.descriptor_location_grant_out
  s2.io.s2_fill_lease_request_in <> binder.io.s2_fill_lease_request_out
  binder.io.s2_fill_lease_in <> s2.io.s2_fill_lease_out
  io.demand <> binder.io.demand_out
  io.authorization <> binder.io.publication_authorization_out
  io.descriptor <> binder.io.descriptor_grant_out
  io.lease <> binder.io.s2_fill_lease_out

  s2.io.s2_observe_slot := 1.U
  io.s2_selected_state := s2.io.s2_observe_state
}

final class RouteAPackedActivationOwnerFactIntegrationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 20, coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 10,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 2,
    transactionGroupTagWidth = 3, p3StageGenerationWidth = 2, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 3, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(d: RouteAPackedActivationOwnerFactHarness): Unit = {
    d.io.mem_init_done.poke(false.B)
    d.io.allocation.valid.poke(false.B); d.io.descriptor_terminal.valid.poke(false.B); d.io.visibility.valid.poke(false.B)
    d.io.accepted_plan.valid.poke(false.B); d.io.publication.valid.poke(false.B)
    d.io.demand.ready.poke(false.B); d.io.authorization.ready.poke(false.B)
    d.io.descriptor.ready.poke(false.B); d.io.lease.ready.poke(false.B)
    d.clock.step(); d.io.mem_init_done.poke(true.B); d.clock.step()
  }

  private def publishPage0(d: RouteAPackedActivationOwnerFactHarness, records: Int = 2): Unit = {
    val a = d.io.allocation.bits
    a.layer.poke(0.U); a.kv_head.poke(0.U); a.valid_records.poke(records.U); a.transaction_group_tag.poke(6.U)
    d.io.allocation.valid.poke(true.B); d.io.allocation.ready.expect(true.B); d.clock.step(); d.io.allocation.valid.poke(false.B)
    val t = d.io.descriptor_terminal.bits
    t.kind.poke(RouteADescriptorOperationKind.NewPage.U); t.page_ref.page_id.poke(0.U); t.page_ref.generation.poke(0.U)
    t.transaction_group_tag.poke(6.U); t.status.poke(p.coreMemoryOkStatusCode.U); t.r1_descriptor_durable.poke(true.B)
    d.io.descriptor_terminal.valid.poke(true.B); d.io.descriptor_terminal.ready.expect(true.B); d.clock.step(); d.io.descriptor_terminal.valid.poke(false.B)
    val v = d.io.visibility.bits
    v.page_ref.page_id.poke(0.U); v.page_ref.generation.poke(0.U); v.transaction_group_tag.poke(6.U)
    d.io.visibility.valid.poke(true.B); d.io.visibility.ready.expect(true.B); d.clock.step(); d.io.visibility.valid.poke(false.B)
    d.clock.step() // consume R5 visibility acknowledgement and mark descriptor readable
  }

  private def planAndPublication(
      d: RouteAPackedActivationOwnerFactHarness,
      pageId: Int = 0,
      pageGeneration: Int = 0,
      sourceGeneration: Int = 1,
  ): Unit = {
    val plan = d.io.accepted_plan.bits
    plan.transaction_identity.request_id.poke(3.U); plan.transaction_identity.incarnation.poke(1.U)
    plan.source_presence.poke(4.U)
    plan.hot_instance.source_kind.poke(0.U); plan.hot_instance.instance_coordinate.poke(0.U); plan.hot_instance.generation.poke(0.U)
    plan.pending_instance.source_kind.poke(1.U); plan.pending_instance.instance_coordinate.poke(0.U); plan.pending_instance.generation.poke(0.U)
    plan.packed_instance.source_kind.poke(2.U); plan.packed_instance.instance_coordinate.poke(1.U); plan.packed_instance.generation.poke(sourceGeneration.U)
    d.io.accepted_plan.valid.poke(true.B); d.io.accepted_plan.ready.expect(true.B); d.clock.step(); d.io.accepted_plan.valid.poke(false.B)
    val pub = d.io.publication.bits
    pub.p3_layer.poke(0.U); pub.p3_stage_generation.poke(1.U); pub.page_ref.page_id.poke(pageId.U)
    pub.page_ref.generation.poke(pageGeneration.U); pub.transaction_group_tag.poke(6.U); pub.valid_records.poke(2.U)
    d.io.publication.valid.poke(true.B); d.io.publication.ready.expect(true.B); d.clock.step(); d.io.publication.valid.poke(false.B)
  }

  it("joins actual R5 descriptor and S2 lease owner responses without test-supplied handles or slot defaults") {
    simulate(new RouteAPackedActivationOwnerFactHarness(p)) { d =>
      init(d); publishPage0(d); planAndPublication(d)
      // Requests and owner responses cross independently; allow the finite
      // handshake sequence to settle before observing the materialized set.
      // R5-first ordering deliberately adds one owner round trip before S2
      // reservation: descriptor request/grant, lease request/grant, evaluate,
      // then emit.  Keep every output backpressured while that sequence settles.
      d.clock.step(6)
      d.io.demand.valid.expect(true.B); d.io.authorization.valid.expect(true.B)
      d.io.descriptor.valid.expect(true.B); d.io.lease.valid.expect(true.B)
      d.io.demand.bits.page_ref.page_id.expect(0.U); d.io.demand.bits.page_ref.generation.expect(0.U)
      d.io.descriptor.bits.payload_handle_or_address.expect(0.U)
      d.io.descriptor.bits.sidecar_handle_or_address.expect(32768.U)
      d.io.descriptor.bits.valid_records.expect(2.U); d.io.descriptor.bits.live_reference_held.expect(true.B)
      d.io.lease.bits.s2_slot.expect(1.U); d.io.lease.bits.source_generation.expect(1.U)
      d.io.lease.bits.requires_sidecar.expect(true.B)
      d.io.s2_selected_state.expect(1.U) // S2 StateFilling after owner-local reservation.
      d.io.demand.ready.poke(true.B); d.io.authorization.ready.poke(true.B)
      d.io.descriptor.ready.poke(true.B); d.io.lease.ready.poke(true.B); d.clock.step()
    }
  }

  it("does not materialize or reserve S2 when the R5 page generation is stale") {
    simulate(new RouteAPackedActivationOwnerFactHarness(p)) { d =>
      init(d); publishPage0(d); planAndPublication(d, pageGeneration = 1, sourceGeneration = 1)
      d.clock.step(6)
      d.io.demand.valid.expect(false.B); d.io.authorization.valid.expect(false.B)
      d.io.descriptor.valid.expect(false.B); d.io.lease.valid.expect(false.B)
      d.io.s2_selected_state.expect(0.U) // stale R5 page cannot consume an S2 lease.
    }
  }

  it("does not materialize when S2 cannot validate the selected next generation") {
    simulate(new RouteAPackedActivationOwnerFactHarness(p)) { d =>
      init(d); publishPage0(d); planAndPublication(d, sourceGeneration = 2)
      d.clock.step(6)
      d.io.demand.valid.expect(false.B); d.io.authorization.valid.expect(false.B)
      d.io.descriptor.valid.expect(false.B); d.io.lease.valid.expect(false.B)
      d.io.s2_selected_state.expect(0.U)
    }
  }

  it("rejects an out-of-range page ID instead of aliasing an allocated R5 entry") {
    simulate(new RouteAPackedActivationOwnerFactHarness(p)) { d =>
      init(d); publishPage0(d); planAndPublication(d, pageId = 8)
      d.clock.step(6)
      d.io.demand.valid.expect(false.B); d.io.authorization.valid.expect(false.B)
      d.io.descriptor.valid.expect(false.B); d.io.lease.valid.expect(false.B)
      d.io.s2_selected_state.expect(0.U)
    }
  }
}
