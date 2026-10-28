package kvpress.routea.baseline

import chisel3._
import chisel3.util.{Decoupled, Enum, PriorityEncoder, RegEnable, UIntToOH, Valid}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** Parent-authorized Full-KV payload-array write. Identity/generation remain
  * in the baseline S2 parent and never become array-child state. */
final class FullKVPayloadArrayWriteRequest(p: RouteASkeletonParameters) extends Bundle {
  val slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val fragment = UInt(p.coreMemoryFragmentIndexWidth.W)
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}
final class FullKVPayloadArrayWriteAck(p: RouteASkeletonParameters) extends Bundle {
  val slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val fragment = UInt(p.coreMemoryFragmentIndexWidth.W)
}
final class FullKVPayloadArrayReadRequest(p: RouteASkeletonParameters) extends Bundle {
  val slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val fragment = UInt(p.coreMemoryFragmentIndexWidth.W)
}
final class FullKVPayloadArrayReadResponse(p: RouteASkeletonParameters) extends Bundle {
  val slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val fragment = UInt(p.coreMemoryFragmentIndexWidth.W)
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

/**
  * Full-KV logical payload-array interior only.  It has no source selection,
  * identity, generation, READY, terminal, consumer, release or fault state.
  */
final class FullKVS2PayloadArrayBoundary(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "full_kv_s2_payload_array_boundary"

  private val slots = 2
  private val fragmentsPerSlot = 1 << p.coreMemoryFragmentIndexWidth
  val io = IO(new Bundle {
    val write_req = Flipped(Decoupled(new FullKVPayloadArrayWriteRequest(p)))
    val write_ack = Decoupled(new FullKVPayloadArrayWriteAck(p))
    val read_req = Flipped(Decoupled(new FullKVPayloadArrayReadRequest(p)))
    val read_rsp = Decoupled(new FullKVPayloadArrayReadResponse(p))
  })
  val payload = Mem(slots * fragmentsPerSlot, UInt(RouteAAnchorWidths.CoreDataWidth.W))
  private def index(slot: UInt, fragment: UInt): UInt = slot * fragmentsPerSlot.U + fragment

  val writeAckValid = RegInit(false.B)
  val writeAck = Reg(new FullKVPayloadArrayWriteAck(p))
  io.write_req.ready := !writeAckValid
  io.write_ack.valid := writeAckValid
  io.write_ack.bits := writeAck
  when(io.write_req.fire) {
    payload.write(index(io.write_req.bits.slot, io.write_req.bits.fragment), io.write_req.bits.data)
    writeAck.slot := io.write_req.bits.slot
    writeAck.fragment := io.write_req.bits.fragment
    writeAckValid := true.B
  }
  when(io.write_ack.fire) { writeAckValid := false.B }

  val readRspValid = RegInit(false.B)
  val readRsp = Reg(new FullKVPayloadArrayReadResponse(p))
  io.read_req.ready := !readRspValid
  io.read_rsp.valid := readRspValid
  io.read_rsp.bits := readRsp
  when(io.read_req.fire) {
    readRsp.slot := io.read_req.bits.slot
    readRsp.fragment := io.read_req.bits.fragment
    readRsp.data := payload.read(index(io.read_req.bits.slot, io.read_req.bits.fragment))
    readRspValid := true.B
  }
  when(io.read_rsp.fire) { readRspValid := false.B }
}

/** Baseline-local two-slot FILL -> READY -> four-consumer -> release control. */
final class FullKVS2GqaSourceWrapper(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val drain_collection_enable = Input(Bool())
    val fill_open_in = Flipped(Decoupled(new FullKVFillOpen(p)))
    val payload_in = Flipped(Decoupled(new FullKVPayloadFragment(p)))
    val terminal_in = Flipped(Decoupled(new FullKVFillTerminal(p)))
    val payload_read_req_in = Flipped(Decoupled(new FullKVPayloadReadRequest(p)))
    val payload_read_rsp_out = Decoupled(new FullKVPayloadReadResponse(p))
    val source_ready_out = Output(Valid(new FullKVSourceReady(p)))
    val consumer_commit_in = Flipped(Decoupled(new FullKVGqaConsumerCommit(p)))
    val source_release_out = Decoupled(new FullKVSourceRelease(p))
    // A fault never becomes READY or a synthetic release.  It crosses the
    // baseline-local terminal owner with its original identity/status.
    val fault_terminal_out = Decoupled(new FullKVFillTerminal(p))
    val component_status_out = RouteAChannels.component_status(p)
  })
  val empty :: filling :: ready :: faulted :: Nil = Enum(4)
  val state = RegInit(VecInit(Seq.fill(2)(empty)))
  val identity = Reg(Vec(2, new TransactionIdentity))
  val generation = Reg(Vec(2, UInt(p.sourceGenerationWidth.W)))
  val expected = Reg(Vec(2, UInt(p.coreMemoryFragmentCountWidth.W)))
  val next = Reg(Vec(2, UInt(p.coreMemoryFragmentIndexWidth.W)))
  val commits = RegInit(VecInit(Seq.fill(2)(0.U(4.W))))
  val faultPending = RegInit(false.B)
  val faultTerminal = Reg(new FullKVFillTerminal(p))
  val storage = Module(new FullKVS2PayloadArrayBoundary(p))

  val payloadWritePending = RegInit(false.B)
  val payloadWriteRequest = Reg(new FullKVPayloadArrayWriteRequest(p))
  val payloadWriteAwaitAck = RegInit(false.B)
  storage.io.write_req.valid := payloadWritePending
  storage.io.write_req.bits := payloadWriteRequest
  storage.io.write_ack.ready := payloadWriteAwaitAck
  when(storage.io.write_req.fire) {
    payloadWritePending := false.B
    payloadWriteAwaitAck := true.B
  }
  when(storage.io.write_ack.fire) {
    assert(storage.io.write_ack.bits.slot === payloadWriteRequest.slot)
    assert(storage.io.write_ack.bits.fragment === payloadWriteRequest.fragment)
    payloadWriteAwaitAck := false.B
    when(state(storage.io.write_ack.bits.slot) === filling) {
      next(storage.io.write_ack.bits.slot) := next(storage.io.write_ack.bits.slot) + 1.U
    }
  }

  val payloadReadRspValid = RegInit(false.B)
  val payloadReadRsp = Reg(new FullKVPayloadReadResponse(p))
  val payloadReadPending = RegInit(false.B)
  val payloadReadRequest = Reg(new FullKVPayloadReadRequest(p))
  val payloadReadOutstanding = RegInit(false.B)
  storage.io.read_req.valid := payloadReadPending
  storage.io.read_req.bits.slot := payloadReadRequest.s2_slot
  storage.io.read_req.bits.fragment := payloadReadRequest.fragment_index
  storage.io.read_rsp.ready := payloadReadOutstanding && !payloadReadRspValid
  when(storage.io.read_req.fire) { payloadReadPending := false.B }

  val open = io.fill_open_in.bits
  val openSlot = open.s2_slot
  val openLegal = io.mem_init_done && open.expected_fragment_count =/= 0.U && state(openSlot) === empty
  io.fill_open_in.ready := openLegal
  when(io.fill_open_in.fire) {
    state(openSlot) := filling; identity(openSlot) := open.transaction_identity
    generation(openSlot) := open.source_generation; expected(openSlot) := open.expected_fragment_count
    next(openSlot) := 0.U; commits(openSlot) := 0.U
  }

  val payload = io.payload_in.bits
  val payloadSlot = payload.s2_slot
  val payloadLegal = !payloadWritePending && !payloadWriteAwaitAck && state(payloadSlot) === filling &&
    identity(payloadSlot).asUInt === payload.transaction_identity.asUInt &&
    generation(payloadSlot) === payload.source_generation && next(payloadSlot) === payload.fragment_index &&
    payload.fragment_index < expected(payloadSlot)
  io.payload_in.ready := payloadLegal
  when(io.payload_in.fire) {
    payloadWritePending := true.B
    payloadWriteRequest.slot := payloadSlot
    payloadWriteRequest.fragment := payload.fragment_index
    payloadWriteRequest.data := payload.data
  }

  val terminal = io.terminal_in.bits
  val terminalSlot = terminal.s2_slot
  val terminalLegal = state(terminalSlot) === filling &&
    identity(terminalSlot).asUInt === terminal.transaction_identity.asUInt &&
    generation(terminalSlot) === terminal.source_generation &&
    ((terminal.status === p.coreMemoryOkStatusCode.U && next(terminalSlot) === expected(terminalSlot)) ||
      terminal.status === p.coreMemoryFaultStatusCode.U)
  io.terminal_in.ready := terminalLegal
  when(io.terminal_in.fire) {
    state(terminalSlot) := Mux(terminal.status === p.coreMemoryOkStatusCode.U, ready, faulted)
    when(terminal.status === p.coreMemoryFaultStatusCode.U) {
      faultTerminal := terminal
      faultPending := true.B
    }
  }

  val payloadRead = io.payload_read_req_in.bits
  val payloadReadSlot = payloadRead.s2_slot
  val payloadReadLegal = io.mem_init_done && !payloadReadOutstanding && !payloadReadRspValid &&
    state(payloadReadSlot) === ready &&
    identity(payloadReadSlot).asUInt === payloadRead.transaction_identity.asUInt &&
    generation(payloadReadSlot) === payloadRead.source_generation &&
    payloadRead.fragment_index < expected(payloadReadSlot)
  io.payload_read_req_in.ready := payloadReadLegal
  io.payload_read_rsp_out.valid := payloadReadRspValid
  io.payload_read_rsp_out.bits := payloadReadRsp
  when(io.payload_read_rsp_out.fire) { payloadReadRspValid := false.B }
  when(io.payload_read_req_in.fire) {
    payloadReadPending := true.B
    payloadReadOutstanding := true.B
    payloadReadRequest := payloadRead
  }
  when(storage.io.read_rsp.fire) {
    assert(storage.io.read_rsp.bits.slot === payloadReadRequest.s2_slot)
    assert(storage.io.read_rsp.bits.fragment === payloadReadRequest.fragment_index)
    payloadReadRsp.request := payloadReadRequest
    payloadReadRsp.data := storage.io.read_rsp.bits.data
    payloadReadRspValid := true.B
    payloadReadOutstanding := false.B
  }
  val payloadReadRspStalled = io.payload_read_rsp_out.valid && !io.payload_read_rsp_out.ready
  val heldPayloadReadRsp = RegEnable(io.payload_read_rsp_out.bits, payloadReadRspStalled)
  when(RegNext(payloadReadRspStalled, false.B)) {
    assert(io.payload_read_rsp_out.bits.asUInt === heldPayloadReadRsp.asUInt)
  }

  val readySlot = Wire(UInt(RouteAAnchorWidths.S2SlotWidth.W))
  readySlot := Mux(state(0) === ready, 0.U, 1.U)
  io.source_ready_out.valid := state(0) === ready || state(1) === ready
  io.source_ready_out.bits.transaction_identity := identity(readySlot)
  io.source_ready_out.bits.source_instance.s2_slot := readySlot
  io.source_ready_out.bits.source_instance.source_generation := generation(readySlot)

  val commit = io.consumer_commit_in.bits
  val commitSlot = commit.source_instance.s2_slot
  val commitBit = UIntToOH(commit.consumer_id, 4)
  val commitLegal = state(commitSlot) === ready && commit.consumer_id < 4.U &&
    identity(commitSlot).asUInt === commit.transaction_identity.asUInt &&
    generation(commitSlot) === commit.source_instance.source_generation && !(commits(commitSlot) & commitBit).orR
  io.consumer_commit_in.ready := commitLegal
  when(io.consumer_commit_in.fire) { commits(commitSlot) := commits(commitSlot) | commitBit }

  val releaseSlot = Wire(UInt(RouteAAnchorWidths.S2SlotWidth.W))
  releaseSlot := Mux(state(0) === ready && commits(0) === "b1111".U, 0.U, 1.U)
  val releasable = (state(0) === ready && commits(0) === "b1111".U) ||
    (state(1) === ready && commits(1) === "b1111".U)
  io.source_release_out.valid := releasable
  io.source_release_out.bits.transaction_identity := identity(releaseSlot)
  io.source_release_out.bits.source_instance.s2_slot := releaseSlot
  io.source_release_out.bits.source_instance.source_generation := generation(releaseSlot)
  when(io.source_release_out.fire) { state(releaseSlot) := empty; commits(releaseSlot) := 0.U }
  io.fault_terminal_out.valid := faultPending
  io.fault_terminal_out.bits := faultTerminal
  when(io.fault_terminal_out.fire) {
    // A fault is terminal for this source instance.  Clearing the faulted
    // slot only after the baseline lifecycle owner has accepted the exact
    // terminal carrier prevents it from becoming a synthetic READY/release
    // while still allowing the real S2 drain fact during retirement.
    faultPending := false.B
    state(faultTerminal.s2_slot) := empty
    commits(faultTerminal.s2_slot) := 0.U
  }
  val locallyDrained = !state.map(_ =/= empty).reduce(_ || _) && !faultPending
  io.component_status_out.valid := io.drain_collection_enable && locallyDrained
  io.component_status_out.bits.acknowledgement_name := p.r6.s2GqaDrainedStatusCode.U
  io.component_status_out.bits.asserted := true.B
}

