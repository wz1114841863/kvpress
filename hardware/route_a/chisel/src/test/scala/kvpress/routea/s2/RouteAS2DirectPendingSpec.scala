package kvpress.routea.s2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAS2GqaSourceWrapper
import kvpress.routea.incremental.RouteADirectPendingEndpointV1
import kvpress.routea.interfaces.RouteASourceKind
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL2.3 functional-storage and existing source-control checks; no macro, controller, or merge model. */
final class RouteAS2DirectPendingSpec extends AnyFunSpec with ChiselSim {
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

  private def initS2(dut: RouteAS2GqaSourceWrapper): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.s2_observe_slot.poke(0.U)
    dut.io.s2_fill_lease_request_in.valid.poke(false.B); dut.io.s2_fill_lease_out.ready.poke(true.B)
    dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.service_req_in.valid.poke(false.B); dut.io.s2_fill_open_in.valid.poke(false.B)
    dut.io.s2_payload_fragment_in.valid.poke(false.B); dut.io.s2_sidecar_fragment_in.valid.poke(false.B)
    dut.io.s2_fill_terminal_in.valid.poke(false.B); dut.io.s2_sidecar_complete_in.valid.poke(false.B)
    dut.io.s2_payload_read_req_in.valid.poke(false.B); dut.io.s2_payload_read_rsp_out.ready.poke(false.B)
    dut.io.s2_sidecar_read_req_in.valid.poke(false.B); dut.io.s2_sidecar_read_rsp_out.ready.poke(false.B)
    dut.io.gqa_consumer_commit_in.valid.poke(false.B); dut.io.s2_release_out.ready.poke(true.B)
    dut.io.mem_init_done.poke(true.B); dut.clock.step()
  }

  private def serviceSlot(dut: RouteAS2GqaSourceWrapper, rid: Int, page: Int): Unit = {
    val service = dut.io.service_req_in.bits
    service.transaction_identity.request_id.poke(rid.U); service.transaction_identity.incarnation.poke(0.U)
    service.page_ref.page_id.poke(page.U); service.page_ref.generation.poke(0.U); service.s2_slot.poke(0.U)
    dut.io.service_req_in.valid.poke(true.B); dut.io.service_req_in.ready.expect(true.B); dut.clock.step(); dut.io.service_req_in.valid.poke(false.B)
  }

  private def fillOnePacked(dut: RouteAS2GqaSourceWrapper, rid: Int, page: Int, generation: Int): Unit = {
    val open = dut.io.s2_fill_open_in.bits
    open.transaction_identity.request_id.poke(rid.U); open.transaction_identity.incarnation.poke(0.U)
    open.page_ref.page_id.poke(page.U); open.page_ref.generation.poke(0.U); open.s2_slot.poke(0.U)
    open.source_generation.poke(generation.U); open.expected_fragment_count.poke(1.U)
    open.expected_sidecar_records.poke(1.U); open.requires_sidecar.poke(true.B)
    dut.io.s2_fill_open_in.valid.poke(true.B); dut.io.s2_fill_open_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_fill_open_in.valid.poke(false.B)
    val terminal = dut.io.s2_fill_terminal_in.bits
    terminal.transaction_identity.request_id.poke(rid.U); terminal.transaction_identity.incarnation.poke(0.U)
    terminal.s2_slot.poke(0.U); terminal.source_generation.poke(generation.U); terminal.fragment_index.poke(0.U)
    terminal.last.poke(true.B); terminal.status.poke(p.coreMemoryOkStatusCode.U)
    // A matching terminal cannot make a slot READY before its payload has
    // actually arrived and been stored.
    dut.io.s2_fill_terminal_in.valid.poke(true.B); dut.io.s2_fill_terminal_in.ready.expect(false.B)
    dut.io.s2_fill_terminal_in.valid.poke(false.B)
    val payload = dut.io.s2_payload_fragment_in.bits
    payload.transaction_identity.request_id.poke(rid.U); payload.transaction_identity.incarnation.poke(0.U)
    payload.s2_slot.poke(0.U); payload.source_generation.poke(generation.U); payload.fragment_index.poke(0.U)
    payload.last.poke(true.B); payload.data.poke(0x5a.U)
    dut.io.s2_payload_fragment_in.valid.poke(true.B); dut.io.s2_payload_fragment_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_payload_fragment_in.valid.poke(false.B)
    dut.io.s2_fill_terminal_in.valid.poke(true.B); dut.io.s2_fill_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_fill_terminal_in.valid.poke(false.B)
    dut.io.s2_observe_state.expect(1.U)
    val sidecarFragment = dut.io.s2_sidecar_fragment_in.bits
    sidecarFragment.transaction_identity.request_id.poke(rid.U); sidecarFragment.transaction_identity.incarnation.poke(0.U)
    sidecarFragment.s2_slot.poke(0.U); sidecarFragment.source_generation.poke(generation.U)
    sidecarFragment.record_ordinal.poke(0.U); sidecarFragment.data.poke(0x1234.U)
    dut.io.s2_sidecar_fragment_in.valid.poke(true.B); dut.io.s2_sidecar_fragment_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_sidecar_fragment_in.valid.poke(false.B)
    val sidecar = dut.io.s2_sidecar_complete_in.bits
    sidecar.transaction_identity.request_id.poke(rid.U); sidecar.transaction_identity.incarnation.poke(0.U)
    sidecar.s2_slot.poke(0.U); sidecar.source_generation.poke(generation.U)
    dut.io.s2_sidecar_complete_in.valid.poke(true.B); dut.io.s2_sidecar_complete_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_sidecar_complete_in.valid.poke(false.B)
    dut.io.s2_observe_state.expect(2.U)
  }

  private def expectS2Storage(dut: RouteAS2GqaSourceWrapper, rid: Int, generation: Int): Unit = {
    val payloadRead = dut.io.s2_payload_read_req_in.bits
    payloadRead.transaction_identity.request_id.poke(rid.U); payloadRead.transaction_identity.incarnation.poke(0.U)
    payloadRead.s2_slot.poke(0.U); payloadRead.source_generation.poke(generation.U); payloadRead.fragment_index.poke(0.U)
    dut.io.s2_payload_read_req_in.valid.poke(true.B); dut.io.s2_payload_read_req_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_payload_read_req_in.valid.poke(false.B)
    dut.io.s2_payload_read_rsp_out.valid.expect(true.B); dut.io.s2_payload_read_rsp_out.bits.data.expect(0x5a.U)
    dut.io.s2_payload_read_rsp_out.ready.poke(false.B); dut.clock.step(); dut.io.s2_payload_read_rsp_out.bits.data.expect(0x5a.U)
    dut.io.s2_payload_read_rsp_out.ready.poke(true.B); dut.clock.step(); dut.io.s2_payload_read_rsp_out.ready.poke(false.B)
    val sidecarRead = dut.io.s2_sidecar_read_req_in.bits
    sidecarRead.transaction_identity.request_id.poke(rid.U); sidecarRead.transaction_identity.incarnation.poke(0.U)
    sidecarRead.s2_slot.poke(0.U); sidecarRead.source_generation.poke(generation.U); sidecarRead.record_ordinal.poke(0.U)
    dut.io.s2_sidecar_read_req_in.valid.poke(true.B); dut.io.s2_sidecar_read_req_in.ready.expect(true.B); dut.clock.step(); dut.io.s2_sidecar_read_req_in.valid.poke(false.B)
    dut.io.s2_sidecar_read_rsp_out.valid.expect(true.B); dut.io.s2_sidecar_read_rsp_out.bits.data.expect(0x1234.U)
    dut.io.s2_sidecar_read_rsp_out.ready.poke(false.B); dut.clock.step(); dut.io.s2_sidecar_read_rsp_out.bits.data.expect(0x1234.U)
    dut.io.s2_sidecar_read_rsp_out.ready.poke(true.B); dut.clock.step(); dut.io.s2_sidecar_read_rsp_out.ready.poke(false.B)
  }

  private def commitS2(dut: RouteAS2GqaSourceWrapper, rid: Int, generation: Int, consumer: Int): Unit = {
    val commit = dut.io.gqa_consumer_commit_in.bits
    commit.transaction_identity.request_id.poke(rid.U); commit.transaction_identity.incarnation.poke(0.U)
    commit.source_instance.source_kind.poke(2.U); commit.source_instance.instance_coordinate.poke(0.U)
    commit.source_instance.generation.poke(generation.U); commit.consumer_id.poke(consumer.U)
    dut.io.gqa_consumer_commit_in.valid.poke(true.B); dut.io.gqa_consumer_commit_in.ready.expect(true.B); dut.clock.step(); dut.io.gqa_consumer_commit_in.valid.poke(false.B)
  }

  it("requires packed sidecar plus four commits before stable S2 release, then rejects stale reuse traffic") {
    simulate(new RouteAS2GqaSourceWrapper(p)) { dut =>
      initS2(dut); serviceSlot(dut, 1, 3); dut.io.s2_observe_generation.expect(1.U)
      fillOnePacked(dut, 1, 3, 1)
      expectS2Storage(dut, 1, 1)
      (0 until 3).foreach(commitS2(dut, 1, 1, _)); dut.io.s2_release_out.valid.expect(false.B)
      commitS2(dut, 1, 1, 3); dut.io.s2_release_out.valid.expect(true.B)
      dut.io.s2_release_out.ready.poke(false.B); dut.clock.step(); dut.io.s2_release_out.valid.expect(true.B)
      dut.io.s2_release_out.ready.poke(true.B); dut.clock.step(); dut.io.s2_observe_state.expect(0.U)
      serviceSlot(dut, 2, 4); dut.io.s2_observe_generation.expect(2.U)
      val stale = dut.io.s2_fill_terminal_in.bits
      stale.transaction_identity.request_id.poke(1.U); stale.transaction_identity.incarnation.poke(0.U)
      stale.s2_slot.poke(0.U); stale.source_generation.poke(1.U); stale.fragment_index.poke(0.U); stale.last.poke(true.B); stale.status.poke(p.coreMemoryOkStatusCode.U)
      dut.io.s2_fill_terminal_in.valid.poke(true.B); dut.io.s2_fill_terminal_in.ready.expect(false.B); dut.io.s2_observe_state.expect(1.U)
      dut.io.s2_fill_terminal_in.valid.poke(false.B)
      val stalePayload = dut.io.s2_payload_fragment_in.bits
      stalePayload.transaction_identity.request_id.poke(1.U); stalePayload.transaction_identity.incarnation.poke(0.U)
      stalePayload.s2_slot.poke(0.U); stalePayload.source_generation.poke(1.U); stalePayload.fragment_index.poke(0.U)
      stalePayload.last.poke(true.B); stalePayload.data.poke(0xff.U)
      dut.io.s2_payload_fragment_in.valid.poke(true.B); dut.io.s2_payload_fragment_in.ready.expect(false.B)
      dut.io.s2_observe_state.expect(1.U)
    }
  }

  private def initDirect(dut: RouteADirectPendingEndpointV1): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.pending_source_open_in.valid.poke(false.B)
    dut.io.pending_source_open_ack_out.ready.poke(true.B)
    dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.direct_pending_record_terminal_in.valid.poke(false.B); dut.io.gqa_consumer_commit_in.valid.poke(false.B)
    dut.io.direct_release_out.ready.poke(true.B); dut.io.mem_init_done.poke(true.B); dut.clock.step()
  }

  private def openDirect(dut: RouteADirectPendingEndpointV1, rid: Int): Unit = {
    val open = dut.io.pending_source_open_in.bits
    open.transaction_identity.request_id.poke(rid.U); open.transaction_identity.incarnation.poke(0.U)
    open.pending_instance.source_kind.poke(RouteASourceKind.Pending.U); open.pending_instance.instance_coordinate.poke(0.U); open.pending_instance.generation.poke(1.U)
    open.layer.poke(0.U); open.kv_head.poke(0.U); open.ordered_pending_descriptor_ref.poke(0.U); open.expected_generation_or_validity.poke(0.U)
    dut.io.pending_source_open_in.valid.poke(true.B); dut.io.pending_source_open_in.ready.expect(true.B); dut.clock.step(); dut.io.pending_source_open_in.valid.poke(false.B)
  }

  private def directTerminal(dut: RouteADirectPendingEndpointV1, rid: Int, generation: Int, ordinal: Int, last: Boolean, fault: Boolean = false): Unit = {
    val terminal = dut.io.direct_pending_record_terminal_in.bits
    terminal.transaction_identity.request_id.poke(rid.U); terminal.transaction_identity.incarnation.poke(0.U)
    terminal.endpoint_generation.poke(generation.U); terminal.ordinal.poke(ordinal.U); terminal.last.poke(last.B)
    terminal.status.poke((if (fault) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U); terminal.explicit_empty.poke(false.B)
    dut.io.direct_pending_record_terminal_in.valid.poke(true.B); dut.io.direct_pending_record_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.direct_pending_record_terminal_in.valid.poke(false.B)
  }

  private def commitDirect(dut: RouteADirectPendingEndpointV1, rid: Int, generation: Int, consumer: Int): Unit = {
    val commit = dut.io.gqa_consumer_commit_in.bits
    commit.transaction_identity.request_id.poke(rid.U); commit.transaction_identity.incarnation.poke(0.U)
    commit.source_instance.source_kind.poke(1.U); commit.source_instance.instance_coordinate.poke(0.U)
    commit.source_instance.generation.poke(generation.U); commit.consumer_id.poke(consumer.U)
    dut.io.gqa_consumer_commit_in.valid.poke(true.B); dut.io.gqa_consumer_commit_in.ready.expect(true.B); dut.clock.step(); dut.io.gqa_consumer_commit_in.valid.poke(false.B)
  }

  it("preserves direct FIFO ordinal and four-commit release while rejecting stale old-incarnation terminal") {
    simulate(new RouteADirectPendingEndpointV1(p)) { dut =>
      initDirect(dut); openDirect(dut, 3); dut.io.direct_observe_generation.expect(1.U)
      val wrong = dut.io.direct_pending_record_terminal_in.bits
      wrong.transaction_identity.request_id.poke(3.U); wrong.transaction_identity.incarnation.poke(0.U); wrong.endpoint_generation.poke(1.U)
      wrong.ordinal.poke(1.U); wrong.last.poke(false.B); wrong.status.poke(p.coreMemoryOkStatusCode.U); wrong.explicit_empty.poke(false.B)
      dut.io.direct_pending_record_terminal_in.valid.poke(true.B); dut.io.direct_pending_record_terminal_in.ready.expect(false.B); dut.io.direct_pending_record_terminal_in.valid.poke(false.B)
      directTerminal(dut, 3, 1, 0, last = false); directTerminal(dut, 3, 1, 1, last = true)
      (0 until 4).foreach(commitDirect(dut, 3, 1, _)); dut.io.direct_release_out.valid.expect(true.B)
      dut.io.direct_release_out.ready.poke(false.B); dut.clock.step(); dut.io.direct_release_out.valid.expect(true.B)
      dut.io.direct_release_out.ready.poke(true.B); dut.clock.step(); dut.io.direct_observe_active.expect(false.B)
      openDirect(dut, 4); dut.io.direct_observe_generation.expect(2.U)
      wrong.transaction_identity.request_id.poke(3.U); wrong.endpoint_generation.poke(1.U); wrong.ordinal.poke(0.U); wrong.last.poke(true.B)
      dut.io.direct_pending_record_terminal_in.valid.poke(true.B); dut.io.direct_pending_record_terminal_in.ready.expect(false.B); dut.io.direct_observe_active.expect(true.B)
    }
  }

  it("fails closed on direct terminal fault without a release") {
    simulate(new RouteADirectPendingEndpointV1(p)) { dut =>
      initDirect(dut); openDirect(dut, 5); directTerminal(dut, 5, 1, 0, last = true, fault = true)
      dut.io.direct_release_out.valid.expect(false.B)
    }
  }
}
