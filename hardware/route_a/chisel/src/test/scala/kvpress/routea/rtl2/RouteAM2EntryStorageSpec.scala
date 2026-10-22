package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAM2EntryStorage
import kvpress.routea.interfaces.{RouteAM2EntryUpdateKind, RouteAM2StorageFaultReason}
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Fixture-only storage-unit checks for MR-2 Package A.
  *
  * These tests deliberately drive M2EntryUpdateDeclaration directly.  They
  * prove the standalone entry-store semantics, not a production lifecycle
  * declaration source, R3 publication closure, an SRAM macro, or PPA.
  */
final class RouteAM2EntryStorageSpec extends AnyFunSpec with ChiselSim {
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

  private final case class Result(status: Int, reason: Int, valid: Boolean, slot: Int, generation: Int)

  private def init(dut: RouteAM2EntryStorage): Unit = {
    dut.io.declaration_in.valid.poke(false.B)
    dut.io.result_out.ready.poke(false.B)
  }

  private def drive(
      dut: RouteAM2EntryStorage,
      operationId: Int,
      kind: Int,
      source: Boolean = false,
      layer: Int = 0,
      head: Int = 0,
      birth: Int = 1,
      sequence: Int = 0,
      count: Int = 1,
      slot: Int = 0,
      generation: Int = 0,
      expectedOldValid: Boolean = false,
      mask: Int = -1,
      grouped: Boolean = false,
  ): Result = {
    val d = dut.io.declaration_in.bits
    d.operation_id.poke(operationId.U)
    d.update_kind.poke(kind.U)
    d.grouped.poke(grouped.B)
    d.layer.poke(layer.U)
    d.kv_head.poke(head.U)
    d.member.poke(0.U)
    d.source.poke(source.B)
    d.birth_opportunity.poke(birth.U)
    d.sequence_start.poke(sequence.U)
    d.initial_or_dequeue_count.poke(count.U)
    d.span_slot.poke(slot.U)
    d.span_generation.poke(generation.U)
    d.expected_old_valid.poke(expectedOldValid.B)
    d.operand_mask.poke((if (mask >= 0) mask else Map(0 -> 3, 1 -> 8, 2 -> 4, 3 -> 7)(kind)).U)
    d.stage_generation.poke(0.U)
    d.transaction_group_tag.poke(0.U)
    d.opaque_mapping_ref.poke(0.U)
    d.mapping_owner.poke(0.U)
    dut.io.declaration_in.valid.poke(true.B)
    dut.io.declaration_in.ready.expect(true.B)
    dut.clock.step()
    dut.io.declaration_in.valid.poke(false.B)

    dut.io.result_out.valid.expect(true.B)
    val result = Result(
      dut.io.result_out.bits.status.peek().litValue.toInt,
      dut.io.result_out.bits.fault_reason.peek().litValue.toInt,
      dut.io.result_out.bits.span_handle.valid.peek().litToBoolean,
      dut.io.result_out.bits.span_handle.slot.peek().litValue.toInt,
      dut.io.result_out.bits.span_handle.generation.peek().litValue.toInt,
    )
    dut.io.result_out.ready.poke(true.B)
    dut.clock.step()
    dut.io.result_out.ready.poke(false.B)
    result
  }

  private def expectOk(result: Result, slot: Int, generation: Int): Unit = {
    assert(result.status == p.coreMemoryOkStatusCode)
    assert(result.reason == RouteAM2StorageFaultReason.None)
    assert(result.valid && result.slot == slot && result.generation == generation)
  }

  it("performs fixture-driven append/select/dequeue/release RMW and safe slot reuse") {
    simulate(new RouteAM2EntryStorage(p)) { dut =>
      init(dut)
      expectOk(drive(dut, 1, RouteAM2EntryUpdateKind.AppendSpan, birth = 9, count = 3), 0, 0)
      dut.io.head_replica_consistent.expect(true.B)
      dut.io.span_live_count.expect(1.U)
      expectOk(drive(dut, 2, RouteAM2EntryUpdateKind.SelectOldest, birth = 9, slot = 0,
        generation = 0, expectedOldValid = true, count = 0), 0, 0)
      expectOk(drive(dut, 3, RouteAM2EntryUpdateKind.DequeueSpan, birth = 9, slot = 0,
        generation = 0, expectedOldValid = true, count = 3), 0, 0)
      expectOk(drive(dut, 4, RouteAM2EntryUpdateKind.ReleaseSpan, birth = 9, slot = 0,
        generation = 0, expectedOldValid = true, count = 0), 0, 0)
      dut.io.span_live_count.expect(0.U)
      expectOk(drive(dut, 5, RouteAM2EntryUpdateKind.AppendSpan, birth = 10, count = 1), 0, 1)
      dut.io.head_replica_consistent.expect(true.B)
      // A legal release advances the local generation.  After generation 254
      // releases, the slot reaches the 8-bit terminal value and is no longer
      // allocatable: fail closed rather than issue a wrapping handle.
      for (generation <- 1 to 254) {
        expectOk(drive(dut, 100 + generation, RouteAM2EntryUpdateKind.DequeueSpan,
          birth = 10 + generation - 1, slot = 0, generation = generation,
          expectedOldValid = true, count = 1), 0, generation)
        expectOk(drive(dut, 400 + generation, RouteAM2EntryUpdateKind.ReleaseSpan,
          birth = 10 + generation - 1, slot = 0, generation = generation,
          expectedOldValid = true, count = 0), 0, generation)
        if (generation < 254) {
          expectOk(drive(dut, 700 + generation, RouteAM2EntryUpdateKind.AppendSpan,
            birth = 10 + generation, count = 1), 0, generation + 1)
        }
      }
      val exhaustedGeneration = drive(dut, 1000, RouteAM2EntryUpdateKind.AppendSpan, birth = 999, count = 1)
      assert(exhaustedGeneration.status == p.coreMemoryFaultStatusCode)
      assert(exhaustedGeneration.reason == RouteAM2StorageFaultReason.GenerationExhausted)
      dut.io.span_live_count.expect(0.U)
    }
  }

