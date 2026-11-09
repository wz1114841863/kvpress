package kvpress.routea.interfaces

import chisel3._
import chisel3.util.Decoupled
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** Owner-produced runtime hint; this is not a page authority token. */
final class PageAvailableV2(p: RouteASkeletonParameters) extends Bundle {
  val page_ref = new PageRef
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
}

final class PersistentReadTopPort(p: RouteASkeletonParameters) extends Bundle {
  val page_available_out = Decoupled(new PageAvailableV2(p))
  val page_select_in = Flipped(Decoupled(new PersistentReadSelectionV2))
  val rejected_out = Decoupled(new PersistentReadRejectionV2)
  // No attention need exist when receipt installation faults.
  val receipt_fault_out = Decoupled(new PersistentReadMarkAck(p))
}
