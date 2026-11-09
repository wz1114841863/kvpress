package kvpress.routea.incremental

import chisel3._
import chisel3.util.{Decoupled, RegEnable, Valid}
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/** Checks once-per-publication facts without accepting attention or changing authority. */
final class RouteAPersistentReadReceiptCollector(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_persistent_read_receipt_collector_v2"
  val io = IO(new Bundle {
    val publication_member_in = Flipped(RouteAChannels.publication_member_observation(p))
    val post_r6_page_ready_in = Flipped(RouteAChannels.post_r6_packed_page_ready_observation(p))
    val mark_ready_out = Decoupled(new PersistentReadReceipt(p))
    val mark_ready_ack_in = Flipped(Decoupled(new PersistentReadMarkAck(p)))
    val page_available_out = Decoupled(new PageAvailableV2(p))
    val receipt_fault_out = Decoupled(new PersistentReadMarkAck(p))
    val readiness_pending_out = Output(Valid(new PersistentReadReceipt(p)))
    val busy = Output(Bool())
  })
  private val Collect = 0.U(3.W)
  private val Mark = 1.U(3.W)
  private val AwaitAck = 2.U(3.W)
  private val Notify = 3.U(3.W)
  private val Fault = 4.U(3.W)
  val state = RegInit(Collect)
  val haveMember = RegInit(false.B)
  val layer = Reg(UInt(6.W))
  val head = Reg(UInt(3.W))
  val tag = Reg(UInt(p.transactionGroupTagWidth.W))
  val nextOrdinal = RegInit(0.U(7.W))
  val receipt = Reg(new PersistentReadReceipt(p))
  val fault = Reg(new PersistentReadMarkAck(p))
  val faultReported = RegInit(false.B)

  io.publication_member_in.ready := state === Collect && !io.post_r6_page_ready_in.valid && nextOrdinal < 64.U
  io.post_r6_page_ready_in.ready := state === Collect
  io.mark_ready_out.valid := state === Mark
  io.mark_ready_out.bits := receipt
  io.mark_ready_ack_in.ready := state === AwaitAck
  io.page_available_out.valid := state === Notify
  io.page_available_out.bits.page_ref := receipt.page_ref
  io.page_available_out.bits.layer := receipt.p3_layer
  io.page_available_out.bits.kv_head := receipt.kv_head
  io.page_available_out.bits.valid_records := receipt.valid_records
  io.page_available_out.bits.transaction_group_tag := receipt.transaction_group_tag
  io.receipt_fault_out.valid := state === Fault && !faultReported
  io.receipt_fault_out.bits := fault
  io.readiness_pending_out.valid := state === Mark || state === AwaitAck
  io.readiness_pending_out.bits := receipt
  io.busy := state =/= Collect || haveMember

  when(io.publication_member_in.fire) {
    val member = io.publication_member_in.bits
    val coordinate = member.logical_position * 288.U + member.layer * 8.U + member.kv_head
    val legal = member.layer < 36.U && member.kv_head < 8.U && member.entry_id === coordinate &&
      member.group_member_ordinal === nextOrdinal &&
      (!haveMember || (member.layer === layer && member.kv_head === head && member.transaction_group_tag === tag))
    assert(legal, "persistent receipt requires the exact R3 member stream")
    when(legal) {
      when(!haveMember) { layer := member.layer; head := member.kv_head; tag := member.transaction_group_tag }
      haveMember := true.B
      nextOrdinal := nextOrdinal + 1.U
    }
  }
  when(io.post_r6_page_ready_in.fire) {
    val ready = io.post_r6_page_ready_in.bits
    val legal = haveMember && ready.p3_layer === layer && ready.transaction_group_tag === tag &&
      ready.valid_records > 0.U && ready.valid_records <= 64.U && ready.valid_records === nextOrdinal
    val joined = Wire(new PersistentReadReceipt(p))
    joined.p3_layer := ready.p3_layer
    joined.p3_stage_generation := ready.p3_stage_generation
    joined.page_ref := ready.page_ref
    joined.transaction_group_tag := ready.transaction_group_tag
    joined.valid_records := ready.valid_records
    joined.kv_head := head
    receipt := joined
    when(legal) { state := Mark }.otherwise {
      fault.receipt := joined
      fault.status := PersistentReadStatus.Invalid.U
      state := Fault
    }
  }
  when(io.mark_ready_out.fire) { state := AwaitAck }
  when(io.mark_ready_ack_in.fire) {
    val ack = io.mark_ready_ack_in.bits
    assert(ack.receipt.asUInt === receipt.asUInt)
    when(ack.status === PersistentReadStatus.OK.U) { state := Notify }.otherwise { fault := ack; state := Fault }
  }
  when(io.page_available_out.fire) { state := Collect; haveMember := false.B; nextOrdinal := 0.U }
  // Report once and retain fail-closed ownership. No retry or group rearm.
  when(io.receipt_fault_out.fire) { faultReported := true.B }
  val markStalled = io.mark_ready_out.valid && !io.mark_ready_out.ready
  val heldMark = RegEnable(io.mark_ready_out.bits, markStalled)
  when(RegNext(markStalled, false.B)) {
    assert(io.mark_ready_out.valid && io.mark_ready_out.bits.asUInt === heldMark.asUInt)
  }
  val noticeStalled = io.page_available_out.valid && !io.page_available_out.ready
  val heldNotice = RegEnable(io.page_available_out.bits, noticeStalled)
  when(RegNext(noticeStalled, false.B)) {
    assert(io.page_available_out.valid && io.page_available_out.bits.asUInt === heldNotice.asUInt)
  }
}
