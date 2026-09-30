package kvpress.routea.r4

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAMergeBoundary
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL1.6 packet/control tests only; this suite makes no FP arithmetic or PPA claim. */
final class RouteAMergeBoundarySpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(dut: RouteAMergeBoundary): Unit = {
    dut.io.drain_collection_enable.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.source_partial_in.valid.poke(false.B); dut.io.consumer_partial_commit.ready.poke(true.B)
    dut.io.merge_req_in.valid.poke(false.B); dut.io.r4_partial_header_in.valid.poke(false.B)
    dut.io.r4_value_fragment_in.valid.poke(false.B); dut.io.r4_result_stub_in.valid.poke(false.B)
    dut.io.r4_numeric_fault_in.valid.poke(false.B); dut.io.merge_rsp_or_numeric_fault.ready.poke(true.B)
    dut.io.merge_req_in.bits.transaction_identity.request_id.poke(0.U); dut.io.merge_req_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.merge_req_in.bits.source_presence.poke(0.U)
    dut.io.r4_partial_header_in.bits.transaction_identity.request_id.poke(0.U); dut.io.r4_partial_header_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.r4_partial_header_in.bits.header.poke(0.U)
    dut.io.r4_value_fragment_in.bits.transaction_identity.request_id.poke(0.U); dut.io.r4_value_fragment_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.r4_value_fragment_in.bits.fragment_index.poke(0.U); dut.io.r4_value_fragment_in.bits.last.poke(false.B); dut.io.r4_value_fragment_in.bits.data.poke(0.U)
    dut.io.r4_result_stub_in.bits.transaction_identity.request_id.poke(0.U); dut.io.r4_result_stub_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.r4_result_stub_in.bits.normalized_value.poke(0.U)
    dut.io.r4_numeric_fault_in.bits.transaction_identity.request_id.poke(0.U); dut.io.r4_numeric_fault_in.bits.transaction_identity.incarnation.poke(0.U)
  }

  private def headerWord(source: Int, consumer: Int, present: Boolean, reserved: BigInt = 0): BigInt = {
    val m = if (present) BigInt(0) else BigInt("ff800000", 16)
    m | (BigInt(source) << 64) | (BigInt(consumer) << 66) |
      (if (present) (BigInt(1) << 69) | (BigInt(8) << 70) else BigInt(0)) |
      (reserved << 74)
  }

  private def sendHeader(dut: RouteAMergeBoundary, rid: Int, incarnation: Int, word: BigInt): Unit = {
    dut.io.r4_partial_header_in.bits.transaction_identity.request_id.poke(rid.U)
    dut.io.r4_partial_header_in.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.r4_partial_header_in.bits.header.poke(word.U); dut.io.r4_partial_header_in.valid.poke(true.B)
    dut.io.r4_partial_header_in.ready.expect(true.B); dut.clock.step(); dut.io.r4_partial_header_in.valid.poke(false.B)
  }

  private def sendMergeRequest(dut: RouteAMergeBoundary, rid: Int, incarnation: Int, presence: Int): Unit = {
    dut.io.merge_req_in.bits.transaction_identity.request_id.poke(rid.U); dut.io.merge_req_in.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.merge_req_in.bits.source_presence.poke(presence.U); dut.io.merge_req_in.valid.poke(true.B)
    dut.io.merge_req_in.ready.expect(true.B); dut.clock.step(); dut.io.merge_req_in.valid.poke(false.B)
  }

  it("accepts frozen absent and ordered present packets, then emits stable consumer commits") {
    simulate(new RouteAMergeBoundary(p)) { dut =>
      init(dut)
      sendHeader(dut, 1, 0, headerWord(source = 1, consumer = 2, present = false))
      dut.io.consumer_partial_commit.valid.expect(true.B); dut.io.consumer_partial_commit.ready.poke(false.B); dut.clock.step()
      dut.io.consumer_partial_commit.bits.transaction_identity.request_id.expect(1.U)
      dut.io.consumer_partial_commit.bits.source_kind.expect(1.U); dut.io.consumer_partial_commit.bits.consumer_id.expect(2.U)
      dut.io.consumer_partial_commit.ready.poke(true.B); dut.clock.step()

      sendHeader(dut, 2, 1, headerWord(source = 2, consumer = 3, present = true))
      for (fragment <- 0 until 8) {
        dut.io.r4_value_fragment_in.bits.transaction_identity.request_id.poke(2.U); dut.io.r4_value_fragment_in.bits.transaction_identity.incarnation.poke(1.U)
        dut.io.r4_value_fragment_in.bits.fragment_index.poke(fragment.U); dut.io.r4_value_fragment_in.bits.last.poke((fragment == 7).B)
        dut.io.r4_value_fragment_in.bits.data.poke(fragment.U); dut.io.r4_value_fragment_in.valid.poke(true.B)
        dut.io.r4_value_fragment_in.ready.expect(true.B); dut.clock.step(); dut.io.r4_value_fragment_in.valid.poke(false.B)
      }
      dut.io.consumer_partial_commit.valid.expect(true.B); dut.io.consumer_partial_commit.bits.source_kind.expect(2.U)
      dut.io.consumer_partial_commit.bits.consumer_id.expect(3.U)
    }
  }

  it("rejects malformed packet structure and out-of-order value fragments without a numeric fallback") {
    simulate(new RouteAMergeBoundary(p)) { dut =>
      init(dut)
      dut.io.r4_partial_header_in.bits.header.poke(headerWord(source = 3, consumer = 0, present = false).U)
      dut.io.r4_partial_header_in.valid.poke(true.B); dut.io.r4_partial_header_in.ready.expect(false.B)
      dut.io.r4_partial_header_in.bits.header.poke(headerWord(source = 0, consumer = 0, present = false, reserved = 1).U)
      dut.io.r4_partial_header_in.ready.expect(false.B); dut.io.r4_partial_header_in.valid.poke(false.B)
      sendHeader(dut, 3, 0, headerWord(source = 0, consumer = 0, present = true))
      dut.io.r4_value_fragment_in.bits.transaction_identity.request_id.poke(3.U); dut.io.r4_value_fragment_in.bits.transaction_identity.incarnation.poke(0.U)
      dut.io.r4_value_fragment_in.bits.fragment_index.poke(1.U); dut.io.r4_value_fragment_in.bits.last.poke(false.B)
      dut.io.r4_value_fragment_in.valid.poke(true.B); dut.io.r4_value_fragment_in.ready.expect(false.B)
      dut.io.r4_value_fragment_in.bits.fragment_index.poke(0.U); dut.io.r4_value_fragment_in.bits.last.poke(true.B)
      dut.io.r4_value_fragment_in.ready.expect(false.B)
    }
  }

  it("maps matching replaceable success or explicit numeric fault to one terminal and rejects duplicates") {
    simulate(new RouteAMergeBoundary(p)) { dut =>
      init(dut)
      dut.io.merge_req_in.bits.source_presence.poke(0.U); dut.io.merge_req_in.valid.poke(true.B); dut.io.merge_req_in.ready.expect(false.B); dut.io.merge_req_in.valid.poke(false.B)
      sendMergeRequest(dut, 4, 0, presence = 3)
      dut.io.r4_numeric_fault_in.bits.transaction_identity.request_id.poke(5.U); dut.io.r4_numeric_fault_in.bits.transaction_identity.incarnation.poke(0.U)
      dut.io.r4_numeric_fault_in.valid.poke(true.B); dut.io.r4_numeric_fault_in.ready.expect(false.B); dut.io.r4_numeric_fault_in.valid.poke(false.B)
      dut.io.r4_numeric_fault_in.bits.transaction_identity.request_id.poke(4.U); dut.io.r4_numeric_fault_in.valid.poke(true.B); dut.io.r4_numeric_fault_in.ready.expect(true.B); dut.clock.step(); dut.io.r4_numeric_fault_in.valid.poke(false.B)
      dut.io.merge_rsp_or_numeric_fault.valid.expect(true.B); dut.io.merge_rsp_or_numeric_fault.ready.poke(false.B); dut.clock.step()
      dut.io.merge_rsp_or_numeric_fault.bits.status.expect(p.coreMemoryFaultStatusCode.U); dut.io.merge_rsp_or_numeric_fault.bits.transaction_identity.request_id.expect(4.U)
      dut.io.merge_rsp_or_numeric_fault.ready.poke(true.B); dut.clock.step(); dut.io.r4_numeric_fault_in.valid.poke(true.B); dut.io.r4_numeric_fault_in.ready.expect(false.B); dut.io.r4_numeric_fault_in.valid.poke(false.B)

      sendMergeRequest(dut, 6, 1, presence = 7)
      dut.io.r4_result_stub_in.bits.transaction_identity.request_id.poke(6.U); dut.io.r4_result_stub_in.bits.transaction_identity.incarnation.poke(1.U)
      dut.io.r4_result_stub_in.bits.normalized_value.poke("h1234".U); dut.io.r4_result_stub_in.valid.poke(true.B)
      dut.io.r4_result_stub_in.ready.expect(true.B); dut.clock.step(); dut.io.r4_result_stub_in.valid.poke(false.B)
      dut.io.merge_rsp_or_numeric_fault.valid.expect(true.B); dut.io.merge_rsp_or_numeric_fault.bits.status.expect(p.coreMemoryOkStatusCode.U)
      dut.io.merge_rsp_or_numeric_fault.bits.normalized_value.expect("h1234".U)
      dut.clock.step()

      // Every nonempty frozen hot/pending/packed membership mask has the same
      // control treatment; this does not test or imply numeric equivalence.
      for (presence <- 1 to 7) {
        val rid = presence
        sendMergeRequest(dut, rid, 0, presence)
        dut.io.r4_numeric_fault_in.bits.transaction_identity.request_id.poke(rid.U)
        dut.io.r4_numeric_fault_in.bits.transaction_identity.incarnation.poke(0.U)
        dut.io.r4_numeric_fault_in.valid.poke(true.B); dut.io.r4_numeric_fault_in.ready.expect(true.B)
        dut.clock.step(); dut.io.r4_numeric_fault_in.valid.poke(false.B)
        dut.io.merge_rsp_or_numeric_fault.valid.expect(true.B); dut.clock.step()
      }
    }
  }
}
