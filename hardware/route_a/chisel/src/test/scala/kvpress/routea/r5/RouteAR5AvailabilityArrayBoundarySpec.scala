package kvpress.routea.r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAR5AvailabilityArrayBoundary
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Parent-adapter port contract for the R5 availability/generation interior.
  * This does not model a macro: it checks only keyed read holding and exact
  * allocation/reclaim acknowledgement facts consumed by RouteAPageManager.
  */
final class RouteAR5AvailabilityArrayBoundarySpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8, coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1, p3StageGenerationWidth = 1, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  it("holds keyed lookup, then returns exact allocation and reclaim generations") {
    simulate(new RouteAR5AvailabilityArrayBoundary(p)) { dut =>
      dut.io.availability_lookup_req.valid.poke(false.B)
      dut.io.availability_lookup_rsp.ready.poke(false.B)
      dut.io.allocation_update.valid.poke(false.B)
      dut.io.reclaim_generation_update.valid.poke(false.B)
      dut.clock.step()

      dut.io.availability_lookup_req.bits.poke(0.U)
      dut.io.availability_lookup_req.valid.poke(true.B)
      dut.io.availability_lookup_req.ready.expect(true.B)
      dut.clock.step(); dut.io.availability_lookup_req.valid.poke(false.B)
      dut.io.availability_lookup_rsp.valid.expect(true.B)
      dut.io.availability_lookup_rsp.bits.page_id.expect(0.U)
      dut.io.availability_lookup_rsp.bits.allocated.expect(false.B)
      dut.io.availability_lookup_rsp.bits.generation.expect(0.U)
      dut.clock.step()
      dut.io.availability_lookup_rsp.valid.expect(true.B)
      dut.io.availability_lookup_rsp.ready.poke(true.B); dut.clock.step()

      dut.io.allocation_update.bits.poke(0.U); dut.io.allocation_update.valid.poke(true.B)
      dut.clock.step(); dut.io.allocation_update.valid.poke(false.B)
      dut.io.allocation_update_ack.valid.expect(true.B)
      dut.io.allocation_update_ack.bits.page_id.expect(0.U)
      dut.io.allocation_update_ack.bits.generation.expect(0.U)
      dut.clock.step()

      dut.io.availability_lookup_req.bits.poke(0.U); dut.io.availability_lookup_req.valid.poke(true.B)
      dut.io.availability_lookup_req.ready.expect(true.B)
      dut.clock.step(); dut.io.availability_lookup_req.valid.poke(false.B)
      dut.io.availability_lookup_rsp.valid.expect(true.B)
      dut.io.availability_lookup_rsp.bits.allocated.expect(true.B)
      dut.io.availability_lookup_rsp.bits.generation.expect(0.U)
      dut.io.availability_lookup_rsp.ready.poke(true.B); dut.clock.step()

      dut.io.reclaim_generation_update.bits.poke(0.U); dut.io.reclaim_generation_update.valid.poke(true.B)
      dut.clock.step(); dut.io.reclaim_generation_update.valid.poke(false.B)
      dut.io.reclaim_generation_update_ack.valid.expect(true.B)
      dut.io.reclaim_generation_update_ack.bits.descriptor_line.expect(0.U)
      dut.io.reclaim_generation_update_ack.bits.allocated_mask.expect(1.U)
      dut.io.reclaim_generation_update_ack.bits.old_generations(0).expect(0.U)
      dut.clock.step()

      dut.io.availability_lookup_req.bits.poke(0.U); dut.io.availability_lookup_req.valid.poke(true.B)
      dut.io.availability_lookup_req.ready.expect(true.B)
      dut.clock.step(); dut.io.availability_lookup_req.valid.poke(false.B)
      dut.io.availability_lookup_rsp.valid.expect(true.B)
      dut.io.availability_lookup_rsp.bits.allocated.expect(false.B)
      dut.io.availability_lookup_rsp.bits.generation.expect(1.U)
    }
  }
}
