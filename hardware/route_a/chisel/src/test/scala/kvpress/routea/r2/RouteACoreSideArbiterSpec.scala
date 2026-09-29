package kvpress.routea.r2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteACoreSideArbiter
import kvpress.routea.interfaces.RouteAR2PredicateBits
import kvpress.routea.params.RouteASkeletonParameters
import org.scalatest.funspec.AnyFunSpec

/** RTL1.2 directed, no-model R2 protocol checks; not a controller/PPA test. */
final class RouteACoreSideArbiterSpec extends AnyFunSpec with ChiselSim {
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
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 1, p3StageGenerationWidth = 1,
    r5AllocatorEntries = 8,
    r5StreamSlots = 8,
  )
  private val commonRead = (1 << RouteAR2PredicateBits.FifoPredecessor) |
    (1 << RouteAR2PredicateBits.Ownership) | (1 << RouteAR2PredicateBits.SourceCredit) |
    (1 << RouteAR2PredicateBits.DestinationReady)

  private def driveCandidate(dut: RouteACoreSideArbiter, cls: Int, id: Int, ordinal: Int, rid: Int, predicates: Int): Unit = {
    val bits = dut.io.candidate_in.bits
    bits.candidate_class.poke(cls.U); bits.candidate_id.poke(id.U); bits.arrival_ordinal.poke(ordinal.U)
    bits.eligibility_snapshot.poke(predicates.U)
    bits.r1_request.transaction_identity.request_id.poke(rid.U); bits.r1_request.transaction_identity.incarnation.poke(0.U)
    bits.r1_request.request_kind.poke(p.coreMemoryReadRequestCode.U); bits.r1_request.destination.poke(1.U)
    bits.r1_request.address_ref.poke((16 + id).U); bits.r1_request.expected_fragment_count.poke(1.U)
    bits.r1_request.fragment_index.poke(0.U); bits.r1_request.last.poke(false.B); bits.r1_request.data.poke(0.U)
  }
  private def init(dut: RouteACoreSideArbiter): Unit = {
    dut.io.candidate_in.valid.poke(false.B); dut.io.core_mem_req.ready.poke(false.B)
    dut.io.core_mem_rsp_in.valid.poke(false.B); dut.io.source_delivery_out.ready.poke(true.B)
    driveCandidate(dut, p.r2S2FullClassCode, 0, 0, 0, commonRead)
    dut.io.core_mem_rsp_in.bits.transaction_identity.request_id.poke(0.U)
    dut.io.core_mem_rsp_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.core_mem_rsp_in.bits.fragment_index.poke(0.U); dut.io.core_mem_rsp_in.bits.last.poke(true.B)
    dut.io.core_mem_rsp_in.bits.status.poke(p.coreMemoryOkStatusCode.U); dut.io.core_mem_rsp_in.bits.data.poke(0x55.U)
  }
  private def enqueue(dut: RouteACoreSideArbiter): Unit = {
    dut.io.candidate_in.valid.poke(true.B); dut.io.candidate_in.ready.expect(true.B); dut.clock.step(); dut.io.candidate_in.valid.poke(false.B)
  }

  it("backpressures an ineligible pending candidate and holds an accepted grant while R1 is not ready") {
    simulate(new RouteACoreSideArbiter(p)) { dut =>
      init(dut)
      driveCandidate(dut, p.r2DirectPendingClassCode, 1, 0, 1, commonRead)
      dut.io.candidate_in.valid.poke(true.B); dut.io.candidate_in.ready.expect(false.B)
      driveCandidate(dut, p.r2S2FullClassCode, 2, 3, 2, commonRead)
      enqueue(dut)
      dut.io.core_mem_req.valid.expect(true.B); dut.io.core_mem_req.bits.transaction_identity.request_id.expect(2.U)
      dut.io.core_mem_req.ready.poke(false.B); dut.clock.step()
      dut.io.core_mem_req.valid.expect(true.B); dut.io.core_mem_req.bits.transaction_identity.request_id.expect(2.U)
      dut.io.candidate_in.ready.expect(false.B)
    }
  }

  it("advances the read cursor only on R1 acceptance and routes the matched terminal response") {
    simulate(new RouteACoreSideArbiter(p)) { dut =>
      init(dut)
      driveCandidate(dut, p.r2S2FullClassCode, 3, 5, 3, commonRead)
      enqueue(dut)
      dut.io.core_mem_req.ready.poke(true.B); dut.io.core_mem_req.valid.expect(true.B); dut.clock.step()
      driveCandidate(dut, p.r2DirectPendingClassCode, 4, 1, 4, commonRead | (1 << RouteAR2PredicateBits.PendingAuthoritative))
      enqueue(dut)
      dut.io.core_mem_req.valid.expect(true.B); dut.io.core_mem_req.bits.transaction_identity.request_id.expect(4.U)
      dut.clock.step()
      dut.io.core_mem_rsp_in.bits.transaction_identity.request_id.poke(4.U)
      dut.io.core_mem_rsp_in.valid.poke(true.B); dut.io.source_delivery_out.valid.expect(true.B)
      dut.io.source_delivery_out.bits.candidate_id.expect(4.U); dut.io.source_delivery_out.bits.destination.expect(1.U)
      dut.clock.step(); dut.io.core_mem_rsp_in.valid.poke(false.B)
    }
  }

  it("keeps the descriptor write outside read rotation and releases its transport reservation only at terminal") {
    simulate(new RouteACoreSideArbiter(p)) { dut =>
      init(dut)
      val writeReady = (1 << RouteAR2PredicateBits.FifoPredecessor) |
        (1 << RouteAR2PredicateBits.Ownership) | (1 << RouteAR2PredicateBits.SourceCredit)
      driveCandidate(dut, p.r2DescriptorMaintenanceClassCode, 6, 0, 6, writeReady)
      dut.io.candidate_in.bits.r1_request.request_kind.poke(p.coreMemoryWriteRequestCode.U)
      dut.io.candidate_in.bits.r1_request.expected_fragment_count.poke(1.U)
      enqueue(dut)
      dut.io.core_mem_req.ready.poke(true.B); dut.io.core_mem_req.valid.expect(true.B)
      dut.io.core_mem_req.bits.request_kind.expect(p.coreMemoryWriteRequestCode.U); dut.clock.step()
      dut.io.core_mem_rsp_in.bits.transaction_identity.request_id.poke(6.U)
      dut.io.core_mem_rsp_in.valid.poke(true.B); dut.io.source_delivery_out.valid.expect(true.B)
      dut.io.source_delivery_out.bits.candidate_class.expect(p.r2DescriptorMaintenanceClassCode.U)
      dut.clock.step(); dut.io.core_mem_rsp_in.valid.poke(false.B)
      // Terminal reservation release permits a different incarnation to be presented.
      driveCandidate(dut, p.r2S2FullClassCode, 7, 1, 6, commonRead)
      dut.io.candidate_in.bits.r1_request.transaction_identity.incarnation.poke(1.U)
      dut.io.candidate_in.ready.expect(true.B)
    }
  }
}
