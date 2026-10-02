package kvpress.routea.r2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteADeliveryContextRegistry
import kvpress.routea.interfaces.RouteADeliveryTargetKind
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.2.1 directed association tests.  These exercise only registry
  * ownership and ready/valid safety; no endpoint, controller, timing, model,
  * GPU, or PPA behavior is represented.
  */
final class RouteADeliveryContextRegistrySpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 2, candidateIdWidth = 2, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 1, p3StageGenerationWidth = 1,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def driveAllocation(
    dut: RouteADeliveryContextRegistry,
    candidateClass: Int,
    requestId: Int,
    incarnation: Int,
    targetKind: Int,
    generation: Int,
  ): Unit = {
    val bits = dut.io.allocation_in.bits
    bits.candidate_class.poke(candidateClass.U)
    bits.transaction_identity.request_id.poke(requestId.U)
    bits.transaction_identity.incarnation.poke(incarnation.U)
    bits.target_kind.poke(targetKind.U)
    bits.target_identity_generation.poke(generation.U)
  }

  private def driveRelease(
    dut: RouteADeliveryContextRegistry,
    ref: Int,
    candidateClass: Int,
    requestId: Int,
    incarnation: Int,
    targetKind: Int,
    generation: Int,
  ): Unit = {
    val bits = dut.io.release_in.bits
    bits.delivery_context_ref.poke(ref.U)
    bits.allocation.candidate_class.poke(candidateClass.U)
    bits.allocation.transaction_identity.request_id.poke(requestId.U)
    bits.allocation.transaction_identity.incarnation.poke(incarnation.U)
    bits.allocation.target_kind.poke(targetKind.U)
    bits.allocation.target_identity_generation.poke(generation.U)
  }

  private def initialize(dut: RouteADeliveryContextRegistry): Unit = {
    dut.io.mem_init_done.poke(false.B)
    dut.io.allocation_in.valid.poke(false.B)
    dut.io.allocation_ack_out.ready.poke(false.B)
    dut.io.release_in.valid.poke(false.B)
    driveAllocation(dut, p.r2PackReadClassCode, 0, 0, RouteADeliveryTargetKind.P3PendingRead, 0)
    driveRelease(dut, 0, p.r2PackReadClassCode, 0, 0, RouteADeliveryTargetKind.P3PendingRead, 0)
  }

  private def start(dut: RouteADeliveryContextRegistry): Unit = {
    dut.io.mem_init_done.poke(true.B)
    dut.clock.step()
  }

  private def allocateAndConsume(
    dut: RouteADeliveryContextRegistry,
    candidateClass: Int,
    requestId: Int,
    incarnation: Int,
    targetKind: Int,
    generation: Int,
  ): Int = {
    driveAllocation(dut, candidateClass, requestId, incarnation, targetKind, generation)
    dut.io.allocation_in.valid.poke(true.B)
    dut.io.allocation_in.ready.expect(true.B)
    dut.clock.step()
    dut.io.allocation_in.valid.poke(false.B)
    dut.io.allocation_ack_out.valid.expect(true.B)
    val ref = dut.io.allocation_ack_out.bits.delivery_context_ref.peek().litValue.toInt
    dut.io.allocation_ack_out.bits.allocation.candidate_class.expect(candidateClass.U)
    dut.io.allocation_ack_out.bits.allocation.transaction_identity.request_id.expect(requestId.U)
    dut.io.allocation_ack_out.bits.allocation.transaction_identity.incarnation.expect(incarnation.U)
    dut.io.allocation_ack_out.bits.allocation.target_kind.expect(targetKind.U)
    dut.io.allocation_ack_out.bits.allocation.target_identity_generation.expect(generation.U)
    dut.io.allocation_ack_out.ready.poke(true.B)
    dut.clock.step()
    dut.io.allocation_ack_out.ready.poke(false.B)
    ref
  }

  it("gates allocation until R1 initialization and holds an accepted association under ack backpressure") {
    simulate(new RouteADeliveryContextRegistry(p)) { dut =>
      initialize(dut)
      dut.io.allocation_in.valid.poke(true.B)
      dut.io.allocation_in.ready.expect(false.B)
      start(dut)

      driveAllocation(dut, p.r2PackReadClassCode, 1, 0, RouteADeliveryTargetKind.P3PendingRead, 2)
      dut.io.allocation_in.valid.poke(true.B); dut.io.allocation_in.ready.expect(true.B)
      dut.clock.step(); dut.io.allocation_in.valid.poke(false.B)
      dut.io.allocation_ack_out.valid.expect(true.B)
      dut.io.allocation_ack_out.bits.delivery_context_ref.expect(0.U)
      dut.io.allocation_ack_out.bits.allocation.transaction_identity.request_id.expect(1.U)
      dut.io.allocation_ack_out.ready.poke(false.B); dut.clock.step()
      dut.io.allocation_ack_out.valid.expect(true.B)
      dut.io.allocation_ack_out.bits.delivery_context_ref.expect(0.U)
      dut.io.allocation_ack_out.bits.allocation.target_identity_generation.expect(2.U)
      dut.io.allocation_ack_out.ready.poke(true.B); dut.clock.step()
    }
  }

  it("rejects a target/class mismatch and an allocation duplicate without changing the live association") {
    simulate(new RouteADeliveryContextRegistry(p)) { dut =>
      initialize(dut); start(dut)
      allocateAndConsume(dut, p.r2S2PackedClassCode, 2, 0, RouteADeliveryTargetKind.S2PackedFill, 1)

      driveAllocation(dut, p.r2S2PackedClassCode, 3, 0, RouteADeliveryTargetKind.DirectPendingRead, 1)
      dut.io.allocation_in.valid.poke(true.B); dut.io.allocation_in.ready.expect(false.B)
      driveAllocation(dut, p.r2S2PackedClassCode, 2, 0, RouteADeliveryTargetKind.S2PackedFill, 3)
      dut.io.allocation_in.ready.expect(false.B)
      dut.io.allocation_in.valid.poke(false.B)

      driveRelease(dut, 0, p.r2S2PackedClassCode, 2, 0, RouteADeliveryTargetKind.S2PackedFill, 1)
      dut.io.release_in.valid.poke(true.B); dut.io.release_in.ready.expect(true.B)
      dut.clock.step(); dut.io.release_in.valid.poke(false.B)
      driveAllocation(dut, p.r2S2PackedClassCode, 2, 1, RouteADeliveryTargetKind.S2PackedFill, 3)
      dut.io.allocation_in.valid.poke(true.B); dut.io.allocation_in.ready.expect(true.B)
    }
  }

  it("does not free a reused reference on a delayed old-incarnation release and exhausts only live refs") {
    simulate(new RouteADeliveryContextRegistry(p)) { dut =>
      initialize(dut); start(dut)
      val oldRef = allocateAndConsume(dut, p.r2PackWriteClassCode, 1, 0,
        RouteADeliveryTargetKind.PackedWriteTerminal, 0)
      driveRelease(dut, oldRef, p.r2PackWriteClassCode, 1, 0,
        RouteADeliveryTargetKind.PackedWriteTerminal, 0)
      dut.io.release_in.valid.poke(true.B); dut.io.release_in.ready.expect(true.B)
      dut.clock.step(); dut.io.release_in.valid.poke(false.B)

      val newRef = allocateAndConsume(dut, p.r2PackWriteClassCode, 1, 1,
        RouteADeliveryTargetKind.PackedWriteTerminal, 1)
      assert(newRef == oldRef)
      driveRelease(dut, oldRef, p.r2PackWriteClassCode, 1, 0,
        RouteADeliveryTargetKind.PackedWriteTerminal, 0)
      dut.io.release_in.valid.poke(true.B); dut.io.release_in.ready.expect(false.B)
      dut.io.release_in.valid.poke(false.B)

      allocateAndConsume(dut, p.r2PackReadClassCode, 2, 0, RouteADeliveryTargetKind.P3PendingRead, 0)
      allocateAndConsume(dut, p.r2S2FullClassCode, 3, 0, RouteADeliveryTargetKind.S2FullFill, 0)
      allocateAndConsume(dut, p.r2DirectPendingClassCode, 4, 0, RouteADeliveryTargetKind.DirectPendingRead, 0)
      driveAllocation(dut, p.r2DescriptorMaintenanceClassCode, 5, 0,
        RouteADeliveryTargetKind.DescriptorMaintenanceTerminal, 0)
      dut.io.allocation_in.valid.poke(true.B); dut.io.allocation_in.ready.expect(false.B)
    }
  }
}
