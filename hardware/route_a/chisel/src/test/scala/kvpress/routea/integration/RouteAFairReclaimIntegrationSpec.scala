package kvpress.routea.integration

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteACoreMemIfV1, RouteACoreSideArbiter}
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAPageManager}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

import scala.util.Random

/** Test-only R1/R2/R5/R6 composition for RTL1-V legal-stall evidence. */
private final class RouteAFairReclaimHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val retire = Flipped(RouteAChannels.runtime_retire_req)
    val status = Flipped(RouteAChannels.component_status(p))
    val allocation = Flipped(RouteAChannels.page_allocation_req(p))
    val descriptor_terminal = Flipped(RouteAChannels.descriptor_maintenance_terminal(p))
    val visibility = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val retire_ack = RouteAChannels.session_retire_ack
    val external = new CoreMemoryExternalPort(p)
  })

  val r6 = Module(new RouteALifecycleAdapter(p))
  val r5 = Module(new RouteAPageManager(p))
  val r2 = Module(new RouteACoreSideArbiter(p))
  val r1 = Module(new RouteACoreMemIfV1(p))

  r6.io.frontend_lifecycle_req <> io.frontend
  r6.io.runtime_retire_req <> io.retire
  r6.io.component_status_in <> io.status
  StructuralTieOff.sink(r6.io.attention_terminal_rsp)
  io.retire_ack <> r6.io.session_retire_ack
  StructuralTieOff.sink(r6.io.hot_control_out)
  StructuralTieOff.sink(r6.io.authority_transition_out)
  StructuralTieOff.sink(r6.io.admission_context_out)
  StructuralTieOff.source(r6.io.authority_transition_in)
  StructuralTieOff.source(r6.io.merge_ready_in)
  StructuralTieOff.source(r6.io.source_completion_plan_in)
  StructuralTieOff.source(r6.io.hot_source_release_in)
  StructuralTieOff.source(r6.io.pending_source_release_in)
  StructuralTieOff.source(r6.io.packed_source_release_in)
  StructuralTieOff.sink(r6.io.s2_service_req)
  StructuralTieOff.sink(r6.io.direct_pending_open)
  StructuralTieOff.sink(r6.io.merge_req)
  StructuralTieOff.source(r6.io.merge_terminal_in)
  StructuralTieOff.sink(r6.io.metadata_publish_req)
  StructuralTieOff.source(r6.io.metadata_publish_ack_in)

  r5.io.mem_init_done := r1.io.r1_init_complete
  r5.io.drain_collection_enable := r6.io.drain_collection_enable
  r5.io.reclaim_permit_in <> r6.io.reclaim_permit_out
  r6.io.r5_reclaim_complete_in := r5.io.reclaim_complete
  r5.io.page_allocation_req_in <> io.allocation
  r5.io.page_allocation_rsp.ready := true.B
  r5.io.descriptor_maintenance_terminal_in <> io.descriptor_terminal
  r5.io.metadata_publish_visibility_in <> io.visibility
  r5.io.metadata_publish_visibility_ack.ready := true.B
  r5.io.component_status_out.ready := true.B

  r2.io.candidate_in <> r5.io.reclaim_candidate_out
  r2.io.reclaim_maintenance_enable := r6.io.reclaim_maintenance_enable
  r2.io.drain_collection_enable := r6.io.drain_collection_enable
  StructuralTieOff.sink(r2.io.payload_drain_status_out)
  StructuralTieOff.sink(r2.io.descriptor_drain_status_out)
  r5.io.reclaim_delivery_in <> r2.io.source_delivery_out

  r1.io.core_mem_req_in <> r2.io.core_mem_req
  r2.io.core_mem_rsp_in <> r1.io.core_mem_rsp
  io.external <> r1.io.external_core_mem_if_v1
  r1.io.r1_drain_permitted := true.B
  r1.io.component_status_out.ready := true.B
}

/** RTL1-V fixed-seed semantic backpressure witness; no controller/PPA model. */
final class RouteAFairReclaimIntegrationSpec extends AnyFunSpec with ChiselSim {
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

  private def clear(dut: RouteAFairReclaimHarness): Unit = {
    dut.io.frontend.valid.poke(false.B); dut.io.retire.valid.poke(false.B); dut.io.status.valid.poke(false.B)
    dut.io.allocation.valid.poke(false.B); dut.io.descriptor_terminal.valid.poke(false.B); dut.io.visibility.valid.poke(false.B)
    dut.io.retire_ack.ready.poke(true.B)
    dut.io.external.init_ack.valid.poke(false.B); dut.io.external.request.ready.poke(false.B); dut.io.external.response.valid.poke(false.B)
    dut.io.external.init_ack.bits.adapter_epoch_ready.poke(false.B)
    dut.io.external.response.bits.transaction_identity.request_id.poke(0.U); dut.io.external.response.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.external.response.bits.fragment_index.poke(0.U); dut.io.external.response.bits.last.poke(true.B)
    dut.io.external.response.bits.status.poke(p.coreMemoryOkStatusCode.U); dut.io.external.response.bits.data.poke(0.U)
  }

  private def status(dut: RouteAFairReclaimHarness, code: Int): Unit = {
    dut.io.status.bits.acknowledgement_name.poke(code.U); dut.io.status.bits.asserted.poke(true.B)
    dut.io.status.valid.poke(true.B); dut.io.status.ready.expect(true.B); dut.clock.step(); dut.io.status.valid.poke(false.B)
  }

