package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.interfaces.RouteAAuthorityStateCode
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** One-instance actual R3--R2--R1--R5 transaction smoke test; no PPA model. */
final class RouteA2_1bWritePathHarnessSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=32, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def init(d: RouteA2_1bWritePathHarness): Unit = {
    d.io.mem_init_done.poke(false.B); d.io.r5_allocate.valid.poke(false.B); d.io.r5_allocation_rsp.ready.poke(true.B)
    d.io.p3_claim.valid.poke(false.B); d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B)
    d.io.hot_payload.valid.poke(false.B); d.io.hot_sidecar.valid.poke(false.B)
    d.io.external.init_ack.valid.poke(false.B); d.io.external.request.ready.poke(false.B); d.io.external.response.valid.poke(false.B)
    d.io.external.response.bits.transaction_identity.request_id.poke(0.U); d.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    d.io.external.response.bits.fragment_index.poke(0.U); d.io.external.response.bits.last.poke(true.B); d.io.external.response.bits.status.poke(0.U); d.io.external.response.bits.data.poke(0.U)
    d.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.mem_init_done.poke(true.B); d.io.external.init_ack.valid.poke(true.B); d.clock.step(); d.io.external.init_ack.valid.poke(false.B)
  }
  private def acceptReq(d: RouteA2_1bWritePathHarness, kind: Int, index: Int): Unit = {
    var waited = 0
    while (d.io.external.request.valid.peek().litValue == 0 && waited < 16) { d.clock.step(); waited += 1 }
    d.io.external.request.valid.expect(true.B); d.io.external.request.bits.request_kind.expect(kind.U)
    d.io.external.request.bits.fragment_index.expect(index.U); d.clock.step(); d.io.external.request.ready.poke(true.B); d.clock.step(); d.io.external.request.ready.poke(false.B)
  }
  private def terminal(d: RouteA2_1bWritePathHarness, fault: Boolean = false): Unit = {
    d.io.external.response.bits.status.poke((if (fault) 1 else 0).U); d.io.external.response.valid.poke(true.B)
    d.io.external.response.ready.expect(true.B); d.clock.step(); d.io.external.response.valid.poke(false.B)
  }

  it("keeps the 64-B payload write and descriptor write on one stalled R1 path without publication") {
    simulate(new RouteA2_1bWritePathHarness(p)) { d =>
      init(d)
      val a=d.io.r5_allocate.bits; a.layer.poke(0.U); a.kv_head.poke(0.U); a.valid_records.poke(1.U); a.transaction_group_tag.poke(1.U)
      d.io.r5_allocate.valid.poke(true.B); d.io.r5_allocate.ready.expect(true.B); d.clock.step(); d.io.r5_allocate.valid.poke(false.B)
      val c=d.io.p3_claim.bits; c.layer.poke(0.U); c.kv_head.poke(0.U); c.owner.poke(0.U); c.page_ref.page_id.poke(0.U); c.page_ref.generation.poke(0.U); c.valid_records.poke(1.U); c.requires_tail_link.poke(false.B); c.transaction_group_tag.poke(1.U)
      d.io.p3_claim.valid.poke(true.B); d.io.p3_claim.ready.expect(true.B); d.clock.step(); d.io.p3_claim.valid.poke(false.B)
      val x=d.io.admission_context.bits; x.entry_id.poke(0.U); x.layer.poke(0.U); x.kv_head.poke(0.U); x.logical_position.poke(0.U); x.payload_ref.poke(55.U); x.transaction_group_tag.poke(1.U); x.group_member_ordinal.poke(0.U); x.group_valid_records.poke(1.U)
      val h=d.io.admission_authority.bits; h.entry_id.poke(0.U); h.from_authority.poke(RouteAAuthorityStateCode.Hot.U); h.to_authority.poke(RouteAAuthorityStateCode.Pending.U); h.transaction_group_tag.poke(1.U)
      d.io.admission_context.valid.poke(true.B); d.io.admission_authority.valid.poke(true.B); d.io.admission_context.ready.expect(true.B); d.clock.step(); d.io.admission_context.valid.poke(false.B); d.io.admission_authority.valid.poke(false.B)
      val f=d.io.hot_payload.bits; f.layer.poke(0.U); f.stage_generation.poke(1.U); f.status.poke(0.U); f.payload_ref.poke(55.U)
      (0 until 8).foreach { i => f.fragment_index.poke(i.U); f.last.poke((i==7).B); f.data.poke((0x100+i).U); d.io.hot_payload.valid.poke(true.B); d.io.hot_payload.ready.expect(true.B); d.clock.step() }; d.io.hot_payload.valid.poke(false.B)
      val s=d.io.hot_sidecar.bits; s.layer.poke(0.U); s.stage_generation.poke(1.U); s.record_ordinal.poke(0.U); s.payload_ref.poke(55.U); s.logical_position.poke(0.U); d.io.hot_sidecar.valid.poke(true.B); d.io.hot_sidecar.ready.expect(true.B); d.clock.step(); d.io.hot_sidecar.valid.poke(false.B)
      d.clock.step(); acceptReq(d,p.coreMemoryWriteRequestCode,0); (0 until 8).foreach(i=>acceptReq(d,p.coreMemoryWriteDataCode,i)); terminal(d)
      d.io.p3_state.expect(5.U) // durable only; no publication/authority release in this harness.
      d.clock.step(); acceptReq(d,p.coreMemoryWriteRequestCode,0); acceptReq(d,p.coreMemoryWriteDataCode,0); terminal(d)
      d.io.p3_state.expect(5.U)
    }
  }
}
