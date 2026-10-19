package kvpress.routea.baseline

import chisel3._
import chisel3.util.{Decoupled, Enum, Valid}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** Converts an already-selected baseline work item into the common R2 carrier. */
final class FullKVReadProducer(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    // The baseline lifecycle owner admits work only after the real R1 init
    // acknowledgement has crossed the status path.  This is a phase gate,
    // not a second source-selection owner.
    val service_enable = Input(Bool())
    val work_in = Flipped(Decoupled(new FullKVReadWork(p)))
    val fill_open_out = Decoupled(new FullKVFillOpen(p))
    val candidate_out = Decoupled(new SourceCandidate(p))
  })

  val opening = RegInit(false.B)
  val issuing = RegInit(false.B)
  val work = Reg(new FullKVReadWork(p))
  val legal = io.work_in.bits.expected_fragment_count =/= 0.U

  io.work_in.ready := io.service_enable && !opening && !issuing && legal
  when(io.work_in.fire) { work := io.work_in.bits; opening := true.B }

  io.fill_open_out.valid := opening
  io.fill_open_out.bits.transaction_identity := work.transaction_identity
  io.fill_open_out.bits.s2_slot := work.s2_slot
  io.fill_open_out.bits.source_generation := work.source_generation
  io.fill_open_out.bits.expected_fragment_count := work.expected_fragment_count
  when(io.fill_open_out.fire) { opening := false.B; issuing := true.B }

  io.candidate_out.valid := issuing
  io.candidate_out.bits := 0.U.asTypeOf(new SourceCandidate(p))
  io.candidate_out.bits.candidate_class := p.r2S2FullClassCode.U
  io.candidate_out.bits.arrival_ordinal := work.arrival_ordinal
  io.candidate_out.bits.candidate_id := work.candidate_id
  io.candidate_out.bits.eligibility_snapshot := work.eligibility_snapshot
  io.candidate_out.bits.delivery_target_descriptor.s2_slot := work.s2_slot
  io.candidate_out.bits.delivery_target_descriptor.source_generation := work.source_generation
  io.candidate_out.bits.delivery_target_descriptor.requires_sidecar := false.B
  io.candidate_out.bits.r1_request.transaction_identity := work.transaction_identity
  io.candidate_out.bits.r1_request.request_kind := p.coreMemoryReadRequestCode.U
  io.candidate_out.bits.r1_request.destination := work.destination_endpoint
  io.candidate_out.bits.r1_request.address_ref := work.payload_handle_or_address
  io.candidate_out.bits.r1_request.expected_fragment_count := work.expected_fragment_count
  io.candidate_out.bits.r1_request.fragment_index := 0.U
  io.candidate_out.bits.r1_request.last := false.B
  io.candidate_out.bits.r1_request.data := 0.U
  when(io.candidate_out.fire) { issuing := false.B }
}

/**
  * Allocates the common delivery-context record before R2 can observe the
  * baseline read.  It has one in-flight association, which is a functional
  * association bound rather than a scheduling policy or storage sizing claim.
  */
final class FullKVDeliveryContextBridge(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val candidate_in = Flipped(Decoupled(new SourceCandidate(p)))
    val candidate_out = Decoupled(new SourceCandidate(p))
    val allocation_out = Decoupled(new DeliveryContextAllocation(p))
    val allocation_ack_in = Flipped(Decoupled(new DeliveryContextAllocationAck(p)))
    val release_event_in = Input(Valid(new DeliveryContextRelease(p)))
  })
  val idle :: allocating :: ready :: awaitingRelease :: Nil = Enum(4)
  val state = RegInit(idle)
  val candidate = Reg(new SourceCandidate(p))
  val allocation = Wire(new DeliveryContextAllocation(p))
  allocation := 0.U.asTypeOf(new DeliveryContextAllocation(p))
  allocation.candidate_class := p.r2S2FullClassCode.U
  allocation.transaction_identity := candidate.r1_request.transaction_identity
  allocation.target_kind := RouteADeliveryTargetKind.S2FullFill.U
  allocation.target_identity_generation := candidate.delivery_target_descriptor.source_generation
  allocation.expected_fragment_count := candidate.r1_request.expected_fragment_count
  allocation.target_descriptor := candidate.delivery_target_descriptor

  io.candidate_in.ready := state === idle
  when(io.candidate_in.fire) { candidate := io.candidate_in.bits; state := allocating }
  io.allocation_out.valid := state === allocating
  io.allocation_out.bits := allocation
  io.allocation_ack_in.ready := state === allocating &&
    io.allocation_ack_in.bits.allocation.asUInt === allocation.asUInt
  when(io.allocation_out.fire) { }

  val boundRef = Reg(UInt(p.sourceDeliveryOpaqueWidth.W))
  when(io.allocation_ack_in.fire) { boundRef := io.allocation_ack_in.bits.delivery_context_ref; state := ready }
  io.candidate_out.valid := state === ready
  io.candidate_out.bits := candidate
  io.candidate_out.bits.delivery_context_ref := boundRef
  when(io.candidate_out.fire) { state := awaitingRelease }
  val releaseMatches = io.release_event_in.bits.delivery_context_ref === boundRef &&
    io.release_event_in.bits.allocation.asUInt === allocation.asUInt
  when(state === awaitingRelease && io.release_event_in.valid && releaseMatches) { state := idle }
}

/** Converts only a registry-resolved Full-KV response into baseline S2 events. */
final class FullKVS2ReadEndpoint(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val resolved_in = Flipped(Decoupled(new ResolvedDelivery(p)))
    val payload_out = Decoupled(new FullKVPayloadFragment(p))
    val terminal_out = Decoupled(new FullKVFillTerminal(p))
  })
  val held = Reg(new ResolvedDelivery(p))
  val heldValid = RegInit(false.B)
  val emitTerminal = RegInit(false.B)
  val response = Mux(heldValid, held.source_delivery.r1_response, io.resolved_in.bits.source_delivery.r1_response)
  val allocation = Mux(heldValid, held.allocation, io.resolved_in.bits.allocation)
  val legal = allocation.candidate_class === p.r2S2FullClassCode.U &&
    allocation.target_kind === RouteADeliveryTargetKind.S2FullFill.U &&
    !allocation.target_descriptor.requires_sidecar
  io.resolved_in.ready := !heldValid && !emitTerminal && legal
  when(io.resolved_in.fire) { held := io.resolved_in.bits; heldValid := true.B }
  val active = heldValid
  val activeResponse = held.source_delivery.r1_response
  val activeAllocation = held.allocation
  val isOk = activeResponse.status === p.coreMemoryOkStatusCode.U
  io.payload_out.valid := active && isOk
  io.payload_out.bits.transaction_identity := activeResponse.transaction_identity
  io.payload_out.bits.s2_slot := activeAllocation.target_descriptor.s2_slot
  io.payload_out.bits.source_generation := activeAllocation.target_descriptor.source_generation
  io.payload_out.bits.fragment_index := activeResponse.fragment_index
  io.payload_out.bits.data := activeResponse.data
  io.terminal_out.valid := active && (!isOk || activeResponse.last)
  io.terminal_out.bits.transaction_identity := activeResponse.transaction_identity
  io.terminal_out.bits.s2_slot := activeAllocation.target_descriptor.s2_slot
  io.terminal_out.bits.source_generation := activeAllocation.target_descriptor.source_generation
  io.terminal_out.bits.status := activeResponse.status
  when(io.payload_out.fire && !activeResponse.last) { heldValid := false.B }
  when(io.terminal_out.fire) { heldValid := false.B }
}
