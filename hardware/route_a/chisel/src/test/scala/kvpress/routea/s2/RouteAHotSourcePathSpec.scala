package kvpress.routea.s2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAHotSourcePath
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** I3 hot-owner completion control only; no hot K/V storage or service path. */
final class RouteAHotSourcePathSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8, coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1, p3StageGenerationWidth = 1, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(dut: RouteAHotSourcePath): Unit = {
    dut.io.lifecycle_control_in.valid.poke(false.B); dut.io.hot_source_open_in.valid.poke(false.B)
    dut.io.gqa_consumer_commit_in.valid.poke(false.B); dut.io.hot_release_out.ready.poke(true.B)
  }

  private def open(dut: RouteAHotSourcePath, generation: Int): Unit = {
    val source = dut.io.hot_source_open_in.bits
    source.transaction_identity.request_id.poke(1.U); source.transaction_identity.incarnation.poke(0.U)
    source.source_instance.source_kind.poke(0.U); source.source_instance.instance_coordinate.poke(99.U); source.source_instance.generation.poke(generation.U)
    dut.io.hot_source_open_in.valid.poke(true.B); dut.io.hot_source_open_in.ready.expect(true.B); dut.clock.step(); dut.io.hot_source_open_in.valid.poke(false.B)
  }

  private def commit(dut: RouteAHotSourcePath, generation: Int, consumer: Int): Unit = {
    val c = dut.io.gqa_consumer_commit_in.bits
    c.transaction_identity.request_id.poke(1.U); c.transaction_identity.incarnation.poke(0.U)
    c.source_instance.source_kind.poke(0.U); c.source_instance.instance_coordinate.poke(99.U); c.source_instance.generation.poke(generation.U); c.consumer_id.poke(consumer.U)
    dut.io.gqa_consumer_commit_in.valid.poke(true.B); dut.io.gqa_consumer_commit_in.ready.expect(true.B); dut.clock.step(); dut.io.gqa_consumer_commit_in.valid.poke(false.B)
  }

  it("requires four matching current-instance commits before one stable hot release") {
    simulate(new RouteAHotSourcePath(p)) { dut =>
      init(dut); open(dut, 1)
      val stale = dut.io.gqa_consumer_commit_in.bits
      stale.transaction_identity.request_id.poke(1.U); stale.transaction_identity.incarnation.poke(0.U)
      stale.source_instance.source_kind.poke(0.U); stale.source_instance.instance_coordinate.poke(99.U); stale.source_instance.generation.poke(0.U); stale.consumer_id.poke(0.U)
      dut.io.gqa_consumer_commit_in.valid.poke(true.B); dut.io.gqa_consumer_commit_in.ready.expect(false.B); dut.io.gqa_consumer_commit_in.valid.poke(false.B)
      (0 until 4).foreach(commit(dut, 1, _))
      dut.io.hot_release_out.valid.expect(true.B); dut.io.hot_release_out.ready.poke(false.B); dut.clock.step()
      dut.io.hot_release_out.bits.source_instance.generation.expect(1.U)
      dut.io.hot_release_out.ready.poke(true.B); dut.clock.step(); dut.io.hot_release_out.valid.expect(false.B)
    }
  }
}
