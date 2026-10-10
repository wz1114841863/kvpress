package kvpress.routea.rtl3

import chisel3._
import chisel3.util.RegEnable
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * RTL3.7-B testbench-only bridge from a typed packed-S2 endpoint terminal to
  * the already frozen packed-read association terminal.  It remembers only
  * the exact work record that it forwards to the existing producer; it neither
  * selects a page, allocates S2, owns an R1/R2 context, nor changes S2 state.
  *
  * The bridge emits the association terminal only after the real S2 wrapper
  * has accepted the endpoint terminal. It is deliberately not instantiated in
  * the production top and makes no controller, timing, or physical-memory
  * claim.
  */
final class RouteARTL37bPackedReadTerminalBridge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_rtl37b_packed_read_terminal_bridge"

  val io = IO(new Bundle {
    val work_in = Flipped(RouteAChannels.packed_s2_read_work(p))
    val work_out = RouteAChannels.packed_s2_read_work(p)
    val endpoint_terminal_in = Flipped(RouteAChannels.s2_fill_terminal(p))
    val s2_terminal_out = RouteAChannels.s2_fill_terminal(p)
    val association_terminal_out = RouteAChannels.packed_read_terminal(p)
  })

  val workActive = RegInit(false.B)
  val work = Reg(new PackedS2ReadWork(p))
  val terminalPending = RegInit(false.B)
  val terminal = Reg(new PackedReadTerminal(p))

  io.work_out.valid := io.work_in.valid && !workActive && !terminalPending
  io.work_out.bits := io.work_in.bits
  io.work_in.ready := io.work_out.ready && !workActive && !terminalPending
  when(io.work_in.fire) {
    work := io.work_in.bits
    workActive := true.B
  }

  val endpoint = io.endpoint_terminal_in.bits
  val endpointMatches = workActive && !terminalPending &&
    endpoint.transaction_identity.asUInt === work.transaction_identity.asUInt &&
    endpoint.s2_slot === work.s2_slot &&
    endpoint.source_generation === work.source_generation
  io.s2_terminal_out.valid := io.endpoint_terminal_in.valid && endpointMatches
  io.s2_terminal_out.bits := endpoint
  io.endpoint_terminal_in.ready := io.s2_terminal_out.ready && endpointMatches
  // The packed endpoint emits an S2 terminal for every payload fragment so
  // that S2 can advance its checked fragment ordinal.  The association, in
  // contrast, has exactly one terminal/release: it is formed only from the
  // final endpoint terminal.  Earlier terminals pass through to S2 without
  // ending the captured work context.
  when(io.endpoint_terminal_in.fire && endpoint.last) {
    terminal.transaction_identity := work.transaction_identity
    terminal.page_ref := work.page_ref
    terminal.s2_slot := work.s2_slot
    terminal.source_generation := work.source_generation
    terminal.delivery_context_ref := work.delivery_context_ref
    terminal.status := endpoint.status
    terminalPending := true.B
  }

  io.association_terminal_out.valid := terminalPending
  io.association_terminal_out.bits := terminal
  when(io.association_terminal_out.fire) {
    terminalPending := false.B
    workActive := false.B
  }

  val heldWork = RegEnable(io.work_out.bits, io.work_out.valid && !io.work_out.ready)
  when(RegNext(io.work_out.valid && !io.work_out.ready, false.B)) {
    assert(io.work_out.bits.asUInt === heldWork.asUInt)
  }
  val heldEndpointTerminal = RegEnable(io.s2_terminal_out.bits,
    io.s2_terminal_out.valid && !io.s2_terminal_out.ready)
  when(RegNext(io.s2_terminal_out.valid && !io.s2_terminal_out.ready, false.B)) {
    assert(io.s2_terminal_out.bits.asUInt === heldEndpointTerminal.asUInt)
  }
  val heldAssociationTerminal = RegEnable(io.association_terminal_out.bits,
    io.association_terminal_out.valid && !io.association_terminal_out.ready)
  when(RegNext(io.association_terminal_out.valid && !io.association_terminal_out.ready, false.B)) {
    assert(io.association_terminal_out.bits.asUInt === heldAssociationTerminal.asUInt)
  }
  when(io.association_terminal_out.valid) {
    assert(workActive)
  }
}

/**
  * RTL3.7-B testbench-only ordering gate. A C2 release observation must be
  * accepted before the same request identity can enter the existing real R6
  * retirement/reclaim path. It forwards neither page ownership nor a drain
  * status; R6/R5 retain their existing global-drain and reclaim ownership.
  */
final class RouteARTL37bReleaseRetireGate(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_rtl37b_release_retire_gate"

  val io = IO(new Bundle {
    val release_in = Flipped(RouteAChannels.packed_read_release_observation(p))
    val release_observation_out = RouteAChannels.packed_read_release_observation(p)
    val runtime_retire_in = Flipped(RouteAChannels.runtime_retire_req)
    val runtime_retire_out = RouteAChannels.runtime_retire_req
  })

  val releaseAccepted = RegInit(false.B)
  val releaseIdentity = Reg(new TransactionIdentity)
  val retireForwarded = RegInit(false.B)

  io.release_observation_out.valid := io.release_in.valid && !releaseAccepted
  io.release_observation_out.bits := io.release_in.bits
  io.release_in.ready := io.release_observation_out.ready && !releaseAccepted
  when(io.release_in.fire) {
    releaseAccepted := true.B
    releaseIdentity := io.release_in.bits.transaction_identity
  }

  val matchingRetire = io.runtime_retire_in.bits.transaction_identity.asUInt === releaseIdentity.asUInt
  io.runtime_retire_out.valid := io.runtime_retire_in.valid && releaseAccepted && !retireForwarded && matchingRetire
  io.runtime_retire_out.bits := io.runtime_retire_in.bits
  io.runtime_retire_in.ready := releaseAccepted && !retireForwarded && matchingRetire && io.runtime_retire_out.ready
  when(io.runtime_retire_out.fire) { retireForwarded := true.B }

  val heldRelease = RegEnable(io.release_observation_out.bits,
    io.release_observation_out.valid && !io.release_observation_out.ready)
  when(RegNext(io.release_observation_out.valid && !io.release_observation_out.ready, false.B)) {
    assert(io.release_observation_out.bits.asUInt === heldRelease.asUInt)
  }
  val heldRetire = RegEnable(io.runtime_retire_out.bits,
    io.runtime_retire_out.valid && !io.runtime_retire_out.ready)
  when(RegNext(io.runtime_retire_out.valid && !io.runtime_retire_out.ready, false.B)) {
    assert(io.runtime_retire_out.bits.asUInt === heldRetire.asUInt)
  }
  when(io.runtime_retire_out.valid) { assert(releaseAccepted && matchingRetire) }
}
