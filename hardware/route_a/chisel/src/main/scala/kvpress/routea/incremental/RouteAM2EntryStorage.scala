package kvpress.routea.incremental

import chisel3._
import chisel3.util.{Decoupled, PopCount, PriorityEncoder, is, switch}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * Bounded logical M2 entry-store realization for the Route-A anchor DUT.
  *
  * This is deliberately a storage-unit boundary, not the production lifecycle
  * integration.  Its declaration channel is currently driven only by explicit
  * unit-test fixtures: no Route-A top-level ingress is connected, and this
  * module neither selects a source nor produces M2/R3 publication authority.
  * A later, separately approved lifecycle-declaration owner may consume this
  * exact typed interface.  The implementation models logical state only; it
  * selects no SRAM macro, port count, latency, controller, or PPA property.
  */
final class RouteAM2EntryStorage(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_m2_entry_storage"

  private val HeadEntries = 36 * 8
  private val SpanEntries = 614
  private val MaxGeneration = ((1 << RouteAAnchorWidths.M2SpanGenerationWidth) - 1).U

  /** 128-bit head-control entry: two source chains plus selection state. */
  final class HeadControlEntry extends Bundle {
    val valid = Bool()
    val private_head = new M2SpanHandle
    val private_tail = new M2SpanHandle
    val shared_head = new M2SpanHandle
    val shared_tail = new M2SpanHandle
    val selection_valid = Bool()
    val selection_source = Bool()
    val selection_epoch = UInt(RouteAAnchorWidths.ContextTokensWidth.W)
    val reserved = UInt(33.W)
  }

  /** 128-bit span-owner entry.  Slot is the array address, not duplicated data. */
  final class SpanOwnerEntry extends Bundle {
    val valid = Bool()
    val source = Bool()
    val generation = UInt(RouteAAnchorWidths.M2SpanGenerationWidth.W)
    val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
    val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
    val birth_opportunity = UInt(RouteAAnchorWidths.ContextTokensWidth.W)
    val sequence_start = UInt(RouteAAnchorWidths.ContextTokensWidth.W)
    val remaining_count = UInt(RouteAAnchorWidths.ContextTokensWidth.W)
    val previous = new M2SpanHandle
    val next = new M2SpanHandle
    val reserved = UInt(23.W)
  }

  val io = IO(new Bundle {
    val declaration_in = Flipped(Decoupled(new M2EntryUpdateDeclaration(p)))
    val result_out = Decoupled(new M2EntryUpdateResult(p))
    // Test/structural observability only; neither output is a lifecycle or
    // publication signal for the production Route-A measurement DUT.
    val head_replica_consistent = Output(Bool())
    val span_live_count = Output(UInt(RouteAAnchorWidths.M2SpanSlotWidth.W))
  })

  val headReplicaA = RegInit(VecInit(Seq.fill(HeadEntries)(0.U.asTypeOf(new HeadControlEntry))))
  val headReplicaB = RegInit(VecInit(Seq.fill(HeadEntries)(0.U.asTypeOf(new HeadControlEntry))))
  val spanOwner = RegInit(VecInit(Seq.fill(SpanEntries)(0.U.asTypeOf(new SpanOwnerEntry))))
  // A slot's next generation persists across legal release/reuse.  A slot at
  // the 8-bit maximum is never reallocated, so no issued handle can later
  // wrap and alias an older handle.
  val nextGeneration = RegInit(VecInit(Seq.fill(SpanEntries)(0.U(RouteAAnchorWidths.M2SpanGenerationWidth.W))))

  val resultPending = RegInit(false.B)
  val resultReg = RegInit(0.U.asTypeOf(new M2EntryUpdateResult(p)))
  io.result_out.valid := resultPending
  io.result_out.bits := resultReg
  when(io.result_out.fire) { resultPending := false.B }
  io.declaration_in.ready := !resultPending

  private def exactHandle(slot: UInt, generation: UInt): M2SpanHandle = {
    val result = Wire(new M2SpanHandle)
    result.valid := true.B
    result.slot := slot
    result.generation := generation
    result
  }

  private def headIndex(layer: UInt, head: UInt): UInt = layer * 8.U + head
  private def handleMatches(entry: SpanOwnerEntry, d: M2EntryUpdateDeclaration): Bool =
    entry.valid && entry.generation === d.span_generation

  val d = io.declaration_in.bits
  val entryIndexRaw = headIndex(d.layer, d.kv_head)
  val entryInRange = entryIndexRaw < HeadEntries.U
  // The range guard is part of declaration validation; this narrowed form is
  // solely the direct-index representation for the 288-entry head array.
  val entryIndex = entryIndexRaw(8, 0)
  val spanInRange = d.span_slot < SpanEntries.U
  val selectedSpan = spanOwner(d.span_slot)
  val selectedSpanMatches = spanInRange && handleMatches(selectedSpan, d)
  val currentHead = headReplicaA(entryIndex)
  val sourceHead = Mux(d.source, currentHead.shared_head, currentHead.private_head)
  val sourceTail = Mux(d.source, currentHead.shared_tail, currentHead.private_tail)

  val freeVector = VecInit(spanOwner.map(entry => !entry.valid))
  val freeExists = freeVector.asUInt.orR
  val freeSlot = PriorityEncoder(freeVector)
  val duplicateSemanticSpan = VecInit(spanOwner.map { entry =>
    entry.valid && entry.source === d.source && entry.layer === d.layer &&
      entry.kv_head === d.kv_head && entry.birth_opportunity === d.birth_opportunity &&
      entry.sequence_start === d.sequence_start
  }).asUInt.orR

  val requiredMask = Wire(UInt(4.W))
  requiredMask := "b1111".U
  switch(d.update_kind) {
    is(RouteAM2EntryUpdateKind.AppendSpan.U) { requiredMask := "b0011".U }
    is(RouteAM2EntryUpdateKind.SelectOldest.U) { requiredMask := "b1000".U }
    is(RouteAM2EntryUpdateKind.DequeueSpan.U) { requiredMask := "b0100".U }
    is(RouteAM2EntryUpdateKind.ReleaseSpan.U) { requiredMask := "b0111".U }
  }
  val supportedKind = d.update_kind <= RouteAM2EntryUpdateKind.ReleaseSpan.U
  val groupFieldsUnusedWhenUngrouped = d.grouped ||
    (d.stage_generation === 0.U && d.transaction_group_tag === 0.U &&
      d.opaque_mapping_ref === 0.U && d.mapping_owner === 0.U)
  val declarationShapeLegal = supportedKind && entryInRange &&
    d.operand_mask === requiredMask && groupFieldsUnusedWhenUngrouped

  val resultTemplate = Wire(new M2EntryUpdateResult(p))
  resultTemplate := 0.U.asTypeOf(new M2EntryUpdateResult(p))
  resultTemplate.operation_id := d.operation_id
  resultTemplate.status := p.coreMemoryFaultStatusCode.U
  resultTemplate.fault_reason := RouteAM2StorageFaultReason.DeclarationMismatch.U
  resultTemplate.grouped := d.grouped
  resultTemplate.layer := d.layer
  resultTemplate.kv_head := d.kv_head
  resultTemplate.member := d.member
  resultTemplate.stage_generation := d.stage_generation
  resultTemplate.transaction_group_tag := d.transaction_group_tag
  resultTemplate.opaque_mapping_ref := d.opaque_mapping_ref
  resultTemplate.mapping_owner := d.mapping_owner

  when(io.declaration_in.fire) {
    resultPending := true.B
    resultReg := resultTemplate

    when(!declarationShapeLegal) {
      // default result is a non-mutating declaration mismatch
    }.elsewhen(d.update_kind === RouteAM2EntryUpdateKind.AppendSpan.U) {
      when(d.expected_old_valid || d.initial_or_dequeue_count === 0.U || duplicateSemanticSpan) {
        resultReg.fault_reason := RouteAM2StorageFaultReason.SemanticPrecondition.U
      }.elsewhen(!freeExists) {
        resultReg.fault_reason := RouteAM2StorageFaultReason.Capacity.U
      }.elsewhen(nextGeneration(freeSlot) === MaxGeneration) {
        resultReg.fault_reason := RouteAM2StorageFaultReason.GenerationExhausted.U
      }.otherwise {
        val newHandle = exactHandle(freeSlot, nextGeneration(freeSlot))
        val newSpan = Wire(new SpanOwnerEntry)
        newSpan := 0.U.asTypeOf(new SpanOwnerEntry)
        newSpan.valid := true.B
        newSpan.source := d.source
        newSpan.generation := nextGeneration(freeSlot)
        newSpan.layer := d.layer
        newSpan.kv_head := d.kv_head
        newSpan.birth_opportunity := d.birth_opportunity
        newSpan.sequence_start := d.sequence_start
        newSpan.remaining_count := d.initial_or_dequeue_count
        newSpan.previous := sourceTail
        spanOwner(freeSlot) := newSpan

        val updatedHead = Wire(new HeadControlEntry)
        updatedHead := currentHead
        updatedHead.valid := true.B
        when(d.source) {
          when(!currentHead.shared_head.valid) { updatedHead.shared_head := newHandle }
          updatedHead.shared_tail := newHandle
        }.otherwise {
          when(!currentHead.private_head.valid) { updatedHead.private_head := newHandle }
          updatedHead.private_tail := newHandle
        }
        // The two replicas are committed from this one accepted declaration in
        // the same clock edge.  They are never independently updated.
        headReplicaA(entryIndex) := updatedHead
        headReplicaB(entryIndex) := updatedHead
        when(sourceTail.valid) {
          val predecessor = Wire(new SpanOwnerEntry)
          predecessor := spanOwner(sourceTail.slot)
          predecessor.next := newHandle
          spanOwner(sourceTail.slot) := predecessor
        }
        resultReg.status := p.coreMemoryOkStatusCode.U
        resultReg.fault_reason := RouteAM2StorageFaultReason.None.U
        resultReg.span_handle := newHandle
      }
    }.elsewhen(!d.expected_old_valid || !selectedSpanMatches) {
      resultReg.fault_reason := RouteAM2StorageFaultReason.Stale.U
    }.elsewhen(d.update_kind === RouteAM2EntryUpdateKind.SelectOldest.U) {
      when(selectedSpan.source =/= d.source || selectedSpan.layer =/= d.layer || selectedSpan.kv_head =/= d.kv_head ||
          !sourceHead.valid || sourceHead.slot =/= d.span_slot || sourceHead.generation =/= d.span_generation) {
        resultReg.fault_reason := RouteAM2StorageFaultReason.SemanticPrecondition.U
      }.otherwise {
        val updatedHead = Wire(new HeadControlEntry)
        updatedHead := currentHead
        updatedHead.selection_valid := true.B
        updatedHead.selection_source := d.source
        updatedHead.selection_epoch := d.birth_opportunity
        headReplicaA(entryIndex) := updatedHead
        headReplicaB(entryIndex) := updatedHead
        resultReg.status := p.coreMemoryOkStatusCode.U
        resultReg.fault_reason := RouteAM2StorageFaultReason.None.U
        resultReg.span_handle := exactHandle(d.span_slot, d.span_generation)
      }
    }.elsewhen(d.update_kind === RouteAM2EntryUpdateKind.DequeueSpan.U) {
      when(selectedSpan.source =/= d.source || selectedSpan.layer =/= d.layer || selectedSpan.kv_head =/= d.kv_head ||
          d.initial_or_dequeue_count === 0.U || d.initial_or_dequeue_count > selectedSpan.remaining_count) {
        resultReg.fault_reason := RouteAM2StorageFaultReason.SemanticPrecondition.U
      }.otherwise {
        val updatedSpan = Wire(new SpanOwnerEntry)
        updatedSpan := selectedSpan
        updatedSpan.remaining_count := selectedSpan.remaining_count - d.initial_or_dequeue_count
        spanOwner(d.span_slot) := updatedSpan
        resultReg.status := p.coreMemoryOkStatusCode.U
        resultReg.fault_reason := RouteAM2StorageFaultReason.None.U
        resultReg.span_handle := exactHandle(d.span_slot, d.span_generation)
      }
    }.elsewhen(d.update_kind === RouteAM2EntryUpdateKind.ReleaseSpan.U) {
      when(selectedSpan.source =/= d.source || selectedSpan.layer =/= d.layer || selectedSpan.kv_head =/= d.kv_head ||
          selectedSpan.remaining_count =/= 0.U) {
        resultReg.fault_reason := RouteAM2StorageFaultReason.SemanticPrecondition.U
      }.elsewhen(selectedSpan.generation === MaxGeneration) {
        resultReg.fault_reason := RouteAM2StorageFaultReason.GenerationExhausted.U
      }.otherwise {
        val updatedHead = Wire(new HeadControlEntry)
        updatedHead := currentHead
        when(d.source) {
          when(currentHead.shared_head.slot === d.span_slot && currentHead.shared_head.generation === d.span_generation) {
            updatedHead.shared_head := selectedSpan.next
          }
          when(currentHead.shared_tail.slot === d.span_slot && currentHead.shared_tail.generation === d.span_generation) {
            updatedHead.shared_tail := selectedSpan.previous
          }
        }.otherwise {
          when(currentHead.private_head.slot === d.span_slot && currentHead.private_head.generation === d.span_generation) {
            updatedHead.private_head := selectedSpan.next
          }
          when(currentHead.private_tail.slot === d.span_slot && currentHead.private_tail.generation === d.span_generation) {
            updatedHead.private_tail := selectedSpan.previous
          }
        }
        headReplicaA(entryIndex) := updatedHead
        headReplicaB(entryIndex) := updatedHead
        when(selectedSpan.previous.valid) {
          val previous = Wire(new SpanOwnerEntry)
          previous := spanOwner(selectedSpan.previous.slot)
          previous.next := selectedSpan.next
          spanOwner(selectedSpan.previous.slot) := previous
        }
        when(selectedSpan.next.valid) {
          val next = Wire(new SpanOwnerEntry)
          next := spanOwner(selectedSpan.next.slot)
          next.previous := selectedSpan.previous
          spanOwner(selectedSpan.next.slot) := next
        }
        spanOwner(d.span_slot) := 0.U.asTypeOf(new SpanOwnerEntry)
        nextGeneration(d.span_slot) := nextGeneration(d.span_slot) + 1.U
        resultReg.status := p.coreMemoryOkStatusCode.U
        resultReg.fault_reason := RouteAM2StorageFaultReason.None.U
        resultReg.span_handle := exactHandle(d.span_slot, d.span_generation)
      }
    }
  }

  io.head_replica_consistent := VecInit((0 until HeadEntries).map { index =>
    headReplicaA(index).asUInt === headReplicaB(index).asUInt
  }).asUInt.andR
  io.span_live_count := PopCount(VecInit(spanOwner.map(_.valid)).asUInt)

  for (index <- 0 until HeadEntries) {
    assert(headReplicaA(index).asUInt === headReplicaB(index).asUInt)
  }
  when(io.result_out.valid && !io.result_out.ready) {
    assert(io.result_out.bits.asUInt === resultReg.asUInt)
  }
}