  private def frontendStart(dut: RouteAFairReclaimHarness): Unit = {
    val in = dut.io.frontend.bits
    in.event_kind.poke(p.r6.sessionStartEventCode.U); in.session_id.poke(false.B); in.context_tokens.poke(32768.U)
    in.entry_id.poke(0.U); in.layer.poke(0.U); in.kv_head.poke(0.U); in.logical_position.poke(0.U); in.payload_ref.poke(0.U)
    in.disposition.poke(false.B); in.transaction_identity.request_id.poke(0.U); in.transaction_identity.incarnation.poke(0.U)
    in.admission_group_tag.poke(0.U); in.admission_member_ordinal.poke(0.U); in.admission_group_valid_records.poke(0.U)
    dut.io.frontend.valid.poke(true.B); dut.io.frontend.ready.expect(true.B); dut.clock.step(); dut.io.frontend.valid.poke(false.B)
  }

  private def allocateAndPublish(dut: RouteAFairReclaimHarness): Unit = {
    val alloc = dut.io.allocation.bits
    alloc.layer.poke(0.U); alloc.kv_head.poke(0.U); alloc.valid_records.poke(1.U); alloc.transaction_group_tag.poke(1.U)
    dut.io.allocation.valid.poke(true.B); dut.io.allocation.ready.expect(true.B); dut.clock.step(); dut.io.allocation.valid.poke(false.B)
    val terminal = dut.io.descriptor_terminal.bits
    terminal.kind.poke(RouteADescriptorOperationKind.NewPage.U); terminal.page_ref.page_id.poke(0.U); terminal.page_ref.generation.poke(0.U)
    terminal.transaction_group_tag.poke(1.U); terminal.status.poke(p.coreMemoryOkStatusCode.U); terminal.r1_descriptor_durable.poke(true.B)
    dut.io.descriptor_terminal.valid.poke(true.B); dut.io.descriptor_terminal.ready.expect(true.B); dut.clock.step(); dut.io.descriptor_terminal.valid.poke(false.B)
    val visibility = dut.io.visibility.bits
    visibility.page_ref.page_id.poke(0.U); visibility.page_ref.generation.poke(0.U); visibility.transaction_group_tag.poke(1.U)
    dut.io.visibility.valid.poke(true.B); dut.io.visibility.ready.expect(true.B); dut.clock.step(); dut.io.visibility.valid.poke(false.B); dut.clock.step()
  }

  it("preserves the R1/R2/R5/R6 reclaim transaction under fixed-seed legal stalls") {
    simulate(new RouteAFairReclaimHarness(p)) { dut =>
      clear(dut)
      dut.io.external.init_ack.bits.adapter_epoch_ready.poke(true.B); dut.io.external.init_ack.valid.poke(true.B)
      dut.io.external.init_ack.ready.expect(true.B); dut.clock.step(); dut.io.external.init_ack.valid.poke(false.B); dut.clock.step()
      Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(dut, _))
      frontendStart(dut); allocateAndPublish(dut)

      dut.io.retire.bits.session_id.poke(false.B); dut.io.retire.bits.transaction_identity.request_id.poke(3.U); dut.io.retire.bits.transaction_identity.incarnation.poke(1.U)
      dut.io.retire.valid.poke(true.B); dut.io.retire.ready.expect(true.B); dut.clock.step(); dut.io.retire.valid.poke(false.B)
      Seq(p.r6.r1MemoryDrainedStatusCode, p.r6.r2PayloadDrainedStatusCode, p.r6.r2DescriptorDrainedStatusCode,
        p.r6.r3M2P3DrainedStatusCode, p.r6.s2GqaDrainedStatusCode, p.r6.directPendingDrainedStatusCode,
        p.r6.mergeDrainedStatusCode).foreach(status(dut, _))

      val random = new Random(0x51A11L)
      var issuedKinds = Vector.empty[BigInt]
      var heldRequest: Option[(BigInt, BigInt, BigInt)] = None
      for (_ <- 0 until 48 if issuedKinds.size < 2) {
        val ready = random.nextBoolean()
        dut.io.external.request.ready.poke(ready.B)
        if (dut.io.external.request.valid.peekBoolean && !ready) {
          val current = (
            dut.io.external.request.bits.request_kind.peek().litValue,
            dut.io.external.request.bits.transaction_identity.request_id.peek().litValue,
            dut.io.external.request.bits.address_ref.peek().litValue,
          )
          heldRequest.foreach(previous => assert(current == previous))
          heldRequest = Some(current)
        } else heldRequest = None
        if (dut.io.external.request.valid.peekBoolean && ready) issuedKinds :+= dut.io.external.request.bits.request_kind.peek().litValue
        dut.clock.step()
      }
      assert(issuedKinds == Vector(BigInt(p.coreMemoryWriteRequestCode), BigInt(p.coreMemoryWriteDataCode)))

      // The seeded schedule also delays the terminal, but eventually releases
      // the fairness assumption. No cycle count is an architectural bound.
      (0 until 3).foreach { _ => dut.io.external.response.valid.poke(false.B); dut.clock.step() }
      dut.io.external.response.valid.poke(true.B); dut.io.external.response.ready.expect(true.B); dut.clock.step(); dut.io.external.response.valid.poke(false.B)
      dut.clock.step()

      Seq(p.r6.r5PageManagerDrainedStatusCode, p.r6.r2DescriptorDrainedStatusCode, p.r6.r1MemoryDrainedStatusCode).foreach(status(dut, _))
      dut.io.retire_ack.ready.poke(false.B); dut.clock.step(); dut.io.retire_ack.valid.expect(true.B)
      dut.io.retire_ack.bits.transaction_identity.request_id.expect(3.U); dut.io.retire_ack.bits.transaction_identity.incarnation.expect(1.U)
      dut.io.retire_ack.ready.poke(true.B); dut.clock.step()
    }
  }
}
