package kvpress.routea.common

import chisel3._
import chisel3.util.{Cat, MuxCase, PopCount, PriorityEncoder, RegEnable, UIntToOH, Valid, log2Ceil}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * RTL2.2.1 functional delivery-context association owner.
  *
  * RTL2.2.2 connects this child to the production write-terminal path through
  * the allocation bridge and typed router. It owns only finite logical association
  * allocation/release and makes no FIFO depth, endpoint, clock, controller,
  * throughput, or PPA claim.  R1 remains responsible for adapter-epoch stale
  * response suppression; reset here destructively clears associations and
  * allocation is held until R1 has signalled `mem_init_done`.
  */
final class RouteADeliveryContextRegistry(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_delivery_context_registry"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val allocation_in = Flipped(RouteAChannels.delivery_context_allocate(p))
    val allocation_ack_out = RouteAChannels.delivery_context_allocation_ack(p)
    val resolve_in = Flipped(RouteAChannels.source_delivery(p))
    val resolved_out = RouteAChannels.resolved_delivery(p)
    val release_in = Flipped(RouteAChannels.delivery_context_release(p))
  })

  private val contextSlots = 1 << p.sourceDeliveryOpaqueWidth
  private def targetKindMatchesClass(allocation: DeliveryContextAllocation): Bool = MuxCase(
    false.B,
    Seq(
      (allocation.candidate_class === p.r2PackReadClassCode.U) ->
        (allocation.target_kind === RouteADeliveryTargetKind.P3PendingRead.U),
      (allocation.candidate_class === p.r2S2FullClassCode.U) ->
        (allocation.target_kind === RouteADeliveryTargetKind.S2FullFill.U),
      (allocation.candidate_class === p.r2S2PackedClassCode.U) ->
        (allocation.target_kind === RouteADeliveryTargetKind.S2PackedFill.U),
      (allocation.candidate_class === p.r2DirectPendingClassCode.U) ->
        (allocation.target_kind === RouteADeliveryTargetKind.DirectPendingRead.U),
      (allocation.candidate_class === p.r2PackWriteClassCode.U) ->
        (allocation.target_kind === RouteADeliveryTargetKind.PackedWriteTerminal.U),
      (allocation.candidate_class === p.r2DescriptorMaintenanceClassCode.U) ->
        (allocation.target_kind === RouteADeliveryTargetKind.DescriptorMaintenanceTerminal.U),
    ),
  )

  val initialized = RegInit(false.B)
  when(io.mem_init_done) { initialized := true.B }

  val valid = RegInit(VecInit(Seq.fill(contextSlots)(false.B)))
  val associations = Reg(Vec(contextSlots, new DeliveryContextAllocation(p)))
  val ackValid = RegInit(false.B)
  val ack = Reg(new DeliveryContextAllocationAck(p))
  val resolvedValid = RegInit(false.B)
  val resolved = Reg(new ResolvedDelivery(p))

  val allocation = io.allocation_in.bits
  val duplicate = VecInit((0 until contextSlots).map { index =>
    valid(index) && associations(index).candidate_class === allocation.candidate_class &&
      associations(index).transaction_identity.asUInt === allocation.transaction_identity.asUInt
  }).asUInt.orR
  val anyFree = !valid.reduce(_ && _)
  val freeIndex = PriorityEncoder(VecInit(valid.map(! _)))
  io.allocation_in.ready := initialized && !ackValid && targetKindMatchesClass(allocation) && !duplicate && anyFree
  io.allocation_ack_out.valid := ackValid
  io.allocation_ack_out.bits := ack

  val delivery = io.resolve_in.bits
  val deliveryRef = delivery.delivery_context_ref
  val resolveMatches = initialized && valid(deliveryRef) &&
    associations(deliveryRef).candidate_class === delivery.candidate_class &&
    associations(deliveryRef).transaction_identity.asUInt === delivery.r1_response.transaction_identity.asUInt
  io.resolve_in.ready := resolveMatches && !resolvedValid
  io.resolved_out.valid := resolvedValid
  io.resolved_out.bits := resolved

  val release = io.release_in.bits
  val releaseRef = release.delivery_context_ref
  val releaseMatches = initialized && valid(releaseRef) &&
    associations(releaseRef).asUInt === release.allocation.asUInt
  io.release_in.ready := releaseMatches

  when(io.allocation_ack_out.fire) { ackValid := false.B }
  when(io.resolved_out.fire) { resolvedValid := false.B }
  when(io.allocation_in.fire) {
    valid(freeIndex) := true.B
    associations(freeIndex) := allocation
    ackValid := true.B
    ack.delivery_context_ref := freeIndex
    ack.allocation := allocation
  }
  when(io.resolve_in.fire) {
    resolvedValid := true.B
    resolved.source_delivery := delivery
    resolved.allocation := associations(deliveryRef)
  }
  when(io.release_in.fire) { valid(releaseRef) := false.B }

  // A held allocation response is immutable.  This is a ready/valid safety
  // condition only, not an allocation-service latency promise.
  val heldAck = RegEnable(io.allocation_ack_out.bits,
    io.allocation_ack_out.valid && !io.allocation_ack_out.ready)
  when(RegNext(io.allocation_ack_out.valid && !io.allocation_ack_out.ready, false.B)) {
    assert(io.allocation_ack_out.bits.asUInt === heldAck.asUInt)
  }
  when(io.release_in.fire) { assert(releaseMatches) }
  when(io.resolve_in.fire) { assert(resolveMatches) }
}

/**
  * The hot-residency data path remains unimplemented.  RTL1-I2 permits this
  * owner-local control acknowledgement so the already-decided lifecycle event
  * can reach R3; accepting it neither stores a token nor services a request.
  */
final class RouteAHotSourcePath(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_hot_source_path"

  val io = IO(new Bundle {
    val lifecycle_control_in = Flipped(RouteAChannels.hot_control(p))
    val hot_source_open_in = Flipped(RouteAChannels.hot_source_open(p))
    val gqa_consumer_commit_in = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val hot_release_out = RouteAChannels.source_release(p)
  })

  io.lifecycle_control_in.ready := true.B
  val active = RegInit(false.B)
  val identity = Reg(new TransactionIdentity)
  val instance = Reg(new SourceInstance(p))
  val consumerMask = RegInit(0.U(4.W))
  val open = io.hot_source_open_in.bits
  val openLegal = open.source_instance.source_kind === RouteASourceKind.Hot.U
  io.hot_source_open_in.ready := !active && openLegal
  when(io.hot_source_open_in.fire) {
    active := true.B
    identity := open.transaction_identity
    instance := open.source_instance
    consumerMask := "b1111".U
  }
  val commit = io.gqa_consumer_commit_in.bits
  val commitBit = (1.U(4.W) << commit.consumer_id)(3, 0)
  val commitMatches = active && commit.source_instance.asUInt === instance.asUInt &&
    commit.transaction_identity.asUInt === identity.asUInt && commit.consumer_id < 4.U &&
    (consumerMask & commitBit) =/= 0.U
  io.gqa_consumer_commit_in.ready := commitMatches
  when(io.gqa_consumer_commit_in.fire) { consumerMask := consumerMask & ~commitBit }
  io.hot_release_out.valid := active && consumerMask === 0.U
  io.hot_release_out.bits.transaction_identity := identity
  io.hot_release_out.bits.source_instance := instance
  when(io.hot_release_out.fire) { active := false.B; consumerMask := 0.U }
  when(io.hot_release_out.valid) { assert(active && consumerMask === 0.U) }
  val heldRelease = RegEnable(io.hot_release_out.bits, io.hot_release_out.valid && !io.hot_release_out.ready)
  when(RegNext(io.hot_release_out.valid && !io.hot_release_out.ready, false.B)) {
    assert(io.hot_release_out.bits.asUInt === heldRelease.asUInt)
  }
}

/**
  * RTL2.3 logical S2 functional storage boundary. The two 32-KiB payload and
  * 512-B sidecar capacities are modeled only as replaceable reference backing;
  * this does not select a macro, port count, latency, controller, or PPA.
  * Source service/GQA packetization remains a later owner-local RTL2.4 step.
  */
