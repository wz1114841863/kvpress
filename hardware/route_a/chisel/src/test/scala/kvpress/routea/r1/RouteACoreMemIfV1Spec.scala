package kvpress.routea.r1

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteACoreMemIfV1
import kvpress.routea.params.RouteASkeletonParameters
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL1.1 directed protocol checks for R1 only. They are intentionally
  * transaction-level: no memory-controller latency, cycle target, bandwidth,
  * PPA, model, GPU, or full Route-A datapath is represented here.
  */
final class RouteACoreMemIfV1Spec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3,
    componentStatusNameWidth = 4,
    hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1,
    pendingValidityWidth = 1,
    candidateClassWidth = 3,
    candidateOrdinalWidth = 1,
    candidateIdWidth = 1,
    candidatePredicateWidth = 10,
    r2S2FullClassCode = 0,
    r2S2PackedClassCode = 1,
    r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3,
    r2PackWriteClassCode = 4,
    r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1,
    coreMemoryRequestKindWidth = 3,
    coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3,
    coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0,
    coreMemoryWriteRequestCode = 1,
    coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0,
    coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1,
    p3StageGenerationWidth = 1,
    r5AllocatorEntries = 8,
    r5StreamSlots = 8,
    sourceGenerationWidth = 2,
  )

  private def driveRequest(
    dut: RouteACoreMemIfV1,
    requestId: Int,
    incarnation: Int,
    kind: Int,
    expectedFragments: Int = 0,
    fragmentIndex: Int = 0,
    last: Boolean = false,
    data: BigInt = 0,
  ): Unit = {
    dut.io.core_mem_req_in.bits.transaction_identity.request_id.poke(requestId.U)
    dut.io.core_mem_req_in.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.core_mem_req_in.bits.request_kind.poke(kind.U)
    dut.io.core_mem_req_in.bits.destination.poke(0.U)
    dut.io.core_mem_req_in.bits.address_ref.poke(0.U)
    dut.io.core_mem_req_in.bits.expected_fragment_count.poke(expectedFragments.U)
    dut.io.core_mem_req_in.bits.fragment_index.poke(fragmentIndex.U)
    dut.io.core_mem_req_in.bits.last.poke(last.B)
    dut.io.core_mem_req_in.bits.data.poke(data.U)
  }

  private def driveResponse(
    dut: RouteACoreMemIfV1,
    requestId: Int,
    incarnation: Int,
    fragmentIndex: Int,
    last: Boolean,
    status: Int,
    data: BigInt = 0,
  ): Unit = {
    dut.io.external_core_mem_if_v1.response.bits.transaction_identity.request_id.poke(requestId.U)
    dut.io.external_core_mem_if_v1.response.bits.transaction_identity.incarnation.poke(incarnation.U)
    dut.io.external_core_mem_if_v1.response.bits.fragment_index.poke(fragmentIndex.U)
    dut.io.external_core_mem_if_v1.response.bits.last.poke(last.B)
    dut.io.external_core_mem_if_v1.response.bits.status.poke(status.U)
    dut.io.external_core_mem_if_v1.response.bits.data.poke(data.U)
  }

  private def initialize(dut: RouteACoreMemIfV1): Unit = {
    dut.io.mem_init_done.poke(false.B)
    dut.io.core_mem_req_in.valid.poke(false.B)
    dut.io.core_mem_rsp.ready.poke(false.B)
    dut.io.external_core_mem_if_v1.request.ready.poke(true.B)
    dut.io.external_core_mem_if_v1.response.valid.poke(false.B)
    driveRequest(dut, requestId = 0, incarnation = 0, kind = p.coreMemoryReadRequestCode)
    driveResponse(dut, requestId = 0, incarnation = 0, fragmentIndex = 0, last = false, status = p.coreMemoryOkStatusCode)
  }

  private def releaseInitialization(dut: RouteACoreMemIfV1): Unit = {
    dut.io.mem_init_done.poke(true.B)
    dut.clock.step()
    dut.io.mem_init_done.poke(false.B)
  }

  private def acceptRequest(dut: RouteACoreMemIfV1): Unit = {
    dut.io.core_mem_req_in.valid.poke(true.B)
    dut.io.core_mem_req_in.ready.expect(true.B)
    dut.io.external_core_mem_if_v1.request.valid.expect(true.B)
    dut.clock.step()
    dut.io.core_mem_req_in.valid.poke(false.B)
  }

  it("gates traffic until init, preserves a stalled read fragment, and drops a terminal stale response") {
    simulate(new RouteACoreMemIfV1(p)) { dut =>
      initialize(dut)
      driveRequest(dut, requestId = 0, incarnation = 1, kind = p.coreMemoryReadRequestCode, expectedFragments = 2)
      dut.io.core_mem_req_in.valid.poke(true.B)
      dut.io.core_mem_req_in.ready.expect(false.B)
      dut.io.external_core_mem_if_v1.request.valid.expect(false.B)

      releaseInitialization(dut)
      acceptRequest(dut)

      driveResponse(dut, requestId = 0, incarnation = 1, fragmentIndex = 0, last = false, status = p.coreMemoryOkStatusCode, data = 0x11)
      dut.io.external_core_mem_if_v1.response.valid.poke(true.B)
      dut.io.core_mem_rsp.valid.expect(true.B)
      dut.io.external_core_mem_if_v1.response.ready.expect(false.B)
      dut.io.core_mem_rsp.ready.poke(true.B)
      dut.io.core_mem_rsp.bits.data.expect(0x11.U)
      dut.clock.step()

      driveResponse(dut, requestId = 0, incarnation = 1, fragmentIndex = 1, last = true, status = p.coreMemoryOkStatusCode, data = 0x22)
      dut.io.core_mem_rsp.valid.expect(true.B)
      dut.io.core_mem_rsp.bits.data.expect(0x22.U)
      dut.clock.step()

      // The table entry was released by the terminal fragment. A delayed copy
      // of the same response is consumed at the external boundary only.
      dut.io.core_mem_rsp.valid.expect(false.B)
      dut.io.external_core_mem_if_v1.response.ready.expect(true.B)
      dut.io.external_core_mem_if_v1.response.valid.poke(false.B)

      // The same identity is retired for this adapter epoch, while the next
      // incarnation is eligible after its predecessor's terminal outcome.
      driveRequest(dut, requestId = 0, incarnation = 1, kind = p.coreMemoryReadRequestCode, expectedFragments = 1)
      dut.io.core_mem_req_in.valid.poke(true.B)
      dut.io.core_mem_req_in.ready.expect(false.B)
      driveRequest(dut, requestId = 0, incarnation = 2, kind = p.coreMemoryReadRequestCode, expectedFragments = 1)
      acceptRequest(dut)
    }
  }

  it("enforces the four-read bound and accepts only ordered write fragments before commit") {
    simulate(new RouteACoreMemIfV1(p)) { dut =>
      initialize(dut)
      releaseInitialization(dut)

      (0 until 4).foreach { requestId =>
        driveRequest(dut, requestId, incarnation = 0, kind = p.coreMemoryReadRequestCode, expectedFragments = 1)
        acceptRequest(dut)
      }
      driveRequest(dut, requestId = 4, incarnation = 0, kind = p.coreMemoryReadRequestCode, expectedFragments = 1)
      dut.io.core_mem_req_in.valid.poke(true.B)
      dut.io.core_mem_req_in.ready.expect(false.B)
      dut.io.core_mem_req_in.valid.poke(false.B)

      driveRequest(dut, requestId = 5, incarnation = 2, kind = p.coreMemoryWriteRequestCode, expectedFragments = 2)
      acceptRequest(dut)

      driveRequest(dut, requestId = 5, incarnation = 2, kind = p.coreMemoryWriteDataCode, fragmentIndex = 1, last = false, data = 0xaa)
      dut.io.core_mem_req_in.valid.poke(true.B)
      dut.io.core_mem_req_in.ready.expect(false.B)

      driveRequest(dut, requestId = 5, incarnation = 2, kind = p.coreMemoryWriteDataCode, fragmentIndex = 0, last = false, data = 0xaa)
      acceptRequest(dut)
      driveRequest(dut, requestId = 5, incarnation = 2, kind = p.coreMemoryWriteDataCode, fragmentIndex = 1, last = true, data = 0xbb)
      acceptRequest(dut)

      driveResponse(dut, requestId = 5, incarnation = 2, fragmentIndex = 0, last = true, status = p.coreMemoryOkStatusCode)
      dut.io.external_core_mem_if_v1.response.valid.poke(true.B)
      dut.io.core_mem_rsp.ready.poke(true.B)
      dut.io.core_mem_rsp.valid.expect(true.B)
      dut.io.core_mem_rsp.bits.status.expect(p.coreMemoryOkStatusCode.U)
      dut.clock.step()
      dut.io.core_mem_rsp.valid.expect(false.B)
    }
  }

  it("fails closed on an early write commit and suppresses a pre-init reset-stale response") {
    simulate(new RouteACoreMemIfV1(p)) { dut =>
      initialize(dut)
      releaseInitialization(dut)
      driveRequest(dut, requestId = 1, incarnation = 3, kind = p.coreMemoryWriteRequestCode, expectedFragments = 1)
      acceptRequest(dut)

      // A commit before write-data completion has no durable payload effect and
      // is surfaced exactly once as a terminal fault.
      driveResponse(dut, requestId = 1, incarnation = 3, fragmentIndex = 0, last = true, status = p.coreMemoryOkStatusCode, data = 0xdead)
      dut.io.external_core_mem_if_v1.response.valid.poke(true.B)
      dut.io.core_mem_rsp.ready.poke(true.B)
      dut.io.core_mem_rsp.valid.expect(true.B)
      dut.io.core_mem_rsp.bits.last.expect(true.B)
      dut.io.core_mem_rsp.bits.status.expect(p.coreMemoryFaultStatusCode.U)
      dut.io.core_mem_rsp.bits.data.expect(0.U)
      dut.clock.step()
      dut.io.external_core_mem_if_v1.response.valid.poke(false.B)

      dut.reset.poke(true.B)
      dut.clock.step()
      dut.reset.poke(false.B)
      dut.io.mem_init_done.poke(false.B)
      driveResponse(dut, requestId = 1, incarnation = 3, fragmentIndex = 0, last = true, status = p.coreMemoryOkStatusCode)
      dut.io.external_core_mem_if_v1.response.valid.poke(true.B)
      dut.io.core_mem_rsp.valid.expect(false.B)
      dut.io.external_core_mem_if_v1.response.ready.expect(true.B)
    }
  }
}
