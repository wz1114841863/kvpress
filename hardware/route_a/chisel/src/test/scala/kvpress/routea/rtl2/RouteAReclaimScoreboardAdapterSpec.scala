package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.Decoupled
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** Testbench event payload for the R5 durable-invalidation observation. */
final class DescriptorInvalidateScoreboardEvent(p: RouteASkeletonParameters) extends Bundle {
  val page_ref = new PageRef
  val descriptor_operation = UInt(2.W)
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
}

/** Testbench event payload for one R5 allocator release observation. */
final class PageFreeScoreboardEvent extends Bundle { val page_ref = new PageRef }

/** Testbench event payload for one R6 outward retirement acknowledgement. */
final class RetireAckScoreboardEvent extends Bundle { val acknowledgement = new SessionRetireAck }

/**
  * Verification-only atomic observer. It neither produces R5/R6 facts nor
  * reads owner-local state: every event is copied from a named accepted
  * carrier. A blocked scoreboard consumer blocks the observed carrier, never
  * creates a partial event acceptance.
  */
final class RouteAReclaimScoreboardAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "testbench_route_a_reclaim_scoreboard_adapter"
  val io = IO(new Bundle {
    val allocator_release_in = Flipped(RouteAChannels.allocator_release)
    val allocator_release_out = RouteAChannels.allocator_release
    val descriptor_invalidate_event_out = Decoupled(new DescriptorInvalidateScoreboardEvent(p))
    val page_free_event_out = Decoupled(new PageFreeScoreboardEvent)
    val retire_ack_in = Flipped(RouteAChannels.session_retire_ack)
    val retire_ack_out = RouteAChannels.session_retire_ack
    val retire_ack_event_out = Decoupled(new RetireAckScoreboardEvent)
  })

  val releaseReady = io.allocator_release_out.ready && io.descriptor_invalidate_event_out.ready && io.page_free_event_out.ready
  val releaseOffer = io.allocator_release_in.valid && releaseReady
  io.allocator_release_in.ready := releaseReady
  io.allocator_release_out.valid := releaseOffer
  io.allocator_release_out.bits := io.allocator_release_in.bits
  io.descriptor_invalidate_event_out.valid := releaseOffer
  io.descriptor_invalidate_event_out.bits.page_ref := io.allocator_release_in.bits.page_ref
  io.descriptor_invalidate_event_out.bits.descriptor_operation := RouteADescriptorOperationKind.Invalidate.U
  io.descriptor_invalidate_event_out.bits.delivery_context_ref := RouteARTL2WriteDeliveryContext.R5Reclaim.U
  io.page_free_event_out.valid := releaseOffer
  io.page_free_event_out.bits.page_ref := io.allocator_release_in.bits.page_ref
  assert(io.allocator_release_in.fire === io.allocator_release_out.fire)
  assert(io.allocator_release_out.fire === io.descriptor_invalidate_event_out.fire)
  assert(io.allocator_release_out.fire === io.page_free_event_out.fire)

  val ackReady = io.retire_ack_out.ready && io.retire_ack_event_out.ready
  val ackOffer = io.retire_ack_in.valid && ackReady
  io.retire_ack_in.ready := ackReady
  io.retire_ack_out.valid := ackOffer
  io.retire_ack_out.bits := io.retire_ack_in.bits
  io.retire_ack_event_out.valid := ackOffer
  io.retire_ack_event_out.bits.acknowledgement := io.retire_ack_in.bits
  assert(io.retire_ack_in.fire === io.retire_ack_out.fire)
  assert(io.retire_ack_out.fire === io.retire_ack_event_out.fire)
}

/** Carrier-level closure only; no R5 allocator or R6 lifecycle behavior here. */
final class RouteAReclaimScoreboardAdapterSpec extends AnyFunSpec with ChiselSim {
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
  private def init(dut: RouteAReclaimScoreboardAdapter): Unit = {
    dut.io.allocator_release_in.valid.poke(false.B); dut.io.retire_ack_in.valid.poke(false.B)
    dut.io.allocator_release_out.ready.poke(false.B); dut.io.descriptor_invalidate_event_out.ready.poke(false.B); dut.io.page_free_event_out.ready.poke(false.B)
    dut.io.retire_ack_out.ready.poke(false.B); dut.io.retire_ack_event_out.ready.poke(false.B)
    dut.io.allocator_release_in.bits.page_ref.page_id.poke(0.U); dut.io.allocator_release_in.bits.page_ref.generation.poke(0.U)
    dut.io.retire_ack_in.bits.session_id.poke(false.B); dut.io.retire_ack_in.bits.transaction_identity.request_id.poke(0.U); dut.io.retire_ack_in.bits.transaction_identity.incarnation.poke(0.U)
  }
  it("binds one R5 old-generation release to invalidate and page-free only on one atomic acceptance") {
    simulate(new RouteAReclaimScoreboardAdapter(p)) { dut =>
      init(dut); dut.io.allocator_release_in.bits.page_ref.page_id.poke(5.U); dut.io.allocator_release_in.bits.page_ref.generation.poke(7.U); dut.io.allocator_release_in.valid.poke(true.B)
      dut.io.allocator_release_in.ready.expect(false.B)
      dut.io.allocator_release_out.ready.poke(true.B); dut.io.descriptor_invalidate_event_out.ready.poke(true.B); dut.io.page_free_event_out.ready.poke(true.B)
      dut.io.allocator_release_in.ready.expect(true.B); dut.io.descriptor_invalidate_event_out.bits.page_ref.page_id.expect(5.U); dut.io.descriptor_invalidate_event_out.bits.page_ref.generation.expect(7.U)
      dut.io.descriptor_invalidate_event_out.bits.descriptor_operation.expect(RouteADescriptorOperationKind.Invalidate.U); dut.io.descriptor_invalidate_event_out.bits.delivery_context_ref.expect(RouteARTL2WriteDeliveryContext.R5Reclaim.U)
      dut.io.page_free_event_out.bits.page_ref.page_id.expect(5.U); dut.clock.step(); dut.io.allocator_release_in.valid.poke(false.B)
      dut.io.allocator_release_out.valid.expect(false.B); dut.io.descriptor_invalidate_event_out.valid.expect(false.B); dut.io.page_free_event_out.valid.expect(false.B)
    }
  }
  it("binds one R6 retire acknowledgement exactly and cannot partially accept it") {
    simulate(new RouteAReclaimScoreboardAdapter(p)) { dut =>
      init(dut); dut.io.retire_ack_in.bits.session_id.poke(true.B); dut.io.retire_ack_in.bits.transaction_identity.request_id.poke(3.U); dut.io.retire_ack_in.bits.transaction_identity.incarnation.poke(2.U); dut.io.retire_ack_in.valid.poke(true.B)
      dut.io.retire_ack_out.ready.poke(true.B); dut.io.retire_ack_event_out.ready.poke(false.B); dut.io.retire_ack_in.ready.expect(false.B); dut.io.retire_ack_out.valid.expect(false.B)
      dut.io.retire_ack_event_out.ready.poke(true.B); dut.io.retire_ack_in.ready.expect(true.B); dut.io.retire_ack_event_out.bits.acknowledgement.transaction_identity.request_id.expect(3.U); dut.io.retire_ack_event_out.bits.acknowledgement.transaction_identity.incarnation.expect(2.U)
      dut.clock.step(); dut.io.retire_ack_in.valid.poke(false.B); dut.io.retire_ack_out.valid.expect(false.B)
    }
  }
}
