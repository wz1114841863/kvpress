package kvpress.routea.incremental

import chisel3._
import chisel3.util.{Cat, PriorityEncoder, RegEnable, log2Ceil}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteADescriptorOperationKind, RouteAM2GroupMember, RouteAPublicationStatus, RouteASkeletonParameters}

/**
  * RTL1.0 structural shell only. Authority, terminal association, and global
  * retirement behavior remain unimplemented until their respective RTL1 phases.
  */
final class RouteALifecycleAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_lifecycle_adapter"

  val io = IO(new Bundle {
    val frontend_lifecycle_req = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val session_retire_ack = RouteAChannels.session_retire_ack
    val component_status_in = Flipped(RouteAChannels.component_status(p))
    val hot_control_out = RouteAChannels.hot_control(p)
    val s2_service_req = RouteAChannels.s2_service_req
    val direct_pending_open = RouteAChannels.direct_pending_open(p)
    val merge_req = RouteAChannels.merge_req
    val merge_terminal_in = Flipped(RouteAChannels.merge_terminal_rsp)
    val metadata_publish_req = RouteAChannels.metadata_publish_req(p)
    val metadata_publish_ack_in = Flipped(RouteAChannels.metadata_publish_ack(p))
  })

  StructuralTieOff.sink(io.frontend_lifecycle_req)
  StructuralTieOff.sink(io.runtime_retire_req)
  StructuralTieOff.source(io.attention_terminal_rsp)
  StructuralTieOff.source(io.session_retire_ack)
  StructuralTieOff.sink(io.component_status_in)
  StructuralTieOff.source(io.hot_control_out)
  StructuralTieOff.source(io.s2_service_req)
  StructuralTieOff.source(io.direct_pending_open)
  StructuralTieOff.source(io.merge_req)
  StructuralTieOff.sink(io.merge_terminal_in)
  StructuralTieOff.source(io.metadata_publish_req)
  StructuralTieOff.sink(io.metadata_publish_ack_in)
}

/** RTL1.4 direct-pending control only; no pending page/buffer or K/V storage. */
final class RouteADirectPendingEndpointV1(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_direct_pending_endpoint_v1"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val pending_source_open_in = Flipped(RouteAChannels.direct_pending_open(p))
    val direct_pending_record_terminal_in = Flipped(RouteAChannels.direct_pending_record_terminal(p))
    val gqa_consumer_commit_in = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val direct_release_out = RouteAChannels.source_release(p)
    val direct_observe_generation = Output(UInt(p.sourceGenerationWidth.W))
    val direct_observe_active = Output(Bool())
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
  val commitMatches = initialized && active && deliverable && !faulted && consumerCommit.source_is_direct &&
    consumerCommit.source_generation === endpointGeneration && identity.asUInt === consumerCommit.transaction_identity.asUInt &&
    consumerCommit.consumer_id < 4.U && (consumerMask & commitBit) =/= 0.U
  io.gqa_consumer_commit_in.ready := commitMatches
  when(io.gqa_consumer_commit_in.fire) {
    consumerMask := consumerMask & ~commitBit
  }

  val releaseEligible = active && deliverable && sourceClosed && !faulted && consumerMask === 0.U
  io.direct_release_out.valid := releaseEligible
  io.direct_release_out.bits.transaction_identity := identity
  io.direct_release_out.bits.source_is_direct := true.B
  io.direct_release_out.bits.source_slot := 0.U
  io.direct_release_out.bits.source_generation := endpointGeneration
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
}

