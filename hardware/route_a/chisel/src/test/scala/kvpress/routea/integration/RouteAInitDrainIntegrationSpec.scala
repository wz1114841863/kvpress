package kvpress.routea.integration

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.{RouteAComponentStatusCollector, RouteAKVSubsystemTop}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL1-I1 directed integration checks only. They exercise reset/init and
  * empty-session retirement; they model neither payload delivery, controller
  * timing, physical queues, numeric merge, nor a complete R3/R5 lifecycle.
  */
final class RouteAInitDrainHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend_lifecycle_req = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val session_retire_ack = RouteAChannels.session_retire_ack
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
  })

  val subsystem = Module(new RouteAKVSubsystemTop(p))
  subsystem.core_clk := clock
  subsystem.destructive_reset := reset.asBool
  subsystem.frontend_lifecycle_req <> io.frontend_lifecycle_req
  subsystem.runtime_retire_req <> io.runtime_retire_req
  StructuralTieOff.source(subsystem.source_plan_declaration_in)
  StructuralTieOff.source(subsystem.hot_payload_fragment_in)
  StructuralTieOff.source(subsystem.hot_position_sidecar_in)
  // C9 adds named verification-environment ingress for the composed C2/C3/C4
  // endpoint path.  Init/drain deliberately exercises none of those paths;
  // make that inert boundary explicit rather than leaving inputs implicit.
  StructuralTieOff.source(subsystem.verification_p3_pack_read_work_in)
  StructuralTieOff.source(subsystem.verification_direct_pending_open_in)
  StructuralTieOff.source(subsystem.verification_direct_pending_read_work_in)
  StructuralTieOff.source(subsystem.verification_s2_sidecar_fragment_in)
  StructuralTieOff.source(subsystem.verification_s2_sidecar_complete_in)
  StructuralTieOff.sink(subsystem.verification_direct_pending_payload_fragment_out)
  io.attention_terminal_rsp <> subsystem.attention_terminal_rsp
  io.session_retire_ack <> subsystem.session_retire_ack
  io.external_core_mem_if_v1 <> subsystem.external_core_mem_if_v1
}

final class RouteAInitDrainIntegrationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    // The composed top includes C4's fixed 64-record packed-page endpoint:
    // count must represent 512 and index must represent 0..511.  These are
    // logical carrier widths, not a physical port or controller selection.
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def driveLifecycleZero(dut: RouteAInitDrainHarness): Unit = {
    val bits = dut.io.frontend_lifecycle_req.bits
    bits.event_kind.poke(0.U); bits.session_id.poke(false.B); bits.context_tokens.poke(0.U)
    bits.entry_id.poke(0.U); bits.layer.poke(0.U); bits.kv_head.poke(0.U); bits.logical_position.poke(0.U)
    bits.payload_ref.poke(0.U); bits.disposition.poke(false.B)
    bits.transaction_identity.request_id.poke(0.U); bits.transaction_identity.incarnation.poke(0.U)
  }

  private def initTop(dut: RouteAInitDrainHarness): Unit = {
    dut.io.frontend_lifecycle_req.valid.poke(false.B); driveLifecycleZero(dut)
    dut.io.runtime_retire_req.valid.poke(false.B); dut.io.runtime_retire_req.bits.session_id.poke(false.B)
    dut.io.runtime_retire_req.bits.transaction_identity.request_id.poke(0.U)
    dut.io.runtime_retire_req.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.attention_terminal_rsp.ready.poke(true.B); dut.io.session_retire_ack.ready.poke(true.B)
    dut.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)
    dut.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(false.B)
    dut.io.external_core_mem_if_v1.request.ready.poke(true.B)
    dut.io.external_core_mem_if_v1.response.valid.poke(false.B)
    dut.io.external_core_mem_if_v1.response.bits.transaction_identity.request_id.poke(0.U)
    dut.io.external_core_mem_if_v1.response.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.external_core_mem_if_v1.response.bits.fragment_index.poke(0.U)
    dut.io.external_core_mem_if_v1.response.bits.last.poke(false.B)
    dut.io.external_core_mem_if_v1.response.bits.status.poke(p.coreMemoryOkStatusCode.U)
    dut.io.external_core_mem_if_v1.response.bits.data.poke(0.U)
  }

  it("allows session start only after the dedicated adapter acknowledgement and all three named init facts") {
    simulate(new RouteAInitDrainHarness(p)) { dut =>
      initTop(dut)
      dut.io.frontend_lifecycle_req.bits.event_kind.poke(p.r6.sessionStartEventCode.U)
      dut.io.frontend_lifecycle_req.bits.context_tokens.poke(32768.U)
      dut.io.frontend_lifecycle_req.valid.poke(true.B)
      dut.io.frontend_lifecycle_req.ready.expect(false.B)
      dut.io.frontend_lifecycle_req.valid.poke(false.B)

      dut.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(true.B)
      dut.io.external_core_mem_if_v1.init_ack.valid.poke(true.B)
      dut.io.external_core_mem_if_v1.init_ack.ready.expect(true.B)
      dut.clock.step()
      dut.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)

      // R1, R3/M2/P3, and R5 each traverse the one-record collector before
      // lifecycle can leave reset. More cycles here are only a directed
      // protocol margin, not a latency result.
      (0 until 12).foreach(_ => dut.clock.step())
      dut.io.frontend_lifecycle_req.valid.poke(true.B)
      dut.io.frontend_lifecycle_req.ready.expect(true.B)
      dut.clock.step()
      dut.io.frontend_lifecycle_req.valid.poke(false.B)
    }
  }

  it("returns retire acknowledgement only after all eight local drain facts are serialized") {
    simulate(new RouteAInitDrainHarness(p)) { dut =>
      initTop(dut)
      dut.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(true.B)
      dut.io.external_core_mem_if_v1.init_ack.valid.poke(true.B); dut.clock.step()
      dut.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)
      (0 until 12).foreach(_ => dut.clock.step())

      dut.io.frontend_lifecycle_req.bits.event_kind.poke(p.r6.sessionStartEventCode.U)
      dut.io.frontend_lifecycle_req.bits.context_tokens.poke(32768.U)
      dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B)
      dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)

      dut.io.runtime_retire_req.bits.transaction_identity.request_id.poke(3.U)
      dut.io.runtime_retire_req.bits.transaction_identity.incarnation.poke(1.U)
      dut.io.runtime_retire_req.valid.poke(true.B); dut.io.runtime_retire_req.ready.expect(true.B)
      dut.clock.step(); dut.io.runtime_retire_req.valid.poke(false.B)

      // One staged fact needs a source handshake and a later R6 handshake;
      // before eight such facts cannot have completed, retire ack is forbidden.
      (0 until 12).foreach { _ =>
        dut.io.session_retire_ack.valid.expect(false.B)
        dut.clock.step()
      }
      // Hold the outward handshake only to observe the eventual acknowledgement;
      // it does not change the local drain predicates or imply a latency bound.
      dut.io.session_retire_ack.ready.poke(false.B)
      (0 until 12).foreach(_ => dut.clock.step())
      dut.io.session_retire_ack.valid.expect(true.B)
      dut.io.session_retire_ack.bits.transaction_identity.request_id.expect(3.U)
      dut.io.session_retire_ack.bits.transaction_identity.incarnation.expect(1.U)
    }
  }
}

final class RouteAComponentStatusCollectorSpec extends AnyFunSpec with ChiselSim {
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

  private def driveSource(dut: RouteAComponentStatusCollector, source: Int, valid: Boolean, code: Int): Unit = {
    dut.io.status_sources(source).valid.poke(valid.B)
    dut.io.status_sources(source).bits.acknowledgement_name.poke(code.U)
    dut.io.status_sources(source).bits.asserted.poke(true.B)
  }

  private def init(dut: RouteAComponentStatusCollector): Unit = {
    dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.reclaim_drain_restart.poke(false.B); dut.io.reclaim_final_drain_enable.poke(true.B)
    (0 until 8).foreach(source => driveSource(dut, source, valid = false, code = 0))
  }

  private def captureOne(dut: RouteAComponentStatusCollector, code: Int): Unit = {
    dut.clock.step()
    dut.io.component_status_out.valid.expect(true.B)
    dut.io.component_status_out.bits.acknowledgement_name.expect(code.U)
    dut.clock.step()
  }

  it("holds R1 drain until both R2 drain partitions have been delivered") {
    simulate(new RouteAComponentStatusCollector(p)) { dut =>
      init(dut); dut.io.drain_collection_enable.poke(true.B)
      driveSource(dut, 0, valid = true, p.r6.r1MemoryDrainedStatusCode)
      dut.clock.step(); dut.io.component_status_out.valid.expect(false.B)

      driveSource(dut, 1, valid = true, p.r6.r2PayloadDrainedStatusCode)
      captureOne(dut, p.r6.r2PayloadDrainedStatusCode)
      driveSource(dut, 1, valid = false, 0)
      driveSource(dut, 2, valid = true, p.r6.r2DescriptorDrainedStatusCode)
      captureOne(dut, p.r6.r2DescriptorDrainedStatusCode)
      driveSource(dut, 2, valid = false, 0)
      dut.io.r1_drain_permitted.expect(true.B)
      captureOne(dut, p.r6.r1MemoryDrainedStatusCode)
    }
  }
}