  it("fails closed for malformed, stale, duplicate, and non-releasable updates without mutation") {
    simulate(new RouteAM2EntryStorage(p)) { dut =>
      init(dut)
      expectOk(drive(dut, 1, RouteAM2EntryUpdateKind.AppendSpan, birth = 4, sequence = 2, count = 2), 0, 0)
      val malformed = drive(dut, 2, RouteAM2EntryUpdateKind.AppendSpan, birth = 5, mask = 0)
      assert(malformed.status == p.coreMemoryFaultStatusCode)
      assert(malformed.reason == RouteAM2StorageFaultReason.DeclarationMismatch)
      val duplicate = drive(dut, 3, RouteAM2EntryUpdateKind.AppendSpan, birth = 4, sequence = 2, count = 2)
      assert(duplicate.reason == RouteAM2StorageFaultReason.SemanticPrecondition)
      val stale = drive(dut, 4, RouteAM2EntryUpdateKind.DequeueSpan, birth = 4, slot = 0,
        generation = 1, expectedOldValid = true, count = 1)
      assert(stale.reason == RouteAM2StorageFaultReason.Stale)
      val prematureRelease = drive(dut, 5, RouteAM2EntryUpdateKind.ReleaseSpan, birth = 4, slot = 0,
        generation = 0, expectedOldValid = true, count = 0)
      assert(prematureRelease.reason == RouteAM2StorageFaultReason.SemanticPrecondition)
      dut.io.span_live_count.expect(1.U)
      dut.io.head_replica_consistent.expect(true.B)
    }
  }

  it("holds a completion under backpressure and does not accept a second declaration") {
    simulate(new RouteAM2EntryStorage(p)) { dut =>
      init(dut)
      val d = dut.io.declaration_in.bits
      d.operation_id.poke(1.U); d.update_kind.poke(RouteAM2EntryUpdateKind.AppendSpan.U)
      d.grouped.poke(false.B); d.layer.poke(0.U); d.kv_head.poke(0.U); d.member.poke(0.U)
      d.source.poke(false.B); d.birth_opportunity.poke(1.U); d.sequence_start.poke(0.U)
      d.initial_or_dequeue_count.poke(1.U); d.span_slot.poke(0.U); d.span_generation.poke(0.U)
      d.expected_old_valid.poke(false.B); d.operand_mask.poke(3.U)
      d.stage_generation.poke(0.U); d.transaction_group_tag.poke(0.U); d.opaque_mapping_ref.poke(0.U); d.mapping_owner.poke(0.U)
      dut.io.declaration_in.valid.poke(true.B); dut.io.declaration_in.ready.expect(true.B)
      dut.clock.step(); dut.io.declaration_in.valid.poke(false.B)
      dut.io.result_out.valid.expect(true.B); dut.io.result_out.bits.operation_id.expect(1.U)
      dut.io.declaration_in.ready.expect(false.B)
      dut.clock.step(); dut.io.result_out.bits.operation_id.expect(1.U)
      dut.io.result_out.ready.poke(true.B); dut.clock.step(); dut.io.result_out.ready.poke(false.B)
      dut.io.declaration_in.ready.expect(true.B)
    }
  }

  it("reports capacity after all 614 bounded span slots are occupied") {
    simulate(new RouteAM2EntryStorage(p)) { dut =>
      init(dut)
      for (index <- 0 until 614) {
        expectOk(drive(dut, index + 1, RouteAM2EntryUpdateKind.AppendSpan,
          birth = index + 1, sequence = index, count = 1), index, 0)
      }
      dut.io.span_live_count.expect(614.U)
      val exhausted = drive(dut, 615, RouteAM2EntryUpdateKind.AppendSpan, birth = 615, sequence = 615, count = 1)
      assert(exhausted.status == p.coreMemoryFaultStatusCode)
      assert(exhausted.reason == RouteAM2StorageFaultReason.Capacity)
    }
  }
}
