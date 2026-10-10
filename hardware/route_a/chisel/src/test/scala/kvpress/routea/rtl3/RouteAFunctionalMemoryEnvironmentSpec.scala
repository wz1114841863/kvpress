package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteACoreMemIfV1
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec
import org.scalatest.matchers.should.Matchers

/**
  * RTL3.1 directed checks for the testbench-only functional memory environment.
  * They exercise accepted R1 transactions only; they are not a physical-memory,
  * throughput, latency, model/GPU, or PPA test.
  */
final class RouteAFunctionalMemoryEnvironmentSpec extends AnyFunSpec with ChiselSim with Matchers {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 1, candidateIdWidth = 1, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 1, p3StageGenerationWidth = 1,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def driveCoreRequest(
    dut: RouteACoreMemIfV1,
    requestId: Int,
    incarnation: Int,
    kind: Int,
    address: Int,
    expectedFragments: Int = 0,
    fragmentIndex: Int = 0,
    last: Boolean = false,
    data: BigInt = 0,
  ): Unit = {
    val request = dut.io.core_mem_req_in.bits
    request.transaction_identity.request_id.poke(requestId.U)
    request.transaction_identity.incarnation.poke(incarnation.U)
    request.request_kind.poke(kind.U)
    request.destination.poke(0.U)
    request.address_ref.poke(address.U)
    request.expected_fragment_count.poke(expectedFragments.U)
    request.fragment_index.poke(fragmentIndex.U)
    request.last.poke(last.B)
    request.data.poke(data.U)
  }

  private def cycle(dut: RouteACoreMemIfV1, environment: RouteAFunctionalMemoryEnvironment): Unit = {
    environment.drive(dut)
    environment.observeAccepted(dut)
    dut.clock.step()
  }

  private def initialize(dut: RouteACoreMemIfV1, environment: RouteAFunctionalMemoryEnvironment): Unit = {
    dut.io.core_mem_req_in.valid.poke(false.B)
    dut.io.core_mem_rsp.ready.poke(true.B)
    dut.io.r1_drain_permitted.poke(false.B)
    dut.io.component_status_out.ready.poke(true.B)
    driveCoreRequest(dut, 0, 0, p.coreMemoryReadRequestCode, address = 0)
    cycle(dut, environment)
    dut.io.r1_init_complete.expect(true.B)
  }

  private def acceptCoreRequest(dut: RouteACoreMemIfV1, environment: RouteAFunctionalMemoryEnvironment): Unit = {
    dut.io.core_mem_req_in.valid.poke(true.B)
    environment.drive(dut)
    dut.io.core_mem_req_in.ready.expect(true.B)
    dut.io.external_core_mem_if_v1.request.valid.expect(true.B)
    environment.observeAccepted(dut)
    dut.clock.step()
    dut.io.core_mem_req_in.valid.poke(false.B)
  }

  it("keeps a payload object and descriptor object distinct when their opaque address_ref is equal") {
    val store = new RouteAFunctionalMemoryStore
    val payload = Vector(BigInt(0x100), BigInt(0x101), BigInt(0x102), BigInt(0x103),
      BigInt(0x104), BigInt(0x105), BigInt(0x106), BigInt(0x107))
    store.preload(addressRef = 0, generation = Some(BigInt(0)), payloadFragments = payload, sidecarRecords = Vector(BigInt(0x900)))
    // A one-fragment descriptor update may use the same still-opaque R1
    // address_ref.  Existing R1 transaction granularity keeps it a distinct
    // logical object in this testbench-only functional model.
    store.commitWrite(addressRef = 0, expectedFragments = 1, payloadFragments = Vector(BigInt(0xdead)))

    store.objectAt(0, payload.size).get shouldBe FunctionalPackedObject(Some(BigInt(0)), payload, Vector(BigInt(0x900)))
    store.objectAt(0, 1).get.payloadFragments shouldBe Vector(BigInt(0xdead))
    store.objectAt(0) shouldBe None
  }

