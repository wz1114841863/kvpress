package kvpress.routea.common

import chisel3._
import chisel3.util.{MuxCase, PopCount, PriorityEncoder, RegEnable, UIntToOH, Valid, log2Ceil}
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

/** RTL1.4 S2 control only; payload/sidecar macros and source mux remain unimplemented. */
final class RouteAS2GqaSourceWrapper(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_s2_gqa_source_wrapper"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val service_req_in = Flipped(RouteAChannels.s2_service_req)
    val s2_fill_open_in = Flipped(RouteAChannels.s2_fill_open(p))
    val s2_fill_terminal_in = Flipped(RouteAChannels.s2_fill_terminal(p))
    val s2_sidecar_complete_in = Flipped(RouteAChannels.s2_sidecar_complete(p))
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
  val requiresSidecar = RegInit(VecInit(Seq.fill(slots)(false.B)))
  val sidecarComplete = RegInit(VecInit(Seq.fill(slots)(false.B)))
  val consumerMask = RegInit(VecInit(Seq.fill(slots)(0.U(4.W))))

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
    requiresSidecar(serviceSlot) := false.B
    sidecarComplete(serviceSlot) := false.B
    consumerMask(serviceSlot) := 0.U
  }

  val fillOpen = io.s2_fill_open_in.bits
  val fillSlot = fillOpen.s2_slot
  val fillOpenMatches = initialized && slotState(fillSlot) === StateFilling && !fillOpened(fillSlot) &&
    slotGeneration(fillSlot) === fillOpen.source_generation &&
    slotIdentity(fillSlot).asUInt === fillOpen.transaction_identity.asUInt &&
    slotPageRef(fillSlot).asUInt === fillOpen.page_ref.asUInt &&
    fillOpen.expected_fragment_count =/= 0.U && fillOpen.expected_fragment_count <= 512.U
  io.s2_fill_open_in.ready := fillOpenMatches
  when(io.s2_fill_open_in.fire) {
    fillOpened(fillSlot) := true.B
    expectedFragments(fillSlot) := fillOpen.expected_fragment_count
    nextFragment(fillSlot) := 0.U
    requiresSidecar(fillSlot) := fillOpen.requires_sidecar
    sidecarComplete(fillSlot) := false.B
  }

  val fillTerminal = io.s2_fill_terminal_in.bits
  val terminalSlot = fillTerminal.s2_slot
  val terminalMatches = initialized && slotState(terminalSlot) === StateFilling && fillOpened(terminalSlot) &&
    slotGeneration(terminalSlot) === fillTerminal.source_generation &&
    slotIdentity(terminalSlot).asUInt === fillTerminal.transaction_identity.asUInt
  val terminalOk = fillTerminal.status === p.coreMemoryOkStatusCode.U
  val terminalFault = fillTerminal.status === p.coreMemoryFaultStatusCode.U
  val terminalOrdinalOk = nextFragment(terminalSlot) < expectedFragments(terminalSlot) &&
    fillTerminal.fragment_index === nextFragment(terminalSlot)(8, 0)
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
    slotIdentity(sidecarSlot).asUInt === sidecar.transaction_identity.asUInt
  io.s2_sidecar_complete_in.ready := sidecarMatches
  when(io.s2_sidecar_complete_in.fire) {
    sidecarComplete(sidecarSlot) := true.B
    when(nextFragment(sidecarSlot) === expectedFragments(sidecarSlot)) {
      slotState(sidecarSlot) := StateReady
      consumerMask(sidecarSlot) := "b1111".U
    }
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
    val candidate_in = Flipped(RouteAChannels.source_candidate(p))
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
  val inputClassCount = PopCount((0 until totalSlots).map { slot =>
    slotValid(slot) && slots(slot).candidate_class === io.candidate_in.bits.candidate_class
  })
  val inputEligible = candidateEligible(io.candidate_in.bits)
  val anyFreeSlot = !slotValid.reduce(_ && _)
  val reclaimDescriptorCandidate = io.candidate_in.bits.candidate_class === p.r2DescriptorMaintenanceClassCode.U
  val candidateIngressAllowed = !io.drain_collection_enable ||
    (io.reclaim_maintenance_enable && reclaimDescriptorCandidate)
  io.candidate_in.ready := candidateIngressAllowed && !selectedRequestStalled && inputEligible && anyFreeSlot && inputClassCount < p.r2CandidateSlotsPerClass.U

  when(io.candidate_in.fire) {
    val freeIndex = PriorityEncoder(VecInit(slotValid.map(! _)))
    slotValid(freeIndex) := true.B
    slots(freeIndex) := io.candidate_in.bits
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
