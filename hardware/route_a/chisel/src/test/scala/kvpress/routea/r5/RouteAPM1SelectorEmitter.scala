package kvpress.routea.r5

import chisel3._
import chisel3.util.{PriorityEncoder, log2Ceil}
import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import kvpress.routea.incremental.RouteAExactLowestPrioritySelector

/** Test-only selector screen at the exact 36,720-line Page Manager geometry. */
private final class RouteAPM1SelectorNetwork(banked: Boolean) extends Module {
  private val entries = 36720
  private val indexWidth = log2Ceil(entries)
  override def desiredName: String = if (banked) "pm1_banked_selector" else "pm1_original_selector"
  val io = IO(new Bundle {
    val allocated = Input(UInt(entries.W))
    val selected_valid = Output(Bool())
    val selected_index = Output(UInt(indexWidth.W))
  })
  if (banked) {
    val (valid, index) = RouteAExactLowestPrioritySelector.banked(io.allocated, entries, 64)
    io.selected_valid := valid
    io.selected_index := index
  } else {
    io.selected_valid := io.allocated.orR
    io.selected_index := PriorityEncoder(io.allocated)
  }
}

object RouteAPM1SelectorEmitter extends App {
  require(args.length == 1, "usage: Test / runMain ...RouteAPM1SelectorEmitter OUTPUT_ROOT")
  val root = Paths.get(args(0))
  require(!Files.exists(root), "refusing to overwrite a prior screen input")
  Files.createDirectories(root)
  for (banked <- Seq(false, true)) {
    val name = if (banked) "pm1_banked_selector" else "pm1_original_selector"
    val sv = ChiselStage.emitSystemVerilog(new RouteAPM1SelectorNetwork(banked),
      firtoolOpts = Array("--disable-layers=Verification", "--disable-all-randomization", "--strip-debug-info"))
    Files.write(root.resolve(s"$name.sv"), sv.getBytes(StandardCharsets.UTF_8))
  }
  println(s"PM1_SELECTOR_SCREEN_INPUT_EMIT_PASS root=$root")
}
