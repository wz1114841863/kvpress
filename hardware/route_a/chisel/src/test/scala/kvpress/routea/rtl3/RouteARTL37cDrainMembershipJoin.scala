package kvpress.routea.rtl3

import chisel3._
import chisel3.util.RegEnable
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * RTL3.7-C testbench-only two-domain drain join.
  *
  * Route-A's frozen R6 collector has one bit per logical drain kind, not one
  * bit per R1/R2 wrapper.  This adapter therefore emits that bit only after
  * both the publication wrapper and the separately-bound C2 wrapper report
  * the exact same asserted drain fact.  It does not change the production
  * collector, add a status code, own an R6 state transition, or represent a
  * physical interconnect.
  */
final class RouteARTL37cDrainMembershipJoin(
    p: RouteASkeletonParameters,
    expectedAcknowledgement: Int,
    initialAcknowledgement: Option[Int] = None,
) extends Module {
  override def desiredName: String = "testbench_route_a_rtl37c_drain_membership_join"

  val io = IO(new Bundle {
    val publication_status_in = Flipped(RouteAChannels.component_status(p))
    val c2_status_in = Flipped(RouteAChannels.component_status(p))
    val joined_status_out = RouteAChannels.component_status(p)
  })

  val publicationSeen = RegInit(false.B)
  val c2Seen = RegInit(false.B)
  val publicationStatus = Reg(new ComponentStatus(p))
  val c2Status = Reg(new ComponentStatus(p))
  val expected = expectedAcknowledgement.U(p.componentStatusNameWidth.W)
  val isExpectedOrInitial = (status: ComponentStatus) => {
    val expectedMatch = status.acknowledgement_name === expected
    initialAcknowledgement match {
      case Some(initial) => expectedMatch ||
        status.acknowledgement_name === initial.U(p.componentStatusNameWidth.W)
      case None => expectedMatch
    }
  }
  val publicationLegal = io.publication_status_in.bits.asserted &&
    isExpectedOrInitial(io.publication_status_in.bits)
  val c2Legal = io.c2_status_in.bits.asserted &&
    isExpectedOrInitial(io.c2_status_in.bits)

  io.publication_status_in.ready := !publicationSeen && publicationLegal
  io.c2_status_in.ready := !c2Seen && c2Legal
  when(io.publication_status_in.fire) {
    publicationSeen := true.B
    publicationStatus := io.publication_status_in.bits
  }
  when(io.c2_status_in.fire) {
    c2Seen := true.B
    c2Status := io.c2_status_in.bits
  }

  io.joined_status_out.valid := publicationSeen && c2Seen
  io.joined_status_out.bits := publicationStatus
  when(io.joined_status_out.fire) {
    publicationSeen := false.B
    c2Seen := false.B
  }

  val held = RegEnable(io.joined_status_out.bits,
    io.joined_status_out.valid && !io.joined_status_out.ready)
  when(RegNext(io.joined_status_out.valid && !io.joined_status_out.ready, false.B)) {
    assert(io.joined_status_out.valid && io.joined_status_out.bits.asUInt === held.asUInt)
  }
  when(io.joined_status_out.valid) {
    assert(publicationStatus.asserted && c2Status.asserted)
    assert(publicationStatus.acknowledgement_name === c2Status.acknowledgement_name)
    assert(isExpectedOrInitial(publicationStatus))
  }
}
