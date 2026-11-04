package kvpress.routea.r5

import chisel3._
import chisel3.util.{Cat, PriorityEncoder, log2Ceil}
import kvpress.routea.incremental.RouteAExactLowestPrioritySelector

/** Test-only PM1 screen with matched Q -> selector -> D boundaries.
  *
  * The shift state is only a compact way to keep every selector input
  * controllable without exposing 36,720 primary inputs. Both sides have the
  * exact same state and result registers; only the selector realization differs.
  */
private[r5] final class RouteAPM1RegisteredSelectorNetwork(
  entries: Int,
  bankSize: Int,
  banked: Boolean,
) extends Module {
  require(entries > 1)
  private val indexWidth = math.max(1, log2Ceil(entries))
  override def desiredName: String =
    if (banked) "pm1_banked_registered_selector" else "pm1_original_registered_selector"

  val io = IO(new Bundle {
    val serial_in = Input(Bool())
    val selected_valid = Output(Bool())
    val selected_index = Output(UInt(indexWidth.W))
  })

  val allocated = RegInit(0.U(entries.W))
  allocated := Cat(allocated(entries - 2, 0), io.serial_in)

  val (valid, index) = if (banked) {
    RouteAExactLowestPrioritySelector.banked(allocated, entries, bankSize)
  } else {
    (allocated.orR, PriorityEncoder(allocated))
  }
  val selectedValid = RegInit(false.B)
  val selectedIndex = RegInit(0.U(indexWidth.W))
  selectedValid := valid
  selectedIndex := index
  io.selected_valid := selectedValid
  io.selected_index := selectedIndex
}
