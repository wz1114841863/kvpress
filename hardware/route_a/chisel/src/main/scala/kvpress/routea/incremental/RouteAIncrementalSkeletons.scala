package kvpress.routea.incremental

import chisel3._
import chisel3.util.{Cat, Enum, Fill, MuxCase, PopCount, PriorityEncoder, RegEnable, log2Ceil}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteADescriptorOperationKind, RouteAM2GroupMember, RouteAPublicationStatus, RouteASkeletonParameters}

/**
  * RTL1.5 R6 lifecycle control. It owns only session/attention/terminal/drain
  * associations; long-lived hot/pending/packed state remains at its frozen
  * owners and crosses this wrapper as event-level authority transitions.
  */
final class RouteALifecycleAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_lifecycle_adapter"

  val io = IO(new Bundle {
    val frontend_lifecycle_req = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val session_retire_ack = RouteAChannels.session_retire_ack
    val component_status_in = Flipped(RouteAChannels.component_status(p))
    val drain_collection_enable = Output(Bool())
    // Retirement-only permit for R5 descriptor invalidation. It is neither an
    // allocation grant nor a memory-controller schedule.
    val reclaim_permit_out = RouteAChannels.reclaim_permit
    val reclaim_maintenance_enable = Output(Bool())
    val reclaim_drain_restart = Output(Bool())
    val reclaim_final_drain_enable = Output(Bool())
    val r5_reclaim_complete_in = Input(Bool())
    val hot_control_out = RouteAChannels.hot_control(p)
    val authority_transition_out = RouteAChannels.r6_authority_transition(p)
    val admission_context_out = RouteAChannels.admission_context(p)
    val authority_transition_in = Flipped(RouteAChannels.r6_authority_transition(p))
    val merge_ready_in = Flipped(RouteAChannels.r6_merge_ready)
    val source_completion_plan_in = Flipped(RouteAChannels.source_completion_plan(p))
    val hot_source_release_in = Flipped(RouteAChannels.source_release(p))
    val pending_source_release_in = Flipped(RouteAChannels.source_release(p))
    val packed_source_release_in = Flipped(RouteAChannels.source_release(p))
    val s2_service_req = RouteAChannels.s2_service_req
    val direct_pending_open = RouteAChannels.direct_pending_open(p)
    val merge_req = RouteAChannels.merge_req
    val merge_terminal_in = Flipped(RouteAChannels.merge_terminal_rsp)
    val metadata_publish_req = RouteAChannels.metadata_publish_req(p)
    val metadata_publish_ack_in = Flipped(RouteAChannels.metadata_publish_ack(p))
  })

  private val StateReset = 0.U(3.W)
  private val StateIdle = 1.U(3.W)
  private val StateActive = 2.U(3.W)
  private val StateRetiring = 3.U(3.W)
  private val StateRetired = 4.U(3.W)
  private val AwaitMergeReady = 0.U(1.W)
  private val MergeIssued = 1.U(1.W)
  private val trackerEntries = p.r6.attentionTrackerEntries
  private val trackerIndexWidth = math.max(1, log2Ceil(trackerEntries))

  val state = RegInit(StateReset)
  val initAcks = RegInit(0.U(3.W))
  val drainAcks = RegInit(0.U(8.W))
  val retireIdentity = Reg(new TransactionIdentity)
  val reclaimPermitIssued = RegInit(false.B)
  val reclaimPermitAccepted = RegInit(false.B)
  val reclaimComplete = RegInit(false.B)

  // This is a lifecycle phase fact, not a timeout or scheduling grant. Local
  // owners use it only to quiesce new ingress and offer their named drain fact.
  io.drain_collection_enable := state === StateRetiring
  io.reclaim_permit_out.valid := state === StateRetiring && reclaimPermitIssued && !reclaimPermitAccepted && !reclaimComplete
  io.reclaim_permit_out.bits.transaction_identity := retireIdentity
  io.reclaim_maintenance_enable := reclaimPermitAccepted && !reclaimComplete
  io.reclaim_final_drain_enable := state === StateRetiring && (!reclaimPermitIssued || reclaimComplete)
  io.reclaim_drain_restart := false.B

  // One lifecycle event remains stable until both independently-owned local
  // observations have accepted it. This is event staging, not a token table.
  val controlPending = RegInit(false.B)
  val controlIsArrival = RegInit(false.B)
  val controlEntryId = Reg(UInt(RouteAAnchorWidths.EntryIdWidth.W))
  val controlLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val controlHead = Reg(UInt(RouteAAnchorWidths.KvHeadWidth.W))
  val controlPosition = Reg(UInt(RouteAAnchorWidths.LogicalPositionWidth.W))
  val controlPayloadRef = Reg(UInt(RouteAAnchorWidths.PayloadRefWidth.W))
  val controlRetain = RegInit(false.B)
  val controlAdmissionGroupTag = Reg(UInt(p.transactionGroupTagWidth.W))
  val controlAdmissionMemberOrdinal = Reg(UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W))
  val controlAdmissionGroupValidRecords = Reg(UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W))
  val hotControlSent = RegInit(false.B)
  val authoritySent = RegInit(false.B)
  val admissionContextSent = RegInit(false.B)

  val attentionValid = RegInit(VecInit(Seq.fill(trackerEntries)(false.B)))
  val attentionIdentity = Reg(Vec(trackerEntries, new TransactionIdentity))
  val attentionStage = RegInit(VecInit(Seq.fill(trackerEntries)(AwaitMergeReady)))
  val sourcePlanValid = RegInit(VecInit(Seq.fill(trackerEntries)(false.B)))
  val sourcePlanPresence = Reg(Vec(trackerEntries, UInt(RouteAAnchorWidths.SourcePresenceWidth.W)))
  val sourcePlanReleased = RegInit(VecInit(Seq.fill(trackerEntries)(0.U(RouteAAnchorWidths.SourcePresenceWidth.W))))
  val sourcePlanHot = Reg(Vec(trackerEntries, new SourceInstance(p)))
  val sourcePlanPending = Reg(Vec(trackerEntries, new SourceInstance(p)))
  val sourcePlanPacked = Reg(Vec(trackerEntries, new SourceInstance(p)))
  val mergePending = RegInit(false.B)
  val mergeIdentity = Reg(new TransactionIdentity)
  val mergePresence = Reg(UInt(RouteAAnchorWidths.SourcePresenceWidth.W))
  val mergeTrackerSlot = Reg(UInt(trackerIndexWidth.W))
  val terminalPending = RegInit(false.B)
  val terminalIdentity = Reg(new TransactionIdentity)
  val terminalStatus = Reg(UInt(RouteAAnchorWidths.TerminalStatusWidth.W))
  val terminalTrackerSlot = Reg(UInt(trackerIndexWidth.W))

  private def identityMatches(left: TransactionIdentity, right: TransactionIdentity): Bool =
    left.asUInt === right.asUInt

  val status = io.component_status_in.bits
  val initCode = status.acknowledgement_name === p.r6.memInitDoneStatusCode.U ||
    status.acknowledgement_name === p.r6.m2P3InitDoneStatusCode.U ||
    status.acknowledgement_name === p.r6.pageManagerInitDoneStatusCode.U
  val drainCode = status.acknowledgement_name === p.r6.r1MemoryDrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.r2PayloadDrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.r2DescriptorDrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.r3M2P3DrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.r5PageManagerDrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.s2GqaDrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.directPendingDrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.mergeDrainedStatusCode.U
  val finalPassDrainCode = status.acknowledgement_name === p.r6.r1MemoryDrainedStatusCode.U ||
    status.acknowledgement_name === p.r6.r2DescriptorDrainedStatusCode.U
  val drainPhaseAccepts = !reclaimPermitIssued || reclaimComplete || !finalPassDrainCode
  io.component_status_in.ready := status.asserted &&
    ((state === StateReset && initCode) || (state === StateRetiring && drainCode && drainPhaseAccepts))
  when(io.component_status_in.fire && state === StateReset) {
    val initBit = WireDefault(0.U(3.W))
    when(status.acknowledgement_name === p.r6.memInitDoneStatusCode.U) { initBit := "b001".U }
    when(status.acknowledgement_name === p.r6.m2P3InitDoneStatusCode.U) { initBit := "b010".U }
    when(status.acknowledgement_name === p.r6.pageManagerInitDoneStatusCode.U) { initBit := "b100".U }
    val nextInitAcks = initAcks | initBit
    initAcks := nextInitAcks
    when(nextInitAcks === "b111".U) { state := StateIdle }
  }
  when(io.component_status_in.fire && state === StateRetiring) {
    val drainBit = WireDefault(0.U(8.W))
    when(status.acknowledgement_name === p.r6.r1MemoryDrainedStatusCode.U) { drainBit := "b00000001".U }
    when(status.acknowledgement_name === p.r6.r2PayloadDrainedStatusCode.U) { drainBit := "b00000010".U }
    when(status.acknowledgement_name === p.r6.r2DescriptorDrainedStatusCode.U) { drainBit := "b00000100".U }
    when(status.acknowledgement_name === p.r6.r3M2P3DrainedStatusCode.U) { drainBit := "b00001000".U }
    when(status.acknowledgement_name === p.r6.r5PageManagerDrainedStatusCode.U) { drainBit := "b00010000".U }
    when(status.acknowledgement_name === p.r6.s2GqaDrainedStatusCode.U) { drainBit := "b00100000".U }
    when(status.acknowledgement_name === p.r6.directPendingDrainedStatusCode.U) { drainBit := "b01000000".U }
    when(status.acknowledgement_name === p.r6.mergeDrainedStatusCode.U) { drainBit := "b10000000".U }
    drainAcks := drainAcks | drainBit
  }

  val lifecycle = io.frontend_lifecycle_req.bits
  val isSessionStart = lifecycle.event_kind === p.r6.sessionStartEventCode.U
  val isArrival = lifecycle.event_kind === p.r6.kvArrivalEventCode.U
  val isMaturity = lifecycle.event_kind === p.r6.maturityDispositionEventCode.U
  val isAttention = lifecycle.event_kind === p.r6.attentionServiceEventCode.U
  val derivedEntryId = lifecycle.logical_position * 288.U + lifecycle.layer * 8.U + lifecycle.kv_head
  val anchorCoordinate = lifecycle.layer < 36.U && lifecycle.kv_head < 8.U &&
    lifecycle.entry_id === derivedEntryId
  val freeMask = VecInit((0 until trackerEntries).map(slot => !attentionValid(slot)))
  val freeAttentionSlot = PriorityEncoder(freeMask)
  val attentionIdentitySeen = VecInit((0 until trackerEntries).map(slot =>
    attentionValid(slot) && identityMatches(attentionIdentity(slot), lifecycle.transaction_identity),
  )).asUInt.orR
  val sessionStartLegal = state === StateIdle && !lifecycle.session_id &&
    lifecycle.context_tokens === 32768.U
  val controlLegal = state === StateActive && !controlPending && !lifecycle.session_id && anchorCoordinate
  val attentionLegal = state === StateActive && !lifecycle.session_id && anchorCoordinate &&
    freeMask.asUInt.orR && !attentionIdentitySeen
  io.frontend_lifecycle_req.ready := MuxCase(false.B, Seq(
    isSessionStart -> sessionStartLegal,
    isArrival -> controlLegal,
    isMaturity -> controlLegal,
    isAttention -> attentionLegal,
  ))
  when(io.frontend_lifecycle_req.fire) {
    when(isSessionStart) {
      state := StateActive
      drainAcks := 0.U
    }.elsewhen(isArrival || isMaturity) {
      controlPending := true.B
      controlIsArrival := isArrival
      controlEntryId := lifecycle.entry_id
      controlLayer := lifecycle.layer
      controlHead := lifecycle.kv_head
      controlPosition := lifecycle.logical_position
      controlPayloadRef := lifecycle.payload_ref
      controlRetain := lifecycle.disposition
      controlAdmissionGroupTag := lifecycle.admission_group_tag
      controlAdmissionMemberOrdinal := lifecycle.admission_member_ordinal
      controlAdmissionGroupValidRecords := lifecycle.admission_group_valid_records
      hotControlSent := false.B
      authoritySent := false.B
      admissionContextSent := false.B
    }.elsewhen(isAttention) {
      attentionValid(freeAttentionSlot) := true.B
      attentionIdentity(freeAttentionSlot) := lifecycle.transaction_identity
      attentionStage(freeAttentionSlot) := AwaitMergeReady
      sourcePlanValid(freeAttentionSlot) := false.B
      sourcePlanReleased(freeAttentionSlot) := 0.U
    }
  }

  io.hot_control_out.valid := controlPending && !hotControlSent
  io.hot_control_out.bits.control_kind := Mux(controlIsArrival, p.r6.hotArrivalControlCode.U,
    Mux(controlRetain, p.r6.hotRetainControlCode.U, p.r6.hotDropControlCode.U))
  io.hot_control_out.bits.entry_id := controlEntryId
  io.hot_control_out.bits.layer := controlLayer
  io.hot_control_out.bits.kv_head := controlHead
  io.hot_control_out.bits.logical_position := controlPosition
  io.hot_control_out.bits.disposition := controlRetain

  io.authority_transition_out.valid := controlPending && !authoritySent
  io.authority_transition_out.bits.entry_id := controlEntryId
  io.authority_transition_out.bits.from_authority := Mux(controlIsArrival,
    RouteAAuthorityStateCode.None.U, RouteAAuthorityStateCode.Hot.U)
  io.authority_transition_out.bits.to_authority := Mux(controlIsArrival,
    RouteAAuthorityStateCode.Hot.U,
    Mux(controlRetain, RouteAAuthorityStateCode.Pending.U, RouteAAuthorityStateCode.None.U))
  io.authority_transition_out.bits.transaction_group_tag := Mux(
    !controlIsArrival && controlRetain,
    controlAdmissionGroupTag,
    0.U,
  )

  io.admission_context_out.valid := controlPending && !controlIsArrival && controlRetain && !admissionContextSent
  io.admission_context_out.bits.entry_id := controlEntryId
  io.admission_context_out.bits.layer := controlLayer
  io.admission_context_out.bits.kv_head := controlHead
  io.admission_context_out.bits.logical_position := controlPosition
  io.admission_context_out.bits.payload_ref := controlPayloadRef
  io.admission_context_out.bits.transaction_group_tag := controlAdmissionGroupTag
  io.admission_context_out.bits.group_member_ordinal := controlAdmissionMemberOrdinal
  io.admission_context_out.bits.group_valid_records := controlAdmissionGroupValidRecords
  when(controlPending) {
    when(io.hot_control_out.fire) { hotControlSent := true.B }
    when(io.authority_transition_out.fire) { authoritySent := true.B }
    when(io.admission_context_out.fire) { admissionContextSent := true.B }
    val hotDone = hotControlSent || io.hot_control_out.fire
    val authorityDone = authoritySent || io.authority_transition_out.fire
    val admissionDone = controlIsArrival || !controlRetain || admissionContextSent || io.admission_context_out.fire
    when(hotDone && authorityDone && admissionDone) { controlPending := false.B }
  }

  val authorityIn = io.authority_transition_in.bits
  val publicationTransition = authorityIn.from_authority === RouteAAuthorityStateCode.Pending.U &&
    authorityIn.to_authority === RouteAAuthorityStateCode.Packed.U
  io.authority_transition_in.ready := (state === StateActive || state === StateRetiring) && publicationTransition
  when(io.authority_transition_in.fire) {
    // a_authority_conservation: the only R3-confirmed incoming handoff is
    // pending -> packed. R6 intentionally carries no duplicate token table;
    // exact per-entry cardinality stays in the transaction scoreboard.
    assert(publicationTransition)
  }
  when(io.authority_transition_out.valid) {
    val arrivalEdge = controlIsArrival &&
      io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.None.U &&
      io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Hot.U
    val retainEdge = !controlIsArrival && controlRetain &&
      io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Hot.U &&
      io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Pending.U
    val dropEdge = !controlIsArrival && !controlRetain &&
      io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Hot.U &&
      io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.None.U
    assert(arrivalEdge || retainEdge || dropEdge)
  }

  val sourcePlan = io.source_completion_plan_in.bits
  val sourcePlanMatches = VecInit((0 until trackerEntries).map(slot =>
    attentionValid(slot) && attentionStage(slot) === AwaitMergeReady && !sourcePlanValid(slot) &&
      identityMatches(attentionIdentity(slot), sourcePlan.transaction_identity),
  ))
  val sourcePlanSlot = PriorityEncoder(sourcePlanMatches)
  val sourcePlanKindsLegal = sourcePlan.source_presence.orR &&
    sourcePlan.hot_instance.source_kind === RouteASourceKind.Hot.U &&
    sourcePlan.pending_instance.source_kind === RouteASourceKind.Pending.U &&
    sourcePlan.packed_instance.source_kind === RouteASourceKind.Packed.U
  io.source_completion_plan_in.ready := (state === StateActive || state === StateRetiring) &&
    sourcePlanKindsLegal && sourcePlanMatches.asUInt.orR
  when(io.source_completion_plan_in.fire) {
    sourcePlanValid(sourcePlanSlot) := true.B
    sourcePlanPresence(sourcePlanSlot) := sourcePlan.source_presence
    sourcePlanReleased(sourcePlanSlot) := 0.U
    sourcePlanHot(sourcePlanSlot) := sourcePlan.hot_instance
    sourcePlanPending(sourcePlanSlot) := sourcePlan.pending_instance
    sourcePlanPacked(sourcePlanSlot) := sourcePlan.packed_instance
  }

  private def releaseMatches(release: SourceRelease, expectedKind: Int, expected: Int => SourceInstance) =
    VecInit((0 until trackerEntries).map(slot =>
      attentionValid(slot) && attentionStage(slot) === AwaitMergeReady && sourcePlanValid(slot) &&
        identityMatches(attentionIdentity(slot), release.transaction_identity) &&
        sourcePlanPresence(slot)(expectedKind) && !sourcePlanReleased(slot)(expectedKind) &&
        release.source_instance.asUInt === expected(slot).asUInt,
    ))
  private def applyRelease(matches: Vec[Bool], releaseKind: Int): Unit = {
    val slot = PriorityEncoder(matches)
    val nextReleased = sourcePlanReleased(slot) | (1.U(RouteAAnchorWidths.SourcePresenceWidth.W) << releaseKind)
    when(matches.asUInt.orR) {
      sourcePlanReleased(slot) := nextReleased
      when(nextReleased === sourcePlanPresence(slot)) {
        mergePending := true.B
        mergeIdentity := attentionIdentity(slot)
        mergePresence := sourcePlanPresence(slot)
        mergeTrackerSlot := slot
        sourcePlanValid(slot) := false.B
      }
    }
  }
  val hotReleaseMatches = releaseMatches(io.hot_source_release_in.bits, RouteASourceKind.Hot, sourcePlanHot)
  val pendingReleaseMatches = releaseMatches(io.pending_source_release_in.bits, RouteASourceKind.Pending, sourcePlanPending)
  val packedReleaseMatches = releaseMatches(io.packed_source_release_in.bits, RouteASourceKind.Packed, sourcePlanPacked)
  val sourceReleaseEnabled = (state === StateActive || state === StateRetiring) && !mergePending && !terminalPending
  io.hot_source_release_in.ready := sourceReleaseEnabled && hotReleaseMatches.asUInt.orR
  io.pending_source_release_in.ready := sourceReleaseEnabled && !hotReleaseMatches.asUInt.orR && pendingReleaseMatches.asUInt.orR
  io.packed_source_release_in.ready := sourceReleaseEnabled && !hotReleaseMatches.asUInt.orR &&
    !pendingReleaseMatches.asUInt.orR && packedReleaseMatches.asUInt.orR
  when(io.hot_source_release_in.fire) { applyRelease(hotReleaseMatches, RouteASourceKind.Hot) }
  when(io.pending_source_release_in.fire) { applyRelease(pendingReleaseMatches, RouteASourceKind.Pending) }
  when(io.packed_source_release_in.fire) { applyRelease(packedReleaseMatches, RouteASourceKind.Packed) }

  val mergeReady = io.merge_ready_in.bits
  val mergeReadyMatches = VecInit((0 until trackerEntries).map(slot =>
    attentionValid(slot) && attentionStage(slot) === AwaitMergeReady &&
      !sourcePlanValid(slot) &&
      identityMatches(attentionIdentity(slot), mergeReady.transaction_identity),
  ))
  val mergeReadySlot = PriorityEncoder(mergeReadyMatches)
  io.merge_ready_in.ready := (state === StateActive || state === StateRetiring) && !mergePending &&
    mergeReady.source_presence.orR && mergeReadyMatches.asUInt.orR
  when(io.merge_ready_in.fire) {
    mergePending := true.B
    mergeIdentity := mergeReady.transaction_identity
    mergePresence := mergeReady.source_presence
    mergeTrackerSlot := mergeReadySlot
  }

  io.merge_req.valid := mergePending
  io.merge_req.bits.transaction_identity := mergeIdentity
  io.merge_req.bits.source_presence := mergePresence
  when(io.merge_req.fire) {
    attentionStage(mergeTrackerSlot) := MergeIssued
    mergePending := false.B
  }

  val mergeTerminal = io.merge_terminal_in.bits
  val terminalMatches = VecInit((0 until trackerEntries).map(slot =>
    attentionValid(slot) && attentionStage(slot) === MergeIssued &&
      identityMatches(attentionIdentity(slot), mergeTerminal.transaction_identity),
  ))
  val terminalMatchSlot = PriorityEncoder(terminalMatches)
  val terminalStatusKnown = mergeTerminal.status === p.coreMemoryOkStatusCode.U ||
    mergeTerminal.status === p.coreMemoryFaultStatusCode.U
  io.merge_terminal_in.ready := (state === StateActive || state === StateRetiring) && !terminalPending &&
    terminalStatusKnown && terminalMatches.asUInt.orR
  when(io.merge_terminal_in.fire) {
    when(mergeTerminal.status === p.coreMemoryFaultStatusCode.U) {
      // a_numeric_fault_consumer: fault is accepted only after merge-ready/GQA completion.
      assert(terminalMatches.asUInt.orR && !terminalPending)
    }
    terminalPending := true.B
    terminalIdentity := mergeTerminal.transaction_identity
    terminalStatus := mergeTerminal.status
    terminalTrackerSlot := terminalMatchSlot
  }

  io.attention_terminal_rsp.valid := terminalPending
  io.attention_terminal_rsp.bits.transaction_identity := terminalIdentity
  io.attention_terminal_rsp.bits.terminal_status := terminalStatus
  when(io.attention_terminal_rsp.fire) {
    // a_exactly_one_terminal: only the one matching live tracker may retire here.
    assert(attentionValid(terminalTrackerSlot) && attentionStage(terminalTrackerSlot) === MergeIssued)
    attentionValid(terminalTrackerSlot) := false.B
    sourcePlanValid(terminalTrackerSlot) := false.B
    terminalPending := false.B
  }

  io.runtime_retire_req.ready := state === StateActive && !io.runtime_retire_req.bits.session_id
  when(io.runtime_retire_req.fire) {
    retireIdentity := io.runtime_retire_req.bits.transaction_identity
    drainAcks := 0.U
    reclaimPermitIssued := false.B
    reclaimPermitAccepted := false.B
    reclaimComplete := false.B
    state := StateRetiring
  }
  val trackerEmpty = !attentionValid.asUInt.orR
  val preReclaimDrained = (drainAcks & "hef".U) === "hef".U
  val preReclaimReady = state === StateRetiring && !reclaimPermitIssued && trackerEmpty &&
    !controlPending && !mergePending && !terminalPending && preReclaimDrained
  when(preReclaimReady) {
    // Pre-reclaim R1 and descriptor-drain facts cannot satisfy the final
    // drain: R5 is about to submit a new descriptor maintenance write.
    reclaimPermitIssued := true.B
    drainAcks := drainAcks & "b11111010".U
    io.reclaim_drain_restart := true.B
  }
  when(io.reclaim_permit_out.fire) { reclaimPermitAccepted := true.B }
  when(state === StateRetiring && reclaimPermitIssued && !reclaimComplete && io.r5_reclaim_complete_in) {
    reclaimComplete := true.B
  }
  val retireReady = state === StateRetiring && reclaimComplete && trackerEmpty && !controlPending && !mergePending &&
    !terminalPending && drainAcks === "hff".U
  io.session_retire_ack.valid := retireReady
  io.session_retire_ack.bits.session_id := false.B
  io.session_retire_ack.bits.transaction_identity := retireIdentity
  when(io.session_retire_ack.fire) {
    // a_global_retirement_membership: this is the only R6 global-drain acknowledgement point.
    assert(reclaimComplete && trackerEmpty && drainAcks === "hff".U)
    state := StateRetired
  }

  // Decoupled outputs are state/payload-stable while their peer holds ready low.
  val heldHot = RegEnable(io.hot_control_out.bits, io.hot_control_out.valid && !io.hot_control_out.ready)
  when(RegNext(io.hot_control_out.valid && !io.hot_control_out.ready, false.B)) {
    assert(io.hot_control_out.bits.asUInt === heldHot.asUInt)
  }
  val heldAuthority = RegEnable(io.authority_transition_out.bits, io.authority_transition_out.valid && !io.authority_transition_out.ready)
  when(RegNext(io.authority_transition_out.valid && !io.authority_transition_out.ready, false.B)) {
    assert(io.authority_transition_out.bits.asUInt === heldAuthority.asUInt)
  }
  val heldAdmission = RegEnable(io.admission_context_out.bits, io.admission_context_out.valid && !io.admission_context_out.ready)
  when(RegNext(io.admission_context_out.valid && !io.admission_context_out.ready, false.B)) {
    assert(io.admission_context_out.bits.asUInt === heldAdmission.asUInt)
  }
  val heldMerge = RegEnable(io.merge_req.bits, io.merge_req.valid && !io.merge_req.ready)
  when(RegNext(io.merge_req.valid && !io.merge_req.ready, false.B)) {
    assert(io.merge_req.bits.asUInt === heldMerge.asUInt)
  }
  val heldTerminal = RegEnable(io.attention_terminal_rsp.bits, io.attention_terminal_rsp.valid && !io.attention_terminal_rsp.ready)
  when(RegNext(io.attention_terminal_rsp.valid && !io.attention_terminal_rsp.ready, false.B)) {
    assert(io.attention_terminal_rsp.bits.asUInt === heldTerminal.asUInt)
  }
  val heldRetire = RegEnable(io.session_retire_ack.bits, io.session_retire_ack.valid && !io.session_retire_ack.ready)
  when(RegNext(io.session_retire_ack.valid && !io.session_retire_ack.ready, false.B)) {
    assert(io.session_retire_ack.bits.asUInt === heldRetire.asUInt)
  }
  val heldReclaimPermit = RegEnable(io.reclaim_permit_out.bits,
    io.reclaim_permit_out.valid && !io.reclaim_permit_out.ready)
  when(RegNext(io.reclaim_permit_out.valid && !io.reclaim_permit_out.ready, false.B)) {
    assert(io.reclaim_permit_out.bits.asUInt === heldReclaimPermit.asUInt)
  }

  StructuralTieOff.source(io.s2_service_req)
  StructuralTieOff.source(io.direct_pending_open)
  StructuralTieOff.source(io.metadata_publish_req)
  // R6 observes this as a completed R3/R5 publication fact only.  It does not
  // issue a second commit or retain publication membership.
  io.metadata_publish_ack_in.ready := state === StateActive || state === StateRetiring
}

