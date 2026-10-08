package kvpress.routea.integration

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteALifecycleAdapter
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.RouteAComponentStatusCollector
import org.scalatest.funspec.AnyFunSpec

import scala.util.Random

/**
  * RTL2.5.3 test-only R6 + status-collector composition.  Component status
  * facts are explicit environment facts; this harness neither infers them
  * from idle state nor selects a controller schedule.
  */
final class RouteARetirementDrainClosureHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val retire = Flipped(RouteAChannels.runtime_retire_req)
    val status_sources = Flipped(Vec(8, RouteAChannels.component_status(p)))
    val r5_reclaim_complete = Input(Bool())
    val reclaim_permit = RouteAChannels.reclaim_permit
    val retire_ack = RouteAChannels.session_retire_ack
    val drain_collection_enable = Output(Bool())
    val reclaim_final_drain_enable = Output(Bool())
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val collector = Module(new RouteAComponentStatusCollector(p))

  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.runtime_retire_req <> io.retire
  lifecycle.io.component_status_in <> collector.io.component_status_out
  collector.io.status_sources <> io.status_sources
  collector.io.drain_collection_enable := lifecycle.io.drain_collection_enable
  collector.io.reclaim_drain_restart := lifecycle.io.reclaim_drain_restart
  collector.io.reclaim_final_drain_enable := lifecycle.io.reclaim_final_drain_enable
  lifecycle.io.r5_reclaim_complete_in := io.r5_reclaim_complete
  io.reclaim_permit <> lifecycle.io.reclaim_permit_out
  io.retire_ack <> lifecycle.io.session_retire_ack
  io.drain_collection_enable := lifecycle.io.drain_collection_enable
  io.reclaim_final_drain_enable := lifecycle.io.reclaim_final_drain_enable

  StructuralTieOff.sink(lifecycle.io.attention_terminal_rsp)
  StructuralTieOff.sink(lifecycle.io.hot_control_out)
  StructuralTieOff.sink(lifecycle.io.authority_transition_out)
  StructuralTieOff.sink(lifecycle.io.admission_context_out)
  StructuralTieOff.source(lifecycle.io.authority_transition_in)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.source(lifecycle.io.source_completion_plan_in)
  lifecycle.io.source_completion_plan_copy_out.ready := true.B
  StructuralTieOff.source(lifecycle.io.hot_source_release_in)
  StructuralTieOff.source(lifecycle.io.pending_source_release_in)
  StructuralTieOff.source(lifecycle.io.packed_source_release_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.merge_req)
  StructuralTieOff.source(lifecycle.io.merge_terminal_in)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
}

/** RTL2.5.3 fixed-membership retirement/drain closure; no controller/PPA model. */
final class RouteARetirementDrainClosureSpec extends AnyFunSpec with ChiselSim {
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

  private val R1 = 0
  private val R2Payload = 1
  private val R2Descriptor = 2
  private val R3 = 3
  private val R5 = 4
  private val S2 = 5
  private val DirectPending = 6
  private val R4 = 7