  it("materializes a successful write only at its accepted terminal and returns the stored payload through an accepted read") {
    simulate(new RouteACoreMemIfV1(p)) { dut =>
      val environment = new RouteAFunctionalMemoryEnvironment(p)
      environment.preload(addressRef = 9, generation = Some(7), payloadFragments = Vector(0x11, 0x22), sidecarRecords = Vector(0x101, 0x102))
      initialize(dut, environment)

      // Legal request backpressure changes only when the R1 request is accepted.
      environment.setRequestAcceptance(false)
      driveCoreRequest(dut, 1, 1, p.coreMemoryWriteRequestCode, address = 9, expectedFragments = 2)
      dut.io.core_mem_req_in.valid.poke(true.B)
      environment.drive(dut)
      dut.io.core_mem_req_in.ready.expect(false.B)
      // valid may remain asserted while the environment applies legal
      // backpressure; only a ready/valid fire is an accepted transaction.
      dut.io.external_core_mem_if_v1.request.valid.expect(true.B)
      cycle(dut, environment)
      environment.setRequestAcceptance(true)
      acceptCoreRequest(dut, environment)

      driveCoreRequest(dut, 1, 1, p.coreMemoryWriteDataCode, address = 9, fragmentIndex = 0, data = 0xa1)
      acceptCoreRequest(dut, environment)
      driveCoreRequest(dut, 1, 1, p.coreMemoryWriteDataCode, address = 9, fragmentIndex = 1, last = true, data = 0xa2)
      acceptCoreRequest(dut, environment)
      environment.objectAt(9).get.payloadFragments shouldBe Vector(0x11, 0x22)

      // Response backpressure leaves the terminal response and uncommitted data stable.
      dut.io.core_mem_rsp.ready.poke(false.B)
      environment.drive(dut)
      dut.io.core_mem_rsp.valid.expect(true.B)
      dut.io.core_mem_rsp.bits.status.expect(p.coreMemoryOkStatusCode.U)
      environment.observeAccepted(dut)
      dut.clock.step()
      environment.drive(dut)
      dut.io.core_mem_rsp.valid.expect(true.B)
      environment.objectAt(9).get.payloadFragments shouldBe Vector(0x11, 0x22)
      dut.io.core_mem_rsp.ready.poke(true.B)
      environment.observeAccepted(dut)
      dut.clock.step()
      environment.objectAt(9).get.payloadFragments shouldBe Vector(0xa1, 0xa2)
      environment.objectAt(9).get.generation shouldBe Some(7)
      environment.objectAt(9).get.sidecarRecords shouldBe Vector(0x101, 0x102)

      driveCoreRequest(dut, 2, 1, p.coreMemoryReadRequestCode, address = 9, expectedFragments = 2)
      acceptCoreRequest(dut, environment)
      environment.drive(dut)
      dut.io.core_mem_rsp.valid.expect(true.B); dut.io.core_mem_rsp.bits.data.expect(0xa1.U)
      environment.observeAccepted(dut); dut.clock.step()
      environment.drive(dut)
      dut.io.core_mem_rsp.valid.expect(true.B); dut.io.core_mem_rsp.bits.data.expect(0xa2.U); dut.io.core_mem_rsp.bits.last.expect(true.B)
      environment.observeAccepted(dut); dut.clock.step()
    }
  }

  it("fails closed for a configured read or write fault without changing the functional object") {
    simulate(new RouteACoreMemIfV1(p)) { dut =>
      val environment = new RouteAFunctionalMemoryEnvironment(p)
      environment.preload(addressRef = 3, generation = Some(2), payloadFragments = Vector(0x31), sidecarRecords = Vector(0x301))
      initialize(dut, environment)

      environment.injectNextReadFault()
      driveCoreRequest(dut, 0, 1, p.coreMemoryReadRequestCode, address = 3, expectedFragments = 1)
      acceptCoreRequest(dut, environment)
      environment.drive(dut)
      dut.io.core_mem_rsp.valid.expect(true.B); dut.io.core_mem_rsp.bits.status.expect(p.coreMemoryFaultStatusCode.U); dut.io.core_mem_rsp.bits.data.expect(0.U)
      environment.observeAccepted(dut); dut.clock.step()
      environment.objectAt(3).get.payloadFragments shouldBe Vector(0x31)

      environment.injectNextWriteFault()
      driveCoreRequest(dut, 1, 2, p.coreMemoryWriteRequestCode, address = 3, expectedFragments = 1)
      acceptCoreRequest(dut, environment)
      driveCoreRequest(dut, 1, 2, p.coreMemoryWriteDataCode, address = 3, fragmentIndex = 0, last = true, data = 0xdead)
      acceptCoreRequest(dut, environment)
      environment.drive(dut)
      dut.io.core_mem_rsp.valid.expect(true.B); dut.io.core_mem_rsp.bits.status.expect(p.coreMemoryFaultStatusCode.U)
      environment.observeAccepted(dut); dut.clock.step()
      environment.objectAt(3).get shouldBe FunctionalPackedObject(Some(2), Vector(0x31), Vector(0x301))
    }
  }
}
