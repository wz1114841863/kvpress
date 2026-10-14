package kvpress.routea.rtl2

import chisel3._
import chisel3.util.Decoupled
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** Testbench-only payload for the selected immutable authority_transition record. */
final class AuthorityTransitionScoreboardEvent(p: RouteASkeletonParameters) extends Bundle {
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val from_authority = UInt(2.W)
  val to_authority = UInt(2.W)
}

/** Testbench-only selected subset of the existing RTL2.5.5 retire-ack binding. */
final class RouteARetireAckScoreboardObserver extends Module {
  override def desiredName: String = "testbench_route_a_retire_ack_scoreboard_observer"
  val io = IO(new Bundle {
    val retire_ack_in = Flipped(RouteAChannels.session_retire_ack)
    val retire_ack_out = RouteAChannels.session_retire_ack
    val scoreboard_event_out = Decoupled(new RetireAckScoreboardEvent)
  })

  val offer = io.retire_ack_in.valid
  io.retire_ack_out.valid := offer && (!io.retire_ack_out.ready || io.scoreboard_event_out.ready)
  io.retire_ack_out.bits := io.retire_ack_in.bits
  io.scoreboard_event_out.valid := offer && (!io.scoreboard_event_out.ready || io.retire_ack_out.ready)
  io.scoreboard_event_out.bits.acknowledgement := io.retire_ack_in.bits
  io.retire_ack_in.ready := io.retire_ack_out.ready && io.scoreboard_event_out.ready
  assert(io.retire_ack_in.fire === io.retire_ack_out.fire)
  assert(io.retire_ack_out.fire === io.scoreboard_event_out.fire)
}

/**
  * C4-P2's zero-buffer test-only selected-event fork.  It observes only the
  * C0 actual R3->R6 pending-to-packed acceptance and the previously bound C3
  * terminal/C3b retire-ack carriers. It owns no authority, page, lifecycle,
  * event queue, or source state.
  */
final class RouteAC3bEventProvenanceObserver(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "testbench_route_a_c3b_event_provenance_observer"
  val io = IO(new Bundle {
    val authority_transition_in = Flipped(RouteAChannels.r6_authority_transition(p))
    val authority_transition_out = RouteAChannels.r6_authority_transition(p)
    val authority_transition_event_out = Decoupled(new AuthorityTransitionScoreboardEvent(p))
    val attention_terminal_in = Flipped(RouteAChannels.attention_terminal_rsp)
    val attention_terminal_out = RouteAChannels.attention_terminal_rsp
    val attention_terminal_event_out = Decoupled(new AttentionTerminalScoreboardEvent)
    val retire_ack_in = Flipped(RouteAChannels.session_retire_ack)
    val retire_ack_out = RouteAChannels.session_retire_ack
    val retire_ack_event_out = Decoupled(new RetireAckScoreboardEvent)
  })

  val transition = io.authority_transition_in.bits
  val selectedTransition = transition.from_authority === RouteAAuthorityStateCode.Pending.U &&
    transition.to_authority === RouteAAuthorityStateCode.Packed.U
  val transitionOffer = io.authority_transition_in.valid
  io.authority_transition_out.valid := transitionOffer &&
    (!selectedTransition || !io.authority_transition_out.ready || io.authority_transition_event_out.ready)
  io.authority_transition_out.bits := transition
  io.authority_transition_event_out.valid := transitionOffer && selectedTransition &&
    (!io.authority_transition_event_out.ready || io.authority_transition_out.ready)
  io.authority_transition_event_out.bits.entry_id := transition.entry_id
  io.authority_transition_event_out.bits.transaction_group_tag := transition.transaction_group_tag
  io.authority_transition_event_out.bits.from_authority := transition.from_authority
  io.authority_transition_event_out.bits.to_authority := transition.to_authority
  io.authority_transition_in.ready := io.authority_transition_out.ready &&
    (!selectedTransition || io.authority_transition_event_out.ready)
  assert(io.authority_transition_in.fire === io.authority_transition_out.fire)
  when(selectedTransition) {
    assert(io.authority_transition_out.fire === io.authority_transition_event_out.fire)
  }

  val terminalObserver = Module(new RouteAAttentionTerminalScoreboardAdapter)
  terminalObserver.io.attention_terminal_in <> io.attention_terminal_in
  io.attention_terminal_out <> terminalObserver.io.attention_terminal_out
  io.attention_terminal_event_out <> terminalObserver.io.scoreboard_event_out

  val retireObserver = Module(new RouteARetireAckScoreboardObserver)
  retireObserver.io.retire_ack_in <> io.retire_ack_in
  io.retire_ack_out <> retireObserver.io.retire_ack_out
  io.retire_ack_event_out <> retireObserver.io.scoreboard_event_out
}
