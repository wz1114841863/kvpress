package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.{RouteAM2P3MembershipRecord, RouteAMemberRecordReadSharing}
import org.scalatest.funspec.AnyFunSpec

/** Same register image feeds the old independent lookup and production RD1
  * helper. This exercises read behavior, not a second lifecycle authority.
  */
private final class RouteARD1ReadMiter extends Module {
  val io = IO(new Bundle {
    val write = Input(Bool())
    val write_layer = Input(UInt(6.W))
    val write_ordinal = Input(UInt(6.W))
    val write_position = Input(UInt(15.W))
    val write_payload = Input(UInt(64.W))
    val valid = Input(Vec(3, Bool()))
    val layer = Input(Vec(3, UInt(6.W)))
    val ordinal = Input(Vec(3, UInt(6.W)))
    val position = Output(Vec(3, UInt(15.W)))
    val payload = Output(Vec(3, UInt(64.W)))
    val equal = Output(Vec(3, Bool()))
  })
  val entries = Reg(Vec(36, Vec(64, new RouteAM2P3MembershipRecord)))
  when(io.write) {
    entries(io.write_layer)(io.write_ordinal).logical_position := io.write_position
    entries(io.write_layer)(io.write_ordinal).payload_ref := io.write_payload
  }
  val shared = RouteAMemberRecordReadSharing(entries,
    (0 until 3).map(i => (io.valid(i), io.layer(i), io.ordinal(i))))
  for (i <- 0 until 3) {
    val original = entries(io.layer(i))(io.ordinal(i))
    io.position(i) := shared(i).logical_position
    io.payload(i) := shared(i).payload_ref
    io.equal(i) := !io.valid(i) || shared(i).asUInt === original.asUInt
    assert(io.equal(i), "RD1 valid-cycle record must equal the independent reader")
  }
}

final class RouteARD1ReadSharingSpec extends AnyFunSpec with ChiselSim {
  it("preserves all addresses, concurrent banks, stalls, and pre-edge writes") {
    simulate(new RouteARD1ReadMiter) { d =>
      val random = new scala.util.Random(0x524431L)
      val positions = Array.ofDim[Int](36, 64)
      val payloads = Array.ofDim[BigInt](36, 64)
      d.io.write.poke(false.B)
      for (i <- 0 until 3) {
        d.io.valid(i).poke(false.B); d.io.layer(i).poke(0.U); d.io.ordinal(i).poke(0.U)
      }
      for (bank <- 0 until 36; ordinal <- 0 until 64) {
        positions(bank)(ordinal) = random.nextInt(32768)
        payloads(bank)(ordinal) = BigInt(64, random)
        d.io.write.poke(true.B); d.io.write_layer.poke(bank.U); d.io.write_ordinal.poke(ordinal.U)
        d.io.write_position.poke(positions(bank)(ordinal).U)
        d.io.write_payload.poke(payloads(bank)(ordinal).U); d.clock.step()
      }
      d.io.write.poke(false.B)
      def check(i: Int, bank: Int, ordinal: Int): Unit = {
        d.io.equal(i).expect(true.B)
        d.io.position(i).expect(positions(bank)(ordinal).U)
        d.io.payload(i).expect(payloads(bank)(ordinal).U)
      }
      // All 6,912 consumer/address choices; other consumers are inactive.
      for (i <- 0 until 3; bank <- 0 until 36; ordinal <- 0 until 64) {
        for (j <- 0 until 3) d.io.valid(j).poke((j == i).B)
        d.io.layer(i).poke(bank.U); d.io.ordinal(i).poke(ordinal.U)
        check(i, bank, ordinal)
      }
      for (_ <- 0 until 512) {
        val banks = random.shuffle((0 until 36).toList).take(3)
        val ordinals = Seq.fill(3)(random.nextInt(64))
        for (i <- 0 until 3) {
          d.io.valid(i).poke(true.B); d.io.layer(i).poke(banks(i).U); d.io.ordinal(i).poke(ordinals(i).U)
        }
        // No ready/fire input exists in the reader. Hold a live request for
        // three cycles while an independent admission word is updated.
        val writeBank = (0 until 36).find(bank => !banks.contains(bank)).get
        val writeOrdinal = (ordinals.head + 1) % 64
        d.io.write.poke(true.B); d.io.write_layer.poke(writeBank.U); d.io.write_ordinal.poke(writeOrdinal.U)
        val nextPayload = BigInt(64, random); val nextPosition = random.nextInt(32768)
        d.io.write_payload.poke(nextPayload.U); d.io.write_position.poke(nextPosition.U)
        for (i <- 0 until 3) check(i, banks(i), ordinals(i)) // pre-edge old image
        d.clock.step()
        positions(writeBank)(writeOrdinal) = nextPosition; payloads(writeBank)(writeOrdinal) = nextPayload
        d.io.write.poke(false.B)
        for (_ <- 0 until 3) {
          for (i <- 0 until 3) check(i, banks(i), ordinals(i))
          d.clock.step()
        }
      }
      for (mask <- 0 until 8) {
        val banks = Seq(0, 17, 35); val ordinals = Seq(0, 31, 63)
        for (i <- 0 until 3) {
          d.io.valid(i).poke(((mask & (1 << i)) != 0).B)
          d.io.layer(i).poke(banks(i).U); d.io.ordinal(i).poke(ordinals(i).U)
        }
        for (i <- 0 until 3 if (mask & (1 << i)) != 0) check(i, banks(i), ordinals(i))
        d.clock.step()
      }
      // Same-bank write/read retains register read-before-edge semantics.
      for (i <- 0 until 3) {
        for (j <- 0 until 3) d.io.valid(j).poke((i == j).B)
        d.io.layer(i).poke(35.U); d.io.ordinal(i).poke(63.U)
        d.io.write.poke(true.B); d.io.write_layer.poke(35.U); d.io.write_ordinal.poke(63.U)
        d.io.write_position.poke(32767.U); d.io.write_payload.poke("hfedcba9876543210".U)
        check(i, 35, 63); d.clock.step()
        positions(35)(63) = 32767; payloads(35)(63) = BigInt("fedcba9876543210", 16)
        d.io.write.poke(false.B); check(i, 35, 63)
      }
    }
  }
}