final class RouteAS2GqaSourceWrapper(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_s2_gqa_source_wrapper"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val service_req_in = Flipped(RouteAChannels.s2_service_req)
    val s2_fill_open_in = Flipped(RouteAChannels.s2_fill_open(p))
    val s2_payload_fragment_in = Flipped(RouteAChannels.s2_payload_fragment(p))
    val s2_sidecar_fragment_in = Flipped(RouteAChannels.s2_sidecar_fragment(p))
    val s2_fill_terminal_in = Flipped(RouteAChannels.s2_fill_terminal(p))
    val s2_sidecar_complete_in = Flipped(RouteAChannels.s2_sidecar_complete(p))
    val s2_payload_read_req_in = Flipped(RouteAChannels.s2_payload_read_req(p))
    val s2_payload_read_rsp_out = RouteAChannels.s2_payload_read_rsp(p)
    val s2_sidecar_read_req_in = Flipped(RouteAChannels.s2_sidecar_read_req(p))
    val s2_sidecar_read_rsp_out = RouteAChannels.s2_sidecar_read_rsp(p)
    val gqa_consumer_commit_in = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val s2_release_out = RouteAChannels.source_release(p)
    val s2_observe_slot = Input(UInt(RouteAAnchorWidths.S2SlotWidth.W))
    val s2_observe_state = Output(UInt(3.W))
    val s2_observe_generation = Output(UInt(p.sourceGenerationWidth.W))
    val component_status_out = RouteAChannels.component_status(p)
  })

  private val slots = 2
  private val StateEmpty = 0.U(3.W)
  private val StateFilling = 1.U(3.W)
  private val StateReady = 2.U(3.W)
  private val StateFaulted = 3.U(3.W)

  val initialized = RegInit(false.B)
  when(io.mem_init_done) { initialized := true.B }
  val slotState = RegInit(VecInit(Seq.fill(slots)(StateEmpty)))
  val slotGeneration = RegInit(VecInit(Seq.fill(slots)(0.U(p.sourceGenerationWidth.W))))
  val slotIdentity = Reg(Vec(slots, new TransactionIdentity))
  val slotPageRef = Reg(Vec(slots, new PageRef))
  val fillOpened = RegInit(VecInit(Seq.fill(slots)(false.B)))
  val expectedFragments = Reg(Vec(slots, UInt(10.W)))
  val nextFragment = RegInit(VecInit(Seq.fill(slots)(0.U(10.W))))
  val payloadNext = RegInit(VecInit(Seq.fill(slots)(0.U(10.W))))
  val expectedSidecars = Reg(Vec(slots, UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)))
  val sidecarNext = RegInit(VecInit(Seq.fill(slots)(0.U(RouteAAnchorWidths.P3ValidRecordsWidth.W))))
  val requiresSidecar = RegInit(VecInit(Seq.fill(slots)(false.B)))
  val sidecarComplete = RegInit(VecInit(Seq.fill(slots)(false.B)))
  val consumerMask = RegInit(VecInit(Seq.fill(slots)(0.U(4.W))))
  // Reference-only, flat logical storage: 2 x 512 payload fragments and
  // 2 x 64 padded sidecar records. It remains replaceable by later SRAM
  // realization and cannot be interpreted as a macro/port choice.
  val payloadStore = Mem(slots * 512, UInt(RouteAAnchorWidths.CoreDataWidth.W))
  val sidecarStore = Mem(slots * 64, UInt(64.W))
  private def payloadIndex(slot: UInt, fragment: UInt): UInt = slot * 512.U + fragment
  private def sidecarIndex(slot: UInt, ordinal: UInt): UInt = slot * 64.U + ordinal
  val payloadReadRspValid = RegInit(false.B)
  val payloadReadRsp = Reg(new S2PayloadReadResponse(p))
  val sidecarReadRspValid = RegInit(false.B)
  val sidecarReadRsp = Reg(new S2SidecarReadResponse(p))

  val service = io.service_req_in.bits
  val serviceSlot = service.s2_slot
  io.service_req_in.ready := initialized && slotState(serviceSlot) === StateEmpty
  when(io.service_req_in.fire) {
    slotState(serviceSlot) := StateFilling
    slotGeneration(serviceSlot) := slotGeneration(serviceSlot) + 1.U
    slotIdentity(serviceSlot) := service.transaction_identity
    slotPageRef(serviceSlot) := service.page_ref
    fillOpened(serviceSlot) := false.B
    nextFragment(serviceSlot) := 0.U
    payloadNext(serviceSlot) := 0.U
    sidecarNext(serviceSlot) := 0.U
    requiresSidecar(serviceSlot) := false.B
    sidecarComplete(serviceSlot) := false.B
    consumerMask(serviceSlot) := 0.U
  }

  val fillOpen = io.s2_fill_open_in.bits
  val fillSlot = fillOpen.s2_slot
  val sidecarCountLegal = Mux(fillOpen.requires_sidecar,
    fillOpen.expected_sidecar_records =/= 0.U && fillOpen.expected_sidecar_records <= 64.U,
    fillOpen.expected_sidecar_records === 0.U)
  val fillOpenMatches = initialized && slotState(fillSlot) === StateFilling && !fillOpened(fillSlot) &&
    slotGeneration(fillSlot) === fillOpen.source_generation &&
    slotIdentity(fillSlot).asUInt === fillOpen.transaction_identity.asUInt &&
    slotPageRef(fillSlot).asUInt === fillOpen.page_ref.asUInt &&
    fillOpen.expected_fragment_count =/= 0.U && fillOpen.expected_fragment_count <= 512.U && sidecarCountLegal
  io.s2_fill_open_in.ready := fillOpenMatches
  when(io.s2_fill_open_in.fire) {
    fillOpened(fillSlot) := true.B
    expectedFragments(fillSlot) := fillOpen.expected_fragment_count
    nextFragment(fillSlot) := 0.U
    payloadNext(fillSlot) := 0.U
    expectedSidecars(fillSlot) := fillOpen.expected_sidecar_records
    sidecarNext(fillSlot) := 0.U
    requiresSidecar(fillSlot) := fillOpen.requires_sidecar
    sidecarComplete(fillSlot) := false.B
  }

  val payloadFragment = io.s2_payload_fragment_in.bits
  val payloadSlot = payloadFragment.s2_slot
  val payloadLastExpected = payloadNext(payloadSlot) + 1.U === expectedFragments(payloadSlot)
  val payloadMatches = initialized && slotState(payloadSlot) === StateFilling && fillOpened(payloadSlot) &&
    slotGeneration(payloadSlot) === payloadFragment.source_generation &&
    slotIdentity(payloadSlot).asUInt === payloadFragment.transaction_identity.asUInt &&
    payloadNext(payloadSlot) < expectedFragments(payloadSlot) &&
    payloadFragment.fragment_index === payloadNext(payloadSlot)(8, 0) &&
    payloadFragment.last === payloadLastExpected
  io.s2_payload_fragment_in.ready := payloadMatches
  when(io.s2_payload_fragment_in.fire) {
    payloadStore.write(payloadIndex(payloadSlot, payloadFragment.fragment_index), payloadFragment.data)
    payloadNext(payloadSlot) := payloadNext(payloadSlot) + 1.U
  }

  val sidecarFragment = io.s2_sidecar_fragment_in.bits
  val sidecarFragmentSlot = sidecarFragment.s2_slot
  val sidecarFragmentMatches = initialized && slotState(sidecarFragmentSlot) === StateFilling &&
    fillOpened(sidecarFragmentSlot) && requiresSidecar(sidecarFragmentSlot) &&
    slotGeneration(sidecarFragmentSlot) === sidecarFragment.source_generation &&
    slotIdentity(sidecarFragmentSlot).asUInt === sidecarFragment.transaction_identity.asUInt &&
    sidecarNext(sidecarFragmentSlot) < expectedSidecars(sidecarFragmentSlot) &&
    sidecarFragment.record_ordinal === sidecarNext(sidecarFragmentSlot)
  io.s2_sidecar_fragment_in.ready := sidecarFragmentMatches
  when(io.s2_sidecar_fragment_in.fire) {
    sidecarStore.write(sidecarIndex(sidecarFragmentSlot, sidecarFragment.record_ordinal), sidecarFragment.data)
    sidecarNext(sidecarFragmentSlot) := sidecarNext(sidecarFragmentSlot) + 1.U
  }

  val fillTerminal = io.s2_fill_terminal_in.bits
  val terminalSlot = fillTerminal.s2_slot
  val terminalMatches = initialized && slotState(terminalSlot) === StateFilling && fillOpened(terminalSlot) &&
    slotGeneration(terminalSlot) === fillTerminal.source_generation &&
    slotIdentity(terminalSlot).asUInt === fillTerminal.transaction_identity.asUInt
  val terminalOk = fillTerminal.status === p.coreMemoryOkStatusCode.U
  val terminalFault = fillTerminal.status === p.coreMemoryFaultStatusCode.U
  val terminalOrdinalOk = nextFragment(terminalSlot) < expectedFragments(terminalSlot) &&
    fillTerminal.fragment_index === nextFragment(terminalSlot)(8, 0) &&
    payloadNext(terminalSlot) === nextFragment(terminalSlot) + 1.U
  val terminalLastExpected = nextFragment(terminalSlot) + 1.U === expectedFragments(terminalSlot)
  io.s2_fill_terminal_in.ready := terminalMatches &&
    ((terminalOk && terminalOrdinalOk && fillTerminal.last === terminalLastExpected) || terminalFault)
  when(io.s2_fill_terminal_in.fire) {
    when(terminalFault) {
      slotState(terminalSlot) := StateFaulted
    }.otherwise {
      val next = nextFragment(terminalSlot) + 1.U
      nextFragment(terminalSlot) := next
      when(fillTerminal.last && (!requiresSidecar(terminalSlot) || sidecarComplete(terminalSlot))) {
        slotState(terminalSlot) := StateReady
        consumerMask(terminalSlot) := "b1111".U
      }
    }
  }

  val sidecar = io.s2_sidecar_complete_in.bits
  val sidecarSlot = sidecar.s2_slot
  val sidecarMatches = initialized && slotState(sidecarSlot) === StateFilling && fillOpened(sidecarSlot) &&
    requiresSidecar(sidecarSlot) && slotGeneration(sidecarSlot) === sidecar.source_generation &&
    slotIdentity(sidecarSlot).asUInt === sidecar.transaction_identity.asUInt &&
    sidecarNext(sidecarSlot) === expectedSidecars(sidecarSlot)
  io.s2_sidecar_complete_in.ready := sidecarMatches
  when(io.s2_sidecar_complete_in.fire) {
    sidecarComplete(sidecarSlot) := true.B
    when(nextFragment(sidecarSlot) === expectedFragments(sidecarSlot)) {
      slotState(sidecarSlot) := StateReady
      consumerMask(sidecarSlot) := "b1111".U
    }
  }

  val payloadRead = io.s2_payload_read_req_in.bits
  val payloadReadSlot = payloadRead.s2_slot
  val payloadReadMatches = initialized && !payloadReadRspValid && slotState(payloadReadSlot) === StateReady &&
    slotGeneration(payloadReadSlot) === payloadRead.source_generation &&
    slotIdentity(payloadReadSlot).asUInt === payloadRead.transaction_identity.asUInt &&
    payloadRead.fragment_index < expectedFragments(payloadReadSlot)
  io.s2_payload_read_req_in.ready := payloadReadMatches
  io.s2_payload_read_rsp_out.valid := payloadReadRspValid
  io.s2_payload_read_rsp_out.bits := payloadReadRsp
  when(io.s2_payload_read_rsp_out.fire) { payloadReadRspValid := false.B }
  when(io.s2_payload_read_req_in.fire) {
    payloadReadRspValid := true.B
    payloadReadRsp.request := payloadRead
    payloadReadRsp.data := payloadStore.read(payloadIndex(payloadReadSlot, payloadRead.fragment_index))
  }

  val sidecarRead = io.s2_sidecar_read_req_in.bits
  val sidecarReadSlot = sidecarRead.s2_slot
  val sidecarReadMatches = initialized && !sidecarReadRspValid && slotState(sidecarReadSlot) === StateReady &&
    requiresSidecar(sidecarReadSlot) && slotGeneration(sidecarReadSlot) === sidecarRead.source_generation &&
    slotIdentity(sidecarReadSlot).asUInt === sidecarRead.transaction_identity.asUInt &&
    sidecarRead.record_ordinal < expectedSidecars(sidecarReadSlot)
  io.s2_sidecar_read_req_in.ready := sidecarReadMatches
  io.s2_sidecar_read_rsp_out.valid := sidecarReadRspValid
  io.s2_sidecar_read_rsp_out.bits := sidecarReadRsp
  when(io.s2_sidecar_read_rsp_out.fire) { sidecarReadRspValid := false.B }
  when(io.s2_sidecar_read_req_in.fire) {
    sidecarReadRspValid := true.B
    sidecarReadRsp.request := sidecarRead
    sidecarReadRsp.data := sidecarStore.read(sidecarIndex(sidecarReadSlot, sidecarRead.record_ordinal))
  }

  // a_ready_low_nonmutation applies to the new owner-local functional-store
  // responses as well: a consumer stall cannot alter an offered fragment.
  val payloadReadRspStalled = io.s2_payload_read_rsp_out.valid && !io.s2_payload_read_rsp_out.ready
  val heldPayloadReadRsp = RegEnable(io.s2_payload_read_rsp_out.bits, payloadReadRspStalled)
  when(RegNext(payloadReadRspStalled, false.B)) {
    assert(io.s2_payload_read_rsp_out.bits.asUInt === heldPayloadReadRsp.asUInt)
  }
  val sidecarReadRspStalled = io.s2_sidecar_read_rsp_out.valid && !io.s2_sidecar_read_rsp_out.ready
  val heldSidecarReadRsp = RegEnable(io.s2_sidecar_read_rsp_out.bits, sidecarReadRspStalled)
  when(RegNext(sidecarReadRspStalled, false.B)) {
    assert(io.s2_sidecar_read_rsp_out.bits.asUInt === heldSidecarReadRsp.asUInt)
  }

  val consumerCommit = io.gqa_consumer_commit_in.bits
  val commitSlot = consumerCommit.source_instance.instance_coordinate(RouteAAnchorWidths.S2SlotWidth - 1, 0)
  val commitBit = (1.U(4.W) << consumerCommit.consumer_id)(3, 0)
  val commitMatches = initialized && consumerCommit.source_instance.source_kind === RouteASourceKind.Packed.U &&
    slotState(commitSlot) === StateReady &&
    slotGeneration(commitSlot) === consumerCommit.source_instance.generation &&
    slotIdentity(commitSlot).asUInt === consumerCommit.transaction_identity.asUInt &&
    consumerCommit.consumer_id < 4.U && (consumerMask(commitSlot) & commitBit) =/= 0.U
  io.gqa_consumer_commit_in.ready := commitMatches
  when(io.gqa_consumer_commit_in.fire) {
    consumerMask(commitSlot) := consumerMask(commitSlot) & ~commitBit
  }

  val releaseEligible = VecInit((0 until slots).map(slot => slotState(slot) === StateReady && consumerMask(slot) === 0.U))
  val releaseAny = releaseEligible.asUInt.orR
  val releaseSlot = PriorityEncoder(releaseEligible)
  io.s2_release_out.valid := releaseAny
  io.s2_release_out.bits.transaction_identity := slotIdentity(releaseSlot)
  io.s2_release_out.bits.source_instance.source_kind := RouteASourceKind.Packed.U
  io.s2_release_out.bits.source_instance.instance_coordinate := releaseSlot
  io.s2_release_out.bits.source_instance.generation := slotGeneration(releaseSlot)
  when(io.s2_release_out.fire) {
    slotState(releaseSlot) := StateEmpty
    fillOpened(releaseSlot) := false.B
    consumerMask(releaseSlot) := 0.U
  }

  // a_gqa_release: an S2 slot cannot free/reuse until all four matching commits.
  when(io.s2_release_out.valid) {
    assert(slotState(releaseSlot) === StateReady)
    assert(consumerMask(releaseSlot) === 0.U)
  }
  val releaseStalled = io.s2_release_out.valid && !io.s2_release_out.ready
  val heldRelease = RegEnable(io.s2_release_out.bits, releaseStalled)
  when(RegNext(releaseStalled, false.B)) {
    assert(io.s2_release_out.bits.asUInt === heldRelease.asUInt)
  }

  io.s2_observe_state := slotState(io.s2_observe_slot)
  io.s2_observe_generation := slotGeneration(io.s2_observe_slot)
  val locallyDrained = VecInit((0 until slots).map(slot => slotState(slot) === StateEmpty)).asUInt.andR
  io.component_status_out.valid := initialized && io.drain_collection_enable && locallyDrained
  io.component_status_out.bits.acknowledgement_name := p.r6.s2GqaDrainedStatusCode.U
  io.component_status_out.bits.asserted := true.B
}

