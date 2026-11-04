package kvpress.routea.rtl3

import chisel3._
import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import kvpress.routea.incremental.{RouteAM2P3MembershipRecord, RouteAMemberRecordReadSharing}

/** Test-only combinational screen at the full 36 x 64 x 79 geometry. Storage
  * is an identical input image on both sides; its area is deliberately absent.
  * Both sides expose exactly the valid-cycle fields used by M/S/O.
  */
private final class RouteARD1ReadNetwork(shared: Boolean) extends Module {
  override def desiredName: String = if (shared) "rd1_shared_read_network" else "rd1_original_read_network"
  val io = IO(new Bundle {
    val entries = Input(Vec(36, Vec(64, new RouteAM2P3MembershipRecord)))
    val valid = Input(Vec(3, Bool()))
    val layer = Input(Vec(3, UInt(6.W)))
    val ordinal = Input(Vec(3, UInt(6.W)))
    val out_valid = Output(Vec(3, Bool()))
    val position = Output(Vec(3, UInt(15.W)))
    val payload = Output(Vec(3, UInt(64.W)))
  })
  val records = if (shared) RouteAMemberRecordReadSharing(io.entries,
    (0 until 3).map(i => (io.valid(i), io.layer(i), io.ordinal(i))))
  else (0 until 3).map(i => io.entries(io.layer(i))(io.ordinal(i)))
  io.out_valid := io.valid
  for (i <- 0 until 3) {
    io.payload(i) := Mux(io.valid(i), records(i).payload_ref, 0.U)
    io.position(i) := (if (i == 0) 0.U else Mux(io.valid(i), records(i).logical_position, 0.U))
  }
}

object RouteARD1ReadNetworkEmitter extends App {
  require(args.length == 1, "usage: Test / runMain ...RouteARD1ReadNetworkEmitter OUTPUT_ROOT")
  val root = Paths.get(args(0))
  require(!Files.exists(root), "refusing to overwrite a prior screen input")
  Files.createDirectories(root)
  for (shared <- Seq(false, true)) {
    val name = if (shared) "rd1_shared_read_network" else "rd1_original_read_network"
    val sv = ChiselStage.emitSystemVerilog(new RouteARD1ReadNetwork(shared),
      firtoolOpts = Array("--disable-layers=Verification", "--disable-all-randomization", "--strip-debug-info"))
    Files.write(root.resolve(s"$name.sv"), sv.getBytes(StandardCharsets.UTF_8))
  }
  println(s"RD1_SCREEN_INPUT_EMIT_PASS root=$root")
}
