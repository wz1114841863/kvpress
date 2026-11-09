package kvpress.routea.interfaces

import chisel3._
import chisel3.util.Decoupled
import kvpress.routea.params.RouteASkeletonParameters

/** Explicit v2 reservation result. BUSY is progress backpressure; INVALID is not. */
object S2ReservationStatusV2 {
  final val Granted = 0
  final val Busy = 1
  final val Invalid = 2
}

final class S2ReservationResultV2(p: RouteASkeletonParameters) extends Bundle {
  val lease = new S2FillLease(p)
  val status = UInt(2.W)
}

/**
  * This port accepts only R6-authorized preflight reservations. It does not
  * replace the v1 lease port's accepted-plan prerequisite or confer page
  * authority. A GRANTED reservation must proceed to the joint plan accept.
  */
final class PersistentReadS2Port(p: RouteASkeletonParameters) extends Bundle {
  val v2_reservation_request_in = Flipped(Decoupled(new S2FillLeaseRequest(p)))
  val v2_reservation_result_out = Decoupled(new S2ReservationResultV2(p))
}
