package kvpress.routea.rtl3

import chisel3._
import chisel3.util.Cat
import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import kvpress.routea.incremental.{RouteAM2P3MembershipRecord, RouteAMemberRecordReadSharing, RouteARecordReadDecode}

/** Four independent raw reads remaining after RD1. Order: M suffix,
  * C payload+suffix, F payload, B member. No valid-dependent don't-care.
  */
private[rtl3] object RouteARD2RemainingReads {
  def apply(entries: Vec[Vec[RouteAM2P3MembershipRecord]], suffixes: Vec[Vec[UInt]],
      layers: Vec[UInt], ordinals: Vec[UInt], decoded: Boolean): Seq[UInt] = {
    require(layers.length == 4 && ordinals.length == 4)
    val memberWords = entries.toSeq.map(_.toSeq.map(_.asUInt))
    val suffixWords = suffixes.toSeq.map(_.toSeq)
    val checkedWords = entries.indices.map(bank => entries(bank).indices.map { ordinal =>
      Cat(suffixes(bank)(ordinal), entries(bank)(ordinal).payload_ref)
    })
    val payloadWords = entries.toSeq.map(_.toSeq.map(_.payload_ref))
    if (decoded) Seq(
      RouteARecordReadDecode(suffixWords, layers(0), ordinals(0)),
      RouteARecordReadDecode(checkedWords, layers(1), ordinals(1)),
      RouteARecordReadDecode(payloadWords, layers(2), ordinals(2)),
      RouteARecordReadDecode(memberWords, layers(3), ordinals(3)),
    ) else Seq(
      suffixes(layers(0))(ordinals(0)),
      Cat(suffixes(layers(1))(ordinals(1)), entries(layers(1))(ordinals(1)).payload_ref),
      entries(layers(2))(ordinals(2)).payload_ref,
      entries(layers(3))(ordinals(3)).asUInt,
    )
  }
}

/** Both sides retain the RD1 M/S/O reader and the same input storage image.
  * RD2 changes only the four remaining readers above. All their raw outputs
  * remain observable even when the corresponding consumer valid is low.
  */
private[rtl3] final class RouteARD2ReadNetwork(decoded: Boolean) extends Module {
  override def desiredName: String = if (decoded) "rd2_decoded_read_network" else "rd2_rd1_read_network"
  val io = IO(new Bundle {
    val entries = Input(Vec(36, Vec(64, new RouteAM2P3MembershipRecord)))
    val suffixes = Input(Vec(36, Vec(64, UInt(80.W))))
    val valid = Input(Vec(3, Bool()))
    val layer = Input(Vec(3, UInt(6.W)))
    val ordinal = Input(Vec(3, UInt(6.W)))
    val checked_layer = Input(Vec(3, UInt(6.W)))
    val checked_ordinal = Input(Vec(3, UInt(6.W)))
    val out_valid = Output(Vec(3, Bool()))
    val position = Output(Vec(3, UInt(15.W)))
    val payload = Output(Vec(3, UInt(64.W)))
    val materializer_suffix = Output(UInt(80.W))
    val checked_record = Output(UInt(144.W))
    val fragment_payload = Output(UInt(64.W))
    val bind_member = Output(UInt(79.W))
  })
  val shared = RouteAMemberRecordReadSharing(io.entries,
    (0 until 3).map(i => (io.valid(i), io.layer(i), io.ordinal(i))))
  io.out_valid := io.valid
  for (i <- 0 until 3) {
    io.payload(i) := Mux(io.valid(i), shared(i).payload_ref, 0.U)
    io.position(i) := (if (i == 0) 0.U else Mux(io.valid(i), shared(i).logical_position, 0.U))
  }
  val layers = VecInit(Seq(io.layer(0)) ++ io.checked_layer.toSeq)
  val ordinals = VecInit(Seq(io.ordinal(0)) ++ io.checked_ordinal.toSeq)
  val reads = RouteARD2RemainingReads(io.entries, io.suffixes, layers, ordinals, decoded)
  io.materializer_suffix := reads(0)
  io.checked_record := reads(1)
  io.fragment_payload := reads(2)
  io.bind_member := reads(3)
}

object RouteARD2ReadNetworkEmitter extends App {
  require(args.length == 1, "usage: Test / runMain ...RouteARD2ReadNetworkEmitter OUTPUT_ROOT")
  val root = Paths.get(args(0))
  require(!Files.exists(root), "refusing to overwrite screen input")
  Files.createDirectories(root)
  for (decoded <- Seq(false, true)) {
    val name = if (decoded) "rd2_decoded_read_network" else "rd2_rd1_read_network"
    val sv = ChiselStage.emitSystemVerilog(new RouteARD2ReadNetwork(decoded),
      firtoolOpts = Array("--disable-layers=Verification", "--disable-all-randomization", "--strip-debug-info"))
    Files.write(root.resolve(s"$name.sv"), sv.getBytes(StandardCharsets.UTF_8))
  }
  println(s"RD2_SCREEN_INPUT_EMIT_PASS root=$root")
}
