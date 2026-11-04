package kvpress.routea.incremental

import chisel3._
import chisel3.util.{Mux1H, PopCount}

/** Inline combinational RD1 reader. Callers own validity, priority and timing.
  * Each bank accepts at most one M/S/O request; distinct banks remain parallel.
  * No record, valid bit, arbitration decision or ready signal is stored here.
  */
object RouteAMemberRecordReadSharing {
  def apply(
    entries: Vec[Vec[RouteAM2P3MembershipRecord]],
    requests: Seq[(Bool, UInt, UInt)],
  ): Seq[RouteAM2P3MembershipRecord] = {
    require(requests.size == 3, "RD1 shares exactly M/S/O")
    val bankRecords = Wire(Vec(entries.length, new RouteAM2P3MembershipRecord))
    for (bank <- entries.indices) {
      val hits = VecInit(requests.map { case (valid, layer, _) => valid && layer === bank.U })
      assert(PopCount(hits) <= 1.U, "RD1 M/S/O reads must be exclusive within each bank")
      val ordinal = Mux1H(hits, requests.map(_._3))
      bankRecords(bank) := entries(bank)(ordinal)
    }
    requests.map { case (valid, layer, _) =>
      when(valid) { assert(layer < entries.length.U, "RD1 valid read layer must be in range") }
      bankRecords(layer)
    }
  }
}
