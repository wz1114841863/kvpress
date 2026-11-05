package kvpress.routea.incremental

import chisel3._
import chisel3.util.Mux1H

/** Experimental RD2 combinational reader. No valid/ready gating, arbitration,
  * storage or cycle change. Callers retain independent concurrent ports.
  * Equivalence domain: in-range bank and ordinal; production is not switched.
  */
object RouteARecordReadDecode {
  def apply(words: Seq[Seq[UInt]], bank: UInt, ordinal: UInt): UInt = {
    require(words.nonEmpty && words.head.nonEmpty)
    require(words.forall(_.size == words.head.size), "RD2 rectangular table required")
    val width = words.head.head.getWidth
    require(words.flatten.forall(_.getWidth == width), "RD2 uniform word widths required")
    val ordinalSelect = words.head.indices.map(index => ordinal === index.U)
    val bankWords = words.map(row => Mux1H(ordinalSelect, row))
    Mux1H(words.indices.map(index => bank === index.U), bankWords)
  }
}
