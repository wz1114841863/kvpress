package kvpress.routea.incremental

import chisel3._
import chisel3.util.{Decoupled, PopCount, RegEnable, Valid, log2Ceil}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAPublicationStatus, RouteASkeletonParameters}

/**
  * Minimal production admission-to-M2 metadata bridge for the bounded Route-A
  * measurement DUT.
  *
  * It accepts only the existing, already joint-accepted retained-member fact
  * emitted by RouteAAdmissionPublicationIngressAdapter.  The bridge owns no
  * KVzap decision, R6 authority transition, R2 grant, R3 publication, source
  * selection, or A4 private/shared FIFO policy.  It records immutable pending
  * membership identity, reserves one real group entry and one bounded logical
  * credit classification, assigns a per-stream append sequence, and forwards
  * the pre-existing M2 group preparation only after all actual members exist.
  *
  * `local32/shared256/staging512` are represented as frozen logical credit
  * ceilings.  A reservation has one group entry plus its exact accepted member
  * mask; it is therefore not a synthetic credit detached from metadata state.
  * The current one-P3-stage-per-layer measurement contour may impose a smaller
  * actual-entry bound first, which is fail-closed backpressure rather than a
  * change to retain/drop disposition.
  */
final class RouteAMetadataAdmissionBridge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_metadata_admission_bridge"

  val io = IO(new Bundle {
    val member_in = Flipped(RouteAChannels.metadata_append_member(p))
    val group_prepare_in = Flipped(RouteAChannels.m2_group_prepare(p))
    val group_prepare_out = RouteAChannels.m2_group_prepare(p)
    val metadata_append_operand_out = RouteAChannels.metadata_append_operand(p)
    // Both are read-only, non-backpressuring observations of existing R3/R5
    // events.  The bridge never creates a second publication or authority.
    val publication_resolution_in = Input(Valid(new M2GroupPublicationResolution(p)))
    val membership_handoff_in = Input(Valid(new MetadataMembershipHandoffObservation(p)))
    val metadata_group_abort_in = Input(Valid(new M2MetadataGroupAbort(p)))
    // Test/structural observability only.  These signals are not a new R2
    // predicate source or a publication-visible metadata interface.
    val local_credit_in_use = Output(Vec(8, UInt(6.W)))
    val shared_credit_in_use = Output(Vec(36, UInt(9.W)))
    val staging_credit_in_use = Output(Vec(36, UInt(10.W)))
    val active_group_count = Output(UInt(6.W))
  })

  private val Stages = 36
  private val Banks = 8
  private val Members = 64
  private val LocalCapacity = 32
  private val SharedCapacity = 256
  private val StagingCapacity = 512
  private val Streams = Stages * Banks
  private val StreamIndexWidth = log2Ceil(Streams)

  val groupActive = RegInit(VecInit(Seq.fill(Stages)(false.B)))
  val groupPrepared = RegInit(VecInit(Seq.fill(Stages)(false.B)))
  val groupPublishedAwaitHandoff = RegInit(VecInit(Seq.fill(Stages)(false.B)))
  val groupFaultedPending = RegInit(VecInit(Seq.fill(Stages)(false.B)))
  val groupHead = Reg(Vec(Stages, UInt(RouteAAnchorWidths.KvHeadWidth.W)))
  val groupTag = Reg(Vec(Stages, UInt(p.transactionGroupTagWidth.W)))
  val groupValidRecords = Reg(Vec(Stages, UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)))
  val groupStageGeneration = Reg(Vec(Stages, UInt(p.p3StageGenerationWidth.W)))
  val groupMemberMask = RegInit(VecInit(Seq.fill(Stages)(0.U(Members.W))))
  // This is the actual bounded membership ledger.  It retains the exact
  // pending binding supplied by the production payload/location owner; no
  // group tag, ordinal, mapping reference, or fixture reconstructs it.
  val groupMembers = Reg(Vec(Stages, Vec(Members, new PendingPayloadReadBinding(p))))
  val groupCreditPool = Reg(Vec(Stages, UInt(MetadataAppendCreditPool.Width.W)))
  val groupAppendSequence = Reg(Vec(Stages, UInt(RouteAAnchorWidths.ContextTokensWidth.W)))
  val groupPredecessorValid = RegInit(VecInit(Seq.fill(Stages)(false.B)))
  val groupPredecessorSequence = Reg(Vec(Stages, UInt(RouteAAnchorWidths.ContextTokensWidth.W)))

  val localCredit = RegInit(VecInit(Seq.fill(Banks)(0.U(6.W))))
  val sharedCredit = RegInit(VecInit(Seq.fill(Stages)(0.U(9.W))))
  val stagingCredit = RegInit(VecInit(Seq.fill(Stages)(0.U(10.W))))
  val streamNextSequence = RegInit(VecInit(Seq.fill(Stages * Banks)(0.U(RouteAAnchorWidths.ContextTokensWidth.W))))
  val streamTailValid = RegInit(VecInit(Seq.fill(Stages * Banks)(false.B)))
  val streamTailSequence = Reg(Vec(Stages * Banks, UInt(RouteAAnchorWidths.ContextTokensWidth.W)))

  // A stream is a physical (layer, head) pair in the bounded 36 x 8 contour.
  // Callers guard both dimensions before an accepted event; retaining only the
  // exact Vec index width prevents out-of-range heads from silently aliasing a
  // valid stream through a wide dynamic index.
  private def streamIndex(layer: UInt, head: UInt): UInt =
    (layer * Banks.U + head)(StreamIndexWidth - 1, 0)
  private def expectedMask(validRecords: UInt): UInt =
    VecInit((0 until Members).map(index => index.U < validRecords)).asUInt
  private def sameGroup(layer: UInt, binding: PendingPayloadReadBinding): Bool =
    groupHead(layer) === binding.kv_head &&
      groupTag(layer) === binding.transaction_group_tag &&
      groupValidRecords(layer) === binding.group_valid_records

  val declaration = io.member_in.bits.payload_binding
  val memberLayer = declaration.layer
  val memberHead = declaration.kv_head
  val memberStream = streamIndex(memberLayer, memberHead)
  val memberOrdinalInRange = declaration.group_valid_records =/= 0.U &&
    declaration.group_valid_records <= Members.U &&
    declaration.group_member_ordinal < declaration.group_valid_records
  val memberLayerInRange = memberLayer < Stages.U
  val memberHeadInRange = memberHead < Banks.U
  val memberBit = (1.U(Members.W) << declaration.group_member_ordinal(5, 0))(Members - 1, 0)
  val existingGroup = memberLayerInRange && groupActive(memberLayer)
  val existingGroupAcceptable = existingGroup && !groupPrepared(memberLayer) &&
    !groupPublishedAwaitHandoff(memberLayer) && !groupFaultedPending(memberLayer) &&
    sameGroup(memberLayer, declaration) && (groupMemberMask(memberLayer) & memberBit) === 0.U

  val localAvailable = localCredit(memberHead) < LocalCapacity.U
  val sharedAvailable = sharedCredit(memberLayer) < SharedCapacity.U
  val stagingAvailable = stagingCredit(memberLayer) < StagingCapacity.U
  val selectedCreditPool = Mux(localAvailable, MetadataAppendCreditPool.Local.U,
    Mux(sharedAvailable, MetadataAppendCreditPool.Shared.U, MetadataAppendCreditPool.Staging.U))
  val newGroupCreditAvailable = localAvailable || sharedAvailable || stagingAvailable
  val newGroupSequenceAvailable = streamNextSequence(memberStream) =/= "hffff".U
  // One physical/private group entry exists per active P3 layer in this
  // bounded contour.  This is checked alongside, not instead of, frozen credit.
  val newGroupEntryAvailable = memberLayerInRange && !groupActive(memberLayer)
  val memberAcceptable = memberLayerInRange && memberHeadInRange && memberOrdinalInRange &&
    Mux(existingGroup, existingGroupAcceptable,
      newGroupCreditAvailable && newGroupEntryAvailable && newGroupSequenceAvailable)
  // Keep credit mutation single-writer in this bounded functional contour.
  // A completed all-member handoff has priority over a new metadata admission;
  // the one-cycle delay is legal backpressure and never changes disposition.
  io.member_in.ready := memberAcceptable && !io.membership_handoff_in.valid

  when(io.member_in.fire) {
    when(!existingGroup) {
      groupActive(memberLayer) := true.B
      groupPrepared(memberLayer) := false.B
      groupPublishedAwaitHandoff(memberLayer) := false.B
      groupFaultedPending(memberLayer) := false.B
      groupHead(memberLayer) := memberHead
      groupTag(memberLayer) := declaration.transaction_group_tag
      groupValidRecords(memberLayer) := declaration.group_valid_records
      groupMemberMask(memberLayer) := memberBit
      groupMembers(memberLayer)(declaration.group_member_ordinal(5, 0)) := declaration
      groupCreditPool(memberLayer) := selectedCreditPool
      groupAppendSequence(memberLayer) := streamNextSequence(memberStream)
      groupPredecessorValid(memberLayer) := streamTailValid(memberStream)
      groupPredecessorSequence(memberLayer) := streamTailSequence(memberStream)
      // The sequence is allocated exactly on the first accepted member of the
      // actual group.  A wrap is fail-closed at ready, never silently reused.
      streamNextSequence(memberStream) := streamNextSequence(memberStream) + 1.U
      when(selectedCreditPool === MetadataAppendCreditPool.Local.U) {
        localCredit(memberHead) := localCredit(memberHead) + 1.U
      }.elsewhen(selectedCreditPool === MetadataAppendCreditPool.Shared.U) {
        sharedCredit(memberLayer) := sharedCredit(memberLayer) + 1.U
      }.otherwise {
        stagingCredit(memberLayer) := stagingCredit(memberLayer) + 1.U
      }
    }.otherwise {
      groupMemberMask(memberLayer) := groupMemberMask(memberLayer) | memberBit
      groupMembers(memberLayer)(declaration.group_member_ordinal(5, 0)) := declaration
    }
  }

  val preparation = io.group_prepare_in.bits
  val preparationLayer = preparation.p3_layer
  val preparationLayerInRange = preparationLayer < Stages.U
  val preparationMatches = preparationLayerInRange && groupActive(preparationLayer) &&
    !groupPrepared(preparationLayer) && !groupPublishedAwaitHandoff(preparationLayer) &&
    !groupFaultedPending(preparationLayer) && groupHead(preparationLayer) === preparation.kv_head &&
    groupTag(preparationLayer) === preparation.transaction_group_tag &&
    groupValidRecords(preparationLayer) === preparation.valid_records &&
    groupMemberMask(preparationLayer) === expectedMask(groupValidRecords(preparationLayer))
  val preparePending = RegInit(false.B)
  val prepareReg = Reg(new M2GroupPrepareDeclaration(p))
  io.group_prepare_in.ready := preparationMatches && !preparePending
  when(io.group_prepare_in.fire) {
    prepareReg := preparation
    groupStageGeneration(preparationLayer) := preparation.p3_stage_generation
    preparePending := true.B
  }
  io.group_prepare_out.valid := preparePending
  io.group_prepare_out.bits := prepareReg
  io.metadata_append_operand_out.valid := preparePending
  io.metadata_append_operand_out.bits.p3_layer := prepareReg.p3_layer
  io.metadata_append_operand_out.bits.kv_head := prepareReg.kv_head
  io.metadata_append_operand_out.bits.p3_stage_generation := prepareReg.p3_stage_generation
  io.metadata_append_operand_out.bits.transaction_group_tag := prepareReg.transaction_group_tag
  io.metadata_append_operand_out.bits.opaque_mapping_ref := prepareReg.opaque_address_ref
  io.metadata_append_operand_out.bits.mapping_owner := prepareReg.owner
  io.metadata_append_operand_out.bits.valid_records := groupValidRecords(prepareReg.p3_layer)
  io.metadata_append_operand_out.bits.member_mask := groupMemberMask(prepareReg.p3_layer)
  io.metadata_append_operand_out.bits.credit_pool := groupCreditPool(prepareReg.p3_layer)
  io.metadata_append_operand_out.bits.append_sequence := groupAppendSequence(prepareReg.p3_layer)
  io.metadata_append_operand_out.bits.predecessor_valid := groupPredecessorValid(prepareReg.p3_layer)
  io.metadata_append_operand_out.bits.predecessor_sequence := groupPredecessorSequence(prepareReg.p3_layer)
  io.metadata_append_operand_out.bits.members := groupMembers(prepareReg.p3_layer)
  // M2 accepts preparation and its lowerer operand together.  Neither half
  // may become an independently consumable declaration.
  when(io.group_prepare_out.fire) {
    assert(io.metadata_append_operand_out.fire)
    val layer = prepareReg.p3_layer
    assert(groupActive(layer))
    assert(groupMemberMask(layer) === expectedMask(groupValidRecords(layer)))
    groupPrepared(layer) := true.B
    preparePending := false.B
  }
  when(io.metadata_append_operand_out.fire) {
    assert(io.group_prepare_out.fire)
  }

  val resolution = io.publication_resolution_in.bits
  val resolutionLayerInRange = resolution.p3_layer < Stages.U
  val resolutionMatches = io.publication_resolution_in.valid && resolutionLayerInRange &&
    groupActive(resolution.p3_layer) && groupPrepared(resolution.p3_layer) &&
    groupStageGeneration(resolution.p3_layer) === resolution.p3_stage_generation &&
    groupTag(resolution.p3_layer) === resolution.transaction_group_tag
  when(io.publication_resolution_in.valid) {
    assert(resolutionMatches)
    when(resolutionMatches) {
      when(resolution.status === RouteAPublicationStatus.Published.U) {
        val stream = streamIndex(resolution.p3_layer, groupHead(resolution.p3_layer))
        assert(streamTailValid(stream) === groupPredecessorValid(resolution.p3_layer))
        when(groupPredecessorValid(resolution.p3_layer)) {
          assert(streamTailSequence(stream) === groupPredecessorSequence(resolution.p3_layer))
        }
        streamTailValid(stream) := true.B
        streamTailSequence(stream) := groupAppendSequence(resolution.p3_layer)
        groupPublishedAwaitHandoff(resolution.p3_layer) := true.B
      }.otherwise {
        // The pending membership and its credit remain live.  Only the private
        // publication preparation is aborted; a later reset/retire path is the
        // explicit reclamation boundary for an unpublishable pending record.
        groupPrepared(resolution.p3_layer) := false.B
        groupFaultedPending(resolution.p3_layer) := true.B
      }
    }
  }

  val abort = io.metadata_group_abort_in.bits
  val abortLayerInRange = abort.p3_layer < Stages.U
  val abortMatches = io.metadata_group_abort_in.valid && abortLayerInRange &&
    groupActive(abort.p3_layer) && groupPrepared(abort.p3_layer) &&
    groupStageGeneration(abort.p3_layer) === abort.p3_stage_generation &&
    groupTag(abort.p3_layer) === abort.transaction_group_tag
  when(io.metadata_group_abort_in.valid) {
    assert(abortMatches)
    when(abortMatches) {
      // A member fault cannot make a group publishable.  It does not erase a
      // legal pending membership or consume its credit; only M2's private
      // prepare is discarded until reset/retire supplies a real reclaim fact.
      groupPrepared(abort.p3_layer) := false.B
      groupFaultedPending(abort.p3_layer) := true.B
    }
  }

  val handoff = io.membership_handoff_in.bits
  val handoffLayerInRange = handoff.p3_layer < Stages.U
  val handoffMatches = io.membership_handoff_in.valid && handoffLayerInRange &&
    groupActive(handoff.p3_layer) && groupPublishedAwaitHandoff(handoff.p3_layer) &&
    groupStageGeneration(handoff.p3_layer) === handoff.p3_stage_generation &&
    groupTag(handoff.p3_layer) === handoff.transaction_group_tag &&
    groupValidRecords(handoff.p3_layer) === handoff.valid_records
  when(io.membership_handoff_in.valid) {
    assert(handoffMatches)
    when(handoffMatches) {
      val layer = handoff.p3_layer
      val head = groupHead(layer)
      when(groupCreditPool(layer) === MetadataAppendCreditPool.Local.U) {
        assert(localCredit(head) =/= 0.U)
        localCredit(head) := localCredit(head) - 1.U
      }.elsewhen(groupCreditPool(layer) === MetadataAppendCreditPool.Shared.U) {
        assert(sharedCredit(layer) =/= 0.U)
        sharedCredit(layer) := sharedCredit(layer) - 1.U
      }.otherwise {
        assert(stagingCredit(layer) =/= 0.U)
        stagingCredit(layer) := stagingCredit(layer) - 1.U
      }
      groupActive(layer) := false.B
      groupPrepared(layer) := false.B
      groupPublishedAwaitHandoff(layer) := false.B
      groupFaultedPending(layer) := false.B
      groupMemberMask(layer) := 0.U
    }
  }

  // An incoming retained group at the maximum sequence is not accepted, so a
  // generation-free sequence can never silently alias an earlier group.
  when(io.member_in.valid && !existingGroup && streamNextSequence(memberStream) === "hffff".U) {
    assert(!io.member_in.ready)
  }
  val prepareStalled = io.group_prepare_out.valid && !io.group_prepare_out.ready
  val heldPrepare = RegEnable(io.group_prepare_out.bits, prepareStalled)
  when(RegNext(prepareStalled, false.B)) {
    assert(io.group_prepare_out.bits.asUInt === heldPrepare.asUInt)
  }

  io.local_credit_in_use := localCredit
  io.shared_credit_in_use := sharedCredit
  io.staging_credit_in_use := stagingCredit
  io.active_group_count := PopCount(groupActive)
}
