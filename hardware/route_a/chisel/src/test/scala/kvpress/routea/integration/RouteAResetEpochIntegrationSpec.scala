package kvpress.routea.integration

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteAS2GqaSourceWrapper}
import kvpress.routea.incremental.{RouteADirectPendingEndpointV1, RouteAPageManager}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL2.5.1 reset-epoch checks; no controller, numeric, or PPA model. */
final class RouteAResetEpochIntegrationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def driveR1Request(dut: RouteACoreMemIfV1, requestId: Int, incarnation: Int): Unit = {
    val request = dut.io.core_mem_req_in.bits
    request.transaction_identity.request_id.poke(requestId.U); request.transaction_identity.incarnation.poke(incarnation.U)
    request.request_kind.poke(p.coreMemoryReadRequestCode.U); request.destination.poke(0.U); request.address_ref.poke(0.U)
    request.expected_fragment_count.poke(1.U); request.fragment_index.poke(0.U); request.last.poke(true.B); request.data.poke(0.U)
  }

  private def driveR1Response(dut: RouteACoreMemIfV1, requestId: Int, incarnation: Int): Unit = {
    val response = dut.io.external_core_mem_if_v1.response.bits
    response.transaction_identity.request_id.poke(requestId.U); response.transaction_identity.incarnation.poke(incarnation.U)
    response.fragment_index.poke(0.U); response.last.poke(true.B); response.status.poke(p.coreMemoryOkStatusCode.U); response.data.poke(0x55.U)
  }

  private def initR1(dut: RouteACoreMemIfV1): Unit = {
    dut.io.core_mem_req_in.valid.poke(false.B); dut.io.core_mem_rsp.ready.poke(true.B); dut.io.r1_drain_permitted.poke(false.B)
    dut.io.component_status_out.ready.poke(true.B)
    dut.io.external_core_mem_if_v1.init_ack.valid.poke(false.B); dut.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(false.B)
    dut.io.external_core_mem_if_v1.request.ready.poke(true.B); dut.io.external_core_mem_if_v1.response.valid.poke(false.B)
    driveR1Request(dut, 0, 0); driveR1Response(dut, 0, 0)
  }

  private def acknowledgeR1Init(dut: RouteACoreMemIfV1): Unit = {
    dut.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(true.B)
    dut.io.external_core_mem_if_v1.init_ack.valid.poke(true.B); dut.io.external_core_mem_if_v1.init_ack.ready.expect(true.B)
    dut.clock.step(); dut.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)
  }

  it("clears an active R1 request on reset and consumes its delayed response outside the core") {
    simulate(new RouteACoreMemIfV1(p)) { dut =>
      initR1(dut); acknowledgeR1Init(dut)
      driveR1Request(dut, requestId = 1, incarnation = 2)
      dut.io.core_mem_req_in.valid.poke(true.B); dut.io.core_mem_req_in.ready.expect(true.B); dut.clock.step(); dut.io.core_mem_req_in.valid.poke(false.B)

      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B)
      dut.io.core_mem_req_in.ready.expect(false.B); dut.io.external_core_mem_if_v1.request.valid.expect(false.B)
      driveR1Response(dut, requestId = 1, incarnation = 2)
      dut.io.external_core_mem_if_v1.response.valid.poke(true.B)
      dut.io.core_mem_rsp.valid.expect(false.B); dut.io.external_core_mem_if_v1.response.ready.expect(true.B)
      dut.clock.step(); dut.io.external_core_mem_if_v1.response.valid.poke(false.B)

      acknowledgeR1Init(dut)
      driveR1Request(dut, requestId = 1, incarnation = 2)
      dut.io.core_mem_req_in.valid.poke(true.B); dut.io.core_mem_req_in.ready.expect(true.B)
    }
  }

  private def initR5(dut: RouteAPageManager): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.drain_collection_enable.poke(false.B); dut.io.reclaim_permit_in.valid.poke(false.B)
    dut.io.reclaim_permit_in.bits.transaction_identity.request_id.poke(0.U); dut.io.reclaim_permit_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.page_allocation_req_in.valid.poke(false.B); dut.io.page_allocation_rsp.ready.poke(true.B)
    dut.io.descriptor_location_request_in.valid.poke(false.B); dut.io.descriptor_location_grant_out.ready.poke(true.B)
    dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B); dut.io.metadata_publish_visibility_in.valid.poke(false.B)
    dut.io.metadata_publish_visibility_ack.ready.poke(true.B); dut.io.reclaim_candidate_out.ready.poke(true.B)
    dut.io.reclaim_delivery_in.valid.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
  }

  private def allocateAndPublishR5(dut: RouteAPageManager, tag: Int): Unit = {
    val allocation = dut.io.page_allocation_req_in.bits
    allocation.layer.poke(0.U); allocation.kv_head.poke(0.U); allocation.valid_records.poke(1.U); allocation.transaction_group_tag.poke(tag.U)
    dut.io.page_allocation_req_in.valid.poke(true.B); dut.io.page_allocation_req_in.ready.expect(true.B)
    dut.clock.step(); dut.io.page_allocation_req_in.valid.poke(false.B)
    val terminal = dut.io.descriptor_maintenance_terminal_in.bits
    terminal.kind.poke(RouteADescriptorOperationKind.NewPage.U); terminal.page_ref.page_id.poke(0.U); terminal.page_ref.generation.poke(0.U)
    terminal.transaction_group_tag.poke(tag.U); terminal.status.poke(p.coreMemoryOkStatusCode.U); terminal.r1_descriptor_durable.poke(true.B)
    dut.io.descriptor_maintenance_terminal_in.valid.poke(true.B); dut.io.descriptor_maintenance_terminal_in.ready.expect(true.B)
    dut.clock.step(); dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B)
    val visibility = dut.io.metadata_publish_visibility_in.bits
    visibility.page_ref.page_id.poke(0.U); visibility.page_ref.generation.poke(0.U); visibility.transaction_group_tag.poke(tag.U)
    dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(true.B)
    dut.clock.step(); dut.io.metadata_publish_visibility_in.valid.poke(false.B); dut.clock.step()
  }

  it("clears published R5 local reachability on reset and gates old descriptor facts until re-init") {
    simulate(new RouteAPageManager(p)) { dut =>
      initR5(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step(); dut.clock.step()
      allocateAndPublishR5(dut, tag = 1)

      dut.io.mem_init_done.poke(false.B); dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B)
      dut.io.page_allocation_req_in.valid.poke(true.B); dut.io.page_allocation_req_in.ready.expect(false.B)
      dut.io.descriptor_maintenance_terminal_in.valid.poke(true.B); dut.io.descriptor_maintenance_terminal_in.ready.expect(false.B)
      dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(false.B)
      dut.io.page_allocation_req_in.valid.poke(false.B); dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B); dut.io.metadata_publish_visibility_in.valid.poke(false.B)

      dut.io.mem_init_done.poke(true.B); dut.clock.step()
      allocateAndPublishR5(dut, tag = 0)
    }
  }

  private def initS2(dut: RouteAS2GqaSourceWrapper): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.s2_observe_slot.poke(0.U); dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.s2_fill_lease_request_in.valid.poke(false.B); dut.io.s2_fill_lease_out.ready.poke(true.B)
    dut.io.service_req_in.valid.poke(false.B); dut.io.s2_fill_open_in.valid.poke(false.B); dut.io.s2_payload_fragment_in.valid.poke(false.B)
    dut.io.s2_sidecar_fragment_in.valid.poke(false.B); dut.io.s2_fill_terminal_in.valid.poke(false.B); dut.io.s2_sidecar_complete_in.valid.poke(false.B)
    dut.io.s2_payload_read_req_in.valid.poke(false.B); dut.io.s2_payload_read_rsp_out.ready.poke(true.B)
    dut.io.s2_sidecar_read_req_in.valid.poke(false.B); dut.io.s2_sidecar_read_rsp_out.ready.poke(true.B)
    dut.io.gqa_consumer_commit_in.valid.poke(false.B); dut.io.s2_release_out.ready.poke(true.B)
  }

  private def openS2Fill(dut: RouteAS2GqaSourceWrapper, requestId: Int, page: Int): Unit = {
    val service = dut.io.service_req_in.bits
    service.transaction_identity.request_id.poke(requestId.U); service.transaction_identity.incarnation.poke(0.U)
    service.page_ref.page_id.poke(page.U); service.page_ref.generation.poke(0.U); service.s2_slot.poke(0.U)
    dut.io.service_req_in.valid.poke(true.B); dut.io.service_req_in.ready.expect(true.B); dut.clock.step(); dut.io.service_req_in.valid.poke(false.B)
    val open = dut.io.s2_fill_open_in.bits
    open.transaction_identity.request_id.poke(requestId.U); open.transaction_identity.incarnation.poke(0.U)
    open.page_ref.page_id.poke(page.U); open.page_ref.generation.poke(0.U); open.s2_slot.poke(0.U); open.source_generation.poke(1.U)
    open.expected_fragment_count.poke(1.U); open.expected_sidecar_records.poke(0.U); open.requires_sidecar.poke(false.B)
    dut.io.s2_fill_open_in.valid.poke(true.B); dut.io.s2_fill_open_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_fill_open_in.valid.poke(false.B)
  }

  private def initDirect(dut: RouteADirectPendingEndpointV1): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.pending_source_open_in.valid.poke(false.B); dut.io.direct_pending_record_terminal_in.valid.poke(false.B)
    dut.io.gqa_consumer_commit_in.valid.poke(false.B); dut.io.direct_release_out.ready.poke(true.B)
  }

  private def openDirect(dut: RouteADirectPendingEndpointV1, requestId: Int): Unit = {
    val open = dut.io.pending_source_open_in.bits
    open.transaction_identity.request_id.poke(requestId.U); open.transaction_identity.incarnation.poke(0.U)
    open.layer.poke(0.U); open.kv_head.poke(0.U); open.ordered_pending_descriptor_ref.poke(0.U); open.expected_generation_or_validity.poke(0.U)
    dut.io.pending_source_open_in.valid.poke(true.B); dut.io.pending_source_open_in.ready.expect(true.B); dut.clock.step(); dut.io.pending_source_open_in.valid.poke(false.B)
  }

  it("clears active S2/direct source associations and rejects old identity facts after reset") {
    simulate(new RouteAS2GqaSourceWrapper(p)) { dut =>
      initS2(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step(); openS2Fill(dut, requestId = 1, page = 3)
      dut.io.mem_init_done.poke(false.B); dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B)
      dut.io.s2_observe_state.expect(0.U)
      val stale = dut.io.s2_payload_fragment_in.bits
      stale.transaction_identity.request_id.poke(1.U); stale.transaction_identity.incarnation.poke(0.U); stale.s2_slot.poke(0.U)
      stale.source_generation.poke(1.U); stale.fragment_index.poke(0.U); stale.last.poke(true.B); stale.data.poke(0xff.U)
      dut.io.s2_payload_fragment_in.valid.poke(true.B); dut.io.s2_payload_fragment_in.ready.expect(false.B); dut.io.s2_payload_fragment_in.valid.poke(false.B)
      dut.io.mem_init_done.poke(true.B); dut.clock.step(); openS2Fill(dut, requestId = 2, page = 4)
      dut.io.s2_fill_open_in.bits.transaction_identity.request_id.poke(1.U); dut.io.s2_fill_open_in.bits.transaction_identity.incarnation.poke(0.U)
      dut.io.s2_fill_open_in.bits.page_ref.page_id.poke(3.U); dut.io.s2_fill_open_in.bits.page_ref.generation.poke(0.U)
      dut.io.s2_fill_open_in.bits.s2_slot.poke(0.U); dut.io.s2_fill_open_in.bits.source_generation.poke(1.U)
      dut.io.s2_fill_open_in.bits.expected_fragment_count.poke(1.U); dut.io.s2_fill_open_in.bits.expected_sidecar_records.poke(0.U); dut.io.s2_fill_open_in.bits.requires_sidecar.poke(false.B)
      dut.io.s2_fill_open_in.valid.poke(true.B); dut.io.s2_fill_open_in.ready.expect(false.B)
    }

    simulate(new RouteADirectPendingEndpointV1(p)) { dut =>
      initDirect(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step(); openDirect(dut, requestId = 3)
      dut.io.mem_init_done.poke(false.B); dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B)
      dut.io.direct_observe_active.expect(false.B)
      val stale = dut.io.direct_pending_record_terminal_in.bits
      stale.transaction_identity.request_id.poke(3.U); stale.transaction_identity.incarnation.poke(0.U); stale.endpoint_generation.poke(1.U)
      stale.ordinal.poke(0.U); stale.last.poke(true.B); stale.status.poke(p.coreMemoryOkStatusCode.U); stale.explicit_empty.poke(false.B)
      dut.io.direct_pending_record_terminal_in.valid.poke(true.B); dut.io.direct_pending_record_terminal_in.ready.expect(false.B); dut.io.direct_pending_record_terminal_in.valid.poke(false.B)
      dut.io.mem_init_done.poke(true.B); dut.clock.step(); openDirect(dut, requestId = 4)
      dut.io.direct_pending_record_terminal_in.valid.poke(true.B); dut.io.direct_pending_record_terminal_in.ready.expect(false.B)
    }
  }

  private def initTop(dut: RouteAInitDrainHarness): Unit = {
    dut.io.frontend_lifecycle_req.valid.poke(false.B); dut.io.runtime_retire_req.valid.poke(false.B)
    dut.io.attention_terminal_rsp.ready.poke(true.B); dut.io.session_retire_ack.ready.poke(true.B)
    dut.io.external_core_mem_if_v1.init_ack.valid.poke(false.B); dut.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(false.B)
    dut.io.external_core_mem_if_v1.request.ready.poke(true.B); dut.io.external_core_mem_if_v1.response.valid.poke(false.B)
    dut.io.external_core_mem_if_v1.response.bits.transaction_identity.request_id.poke(0.U)
    dut.io.external_core_mem_if_v1.response.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.external_core_mem_if_v1.response.bits.fragment_index.poke(0.U); dut.io.external_core_mem_if_v1.response.bits.last.poke(true.B)
    dut.io.external_core_mem_if_v1.response.bits.status.poke(p.coreMemoryOkStatusCode.U); dut.io.external_core_mem_if_v1.response.bits.data.poke(0.U)
    val frontend = dut.io.frontend_lifecycle_req.bits
    frontend.event_kind.poke(p.r6.sessionStartEventCode.U); frontend.session_id.poke(false.B); frontend.context_tokens.poke(32768.U)
    frontend.entry_id.poke(0.U); frontend.layer.poke(0.U); frontend.kv_head.poke(0.U); frontend.logical_position.poke(0.U); frontend.payload_ref.poke(0.U)
    frontend.disposition.poke(false.B); frontend.transaction_identity.request_id.poke(0.U); frontend.transaction_identity.incarnation.poke(0.U)
    frontend.admission_group_tag.poke(0.U); frontend.admission_member_ordinal.poke(0.U); frontend.admission_group_valid_records.poke(0.U)
    dut.io.runtime_retire_req.bits.session_id.poke(false.B); dut.io.runtime_retire_req.bits.transaction_identity.request_id.poke(0.U); dut.io.runtime_retire_req.bits.transaction_identity.incarnation.poke(0.U)
  }

  private def reinitializeTop(dut: RouteAInitDrainHarness): Unit = {
    dut.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(true.B)
    dut.io.external_core_mem_if_v1.init_ack.valid.poke(true.B); dut.io.external_core_mem_if_v1.init_ack.ready.expect(true.B)
    dut.clock.step(); dut.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)
    (0 until 12).foreach(_ => dut.clock.step())
  }

  it("requires a new R1 epoch acknowledgement and fresh R6 init collection after top-level destructive reset") {
    simulate(new RouteAInitDrainHarness(p)) { dut =>
      initTop(dut); reinitializeTop(dut)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
      dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)

      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(false.B)
      dut.io.frontend_lifecycle_req.valid.poke(false.B)
      dut.io.external_core_mem_if_v1.request.valid.expect(false.B)

      reinitializeTop(dut)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
    }
  }
}
