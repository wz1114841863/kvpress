package kvpress.routea.r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.{PriorityEncoder, log2Ceil}
import kvpress.routea.incremental.RouteAExactLowestPrioritySelector
import org.scalatest.funspec.AnyFunSpec

private final class RouteAPM1SelectorMiter(entries: Int, bankSize: Int, compareReference: Boolean = true) extends Module {
  private val indexWidth = math.max(1, log2Ceil(entries))
  private val bankCount = (entries + bankSize - 1) / bankSize
  val io = IO(new Bundle {
    // Bank-sized ports avoid a simulator-only >8K-bit initialization warning.
    val banks = Input(Vec(bankCount, UInt(bankSize.W)))
    val valid = Output(Bool())
    val index = Output(UInt(indexWidth.W))
    val equal = Output(Bool())
  })
  val bits = io.banks.asUInt(entries - 1, 0)
  val (candidateValid, candidateIndex) =
    RouteAExactLowestPrioritySelector.banked(bits, entries, bankSize)
  io.valid := candidateValid
  io.index := candidateIndex
  io.equal := (if (compareReference) {
    val referenceValid = bits.orR
    val referenceIndex = PriorityEncoder(bits)
    candidateValid === referenceValid && candidateIndex === referenceIndex
  } else true.B)
  assert(io.equal, "PM1 banked selector must equal the original lowest-set-bit selector")
}

final class RouteAPM1ExactPrioritySelectorSpec extends AnyFunSpec with ChiselSim {
  private def check(d: RouteAPM1SelectorMiter, value: BigInt, entries: Int, bankSize: Int, expected: Int): Unit = {
    for (bank <- d.io.banks.indices) {
      val word = (value >> (bank * bankSize)) & ((BigInt(1) << bankSize) - 1)
      d.io.banks(bank).poke(word.U)
    }
    d.io.equal.expect(true.B)
    d.io.valid.expect((value != 0).B)
    d.io.index.expect(expected.U)
  }

  it("is exhaustive across partial banks at a bounded geometry") {
    val entries = 13
    val bankSize = 8
    simulate(new RouteAPM1SelectorMiter(entries, 8)) { d =>
      for (value <- 0 until (1 << entries)) {
        val expected = if (value == 0) entries - 1 else Integer.numberOfTrailingZeros(value)
        check(d, BigInt(value), entries, bankSize, expected)
      }
    }
  }

  it("preserves zero, every one-hot index, bank boundaries, and random full-scale patterns") {
    val entries = 36720
    val bankSize = 64
    simulate(new RouteAPM1SelectorMiter(entries, bankSize, compareReference = false)) { d =>
      for (bank <- d.io.banks.indices) d.io.banks(bank).poke(0.U)
      d.io.equal.expect(true.B); d.io.valid.expect(false.B); d.io.index.expect((entries - 1).U)

      for (bank <- d.io.banks.indices) d.io.banks(bank).poke(((BigInt(1) << bankSize) - 1).U)
      d.io.equal.expect(true.B); d.io.valid.expect(true.B); d.io.index.expect(0.U)

      // Only one bank word changes per one-hot step.
      for (bank <- d.io.banks.indices) d.io.banks(bank).poke(0.U)
      for (index <- 0 until entries) {
        if (index > 0 && index % bankSize == 0) d.io.banks(index / bankSize - 1).poke(0.U)
        d.io.banks(index / bankSize).poke((BigInt(1) << (index % bankSize)).U)
        d.io.equal.expect(true.B); d.io.valid.expect(true.B); d.io.index.expect(index.U)
      }

      val boundaryIndices = Seq(0, 1, 62, 63, 64, 65, 127, 128, 36671, 36672, 36718, 36719)
      for (low <- boundaryIndices; high <- boundaryIndices if high > low) {
        check(d, (BigInt(1) << low) | (BigInt(1) << high), entries, bankSize, low)
      }

      val random = new scala.util.Random(0x504d31L)
      for (_ <- 0 until 512) {
        val value = BigInt(entries, random)
        check(d, value, entries, bankSize, value.lowestSetBit)
      }
      for (_ <- 0 until 512) {
        val indices = Seq.fill(8)(random.nextInt(entries))
        val value = indices.foldLeft(BigInt(0))((acc, index) => acc.setBit(index))
        check(d, value, entries, bankSize, indices.min)
      }
    }
  }
}
