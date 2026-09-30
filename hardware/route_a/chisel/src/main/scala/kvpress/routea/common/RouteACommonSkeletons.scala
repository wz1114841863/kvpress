package kvpress.routea.common

import chisel3._
import chisel3.util.{MuxCase, PopCount, PriorityEncoder, RegEnable, UIntToOH, log2Ceil}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

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
