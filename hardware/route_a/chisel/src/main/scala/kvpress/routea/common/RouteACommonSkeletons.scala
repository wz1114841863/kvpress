package kvpress.routea.common

import chisel3._
import chisel3.util.{MuxCase, PopCount, PriorityEncoder, RegEnable, UIntToOH, log2Ceil}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** RTL1.0 structural shell only; hot-residency behavior begins in a later phase. */
final class RouteAHotSourcePath(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_hot_source_path"

  val io = IO(new Bundle {
    val lifecycle_control_in = Flipped(RouteAChannels.hot_control(p))
  })

  StructuralTieOff.sink(io.lifecycle_control_in)
}

/** RTL1.4.0 carrier shell; no S2 storage, generation, or GQA behavior exists here yet. */
final class RouteAS2GqaSourceWrapper(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_s2_gqa_source_wrapper"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val service_req_in = Flipped(RouteAChannels.s2_service_req)
    val s2_fill_open_in = Flipped(RouteAChannels.s2_fill_open(p))
    val s2_fill_terminal_in = Flipped(RouteAChannels.s2_fill_terminal(p))
    val s2_sidecar_complete_in = Flipped(RouteAChannels.s2_sidecar_complete(p))
    val gqa_consumer_commit_in = Flipped(RouteAChannels.gqa_consumer_commit(p))
    val s2_release_out = RouteAChannels.source_release(p)
    val s2_observe_slot = Input(UInt(RouteAAnchorWidths.S2SlotWidth.W))
    val s2_observe_state = Output(UInt(3.W))
    val s2_observe_generation = Output(UInt(p.sourceGenerationWidth.W))
  })

  StructuralTieOff.sink(io.service_req_in)
  StructuralTieOff.sink(io.s2_fill_open_in)
  StructuralTieOff.sink(io.s2_fill_terminal_in)
  StructuralTieOff.sink(io.s2_sidecar_complete_in)
  StructuralTieOff.sink(io.gqa_consumer_commit_in)
  StructuralTieOff.source(io.s2_release_out)
  io.s2_observe_state := 0.U
  io.s2_observe_generation := 0.U
}

/** RTL1.2 R2 eligibility, lossless candidate storage, and accepted-grant control. */
final class RouteACoreSideArbiter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_core_side_arbiter"

  val io = IO(new Bundle {
    val candidate_in = Flipped(RouteAChannels.source_candidate(p))
    val core_mem_req = RouteAChannels.core_mem_req(p)
    val core_mem_rsp_in = Flipped(RouteAChannels.core_mem_rsp(p))
    val source_delivery_out = RouteAChannels.source_delivery(p)
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
  io.candidate_in.ready := !selectedRequestStalled && inputEligible && anyFreeSlot && inputClassCount < p.r2CandidateSlotsPerClass.U

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
  io.source_delivery_out.bits.r1_response := response
  io.core_mem_rsp_in.ready := !matchingResponse || io.source_delivery_out.ready

  when(io.source_delivery_out.fire && response.last) {
    outstandingValid(responseRid) := false.B
  }

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
  * controller, CDC, timing, or PPA implementation. `mem_init_done` is the
  * adapter's reset-epoch acknowledgement: the adapter must suppress pre-reset
  * replies before it raises this local signal.
  */
final class RouteACoreMemIfV1(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_core_mem_if_v1"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val core_mem_req_in = Flipped(RouteAChannels.core_mem_req(p))
    val core_mem_rsp = RouteAChannels.core_mem_rsp(p)
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
  })

  private val requestIdSlots = 1 << RouteAAnchorWidths.RequestIdWidth
  private val maximumLiveReads = 4
  private val maximumLiveWrites = 1

  val initialized = RegInit(false.B)
  when(io.mem_init_done) {
    initialized := true.B
  }

  val readLive = RegInit(VecInit(Seq.fill(requestIdSlots)(false.B)))
  val readIncarnation = Reg(Vec(requestIdSlots, UInt(RouteAAnchorWidths.IncarnationWidth.W)))
  val readExpectedFragments = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentCountWidth.W)))
  val readNextFragment = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentIndexWidth.W)))

  val writeLive = RegInit(VecInit(Seq.fill(requestIdSlots)(false.B)))
  val writeIncarnation = Reg(Vec(requestIdSlots, UInt(RouteAAnchorWidths.IncarnationWidth.W)))
  val writeExpectedFragments = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentCountWidth.W)))
  val writeNextFragment = Reg(Vec(requestIdSlots, UInt(p.coreMemoryFragmentIndexWidth.W)))
  val writeDataComplete = RegInit(VecInit(Seq.fill(requestIdSlots)(false.B)))
  // Within one adapter epoch an identical identity is never reused after a
  // terminal outcome. The finite incarnation namespace is renewed only by
  // destructive reset plus the external adapter's mem_init_done handshake.
  private val incarnationSlots = 1 << RouteAAnchorWidths.IncarnationWidth
  val seenIncarnations = RegInit(VecInit(Seq.fill(requestIdSlots)(0.U(incarnationSlots.W))))

  val req = io.core_mem_req_in.bits
  val reqRequestId = req.transaction_identity.request_id
  val reqIncarnation = req.transaction_identity.incarnation
  val reqIdentitySlotBusy = readLive(reqRequestId) || writeLive(reqRequestId)
  val reqIdentitySeen = seenIncarnations(reqRequestId)(reqIncarnation)
  val reqIncarnationMask = UIntToOH(reqIncarnation, incarnationSlots)
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
    (isReadRequest && !reqIdentitySlotBusy && !reqIdentitySeen && readSlotsAvailable && nonzeroExpectedCount) ||
      (isWriteRequest && !reqIdentitySlotBusy && !reqIdentitySeen && writeSlotsAvailable && nonzeroExpectedCount) ||
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
      seenIncarnations(reqRequestId) := seenIncarnations(reqRequestId) | reqIncarnationMask
    }.elsewhen(isWriteRequest) {
      writeLive(reqRequestId) := true.B
      writeIncarnation(reqRequestId) := reqIncarnation
      writeExpectedFragments(reqRequestId) := req.expected_fragment_count
      writeNextFragment(reqRequestId) := 0.U
      writeDataComplete(reqRequestId) := false.B
      seenIncarnations(reqRequestId) := seenIncarnations(reqRequestId) | reqIncarnationMask
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
}
