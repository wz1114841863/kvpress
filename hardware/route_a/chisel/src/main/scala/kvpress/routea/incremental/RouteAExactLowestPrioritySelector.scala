package kvpress.routea.incremental

import chisel3._
import chisel3.util._

/** PM1 candidate: exact lowest-set-bit selection through fixed-size banks.
  *
  * This helper is combinational. It does not own or reduce the input state,
  * register the result, or change the empty-input convention. The caller
  * remains responsible for using `valid` before consuming `index`.
  */
object RouteAExactLowestPrioritySelector {
  def banked(bits: UInt, entries: Int, bankSize: Int): (Bool, UInt) = {
    require(entries > 0, "PM1 requires at least one input bit")
    require(bits.getWidth == entries, "PM1 input width must equal entries")
    require(bankSize > 1 && isPow2(bankSize), "PM1 bank size must be a power of two")

    val indexWidth = math.max(1, log2Ceil(entries))
    val localWidth = log2Ceil(bankSize)
    val bankCount = (entries + bankSize - 1) / bankSize
    val bankValid = Wire(Vec(bankCount, Bool()))
    val bankOffset = Wire(Vec(bankCount, UInt(localWidth.W)))

    for (bank <- 0 until bankCount) {
      val low = bank * bankSize
      val live = math.min(bankSize, entries - low)
      val liveBits = bits(low + live - 1, low)
      val padded = if (live == bankSize) liveBits else Cat(0.U((bankSize - live).W), liveBits)
      bankValid(bank) := padded.orR
      bankOffset(bank) := PriorityEncoder(padded)
    }

    // Use UInt ordering explicitly: bit/bank zero is the lowest priority
    // index, matching PriorityEncoder(allocatedLine.asUInt) in Page Manager.
    val selectedBank = PriorityEncoder(bankValid.asUInt)
    val selectedOffset = bankOffset(selectedBank)
    val selectedWide = Cat(selectedBank, selectedOffset)
    val valid = bankValid.asUInt.orR
    // Chisel PriorityEncoder returns its terminal index when no input is set.
    // Page Manager guards the index with valid, but preserve that raw output
    // convention as well so the isolated candidate is bit-exact.
    val selected = Mux(valid, selectedWide(indexWidth - 1, 0), (entries - 1).U)
    (valid, selected)
  }
}
