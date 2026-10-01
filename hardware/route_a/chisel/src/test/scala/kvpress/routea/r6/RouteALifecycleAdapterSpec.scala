package kvpress.routea.r6

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteALifecycleAdapter
import kvpress.routea.interfaces.RouteAAuthorityStateCode
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL1.5 directed R6 control checks; no source mux, payload, timing, or PPA model. */
final class RouteALifecycleAdapterSpec extends AnyFunSpec with ChiselSim {
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

  private def driveFrontend(
    dut: RouteALifecycleAdapter,
    event: Int,
    entry: Int = 0,
    layer: Int = 0,
    head: Int = 0,
    position: Int = 0,
    retain: Boolean = false,
    rid: Int = 0,
    incarnation: Int = 0,
    contextTokens: Int = 0,
  ): Unit = {
    val bits = dut.io.frontend_lifecycle_req.bits
    bits.event_kind.poke(event.U); bits.session_id.poke(false.B); bits.context_tokens.poke(contextTokens.U)
    bits.entry_id.poke(entry.U); bits.layer.poke(layer.U); bits.kv_head.poke(head.U); bits.logical_position.poke(position.U)
    bits.payload_ref.poke(position.U); bits.disposition.poke(retain.B)
    bits.transaction_identity.request_id.poke(rid.U); bits.transaction_identity.incarnation.poke(incarnation.U)
    bits.admission_group_tag.poke(1.U); bits.admission_member_ordinal.poke(0.U)
    bits.admission_group_valid_records.poke(1.U)
  }

  private def init(dut: RouteALifecycleAdapter): Unit = {
    dut.io.frontend_lifecycle_req.valid.poke(false.B); dut.io.runtime_retire_req.valid.poke(false.B)
    dut.io.component_status_in.valid.poke(false.B); dut.io.authority_transition_in.valid.poke(false.B)
    dut.io.merge_ready_in.valid.poke(false.B); dut.io.merge_terminal_in.valid.poke(false.B)
    dut.io.source_completion_plan_in.valid.poke(false.B)
    dut.io.hot_source_release_in.valid.poke(false.B); dut.io.pending_source_release_in.valid.poke(false.B); dut.io.packed_source_release_in.valid.poke(false.B)
    dut.io.hot_control_out.ready.poke(true.B); dut.io.authority_transition_out.ready.poke(true.B)
    dut.io.admission_context_out.ready.poke(true.B)
    dut.io.merge_req.ready.poke(true.B); dut.io.attention_terminal_rsp.ready.poke(true.B)
    dut.io.session_retire_ack.ready.poke(true.B); dut.io.s2_service_req.ready.poke(true.B)
    dut.io.reclaim_permit_out.ready.poke(true.B)
    dut.io.direct_pending_open.ready.poke(true.B); dut.io.metadata_publish_req.ready.poke(true.B)
    dut.io.metadata_publish_ack_in.valid.poke(false.B)
    dut.io.r5_reclaim_complete_in.poke(false.B)
    driveFrontend(dut, p.r6.sessionStartEventCode, contextTokens = 32768)
    dut.io.runtime_retire_req.bits.session_id.poke(false.B)
    dut.io.runtime_retire_req.bits.transaction_identity.request_id.poke(0.U)
    dut.io.runtime_retire_req.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.component_status_in.bits.acknowledgement_name.poke(0.U); dut.io.component_status_in.bits.asserted.poke(false.B)
    dut.io.authority_transition_in.bits.entry_id.poke(0.U); dut.io.authority_transition_in.bits.from_authority.poke(0.U)
    dut.io.authority_transition_in.bits.to_authority.poke(0.U); dut.io.authority_transition_in.bits.transaction_group_tag.poke(0.U)
    dut.io.merge_ready_in.bits.transaction_identity.request_id.poke(0.U); dut.io.merge_ready_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.merge_ready_in.bits.source_presence.poke(0.U)
    dut.io.merge_terminal_in.bits.transaction_identity.request_id.poke(0.U); dut.io.merge_terminal_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.merge_terminal_in.bits.status.poke(p.coreMemoryOkStatusCode.U); dut.io.merge_terminal_in.bits.normalized_value.poke(0.U)
  }

  private def sendStatus(dut: RouteALifecycleAdapter, code: Int): Unit = {
    dut.io.component_status_in.bits.acknowledgement_name.poke(code.U)
    dut.io.component_status_in.bits.asserted.poke(true.B); dut.io.component_status_in.valid.poke(true.B)
    dut.io.component_status_in.ready.expect(true.B); dut.clock.step(); dut.io.component_status_in.valid.poke(false.B)
  }