/** RTL1.2 R2 eligibility, lossless candidate storage, and accepted-grant control. */
final class RouteACoreSideArbiter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_core_side_arbiter"

  val io = IO(new Bundle {
    // Existing ingress retains its compatibility name.  A second logical
    // ingress lets R2 itself, rather than the top, arbitrate a later
    // read-path offer against the active write/maintenance path.
    val candidate_in = Flipped(RouteAChannels.source_candidate(p))
    val read_candidate_in = Flipped(RouteAChannels.source_candidate(p))
    val core_mem_req = RouteAChannels.core_mem_req(p)
    val core_mem_rsp_in = Flipped(RouteAChannels.core_mem_rsp(p))
    val source_delivery_out = RouteAChannels.source_delivery(p)
    val drain_collection_enable = Input(Bool())
    // R6 opens this only for the retirement descriptor-invalidating carrier.
    // It never reopens ordinary data-path candidate ingress during drain.
    val reclaim_maintenance_enable = Input(Bool())
    val payload_drain_status_out = RouteAChannels.component_status(p)
    val descriptor_drain_status_out = RouteAChannels.component_status(p)
  })

  private val readGroups = 3
  private val totalSlots = 6 * p.r2CandidateSlotsPerClass
  private val slotIndexWidth = math.max(1, log2Ceil(totalSlots))
  private val requestIdSlots = 1 << RouteAAnchorWidths.RequestIdWidth

  val slotValid = RegInit(VecInit(Seq.fill(totalSlots)(false.B)))
  val slots = Reg(Vec(totalSlots, new SourceCandidate(p)))
  val readCursor = RegInit(0.U(2.W))
  val outstandingValid = RegInit(VecInit(Seq.fill(requestIdSlots)(false.B)))
  val outstanding = Reg(Vec(requestIdSlots, new SourceCandidate(p)))

  private def predicate(candidate: SourceCandidate, bit: Int): Bool =
    candidate.eligibility_snapshot(bit)

  private def commonReadReady(candidate: SourceCandidate): Bool =
    predicate(candidate, RouteAR2PredicateBits.FifoPredecessor) &&
      predicate(candidate, RouteAR2PredicateBits.Ownership) &&
      predicate(candidate, RouteAR2PredicateBits.SourceCredit) &&
      predicate(candidate, RouteAR2PredicateBits.DestinationReady)

  private def commonWriteReady(candidate: SourceCandidate): Bool =
    predicate(candidate, RouteAR2PredicateBits.FifoPredecessor) &&
      predicate(candidate, RouteAR2PredicateBits.Ownership) &&
      predicate(candidate, RouteAR2PredicateBits.SourceCredit)

  private def isReadClass(candidate: SourceCandidate): Bool =
    candidate.candidate_class === p.r2S2FullClassCode.U ||
      candidate.candidate_class === p.r2S2PackedClassCode.U ||
      candidate.candidate_class === p.r2DirectPendingClassCode.U ||
      candidate.candidate_class === p.r2PackReadClassCode.U

  private def isWriteClass(candidate: SourceCandidate): Bool =
    candidate.candidate_class === p.r2PackWriteClassCode.U ||
      candidate.candidate_class === p.r2DescriptorMaintenanceClassCode.U

  private def readGroup(candidate: SourceCandidate): UInt = Mux(
    candidate.candidate_class === p.r2DirectPendingClassCode.U,
    1.U,
    Mux(candidate.candidate_class === p.r2PackReadClassCode.U, 2.U, 0.U),
  )

  private def isLaunchRequest(candidate: SourceCandidate): Bool =
    candidate.r1_request.request_kind === p.coreMemoryReadRequestCode.U ||
      candidate.r1_request.request_kind === p.coreMemoryWriteRequestCode.U

  private def matchingOutstanding(candidate: SourceCandidate): Bool = {
    val rid = candidate.r1_request.transaction_identity.request_id
    outstandingValid(rid) &&
      outstanding(rid).r1_request.transaction_identity.incarnation === candidate.r1_request.transaction_identity.incarnation
  }

  private def protocolCompatible(candidate: SourceCandidate): Bool = {
    val kind = candidate.r1_request.request_kind
    val readCompatible = isReadClass(candidate) && kind === p.coreMemoryReadRequestCode.U
    val writeCompatible = isWriteClass(candidate) && (
      kind === p.coreMemoryWriteRequestCode.U || kind === p.coreMemoryWriteDataCode.U
    )
    val descriptorFragment = candidate.r1_request.expected_fragment_count === 1.U &&
      candidate.r1_request.fragment_index === 0.U && candidate.r1_request.last
    !(candidate.candidate_class === p.r2DescriptorMaintenanceClassCode.U) || descriptorFragment ||
      kind === p.coreMemoryWriteRequestCode.U && candidate.r1_request.expected_fragment_count === 1.U
  }

  private def candidateEligible(candidate: SourceCandidate): Bool = {
    val c = candidate.candidate_class
    val sourceReady = MuxCase(
      false.B,
      Seq(
        (c === p.r2S2FullClassCode.U) -> commonReadReady(candidate),
        (c === p.r2S2PackedClassCode.U) -> (commonReadReady(candidate) && predicate(candidate, RouteAR2PredicateBits.PackedMetadataPublished)),
        (c === p.r2DirectPendingClassCode.U) -> (commonReadReady(candidate) && predicate(candidate, RouteAR2PredicateBits.PendingAuthoritative)),
        (c === p.r2PackReadClassCode.U) -> (commonReadReady(candidate) && predicate(candidate, RouteAR2PredicateBits.PendingAuthoritative) && predicate(candidate, RouteAR2PredicateBits.P3StageReadyOwned)),
        (c === p.r2PackWriteClassCode.U) -> (commonWriteReady(candidate) && predicate(candidate, RouteAR2PredicateBits.PageAllocated) && predicate(candidate, RouteAR2PredicateBits.P3StageComplete) && predicate(candidate, RouteAR2PredicateBits.P3StageOwned)),
        (c === p.r2DescriptorMaintenanceClassCode.U) -> commonWriteReady(candidate),
      ),
    )
    val rid = candidate.r1_request.transaction_identity.request_id
    val launchAllowed = !isLaunchRequest(candidate) || !outstandingValid(rid)
    val writeDataAllowed = candidate.r1_request.request_kind =/= p.coreMemoryWriteDataCode.U || matchingOutstanding(candidate)
    sourceReady && protocolCompatible(candidate) && launchAllowed && writeDataAllowed
  }

  private def earlier(left: SourceCandidate, right: SourceCandidate): Bool =
    left.arrival_ordinal < right.arrival_ordinal ||
      (left.arrival_ordinal === right.arrival_ordinal && left.candidate_id < right.candidate_id)

  def choose(predicateForSlot: Int => Bool): (Bool, UInt) = {
    var found: Bool = false.B
    var selected: UInt = 0.U(slotIndexWidth.W)
    var bestCandidate: SourceCandidate = 0.U.asTypeOf(new SourceCandidate(p))
    for (index <- 0 until totalSlots) {
      val matchSlot = predicateForSlot(index)
      val take = matchSlot && (!found || earlier(slots(index), bestCandidate))
      selected = Mux(take, index.U(slotIndexWidth.W), selected)
      bestCandidate = Mux(take, slots(index), bestCandidate)
      found = found || matchSlot
    }
    (found, selected)
  }

  var rotatingReadFound: Bool = false.B
  var rotatingReadIndex: UInt = 0.U(slotIndexWidth.W)
  for (offset <- 0 until readGroups) {
    val group = (readCursor + offset.U) % readGroups.U
    val (found, index) = choose(slot => slotValid(slot) && candidateEligible(slots(slot)) && isReadClass(slots(slot)) && readGroup(slots(slot)) === group)
    rotatingReadIndex = Mux(!rotatingReadFound && found, index, rotatingReadIndex)
    rotatingReadFound = rotatingReadFound || found
  }
  val (writeFound, writeIndex) = choose(slot => slotValid(slot) && candidateEligible(slots(slot)) && isWriteClass(slots(slot)))
  val selectedFound = rotatingReadFound || writeFound
  val selectedIndex = Mux(rotatingReadFound, rotatingReadIndex, writeIndex)
  val selectedCandidate = slots(selectedIndex)
  val selectedIsRead = rotatingReadFound
  // A single logical R1 request carrier serializes a simultaneous read/write
  // offer by the frozen ordinal/id order. This never advances read rotation
  // for a write and makes no controller throughput claim.
  val globalWinnerIsRead = WireDefault(selectedIsRead)
  when(rotatingReadFound && writeFound && earlier(slots(writeIndex), slots(rotatingReadIndex))) {
    globalWinnerIsRead := false.B
  }
  val finalIndex = Mux(globalWinnerIsRead, rotatingReadIndex, writeIndex)
  val finalCandidate = slots(finalIndex)
  val finalFound = Mux(globalWinnerIsRead, rotatingReadFound, writeFound)

  io.core_mem_req.valid := finalFound
  io.core_mem_req.bits := finalCandidate.r1_request

  val selectedRequestStalled = io.core_mem_req.valid && !io.core_mem_req.ready
  val anyFreeSlot = !slotValid.reduce(_ && _)
  private def ingressReady(candidate: SourceCandidate): Bool = {
    val classCount = PopCount((0 until totalSlots).map { slot =>
      slotValid(slot) && slots(slot).candidate_class === candidate.candidate_class
    })
    val reclaimDescriptorCandidate = candidate.candidate_class === p.r2DescriptorMaintenanceClassCode.U
    val ingressAllowed = !io.drain_collection_enable ||
      (io.reclaim_maintenance_enable && reclaimDescriptorCandidate)
    ingressAllowed && !selectedRequestStalled && candidateEligible(candidate) && anyFreeSlot &&
      classCount < p.r2CandidateSlotsPerClass.U
  }

  val legacyAcceptable = io.candidate_in.valid && ingressReady(io.candidate_in.bits)
  val readAcceptable = io.read_candidate_in.valid && ingressReady(io.read_candidate_in.bits)
  // This is candidate acceptance inside R2, not a top-level mux or a second
  // scheduler.  It preserves the already-frozen ordinal/id rule whenever both
  // logical ingress carriers are simultaneously acceptable.
  val readIngressWins = readAcceptable &&
    (!legacyAcceptable || earlier(io.read_candidate_in.bits, io.candidate_in.bits))
  io.candidate_in.ready := legacyAcceptable && !readIngressWins
  io.read_candidate_in.ready := readAcceptable && readIngressWins
  val acceptedIncoming = Mux(readIngressWins, io.read_candidate_in.bits, io.candidate_in.bits)
  val incomingFire = io.read_candidate_in.fire || io.candidate_in.fire

  when(incomingFire) {
    val freeIndex = PriorityEncoder(VecInit(slotValid.map(! _)))
    slotValid(freeIndex) := true.B
    slots(freeIndex) := acceptedIncoming
  }

  when(io.core_mem_req.fire) {
    slotValid(finalIndex) := false.B
    when(isLaunchRequest(finalCandidate)) {
      val rid = finalCandidate.r1_request.transaction_identity.request_id
      outstandingValid(rid) := true.B
      outstanding(rid) := finalCandidate
    }
    when(globalWinnerIsRead) {
      readCursor := (readGroup(finalCandidate) + 1.U) % readGroups.U
    }
  }

  val response = io.core_mem_rsp_in.bits
  val responseRid = response.transaction_identity.request_id
  val matchingResponse = outstandingValid(responseRid) &&
    outstanding(responseRid).r1_request.transaction_identity.incarnation === response.transaction_identity.incarnation
  io.source_delivery_out.valid := io.core_mem_rsp_in.valid && matchingResponse
  io.source_delivery_out.bits.candidate_id := outstanding(responseRid).candidate_id
  io.source_delivery_out.bits.candidate_class := outstanding(responseRid).candidate_class
  io.source_delivery_out.bits.destination := outstanding(responseRid).r1_request.destination
  io.source_delivery_out.bits.delivery_context_ref := outstanding(responseRid).delivery_context_ref
  io.source_delivery_out.bits.r1_response := response
  io.core_mem_rsp_in.ready := !matchingResponse || io.source_delivery_out.ready

  when(io.source_delivery_out.fire && response.last) {
    outstandingValid(responseRid) := false.B
  }

  // R2 is the only upstream issuer for R1. During retirement ordinary
  // candidate acceptance stops; I4 permits only R5's descriptor-invalidating
  // maintenance carrier after R6's explicit permit. The two named facts retain
  // the frozen payload/descriptor distinction; no physical FIFO or service-rate
  // interpretation is implied.
  val payloadSlotsLive = VecInit((0 until totalSlots).map(slot =>
    slotValid(slot) && slots(slot).candidate_class =/= p.r2DescriptorMaintenanceClassCode.U,
  )).asUInt.orR
  val descriptorSlotsLive = VecInit((0 until totalSlots).map(slot =>
    slotValid(slot) && slots(slot).candidate_class === p.r2DescriptorMaintenanceClassCode.U,
  )).asUInt.orR
  val payloadOutstandingLive = VecInit((0 until requestIdSlots).map(rid =>
    outstandingValid(rid) && outstanding(rid).candidate_class =/= p.r2DescriptorMaintenanceClassCode.U,
  )).asUInt.orR
  val descriptorOutstandingLive = VecInit((0 until requestIdSlots).map(rid =>
    outstandingValid(rid) && outstanding(rid).candidate_class === p.r2DescriptorMaintenanceClassCode.U,
  )).asUInt.orR
  val payloadDrained = !payloadSlotsLive && !payloadOutstandingLive
  val descriptorDrained = !descriptorSlotsLive && !descriptorOutstandingLive
  io.payload_drain_status_out.valid := io.drain_collection_enable && payloadDrained
  io.payload_drain_status_out.bits.acknowledgement_name := p.r6.r2PayloadDrainedStatusCode.U
  io.payload_drain_status_out.bits.asserted := true.B
  io.descriptor_drain_status_out.valid := io.drain_collection_enable && descriptorDrained
  io.descriptor_drain_status_out.bits.acknowledgement_name := p.r6.r2DescriptorDrainedStatusCode.U
  io.descriptor_drain_status_out.bits.asserted := true.B

  // a_ready_low_nonmutation: grant cursor and selected request do not move on
  // valid-without-ready. Candidate intake is explicitly backpressured there.
  val priorStall = RegNext(selectedRequestStalled, false.B)
  val heldCursor = RegEnable(readCursor, selectedRequestStalled)
  val heldRequest = RegEnable(io.core_mem_req.bits, selectedRequestStalled)
  when(priorStall) {
    assert(readCursor === heldCursor)
    assert(io.core_mem_req.bits.asUInt === heldRequest.asUInt)
  }
  // a_fifo_credit_losslessness: each issue arises from an eligible stored
  // candidate; a reservation is represented by exactly one outstanding RID.
  when(io.core_mem_req.fire) {
    assert(candidateEligible(finalCandidate))
  }
  when(io.source_delivery_out.fire && response.last) {
    assert(matchingResponse)
  }
  val readIngressStalled = io.read_candidate_in.valid && !io.read_candidate_in.ready
  val heldReadIngress = RegEnable(io.read_candidate_in.bits, readIngressStalled)
  when(RegNext(readIngressStalled, false.B)) {
    assert(io.read_candidate_in.bits.asUInt === heldReadIngress.asUInt)
  }
}