/**
  * RTL2.1a's sole retained-group protocol owner.  This is a one-packer,
  * one-active-group control association: it stores immutable R6 RETAIN facts,
  * obtains the pre-existing R5 allocation and R3 P3 reservation, then relays
  * every original context/authority pair to the existing R3 join.  It never
  * moves payload, creates R1 work, changes authority, publishes metadata, or
  * chooses a queue/macro implementation.
  */
final class RouteAAdmissionPublicationIngressAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_admission_publication_ingress_adapter"

  val io = IO(new Bundle {
    val r6_admission_context_in = Flipped(RouteAChannels.admission_context(p))
    val r6_authority_in = Flipped(RouteAChannels.r6_authority_transition(p))
    val r5_allocation_req = RouteAChannels.page_allocation_req(p)
    val r5_allocation_rsp_in = Flipped(RouteAChannels.page_allocation_rsp(p))
    val r3_p3_claim = RouteAChannels.p3_claim(p)
    val r3_p3_claim_ack_in = Flipped(RouteAChannels.p3_claim_ack(p))
    val r3_admission_context_out = RouteAChannels.admission_context(p)
    val r3_admission_authority_out = RouteAChannels.r6_authority_transition(p)
  })

  private val states = Enum(7)
  private val StateCollect = states(0)
  private val StateAllocate = states(1)
  private val StateAwaitAllocation = states(2)
  private val StateClaim = states(3)
  private val StateAwaitClaimAck = states(4)
  private val StateRelay = states(5)
  private val StateDone = states(6)
  private val MemberCount = 64
  private val ordinalWidth = RouteAAnchorWidths.P3ValidRecordsWidth

  val state = RegInit(StateCollect)
  val present = RegInit(0.U(MemberCount.W))
  val groupLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val groupHead = Reg(UInt(RouteAAnchorWidths.KvHeadWidth.W))
  val groupTag = Reg(UInt(p.transactionGroupTagWidth.W))
  val groupValidRecords = Reg(UInt(ordinalWidth.W))
  val members = Reg(Vec(MemberCount, new AdmissionContext(p)))
  val authorities = Reg(Vec(MemberCount, new R6AuthorityTransition(p)))
  val allocatedPageRef = Reg(new PageRef)
  val allocatedRequiresTailLink = RegInit(false.B)
  val relayOrdinal = RegInit(0.U(ordinalWidth.W))

  val context = io.r6_admission_context_in.bits
  val authority = io.r6_authority_in.bits
  val contextCoordinate = context.logical_position * 288.U + context.layer * 8.U + context.kv_head
  val ordinalInRange = context.group_member_ordinal < context.group_valid_records &&
    context.group_valid_records =/= 0.U && context.group_valid_records <= MemberCount.U
  val ordinalMask = (1.U(MemberCount.W) << context.group_member_ordinal(5, 0))(MemberCount - 1, 0)
  val firstMember = !present.orR
  val groupMatches = groupLayer === context.layer && groupHead === context.kv_head &&
    groupTag === context.transaction_group_tag && groupValidRecords === context.group_valid_records
  val authorityMatches = authority.entry_id === context.entry_id &&
    authority.from_authority === RouteAAuthorityStateCode.Hot.U &&
    authority.to_authority === RouteAAuthorityStateCode.Pending.U &&
    authority.transaction_group_tag === context.transaction_group_tag
  val acceptedMember = state === StateCollect && ordinalInRange && authorityMatches &&
    context.entry_id === contextCoordinate && (firstMember || groupMatches) && (present & ordinalMask) === 0.U

  // R6 emits these as two independent decoupled channels, but the frozen
  // retained admission contract permits only an atomic pair at this ingress.
  io.r6_admission_context_in.ready := acceptedMember && io.r6_authority_in.valid
  io.r6_authority_in.ready := acceptedMember && io.r6_admission_context_in.valid
  when(io.r6_admission_context_in.fire) {
    assert(io.r6_authority_in.fire)
    when(firstMember) {
      groupLayer := context.layer
      groupHead := context.kv_head
      groupTag := context.transaction_group_tag
      groupValidRecords := context.group_valid_records
    }
    val nextPresent = present | ordinalMask
    present := nextPresent
    members(context.group_member_ordinal(5, 0)) := context
    authorities(context.group_member_ordinal(5, 0)) := authority
    when(PopCount(nextPresent) === context.group_valid_records) {
      state := StateAllocate
    }
  }
  when(io.r6_authority_in.fire) { assert(io.r6_admission_context_in.fire) }

  io.r5_allocation_req.valid := state === StateAllocate
  io.r5_allocation_req.bits.layer := groupLayer
  io.r5_allocation_req.bits.kv_head := groupHead
  io.r5_allocation_req.bits.valid_records := groupValidRecords
  io.r5_allocation_req.bits.transaction_group_tag := groupTag
  when(io.r5_allocation_req.fire) { state := StateAwaitAllocation }

  val allocation = io.r5_allocation_rsp_in.bits
  val allocationMatches = state === StateAwaitAllocation && allocation.layer === groupLayer &&
    allocation.kv_head === groupHead && allocation.transaction_group_tag === groupTag
  io.r5_allocation_rsp_in.ready := allocationMatches
  when(io.r5_allocation_rsp_in.fire) {
    allocatedPageRef := allocation.page_ref
    allocatedRequiresTailLink := allocation.requires_tail_link
    state := StateClaim
  }

  io.r3_p3_claim.valid := state === StateClaim
  io.r3_p3_claim.bits.layer := groupLayer
  io.r3_p3_claim.bits.kv_head := groupHead
  io.r3_p3_claim.bits.owner := 0.U
  io.r3_p3_claim.bits.page_ref := allocatedPageRef
  io.r3_p3_claim.bits.valid_records := groupValidRecords
  io.r3_p3_claim.bits.requires_tail_link := allocatedRequiresTailLink
  io.r3_p3_claim.bits.transaction_group_tag := groupTag
  when(io.r3_p3_claim.fire) { state := StateAwaitClaimAck }

  // P3ClaimAck deliberately contains only layer and stage generation.  The
  // one-active-group anchor makes layer equality sufficient to associate this
  // acknowledgement locally; the adapter never reconstructs a group tag.
  val claimAck = io.r3_p3_claim_ack_in.bits
  val claimAckMatches = state === StateAwaitClaimAck && claimAck.layer === groupLayer
  io.r3_p3_claim_ack_in.ready := claimAckMatches
  when(io.r3_p3_claim_ack_in.fire) {
    relayOrdinal := 0.U
    state := StateRelay
  }

  val relayMember = members(relayOrdinal(5, 0))
  val relayAuthority = authorities(relayOrdinal(5, 0))
  val relayActive = state === StateRelay && relayOrdinal < groupValidRecords
  io.r3_admission_context_out.valid := relayActive
  io.r3_admission_context_out.bits := relayMember
  io.r3_admission_authority_out.valid := relayActive
  io.r3_admission_authority_out.bits := relayAuthority
  when(io.r3_admission_context_out.fire || io.r3_admission_authority_out.fire) {
    // The frozen R3 join makes the two fires simultaneous.  This assertion
    // prevents a future alternate consumer from silently accepting one half.
    assert(io.r3_admission_context_out.fire && io.r3_admission_authority_out.fire)
    when(relayOrdinal + 1.U === groupValidRecords) {
      state := StateDone
    }.otherwise {
      relayOrdinal := relayOrdinal + 1.U
    }
  }

  when(io.r3_p3_claim.valid) {
    assert(io.r3_p3_claim.bits.owner === 0.U)
    assert(io.r3_p3_claim.bits.valid_records =/= 0.U && io.r3_p3_claim.bits.valid_records <= MemberCount.U)
  }
  when(io.r3_admission_context_out.valid) {
    assert(io.r3_admission_authority_out.valid)
    assert(relayMember.group_member_ordinal === relayOrdinal)
    assert(relayMember.transaction_group_tag === groupTag)
    assert(relayAuthority.entry_id === relayMember.entry_id)
    assert(relayAuthority.from_authority === RouteAAuthorityStateCode.Hot.U)
    assert(relayAuthority.to_authority === RouteAAuthorityStateCode.Pending.U)
  }

  val heldAllocation = RegEnable(io.r5_allocation_req.bits, io.r5_allocation_req.valid && !io.r5_allocation_req.ready)
  when(RegNext(io.r5_allocation_req.valid && !io.r5_allocation_req.ready, false.B)) {
    assert(io.r5_allocation_req.bits.asUInt === heldAllocation.asUInt)
  }
  val heldClaim = RegEnable(io.r3_p3_claim.bits, io.r3_p3_claim.valid && !io.r3_p3_claim.ready)
  when(RegNext(io.r3_p3_claim.valid && !io.r3_p3_claim.ready, false.B)) {
    assert(io.r3_p3_claim.bits.asUInt === heldClaim.asUInt)
  }
  val heldRelayContext = RegEnable(io.r3_admission_context_out.bits,
    io.r3_admission_context_out.valid && !io.r3_admission_context_out.ready)
  when(RegNext(io.r3_admission_context_out.valid && !io.r3_admission_context_out.ready, false.B)) {
    assert(io.r3_admission_context_out.bits.asUInt === heldRelayContext.asUInt)
  }
}