/**
  * Full-KV-only serialization of real R1/R2/S2 init and drain facts.
  *
  * Sources 0..3 are respectively R1, R2 payload, R2 descriptor, and S2.
  * The R2 descriptor fact is an observation that the shared R2 descriptor
  * partition has no live slot or outstanding request in this Full-KV contour;
  * it neither creates nor implies a descriptor-maintenance transaction.
  */
final class FullKVStatusCollector(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val sources = Flipped(Vec(4, RouteAChannels.component_status(p)))
    val drain_collection_enable = Input(Bool())
    val r1_drain_permitted = Output(Bool())
    val status_out = RouteAChannels.component_status(p)
  })
  private val R1 = 0

  private def isInit(code: UInt): Bool = code === p.r6.memInitDoneStatusCode.U

  private def drainBit(code: UInt): UInt = {
    val bit = WireDefault(0.U(4.W))
    when(code === p.r6.r1MemoryDrainedStatusCode.U) { bit := "b0001".U }
    when(code === p.r6.r2PayloadDrainedStatusCode.U) { bit := "b0010".U }
    when(code === p.r6.r2DescriptorDrainedStatusCode.U) { bit := "b0100".U }
    when(code === p.r6.s2GqaDrainedStatusCode.U) { bit := "b1000".U }
    bit
  }

  val delivered = RegInit(0.U(4.W))
  when(!io.drain_collection_enable) { delivered := 0.U }
  val eligible = Wire(Vec(4, Bool()))
  for (i <- 0 until 4) {
    val status = io.sources(i).bits
    val bit = drainBit(status.acknowledgement_name)
    val initOffer = !io.drain_collection_enable && isInit(status.acknowledgement_name)
    val drainOffer = io.drain_collection_enable && bit.orR && (delivered & bit) === 0.U
    // R1 may state that it is empty only after both actual R2 partitions
    // report no future issue/outstanding work.
    val r1Ordered = if (i == R1) !drainOffer || (delivered & "b0110".U) === "b0110".U else true.B
    eligible(i) := io.sources(i).valid && status.asserted && (initOffer || drainOffer) && r1Ordered
  }
  val any = eligible.asUInt.orR
  val selected = PriorityEncoder(eligible)

  val stagedValid = RegInit(false.B)
  val stagedStatus = Reg(new ComponentStatus(p))
  val stagedDrainBit = Reg(UInt(4.W))
  for (i <- 0 until 4) {
    io.sources(i).ready := !stagedValid && any && selected === i.U
  }
  when(!stagedValid && any) {
    stagedValid := true.B
    stagedStatus := io.sources(selected).bits
    stagedDrainBit := drainBit(io.sources(selected).bits.acknowledgement_name)
  }

  io.status_out.valid := stagedValid
  io.status_out.bits := stagedStatus
  when(io.status_out.fire) {
    when(stagedDrainBit.orR) { delivered := delivered | stagedDrainBit }
    stagedValid := false.B
  }
  io.r1_drain_permitted := io.drain_collection_enable && (delivered & "b0110".U) === "b0110".U

  val heldStatus = RegEnable(io.status_out.bits, io.status_out.valid && !io.status_out.ready)
  when(RegNext(io.status_out.valid && !io.status_out.ready, false.B)) {
    assert(io.status_out.bits.asUInt === heldStatus.asUInt)
  }
  when(io.status_out.fire) {
    assert(isInit(stagedStatus.acknowledgement_name) || stagedDrainBit.orR)
  }
}

