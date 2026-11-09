package kvpress.routea.incremental

import chisel3._
import chisel3.util.{Decoupled, Enum, PriorityEncoder, RegEnable, Valid, is, log2Ceil, switch}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * Production-v2 preflight and activation for an explicitly selected live page.
  * R6 provides the actual accepted attention owner, R5 the persistent page
  * permission and locations, and S2 the new reservation. No source is opened
  * until the declaration and R6 plan accept jointly, and the same reservation
  * is forwarded after R6's exact accepted-plan copy returns.
  */
final class RouteAPersistentPackedReadController(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_persistent_packed_read_controller_v2"

  val io = IO(new Bundle {
    val plan_in = Flipped(RouteAChannels.source_completion_plan(p))
    val plan_out = RouteAChannels.source_completion_plan(p)
    val accepted_plan_in = Flipped(RouteAChannels.source_completion_plan(p))
    val page_select_in = Flipped(Decoupled(new PersistentReadSelectionV2))
    val context_query_out = Decoupled(new R6PreflightContextQueryV2)
    val context_result_in = Flipped(Decoupled(new R6PreflightContextResultV2))
    val r6_reject_out = Decoupled(new PreplanRejectV2)
    val binder_cancel_out = Decoupled(new PreplanRejectV2)
    val query_out = Decoupled(new PersistentReadQuery)
    val query_result_in = Flipped(Decoupled(new PersistentReadResult(p)))
    val reservation_request_out = Decoupled(new S2FillLeaseRequest(p))
    val reservation_result_in = Flipped(Decoupled(new S2ReservationResultV2(p)))
    val readiness_pending_in = Input(Valid(new PersistentReadReceipt(p)))
    val attention_terminal_in = Input(Valid(new TransactionIdentity))
    val demand_out = RouteAChannels.packed_source_demand(p)
    val publication_authorization_out = RouteAChannels.publication_read_authorization(p)
    val descriptor_grant_out = RouteAChannels.descriptor_location_grant(p)
    val s2_fill_lease_out = RouteAChannels.s2_fill_lease(p)
    val rejected_out = Decoupled(new PersistentReadRejectionV2)
    val busy = Output(Bool())
  })

  private val states = Enum(10)
  private val Idle = states(0)
  private val NeedContext = states(1)
  private val WaitContext = states(2)
  private val WaitSelection = states(3)
  private val Query = states(4)
  private val WaitQuery = states(5)
  private val Reserve = states(6)
  private val WaitReservation = states(7)
  private val JointAccept = states(8)
  private val Complete = states(9)
  // Error is separate from accepted activation: no lease is owned here.
  val rejecting = RegInit(false.B)
  val state = RegInit(Idle)
  val plan = Reg(new SourceCompletionPlan(p))
  val owner = Reg(new R6PreflightContextResultV2)
  val selectedPage = Reg(new PageRef)
  val result = Reg(new PersistentReadResult(p))
  val lease = Reg(new S2FillLease(p))
  val haveLease = RegInit(false.B)
  val copied = RegInit(false.B)
  val sentDemand = RegInit(false.B)
  val sentPublication = RegInit(false.B)
  val sentDescriptor = RegInit(false.B)
  val sentLease = RegInit(false.B)
  val rejectedR6 = RegInit(false.B)
  val canceledBinder = RegInit(false.B)
  val rejectionSent = RegInit(false.B)
  val rejectionStatus = Reg(UInt(2.W))
  val demandOrdinal = RegInit(0.U(p.candidateOrdinalWidth.W))

  private val entries = p.r6.attentionTrackerEntries
  private val selectorIndexWidth = math.max(1, log2Ceil(entries))
  val selectorValid = RegInit(VecInit(Seq.fill(entries)(false.B)))
  val selectors = Reg(Vec(entries, new PersistentReadSelectionV2))
  val selectedIndex = Reg(UInt(selectorIndexWidth.W))
  private def sameIdentity(a: TransactionIdentity, b: TransactionIdentity): Bool = a.asUInt === b.asUInt
  private def samePage(a: PageRef, b: PageRef): Bool = a.asUInt === b.asUInt

  // Validate every hint against R6 before placing it in the bounded table.
  // This front-end is independent of source-declaration order, so four legal
  // attentions may provide selectors in any order without a head-of-line loop.
  val probePending = RegInit(false.B)
  val probeSent = RegInit(false.B)
  val probeCanceled = RegInit(false.B)
  val probe = Reg(new PersistentReadSelectionV2)
  val probeIndex = Reg(UInt(selectorIndexWidth.W))
  val localRejectPending = RegInit(false.B)
  val localReject = Reg(new PersistentReadRejectionV2)
  val contextInFlight = RegInit(false.B)
  val contextForSelector = RegInit(false.B)
  val contextRequestPending = RegInit(false.B)
  val contextRequestSelector = RegInit(false.B)
  val contextRequestIdentity = Reg(new TransactionIdentity)
  val freeSelectors = VecInit((0 until entries).map(i => !selectorValid(i)))
  val duplicateSelectors = VecInit((0 until entries).map(i => selectorValid(i) &&
    sameIdentity(selectors(i).transaction_identity, io.page_select_in.bits.transaction_identity)))
  io.page_select_in.ready := !probePending && !localRejectPending &&
    (freeSelectors.asUInt.orR || duplicateSelectors.asUInt.orR)
  when(io.page_select_in.fire) {
    when(duplicateSelectors.asUInt.orR) {
      localRejectPending := true.B
      localReject.transaction_identity := io.page_select_in.bits.transaction_identity
      localReject.status := PersistentReadStatus.Invalid.U
    }.otherwise {
      probe := io.page_select_in.bits
      probeIndex := PriorityEncoder(freeSelectors)
      probePending := true.B
      probeSent := false.B
      probeCanceled := false.B
    }
  }

  val selectorQuery = probePending && !probeSent && !localRejectPending
  val planQuery = state === NeedContext && !rejecting
  when(!contextRequestPending && !contextInFlight && (selectorQuery || planQuery)) {
    contextRequestPending := true.B
    contextRequestSelector := selectorQuery
    contextRequestIdentity := Mux(selectorQuery, probe.transaction_identity, plan.transaction_identity)
  }
  io.context_query_out.valid := contextRequestPending
  io.context_query_out.bits.transaction_identity := contextRequestIdentity
  when(io.context_query_out.fire) {
    contextRequestPending := false.B
    contextInFlight := true.B
    contextForSelector := contextRequestSelector
    when(contextRequestSelector) { probeSent := true.B }.otherwise { state := WaitContext }
  }
  io.context_result_in.ready := contextInFlight && (!contextForSelector || !localRejectPending)
  when(io.context_result_in.fire) {
    contextInFlight := false.B
    when(contextForSelector) {
      assert(sameIdentity(io.context_result_in.bits.transaction_identity, probe.transaction_identity))
      val terminalSame = io.attention_terminal_in.valid &&
        sameIdentity(io.attention_terminal_in.bits, probe.transaction_identity)
      when(io.context_result_in.bits.eligible && !probeCanceled && !terminalSame) {
        selectors(probeIndex) := probe
        selectorValid(probeIndex) := true.B
      }.otherwise {
        localRejectPending := true.B
        localReject.transaction_identity := probe.transaction_identity
        localReject.status := PersistentReadStatus.Invalid.U
      }
      probePending := false.B
      probeSent := false.B
      probeCanceled := false.B
    }.otherwise {
      assert(state === WaitContext)
      assert(sameIdentity(io.context_result_in.bits.transaction_identity, plan.transaction_identity))
      owner := io.context_result_in.bits
      when(io.context_result_in.bits.eligible) {
        state := WaitSelection
      }.otherwise {
        rejecting := true.B
        rejectionStatus := PersistentReadStatus.Invalid.U
      }
    }
  }

  val matchingSelectors = VecInit((0 until entries).map(i => selectorValid(i) &&
    sameIdentity(selectors(i).transaction_identity, plan.transaction_identity)))
  when(state === WaitSelection && matchingSelectors.asUInt.orR && !rejecting) {
    val index = PriorityEncoder(matchingSelectors)
    selectedIndex := index
    selectedPage := selectors(index).page_ref
    state := Query
  }

  // Legacy source sets without packed work retain the original direct
  // source-plan handshake. All packed plans remain held upstream until the
  // R6-owned preflight and S2 reservation have succeeded.
  val inputPacked = io.plan_in.bits.source_presence(RouteASourceKind.Packed)
  io.plan_out.valid := false.B
  io.plan_out.bits := io.plan_in.bits
  io.plan_in.ready := false.B
  when(state === Idle && !rejecting) {
    when(!inputPacked) {
      io.plan_out.valid := io.plan_in.valid
      io.plan_in.ready := io.plan_out.ready
    }.elsewhen(io.plan_in.valid) {
      plan := io.plan_in.bits
      owner.eligible := false.B
      haveLease := false.B
      copied := false.B
      sentDemand := false.B
      sentPublication := false.B
      sentDescriptor := false.B
      sentLease := false.B
      rejectedR6 := false.B
      canceledBinder := false.B
      rejectionSent := false.B
      state := NeedContext
    }
  }

  io.query_out.valid := state === Query && !rejecting
  io.query_out.bits.transaction_identity := plan.transaction_identity
  io.query_out.bits.page_ref := selectedPage
  io.query_out.bits.layer := owner.layer
  io.query_out.bits.kv_head := owner.kv_head
  when(io.query_out.fire) { state := WaitQuery }
  io.query_result_in.ready := state === WaitQuery && !rejecting
  when(io.query_result_in.fire) {
    val reply = io.query_result_in.bits
    val matching = sameIdentity(reply.grant.transaction_identity, plan.transaction_identity) &&
      samePage(reply.grant.page_ref, selectedPage) && reply.layer === owner.layer && reply.kv_head === owner.kv_head
    val pending = io.readiness_pending_in.valid &&
      samePage(io.readiness_pending_in.bits.page_ref, selectedPage) &&
      io.readiness_pending_in.bits.p3_layer === owner.layer &&
      io.readiness_pending_in.bits.kv_head === owner.kv_head
    when(matching && reply.status === PersistentReadStatus.OK.U &&
      reply.grant.live_reference_held && reply.grant.valid_records =/= 0.U &&
      reply.grant.valid_records <= 64.U && reply.grant.sidecar_records === reply.grant.valid_records) {
      result := reply
      state := Reserve
    }.elsewhen(matching && reply.status === PersistentReadStatus.NotReady.U && pending) {
      // Consume the response before retrying: the shared R5 query port must
      // remain available to install the exact receipt that enables this page.
      state := Query
    }.otherwise {
      rejectionStatus := Mux(reply.status === PersistentReadStatus.Fault.U,
        PersistentReadStatus.Fault.U, PersistentReadStatus.Invalid.U)
      rejecting := true.B
    }
  }

  io.reservation_request_out.valid := state === Reserve && !rejecting
  io.reservation_request_out.bits.transaction_identity := plan.transaction_identity
  io.reservation_request_out.bits.page_ref := selectedPage
  io.reservation_request_out.bits.selected_instance := plan.packed_instance
  when(io.reservation_request_out.fire) { state := WaitReservation }
  io.reservation_result_in.ready := state === WaitReservation && !rejecting
  when(io.reservation_result_in.fire) {
    val reply = io.reservation_result_in.bits
    val matching = sameIdentity(reply.lease.transaction_identity, plan.transaction_identity) &&
      samePage(reply.lease.page_ref, selectedPage)
    when(reply.status === S2ReservationStatusV2.Granted.U) {
      // A granted resource may not be discarded through an ordinary error
      // branch. The S2-owned exact reply is a producer contract assertion.
      assert(matching && reply.lease.s2_slot === plan.packed_instance.instance_coordinate &&
        reply.lease.source_generation === plan.packed_instance.generation && reply.lease.requires_sidecar)
      lease := reply.lease
      haveLease := true.B
      state := JointAccept
    }.elsewhen(reply.status === S2ReservationStatusV2.Busy.U && matching) {
      state := Reserve
    }.otherwise {
      rejectionStatus := PersistentReadStatus.Invalid.U
      rejecting := true.B
    }
  }

  when(state === JointAccept && !rejecting) {
    assert(haveLease)
    assert(io.plan_in.valid && io.plan_in.bits.asUInt === plan.asUInt)
    io.plan_out.valid := io.plan_in.valid
    io.plan_out.bits := plan
    io.plan_in.ready := io.plan_out.ready
    when(io.plan_out.fire) {
      selectorValid(selectedIndex) := false.B
      state := Complete
    }
  }

  io.accepted_plan_in.ready := state === Complete && !copied && !rejecting &&
    io.accepted_plan_in.bits.asUInt === plan.asUInt
  when(io.accepted_plan_in.fire) { copied := true.B }
  val emit = state === Complete && copied && !rejecting
  io.demand_out.valid := emit && !sentDemand
  io.demand_out.bits := 0.U.asTypeOf(new PackedSourceDemand(p))
  io.demand_out.bits.transaction_identity := plan.transaction_identity
  io.demand_out.bits.page_ref := selectedPage
  io.demand_out.bits.arrival_ordinal := demandOrdinal
  io.demand_out.bits.candidate_id := demandOrdinal
  io.demand_out.bits.eligibility_snapshot := ((BigInt(1) << RouteAR2PredicateBits.FifoPredecessor) |
    (BigInt(1) << RouteAR2PredicateBits.Ownership) | (BigInt(1) << RouteAR2PredicateBits.SourceCredit) |
    (BigInt(1) << RouteAR2PredicateBits.DestinationReady) |
    (BigInt(1) << RouteAR2PredicateBits.PackedMetadataPublished)).U
  io.demand_out.bits.destination_endpoint := 0.U
  io.publication_authorization_out.valid := emit && !sentPublication
  io.publication_authorization_out.bits.transaction_identity := plan.transaction_identity
  io.publication_authorization_out.bits.page_ref := selectedPage
  io.publication_authorization_out.bits.transaction_group_tag := result.transaction_group_tag
  io.publication_authorization_out.bits.valid_records := result.grant.valid_records
  io.publication_authorization_out.bits.packed_authoritative := true.B
  io.descriptor_grant_out.valid := emit && !sentDescriptor
  io.descriptor_grant_out.bits := result.grant
  io.s2_fill_lease_out.valid := emit && !sentLease
  io.s2_fill_lease_out.bits := lease
  when(io.demand_out.fire) { sentDemand := true.B }
  when(io.publication_authorization_out.fire) { sentPublication := true.B }
  when(io.descriptor_grant_out.fire) { sentDescriptor := true.B }
  when(io.s2_fill_lease_out.fire) { sentLease := true.B }
  when(emit && (sentDemand || io.demand_out.fire) &&
    (sentPublication || io.publication_authorization_out.fire) &&
    (sentDescriptor || io.descriptor_grant_out.fire) && (sentLease || io.s2_fill_lease_out.fire)) {
    state := Idle
    copied := false.B
    haveLease := false.B
    demandOrdinal := demandOrdinal + 1.U
  }

  io.r6_reject_out.valid := rejecting && owner.eligible && !rejectedR6
  io.r6_reject_out.bits.transaction_identity := plan.transaction_identity
  io.binder_cancel_out.valid := rejecting && !canceledBinder
  io.binder_cancel_out.bits.transaction_identity := plan.transaction_identity
  when(io.r6_reject_out.fire) { rejectedR6 := true.B }
  when(io.binder_cancel_out.fire) { canceledBinder := true.B }
  val rejectionOutPending = RegInit(false.B)
  val rejectionOutLocal = RegInit(false.B)
  val rejectionOutput = Reg(new PersistentReadRejectionV2)
  when(!rejectionOutPending && (localRejectPending || (rejecting && !rejectionSent))) {
    rejectionOutPending := true.B
    rejectionOutLocal := localRejectPending
    rejectionOutput := localReject
    when(!localRejectPending) {
      rejectionOutput.transaction_identity := plan.transaction_identity
      rejectionOutput.status := rejectionStatus
    }
  }
  io.rejected_out.valid := rejectionOutPending
  io.rejected_out.bits := rejectionOutput
  when(io.rejected_out.fire) {
    rejectionOutPending := false.B
    when(rejectionOutLocal) { localRejectPending := false.B }.otherwise { rejectionSent := true.B }
  }
  when(rejecting) {
    assert(!haveLease, "preflight rejection cannot silently discard an S2 reservation")
    assert(!io.plan_out.fire)
    when((!owner.eligible || rejectedR6 || io.r6_reject_out.fire) &&
      (canceledBinder || io.binder_cancel_out.fire) &&
      (rejectionSent || (io.rejected_out.fire && !rejectionOutLocal))) {
      for (i <- 0 until entries) {
        when(selectorValid(i) && sameIdentity(selectors(i).transaction_identity, plan.transaction_identity)) {
          selectorValid(i) := false.B
        }
      }
      rejecting := false.B
      state := Idle
    }
  }

  for (i <- 0 until entries) {
    when(io.attention_terminal_in.valid && selectorValid(i) &&
      sameIdentity(selectors(i).transaction_identity, io.attention_terminal_in.bits)) {
      selectorValid(i) := false.B
    }
  }
  when(io.attention_terminal_in.valid && probePending &&
    sameIdentity(probe.transaction_identity, io.attention_terminal_in.bits)) { probeCanceled := true.B }

  io.busy := state =/= Idle || rejecting || probePending || contextRequestPending ||
    contextInFlight || localRejectPending || rejectionOutPending
  private def holdCheck[T <: Data](channel: chisel3.util.DecoupledIO[T]): Unit = {
    val held = RegEnable(channel.bits, channel.valid && !channel.ready)
    when(RegNext(channel.valid && !channel.ready, false.B)) { assert(channel.bits.asUInt === held.asUInt) }
  }
  holdCheck(io.plan_out)
  holdCheck(io.context_query_out)
  holdCheck(io.query_out)
  holdCheck(io.reservation_request_out)
  holdCheck(io.r6_reject_out)
  holdCheck(io.binder_cancel_out)
  holdCheck(io.demand_out)
  holdCheck(io.publication_authorization_out)
  holdCheck(io.descriptor_grant_out)
  holdCheck(io.s2_fill_lease_out)
  holdCheck(io.rejected_out)
}