  private def initializeSession(dut: RouteALifecycleAdapter): Unit = {
    Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode)
      .foreach(sendStatus(dut, _))
    driveFrontend(dut, p.r6.sessionStartEventCode, contextTokens = 32768)
    dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
    dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)
  }

  private def sendAttention(dut: RouteALifecycleAdapter, rid: Int, incarnation: Int, position: Int = 1): Unit = {
    driveFrontend(dut, p.r6.attentionServiceEventCode, entry = position * 288, position = position, rid = rid, incarnation = incarnation)
    dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
    dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)
  }

  private def issueMerge(dut: RouteALifecycleAdapter, rid: Int, incarnation: Int, presence: Int = 1): Unit = {
    dut.io.merge_ready_in.bits.transaction_identity.request_id.poke(rid.U); dut.io.merge_ready_in.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.merge_ready_in.bits.source_presence.poke(presence.U); dut.io.merge_ready_in.valid.poke(true.B)
    dut.io.merge_ready_in.ready.expect(true.B); dut.clock.step(); dut.io.merge_ready_in.valid.poke(false.B)
    dut.io.merge_req.valid.expect(true.B); dut.io.merge_req.bits.transaction_identity.request_id.expect(rid.U)
    dut.io.merge_req.ready.poke(true.B); dut.clock.step()
  }

  private def terminalize(dut: RouteALifecycleAdapter, rid: Int, incarnation: Int, status: Int): Unit = {
    dut.io.merge_terminal_in.bits.transaction_identity.request_id.poke(rid.U); dut.io.merge_terminal_in.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.merge_terminal_in.bits.status.poke(status.U); dut.io.merge_terminal_in.valid.poke(true.B)
    dut.io.merge_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.merge_terminal_in.valid.poke(false.B)
  }

  it("gates session init and emits stable hot plus authority events without copying authority state") {
    simulate(new RouteALifecycleAdapter(p)) { dut =>
      init(dut)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(false.B); dut.io.frontend_lifecycle_req.valid.poke(false.B)
      initializeSession(dut)

      driveFrontend(dut, p.r6.kvArrivalEventCode, entry = 0, position = 0)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B); dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)
      dut.io.hot_control_out.valid.expect(true.B); dut.io.authority_transition_out.valid.expect(true.B)
      dut.io.hot_control_out.ready.poke(false.B); dut.io.authority_transition_out.ready.poke(false.B); dut.clock.step()
      dut.io.hot_control_out.bits.entry_id.expect(0.U); dut.io.authority_transition_out.bits.from_authority.expect(RouteAAuthorityStateCode.None.U)
      dut.io.authority_transition_out.bits.to_authority.expect(RouteAAuthorityStateCode.Hot.U)
      dut.io.hot_control_out.ready.poke(true.B); dut.clock.step(); dut.io.authority_transition_out.valid.expect(true.B)
      dut.io.authority_transition_out.ready.poke(true.B); dut.clock.step(); dut.io.hot_control_out.valid.expect(false.B)

      driveFrontend(dut, p.r6.maturityDispositionEventCode, entry = 0, position = 0, retain = true)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B); dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)
      dut.io.authority_transition_out.bits.from_authority.expect(RouteAAuthorityStateCode.Hot.U)
      dut.io.authority_transition_out.bits.to_authority.expect(RouteAAuthorityStateCode.Pending.U)
      dut.clock.step()

      val published = dut.io.authority_transition_in.bits
      published.entry_id.poke(0.U); published.from_authority.poke(RouteAAuthorityStateCode.Pending.U)
      published.to_authority.poke(RouteAAuthorityStateCode.Packed.U); published.transaction_group_tag.poke(1.U)
      dut.io.authority_transition_in.valid.poke(true.B); dut.io.authority_transition_in.ready.expect(true.B); dut.clock.step(); dut.io.authority_transition_in.valid.poke(false.B)
      published.from_authority.poke(RouteAAuthorityStateCode.Hot.U); dut.io.authority_transition_in.valid.poke(true.B); dut.io.authority_transition_in.ready.expect(false.B)
    }
  }

  it("requires GQA-complete merge-ready before one stable outward terminal and rejects stale duplication") {
    simulate(new RouteALifecycleAdapter(p)) { dut =>
      init(dut); initializeSession(dut); sendAttention(dut, 1, 0)
      dut.io.merge_terminal_in.bits.transaction_identity.request_id.poke(1.U); dut.io.merge_terminal_in.bits.transaction_identity.incarnation.poke(0.U)
      dut.io.merge_terminal_in.bits.status.poke(p.coreMemoryFaultStatusCode.U); dut.io.merge_terminal_in.valid.poke(true.B); dut.io.merge_terminal_in.ready.expect(false.B)
      dut.io.merge_terminal_in.valid.poke(false.B)
      dut.io.merge_ready_in.bits.source_presence.poke(0.U); dut.io.merge_ready_in.valid.poke(true.B); dut.io.merge_ready_in.ready.expect(false.B); dut.io.merge_ready_in.valid.poke(false.B)
      issueMerge(dut, 1, 0, presence = 3)
      terminalize(dut, 1, 0, p.coreMemoryFaultStatusCode)
      dut.io.attention_terminal_rsp.valid.expect(true.B); dut.io.attention_terminal_rsp.ready.poke(false.B); dut.clock.step()
      dut.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(1.U); dut.io.attention_terminal_rsp.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
      dut.io.attention_terminal_rsp.ready.poke(true.B); dut.clock.step(); dut.io.attention_terminal_rsp.valid.expect(false.B)
      dut.io.merge_terminal_in.valid.poke(true.B); dut.io.merge_terminal_in.ready.expect(false.B)
    }
  }

  it("emits only the frozen hot-to-drop authority edge for a DROP maturity") {
    simulate(new RouteALifecycleAdapter(p)) { dut =>
      init(dut); initializeSession(dut)
      driveFrontend(dut, p.r6.kvArrivalEventCode, entry = 0, position = 0)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
      dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)
      dut.clock.step() // hot and none->hot events are accepted by the ready-high peers.
      driveFrontend(dut, p.r6.maturityDispositionEventCode, entry = 0, position = 0, retain = false)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
      dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)
      dut.io.authority_transition_out.valid.expect(true.B)
      dut.io.authority_transition_out.bits.from_authority.expect(RouteAAuthorityStateCode.Hot.U)
      dut.io.authority_transition_out.bits.to_authority.expect(RouteAAuthorityStateCode.None.U)
    }
  }

  it("requires a two-pass R5 reclaim drain before matching retirement ack") {
    simulate(new RouteALifecycleAdapter(p)) { dut =>
      init(dut); initializeSession(dut); sendAttention(dut, 2, 0)
      dut.io.runtime_retire_req.bits.session_id.poke(false.B); dut.io.runtime_retire_req.bits.transaction_identity.request_id.poke(3.U)
      dut.io.runtime_retire_req.bits.transaction_identity.incarnation.poke(1.U); dut.io.runtime_retire_req.valid.poke(true.B)
      dut.io.runtime_retire_req.ready.expect(true.B); dut.clock.step(); dut.io.runtime_retire_req.valid.poke(false.B)
      driveFrontend(dut, p.r6.kvArrivalEventCode, entry = 0, position = 0); dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(false.B); dut.io.frontend_lifecycle_req.valid.poke(false.B)
      issueMerge(dut, 2, 0); terminalize(dut, 2, 0, p.coreMemoryOkStatusCode); dut.clock.step()
      val drains = Seq(
        p.r6.r1MemoryDrainedStatusCode, p.r6.r2PayloadDrainedStatusCode, p.r6.r2DescriptorDrainedStatusCode,
        p.r6.r3M2P3DrainedStatusCode, p.r6.r5PageManagerDrainedStatusCode, p.r6.s2GqaDrainedStatusCode,
        p.r6.directPendingDrainedStatusCode, p.r6.mergeDrainedStatusCode,
      )
      drains.foreach(sendStatus(dut, _)); dut.io.session_retire_ack.valid.expect(false.B); dut.clock.step()
      dut.io.reclaim_permit_out.valid.expect(true.B)
      dut.io.reclaim_permit_out.ready.poke(false.B); dut.clock.step()
      dut.io.reclaim_permit_out.valid.expect(true.B)
      dut.io.reclaim_permit_out.bits.transaction_identity.request_id.expect(3.U)
      dut.io.reclaim_permit_out.ready.poke(true.B); dut.clock.step() // permit is accepted before R5 may report completion
      // The final R1/R2-descriptor facts are intentionally suppressed until
      // R5 reports its durable line invalidation sequence complete.
      dut.io.component_status_in.bits.acknowledgement_name.poke(p.r6.r1MemoryDrainedStatusCode.U)
      dut.io.component_status_in.bits.asserted.poke(true.B); dut.io.component_status_in.valid.poke(true.B)
      dut.io.component_status_in.ready.expect(false.B); dut.io.component_status_in.valid.poke(false.B)
      dut.io.r5_reclaim_complete_in.poke(true.B); dut.clock.step(); dut.io.r5_reclaim_complete_in.poke(false.B)
      sendStatus(dut, p.r6.r2DescriptorDrainedStatusCode)
      sendStatus(dut, p.r6.r1MemoryDrainedStatusCode)
      dut.io.session_retire_ack.valid.expect(true.B)
      dut.io.session_retire_ack.ready.poke(false.B); dut.clock.step(); dut.io.session_retire_ack.bits.transaction_identity.request_id.expect(3.U)
      dut.io.session_retire_ack.bits.transaction_identity.incarnation.expect(1.U); dut.io.session_retire_ack.ready.poke(true.B); dut.clock.step()
    }
  }

  it("destructive reset removes local lifecycle reachability and requires init again") {
    simulate(new RouteALifecycleAdapter(p)) { dut =>
      init(dut); initializeSession(dut); sendAttention(dut, 1, 0)
      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B); dut.clock.step()
      driveFrontend(dut, p.r6.sessionStartEventCode, contextTokens = 32768)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(false.B)
      dut.io.frontend_lifecycle_req.valid.poke(false.B)
      Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode)
        .foreach(sendStatus(dut, _))
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
    }
  }
}