  private def driveLifecycleZero(dut: RouteARetirementDrainClosureHarness): Unit = {
    val f = dut.io.frontend.bits
    f.event_kind.poke(0.U); f.session_id.poke(false.B); f.context_tokens.poke(0.U)
    f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U)
    f.payload_ref.poke(0.U); f.disposition.poke(false.B)
    f.transaction_identity.request_id.poke(0.U); f.transaction_identity.incarnation.poke(0.U)
    f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(0.U)
  }

  private def driveStatus(dut: RouteARetirementDrainClosureHarness, source: Int, valid: Boolean, code: Int): Unit = {
    dut.io.status_sources(source).valid.poke(valid.B)
    dut.io.status_sources(source).bits.acknowledgement_name.poke(code.U)
    dut.io.status_sources(source).bits.asserted.poke(true.B)
  }

  private def init(dut: RouteARetirementDrainClosureHarness): Unit = {
    dut.io.frontend.valid.poke(false.B); driveLifecycleZero(dut)
    dut.io.retire.valid.poke(false.B); dut.io.retire.bits.session_id.poke(false.B)
    dut.io.retire.bits.transaction_identity.request_id.poke(0.U)
    dut.io.retire.bits.transaction_identity.incarnation.poke(0.U)
    (0 until 8).foreach(source => driveStatus(dut, source, valid = false, code = 0))
    dut.io.r5_reclaim_complete.poke(false.B)
    dut.io.reclaim_permit.ready.poke(false.B)
    dut.io.retire_ack.ready.poke(false.B)
  }

  private def sendStatus(dut: RouteARetirementDrainClosureHarness, source: Int, code: Int): Unit = {
    driveStatus(dut, source, valid = true, code)
    dut.io.status_sources(source).ready.expect(true.B)
    dut.clock.step()
    driveStatus(dut, source, valid = false, code)
    // The collector's one-record latch now presents the exact fact to R6.
    dut.clock.step()
  }

  private def startActiveSession(dut: RouteARetirementDrainClosureHarness): Unit = {
    sendStatus(dut, R1, p.r6.memInitDoneStatusCode)
    sendStatus(dut, R3, p.r6.m2P3InitDoneStatusCode)
    sendStatus(dut, R5, p.r6.pageManagerInitDoneStatusCode)
    dut.io.frontend.bits.event_kind.poke(p.r6.sessionStartEventCode.U)
    dut.io.frontend.bits.context_tokens.poke(32768.U)
    dut.io.frontend.valid.poke(true.B)
    dut.io.frontend.ready.expect(true.B)
    dut.clock.step()
    dut.io.frontend.valid.poke(false.B)
  }

  private def retire(dut: RouteARetirementDrainClosureHarness, rid: Int, incarnation: Int): Unit = {
    dut.io.retire.bits.session_id.poke(false.B)
    dut.io.retire.bits.transaction_identity.request_id.poke(rid.U)
    dut.io.retire.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.retire.valid.poke(true.B)
    dut.io.retire.ready.expect(true.B)
    dut.clock.step()
    dut.io.retire.valid.poke(false.B)
    dut.io.drain_collection_enable.expect(true.B)
  }

  private def sendPreReclaimFacts(dut: RouteARetirementDrainClosureHarness, includeR4: Boolean): Unit = {
    // R1 is intentionally after both R2 partitions: this is the collector's
    // frozen R1 ordering rule, not a service-rate or priority policy.
    Seq(
      (R2Payload, p.r6.r2PayloadDrainedStatusCode),
      (R2Descriptor, p.r6.r2DescriptorDrainedStatusCode),
      (R1, p.r6.r1MemoryDrainedStatusCode),
      (R3, p.r6.r3M2P3DrainedStatusCode),
      (S2, p.r6.s2GqaDrainedStatusCode),
      (DirectPending, p.r6.directPendingDrainedStatusCode),
    ).foreach { case (source, code) => sendStatus(dut, source, code) }
    if (includeR4) sendStatus(dut, R4, p.r6.mergeDrainedStatusCode)
  }

  private def completeR5AndFinalPass(dut: RouteARetirementDrainClosureHarness): Unit = {
    dut.io.r5_reclaim_complete.poke(true.B)
    dut.clock.step()
    dut.io.r5_reclaim_complete.poke(false.B)
    dut.io.reclaim_final_drain_enable.expect(true.B)
    sendStatus(dut, R2Descriptor, p.r6.r2DescriptorDrainedStatusCode)
    sendStatus(dut, R1, p.r6.r1MemoryDrainedStatusCode)
  }

  it("requires every frozen drain member, R5 completion, and final-pass facts before one matching retire acknowledgement") {
    simulate(new RouteARetirementDrainClosureHarness(p)) { dut =>
      init(dut); startActiveSession(dut); retire(dut, rid = 5, incarnation = 3)
      sendPreReclaimFacts(dut, includeR4 = false)
      dut.io.reclaim_permit.valid.expect(false.B)
      dut.io.retire_ack.valid.expect(false.B)

      sendStatus(dut, R4, p.r6.mergeDrainedStatusCode)
      // The last status is accepted first; R6 then observes the complete
      // bitmap and stages the permit in a later control step.
      dut.clock.step(2)
      dut.io.reclaim_permit.valid.expect(true.B)
      dut.io.reclaim_permit.bits.transaction_identity.request_id.expect(5.U)
      dut.io.reclaim_permit.bits.transaction_identity.incarnation.expect(3.U)
      dut.clock.step()
      dut.io.reclaim_permit.valid.expect(true.B)
      dut.io.reclaim_permit.ready.poke(true.B)
      dut.clock.step()
      dut.io.reclaim_permit.ready.poke(false.B)

      // R1 and R2-descriptor final facts cannot pass the collector before the
      // accepted permit's R5 completion; retrying retirement is also illegal.
      driveStatus(dut, R2Descriptor, valid = true, p.r6.r2DescriptorDrainedStatusCode)
      dut.io.status_sources(R2Descriptor).ready.expect(false.B)
      driveStatus(dut, R2Descriptor, valid = false, p.r6.r2DescriptorDrainedStatusCode)
      dut.io.retire.valid.poke(true.B)
      dut.io.retire.ready.expect(false.B)
      dut.io.retire.valid.poke(false.B)
      dut.io.retire_ack.valid.expect(false.B)

      completeR5AndFinalPass(dut)
      dut.io.retire_ack.valid.expect(false.B) // the R5 drain membership is still missing.
      sendStatus(dut, R5, p.r6.r5PageManagerDrainedStatusCode)
      dut.io.retire_ack.valid.expect(true.B)
      dut.io.retire_ack.bits.transaction_identity.request_id.expect(5.U)
      dut.io.retire_ack.bits.transaction_identity.incarnation.expect(3.U)
      dut.clock.step()
      dut.io.retire_ack.valid.expect(true.B)
      dut.io.retire_ack.ready.poke(true.B)
      dut.clock.step()
      dut.io.retire_ack.ready.poke(false.B)
      dut.io.retire_ack.valid.expect(false.B)
    }
  }

  it("preserves permit and retire-ack identity through fixed-seed finite legal stalls before fairness release") {
    simulate(new RouteARetirementDrainClosureHarness(p)) { dut =>
      init(dut); startActiveSession(dut); retire(dut, rid = 6, incarnation = 1)
      sendPreReclaimFacts(dut, includeR4 = true)
      dut.clock.step(2)
      dut.io.reclaim_permit.valid.expect(true.B)

      val random = new Random(0x2_5_3L)
      var heldPermit: Option[(BigInt, BigInt)] = None
      dut.io.reclaim_permit.ready.poke(false.B)
      heldPermit = Some((
        dut.io.reclaim_permit.bits.transaction_identity.request_id.peek().litValue,
        dut.io.reclaim_permit.bits.transaction_identity.incarnation.peek().litValue,
      ))
      dut.clock.step()
      (0 until 9).foreach { _ =>
        val ready = random.nextBoolean()
        dut.io.reclaim_permit.ready.poke(ready.B)
        if (dut.io.reclaim_permit.valid.peekBoolean && !ready) {
          val current = (
            dut.io.reclaim_permit.bits.transaction_identity.request_id.peek().litValue,
            dut.io.reclaim_permit.bits.transaction_identity.incarnation.peek().litValue,
          )
          heldPermit.foreach(previous => assert(current == previous))
          heldPermit = Some(current)
        }
        dut.clock.step()
      }
      dut.io.reclaim_permit.ready.poke(true.B)
      while (dut.io.reclaim_permit.valid.peekBoolean) { dut.clock.step() }
      dut.io.reclaim_permit.ready.poke(false.B)

      completeR5AndFinalPass(dut)
      sendStatus(dut, R5, p.r6.r5PageManagerDrainedStatusCode)
      dut.io.retire_ack.valid.expect(true.B)
      var heldAck: Option[(BigInt, BigInt)] = None
      dut.io.retire_ack.ready.poke(false.B)
      heldAck = Some((
        dut.io.retire_ack.bits.transaction_identity.request_id.peek().litValue,
        dut.io.retire_ack.bits.transaction_identity.incarnation.peek().litValue,
      ))
      dut.clock.step()
      (0 until 7).foreach { _ =>
        val ready = random.nextBoolean()
        dut.io.retire_ack.ready.poke(ready.B)
        if (dut.io.retire_ack.valid.peekBoolean && !ready) {
          val current = (
            dut.io.retire_ack.bits.transaction_identity.request_id.peek().litValue,
            dut.io.retire_ack.bits.transaction_identity.incarnation.peek().litValue,
          )
          heldAck.foreach(previous => assert(current == previous))
          heldAck = Some(current)
        }
        dut.clock.step()
      }
      dut.io.retire_ack.ready.poke(true.B)
      while (dut.io.retire_ack.valid.peekBoolean) { dut.clock.step() }
      assert(heldPermit.contains((BigInt(6), BigInt(1))))
      assert(heldAck.contains((BigInt(6), BigInt(1))))
    }
  }
}