/** RTL1.4 direct-pending control only; no pending page/buffer or K/V storage. */
final class RouteADirectPendingEndpointV1(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_direct_pending_endpoint_v1"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val pending_source_open_in = Flipped(RouteAChannels.direct_pending_open(p))
    val direct_pending_record_terminal_in = Flipped(RouteAChannels.direct_pending_record_terminal(p))
    val gqa_consumer_commit_in = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val direct_release_out = RouteAChannels.source_release(p)
    val direct_observe_generation = Output(UInt(p.sourceGenerationWidth.W))
    val direct_observe_active = Output(Bool())
    val component_status_out = RouteAChannels.component_status(p)
  })

  val initialized = RegInit(false.B)
  when(io.mem_init_done) { initialized := true.B }
  val active = RegInit(false.B)
  val endpointGeneration = RegInit(0.U(p.sourceGenerationWidth.W))
  val identity = Reg(new TransactionIdentity)
  val expectedOrdinal = RegInit(0.U(RouteAAnchorWidths.LogicalPositionWidth.W))
  val deliverable = RegInit(false.B)
  val sourceClosed = RegInit(false.B)
  val faulted = RegInit(false.B)
  val consumerMask = RegInit(0.U(4.W))

  val open = io.pending_source_open_in.bits
  io.pending_source_open_in.ready := initialized && !active
  when(io.pending_source_open_in.fire) {
    active := true.B
    endpointGeneration := endpointGeneration + 1.U
    identity := open.transaction_identity
    expectedOrdinal := 0.U
    deliverable := false.B
    sourceClosed := false.B
    faulted := false.B
    consumerMask := 0.U
  }

  val record = io.direct_pending_record_terminal_in.bits
  val recordMatches = initialized && active && !faulted && !sourceClosed &&
    endpointGeneration === record.endpoint_generation && identity.asUInt === record.transaction_identity.asUInt
  val recordOk = record.status === p.coreMemoryOkStatusCode.U
  val recordFault = record.status === p.coreMemoryFaultStatusCode.U
  val emptyLegal = !record.explicit_empty || (record.ordinal === 0.U && record.last)
  io.direct_pending_record_terminal_in.ready := recordMatches &&
    (recordFault || (recordOk && record.ordinal === expectedOrdinal && emptyLegal))
  when(io.direct_pending_record_terminal_in.fire) {
    when(recordFault) {
      faulted := true.B
    }.otherwise {
      expectedOrdinal := expectedOrdinal + 1.U
      when(!deliverable) {
        deliverable := true.B
        consumerMask := "b1111".U
      }
      when(record.last) { sourceClosed := true.B }
    }
  }

  val consumerCommit = io.gqa_consumer_commit_in.bits
  val commitBit = (1.U(4.W) << consumerCommit.consumer_id)(3, 0)
  val commitMatches = initialized && active && deliverable && !faulted &&
    consumerCommit.source_instance.source_kind === RouteASourceKind.Pending.U &&
    consumerCommit.source_instance.instance_coordinate === 0.U &&
    consumerCommit.source_instance.generation === endpointGeneration && identity.asUInt === consumerCommit.transaction_identity.asUInt &&
    consumerCommit.consumer_id < 4.U && (consumerMask & commitBit) =/= 0.U
  io.gqa_consumer_commit_in.ready := commitMatches
  when(io.gqa_consumer_commit_in.fire) {
    consumerMask := consumerMask & ~commitBit
  }

  val releaseEligible = active && deliverable && sourceClosed && !faulted && consumerMask === 0.U
  io.direct_release_out.valid := releaseEligible
  io.direct_release_out.bits.transaction_identity := identity
  io.direct_release_out.bits.source_instance.source_kind := RouteASourceKind.Pending.U
  io.direct_release_out.bits.source_instance.instance_coordinate := 0.U
  io.direct_release_out.bits.source_instance.generation := endpointGeneration
  when(io.direct_release_out.fire) {
    active := false.B
    deliverable := false.B
    sourceClosed := false.B
    consumerMask := 0.U
  }

  when(io.direct_release_out.valid) {
    assert(sourceClosed && consumerMask === 0.U && !faulted)
  }
  val releaseStalled = io.direct_release_out.valid && !io.direct_release_out.ready
  val heldRelease = RegEnable(io.direct_release_out.bits, releaseStalled)
  when(RegNext(releaseStalled, false.B)) {
    assert(io.direct_release_out.bits.asUInt === heldRelease.asUInt)
  }

  io.direct_observe_generation := endpointGeneration
  io.direct_observe_active := active
  io.component_status_out.valid := initialized && io.drain_collection_enable && !active
  io.component_status_out.bits.acknowledgement_name := p.r6.directPendingDrainedStatusCode.U
  io.component_status_out.bits.asserted := true.B
}

/**
  * Functional reference endpoint for R3's private M2 protocol carriers.
  *
  * It reflects only identities that R3 has already issued and returns an OK
  * member completion.  It is deliberately replaceable: this is neither an M2
  * macro, a port count, a service-rate model, nor a physical timing contract.
  */
final class RouteAM2ReferenceProtocolProvider(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_m2_reference_protocol_provider"

  val io = IO(new Bundle {
    val member_request_in = Flipped(RouteAChannels.m2_group_member_req(p))
    val member_response_out = RouteAChannels.m2_group_member_rsp(p)
    val publication_candidate_in = Flipped(RouteAChannels.metadata_publish_req(p))
    val publication_request_out = RouteAChannels.metadata_publish_req(p)
  })

  val memberPending = RegInit(false.B)
  val memberRequest = Reg(new M2GroupMemberRequest(p))
  io.member_request_in.ready := !memberPending
  when(io.member_request_in.fire) {
    memberPending := true.B
    memberRequest := io.member_request_in.bits
  }
  io.member_response_out.valid := memberPending
  io.member_response_out.bits.layer := memberRequest.layer
  io.member_response_out.bits.stage_generation := memberRequest.stage_generation
  io.member_response_out.bits.transaction_group_tag := memberRequest.transaction_group_tag
  io.member_response_out.bits.member := memberRequest.member
  io.member_response_out.bits.status := p.coreMemoryOkStatusCode.U
  when(io.member_response_out.fire) { memberPending := false.B }

  val publicationPending = RegInit(false.B)
  val publicationCandidate = Reg(new MetadataPublishRequest(p))
  io.publication_candidate_in.ready := !publicationPending
  when(io.publication_candidate_in.fire) {
    publicationPending := true.B
    publicationCandidate := io.publication_candidate_in.bits
  }
  io.publication_request_out.valid := publicationPending
  io.publication_request_out.bits := publicationCandidate
  when(io.publication_request_out.fire) { publicationPending := false.B }

  when(io.member_response_out.valid && !io.member_response_out.ready) {
    assert(io.member_response_out.bits.layer === memberRequest.layer)
    assert(io.member_response_out.bits.stage_generation === memberRequest.stage_generation)
    assert(io.member_response_out.bits.transaction_group_tag === memberRequest.transaction_group_tag)
    assert(io.member_response_out.bits.member === memberRequest.member)
  }
  when(io.publication_request_out.valid && !io.publication_request_out.ready) {
    assert(io.publication_request_out.bits.asUInt === publicationCandidate.asUInt)
  }
}