/**
  * RTL2.3.1 producer-local read issue refinement.  It translates only a
  * named owner's immutable ReadIssueDescriptor into the pre-existing R2
  * SourceCandidate carrier.  It contains no queue, arbitration, identity
  * allocation, response handling, endpoint deposition, or authority state.
  * The production top deliberately does not instantiate it until a later
  * read-ingress closure names and connects all producer lanes.
  */
final class RouteAReadIssueCandidateAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_read_issue_candidate_adapter"

  val io = IO(new Bundle {
    val read_issue_in = Flipped(RouteAChannels.read_issue_descriptor(p))
    val candidate_out = RouteAChannels.source_candidate(p)
  })

  val issue = io.read_issue_in.bits
  val isReadClass = issue.candidate_class === p.r2S2FullClassCode.U ||
    issue.candidate_class === p.r2S2PackedClassCode.U ||
    issue.candidate_class === p.r2DirectPendingClassCode.U ||
    issue.candidate_class === p.r2PackReadClassCode.U
  val isCoreReadSource = issue.source_kind =/= RouteASourceKind.Hot.U
  val validCountLegal = issue.valid_count =/= 0.U && issue.valid_count <= 64.U
  val fragmentsLegal = issue.expected_fragment_count =/= 0.U
  val notExplicitEmpty = !issue.target_descriptor.pending_explicit_empty
  val issueLegal = isReadClass && isCoreReadSource && validCountLegal && fragmentsLegal && notExplicitEmpty

  io.candidate_out.valid := io.read_issue_in.valid && issueLegal
  io.candidate_out.bits := 0.U.asTypeOf(new SourceCandidate(p))
  io.candidate_out.bits.candidate_class := issue.candidate_class
  io.candidate_out.bits.arrival_ordinal := issue.arrival_ordinal
  io.candidate_out.bits.candidate_id := issue.candidate_id
  io.candidate_out.bits.eligibility_snapshot := issue.eligibility_snapshot
  io.candidate_out.bits.delivery_context_ref := issue.delivery_context_ref
  io.candidate_out.bits.delivery_target_descriptor := issue.target_descriptor
  io.candidate_out.bits.r1_request.transaction_identity := issue.transaction_identity
  io.candidate_out.bits.r1_request.request_kind := p.coreMemoryReadRequestCode.U
  io.candidate_out.bits.r1_request.destination := issue.destination_endpoint
  io.candidate_out.bits.r1_request.address_ref := issue.payload_handle_or_address
  io.candidate_out.bits.r1_request.expected_fragment_count := issue.expected_fragment_count
  io.candidate_out.bits.r1_request.fragment_index := 0.U
  io.candidate_out.bits.r1_request.last := false.B
  io.candidate_out.bits.r1_request.data := 0.U
  io.read_issue_in.ready := io.candidate_out.ready && issueLegal

  val held = RegEnable(io.candidate_out.bits, io.candidate_out.valid && !io.candidate_out.ready)
  when(RegNext(io.candidate_out.valid && !io.candidate_out.ready, false.B)) {
    assert(io.candidate_out.bits.asUInt === held.asUInt)
  }
}

