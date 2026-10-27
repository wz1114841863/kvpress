package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAP3StageArrayBoundary
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Logical P3 wrapper protocol check.  This uses no macro model: it proves
  * only that the parent can observe exact write acknowledgements and that a
  * tagged read response is held under parent backpressure.
  */
final class RouteAP3StageArrayBoundarySpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=16, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  it("acknowledges exact writes and holds an identity-tagged payload response") {
    simulate(new RouteAP3StageArrayBoundary(p)) { dut =>
      dut.io.payload_write_req.valid.poke(false.B); dut.io.payload_write_ack.ready.poke(false.B)
      dut.io.sidecar_write_req.valid.poke(false.B); dut.io.sidecar_write_ack.ready.poke(false.B)
      dut.io.payload_read_req.valid.poke(false.B); dut.io.payload_read_rsp.ready.poke(false.B)
      dut.clock.step()

      val write = dut.io.payload_write_req.bits
      write.layer.poke(2.U); write.fragment.poke(5.U); write.data.poke("h55".U)
      dut.io.payload_write_req.valid.poke(true.B); dut.io.payload_write_req.ready.expect(true.B)
      dut.clock.step(); dut.io.payload_write_req.valid.poke(false.B)
      dut.io.payload_write_ack.valid.expect(true.B)
      dut.io.payload_write_ack.bits.layer.expect(2.U); dut.io.payload_write_ack.bits.fragment.expect(5.U)
      dut.clock.step(); dut.io.payload_write_ack.valid.expect(true.B)
      dut.io.payload_write_ack.ready.poke(true.B); dut.clock.step(); dut.io.payload_write_ack.ready.poke(false.B)

      val sidecar = dut.io.sidecar_write_req.bits
      sidecar.layer.poke(2.U); sidecar.ordinal.poke(1.U); sidecar.data.poke(19.U)
      dut.io.sidecar_write_req.valid.poke(true.B); dut.io.sidecar_write_req.ready.expect(true.B)
      dut.clock.step(); dut.io.sidecar_write_req.valid.poke(false.B)
      dut.io.sidecar_write_ack.valid.expect(true.B)
      dut.io.sidecar_write_ack.bits.layer.expect(2.U); dut.io.sidecar_write_ack.bits.ordinal.expect(1.U)
      dut.io.sidecar_write_ack.ready.poke(true.B); dut.clock.step(); dut.io.sidecar_write_ack.ready.poke(false.B)

      val read = dut.io.payload_read_req.bits
      read.layer.poke(2.U); read.fragment.poke(5.U)
      dut.io.payload_read_req.valid.poke(true.B); dut.io.payload_read_req.ready.expect(true.B)
      dut.clock.step(); dut.io.payload_read_req.valid.poke(false.B)
      dut.io.payload_read_rsp.valid.expect(true.B)
      dut.io.payload_read_rsp.bits.layer.expect(2.U); dut.io.payload_read_rsp.bits.fragment.expect(5.U)
      dut.io.payload_read_rsp.bits.data.expect("h55".U)
      dut.clock.step(); dut.io.payload_read_rsp.valid.expect(true.B)
      dut.io.payload_read_rsp.ready.poke(true.B); dut.clock.step()
    }
  }
}