/** RTL1.3 R3 control state: no P3 payload macro, M2 macro, or HBM controller. */
final class RouteAM2P3Wrapper(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_m2_p3_wrapper"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val p3_claim_in = Flipped(RouteAChannels.p3_claim(p))
    val p3_claim_ack = RouteAChannels.p3_claim_ack(p)
    val admission_context_in = Flipped(RouteAChannels.admission_context(p))
    val admission_authority_in = Flipped(RouteAChannels.r6_authority_transition(p))
    val authority_transition_out = RouteAChannels.r6_authority_transition(p)
    val publication_commit_observation = RouteAChannels.publication_commit_observation(p)
    val publication_member_observation = RouteAChannels.publication_member_observation(p)
    val p3_pending_fragment_in = Flipped(RouteAChannels.p3_pending_fragment(p))
    val p3_sidecar_bind_in = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val p3_packed_write_issue_in = Flipped(RouteAChannels.p3_packed_write_issue(p))
    val p3_packed_write_terminal_in = Flipped(RouteAChannels.p3_packed_write_terminal(p))
    // RTL2.1b: the R3-owned functional P3 backing is the sole producer of
    // its packed-write candidate. R2/R1 remain the unique transport path.
    val p3_packed_write_candidate_out = RouteAChannels.source_candidate(p)
    val p3_packed_write_delivery_in = Flipped(RouteAChannels.source_delivery(p))
    val p3_payload_durable_out = RouteAChannels.p3_payload_durable(p)
    val descriptor_durability_prerequisite_in = Flipped(RouteAChannels.descriptor_durability_prerequisite(p))
    val m2_group_member_req_out = RouteAChannels.m2_group_member_req(p)
    val m2_group_member_rsp_in = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val p3_observe_layer = Input(UInt(RouteAAnchorWidths.LayerWidth.W))
    val p3_observe_state = Output(UInt(RouteAAnchorWidths.P3StateWidth.W))
    val p3_observe_generation = Output(UInt(p.p3StageGenerationWidth.W))
    val m2_publish_candidate_out = RouteAChannels.metadata_publish_req(p)
    val m2_publish_req_in = Flipped(RouteAChannels.metadata_publish_req(p))
    val metadata_publish_visibility_apply = RouteAChannels.metadata_publish_visibility(p)
    val metadata_publish_visibility_ack_in = Flipped(RouteAChannels.metadata_publish_visibility_ack)
    val m2_publish_ack = RouteAChannels.metadata_publish_ack(p)
    val component_status_out = RouteAChannels.component_status(p)
  })

  private val stages = 36
  private val StateEmpty = 0.U(RouteAAnchorWidths.P3StateWidth.W)
  private val StateReserved = 1.U(RouteAAnchorWidths.P3StateWidth.W)
  private val StateFilling = 2.U(RouteAAnchorWidths.P3StateWidth.W)
  private val StateComplete = 3.U(RouteAAnchorWidths.P3StateWidth.W)
  private val StateWriteIssued = 4.U(RouteAAnchorWidths.P3StateWidth.W)
  private val StateDurable = 5.U(RouteAAnchorWidths.P3StateWidth.W)
  private val StateFaulted = 6.U(RouteAAnchorWidths.P3StateWidth.W)

  val initialized = RegInit(false.B)
  when(io.mem_init_done) { initialized := true.B }
  val initStatusReported = RegInit(false.B)
  val stageState = RegInit(VecInit(Seq.fill(stages)(StateEmpty)))
  val stageGeneration = RegInit(VecInit(Seq.fill(stages)(0.U(p.p3StageGenerationWidth.W))))
  val stageValidRecords = Reg(Vec(stages, UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)))
  val stageFragmentNext = RegInit(VecInit(Seq.fill(stages)(0.U(10.W))))
  val stageSidecarNext = RegInit(VecInit(Seq.fill(stages)(0.U(RouteAAnchorWidths.P3ValidRecordsWidth.W))))
  val stagePageRef = Reg(Vec(stages, new PageRef))
  val stageHead = Reg(Vec(stages, UInt(RouteAAnchorWidths.KvHeadWidth.W)))
  val stageTag = Reg(Vec(stages, UInt(p.transactionGroupTagWidth.W)))
  val stageM2Members = RegInit(VecInit(Seq.fill(stages)(0.U(2.W))))
  val stageDescriptorRequiredMask = Reg(Vec(stages, UInt(2.W)))
  // Replaceable functional/reference backing for the fixed logical P3
  // envelope: 64 records x 8 ordered 64-B fragments per layer, plus the
  // 8-B logical-position sidecar. This does not choose an SRAM macro, port
  // count, clock schedule, or physical HBM representation.
  // Flat indexing retains the exact 36 x 512 and 36 x 64 logical capacities
  // while deliberately leaving the future macro/port organization replaceable.
  val stagePayload = Mem(stages * 512, UInt(RouteAAnchorWidths.CoreDataWidth.W))
  val stageSidecar = Mem(stages * 64, UInt(64.W))
  private def payloadStoreIndex(layer: UInt, fragment: UInt): UInt = layer * 512.U + fragment
  private def sidecarStoreIndex(layer: UInt, ordinal: UInt): UInt = layer * 64.U + ordinal
  val stageDescriptorPrerequisite = RegInit(VecInit(Seq.fill(stages)(false.B)))
  // The following is a logical, per-record association ledger.  It contains
  // sidecar/payload references only, never K/V data or authoritative residency.
  val membershipPresent = RegInit(VecInit(Seq.fill(stages)(0.U(64.W))))
  val membershipEntries = Reg(Vec(stages, Vec(64, new AdmissionContext(p))))
  val observationActive = RegInit(VecInit(Seq.fill(stages)(false.B)))
  val observationCommitSent = RegInit(VecInit(Seq.fill(stages)(false.B)))
  val observationMemberOrdinal = RegInit(VecInit(Seq.fill(stages)(0.U(RouteAAnchorWidths.P3ValidRecordsWidth.W))))
  val observationMemberSent = RegInit(VecInit(Seq.fill(stages)(false.B)))
  val observationAuthoritySent = RegInit(VecInit(Seq.fill(stages)(false.B)))

  private val WriteIdle = 0.U(2.W)
  private val WriteRequest = 1.U(2.W)
  private val WriteData = 2.U(2.W)
  private val WriteAwaitTerminal = 3.U(2.W)
  val packedWriteState = RegInit(WriteIdle)
  val packedWriteLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val packedWriteFragment = RegInit(0.U(RouteAAnchorWidths.P3FragmentIndexWidth.W))
  val packedWriteIdentity = Reg(new TransactionIdentity)
  val packedWriteSequence = RegInit(0.U((RouteAAnchorWidths.RequestIdWidth + RouteAAnchorWidths.IncarnationWidth).W))
  val payloadDurablePending = RegInit(VecInit(Seq.fill(stages)(false.B)))

  val claimAckValid = RegInit(false.B)
  val claimAckLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val claimAckGeneration = Reg(UInt(p.p3StageGenerationWidth.W))
  io.p3_claim_ack.valid := claimAckValid
  io.p3_claim_ack.bits.layer := claimAckLayer
  io.p3_claim_ack.bits.stage_generation := claimAckGeneration
  when(io.p3_claim_ack.fire) { claimAckValid := false.B }

  val claim = io.p3_claim_in.bits
  val claimLayer = claim.layer
  val validClaimRecords = claim.valid_records =/= 0.U && claim.valid_records <= 64.U
  io.p3_claim_in.ready := initialized && !claimAckValid && validClaimRecords &&
    stageState(claimLayer) === StateEmpty && !observationActive(claimLayer)
  when(io.p3_claim_in.fire) {
    val nextGeneration = stageGeneration(claimLayer) + 1.U
    stageGeneration(claimLayer) := nextGeneration
    stageState(claimLayer) := StateReserved
    stageValidRecords(claimLayer) := claim.valid_records
    stageFragmentNext(claimLayer) := 0.U
    stageSidecarNext(claimLayer) := 0.U
    stagePageRef(claimLayer) := claim.page_ref
    stageHead(claimLayer) := claim.kv_head
    stageTag(claimLayer) := claim.transaction_group_tag
    stageM2Members(claimLayer) := 0.U
    stageDescriptorRequiredMask(claimLayer) := Mux(claim.requires_tail_link, 3.U, 1.U)
    stageDescriptorPrerequisite(claimLayer) := false.B
    payloadDurablePending(claimLayer) := false.B
    membershipPresent(claimLayer) := 0.U
    claimAckValid := true.B
    claimAckLayer := claimLayer
    claimAckGeneration := nextGeneration
  }

  // A retained maturity may enter the R3 ledger only together with its exact
  // hot->pending transition.  The ready signals form one lossless join: either
  // both immutable facts are accepted or neither is.  This has no payload path.
  val admission = io.admission_context_in.bits
  val admissionLayer = admission.layer
  val admissionAuthority = io.admission_authority_in.bits
  val admissionCoordinate = admission.logical_position * 288.U + admission.layer * 8.U + admission.kv_head
  val admissionOrdinalMask = 1.U(64.W) << admission.group_member_ordinal
  val admissionAuthorityMatches = admissionAuthority.entry_id === admission.entry_id &&
    admissionAuthority.from_authority === RouteAAuthorityStateCode.Hot.U &&
    admissionAuthority.to_authority === RouteAAuthorityStateCode.Pending.U &&
    admissionAuthority.transaction_group_tag === admission.transaction_group_tag
  val admissionStageMatches = initialized && !observationActive(admissionLayer) &&
    (stageState(admissionLayer) === StateReserved || stageState(admissionLayer) === StateFilling ||
      stageState(admissionLayer) === StateComplete || stageState(admissionLayer) === StateWriteIssued ||
      stageState(admissionLayer) === StateDurable) &&
    stageHead(admissionLayer) === admission.kv_head &&
    stageTag(admissionLayer) === admission.transaction_group_tag &&
    stageValidRecords(admissionLayer) === admission.group_valid_records &&
    admission.group_valid_records =/= 0.U && admission.group_valid_records <= 64.U &&
    admission.group_member_ordinal < admission.group_valid_records &&
    admission.entry_id === admissionCoordinate &&
    (membershipPresent(admissionLayer) & admissionOrdinalMask) === 0.U
  val admissionJoinReady = admissionStageMatches && admissionAuthorityMatches
  io.admission_context_in.ready := admissionJoinReady && io.admission_authority_in.valid
  io.admission_authority_in.ready := admissionJoinReady && io.admission_context_in.valid
  when(io.admission_context_in.fire) {
    assert(io.admission_authority_in.fire)
    membershipPresent(admissionLayer) := membershipPresent(admissionLayer) | admissionOrdinalMask
    membershipEntries(admissionLayer)(admission.group_member_ordinal(5, 0)) := admission
  }

  def expectedFragments(layer: UInt): UInt = Cat(stageValidRecords(layer), 0.U(3.W))
  val fragment = io.p3_pending_fragment_in.bits
  val fragmentLayer = fragment.layer
  val membershipCompleteForFragment = PopCount(membershipPresent(fragmentLayer)) === stageValidRecords(fragmentLayer)
  val fragmentRecordOrdinal = fragment.fragment_index(8, 3)
  val fragmentPayloadMatches = membershipCompleteForFragment &&
    membershipEntries(fragmentLayer)(fragmentRecordOrdinal).payload_ref === fragment.payload_ref
  val fragmentMatches = initialized &&
    (stageState(fragmentLayer) === StateReserved || stageState(fragmentLayer) === StateFilling) &&
    stageGeneration(fragmentLayer) === fragment.stage_generation && fragmentPayloadMatches
  val fragmentExpected = expectedFragments(fragmentLayer)
  val fragmentOrdinalOk = stageFragmentNext(fragmentLayer) < fragmentExpected &&
    fragment.fragment_index === stageFragmentNext(fragmentLayer)(8, 0)
  val fragmentLastExpected = stageFragmentNext(fragmentLayer) + 1.U === fragmentExpected
  val fragmentOk = fragment.status === p.coreMemoryOkStatusCode.U
  val fragmentFault = fragment.status === p.coreMemoryFaultStatusCode.U
  io.p3_pending_fragment_in.ready := fragmentMatches &&
    ((fragmentOk && fragmentOrdinalOk && fragment.last === fragmentLastExpected) || fragmentFault)
  when(io.p3_pending_fragment_in.fire) {
    when(fragmentFault) {
      stageState(fragmentLayer) := StateFaulted
    }.otherwise {
      val nextFragment = stageFragmentNext(fragmentLayer) + 1.U
      stagePayload.write(payloadStoreIndex(fragmentLayer, fragment.fragment_index), fragment.data)
      stageFragmentNext(fragmentLayer) := nextFragment
      when(stageState(fragmentLayer) === StateReserved) { stageState(fragmentLayer) := StateFilling }
      when(fragment.last && stageSidecarNext(fragmentLayer) === stageValidRecords(fragmentLayer)) {
        stageState(fragmentLayer) := StateComplete
      }
    }
  }

  val sidecar = io.p3_sidecar_bind_in.bits
  val sidecarLayer = sidecar.layer
  val sidecarOrdinal = sidecar.record_ordinal(5, 0)
  val sidecarPayloadMatches = membershipPresent(sidecarLayer)(sidecarOrdinal) &&
    membershipEntries(sidecarLayer)(sidecarOrdinal).payload_ref === sidecar.payload_ref &&
    membershipEntries(sidecarLayer)(sidecarOrdinal).logical_position === sidecar.logical_position
  val sidecarMatches = initialized &&
    (stageState(sidecarLayer) === StateReserved || stageState(sidecarLayer) === StateFilling) &&
    stageGeneration(sidecarLayer) === sidecar.stage_generation &&
    stageSidecarNext(sidecarLayer) < stageValidRecords(sidecarLayer) &&
    sidecar.record_ordinal === stageSidecarNext(sidecarLayer) && sidecarPayloadMatches
  io.p3_sidecar_bind_in.ready := sidecarMatches
  when(io.p3_sidecar_bind_in.fire) {
    val nextSidecar = stageSidecarNext(sidecarLayer) + 1.U
    stageSidecar.write(sidecarStoreIndex(sidecarLayer, sidecarOrdinal), sidecar.logical_position)
    stageSidecarNext(sidecarLayer) := nextSidecar
    when(stageFragmentNext(sidecarLayer) === expectedFragments(sidecarLayer) && nextSidecar === stageValidRecords(sidecarLayer)) {
      stageState(sidecarLayer) := StateComplete
    }
  }

  val writeIssue = io.p3_packed_write_issue_in.bits
  val issueLayer = writeIssue.layer
  io.p3_packed_write_issue_in.ready := initialized && stageState(issueLayer) === StateComplete &&
    stageGeneration(issueLayer) === writeIssue.stage_generation &&
    stageTag(issueLayer) === writeIssue.transaction_group_tag
  when(io.p3_packed_write_issue_in.fire) { stageState(issueLayer) := StateWriteIssued }

  val writeTerminal = io.p3_packed_write_terminal_in.bits
  val writeLayer = writeTerminal.layer
  val writeMatches = initialized && stageState(writeLayer) === StateWriteIssued &&
    stageGeneration(writeLayer) === writeTerminal.stage_generation &&
    stageTag(writeLayer) === writeTerminal.transaction_group_tag
  val writeOk = writeTerminal.status === p.coreMemoryOkStatusCode.U && writeTerminal.r1_payload_durable
  val writeFault = writeTerminal.status === p.coreMemoryFaultStatusCode.U
  io.p3_packed_write_terminal_in.ready := writeMatches && (writeOk || writeFault)
  when(io.p3_packed_write_terminal_in.fire) {
    stageState(writeLayer) := Mux(writeFault, StateFaulted, StateDurable)
    when(!writeFault) { payloadDurablePending(writeLayer) := true.B }
  }

  // One R3-local functional write flow serializes the pre-existing one-packer
  // anchor. It is not a new global scheduler or a memory service-rate claim.
  val packedWriteWidthSupported = (p.coreMemoryFragmentCountWidth >= 10 && p.coreMemoryFragmentIndexWidth >= 9).B
  val completeStages = VecInit((0 until stages).map(layer => stageState(layer) === StateComplete))
  when(packedWriteState === WriteIdle && packedWriteWidthSupported && completeStages.asUInt.orR) {
    packedWriteLayer := PriorityEncoder(completeStages)
    packedWriteFragment := 0.U
    packedWriteIdentity.request_id := packedWriteSequence(RouteAAnchorWidths.RequestIdWidth - 1, 0)
    packedWriteIdentity.incarnation := packedWriteSequence(RouteAAnchorWidths.RequestIdWidth + RouteAAnchorWidths.IncarnationWidth - 1, RouteAAnchorWidths.RequestIdWidth)
    packedWriteState := WriteRequest
  }
  val packedWriteExpected = expectedFragments(packedWriteLayer)
  val packedWriteEligibility = (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.FifoPredecessor) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.Ownership) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.SourceCredit) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.PageAllocated) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.P3StageComplete) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.P3StageOwned)
  io.p3_packed_write_candidate_out.valid := packedWriteWidthSupported &&
    (packedWriteState === WriteRequest || packedWriteState === WriteData)
  io.p3_packed_write_candidate_out.bits.candidate_class := p.r2PackWriteClassCode.U
  io.p3_packed_write_candidate_out.bits.arrival_ordinal := packedWriteSequence
  io.p3_packed_write_candidate_out.bits.candidate_id := packedWriteSequence
  io.p3_packed_write_candidate_out.bits.eligibility_snapshot := packedWriteEligibility
  io.p3_packed_write_candidate_out.bits.delivery_context_ref := RouteARTL2WriteDeliveryContext.R3PackedWrite.U
  io.p3_packed_write_candidate_out.bits.r1_request.transaction_identity := packedWriteIdentity
  io.p3_packed_write_candidate_out.bits.r1_request.request_kind := Mux(
    packedWriteState === WriteRequest, p.coreMemoryWriteRequestCode.U, p.coreMemoryWriteDataCode.U,
  )
  io.p3_packed_write_candidate_out.bits.r1_request.destination := 0.U
  // This is the R5-selected logical page payload offset handle (page_id *
  // 33,280 B), truncated only by the still-parameterized opaque R1 handle.
  io.p3_packed_write_candidate_out.bits.r1_request.address_ref := stagePageRef(packedWriteLayer).page_id * 33280.U
  io.p3_packed_write_candidate_out.bits.r1_request.expected_fragment_count := packedWriteExpected
  io.p3_packed_write_candidate_out.bits.r1_request.fragment_index := packedWriteFragment
  io.p3_packed_write_candidate_out.bits.r1_request.last := packedWriteFragment + 1.U === packedWriteExpected
  io.p3_packed_write_candidate_out.bits.r1_request.data := Mux(
    packedWriteState === WriteData, stagePayload.read(payloadStoreIndex(packedWriteLayer, packedWriteFragment)), 0.U,
  )
  when(io.p3_packed_write_candidate_out.fire) {
    when(packedWriteState === WriteRequest) {
      stageState(packedWriteLayer) := StateWriteIssued
      packedWriteState := WriteData
    }.otherwise {
      when(packedWriteFragment + 1.U === packedWriteExpected) {
        packedWriteState := WriteAwaitTerminal
      }.otherwise {
        packedWriteFragment := packedWriteFragment + 1.U
      }
    }
  }

  val packedWriteDelivery = io.p3_packed_write_delivery_in.bits
  val packedWriteDeliveryMatches = packedWriteState === WriteAwaitTerminal &&
    packedWriteDelivery.candidate_class === p.r2PackWriteClassCode.U &&
    packedWriteDelivery.candidate_id === packedWriteSequence &&
    packedWriteDelivery.r1_response.transaction_identity.asUInt === packedWriteIdentity.asUInt &&
    packedWriteDelivery.r1_response.last
  val packedWriteDeliveryOk = packedWriteDelivery.r1_response.status === p.coreMemoryOkStatusCode.U
  val packedWriteDeliveryFault = packedWriteDelivery.r1_response.status === p.coreMemoryFaultStatusCode.U
  io.p3_packed_write_delivery_in.ready := packedWriteDeliveryMatches && (packedWriteDeliveryOk || packedWriteDeliveryFault)
  when(io.p3_packed_write_delivery_in.fire) {
    stageState(packedWriteLayer) := Mux(packedWriteDeliveryFault, StateFaulted, StateDurable)
    when(!packedWriteDeliveryFault) { payloadDurablePending(packedWriteLayer) := true.B }
    packedWriteState := WriteIdle
    packedWriteSequence := packedWriteSequence + 1.U
  }
  // A direct control-only test ingress cannot race the actual R2/R1 flow.
  when(io.p3_packed_write_issue_in.fire || io.p3_packed_write_terminal_in.fire) {
    assert(packedWriteState === WriteIdle)
  }

  val anyPayloadDurable = payloadDurablePending.asUInt.orR
  val payloadDurableLayer = PriorityEncoder(payloadDurablePending)
  io.p3_payload_durable_out.valid := anyPayloadDurable
  io.p3_payload_durable_out.bits.layer := payloadDurableLayer
  io.p3_payload_durable_out.bits.kv_head := stageHead(payloadDurableLayer)
  io.p3_payload_durable_out.bits.page_ref := stagePageRef(payloadDurableLayer)
  io.p3_payload_durable_out.bits.stage_generation := stageGeneration(payloadDurableLayer)
  io.p3_payload_durable_out.bits.transaction_group_tag := stageTag(payloadDurableLayer)
  io.p3_payload_durable_out.bits.status := p.coreMemoryOkStatusCode.U
  when(io.p3_payload_durable_out.fire) { payloadDurablePending(payloadDurableLayer) := false.B }

  val descriptorPrerequisite = io.descriptor_durability_prerequisite_in.bits
  val descriptorPrerequisiteLayer = descriptorPrerequisite.layer
  val descriptorMaskExact = descriptorPrerequisite.required_descriptor_operation_mask ===
    stageDescriptorRequiredMask(descriptorPrerequisiteLayer)
  val descriptorPrerequisiteMatches = initialized && stageState(descriptorPrerequisiteLayer) === StateDurable &&
    stageHead(descriptorPrerequisiteLayer) === descriptorPrerequisite.kv_head &&
    stagePageRef(descriptorPrerequisiteLayer).asUInt === descriptorPrerequisite.page_ref.asUInt &&
    stageTag(descriptorPrerequisiteLayer) === descriptorPrerequisite.transaction_group_tag &&
    !stageDescriptorPrerequisite(descriptorPrerequisiteLayer)
  val descriptorPrerequisiteOk = descriptorPrerequisite.status === p.coreMemoryOkStatusCode.U &&
    descriptorPrerequisite.descriptor_prepared && descriptorMaskExact &&
    descriptorPrerequisite.durable_descriptor_operation_mask === descriptorPrerequisite.required_descriptor_operation_mask
  val descriptorPrerequisiteFault = descriptorPrerequisite.status === p.coreMemoryFaultStatusCode.U
  io.descriptor_durability_prerequisite_in.ready := descriptorPrerequisiteMatches &&
    (descriptorPrerequisiteOk || descriptorPrerequisiteFault)
  when(io.descriptor_durability_prerequisite_in.fire) {
    when(descriptorPrerequisiteFault) { stageState(descriptorPrerequisiteLayer) := StateFaulted }
      .otherwise { stageDescriptorPrerequisite(descriptorPrerequisiteLayer) := true.B }
  }

  // R3 is the sole M2 group-member initiator.  A member response is accepted
  // only for the one exact request still outstanding; stale and mismatched
  // completions are therefore inert at this boundary.
  val m2MemberRequestOutstanding = RegInit(false.B)
  val m2MemberRequestLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val m2MemberRequestGeneration = Reg(UInt(p.p3StageGenerationWidth.W))
  val m2MemberRequestTag = Reg(UInt(p.transactionGroupTagWidth.W))
  val m2MemberRequestMember = Reg(UInt(1.W))
  val m2MemberEligible = VecInit((0 until stages).map { layer =>
    stageState(layer) === StateDurable && stageDescriptorPrerequisite(layer) &&
      stageM2Members(layer) =/= 3.U
  })
  val m2MemberEligibleAny = m2MemberEligible.asUInt.orR
  val m2MemberIssueLayer = PriorityEncoder(m2MemberEligible)
  io.m2_group_member_req_out.valid := initialized && !m2MemberRequestOutstanding && m2MemberEligibleAny
  io.m2_group_member_req_out.bits.layer := m2MemberIssueLayer
  io.m2_group_member_req_out.bits.stage_generation := stageGeneration(m2MemberIssueLayer)
  io.m2_group_member_req_out.bits.transaction_group_tag := stageTag(m2MemberIssueLayer)
  io.m2_group_member_req_out.bits.member := Mux(stageM2Members(m2MemberIssueLayer)(0),
    RouteAM2GroupMember.SpanOwnerRmw.U, RouteAM2GroupMember.HeadControlRmw.U)
  when(io.m2_group_member_req_out.fire) {
    m2MemberRequestOutstanding := true.B
    m2MemberRequestLayer := m2MemberIssueLayer
    m2MemberRequestGeneration := stageGeneration(m2MemberIssueLayer)
    m2MemberRequestTag := stageTag(m2MemberIssueLayer)
    m2MemberRequestMember := io.m2_group_member_req_out.bits.member
  }

  val m2Member = io.m2_group_member_rsp_in.bits
  val memberLayer = m2Member.layer
  val memberBit = (1.U(2.W) << m2Member.member)(1, 0)
  val memberMatches = initialized && m2MemberRequestOutstanding &&
    memberLayer === m2MemberRequestLayer &&
    m2Member.stage_generation === m2MemberRequestGeneration &&
    m2Member.transaction_group_tag === m2MemberRequestTag &&
    m2Member.member === m2MemberRequestMember &&
    stageState(memberLayer) === StateDurable &&
    stageGeneration(memberLayer) === m2Member.stage_generation &&
    stageTag(memberLayer) === m2Member.transaction_group_tag &&
    m2Member.member <= RouteAM2GroupMember.SpanOwnerRmw.U &&
    (stageM2Members(memberLayer) & memberBit) === 0.U
  val memberOk = m2Member.status === p.coreMemoryOkStatusCode.U
  val memberFault = m2Member.status === p.coreMemoryFaultStatusCode.U
  io.m2_group_member_rsp_in.ready := memberMatches && (memberOk || memberFault)
  when(io.m2_group_member_rsp_in.fire) {
    m2MemberRequestOutstanding := false.B
    when(memberFault) { stageState(memberLayer) := StateFaulted }
      .otherwise { stageM2Members(memberLayer) := stageM2Members(memberLayer) | memberBit }
  }

  val publicationActive = RegInit(false.B)
  val publicationAwaitingVisibilityAck = RegInit(false.B)
  val publicationLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val publicationTag = Reg(UInt(p.transactionGroupTagWidth.W))
  val publicationPageRef = Reg(new PageRef)
  // Issuing a publication candidate is separate from accepting the returned
  // M2 publication request.  The round trip makes the protocol attribution
  // explicit while retaining R3 as the only issuer of immutable coordinates.
  val publicationRequestOutstanding = RegInit(false.B)
  val publicationRequestLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val publicationRequestGeneration = Reg(UInt(p.p3StageGenerationWidth.W))
  val publicationRequestTag = Reg(UInt(p.transactionGroupTagWidth.W))
  val publicationEligible = VecInit((0 until stages).map { layer =>
    stageState(layer) === StateDurable && stageM2Members(layer) === 3.U &&
      stageDescriptorPrerequisite(layer) &&
      PopCount(membershipPresent(layer)) === stageValidRecords(layer)
  })
  val publicationEligibleAny = publicationEligible.asUInt.orR
  val publicationEligibleLayer = PriorityEncoder(publicationEligible)
  io.m2_publish_candidate_out.valid := initialized && !publicationActive &&
    !publicationRequestOutstanding && publicationEligibleAny
  io.m2_publish_candidate_out.bits.transaction_group_tag := stageTag(publicationEligibleLayer)
  io.m2_publish_candidate_out.bits.p3_layer := publicationEligibleLayer
  io.m2_publish_candidate_out.bits.p3_stage_generation := stageGeneration(publicationEligibleLayer)
  when(io.m2_publish_candidate_out.fire) {
    publicationRequestOutstanding := true.B
    publicationRequestLayer := publicationEligibleLayer
    publicationRequestGeneration := stageGeneration(publicationEligibleLayer)
    publicationRequestTag := stageTag(publicationEligibleLayer)
  }

  val publish = io.m2_publish_req_in.bits
  val membershipComplete = PopCount(membershipPresent(publish.p3_layer)) === stageValidRecords(publish.p3_layer)
  val publishPrerequisites = initialized && publicationRequestOutstanding &&
    publish.p3_layer === publicationRequestLayer &&
    publish.p3_stage_generation === publicationRequestGeneration &&
    publish.transaction_group_tag === publicationRequestTag &&
    stageState(publish.p3_layer) === StateDurable &&
    stageGeneration(publish.p3_layer) === publish.p3_stage_generation &&
    stageTag(publish.p3_layer) === publish.transaction_group_tag &&
    stageM2Members(publish.p3_layer) === 3.U && membershipComplete && stageDescriptorPrerequisite(publish.p3_layer)
  io.m2_publish_req_in.ready := !publicationActive && publishPrerequisites
  when(io.m2_publish_req_in.fire) {
    publicationRequestOutstanding := false.B
    publicationActive := true.B
    publicationAwaitingVisibilityAck := false.B
    publicationLayer := publish.p3_layer
    publicationTag := publish.transaction_group_tag
    publicationPageRef := stagePageRef(publish.p3_layer)
  }

  io.metadata_publish_visibility_apply.valid := publicationActive && !publicationAwaitingVisibilityAck
  io.metadata_publish_visibility_apply.bits.page_ref := publicationPageRef
  io.metadata_publish_visibility_apply.bits.transaction_group_tag := publicationTag
  when(io.metadata_publish_visibility_apply.fire) { publicationAwaitingVisibilityAck := true.B }

  val publishAckValid = RegInit(false.B)
  val publishAckStatus = Reg(UInt(RouteAAnchorWidths.PublicationStatusWidth.W))
  io.m2_publish_ack.valid := publishAckValid
  io.m2_publish_ack.bits.transaction_group_tag := publicationTag
  io.m2_publish_ack.bits.status := publishAckStatus
  val visibilityAckMatches = publicationActive && publicationAwaitingVisibilityAck &&
    io.metadata_publish_visibility_ack_in.bits.page_ref.asUInt === publicationPageRef.asUInt
  io.metadata_publish_visibility_ack_in.ready := visibilityAckMatches && !publishAckValid
  when(io.metadata_publish_visibility_ack_in.fire) {
    publishAckValid := true.B
    publishAckStatus := io.metadata_publish_visibility_ack_in.bits.status
  }
  when(io.m2_publish_ack.fire) {
    when(publishAckStatus === RouteAPublicationStatus.Published.U) {
      stageState(publicationLayer) := StateEmpty
      stageM2Members(publicationLayer) := 0.U
      observationActive(publicationLayer) := true.B
      observationCommitSent(publicationLayer) := false.B
      observationMemberOrdinal(publicationLayer) := 0.U
      observationMemberSent(publicationLayer) := false.B
      observationAuthoritySent(publicationLayer) := false.B
    }.otherwise {
      stageState(publicationLayer) := StateFaulted
    }
    publicationActive := false.B
    publicationAwaitingVisibilityAck := false.B
    publishAckValid := false.B
  }

  // a_metadata_publish_commit: the only visible R3 publication is held behind
  // all immutable durability/group prerequisites and the nested R5 handshake.
  when(io.metadata_publish_visibility_apply.valid) {
    assert(stageState(publicationLayer) === StateDurable)
    assert(stageM2Members(publicationLayer) === 3.U)
    assert(stageDescriptorPrerequisite(publicationLayer))
    assert(PopCount(membershipPresent(publicationLayer)) === stageValidRecords(publicationLayer))
  }
  when(io.m2_publish_ack.valid && io.m2_publish_ack.bits.status === RouteAPublicationStatus.Published.U) {
    assert(publicationAwaitingVisibilityAck)
  }

  // Publication observations report the one completed atomic boundary.  They
  // are intentionally post-commit and can be held under ready-low without
  // changing membership, page visibility, or authority linearization.
  val anyObservationActive = observationActive.asUInt.orR
  val observationLayer = PriorityEncoder(observationActive)
  val observationEntry = membershipEntries(observationLayer)(observationMemberOrdinal(observationLayer)(5, 0))
  io.publication_commit_observation.valid := anyObservationActive && !observationCommitSent(observationLayer)
  io.publication_commit_observation.bits.p3_layer := observationLayer
  io.publication_commit_observation.bits.p3_stage_generation := stageGeneration(observationLayer)
  io.publication_commit_observation.bits.page_ref := stagePageRef(observationLayer)
  io.publication_commit_observation.bits.transaction_group_tag := stageTag(observationLayer)
  io.publication_commit_observation.bits.valid_records := stageValidRecords(observationLayer)
  when(io.publication_commit_observation.fire) {
    observationCommitSent(observationLayer) := true.B
  }

  val memberObservationValid = anyObservationActive && observationCommitSent(observationLayer) &&
    observationMemberOrdinal(observationLayer) < stageValidRecords(observationLayer)
  io.publication_member_observation.valid := memberObservationValid && !observationMemberSent(observationLayer)
  io.publication_member_observation.bits.entry_id := observationEntry.entry_id
  io.publication_member_observation.bits.layer := observationEntry.layer
  io.publication_member_observation.bits.kv_head := observationEntry.kv_head
  io.publication_member_observation.bits.logical_position := observationEntry.logical_position
  io.publication_member_observation.bits.payload_ref := observationEntry.payload_ref
  io.publication_member_observation.bits.transaction_group_tag := stageTag(observationLayer)
  io.publication_member_observation.bits.group_member_ordinal := observationMemberOrdinal(observationLayer)
  io.authority_transition_out.valid := memberObservationValid && !observationAuthoritySent(observationLayer)
  io.authority_transition_out.bits.entry_id := observationEntry.entry_id
  io.authority_transition_out.bits.from_authority := RouteAAuthorityStateCode.Pending.U
  io.authority_transition_out.bits.to_authority := RouteAAuthorityStateCode.Packed.U
  io.authority_transition_out.bits.transaction_group_tag := stageTag(observationLayer)
  when(io.publication_member_observation.fire) {
    observationMemberSent(observationLayer) := true.B
  }
  when(io.authority_transition_out.fire) {
    observationAuthoritySent(observationLayer) := true.B
  }
  val memberObservationDone = observationMemberSent(observationLayer) || io.publication_member_observation.fire
  val authorityObservationDone = observationAuthoritySent(observationLayer) || io.authority_transition_out.fire
  when(memberObservationValid && memberObservationDone && authorityObservationDone) {
    val nextOrdinal = observationMemberOrdinal(observationLayer) + 1.U
    observationMemberOrdinal(observationLayer) := nextOrdinal
    observationMemberSent(observationLayer) := false.B
    observationAuthoritySent(observationLayer) := false.B
    when(nextOrdinal === stageValidRecords(observationLayer)) {
      observationActive(observationLayer) := false.B
      observationCommitSent(observationLayer) := false.B
      membershipPresent(observationLayer) := 0.U
    }
  }
  when(io.authority_transition_out.valid) {
    assert(io.authority_transition_out.bits.from_authority === RouteAAuthorityStateCode.Pending.U)
    assert(io.authority_transition_out.bits.to_authority === RouteAAuthorityStateCode.Packed.U)
  }

  io.p3_observe_state := stageState(io.p3_observe_layer)
  io.p3_observe_generation := stageGeneration(io.p3_observe_layer)
  val stagesEmpty = VecInit((0 until stages).map(stage => stageState(stage) === StateEmpty)).asUInt.andR
  val locallyDrained = stagesEmpty && !observationActive.asUInt.orR && !claimAckValid && !publicationActive &&
    !publicationAwaitingVisibilityAck && !publishAckValid
  val initStatusPending = initialized && !initStatusReported
  io.component_status_out.valid := initStatusPending ||
    (initialized && initStatusReported && io.drain_collection_enable && locallyDrained)
  io.component_status_out.bits.acknowledgement_name := Mux(
    initStatusPending,
    p.r6.m2P3InitDoneStatusCode.U,
    p.r6.r3M2P3DrainedStatusCode.U,
  )
  io.component_status_out.bits.asserted := true.B
  when(io.component_status_out.fire && initStatusPending) { initStatusReported := true.B }
}

