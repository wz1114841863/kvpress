package kvpress.routea.common

import chisel3._
import chisel3.util.{PopCount, UIntToOH}
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

/** RTL1.0 structural shell only; no S2 state, generation, or GQA behavior exists here. */
final class RouteAS2GqaSourceWrapper extends Module {
  override def desiredName: String = "route_a_s2_gqa_source_wrapper"

  val io = IO(new Bundle {
    val service_req_in = Flipped(RouteAChannels.s2_service_req)
  })

  StructuralTieOff.sink(io.service_req_in)
}

/** RTL1.0 structural shell only; no R2 eligibility, credit, FIFO, or grant state exists here. */
final class RouteACoreSideArbiter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_core_side_arbiter"

  val io = IO(new Bundle {
    val candidate_in = Flipped(RouteAChannels.source_candidate(p))
    val core_mem_req = RouteAChannels.core_mem_req(p)
    val core_mem_rsp_in = Flipped(RouteAChannels.core_mem_rsp(p))
    val source_delivery_out = RouteAChannels.source_delivery(p)
  })

  StructuralTieOff.sink(io.candidate_in)
  StructuralTieOff.source(io.core_mem_req)
  StructuralTieOff.sink(io.core_mem_rsp_in)
  StructuralTieOff.source(io.source_delivery_out)
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