/**
  * RTL2.1b logical multi-producer ingress for the sole R2 FIFO owner.  It is
  * a lossless ready/valid merge, not a second FIFO, scheduler, or controller.
  * Among simultaneously offered candidates it selects the frozen ordinal/id
  * order; candidates not selected remain held by their unique producer.
  */
final class RouteAR2WriteIngressMerge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_r2_write_ingress_merge"

  val io = IO(new Bundle {
    val r3_packed_write_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_append_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_reclaim_in = Flipped(RouteAChannels.source_candidate(p))
    val candidate_out = RouteAChannels.source_candidate(p)
  })

  private def earlier(left: SourceCandidate, right: SourceCandidate): Bool =
    left.arrival_ordinal < right.arrival_ordinal ||
      (left.arrival_ordinal === right.arrival_ordinal && left.candidate_id < right.candidate_id)

  val inputs = Seq(io.r3_packed_write_in, io.r5_append_in, io.r5_reclaim_in)
  val validVec = VecInit(inputs.map(_.valid))
  val first = Wire(new SourceCandidate(p)); first := io.r3_packed_write_in.bits
  val chooseR3 = io.r3_packed_write_in.valid &&
    (!io.r5_append_in.valid || earlier(io.r3_packed_write_in.bits, io.r5_append_in.bits)) &&
    (!io.r5_reclaim_in.valid || earlier(io.r3_packed_write_in.bits, io.r5_reclaim_in.bits))
  val chooseAppend = !chooseR3 && io.r5_append_in.valid &&
    (!io.r5_reclaim_in.valid || earlier(io.r5_append_in.bits, io.r5_reclaim_in.bits))
  val chooseReclaim = !chooseR3 && !chooseAppend && io.r5_reclaim_in.valid
  io.candidate_out.valid := validVec.asUInt.orR
  io.candidate_out.bits := Mux(chooseR3, io.r3_packed_write_in.bits,
    Mux(chooseAppend, io.r5_append_in.bits, io.r5_reclaim_in.bits))
  io.r3_packed_write_in.ready := io.candidate_out.ready && chooseR3
  io.r5_append_in.ready := io.candidate_out.ready && chooseAppend
  io.r5_reclaim_in.ready := io.candidate_out.ready && chooseReclaim

  val held = RegEnable(io.candidate_out.bits, io.candidate_out.valid && !io.candidate_out.ready)
  when(RegNext(io.candidate_out.valid && !io.candidate_out.ready, false.B)) {
    assert(io.candidate_out.bits.asUInt === held.asUInt)
  }
}

/**
  * RTL2.3.2 lossless pre-R2 merge for the Route-A incremental read lanes.
  * It applies only the frozen producer-supplied ordinal/id comparison in order
  * to present one carrier to the existing R2 FIFO owner; it has no storage,
  * credit, cursor, request, or response state and does not replace R2's read
  * rotation/arbitration.
  */
final class RouteAR2ReadIngressMerge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_r2_read_ingress_merge"

  val io = IO(new Bundle {
    val r3_pack_read_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_direct_pending_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_s2_packed_in = Flipped(RouteAChannels.source_candidate(p))
    val candidate_out = RouteAChannels.source_candidate(p)
  })

  private def earlier(left: SourceCandidate, right: SourceCandidate): Bool =
    left.arrival_ordinal < right.arrival_ordinal ||
      (left.arrival_ordinal === right.arrival_ordinal && left.candidate_id < right.candidate_id)

  val inputs = Seq(io.r3_pack_read_in, io.r3_direct_pending_in, io.r5_s2_packed_in)
  val validVec = VecInit(inputs.map(_.valid))
  val choosePack = io.r3_pack_read_in.valid &&
    (!io.r3_direct_pending_in.valid || earlier(io.r3_pack_read_in.bits, io.r3_direct_pending_in.bits)) &&
    (!io.r5_s2_packed_in.valid || earlier(io.r3_pack_read_in.bits, io.r5_s2_packed_in.bits))
  val chooseDirect = !choosePack && io.r3_direct_pending_in.valid &&
    (!io.r5_s2_packed_in.valid || earlier(io.r3_direct_pending_in.bits, io.r5_s2_packed_in.bits))
  val choosePacked = !choosePack && !chooseDirect && io.r5_s2_packed_in.valid
  io.candidate_out.valid := validVec.asUInt.orR
  io.candidate_out.bits := Mux(choosePack, io.r3_pack_read_in.bits,
    Mux(chooseDirect, io.r3_direct_pending_in.bits, io.r5_s2_packed_in.bits))
  io.r3_pack_read_in.ready := io.candidate_out.ready && choosePack
  io.r3_direct_pending_in.ready := io.candidate_out.ready && chooseDirect
  io.r5_s2_packed_in.ready := io.candidate_out.ready && choosePacked

  val held = RegEnable(io.candidate_out.bits, io.candidate_out.valid && !io.candidate_out.ready)
  when(RegNext(io.candidate_out.valid && !io.candidate_out.ready, false.B)) {
    assert(io.candidate_out.bits.asUInt === held.asUInt)
  }
}

/**
 * Sole pre-R2 allocation bridge for the three already-existing write
  * producers. It owns no association or R2 ordering decision: the registry
  * owns refs, and the existing write-ingress merge still applies the frozen
  * `(arrival_ordinal, candidate_id)` rule after the opaque ref is bound.
  */
final class RouteADeliveryContextAllocationBridge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_delivery_context_allocation_bridge"

  val io = IO(new Bundle {
    val r3_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_append_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_reclaim_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_out = RouteAChannels.source_candidate(p)
    val r5_append_out = RouteAChannels.source_candidate(p)
    val r5_reclaim_out = RouteAChannels.source_candidate(p)
    val registry_allocate_out = RouteAChannels.delivery_context_allocate(p)
    val registry_allocation_ack_in = Flipped(RouteAChannels.delivery_context_allocation_ack(p))
    val release_event_in = Input(Valid(new DeliveryContextRelease(p)))
  })

  private val producerCount = 3
  val inputs = Seq(io.r3_in, io.r5_append_in, io.r5_reclaim_in)
  val outputs = Seq(io.r3_out, io.r5_append_out, io.r5_reclaim_out)
  val bound = RegInit(VecInit(Seq.fill(producerCount)(false.B)))
  val awaitingRelease = RegInit(VecInit(Seq.fill(producerCount)(false.B)))
  val captured = Reg(Vec(producerCount, new SourceCandidate(p)))
  val refs = Reg(Vec(producerCount, UInt(p.sourceDeliveryOpaqueWidth.W)))
  val allocationActive = RegInit(false.B)
  val allocationProducer = Reg(UInt(2.W))

  private def earlier(left: SourceCandidate, right: SourceCandidate): Bool =
    left.arrival_ordinal < right.arrival_ordinal ||
      (left.arrival_ordinal === right.arrival_ordinal && left.candidate_id < right.candidate_id)
  private def targetKind(candidate: SourceCandidate): UInt = MuxCase(0.U(RouteADeliveryTargetKind.Width.W), Seq(
    (candidate.candidate_class === p.r2PackReadClassCode.U) -> RouteADeliveryTargetKind.P3PendingRead.U,
    (candidate.candidate_class === p.r2S2FullClassCode.U) -> RouteADeliveryTargetKind.S2FullFill.U,
    (candidate.candidate_class === p.r2S2PackedClassCode.U) -> RouteADeliveryTargetKind.S2PackedFill.U,
    (candidate.candidate_class === p.r2DirectPendingClassCode.U) -> RouteADeliveryTargetKind.DirectPendingRead.U,
    (candidate.candidate_class === p.r2PackWriteClassCode.U) -> RouteADeliveryTargetKind.PackedWriteTerminal.U,
    (candidate.candidate_class === p.r2DescriptorMaintenanceClassCode.U) -> RouteADeliveryTargetKind.DescriptorMaintenanceTerminal.U,
  ))

  var found: Bool = false.B
  var selected = 0.U(2.W)
  var best = 0.U.asTypeOf(new SourceCandidate(p))
  for (index <- 0 until producerCount) {
    val eligible = inputs(index).valid && !bound(index) && !awaitingRelease(index)
    val take = eligible && (!found || earlier(inputs(index).bits, best))
    selected = Mux(take, index.U, selected)
    best = Mux(take, inputs(index).bits, best)
    found = found || eligible
  }

  io.registry_allocate_out.valid := !allocationActive && found
  io.registry_allocate_out.bits.candidate_class := best.candidate_class
  io.registry_allocate_out.bits.transaction_identity := best.r1_request.transaction_identity
  io.registry_allocate_out.bits.target_kind := targetKind(best)
  io.registry_allocate_out.bits.target_identity_generation := best.delivery_target_descriptor.source_generation
  io.registry_allocate_out.bits.expected_fragment_count := best.r1_request.expected_fragment_count
  io.registry_allocate_out.bits.target_descriptor := best.delivery_target_descriptor
  io.registry_allocation_ack_in.ready := allocationActive

  when(io.registry_allocate_out.fire) {
    captured(selected) := best
    allocationProducer := selected
    allocationActive := true.B
  }
  when(io.registry_allocation_ack_in.fire) {
    val pending = allocationProducer
    assert(io.registry_allocation_ack_in.bits.allocation.candidate_class === captured(pending).candidate_class)
    assert(io.registry_allocation_ack_in.bits.allocation.transaction_identity.asUInt ===
      captured(pending).r1_request.transaction_identity.asUInt)
    assert(io.registry_allocation_ack_in.bits.allocation.expected_fragment_count ===
      captured(pending).r1_request.expected_fragment_count)
    assert(io.registry_allocation_ack_in.bits.allocation.target_descriptor.asUInt ===
      captured(pending).delivery_target_descriptor.asUInt)
    refs(pending) := io.registry_allocation_ack_in.bits.delivery_context_ref
    bound(pending) := true.B
    allocationActive := false.B
  }

  for (index <- 0 until producerCount) {
    outputs(index).valid := bound(index) && !awaitingRelease(index)
    outputs(index).bits := captured(index)
    outputs(index).bits.delivery_context_ref := refs(index)
    inputs(index).ready := outputs(index).fire
    when(outputs(index).fire) {
      bound(index) := false.B
      awaitingRelease(index) := true.B
    }
    when(io.release_event_in.valid && awaitingRelease(index) &&
      io.release_event_in.bits.delivery_context_ref === refs(index)) {
      assert(io.release_event_in.bits.allocation.candidate_class === captured(index).candidate_class)
      assert(io.release_event_in.bits.allocation.transaction_identity.asUInt ===
        captured(index).r1_request.transaction_identity.asUInt)
      awaitingRelease(index) := false.B
    }
  }
}

