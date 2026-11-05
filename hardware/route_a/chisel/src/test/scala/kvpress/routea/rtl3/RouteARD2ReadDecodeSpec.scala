package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.log2Ceil
import kvpress.routea.incremental.RouteAM2P3MembershipRecord
import org.scalatest.funspec.AnyFunSpec

private final class RouteARD2ReadMiter(banks: Int, records: Int) extends Module {
  val io = IO(new Bundle {
    val write = Input(Bool())
    val write_layer = Input(UInt(log2Ceil(banks).W))
    val write_ordinal = Input(UInt(log2Ceil(records).W))
    val write_position = Input(UInt(15.W))
    val write_payload = Input(UInt(64.W))
    val write_suffix = Input(UInt(80.W))
    // Valid is deliberately irrelevant to all four raw validation reads.
    val valid = Input(Vec(4, Bool()))
    val layer = Input(Vec(4, UInt(log2Ceil(banks).W)))
    val ordinal = Input(Vec(4, UInt(log2Ceil(records).W)))
    val data = Output(Vec(4, UInt(159.W)))
    val equal = Output(Vec(4, Bool()))
  })
  val entries = Reg(Vec(banks, Vec(records, new RouteAM2P3MembershipRecord)))
  val suffixes = Reg(Vec(banks, Vec(records, UInt(80.W))))
  when(io.write) {
    entries(io.write_layer)(io.write_ordinal).logical_position := io.write_position
    entries(io.write_layer)(io.write_ordinal).payload_ref := io.write_payload
    suffixes(io.write_layer)(io.write_ordinal) := io.write_suffix
  }
  val baseline = RouteARD2RemainingReads(entries, suffixes, io.layer, io.ordinal, decoded = false)
  val candidate = RouteARD2RemainingReads(entries, suffixes, io.layer, io.ordinal, decoded = true)
  for (i <- 0 until 4) {
    io.data(i) := candidate(i)
    io.equal(i) := candidate(i) === baseline(i)
    when(io.layer(i) < banks.U && io.ordinal(i) < records.U) {
      assert(io.equal(i), "RD2 raw read differs, including valid-low cycles")
    }
  }
}

final class RouteARD2ReadDecodeSpec extends AnyFunSpec with ChiselSim {
  // Bound C++ build memory without changing the simulated RTL or stimulus.
  private implicit val rd2Simulator: chisel3.simulator.HasSimulator =
    chisel3.simulator.HasSimulator.simulators.verilator(
      verilatorSettings = svsim.verilator.Backend.CompilationSettings.default
        .withOutputSplit(Some(2000))
        .withOutputSplitCFuncs(Some(200))
        .withParallelism(Some(svsim.verilator.Backend.CompilationSettings.Parallelism.Different.default
          .withBuild(Some(1)).withVerilate(Some(2)))),
    )
  for ((banks, records) <- Seq((4, 8), (36, 64))) {
    it(s"preserves independent raw reads and pre-edge writes at $banks x $records") {
      simulate(new RouteARD2ReadMiter(banks, records)) { d =>
        val random = new scala.util.Random(0x524432L)
        val positions = Array.ofDim[BigInt](banks, records)
        val payloads = Array.ofDim[BigInt](banks, records)
        val suffixes = Array.ofDim[BigInt](banks, records)
        d.io.write.poke(false.B)
        for (i <- 0 until 4) {
          d.io.valid(i).poke(false.B); d.io.layer(i).poke(0.U); d.io.ordinal(i).poke(0.U)
        }
        for (bank <- 0 until banks; ordinal <- 0 until records) {
          positions(bank)(ordinal) = BigInt(15, random)
          payloads(bank)(ordinal) = BigInt(64, random)
          suffixes(bank)(ordinal) = BigInt(80, random)
          d.io.write.poke(true.B); d.io.write_layer.poke(bank.U); d.io.write_ordinal.poke(ordinal.U)
          d.io.write_position.poke(positions(bank)(ordinal).U)
          d.io.write_payload.poke(payloads(bank)(ordinal).U)
          d.io.write_suffix.poke(suffixes(bank)(ordinal).U); d.clock.step()
        }
        d.io.write.poke(false.B)
        def check(i: Int, bank: Int, ordinal: Int): Unit = {
          val member = (positions(bank)(ordinal) << 64) | payloads(bank)(ordinal)
          val expected = i match {
            case 0 => suffixes(bank)(ordinal)
            case 1 => (suffixes(bank)(ordinal) << 64) | payloads(bank)(ordinal)
            case 2 => payloads(bank)(ordinal)
            case 3 => member
          }
          d.io.equal(i).expect(true.B); d.io.data(i).expect(expected.U)
        }
        // Every address on every independent reader, always valid-low.
        for (bank <- 0 until banks; ordinal <- 0 until records) {
          for (i <- 0 until 4) {
            d.io.layer(i).poke(bank.U); d.io.ordinal(i).poke(ordinal.U)
            check(i, bank, ordinal)
          }
        }
        // Same-bank different ordinals, different banks, and all validity masks.
        for (cycle <- 0 until 256) {
          val selectedBanks = Seq.fill(4)(if (cycle % 2 == 0) cycle % banks else random.nextInt(banks))
          val selectedOrdinals = Seq.fill(4)(random.nextInt(records))
          for (i <- 0 until 4) {
            d.io.valid(i).poke(((cycle & (1 << i)) != 0).B)
            d.io.layer(i).poke(selectedBanks(i).U); d.io.ordinal(i).poke(selectedOrdinals(i).U)
          }
          val bank = selectedBanks.head; val ordinal = selectedOrdinals.head
          val position = BigInt(15, random); val payload = BigInt(64, random); val suffix = BigInt(80, random)
          d.io.write.poke(true.B); d.io.write_layer.poke(bank.U); d.io.write_ordinal.poke(ordinal.U)
          d.io.write_position.poke(position.U); d.io.write_payload.poke(payload.U); d.io.write_suffix.poke(suffix.U)
          for (i <- 0 until 4) check(i, selectedBanks(i), selectedOrdinals(i))
          d.clock.step()
          positions(bank)(ordinal) = position; payloads(bank)(ordinal) = payload; suffixes(bank)(ordinal) = suffix
          d.io.write.poke(false.B)
          for (_ <- 0 until 3) {
            for (i <- 0 until 4) check(i, selectedBanks(i), selectedOrdinals(i))
            d.clock.step()
          }
        }
      }
    }
  }
}