/** RTL1.3 R3 control state: no P3 payload macro, M2 macro, or HBM controller. */
final class RouteAM2P3Wrapper(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_m2_p3_wrapper"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val p3_claim_in = Flipped(RouteAChannels.p3_claim(p))
    val p3_claim_ack = RouteAChannels.p3_claim_ack(p)
    val p3_pending_fragment_in = Flipped(RouteAChannels.p3_pending_fragment(p))
    val p3_sidecar_bind_in = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val p3_packed_write_issue_in = Flipped(RouteAChannels.p3_packed_write_issue(p))
    val p3_packed_write_terminal_in = Flipped(RouteAChannels.p3_packed_write_terminal(p))
    val m2_group_member_rsp_in = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val p3_observe_layer = Input(UInt(RouteAAnchorWidths.LayerWidth.W))
    val p3_observe_state = Output(UInt(RouteAAnchorWidths.P3StateWidth.W))
    val p3_observe_generation = Output(UInt(p.p3StageGenerationWidth.W))
    val m2_publish_req_in = Flipped(RouteAChannels.metadata_publish_req(p))
    val metadata_publish_visibility_apply = RouteAChannels.metadata_publish_visibility(p)
    val metadata_publish_visibility_ack_in = Flipped(RouteAChannels.metadata_publish_visibility_ack)
    val m2_publish_ack = RouteAChannels.metadata_publish_ack(p)
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
  val stageState = RegInit(VecInit(Seq.fill(stages)(StateEmpty)))
  val stageGeneration = RegInit(VecInit(Seq.fill(stages)(0.U(p.p3StageGenerationWidth.W))))
  val stageValidRecords = Reg(Vec(stages, UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)))
  val stageFragmentNext = RegInit(VecInit(Seq.fill(stages)(0.U(10.W))))
  val stageSidecarNext = RegInit(VecInit(Seq.fill(stages)(0.U(RouteAAnchorWidths.P3ValidRecordsWidth.W))))
  val stagePageRef = Reg(Vec(stages, new PageRef))
  val stageTag = Reg(Vec(stages, UInt(p.transactionGroupTagWidth.W)))
  val stageM2Members = RegInit(VecInit(Seq.fill(stages)(0.U(2.W))))

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
  io.p3_claim_in.ready := initialized && !claimAckValid && validClaimRecords && stageState(claimLayer) === StateEmpty
  when(io.p3_claim_in.fire) {
    val nextGeneration = stageGeneration(claimLayer) + 1.U
    stageGeneration(claimLayer) := nextGeneration
    stageState(claimLayer) := StateReserved
    stageValidRecords(claimLayer) := claim.valid_records
    stageFragmentNext(claimLayer) := 0.U
    stageSidecarNext(claimLayer) := 0.U
    stagePageRef(claimLayer) := claim.page_ref
    stageTag(claimLayer) := claim.transaction_group_tag
    stageM2Members(claimLayer) := 0.U
    claimAckValid := true.B
    claimAckLayer := claimLayer
    claimAckGeneration := nextGeneration
  }

  def expectedFragments(layer: UInt): UInt = Cat(stageValidRecords(layer), 0.U(3.W))
  val fragment = io.p3_pending_fragment_in.bits
  val fragmentLayer = fragment.layer
  val fragmentMatches = initialized &&
    (stageState(fragmentLayer) === StateReserved || stageState(fragmentLayer) === StateFilling) &&
    stageGeneration(fragmentLayer) === fragment.stage_generation
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
      stageFragmentNext(fragmentLayer) := nextFragment
      when(stageState(fragmentLayer) === StateReserved) { stageState(fragmentLayer) := StateFilling }
      when(fragment.last && stageSidecarNext(fragmentLayer) === stageValidRecords(fragmentLayer)) {
        stageState(fragmentLayer) := StateComplete
      }
    }
  }

  val sidecar = io.p3_sidecar_bind_in.bits
  val sidecarLayer = sidecar.layer
  val sidecarMatches = initialized &&
    (stageState(sidecarLayer) === StateReserved || stageState(sidecarLayer) === StateFilling) &&
    stageGeneration(sidecarLayer) === sidecar.stage_generation &&
    stageSidecarNext(sidecarLayer) < stageValidRecords(sidecarLayer) &&
    sidecar.record_ordinal === stageSidecarNext(sidecarLayer)
  io.p3_sidecar_bind_in.ready := sidecarMatches
  when(io.p3_sidecar_bind_in.fire) {
    val nextSidecar = stageSidecarNext(sidecarLayer) + 1.U
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
  }

  val m2Member = io.m2_group_member_rsp_in.bits
  val memberLayer = m2Member.layer
  val memberBit = (1.U(2.W) << m2Member.member)(1, 0)
  val memberMatches = initialized && stageState(memberLayer) === StateDurable &&
    stageGeneration(memberLayer) === m2Member.stage_generation &&
    stageTag(memberLayer) === m2Member.transaction_group_tag &&
    m2Member.member <= RouteAM2GroupMember.SpanOwnerRmw.U &&
    (stageM2Members(memberLayer) & memberBit) === 0.U
  val memberOk = m2Member.status === p.coreMemoryOkStatusCode.U
  val memberFault = m2Member.status === p.coreMemoryFaultStatusCode.U
  io.m2_group_member_rsp_in.ready := memberMatches && (memberOk || memberFault)
  when(io.m2_group_member_rsp_in.fire) {
    when(memberFault) { stageState(memberLayer) := StateFaulted }
      .otherwise { stageM2Members(memberLayer) := stageM2Members(memberLayer) | memberBit }
  }

  val publicationActive = RegInit(false.B)
  val publicationAwaitingVisibilityAck = RegInit(false.B)
  val publicationLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val publicationTag = Reg(UInt(p.transactionGroupTagWidth.W))
  val publicationPageRef = Reg(new PageRef)
  val publish = io.m2_publish_req_in.bits
  val publishPrerequisites = initialized && stageState(publish.p3_layer) === StateDurable &&
    stageGeneration(publish.p3_layer) === publish.p3_stage_generation &&
    stageTag(publish.p3_layer) === publish.transaction_group_tag &&
    stageM2Members(publish.p3_layer) === 3.U
  io.m2_publish_req_in.ready := !publicationActive && publishPrerequisites
  when(io.m2_publish_req_in.fire) {
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
  }
  when(io.m2_publish_ack.valid && io.m2_publish_ack.bits.status === RouteAPublicationStatus.Published.U) {
    assert(publicationAwaitingVisibilityAck)
  }

  io.p3_observe_state := stageState(io.p3_observe_layer)
  io.p3_observe_generation := stageGeneration(io.p3_observe_layer)
}

