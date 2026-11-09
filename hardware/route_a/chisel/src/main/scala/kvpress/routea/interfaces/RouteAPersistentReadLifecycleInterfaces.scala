package kvpress.routea.interfaces

import chisel3._
import chisel3.util.Decoupled
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** Versioned runtime hint. It names a page, but supplies no ownership fact. */
final class PersistentReadSelectionV2 extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
}

/** Observable local rejection, separate from an R6-owned attention terminal. */
final class PersistentReadRejectionV2 extends Bundle {
  val transaction_identity = new TransactionIdentity
  val status = UInt(2.W)
}

final class R6PreflightContextQueryV2 extends Bundle {
  val transaction_identity = new TransactionIdentity
}

/** The owner coordinates originate only in the accepted frontend attention. */
final class R6PreflightContextResultV2 extends Bundle {
  val transaction_identity = new TransactionIdentity
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val eligible = Bool()
}

/** Exact cancellation of a declaration that has not been accepted as a plan. */
final class PreplanRejectV2 extends Bundle {
  val transaction_identity = new TransactionIdentity
}

/** Optional R6 owner ports. The legacy lifecycle IO remains unchanged. */
final class R6PersistentReadPortV2 extends Bundle {
  val context_query_in = Flipped(Decoupled(new R6PreflightContextQueryV2))
  val context_result_out = Decoupled(new R6PreflightContextResultV2)
  val preplan_reject_in = Flipped(Decoupled(new PreplanRejectV2))
  val owners_drained = Input(Bool())
}
