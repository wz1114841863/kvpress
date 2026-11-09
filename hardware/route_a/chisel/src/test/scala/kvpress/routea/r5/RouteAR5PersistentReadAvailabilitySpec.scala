package kvpress.routea.r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAR5AvailabilityArrayBoundary
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** Checks the real v2 child, including clear priority and held acknowledgement. */
final class RouteAR5PersistentReadAvailabilitySpec extends AnyFunSpec with ChiselSim {
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

  it("retains exact read qualification and prioritizes non-backpressured allocation/reclaim clears") {
    simulate(new RouteAR5AvailabilityArrayBoundary(p, persistentReadEnabled = true)) { dut =>
      val port = dut.persistentRead.get
      dut.io.availability_lookup_req.valid.poke(false.B)
      dut.io.availability_lookup_req.bits.poke(0.U)
      dut.io.availability_lookup_rsp.ready.poke(false.B)
      dut.io.allocation_update.valid.poke(false.B)
      dut.io.allocation_update.bits.poke(0.U)
      dut.io.reclaim_generation_update.valid.poke(false.B)
      dut.io.reclaim_generation_update.bits.poke(0.U)
      port.mark_update.valid.poke(false.B)
      port.mark_update.bits.page_id.poke(0.U)
      port.mark_update.bits.generation.poke(0.U)
      port.mark_ack.ready.poke(false.B)
      dut.clock.step()

      def lookup(allocated: Boolean, generation: Int, readReady: Boolean): Unit = {
        dut.io.availability_lookup_req.ready.expect(true.B)
        dut.io.availability_lookup_req.valid.poke(true.B)
        dut.clock.step()
        dut.io.availability_lookup_req.valid.poke(false.B)
        for (_ <- 0 until 3) {
          dut.io.availability_lookup_rsp.valid.expect(true.B)
          dut.io.availability_lookup_rsp.bits.page_id.expect(0.U)
          dut.io.availability_lookup_rsp.bits.allocated.expect(allocated.B)
          dut.io.availability_lookup_rsp.bits.generation.expect(generation.U)
          port.lookup_read_ready.expect(readReady.B)
          dut.clock.step()
        }
        dut.io.availability_lookup_rsp.ready.poke(true.B)
        dut.clock.step()
        dut.io.availability_lookup_rsp.ready.poke(false.B)
      }
      def checkMarkAck(generation: Int, accepted: Boolean): Unit = {
        port.mark_ack.valid.expect(true.B)
        port.mark_ack.bits.page_ref.page_id.expect(0.U)
        port.mark_ack.bits.page_ref.generation.expect(generation.U)
        port.mark_ack.bits.accepted.expect(accepted.B)
      }
      def consumeMarkAck(): Unit = {
        port.mark_ack.ready.poke(true.B)
        dut.clock.step()
        port.mark_ack.ready.poke(false.B)
      }

      lookup(allocated = false, generation = 0, readReady = false)
      dut.io.allocation_update.valid.poke(true.B)
      dut.clock.step()
      dut.io.allocation_update.valid.poke(false.B)
      dut.io.allocation_update_ack.valid.expect(true.B)
      dut.io.allocation_update_ack.bits.generation.expect(0.U)
      lookup(allocated = true, generation = 0, readReady = false)

      port.mark_update.valid.poke(true.B)
      port.mark_update.ready.expect(true.B)
      dut.clock.step()
      port.mark_update.valid.poke(false.B)
      for (_ <- 0 until 3) { checkMarkAck(0, accepted = true); dut.clock.step() }
      lookup(allocated = true, generation = 0, readReady = true)

      // A held successful mark ACK cannot delay the parent's Valid reclaim.
      // A new offered mark is not accepted in the same clock as that clear.
      port.mark_update.valid.poke(true.B)
      dut.io.reclaim_generation_update.valid.poke(true.B)
      port.mark_update.ready.expect(false.B)
      dut.clock.step()
      dut.io.reclaim_generation_update.valid.poke(false.B)
      dut.io.reclaim_generation_update_ack.valid.expect(true.B)
      dut.io.reclaim_generation_update_ack.bits.allocated_mask.expect(1.U)
      dut.io.reclaim_generation_update_ack.bits.old_generations(0).expect(0.U)
      checkMarkAck(0, accepted = true)
      port.mark_update.ready.expect(false.B)
      lookup(allocated = false, generation = 1, readReady = false)
      consumeMarkAck()

      // The same held request is now processed and explicitly rejected as
      // stale. No assertion, silent generation rewrite, or resurrected page.
      port.mark_update.ready.expect(true.B)
      dut.clock.step()
      port.mark_update.valid.poke(false.B)
      checkMarkAck(0, accepted = false)
      consumeMarkAck()

      // Allocation also takes priority over an offered mark without ready.
      port.mark_update.bits.generation.poke(1.U)
      port.mark_update.valid.poke(true.B)
      dut.io.allocation_update.valid.poke(true.B)
      port.mark_update.ready.expect(false.B)
      dut.clock.step()
      dut.io.allocation_update.valid.poke(false.B)
      dut.io.allocation_update_ack.valid.expect(true.B)
      dut.io.allocation_update_ack.bits.generation.expect(1.U)
      port.mark_ack.valid.expect(false.B)
      port.mark_update.ready.expect(true.B)
      dut.clock.step()
      port.mark_update.valid.poke(false.B)
      checkMarkAck(1, accepted = true)
      consumeMarkAck()
      lookup(allocated = true, generation = 1, readReady = true)
      println("KVZAP_PERSISTENT_AVAILABILITY_CLEAR_HOLD_STALE_PASS")
    }
  }
}