/**
  * RTL2.3.2 read-lane counterpart to the write allocation bridge.  It only
  * serializes registry allocation for R3 pack-read/direct-pending and R5
  * packed-S2 producers.  It neither owns the opaque associations, selects an
  * R2 grant, launches R1, nor accepts/delivers a response.
  */
final class RouteAReadDeliveryContextAllocationBridge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_read_delivery_context_allocation_bridge"

  val io = IO(new Bundle {
    val r3_pack_read_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_direct_pending_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_s2_packed_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_pack_read_out = RouteAChannels.source_candidate(p)
    val r3_direct_pending_out = RouteAChannels.source_candidate(p)
    val r5_s2_packed_out = RouteAChannels.source_candidate(p)
    val registry_allocate_out = RouteAChannels.delivery_context_allocate(p)
    val registry_allocation_ack_in = Flipped(RouteAChannels.delivery_context_allocation_ack(p))
    val release_event_in = Input(Valid(new DeliveryContextRelease(p)))
  })

  private val producerCount = 3
  val inputs = Seq(io.r3_pack_read_in, io.r3_direct_pending_in, io.r5_s2_packed_in)
  val outputs = Seq(io.r3_pack_read_out, io.r3_direct_pending_out, io.r5_s2_packed_out)
  val bound = RegInit(VecInit(Seq.fill(producerCount)(false.B)))
  val awaitingRelease = RegInit(VecInit(Seq.fill(producerCount)(false.B)))
  val captured = Reg(Vec(producerCount, new SourceCandidate(p)))
  val refs = Reg(Vec(producerCount, UInt(p.sourceDeliveryOpaqueWidth.W)))
  val allocationActive = RegInit(false.B)
  val allocationProducer = Reg(UInt(2.W))

  private def earlier(left: SourceCandidate, right: SourceCandidate): Bool =
    left.arrival_ordinal < right.arrival_ordinal ||
      (left.arrival_ordinal === right.arrival_ordinal && left.candidate_id < right.candidate_id)
  private def targetKind(candidate: SourceCandidate): UInt = MuxCase(0.U(RouteADeliveryTargetKind.Width.W), Seq(
    (candidate.candidate_class === p.r2PackReadClassCode.U) -> RouteADeliveryTargetKind.P3PendingRead.U,
    (candidate.candidate_class === p.r2DirectPendingClassCode.U) -> RouteADeliveryTargetKind.DirectPendingRead.U,
    (candidate.candidate_class === p.r2S2PackedClassCode.U) -> RouteADeliveryTargetKind.S2PackedFill.U,
  ))
  private def legalReadCandidate(candidate: SourceCandidate): Bool = {
    val readClass = candidate.candidate_class === p.r2PackReadClassCode.U ||
      candidate.candidate_class === p.r2DirectPendingClassCode.U ||
      candidate.candidate_class === p.r2S2PackedClassCode.U
    readClass && candidate.r1_request.request_kind === p.coreMemoryReadRequestCode.U &&
      candidate.r1_request.expected_fragment_count =/= 0.U
  }

  var found: Bool = false.B
  var selected = 0.U(2.W)
  var best = 0.U.asTypeOf(new SourceCandidate(p))
  for (index <- 0 until producerCount) {
    val eligible = inputs(index).valid && legalReadCandidate(inputs(index).bits) && !bound(index) && !awaitingRelease(index)
    val take = eligible && (!found || earlier(inputs(index).bits, best))
    selected = Mux(take, index.U, selected)
    best = Mux(take, inputs(index).bits, best)
    found = found || eligible
  }

  io.registry_allocate_out.valid := !allocationActive && found
  io.registry_allocate_out.bits.candidate_class := best.candidate_class
  io.registry_allocate_out.bits.transaction_identity := best.r1_request.transaction_identity
  io.registry_allocate_out.bits.target_kind := targetKind(best)
  io.registry_allocate_out.bits.target_identity_generation := best.delivery_target_descriptor.source_generation
  io.registry_allocate_out.bits.expected_fragment_count := best.r1_request.expected_fragment_count
  io.registry_allocate_out.bits.target_descriptor := best.delivery_target_descriptor
  io.registry_allocation_ack_in.ready := allocationActive

  when(io.registry_allocate_out.fire) {
    captured(selected) := best
    allocationProducer := selected
    allocationActive := true.B
  }
  when(io.registry_allocation_ack_in.fire) {
    val pending = allocationProducer
    assert(io.registry_allocation_ack_in.bits.allocation.candidate_class === captured(pending).candidate_class)
    assert(io.registry_allocation_ack_in.bits.allocation.transaction_identity.asUInt ===
      captured(pending).r1_request.transaction_identity.asUInt)
    assert(io.registry_allocation_ack_in.bits.allocation.expected_fragment_count ===
      captured(pending).r1_request.expected_fragment_count)
    assert(io.registry_allocation_ack_in.bits.allocation.target_descriptor.asUInt ===
      captured(pending).delivery_target_descriptor.asUInt)
    refs(pending) := io.registry_allocation_ack_in.bits.delivery_context_ref
    bound(pending) := true.B
    allocationActive := false.B
  }

  for (index <- 0 until producerCount) {
    outputs(index).valid := bound(index) && !awaitingRelease(index)
    outputs(index).bits := captured(index)
    outputs(index).bits.delivery_context_ref := refs(index)
    inputs(index).ready := outputs(index).fire
    when(outputs(index).fire) {
      bound(index) := false.B
      awaitingRelease(index) := true.B
    }
    when(io.release_event_in.valid && awaitingRelease(index) &&
      io.release_event_in.bits.delivery_context_ref === refs(index)) {
      assert(io.release_event_in.bits.allocation.candidate_class === captured(index).candidate_class)
      assert(io.release_event_in.bits.allocation.transaction_identity.asUInt ===
        captured(index).r1_request.transaction_identity.asUInt)
      awaitingRelease(index) := false.B
    }
  }
}

/**
  * RTL2.3-C1 sole production composition point before the already-sole
  * delivery-context registry.  It receives all six frozen producer lanes,
  * serializes only immutable association allocation by existing ordinal/id,
  * and returns each bound candidate to its class-specific pre-R2 ingress.
  * It owns neither the association table (registry), R2 grant/rotation/FIFO,
  * R1 request lifecycle, payload, endpoint, authority, nor source service.
  */
final class RouteAUnifiedDeliveryContextAllocationBridge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_unified_delivery_context_allocation_bridge"

  val io = IO(new Bundle {
    val r3_pack_read_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_direct_pending_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_s2_packed_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_packed_write_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_append_in = Flipped(RouteAChannels.source_candidate(p))
    val r5_reclaim_in = Flipped(RouteAChannels.source_candidate(p))
    val r3_pack_read_out = RouteAChannels.source_candidate(p)
    val r3_direct_pending_out = RouteAChannels.source_candidate(p)
    val r5_s2_packed_out = RouteAChannels.source_candidate(p)
    val r3_packed_write_out = RouteAChannels.source_candidate(p)
    val r5_append_out = RouteAChannels.source_candidate(p)
    val r5_reclaim_out = RouteAChannels.source_candidate(p)
    val registry_allocate_out = RouteAChannels.delivery_context_allocate(p)
    val registry_allocation_ack_in = Flipped(RouteAChannels.delivery_context_allocation_ack(p))
    val release_event_in = Input(Valid(new DeliveryContextRelease(p)))
  })

  private val producerCount = 6
  private val producerIndexWidth = log2Ceil(producerCount)
  val inputs = Seq(
    io.r3_pack_read_in, io.r3_direct_pending_in, io.r5_s2_packed_in,
    io.r3_packed_write_in, io.r5_append_in, io.r5_reclaim_in,
  )
  val outputs = Seq(
    io.r3_pack_read_out, io.r3_direct_pending_out, io.r5_s2_packed_out,
    io.r3_packed_write_out, io.r5_append_out, io.r5_reclaim_out,
  )
  val bound = RegInit(VecInit(Seq.fill(producerCount)(false.B)))
  val awaitingRelease = RegInit(VecInit(Seq.fill(producerCount)(false.B)))
  val captured = Reg(Vec(producerCount, new SourceCandidate(p)))
  val refs = Reg(Vec(producerCount, UInt(p.sourceDeliveryOpaqueWidth.W)))
  val allocationActive = RegInit(false.B)
  val allocationProducer = Reg(UInt(producerIndexWidth.W))

  private def earlier(left: SourceCandidate, right: SourceCandidate): Bool =
    left.arrival_ordinal < right.arrival_ordinal ||
      (left.arrival_ordinal === right.arrival_ordinal && left.candidate_id < right.candidate_id)
  private def targetKind(candidate: SourceCandidate): UInt = MuxCase(0.U(RouteADeliveryTargetKind.Width.W), Seq(
    (candidate.candidate_class === p.r2PackReadClassCode.U) -> RouteADeliveryTargetKind.P3PendingRead.U,
    (candidate.candidate_class === p.r2S2FullClassCode.U) -> RouteADeliveryTargetKind.S2FullFill.U,
    (candidate.candidate_class === p.r2S2PackedClassCode.U) -> RouteADeliveryTargetKind.S2PackedFill.U,
    (candidate.candidate_class === p.r2DirectPendingClassCode.U) -> RouteADeliveryTargetKind.DirectPendingRead.U,
    (candidate.candidate_class === p.r2PackWriteClassCode.U) -> RouteADeliveryTargetKind.PackedWriteTerminal.U,
    (candidate.candidate_class === p.r2DescriptorMaintenanceClassCode.U) -> RouteADeliveryTargetKind.DescriptorMaintenanceTerminal.U,
  ))
  private val expectedLaneClasses = Seq(
    p.r2PackReadClassCode,
    p.r2DirectPendingClassCode,
    p.r2S2PackedClassCode,
    p.r2PackWriteClassCode,
    p.r2DescriptorMaintenanceClassCode,
    p.r2DescriptorMaintenanceClassCode,
  )

  var found: Bool = false.B
  var selected = 0.U(producerIndexWidth.W)
  var best = 0.U.asTypeOf(new SourceCandidate(p))
  for (index <- 0 until producerCount) {
    // A class may be legal at R2 yet illegal on this named owner lane.  This
    // closes the route-a producer ownership boundary before the shared bridge
    // can allocate an association for a misdirected carrier.
    val laneClassMatches = inputs(index).bits.candidate_class === expectedLaneClasses(index).U
    val eligible = inputs(index).valid && laneClassMatches && !bound(index) && !awaitingRelease(index)
    val take = eligible && (!found || earlier(inputs(index).bits, best))
    selected = Mux(take, index.U(producerIndexWidth.W), selected)
    best = Mux(take, inputs(index).bits, best)
    found = found || eligible
  }

  io.registry_allocate_out.valid := !allocationActive && found
  io.registry_allocate_out.bits.candidate_class := best.candidate_class
  io.registry_allocate_out.bits.transaction_identity := best.r1_request.transaction_identity
  io.registry_allocate_out.bits.target_kind := targetKind(best)
  io.registry_allocate_out.bits.target_identity_generation := best.delivery_target_descriptor.source_generation
  io.registry_allocate_out.bits.expected_fragment_count := best.r1_request.expected_fragment_count
  io.registry_allocate_out.bits.target_descriptor := best.delivery_target_descriptor
  io.registry_allocation_ack_in.ready := allocationActive

  when(io.registry_allocate_out.fire) {
    captured(selected) := best
    allocationProducer := selected
    allocationActive := true.B
  }
  when(io.registry_allocation_ack_in.fire) {
    val pending = allocationProducer
    assert(io.registry_allocation_ack_in.bits.allocation.candidate_class === captured(pending).candidate_class)
    assert(io.registry_allocation_ack_in.bits.allocation.transaction_identity.asUInt ===
      captured(pending).r1_request.transaction_identity.asUInt)
    assert(io.registry_allocation_ack_in.bits.allocation.expected_fragment_count ===
      captured(pending).r1_request.expected_fragment_count)
    assert(io.registry_allocation_ack_in.bits.allocation.target_descriptor.asUInt ===
      captured(pending).delivery_target_descriptor.asUInt)
    refs(pending) := io.registry_allocation_ack_in.bits.delivery_context_ref
    bound(pending) := true.B
    allocationActive := false.B
  }

  for (index <- 0 until producerCount) {
    outputs(index).valid := bound(index) && !awaitingRelease(index)
    outputs(index).bits := captured(index)
    outputs(index).bits.delivery_context_ref := refs(index)
    inputs(index).ready := outputs(index).fire
    when(outputs(index).fire) {
      bound(index) := false.B
      awaitingRelease(index) := true.B
    }
    when(io.release_event_in.valid && awaitingRelease(index) &&
      io.release_event_in.bits.delivery_context_ref === refs(index)) {
      assert(io.release_event_in.bits.allocation.candidate_class === captured(index).candidate_class)
      assert(io.release_event_in.bits.allocation.transaction_identity.asUInt ===
        captured(index).r1_request.transaction_identity.asUInt)
      awaitingRelease(index) := false.B
    }
  }
}