/** RTL1.3 R5 control state; descriptor payload/HBM traffic remains on R2/R1. */
final class RouteAPageManager(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_page_manager"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val page_allocation_req_in = Flipped(RouteAChannels.page_allocation_req(p))
    val page_allocation_rsp = RouteAChannels.page_allocation_rsp(p)
    val descriptor_maintenance_terminal_in = Flipped(RouteAChannels.descriptor_maintenance_terminal(p))
    val metadata_publish_visibility_in = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val metadata_publish_visibility_ack = RouteAChannels.metadata_publish_visibility_ack
  })

  private val streamSlots = p.r5StreamSlots
  private val streamIndexWidth = math.max(1, log2Ceil(streamSlots))
  val initialized = RegInit(false.B)
  when(io.mem_init_done) { initialized := true.B }
  val allocated = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(false.B)))
  val generations = RegInit(VecInit(Seq.fill(p.r5AllocatorEntries)(0.U(RouteAAnchorWidths.PageGenerationWidth.W))))
  val buildActive = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildFault = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildPageId = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageIdWidth.W)))
  val buildGeneration = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageGenerationWidth.W)))
  val buildTag = Reg(Vec(streamSlots, UInt(p.transactionGroupTagWidth.W)))
  val buildNewDurable = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildTailDurable = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val buildNeedsTail = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val visibleTailPresent = RegInit(VecInit(Seq.fill(streamSlots)(false.B)))
  val visibleTailId = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageIdWidth.W)))
  val visibleTailGeneration = Reg(Vec(streamSlots, UInt(RouteAAnchorWidths.PageGenerationWidth.W)))

  def streamIndexWide(layer: UInt, head: UInt): UInt = Cat(layer, head)
  val allocationRspValid = RegInit(false.B)
  val allocationRsp = Reg(new PageAllocationResponse(p))
  io.page_allocation_rsp.valid := allocationRspValid
  io.page_allocation_rsp.bits := allocationRsp
  when(io.page_allocation_rsp.fire) { allocationRspValid := false.B }

  val alloc = io.page_allocation_req_in.bits
  val allocStreamWide = streamIndexWide(alloc.layer, alloc.kv_head)
  val allocStream = allocStreamWide(streamIndexWidth - 1, 0)
  val allocValidRecords = alloc.valid_records =/= 0.U && alloc.valid_records <= 64.U
  val freeExists = !allocated.reduce(_ && _)
  val freeIndex = PriorityEncoder(VecInit(allocated.map(! _)))
  io.page_allocation_req_in.ready := initialized && !allocationRspValid && allocValidRecords &&
    allocStreamWide < streamSlots.U && !buildActive(allocStream) && freeExists
  when(io.page_allocation_req_in.fire) {
    allocated(freeIndex) := true.B
    buildActive(allocStream) := true.B
    buildFault(allocStream) := false.B
    buildPageId(allocStream) := freeIndex
    buildGeneration(allocStream) := generations(freeIndex)
    buildTag(allocStream) := alloc.transaction_group_tag
    buildNewDurable(allocStream) := false.B
    buildTailDurable(allocStream) := false.B
    buildNeedsTail(allocStream) := visibleTailPresent(allocStream)
    allocationRspValid := true.B
    allocationRsp.layer := alloc.layer
    allocationRsp.kv_head := alloc.kv_head
    allocationRsp.page_ref.page_id := freeIndex
    allocationRsp.page_ref.generation := generations(freeIndex)
    allocationRsp.requires_tail_link := visibleTailPresent(allocStream)
    allocationRsp.transaction_group_tag := alloc.transaction_group_tag
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
  val visibilityAckPending = RegInit(false.B)
  val visibilityAckPageRef = Reg(new PageRef)
  val visibilityAckSlot = Reg(UInt(streamIndexWidth.W))
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
}

/**
  * Replaceable R4 boundary shell only. It does not implement merge arithmetic,
  * partial state, numeric-fault detection, source release, or terminal policy.
  */
final class RouteAMergeBoundary extends Module {
  override def desiredName: String = "route_a_merge_boundary"

  val io = IO(new Bundle {
    val source_partial_in = Flipped(RouteAChannels.source_partial)
    val consumer_partial_commit = RouteAChannels.consumer_partial_commit
    val merge_req_in = Flipped(RouteAChannels.merge_req)
    val merge_rsp_or_numeric_fault = RouteAChannels.merge_terminal_rsp
  })

  StructuralTieOff.sink(io.source_partial_in)
  StructuralTieOff.source(io.consumer_partial_commit)
  StructuralTieOff.sink(io.merge_req_in)
  StructuralTieOff.source(io.merge_rsp_or_numeric_fault)
}
