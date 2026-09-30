package kvpress.routea.top

import chisel3._
import chisel3.util.{PriorityEncoder, RegEnable}
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * Lossless serialization only for the named R6 init/drain facts.
  *
  * This module has no token, page, source, publication, R1-live-identity, or
  * lifecycle-terminal ownership. Its one staged ready/valid record is not a
  * physical FIFO selection. The delivered-drain bitmap is reset on leaving
  * retirement and only suppresses duplicate level facts within that one drain
  * collection epoch.
  */
final class RouteAComponentStatusCollector(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_component_status_collector"

  private val sourceCount = 8
  private val R1 = 0
  private val R2Payload = 1
  private val R2Descriptor = 2

  val io = IO(new Bundle {
    val status_sources = Flipped(Vec(sourceCount, RouteAChannels.component_status(p)))
    val drain_collection_enable = Input(Bool())
    // R6 pulse when pre-reclaim R1/R2-descriptor facts become stale because
    // R5 will create one more descriptor maintenance write.
    val reclaim_drain_restart = Input(Bool())
    // Final-pass gate: R1 and R2-descriptor drains are withheld while that
    // maintenance write is live, then replayed after R5 reports completion.
    val reclaim_final_drain_enable = Input(Bool())
    val r1_drain_permitted = Output(Bool())
    val component_status_out = RouteAChannels.component_status(p)
  })

  private def isInit(code: UInt): Bool =
    code === p.r6.memInitDoneStatusCode.U ||
      code === p.r6.m2P3InitDoneStatusCode.U ||
      code === p.r6.pageManagerInitDoneStatusCode.U

  private def drainBit(code: UInt): UInt = {
    val bit = WireDefault(0.U(8.W))
    when(code === p.r6.r1MemoryDrainedStatusCode.U) { bit := "b00000001".U }
    when(code === p.r6.r2PayloadDrainedStatusCode.U) { bit := "b00000010".U }
    when(code === p.r6.r2DescriptorDrainedStatusCode.U) { bit := "b00000100".U }
    when(code === p.r6.r3M2P3DrainedStatusCode.U) { bit := "b00001000".U }
    when(code === p.r6.r5PageManagerDrainedStatusCode.U) { bit := "b00010000".U }
    when(code === p.r6.s2GqaDrainedStatusCode.U) { bit := "b00100000".U }
    when(code === p.r6.directPendingDrainedStatusCode.U) { bit := "b01000000".U }
    when(code === p.r6.mergeDrainedStatusCode.U) { bit := "b10000000".U }
    bit
  }

  val deliveredDrains = RegInit(0.U(8.W))
  when(!io.drain_collection_enable) { deliveredDrains := 0.U }
    .elsewhen(io.reclaim_drain_restart) { deliveredDrains := deliveredDrains & "b11111010".U }
  io.r1_drain_permitted := io.drain_collection_enable &&
    (deliveredDrains & "b00000110".U) === "b00000110".U

  val eligible = Wire(Vec(sourceCount, Bool()))
  for (source <- 0 until sourceCount) {
    val status = io.status_sources(source).bits
    val initOffer = !io.drain_collection_enable && isInit(status.acknowledgement_name)
    val statusDrainBit = drainBit(status.acknowledgement_name)
    val finalPassSuppressed = if (source == R1 || source == R2Descriptor) !io.reclaim_final_drain_enable else false.B
    val drainOffer = io.drain_collection_enable && !finalPassSuppressed && statusDrainBit.orR &&
      (deliveredDrains & statusDrainBit) === 0.U
    // R1 may declare empty only after R2 has stopped future issue and drained
    // both frozen R2 partitions. This is ordering, not a substitute predicate.
    val r1OrderingOk = if (source == R1) !drainOffer || io.r1_drain_permitted else true.B
    eligible(source) := io.status_sources(source).valid && status.asserted &&
      (initOffer || drainOffer) && r1OrderingOk
  }
  val anyEligible = eligible.asUInt.orR
  val selected = PriorityEncoder(eligible)

  val stagedValid = RegInit(false.B)
  val stagedStatus = Reg(new ComponentStatus(p))
  val stagedDrainBit = Reg(UInt(8.W))

  for (source <- 0 until sourceCount) {
    io.status_sources(source).ready := !stagedValid && anyEligible && selected === source.U
  }
  when(!stagedValid && anyEligible) {
    stagedValid := true.B
    stagedStatus := io.status_sources(selected).bits
    stagedDrainBit := drainBit(io.status_sources(selected).bits.acknowledgement_name)
  }

  io.component_status_out.valid := stagedValid
  io.component_status_out.bits := stagedStatus
  when(io.component_status_out.fire) {
    when(stagedDrainBit.orR) { deliveredDrains := deliveredDrains | stagedDrainBit }
    stagedValid := false.B
  }

  // A one-record staging latch makes output payload stable under R6 ready-low.
  val heldStatus = RegEnable(io.component_status_out.bits,
    io.component_status_out.valid && !io.component_status_out.ready)
  when(RegNext(io.component_status_out.valid && !io.component_status_out.ready, false.B)) {
    assert(io.component_status_out.bits.asUInt === heldStatus.asUInt)
  }
  when(io.component_status_out.fire) {
    assert(isInit(stagedStatus.acknowledgement_name) || stagedDrainBit.orR)
  }
}