/**
  * Registry-resolved typed delivery router. It cannot reconstruct an endpoint
  * from R1 response fields: every legal route is selected from the registry's
  * stored target kind and descriptor. Read endpoints are exposed as typed
  * handoffs only; their functional storage/transport activation remains later
  * RTL2 work.
  */
final class RouteATypedDeliveryRouter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_typed_delivery_router"

  val io = IO(new Bundle {
    val resolved_in = Flipped(RouteAChannels.resolved_delivery(p))
    val r3_packed_write_out = RouteAChannels.source_delivery(p)
    val r5_append_out = RouteAChannels.source_delivery(p)
    val r5_reclaim_out = RouteAChannels.source_delivery(p)
    val read_fragment_out = RouteAChannels.resolved_delivery(p)
    val release_out = RouteAChannels.delivery_context_release(p)
    val release_event_out = Output(Valid(new DeliveryContextRelease(p)))
  })

  val resolved = io.resolved_in.bits
  val source = resolved.source_delivery
  val allocation = resolved.allocation
  val descriptor = allocation.target_descriptor
  val isR3 = source.candidate_class === p.r2PackWriteClassCode.U &&
    allocation.target_kind === RouteADeliveryTargetKind.PackedWriteTerminal.U &&
    descriptor.write_endpoint === RouteAWriteDeliveryEndpoint.P3PackedWrite.U && source.r1_response.last
  val isAppend = source.candidate_class === p.r2DescriptorMaintenanceClassCode.U &&
    allocation.target_kind === RouteADeliveryTargetKind.DescriptorMaintenanceTerminal.U &&
    descriptor.write_endpoint === RouteAWriteDeliveryEndpoint.R5Append.U && source.r1_response.last
  val isReclaim = source.candidate_class === p.r2DescriptorMaintenanceClassCode.U &&
    allocation.target_kind === RouteADeliveryTargetKind.DescriptorMaintenanceTerminal.U &&
    descriptor.write_endpoint === RouteAWriteDeliveryEndpoint.R5Reclaim.U && source.r1_response.last
  val isRead = (source.candidate_class === p.r2PackReadClassCode.U &&
      allocation.target_kind === RouteADeliveryTargetKind.P3PendingRead.U) ||
    (source.candidate_class === p.r2S2FullClassCode.U &&
      allocation.target_kind === RouteADeliveryTargetKind.S2FullFill.U) ||
    (source.candidate_class === p.r2S2PackedClassCode.U &&
      allocation.target_kind === RouteADeliveryTargetKind.S2PackedFill.U) ||
    (source.candidate_class === p.r2DirectPendingClassCode.U &&
      allocation.target_kind === RouteADeliveryTargetKind.DirectPendingRead.U)

  io.r3_packed_write_out.valid := io.resolved_in.valid && isR3
  io.r3_packed_write_out.bits := source
  io.r5_append_out.valid := io.resolved_in.valid && isAppend
  io.r5_append_out.bits := source
  io.r5_reclaim_out.valid := io.resolved_in.valid && isReclaim
  io.r5_reclaim_out.bits := source
  io.read_fragment_out.valid := io.resolved_in.valid && isRead
  io.read_fragment_out.bits := resolved

  val releasePending = RegInit(false.B)
  val release = Reg(new DeliveryContextRelease(p))
  val routeReady = Mux(isR3, io.r3_packed_write_out.ready,
    Mux(isAppend, io.r5_append_out.ready,
      Mux(isReclaim, io.r5_reclaim_out.ready,
        Mux(isRead, io.read_fragment_out.ready, false.B))))
  io.resolved_in.ready := !releasePending && routeReady
  when(io.resolved_in.fire && source.r1_response.last) {
    releasePending := true.B
    release.delivery_context_ref := source.delivery_context_ref
    release.allocation := allocation
  }
  io.release_out.valid := releasePending
  io.release_out.bits := release
  io.release_event_out.valid := io.release_out.fire
  io.release_event_out.bits := release
  when(io.release_out.fire) { releasePending := false.B }

  val heldRelease = RegEnable(io.release_out.bits, io.release_out.valid && !io.release_out.ready)
  when(RegNext(io.release_out.valid && !io.release_out.ready, false.B)) {
    assert(io.release_out.bits.asUInt === heldRelease.asUInt)
  }
}

/**
  * RTL2.3-C2 endpoint for a registry-resolved R3 pending-member pack read.
  * It translates only an exact typed response into P3's existing logical
  * fragment carrier.  It owns no association, source scheduling, P3 state,
  * sidecar, authority, retry, fallback, or data transformation.  A malformed,
  * stale, mismatched, or non-terminal fault response remains backpressured and
  * cannot deposit functional P3 payload data.
  */
final class RouteAR3PackReadEndpoint(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_r3_pack_read_endpoint"

  val io = IO(new Bundle {
    val resolved_fragment_in = Flipped(RouteAChannels.resolved_delivery(p))
    val p3_pending_fragment_out = RouteAChannels.p3_pending_fragment(p)
  })

  val resolved = io.resolved_fragment_in.bits
  val source = resolved.source_delivery
  val allocation = resolved.allocation
  val descriptor = allocation.target_descriptor
  val response = source.r1_response
  val expectedEightFragments = allocation.expected_fragment_count === 8.U
  val endpointKindMatches = source.candidate_class === p.r2PackReadClassCode.U &&
    allocation.candidate_class === p.r2PackReadClassCode.U &&
    allocation.target_kind === RouteADeliveryTargetKind.P3PendingRead.U
  val identityMatches = allocation.transaction_identity.asUInt === response.transaction_identity.asUInt
  val generationMatches = allocation.target_identity_generation === descriptor.source_generation
  val ordinalLegal = descriptor.pending_ordinal < 64.U
  val responseIndexLegal = response.fragment_index < 8.U
  val responseOk = response.status === p.coreMemoryOkStatusCode.U
  val responseFault = response.status === p.coreMemoryFaultStatusCode.U
  val lastLegal = Mux(responseOk,
    response.last === (response.fragment_index === 7.U),
    response.last)
  val statusLegal = responseOk || responseFault
  val endpointLegal = endpointKindMatches && identityMatches && generationMatches &&
    expectedEightFragments && ordinalLegal && responseIndexLegal && statusLegal && lastLegal

  io.p3_pending_fragment_out.valid := io.resolved_fragment_in.valid && endpointLegal
  io.p3_pending_fragment_out.bits.layer := descriptor.p3_layer
  io.p3_pending_fragment_out.bits.stage_generation := descriptor.p3_stage_generation
  io.p3_pending_fragment_out.bits.fragment_index := Cat(descriptor.pending_ordinal(5, 0), response.fragment_index(2, 0))
  io.p3_pending_fragment_out.bits.last := response.last
  io.p3_pending_fragment_out.bits.status := response.status
  io.p3_pending_fragment_out.bits.payload_ref := descriptor.p3_member_payload_ref
  io.p3_pending_fragment_out.bits.data := response.data
  io.resolved_fragment_in.ready := endpointLegal && io.p3_pending_fragment_out.ready

  val held = RegEnable(io.p3_pending_fragment_out.bits,
    io.p3_pending_fragment_out.valid && !io.p3_pending_fragment_out.ready)
  when(RegNext(io.p3_pending_fragment_out.valid && !io.p3_pending_fragment_out.ready, false.B)) {
    assert(io.p3_pending_fragment_out.bits.asUInt === held.asUInt)
  }
}

/**
  * Historical RTL2.1b write-terminal-only router, retained by its isolated
  * direct harness. Production top-level wiring uses RouteATypedDeliveryRouter
  * since RTL2.2.2. The three keys do not encode a physical crossbar or HBM
  * response protocol.
  */