/** RTL1.3 R5 control state; descriptor payload/HBM traffic remains on R2/R1. */
final class RouteAPageManager(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_page_manager"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val reclaim_permit_in = Flipped(RouteAChannels.reclaim_permit)
    val reclaim_candidate_out = RouteAChannels.source_candidate(p)
    val reclaim_delivery_in = Flipped(RouteAChannels.source_delivery(p))
    val reclaim_complete = Output(Bool())
    val page_allocation_req_in = Flipped(RouteAChannels.page_allocation_req(p))
    val page_allocation_rsp = RouteAChannels.page_allocation_rsp(p)
    // RTL2.1b append-maintenance producer/terminal path. It remains distinct
    // from the existing retirement invalidation carrier.
    val append_candidate_out = RouteAChannels.source_candidate(p)
    val append_delivery_in = Flipped(RouteAChannels.source_delivery(p))
    val p3_payload_durable_in = Flipped(RouteAChannels.p3_payload_durable(p))
    val descriptor_durability_prerequisite_out = RouteAChannels.descriptor_durability_prerequisite(p)
    val descriptor_maintenance_terminal_in = Flipped(RouteAChannels.descriptor_maintenance_terminal(p))
    val metadata_publish_visibility_in = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val metadata_publish_visibility_ack = RouteAChannels.metadata_publish_visibility_ack
    val component_status_out = RouteAChannels.component_status(p)
  })

  private val streamSlots = p.r5StreamSlots
  private val streamIndexWidth = math.max(1, log2Ceil(streamSlots))
  require(p.r5AllocatorEntries % 4 == 0,
    "R5 descriptor reclaim requires four 128-bit lanes per logical 64-B descriptor line")
  private val descriptorLines = p.r5AllocatorEntries / 4
  private val descriptorLineWidth = math.max(1, log2Ceil(descriptorLines))
  private val allocatorIndexWidth = math.max(1, log2Ceil(p.r5AllocatorEntries))
  private val ReclaimIdle = 0.U(2.W)
  private val ReclaimRequest = 1.U(2.W)
  private val ReclaimData = 2.U(2.W)
  private val ReclaimAwaitTerminal = 3.U(2.W)
  val initialized = RegInit(false.B)
  when(io.mem_init_done) { initialized := true.B }
  val initStatusReported = RegInit(false.B)
  val allocated = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(false.B)))
  val generations = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(0.U(RouteAAnchorWidths.PageGenerationWidth.W))))
  // Verification-only assertion shadow: it is not a descriptor cache, a
  // second allocator, or an additional authority owner. It records that a
  // previously allocated lane has crossed the one accepted durable invalidate
  // terminal before its allocator bit may remain free.
  val allocationSeen = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(false.B)))
  val durableInvalidation = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(false.B)))
  val buildActive = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildFault = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildPayloadDurable = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildPrerequisiteReported = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildLayer = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.LayerWidth.W)))
  val buildHead = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.KvHeadWidth.W)))
  val buildValidRecords = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)))
  val buildPageId = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageIdWidth.W)))
  val buildGeneration = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageGenerationWidth.W)))
  val buildTag = Reg(Vec(streamSlots, UInt(p.transactionGroupTagWidth.W)))
  val buildNewDurable = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildTailDurable = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildNeedsTail = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val visibleTailPresent = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val visibleTailId = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageIdWidth.W)))
  val visibleTailGeneration = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageGenerationWidth.W)))
  val visibilityAckPending = RegInit(false.B)
  val visibilityAckPageRef = Reg(new PageRef)
  val visibilityAckSlot = Reg(UInt(streamIndexWidth.W))
  val allocationRspValid = RegInit(false.B)
  val allocationRsp = Reg(new PageAllocationResponse(p))
  val reclaimPermitted = RegInit(false.B)
  val reclaimState = RegInit(ReclaimIdle)
  val reclaimLine = Reg(UInt(descriptorLineWidth.W))
  val reclaimSequence = RegInit(0.U(5.W))
  val reclaimFaulted = RegInit(false.B)
  // Functional/reference descriptor-entry backing. This preserves all four
  // 128-bit lanes when producing the frozen 64-B maintenance line; it is not
  // an HBM macro/cache/controller implementation or a PPA claim.
  val descriptorEntryImage = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(0.U(128.W))))
  private def allocatorIndex(pageId: UInt): UInt = pageId(allocatorIndexWidth - 1, 0)
  private val AppendIdle = 0.U(2.W)
  private val AppendRequest = 1.U(2.W)
  private val AppendData = 2.U(2.W)
  private val AppendAwaitTerminal = 3.U(2.W)
  val appendState = RegInit(AppendIdle)
  val appendSlot = Reg(UInt(streamIndexWidth.W))
  val appendKind = Reg(UInt(2.W))
  val appendIdentity = Reg(new TransactionIdentity)
  val appendSequence = RegInit(0.U((RouteAAnchorWidths.RequestIdWidth + RouteAAnchorWidths.IncarnationWidth).W))

  val lineAllocated = VecInit((0 until descriptorLines).map { line =>
    (0 until 4).map(lane => allocated(line * 4 + lane)).reduce(_ || _)
  })
  val anyAllocatedLine = lineAllocated.asUInt.orR
  val nextAllocatedLine = PriorityEncoder(lineAllocated)

  private def reclaimIdentity: TransactionIdentity = {
    val identity = Wire(new TransactionIdentity)
    identity.request_id := reclaimSequence(RouteAAnchorWidths.RequestIdWidth - 1, 0)
    identity.incarnation := reclaimSequence(4, RouteAAnchorWidths.RequestIdWidth)
    identity
  }
  private def descriptorLaneImage(lane: Int): UInt = {
    val pageIndexWide = reclaimLine * 4.U + lane.U
    val pageIndex = pageIndexWide(log2Ceil(p.r5AllocatorEntries) - 1, 0)
    val nextGeneration = Mux(allocated(pageIndex), generations(pageIndex) + 1.U, generations(pageIndex))
    // [1:0]=FREE; [51:44]=page generation; all other descriptor fields zero.
    Cat(0.U(76.W), nextGeneration, 0.U(44.W))
  }
  val reclaimDescriptorData = Cat(
    descriptorLaneImage(3), descriptorLaneImage(2), descriptorLaneImage(1), descriptorLaneImage(0),
  )
  val reclaimActive = reclaimState =/= ReclaimIdle
  val reclaimLocalSafe = !buildActive.asUInt.orR && !allocationRspValid && !visibilityAckPending

  io.reclaim_permit_in.ready := initialized && !reclaimPermitted && reclaimLocalSafe
  when(io.reclaim_permit_in.fire) {
    reclaimPermitted := true.B
  }
  when(reclaimPermitted && reclaimState === ReclaimIdle && anyAllocatedLine && !reclaimFaulted) {
    reclaimLine := nextAllocatedLine
    reclaimState := ReclaimRequest
  }

  val reclaimEligibility = (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.FifoPredecessor) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.Ownership) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.SourceCredit)
  io.reclaim_candidate_out.valid := reclaimState === ReclaimRequest || reclaimState === ReclaimData
  io.reclaim_candidate_out.bits.candidate_class := p.r2DescriptorMaintenanceClassCode.U
  io.reclaim_candidate_out.bits.arrival_ordinal := reclaimSequence
  io.reclaim_candidate_out.bits.candidate_id := reclaimSequence
  io.reclaim_candidate_out.bits.eligibility_snapshot := reclaimEligibility
  io.reclaim_candidate_out.bits.delivery_context_ref := 0.U
  io.reclaim_candidate_out.bits.r1_request.transaction_identity := reclaimIdentity
  io.reclaim_candidate_out.bits.r1_request.request_kind := Mux(
    reclaimState === ReclaimRequest,
    p.coreMemoryWriteRequestCode.U,
    p.coreMemoryWriteDataCode.U,
  )
  io.reclaim_candidate_out.bits.r1_request.destination := 0.U
  io.reclaim_candidate_out.bits.r1_request.address_ref := reclaimLine
  io.reclaim_candidate_out.bits.r1_request.expected_fragment_count := 1.U
  io.reclaim_candidate_out.bits.r1_request.fragment_index := 0.U
  io.reclaim_candidate_out.bits.r1_request.last := true.B
  io.reclaim_candidate_out.bits.r1_request.data := Mux(
    reclaimState === ReclaimData, reclaimDescriptorData, 0.U,
  )
  when(io.reclaim_candidate_out.fire) {
    when(reclaimState === ReclaimRequest) { reclaimState := ReclaimData }
      .otherwise { reclaimState := ReclaimAwaitTerminal }
  }

  val reclaimDelivery = io.reclaim_delivery_in.bits
  val reclaimDeliveryMatches = reclaimState === ReclaimAwaitTerminal &&
    reclaimDelivery.candidate_class === p.r2DescriptorMaintenanceClassCode.U &&
    reclaimDelivery.candidate_id === reclaimSequence &&
    reclaimDelivery.r1_response.transaction_identity.asUInt === reclaimIdentity.asUInt &&
    reclaimDelivery.r1_response.last
  val reclaimDeliveryStatusKnown = reclaimDelivery.r1_response.status === p.coreMemoryOkStatusCode.U ||
    reclaimDelivery.r1_response.status === p.coreMemoryFaultStatusCode.U
  io.reclaim_delivery_in.ready := reclaimDeliveryMatches && reclaimDeliveryStatusKnown
  when(io.reclaim_delivery_in.fire) {
    when(reclaimDelivery.r1_response.status === p.coreMemoryFaultStatusCode.U) {
      reclaimFaulted := true.B
    }.otherwise {
      for (line <- 0 until descriptorLines; lane <- 0 until 4) {
        when(reclaimLine === line.U && allocated(line * 4 + lane)) {
          durableInvalidation(line * 4 + lane) := true.B
          allocated(line * 4 + lane) := false.B
          generations(line * 4 + lane) := generations(line * 4 + lane) + 1.U
        }
      }
      reclaimSequence := reclaimSequence + 1.U
      reclaimState := ReclaimIdle
    }
  }
  // A fault intentionally leaves the matching line allocated and blocks final
  // retirement.  A stalled delivery leaves the candidate/line association intact.
  when(io.reclaim_delivery_in.fire && reclaimDelivery.r1_response.status === p.coreMemoryOkStatusCode.U) {
    // a_descriptor_invalidate_before_free: this is the only free/generation
    // advance site, and it is guarded by R6's existing retirement permit plus
    // the matching terminal R1 descriptor response.
    assert(reclaimDeliveryMatches)
    assert(reclaimPermitted)
    assert(lineAllocated(reclaimLine))
  }
  for (page <- 0 until p.r5AllocatorEntries) {
    when(!allocated(page) && allocationSeen(page)) {
      assert(durableInvalidation(page))
    }
    when(allocated(page)) {
      assert(!durableInvalidation(page))
    }
  }
  io.reclaim_complete := reclaimPermitted && !reclaimActive && !anyAllocatedLine && !reclaimFaulted

  def streamIndexWide(layer: UInt, head: UInt): UInt = Cat(layer, head)
  io.page_allocation_rsp.valid := allocationRspValid
  io.page_allocation_rsp.bits := allocationRsp
  when(io.page_allocation_rsp.fire) { allocationRspValid := false.B }

  val alloc = io.page_allocation_req_in.bits
  val allocStreamWide = streamIndexWide(alloc.layer, alloc.kv_head)
  val allocStream = allocStreamWide(streamIndexWidth - 1, 0)
  val allocValidRecords = alloc.valid_records =/= 0.U && alloc.valid_records <= 64.U
  val freeExists = !allocated.reduce(_ && _)
  val freeIndex = PriorityEncoder(VecInit(allocated.map(! _)))
  io.page_allocation_req_in.ready := initialized && !io.drain_collection_enable && !reclaimPermitted && !allocationRspValid && allocValidRecords &&
    allocStreamWide < streamSlots.U && !buildActive(allocStream) && freeExists
  when(io.page_allocation_req_in.fire) {
    allocated(freeIndex) := true.B
    allocationSeen(freeIndex) := true.B
    durableInvalidation(freeIndex) := false.B
    buildActive(allocStream) := true.B
    buildFault(allocStream) := false.B
    buildPayloadDurable(allocStream) := false.B
    buildPrerequisiteReported(allocStream) := false.B
    buildLayer(allocStream) := alloc.layer
    buildHead(allocStream) := alloc.kv_head
    buildValidRecords(allocStream) := alloc.valid_records
    buildPageId(allocStream) := freeIndex
    buildGeneration(allocStream) := generations(freeIndex)
    buildTag(allocStream) := alloc.transaction_group_tag
    buildNewDurable(allocStream) := false.B
    buildTailDurable(allocStream) := false.B
    buildNeedsTail(allocStream) := visibleTailPresent(allocStream)
    // ALLOCATED_UNPUBLISHED, with no successor, as the private functional
    // descriptor image. Visibility remains separately guarded by R3 commit.
    descriptorEntryImage(freeIndex) := Cat(
      0.U(76.W), generations(freeIndex), 0.U(8.W), Fill(18, 1.U(1.W)),
      alloc.valid_records, alloc.kv_head, alloc.layer, 1.U(2.W),
    )
    allocationRspValid := true.B
    allocationRsp.layer := alloc.layer
    allocationRsp.kv_head := alloc.kv_head
    allocationRsp.page_ref.page_id := freeIndex
    allocationRsp.page_ref.generation := generations(freeIndex)
    allocationRsp.requires_tail_link := visibleTailPresent(allocStream)
    allocationRsp.transaction_group_tag := alloc.transaction_group_tag
  }

  val payloadDurable = io.p3_payload_durable_in.bits
  val payloadDurableMatches = VecInit((0 until streamSlots).map { slot =>
    buildActive(slot) && !buildPayloadDurable(slot) && !buildFault(slot) &&
      buildLayer(slot) === payloadDurable.layer && buildHead(slot) === payloadDurable.kv_head &&
      buildPageId(slot) === payloadDurable.page_ref.page_id &&
      buildGeneration(slot) === payloadDurable.page_ref.generation &&
      buildTag(slot) === payloadDurable.transaction_group_tag
  })
  val payloadDurableAnyMatch = payloadDurableMatches.asUInt.orR
  val payloadDurableSlot = PriorityEncoder(payloadDurableMatches)
  val payloadDurableOk = payloadDurable.status === p.coreMemoryOkStatusCode.U
  val payloadDurableFault = payloadDurable.status === p.coreMemoryFaultStatusCode.U
  io.p3_payload_durable_in.ready := initialized && payloadDurableAnyMatch && (payloadDurableOk || payloadDurableFault)
  when(io.p3_payload_durable_in.fire) {
    when(payloadDurableFault) { buildFault(payloadDurableSlot) := true.B }
      .otherwise { buildPayloadDurable(payloadDurableSlot) := true.B }
  }

  // R5 performs only its own private descriptor-operation sequencing. The
  // global R2 FIFO/arbitration still receives a single normal candidate.
  val appendEligible = VecInit((0 until streamSlots).map { slot =>
    buildActive(slot) && buildPayloadDurable(slot) && !buildFault(slot) &&
      (!buildNewDurable(slot) || (buildNeedsTail(slot) && !buildTailDurable(slot)))
  })
  when(appendState === AppendIdle && appendEligible.asUInt.orR) {
    appendSlot := PriorityEncoder(appendEligible)
    appendKind := Mux(!buildNewDurable(PriorityEncoder(appendEligible)),
      RouteADescriptorOperationKind.NewPage.U, RouteADescriptorOperationKind.TailLink.U)
    appendIdentity.request_id := appendSequence(RouteAAnchorWidths.RequestIdWidth - 1, 0)
    appendIdentity.incarnation := appendSequence(RouteAAnchorWidths.RequestIdWidth + RouteAAnchorWidths.IncarnationWidth - 1, RouteAAnchorWidths.RequestIdWidth)
    appendState := AppendRequest
  }
  val appendSubjectPage = Mux(appendKind === RouteADescriptorOperationKind.NewPage.U,
    buildPageId(appendSlot), visibleTailId(appendSlot))
  val appendSubjectGeneration = Mux(appendKind === RouteADescriptorOperationKind.NewPage.U,
    buildGeneration(appendSlot), visibleTailGeneration(appendSlot))
  val appendDescriptorImage = Mux(
    appendKind === RouteADescriptorOperationKind.NewPage.U,
    descriptorEntryImage(allocatorIndex(buildPageId(appendSlot))),
    Cat(
      descriptorEntryImage(allocatorIndex(visibleTailId(appendSlot)))(127, 44), buildGeneration(appendSlot),
      buildPageId(appendSlot), descriptorEntryImage(allocatorIndex(visibleTailId(appendSlot)))(17, 0),
    ),
  )
  val appendLine = appendSubjectPage(RouteAAnchorWidths.PageIdWidth - 1, 2)
  def appendLineLaneImage(lane: Int): UInt = {
    val lanePage = Cat(appendLine, lane.U(2.W))
    Mux(lanePage === appendSubjectPage, appendDescriptorImage, descriptorEntryImage(allocatorIndex(lanePage)))
  }
  val appendLineData = Cat(appendLineLaneImage(3), appendLineLaneImage(2), appendLineLaneImage(1), appendLineLaneImage(0))
  val appendEligibility = (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.FifoPredecessor) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.Ownership) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.SourceCredit)
  io.append_candidate_out.valid := appendState === AppendRequest || appendState === AppendData
  io.append_candidate_out.bits.candidate_class := p.r2DescriptorMaintenanceClassCode.U
  io.append_candidate_out.bits.arrival_ordinal := appendSequence
  io.append_candidate_out.bits.candidate_id := appendSequence
  io.append_candidate_out.bits.eligibility_snapshot := appendEligibility
  io.append_candidate_out.bits.delivery_context_ref := RouteARTL2WriteDeliveryContext.R5Append.U
  io.append_candidate_out.bits.r1_request.transaction_identity := appendIdentity
  io.append_candidate_out.bits.r1_request.request_kind := Mux(
    appendState === AppendRequest, p.coreMemoryWriteRequestCode.U, p.coreMemoryWriteDataCode.U,
  )
  io.append_candidate_out.bits.r1_request.destination := 0.U
  io.append_candidate_out.bits.r1_request.address_ref := appendLine
  io.append_candidate_out.bits.r1_request.expected_fragment_count := 1.U
  io.append_candidate_out.bits.r1_request.fragment_index := 0.U
  io.append_candidate_out.bits.r1_request.last := true.B
  io.append_candidate_out.bits.r1_request.data := Mux(appendState === AppendData, appendLineData, 0.U)
  when(io.append_candidate_out.fire) {
    when(appendState === AppendRequest) { appendState := AppendData }
      .otherwise { appendState := AppendAwaitTerminal }
  }
  val appendDelivery = io.append_delivery_in.bits
  val appendDeliveryMatches = appendState === AppendAwaitTerminal &&
    appendDelivery.candidate_class === p.r2DescriptorMaintenanceClassCode.U &&
    appendDelivery.candidate_id === appendSequence &&
    appendDelivery.r1_response.transaction_identity.asUInt === appendIdentity.asUInt &&
    appendDelivery.r1_response.last
  val appendDeliveryOk = appendDelivery.r1_response.status === p.coreMemoryOkStatusCode.U
  val appendDeliveryFault = appendDelivery.r1_response.status === p.coreMemoryFaultStatusCode.U
  io.append_delivery_in.ready := appendDeliveryMatches && (appendDeliveryOk || appendDeliveryFault)
  when(io.append_delivery_in.fire) {
    when(appendDeliveryFault) {
      buildFault(appendSlot) := true.B
    }.elsewhen(appendKind === RouteADescriptorOperationKind.NewPage.U) {
      buildNewDurable(appendSlot) := true.B
      descriptorEntryImage(allocatorIndex(appendSubjectPage)) := appendDescriptorImage
    }.otherwise {
      buildTailDurable(appendSlot) := true.B
      descriptorEntryImage(allocatorIndex(appendSubjectPage)) := appendDescriptorImage
    }
    appendState := AppendIdle
    appendSequence := appendSequence + 1.U
  }

  val descriptorPrerequisiteEligible = VecInit((0 until streamSlots).map { slot =>
    buildActive(slot) && !buildPrerequisiteReported(slot) &&
      (buildFault(slot) || (buildPayloadDurable(slot) && buildNewDurable(slot) &&
        (!buildNeedsTail(slot) || buildTailDurable(slot))))
  })
  val descriptorPrerequisiteAny = descriptorPrerequisiteEligible.asUInt.orR
  val descriptorPrerequisiteSlot = PriorityEncoder(descriptorPrerequisiteEligible)
  val descriptorRequiredMask = Mux(buildNeedsTail(descriptorPrerequisiteSlot), 3.U, 1.U)
  val descriptorDurableMask = Cat(buildTailDurable(descriptorPrerequisiteSlot), buildNewDurable(descriptorPrerequisiteSlot))
  io.descriptor_durability_prerequisite_out.valid := descriptorPrerequisiteAny
  io.descriptor_durability_prerequisite_out.bits.layer := buildLayer(descriptorPrerequisiteSlot)
  io.descriptor_durability_prerequisite_out.bits.kv_head := buildHead(descriptorPrerequisiteSlot)
  io.descriptor_durability_prerequisite_out.bits.page_ref.page_id := buildPageId(descriptorPrerequisiteSlot)
  io.descriptor_durability_prerequisite_out.bits.page_ref.generation := buildGeneration(descriptorPrerequisiteSlot)
  io.descriptor_durability_prerequisite_out.bits.transaction_group_tag := buildTag(descriptorPrerequisiteSlot)
  io.descriptor_durability_prerequisite_out.bits.required_descriptor_operation_mask := descriptorRequiredMask
  io.descriptor_durability_prerequisite_out.bits.durable_descriptor_operation_mask := descriptorDurableMask
  io.descriptor_durability_prerequisite_out.bits.descriptor_prepared := !buildFault(descriptorPrerequisiteSlot)
  io.descriptor_durability_prerequisite_out.bits.status := Mux(buildFault(descriptorPrerequisiteSlot),
    p.coreMemoryFaultStatusCode.U, p.coreMemoryOkStatusCode.U)
  when(io.descriptor_durability_prerequisite_out.fire) {
    buildPrerequisiteReported(descriptorPrerequisiteSlot) := true.B
  }

  val descriptorTerminal = io.descriptor_maintenance_terminal_in.bits
  val terminalMatches = VecInit((0 until streamSlots).map { slot =>
    buildActive(slot) && buildPageId(slot) === descriptorTerminal.page_ref.page_id &&
      buildGeneration(slot) === descriptorTerminal.page_ref.generation &&
      buildTag(slot) === descriptorTerminal.transaction_group_tag
  })
  val terminalAnyMatch = terminalMatches.asUInt.orR
  val terminalSlot = PriorityEncoder(terminalMatches)
  val terminalKindAllowed = (descriptorTerminal.kind === RouteADescriptorOperationKind.NewPage.U && !buildNewDurable(terminalSlot)) ||
    (descriptorTerminal.kind === RouteADescriptorOperationKind.TailLink.U && buildNeedsTail(terminalSlot) && !buildTailDurable(terminalSlot))
  val terminalOk = descriptorTerminal.status === p.coreMemoryOkStatusCode.U && descriptorTerminal.r1_descriptor_durable
  val terminalFault = descriptorTerminal.status === p.coreMemoryFaultStatusCode.U
  io.descriptor_maintenance_terminal_in.ready := initialized && terminalAnyMatch && !buildFault(terminalSlot) &&
    terminalKindAllowed && (terminalOk || terminalFault)
  when(io.descriptor_maintenance_terminal_in.fire) {
    when(terminalFault) { buildFault(terminalSlot) := true.B }
      .elsewhen(descriptorTerminal.kind === RouteADescriptorOperationKind.NewPage.U) { buildNewDurable(terminalSlot) := true.B }
      .otherwise { buildTailDurable(terminalSlot) := true.B }
  }

  val visibility = io.metadata_publish_visibility_in.bits
  val visibilityMatches = VecInit((0 until streamSlots).map { slot =>
    buildActive(slot) && !buildFault(slot) && buildNewDurable(slot) &&
      (!buildNeedsTail(slot) || buildTailDurable(slot)) &&
      buildPageId(slot) === visibility.page_ref.page_id &&
      buildGeneration(slot) === visibility.page_ref.generation &&
      buildTag(slot) === visibility.transaction_group_tag
  })
  val visibilityAnyMatch = visibilityMatches.asUInt.orR
  val visibilitySlot = PriorityEncoder(visibilityMatches)
  io.metadata_publish_visibility_in.ready := initialized && !visibilityAckPending && visibilityAnyMatch
  when(io.metadata_publish_visibility_in.fire) {
    visibilityAckPending := true.B
    visibilityAckPageRef := visibility.page_ref
    visibilityAckSlot := visibilitySlot
  }
  io.metadata_publish_visibility_ack.valid := visibilityAckPending
  io.metadata_publish_visibility_ack.bits.page_ref := visibilityAckPageRef
  io.metadata_publish_visibility_ack.bits.status := RouteAPublicationStatus.Published.U
  when(io.metadata_publish_visibility_ack.fire) {
    visibleTailPresent(visibilityAckSlot) := true.B
    visibleTailId(visibilityAckSlot) := visibilityAckPageRef.page_id
    visibleTailGeneration(visibilityAckSlot) := visibilityAckPageRef.generation
    buildActive(visibilityAckSlot) := false.B
    visibilityAckPending := false.B
  }

  // A descriptor becomes traversable only at the nested R3 publication event.
  when(io.metadata_publish_visibility_in.fire) {
    assert(visibilityAnyMatch)
  }
  val allocatorEmpty = !allocated.asUInt.orR
  val buildsEmpty = !buildActive.asUInt.orR
  val locallyDrained = allocatorEmpty && buildsEmpty && !allocationRspValid && !visibilityAckPending &&
    !reclaimActive && (!reclaimPermitted || io.reclaim_complete)
  val initStatusPending = initialized && !initStatusReported
  io.component_status_out.valid := initStatusPending ||
    (initialized && initStatusReported && io.drain_collection_enable && locallyDrained)
  io.component_status_out.bits.acknowledgement_name := Mux(
    initStatusPending,
    p.r6.pageManagerInitDoneStatusCode.U,
    p.r6.r5PageManagerDrainedStatusCode.U,
  )
  io.component_status_out.bits.asserted := true.B
  when(io.component_status_out.fire && initStatusPending) { initStatusReported := true.B }
}