/**
  * Baseline-local lifecycle owner.  It consumes only the serialized status
  * facts above; it never selects a source or manufactures completion facts.
  */
final class FullKVTerminalRetireAdapter(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val source_release_in = Flipped(Decoupled(new FullKVSourceRelease(p)))
    val source_fault_in = Flipped(Decoupled(new FullKVFillTerminal(p)))
    val attention_terminal_rsp = Decoupled(new AttentionTerminalResponse)
    val runtime_retire_req = Flipped(Decoupled(new RuntimeRetireRequest))
    val session_retire_ack = Decoupled(new SessionRetireAck)
    val component_status_in = Flipped(RouteAChannels.component_status(p))
    val service_enable = Output(Bool())
    val drain_collection_enable = Output(Bool())
  })
  val boot :: idle :: terminal :: retire :: acknowledge :: Nil = Enum(5)
  val state = RegInit(boot)
  val identity = Reg(new TransactionIdentity)
  val terminalStatus = Reg(UInt(RouteAAnchorWidths.TerminalStatusWidth.W))
  val sessionId = Reg(Bool())
  val drainAcks = RegInit(0.U(4.W))

  private def drainBit(code: UInt): UInt = {
    val bit = WireDefault(0.U(4.W))
    when(code === p.r6.r1MemoryDrainedStatusCode.U) { bit := "b0001".U }
    when(code === p.r6.r2PayloadDrainedStatusCode.U) { bit := "b0010".U }
    when(code === p.r6.r2DescriptorDrainedStatusCode.U) { bit := "b0100".U }
    when(code === p.r6.s2GqaDrainedStatusCode.U) { bit := "b1000".U }
    bit
  }
  val status = io.component_status_in.bits
  val initFact = status.asserted && status.acknowledgement_name === p.r6.memInitDoneStatusCode.U
  val statusDrainBit = drainBit(status.acknowledgement_name)
  val drainFact = status.asserted && statusDrainBit.orR
  io.component_status_in.ready := (state === boot && initFact) ||
    ((state === retire || state === acknowledge) && drainFact)
  when(io.component_status_in.fire && state === boot) { state := idle }
  when(io.component_status_in.fire && (state === retire || state === acknowledge)) {
    drainAcks := drainAcks | statusDrainBit
  }

  io.service_enable := state === idle
  io.source_release_in.ready := state === idle && !io.source_fault_in.valid
  io.source_fault_in.ready := state === idle && !io.source_release_in.valid &&
    io.source_fault_in.bits.status === p.coreMemoryFaultStatusCode.U
  when(io.source_release_in.fire) {
    identity := io.source_release_in.bits.transaction_identity
    terminalStatus := p.coreMemoryOkStatusCode.U
    state := terminal
  }
  when(io.source_fault_in.fire) {
    identity := io.source_fault_in.bits.transaction_identity
    terminalStatus := io.source_fault_in.bits.status
    state := terminal
  }
  io.attention_terminal_rsp.valid := state === terminal
  io.attention_terminal_rsp.bits.transaction_identity := identity
  io.attention_terminal_rsp.bits.terminal_status := terminalStatus
  when(io.attention_terminal_rsp.fire) {
    // A new retirement epoch starts at the one outward terminal.  Drain facts
    // may legitimately arrive before the environment presents runtime-retire;
    // never discard those already accepted facts at that later handshake.
    drainAcks := 0.U
    state := retire
  }
  io.runtime_retire_req.ready := state === retire &&
    io.runtime_retire_req.bits.transaction_identity.asUInt === identity.asUInt
  when(io.runtime_retire_req.fire) {
    sessionId := io.runtime_retire_req.bits.session_id
    state := acknowledge
  }
  io.session_retire_ack.valid := state === acknowledge && drainAcks === "b1111".U
  io.session_retire_ack.bits.session_id := sessionId
  io.session_retire_ack.bits.transaction_identity := identity
  when(io.session_retire_ack.fire) { state := idle }
  io.drain_collection_enable := state === retire || state === acknowledge
}