final class RouteAR2WriteDeliveryRouter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_r2_write_delivery_router"

  val io = IO(new Bundle {
    val source_delivery_in = Flipped(RouteAChannels.source_delivery(p))
    val r3_packed_write_out = RouteAChannels.source_delivery(p)
    val r5_append_out = RouteAChannels.source_delivery(p)
    val r5_reclaim_out = RouteAChannels.source_delivery(p)
  })

  val delivery = io.source_delivery_in.bits
  val isR3 = delivery.candidate_class === p.r2PackWriteClassCode.U &&
    delivery.delivery_context_ref === RouteARTL2WriteDeliveryContext.R3PackedWrite.U
  val isAppend = delivery.candidate_class === p.r2DescriptorMaintenanceClassCode.U &&
    delivery.delivery_context_ref === RouteARTL2WriteDeliveryContext.R5Append.U
  val isReclaim = delivery.candidate_class === p.r2DescriptorMaintenanceClassCode.U &&
    delivery.delivery_context_ref === RouteARTL2WriteDeliveryContext.R5Reclaim.U
  io.r3_packed_write_out.valid := io.source_delivery_in.valid && isR3
  io.r3_packed_write_out.bits := delivery
  io.r5_append_out.valid := io.source_delivery_in.valid && isAppend
  io.r5_append_out.bits := delivery
  io.r5_reclaim_out.valid := io.source_delivery_in.valid && isReclaim
  io.r5_reclaim_out.bits := delivery
  io.source_delivery_in.ready := Mux(isR3, io.r3_packed_write_out.ready,
    Mux(isAppend, io.r5_append_out.ready, Mux(isReclaim, io.r5_reclaim_out.ready, false.B)))
}

/**
  * RTL1.1 R1 core-memory transaction wrapper.
  *
  * This is deliberately a core-clock ready/valid wrapper, not an HBM command,
  * controller, CDC, timing, or PPA implementation. The dedicated external
  * `init_ack` is the adapter's reset-epoch acknowledgement: the adapter must
  * suppress pre-reset replies before it accepts that handshake.
  */
final class RouteACoreMemIfV1(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_core_mem_if_v1"

  val io = IO(new Bundle {
    val core_mem_req_in = Flipped(RouteAChannels.core_mem_req(p))
    val core_mem_rsp = RouteAChannels.core_mem_rsp(p)
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
    val r1_init_complete = Output(Bool())
    val r1_drain_permitted = Input(Bool())
    val component_status_out = RouteAChannels.component_status(p)
  })

  private val requestIdSlots = 1 << RouteAAnchorWidths.RequestIdWidth
  private val maximumLiveReads = 4
  private val maximumLiveWrites = 1

  val initialized = RegInit(false.B)
  io.external_core_mem_if_v1.init_ack.ready := !initialized &&
    io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready
  when(io.external_core_mem_if_v1.init_ack.fire) {
    initialized := true.B
  }
  io.r1_init_complete := initialized
  val initStatusReported = RegInit(false.B)

  val readLive = RegInit(VecInit(Seq.fill(requestIdSlots)(false.B)))
  val readIncarnation = Reg(Vec(requestIdSlots, UInt(RouteAAnchorWidths.IncarnationWidth.W)))
  val readExpectedFragments = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentCountWidth.W)))
  val readNextFragment = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentIndexWidth.W)))

  val writeLive = RegInit(VecInit(Seq.fill(requestIdSlots)(false.B)))
  val writeIncarnation = Reg(Vec(requestIdSlots, UInt(RouteAAnchorWidths.IncarnationWidth.W)))
  val writeExpectedFragments = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentCountWidth.W)))
  val writeNextFragment = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentIndexWidth.W)))
  val writeDataComplete = RegInit(VecInit(Seq.fill(requestIdSlots)(false.B)))

  val req = io.core_mem_req_in.bits
  val reqRequestId = req.transaction_identity.request_id
  val reqIncarnation = req.transaction_identity.incarnation
  val reqIdentitySlotBusy = readLive(reqRequestId) || writeLive(reqRequestId)
  val readSlotsAvailable = PopCount(readLive) < maximumLiveReads.U
  val writeSlotsAvailable = PopCount(writeLive) < maximumLiveWrites.U
  val nonzeroExpectedCount = req.expected_fragment_count =/= 0.U

  val isReadRequest = req.request_kind === p.coreMemoryReadRequestCode.U(p.coreMemoryRequestKindWidth.W)
  val isWriteRequest = req.request_kind === p.coreMemoryWriteRequestCode.U(p.coreMemoryRequestKindWidth.W)
  val isWriteData = req.request_kind === p.coreMemoryWriteDataCode.U(p.coreMemoryRequestKindWidth.W)

  val expectedWriteLast = writeNextFragment(reqRequestId) === (writeExpectedFragments(reqRequestId) - 1.U)
  val legalWriteData = writeLive(reqRequestId) &&
    writeIncarnation(reqRequestId) === reqIncarnation &&
    !writeDataComplete(reqRequestId) &&
    req.fragment_index === writeNextFragment(reqRequestId) &&
    req.last === expectedWriteLast

  val legalIncomingRequest = initialized && (
    (isReadRequest && !reqIdentitySlotBusy && readSlotsAvailable && nonzeroExpectedCount) ||
      (isWriteRequest && !reqIdentitySlotBusy && writeSlotsAvailable && nonzeroExpectedCount) ||
      (isWriteData && legalWriteData)
  )

  io.core_mem_req_in.ready := legalIncomingRequest && io.external_core_mem_if_v1.request.ready
  io.external_core_mem_if_v1.request.valid := io.core_mem_req_in.valid && legalIncomingRequest
  io.external_core_mem_if_v1.request.bits := req

  // a_descriptor_unique_memory_path: every accepted R1 transaction reaches
  // the one frozen external-memory carrier, never a second hidden endpoint.
  when(io.external_core_mem_if_v1.request.valid) {
    assert(io.core_mem_req_in.valid && legalIncomingRequest)
  }
  // a_reset_stale_exclusion: no core traffic escapes before the adapter has
  // acknowledged that its pre-reset reply population was suppressed/drained.
  when(!initialized) {
    assert(!io.core_mem_req_in.ready && !io.external_core_mem_if_v1.request.valid)
  }

  when(io.core_mem_req_in.fire) {
    when(isReadRequest) {
      readLive(reqRequestId) := true.B
      readIncarnation(reqRequestId) := reqIncarnation
      readExpectedFragments(reqRequestId) := req.expected_fragment_count
      readNextFragment(reqRequestId) := 0.U
    }.elsewhen(isWriteRequest) {
      writeLive(reqRequestId) := true.B
      writeIncarnation(reqRequestId) := reqIncarnation
      writeExpectedFragments(reqRequestId) := req.expected_fragment_count
      writeNextFragment(reqRequestId) := 0.U
      writeDataComplete(reqRequestId) := false.B
    }.otherwise { // legalWriteData is the only remaining legal operation.
      writeNextFragment(reqRequestId) := writeNextFragment(reqRequestId) + 1.U
      when(req.last) {
        writeDataComplete(reqRequestId) := true.B
      }
    }
  }

  val externalResponse = io.external_core_mem_if_v1.response.bits
  val responseRequestId = externalResponse.transaction_identity.request_id
  val responseIncarnation = externalResponse.transaction_identity.incarnation
  val matchingRead = readLive(responseRequestId) &&
    readIncarnation(responseRequestId) === responseIncarnation
  val matchingWrite = writeLive(responseRequestId) &&
    writeIncarnation(responseRequestId) === responseIncarnation
  val matchingResponse = matchingRead || matchingWrite

  val responseIsOk = externalResponse.status === p.coreMemoryOkStatusCode.U(RouteAAnchorWidths.TerminalStatusWidth.W)
  val responseIsFault = externalResponse.status === p.coreMemoryFaultStatusCode.U(RouteAAnchorWidths.TerminalStatusWidth.W)
  val expectedReadLast = readNextFragment(responseRequestId) === (readExpectedFragments(responseRequestId) - 1.U)
  val legalReadResponse = matchingRead && (
    (responseIsOk &&
      externalResponse.fragment_index === readNextFragment(responseRequestId) &&
      externalResponse.last === expectedReadLast) ||
      (responseIsFault && externalResponse.last)
  )
  val legalWriteCommit = matchingWrite &&
    writeDataComplete(responseRequestId) &&
    externalResponse.last &&
    (responseIsOk || responseIsFault)
  val protocolLegalResponse = legalReadResponse || legalWriteCommit

  // Any malformed matching read response fails closed as a terminal fault;
  // otherwise a bad fragment could leave a live identity ambiguously open.
  val terminalReadResponse = matchingRead && (!legalReadResponse || !responseIsOk || externalResponse.last)
  val terminalWriteResponse = matchingWrite
  val terminalResponse = terminalReadResponse || terminalWriteResponse

  io.core_mem_rsp.valid := io.external_core_mem_if_v1.response.valid && matchingResponse
  io.core_mem_rsp.bits := externalResponse
  when(matchingResponse && !protocolLegalResponse) {
    io.core_mem_rsp.bits.fragment_index := 0.U
    io.core_mem_rsp.bits.last := true.B
    io.core_mem_rsp.bits.status := p.coreMemoryFaultStatusCode.U(RouteAAnchorWidths.TerminalStatusWidth.W)
    io.core_mem_rsp.bits.data := 0.U
  }.elsewhen(matchingResponse && responseIsFault) {
    // Faults are terminal and intentionally carry no payload into core logic.
    io.core_mem_rsp.bits.data := 0.U
  }

  // Unmatched responses are stale and are consumed without becoming a core
  // response. Matching responses observe ordinary backpressure.
  io.external_core_mem_if_v1.response.ready := !matchingResponse || io.core_mem_rsp.ready

  // a_stale_response: unmatched (including reset-stale) adapter responses are
  // consumed at this boundary and cannot mutate or become a core response.
  when(io.external_core_mem_if_v1.response.valid && !matchingResponse) {
    assert(!io.core_mem_rsp.valid)
  }

  when(io.core_mem_rsp.fire) {
    when(matchingRead) {
      when(terminalResponse) {
        readLive(responseRequestId) := false.B
      }.otherwise {
        readNextFragment(responseRequestId) := readNextFragment(responseRequestId) + 1.U
      }
    }.elsewhen(matchingWrite) {
      when(terminalResponse) {
        writeLive(responseRequestId) := false.B
        writeDataComplete(responseRequestId) := false.B
      }
    }
  }

  val locallyDrained = !readLive.asUInt.orR && !writeLive.asUInt.orR
  val initStatusPending = initialized && !initStatusReported
  io.component_status_out.valid := initStatusPending || (io.r1_drain_permitted && locallyDrained)
  io.component_status_out.bits.acknowledgement_name := Mux(
    initStatusPending,
    p.r6.memInitDoneStatusCode.U,
    p.r6.r1MemoryDrainedStatusCode.U,
  )
  io.component_status_out.bits.asserted := true.B
  when(io.component_status_out.fire && initStatusPending) {
    initStatusReported := true.B
  }
}
