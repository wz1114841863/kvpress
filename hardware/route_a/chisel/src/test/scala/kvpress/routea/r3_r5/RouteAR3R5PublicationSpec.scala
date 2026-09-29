package kvpress.routea.r3_r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.{RouteAM2P3Wrapper, RouteAPageManager}
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAM2GroupMember, RouteAPublicationStatus, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

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
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8,
    r5StreamSlots = 8,
  )

  private def initR3(dut: RouteAM2P3Wrapper): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.p3_observe_layer.poke(0.U)
    dut.io.p3_claim_in.valid.poke(false.B); dut.io.p3_claim_ack.ready.poke(true.B)
    dut.io.p3_pending_fragment_in.valid.poke(false.B); dut.io.p3_sidecar_bind_in.valid.poke(false.B)
    dut.io.p3_packed_write_issue_in.valid.poke(false.B); dut.io.p3_packed_write_terminal_in.valid.poke(false.B)
    dut.io.m2_group_member_rsp_in.valid.poke(false.B); dut.io.m2_publish_req_in.valid.poke(false.B)
    dut.io.metadata_publish_visibility_apply.ready.poke(true.B)
    dut.io.metadata_publish_visibility_ack_in.valid.poke(false.B); dut.io.m2_publish_ack.ready.poke(true.B)
    dut.io.mem_init_done.poke(true.B); dut.clock.step()
  }

  private def claimOneRecord(dut: RouteAM2P3Wrapper): Unit = {
    val claim = dut.io.p3_claim_in.bits
    claim.layer.poke(0.U); claim.kv_head.poke(0.U); claim.owner.poke(0.U)
    claim.page_ref.page_id.poke(0.U); claim.page_ref.generation.poke(0.U)
    claim.valid_records.poke(1.U); claim.transaction_group_tag.poke(1.U)
    dut.io.p3_claim_in.valid.poke(true.B); dut.io.p3_claim_in.ready.expect(true.B); dut.clock.step()
    dut.io.p3_claim_in.valid.poke(false.B); dut.clock.step()
    dut.io.p3_observe_generation.expect(1.U)
    dut.io.p3_observe_state.expect(1.U)
  }

  private def finishP3AndM2(dut: RouteAM2P3Wrapper): Unit = {
    val fragment = dut.io.p3_pending_fragment_in.bits
    fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.status.poke(p.coreMemoryOkStatusCode.U)
    for (fragmentIndex <- 0 until 8) {
      fragment.fragment_index.poke(fragmentIndex.U); fragment.last.poke((fragmentIndex == 7).B)
      dut.io.p3_pending_fragment_in.valid.poke(true.B); dut.io.p3_pending_fragment_in.ready.expect(true.B); dut.clock.step()
    }
    dut.io.p3_pending_fragment_in.valid.poke(false.B)
    val sidecar = dut.io.p3_sidecar_bind_in.bits
    sidecar.layer.poke(0.U); sidecar.stage_generation.poke(1.U); sidecar.record_ordinal.poke(0.U)
    dut.io.p3_sidecar_bind_in.valid.poke(true.B); dut.io.p3_sidecar_bind_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_sidecar_bind_in.valid.poke(false.B)
    dut.io.p3_packed_write_terminal_in.bits.layer.poke(0.U); dut.io.p3_packed_write_terminal_in.bits.stage_generation.poke(1.U)
    dut.io.p3_packed_write_terminal_in.bits.transaction_group_tag.poke(1.U); dut.io.p3_packed_write_terminal_in.bits.status.poke(p.coreMemoryOkStatusCode.U)
    dut.io.p3_packed_write_terminal_in.bits.r1_payload_durable.poke(true.B)
    dut.io.p3_packed_write_terminal_in.valid.poke(true.B); dut.io.p3_packed_write_terminal_in.ready.expect(false.B); dut.io.p3_packed_write_terminal_in.valid.poke(false.B)
    dut.io.p3_packed_write_issue_in.bits.layer.poke(0.U); dut.io.p3_packed_write_issue_in.bits.stage_generation.poke(1.U); dut.io.p3_packed_write_issue_in.bits.transaction_group_tag.poke(1.U)
    dut.io.p3_packed_write_issue_in.valid.poke(true.B); dut.io.p3_packed_write_issue_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_packed_write_issue_in.valid.poke(false.B)
    dut.io.p3_packed_write_terminal_in.valid.poke(true.B); dut.io.p3_packed_write_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_packed_write_terminal_in.valid.poke(false.B)
    for (member <- Seq(RouteAM2GroupMember.HeadControlRmw, RouteAM2GroupMember.SpanOwnerRmw)) {
      val response = dut.io.m2_group_member_rsp_in.bits
      response.layer.poke(0.U); response.stage_generation.poke(1.U); response.transaction_group_tag.poke(1.U)
      response.member.poke(member.U); response.status.poke(p.coreMemoryOkStatusCode.U)
      dut.io.m2_group_member_rsp_in.valid.poke(true.B); dut.io.m2_group_member_rsp_in.ready.expect(true.B); dut.clock.step(); dut.io.m2_group_member_rsp_in.valid.poke(false.B)
    }
  }

  it("publishes exactly once only after durable P3 and both private M2 members") {
    simulate(new RouteAM2P3Wrapper(p)) { dut =>
      initR3(dut); claimOneRecord(dut)
      val publish = dut.io.m2_publish_req_in.bits
      publish.transaction_group_tag.poke(1.U); publish.p3_layer.poke(0.U); publish.p3_stage_generation.poke(1.U)
      dut.io.m2_publish_req_in.valid.poke(true.B); dut.io.m2_publish_req_in.ready.expect(false.B); dut.io.m2_publish_req_in.valid.poke(false.B)
      finishP3AndM2(dut)
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
    simulate(new RouteAM2P3Wrapper(p)) { dut =>
      initR3(dut); claimOneRecord(dut)
      val fragment = dut.io.p3_pending_fragment_in.bits
      fragment.layer.poke(0.U); fragment.stage_generation.poke(1.U); fragment.fragment_index.poke(0.U)
      fragment.last.poke(true.B); fragment.status.poke(p.coreMemoryFaultStatusCode.U)
      dut.io.p3_pending_fragment_in.valid.poke(true.B); dut.io.p3_pending_fragment_in.ready.expect(true.B); dut.clock.step(); dut.io.p3_pending_fragment_in.valid.poke(false.B)
      dut.io.m2_publish_req_in.bits.transaction_group_tag.poke(1.U); dut.io.m2_publish_req_in.bits.p3_layer.poke(0.U); dut.io.m2_publish_req_in.bits.p3_stage_generation.poke(1.U)
      dut.io.m2_publish_req_in.valid.poke(true.B); dut.io.m2_publish_req_in.ready.expect(false.B)
    }
  }

  private def initR5(dut: RouteAPageManager): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.page_allocation_req_in.valid.poke(false.B)
    dut.io.page_allocation_rsp.ready.poke(true.B); dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B)
    dut.io.metadata_publish_visibility_in.valid.poke(false.B); dut.io.metadata_publish_visibility_ack.ready.poke(true.B)
    dut.io.mem_init_done.poke(true.B); dut.clock.step()
  }

  private def allocate(dut: RouteAPageManager, tag: Int): Unit = {
    val alloc = dut.io.page_allocation_req_in.bits
    alloc.layer.poke(0.U); alloc.kv_head.poke(0.U); alloc.valid_records.poke(1.U); alloc.transaction_group_tag.poke(tag.U)
    dut.io.page_allocation_req_in.valid.poke(true.B); dut.io.page_allocation_req_in.ready.expect(true.B); dut.clock.step(); dut.io.page_allocation_req_in.valid.poke(false.B)
  }

  private def descriptorTerminal(dut: RouteAPageManager, page: Int, tag: Int, kind: Int, fault: Boolean = false): Unit = {
    val terminal = dut.io.descriptor_maintenance_terminal_in.bits
    terminal.kind.poke(kind.U); terminal.page_ref.page_id.poke(page.U); terminal.page_ref.generation.poke(0.U)
    terminal.transaction_group_tag.poke(tag.U); terminal.status.poke((if (fault) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U)
    terminal.r1_descriptor_durable.poke((!fault).B)
    dut.io.descriptor_maintenance_terminal_in.valid.poke(true.B); dut.io.descriptor_maintenance_terminal_in.ready.expect(true.B); dut.clock.step(); dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B)
  }

  it("keeps descriptor-private pages unreachable until publication and requires a tail link on append") {
    simulate(new RouteAPageManager(p)) { dut =>
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
    simulate(new RouteAPageManager(p)) { dut =>
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
