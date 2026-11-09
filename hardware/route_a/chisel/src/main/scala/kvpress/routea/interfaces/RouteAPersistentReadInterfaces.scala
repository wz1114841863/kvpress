package kvpress.routea.interfaces

import chisel3._
import chisel3.util.Decoupled
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** Explicit production-v2 results; ready-low is reserved for real backpressure. */
object PersistentReadStatus {
  final val OK = 0
  final val NotReady = 1
  final val Invalid = 2
  final val Fault = 3
  final val Width = 2
}

/** Exact group receipt formed only from accepted R3 members and post-R6 ready. */
final class PersistentReadReceipt(p: RouteASkeletonParameters) extends Bundle {
  val p3_layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val p3_stage_generation = UInt(p.p3StageGenerationWidth.W)
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
}

final class PersistentReadMarkAck(p: RouteASkeletonParameters) extends Bundle {
  val receipt = new PersistentReadReceipt(p)
  val status = UInt(PersistentReadStatus.Width.W)
}

/** The layer/head comes from R6's actual accepted attention, not the page hint. */
final class PersistentReadQuery extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
}

final class PersistentReadResult(p: RouteASkeletonParameters) extends Bundle {
  val grant = new DescriptorLocationGrant(p)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val status = UInt(PersistentReadStatus.Width.W)
}

/** Optional R5 owner-local v2 boundary; absent from every default/v1 instance. */
final class PersistentReadR5Port(p: RouteASkeletonParameters) extends Bundle {
  val mark_ready_in = Flipped(Decoupled(new PersistentReadReceipt(p)))
  val mark_ready_ack_out = Decoupled(new PersistentReadMarkAck(p))
  val query_in = Flipped(Decoupled(new PersistentReadQuery))
  val query_result_out = Decoupled(new PersistentReadResult(p))
  val busy = Output(Bool())
}

final class PersistentReadAvailabilityMarkAck extends Bundle {
  val page_ref = new PageRef
  val accepted = Bool()
}

/** V2 data accompanies the existing held availability response. */
final class PersistentReadAvailabilityPort extends Bundle {
  val mark_update = Flipped(Decoupled(new PageRef))
  val mark_ack = Decoupled(new PersistentReadAvailabilityMarkAck)
  val lookup_read_ready = Output(Bool())
}