/**
  * RTL1.6 packet/control boundary only. This parses frozen packet structure and
  * maps a replaceable result/fault slot to R6; it performs no numeric merge.
  */
final class RouteAMergeBoundary(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_merge_boundary"

  val io = IO(new Bundle {
    val drain_collection_enable = Input(Bool())
    val source_partial_in = Flipped(RouteAChannels.source_partial)
    val consumer_partial_commit = RouteAChannels.consumer_partial_commit(p)
    val merge_req_in = Flipped(RouteAChannels.merge_req)
    val r4_partial_header_in = Flipped(RouteAChannels.r4_partial_header)
    val r4_source_instance_in = Flipped(RouteAChannels.r4_source_instance_sideband(p))
    val r4_value_fragment_in = Flipped(RouteAChannels.r4_value_fragment)
    val r4_result_stub_in = Flipped(RouteAChannels.r4_result_stub)
    val r4_numeric_fault_in = Flipped(RouteAChannels.r4_numeric_fault)
    val merge_rsp_or_numeric_fault = RouteAChannels.merge_terminal_rsp
    val component_status_out = RouteAChannels.component_status(p)
  })

  val packetActive = RegInit(false.B)
  val packetIdentity = Reg(new TransactionIdentity)
  val packetSource = Reg(UInt(RouteAAnchorWidths.SourceKindWidth.W))
  val packetSourceInstance = Reg(new SourceInstance(p))
  val packetConsumer = Reg(UInt(RouteAAnchorWidths.ConsumerIdWidth.W))
  val nextFragment = RegInit(0.U(3.W))
  val commitPending = RegInit(false.B)
  val commitIdentity = Reg(new TransactionIdentity)
  val commitSource = Reg(UInt(RouteAAnchorWidths.SourceKindWidth.W))
  val commitSourceInstance = Reg(new SourceInstance(p))
  val commitConsumer = Reg(UInt(RouteAAnchorWidths.ConsumerIdWidth.W))

  val mergeActive = RegInit(false.B)
  val mergeIdentity = Reg(new TransactionIdentity)
  val terminalPending = RegInit(false.B)
  val terminalIdentity = Reg(new TransactionIdentity)
  val terminalStatus = Reg(UInt(RouteAAnchorWidths.TerminalStatusWidth.W))
  val terminalValue = Reg(UInt(RouteAAnchorWidths.NormalizedValueWidth.W))

  private def identityMatches(left: TransactionIdentity, right: TransactionIdentity): Bool =
    left.asUInt === right.asUInt

  val header = io.r4_partial_header_in.bits.header
  val headerSource = header(65, 64)
  val headerConsumer = header(67, 66)
  val headerMergeInstance = header(68)
  val headerPresent = header(69)
  val headerFragmentCount = header(73, 70)
  val headerReserved = header(127, 74)
  val headerSourceLegal = headerSource <= 2.U
  val absentIdentity = header(31, 0) === "hff800000".U && header(63, 32) === 0.U
  val headerStructureLegal = headerSourceLegal && !headerMergeInstance && headerReserved === 0.U &&
    Mux(headerPresent, headerFragmentCount === 8.U, headerFragmentCount === 0.U && absentIdentity)
  val sourceSideband = io.r4_source_instance_in.bits
  val sidebandMatchesHeader = sourceSideband.transaction_identity.asUInt === io.r4_partial_header_in.bits.transaction_identity.asUInt &&
    sourceSideband.source_instance.source_kind === headerSource && sourceSideband.consumer_id === headerConsumer &&
    sourceSideband.source_instance.source_kind <= RouteASourceKind.Packed.U
  val headerAndSidebandReady = !packetActive && !commitPending && headerStructureLegal && sidebandMatchesHeader
  io.r4_partial_header_in.ready := headerAndSidebandReady && io.r4_source_instance_in.valid
  io.r4_source_instance_in.ready := headerAndSidebandReady && io.r4_partial_header_in.valid
  when(io.r4_partial_header_in.fire) {
    assert(io.r4_source_instance_in.fire)
    when(headerPresent) {
      packetActive := true.B
      packetIdentity := io.r4_partial_header_in.bits.transaction_identity
      packetSource := headerSource
      packetSourceInstance := sourceSideband.source_instance
      packetConsumer := headerConsumer
      nextFragment := 0.U
    }.otherwise {
      commitPending := true.B
      commitIdentity := io.r4_partial_header_in.bits.transaction_identity
      commitSource := headerSource
      commitSourceInstance := sourceSideband.source_instance
      commitConsumer := headerConsumer
    }
  }

  val fragment = io.r4_value_fragment_in.bits
  val finalFragment = nextFragment === 7.U
  val fragmentMatches = packetActive && identityMatches(packetIdentity, fragment.transaction_identity) &&
    fragment.fragment_index === nextFragment && fragment.last === finalFragment
  io.r4_value_fragment_in.ready := fragmentMatches && !commitPending
  when(io.r4_value_fragment_in.fire) {
    when(finalFragment) {
      packetActive := false.B
      commitPending := true.B
      commitIdentity := packetIdentity
      commitSource := packetSource
      commitSourceInstance := packetSourceInstance
      commitConsumer := packetConsumer
    }.otherwise {
      nextFragment := nextFragment + 1.U
    }
  }

  io.consumer_partial_commit.valid := commitPending
  io.consumer_partial_commit.bits.transaction_identity := commitIdentity
  io.consumer_partial_commit.bits.consumer_id := commitConsumer
  io.consumer_partial_commit.bits.source_kind := commitSource
  io.consumer_partial_commit.bits.source_instance := commitSourceInstance
  when(io.consumer_partial_commit.fire) {
    commitPending := false.B
  }

  io.merge_req_in.ready := !mergeActive && !terminalPending && io.merge_req_in.bits.source_presence.orR
  when(io.merge_req_in.fire) {
    mergeActive := true.B
    mergeIdentity := io.merge_req_in.bits.transaction_identity
  }

  val resultMatches = mergeActive && !terminalPending &&
    identityMatches(mergeIdentity, io.r4_result_stub_in.bits.transaction_identity)
  val faultMatches = mergeActive && !terminalPending &&
    identityMatches(mergeIdentity, io.r4_numeric_fault_in.bits.transaction_identity)
  // A simultaneous success and fault is an upstream protocol violation; neither
  // slot is accepted, so the boundary cannot manufacture a terminal outcome.
  io.r4_result_stub_in.ready := resultMatches && !io.r4_numeric_fault_in.valid
  io.r4_numeric_fault_in.ready := faultMatches && !io.r4_result_stub_in.valid
  when(io.r4_result_stub_in.fire) {
    terminalPending := true.B
    terminalIdentity := io.r4_result_stub_in.bits.transaction_identity
    terminalStatus := p.coreMemoryOkStatusCode.U
    terminalValue := io.r4_result_stub_in.bits.normalized_value
  }
  when(io.r4_numeric_fault_in.fire) {
    terminalPending := true.B
    terminalIdentity := io.r4_numeric_fault_in.bits.transaction_identity
    terminalStatus := p.coreMemoryFaultStatusCode.U
    terminalValue := 0.U
  }

  io.merge_rsp_or_numeric_fault.valid := terminalPending
  io.merge_rsp_or_numeric_fault.bits.transaction_identity := terminalIdentity
  io.merge_rsp_or_numeric_fault.bits.status := terminalStatus
  io.merge_rsp_or_numeric_fault.bits.normalized_value := terminalValue
  when(io.merge_rsp_or_numeric_fault.fire) {
    assert(mergeActive && identityMatches(mergeIdentity, terminalIdentity))
    mergeActive := false.B
    terminalPending := false.B
  }

  // The only R4 state checks here are packet/terminal association checks; no
  // arithmetic, finite-value classification, normalization, or source reorder is inferred.
  when(io.r4_result_stub_in.fire) {
    assert(resultMatches && !io.r4_numeric_fault_in.valid)
  }
  when(io.r4_numeric_fault_in.fire) {
    assert(faultMatches && !io.r4_result_stub_in.valid)
  }
  val heldCommit = RegEnable(io.consumer_partial_commit.bits,
    io.consumer_partial_commit.valid && !io.consumer_partial_commit.ready)
  when(RegNext(io.consumer_partial_commit.valid && !io.consumer_partial_commit.ready, false.B)) {
    assert(io.consumer_partial_commit.bits.asUInt === heldCommit.asUInt)
  }
  val heldTerminal = RegEnable(io.merge_rsp_or_numeric_fault.bits,
    io.merge_rsp_or_numeric_fault.valid && !io.merge_rsp_or_numeric_fault.ready)
  when(RegNext(io.merge_rsp_or_numeric_fault.valid && !io.merge_rsp_or_numeric_fault.ready, false.B)) {
    assert(io.merge_rsp_or_numeric_fault.bits.asUInt === heldTerminal.asUInt)
  }

  StructuralTieOff.sink(io.source_partial_in)
  val locallyDrained = !packetActive && !commitPending && !mergeActive && !terminalPending
  io.component_status_out.valid := io.drain_collection_enable && locallyDrained
  io.component_status_out.bits.acknowledgement_name := p.r6.mergeDrainedStatusCode.U
  io.component_status_out.bits.asserted := true.B
}
