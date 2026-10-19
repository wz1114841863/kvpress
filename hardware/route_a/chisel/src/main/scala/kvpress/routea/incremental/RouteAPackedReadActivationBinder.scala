package kvpress.routea.incremental

import chisel3._
import chisel3.util.{RegEnable, Valid, is, switch}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * Lossless exact-copy fork for the one R6-accepted completion plan.
  *
 * The packet path observes every nonempty accepted plan.  The hot and packed
 * activation paths receive the same bits only when their respective source is
 * present.  Each consumer may backpressure independently; this module chooses
 * no source and creates no second plan.
  */
final class RouteASourceCompletionPlanActivationFork(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_source_completion_plan_activation_fork"

  val io = IO(new Bundle {
    val accepted_plan_in = Flipped(RouteAChannels.source_completion_plan(p))
    val packet_plan_out = RouteAChannels.source_completion_plan(p)
    val hot_activation_plan_out = RouteAChannels.source_completion_plan(p)
    val packed_activation_plan_out = RouteAChannels.source_completion_plan(p)
  })

  val full = RegInit(false.B)
  val packetPending = RegInit(false.B)
  val hotPending = RegInit(false.B)
  val packedPending = RegInit(false.B)
  val held = Reg(new SourceCompletionPlan(p))

  io.accepted_plan_in.ready := !full
  io.packet_plan_out.valid := full && packetPending
  io.packet_plan_out.bits := held
  io.hot_activation_plan_out.valid := full && hotPending
  io.hot_activation_plan_out.bits := held
  io.packed_activation_plan_out.valid := full && packedPending
  io.packed_activation_plan_out.bits := held

  when(io.accepted_plan_in.fire) {
    held := io.accepted_plan_in.bits
    full := true.B
    packetPending := true.B
    hotPending := io.accepted_plan_in.bits.source_presence(RouteASourceKind.Hot)
    packedPending := io.accepted_plan_in.bits.source_presence(RouteASourceKind.Packed)
  }
  when(io.packet_plan_out.fire) { packetPending := false.B }
  when(io.hot_activation_plan_out.fire) { hotPending := false.B }
  when(io.packed_activation_plan_out.fire) { packedPending := false.B }
  when(full && (!packetPending || io.packet_plan_out.fire) &&
      (!hotPending || io.hot_activation_plan_out.fire) &&
      (!packedPending || io.packed_activation_plan_out.fire)) {
    full := false.B
  }

  val heldPacket = RegEnable(io.packet_plan_out.bits,
    io.packet_plan_out.valid && !io.packet_plan_out.ready)
  when(RegNext(io.packet_plan_out.valid && !io.packet_plan_out.ready, false.B)) {
    assert(io.packet_plan_out.bits.asUInt === heldPacket.asUInt)
  }
  val heldHot = RegEnable(io.hot_activation_plan_out.bits,
    io.hot_activation_plan_out.valid && !io.hot_activation_plan_out.ready)
  when(RegNext(io.hot_activation_plan_out.valid && !io.hot_activation_plan_out.ready, false.B)) {
    assert(io.hot_activation_plan_out.bits.asUInt === heldHot.asUInt)
  }
  val heldPacked = RegEnable(io.packed_activation_plan_out.bits,
    io.packed_activation_plan_out.valid && !io.packed_activation_plan_out.ready)
  when(RegNext(io.packed_activation_plan_out.valid && !io.packed_activation_plan_out.ready, false.B)) {
    assert(io.packed_activation_plan_out.bits.asUInt === heldPacked.asUInt)
  }
}

/**
 * Converts only the immutable hot selection already accepted by R6 into the
 * existing hot-owner open carrier.  It has no payload, address, scheduling,
 * or authority state: source selection remains in the accepted plan and hot
 * residency remains owned by [[RouteAHotSourcePath]].
 */
final class RouteAHotSourcePlanActivationAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_hot_source_plan_activation_adapter"

  val io = IO(new Bundle {
    val accepted_plan_in = Flipped(RouteAChannels.source_completion_plan(p))
    val hot_source_open_out = RouteAChannels.hot_source_open(p)
  })

  val pending = RegInit(false.B)
  val held = Reg(new SourceCompletionPlan(p))
  val inputLegal = io.accepted_plan_in.bits.source_presence(RouteASourceKind.Hot) &&
    io.accepted_plan_in.bits.hot_instance.source_kind === RouteASourceKind.Hot.U

  io.accepted_plan_in.ready := !pending && inputLegal
  when(io.accepted_plan_in.fire) {
    held := io.accepted_plan_in.bits
    pending := true.B
  }

  io.hot_source_open_out.valid := pending
  io.hot_source_open_out.bits.transaction_identity := held.transaction_identity
  io.hot_source_open_out.bits.source_instance := held.hot_instance
  when(io.hot_source_open_out.fire) { pending := false.B }

  val heldOpen = RegEnable(io.hot_source_open_out.bits,
    io.hot_source_open_out.valid && !io.hot_source_open_out.ready)
  when(RegNext(io.hot_source_open_out.valid && !io.hot_source_open_out.ready, false.B)) {
    assert(io.hot_source_open_out.bits.asUInt === heldOpen.asUInt)
  }
}

/**
  * RTL3.8.1 finite, fail-closed materializer for one already selected packed
  * source activation.
  *
  * R6 owns source-set selection; R3 owns the publication observation; R5 owns
  * the opaque readable-descriptor fact; and S2 owns the fill lease.  This
  * binder owns none of those facts.  It only creates the four identity-bound
  * carriers required by [[RouteAPackedReadAssociationOwner]] after their
  * exact join succeeds.  In particular, it never creates a metadata publish,
  * descriptor mutation, S2 allocation, authority transition, or R2 choice.
  *
  * The one held association is a functional closure baseline.  It is not an
  * R2 outstanding-request limit or a scheduler policy.
  */
final class RouteAPackedReadActivationBinder(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_packed_read_activation_binder"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    // Exact copy of an R6-accepted plan.  It is intentionally an input rather
    // than a source-plan declaration: this module cannot select a source set.
    val accepted_plan_in = Flipped(RouteAChannels.source_completion_plan(p))
    // R3's immutable member stream is consumed here rather than discarded by
    // the top.  R3 still owns its ledger and observes R6 acceptance; this
    // binder only validates the emitted stream against the later page-ready
    // summary and never becomes an authority owner.
    val publication_member_in = Flipped(RouteAChannels.publication_member_observation(p))
    // R3 emits this read-only fact only after the committed page's complete
    // member ledger has seen the actual R3->R6 acceptance handshakes.
    val post_r6_page_ready_in = Flipped(RouteAChannels.post_r6_packed_page_ready_observation(p))
    // The binder requests, but never constructs, the two owner-local facts.
    // Requests contain no address and preserve R6's selected SourceInstance.
    val descriptor_location_request_out = RouteAChannels.descriptor_location_request(p)
    val s2_fill_lease_request_out = RouteAChannels.s2_fill_lease_request(p)
    // R5/S2 owner responses; the binder cannot infer handles or slots.
    val descriptor_grant_in = Flipped(RouteAChannels.descriptor_location_grant(p))
    val s2_fill_lease_in = Flipped(RouteAChannels.s2_fill_lease(p))
    val demand_out = RouteAChannels.packed_source_demand(p)
    val publication_authorization_out = RouteAChannels.publication_read_authorization(p)
    val descriptor_grant_out = RouteAChannels.descriptor_location_grant(p)
    val s2_fill_lease_out = RouteAChannels.s2_fill_lease(p)
    // A one-cycle observation only.  It is neither a terminal outcome nor an
    // authority/fault event; callers may use it for directed fail-closed tests.
    val rejected_observation = Output(Valid(new TransactionIdentity))
  })

  private val Collect = 0.U(2.W)
  private val Evaluate = 1.U(2.W)
  private val Emit = 2.U(2.W)
  val state = RegInit(Collect)

  val havePlan = RegInit(false.B)
  val havePageReady = RegInit(false.B)
  val haveMemberStream = RegInit(false.B)
  val memberStreamPoisoned = RegInit(false.B)
  val memberStreamLayer = Reg(UInt(RouteAAnchorWidths.LayerWidth.W))
  val memberStreamTag = Reg(UInt(p.transactionGroupTagWidth.W))
  val memberNextOrdinal = RegInit(0.U(RouteAAnchorWidths.P3ValidRecordsWidth.W))
  val haveDescriptor = RegInit(false.B)
  val haveLease = RegInit(false.B)
  val plan = Reg(new SourceCompletionPlan(p))
  val publication = Reg(new PostR6PackedPageReadyObservation(p))
  val descriptor = Reg(new DescriptorLocationGrant(p))
  val lease = Reg(new S2FillLease(p))
  val demandOrdinal = RegInit(0.U(p.candidateOrdinalWidth.W))
  val sentDemand = RegInit(false.B)
  val sentPublication = RegInit(false.B)
  val sentDescriptor = RegInit(false.B)
  val sentLease = RegInit(false.B)
  val rejected = RegInit(false.B)
  val rejectedIdentity = Reg(new TransactionIdentity)

  private def sameIdentity(left: TransactionIdentity, right: TransactionIdentity): Bool =
    left.asUInt === right.asUInt
  private def samePage(left: PageRef, right: PageRef): Bool = left.asUInt === right.asUInt

  val planLegal = io.accepted_plan_in.bits.source_presence(RouteASourceKind.Packed) &&
    io.accepted_plan_in.bits.packed_instance.source_kind === RouteASourceKind.Packed.U
  val recordsLegal = publication.valid_records =/= 0.U && publication.valid_records <= 64.U
  val memberStreamMatchesReady = haveMemberStream && !memberStreamPoisoned &&
    memberStreamLayer === publication.p3_layer &&
    memberStreamTag === publication.transaction_group_tag &&
    memberNextOrdinal === publication.valid_records
  val descriptorMatchesHeldFacts =
    sameIdentity(plan.transaction_identity, descriptor.transaction_identity) &&
      samePage(publication.page_ref, descriptor.page_ref) &&
      recordsLegal && publication.valid_records === descriptor.valid_records &&
      descriptor.sidecar_records === descriptor.valid_records &&
      descriptor.live_reference_held
  val joinedExactly =
    plan.source_presence(RouteASourceKind.Packed) &&
      plan.packed_instance.source_kind === RouteASourceKind.Packed.U &&
      descriptorMatchesHeldFacts &&
      sameIdentity(plan.transaction_identity, lease.transaction_identity) &&
      samePage(publication.page_ref, lease.page_ref) &&
      plan.packed_instance.instance_coordinate === lease.s2_slot &&
      plan.packed_instance.generation === lease.source_generation &&
      lease.requires_sidecar

  val packedEligibility = (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.FifoPredecessor) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.Ownership) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.SourceCredit) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.DestinationReady) |
    (1.U(p.candidatePredicateWidth.W) << RouteAR2PredicateBits.PackedMetadataPublished)

  io.accepted_plan_in.ready := false.B
  io.publication_member_in.ready := false.B
  io.post_r6_page_ready_in.ready := false.B
  io.descriptor_grant_in.ready := false.B
  io.s2_fill_lease_in.ready := false.B
  io.descriptor_location_request_out.valid := havePlan && havePageReady && memberStreamMatchesReady && !haveDescriptor
  io.descriptor_location_request_out.bits.transaction_identity := plan.transaction_identity
  io.descriptor_location_request_out.bits.page_ref := publication.page_ref
  io.descriptor_location_request_out.bits.valid_records := publication.valid_records
  // Reserve scarce S2 state only after R5 has proved that the exact published
  // descriptor is readable.  A stale/unpublished page therefore cannot leak
  // a FILLING slot while the binder waits for an impossible R5 response.
  io.s2_fill_lease_request_out.valid := havePlan && havePageReady && memberStreamMatchesReady && haveDescriptor &&
    descriptorMatchesHeldFacts && !haveLease
  io.s2_fill_lease_request_out.bits.transaction_identity := plan.transaction_identity
  io.s2_fill_lease_request_out.bits.page_ref := publication.page_ref
  io.s2_fill_lease_request_out.bits.selected_instance := plan.packed_instance
  io.demand_out.valid := false.B
  io.demand_out.bits := 0.U.asTypeOf(new PackedSourceDemand(p))
  io.publication_authorization_out.valid := false.B
  io.publication_authorization_out.bits := 0.U.asTypeOf(new PublicationReadAuthorization(p))
  io.descriptor_grant_out.valid := false.B
  io.descriptor_grant_out.bits := descriptor
  io.s2_fill_lease_out.valid := false.B
  io.s2_fill_lease_out.bits := lease
  io.rejected_observation.valid := rejected
  io.rejected_observation.bits := rejectedIdentity

  when(!io.mem_init_done) {
    state := Collect
    havePlan := false.B
    havePageReady := false.B
    haveMemberStream := false.B
    memberStreamPoisoned := false.B
    memberNextOrdinal := 0.U
    haveDescriptor := false.B
    haveLease := false.B
    sentDemand := false.B
    sentPublication := false.B
    sentDescriptor := false.B
    sentLease := false.B
    rejected := false.B
  }.otherwise {
    when(rejected) { rejected := false.B }
    switch(state) {
      is(Collect) {
        io.accepted_plan_in.ready := !havePlan && planLegal
        // Consume the owner-produced member stream in exact ordinal order.
        // A malformed/duplicate fact is consumed once and poisons this
        // bounded association, so it can never produce first-use work.
        // C0 intentionally keeps one bounded page association in flight.  Do
        // not consume a later page's member stream while this completed stream
        // is awaiting/using its page-ready summary: that later stream has no
        // PageRef on this channel and must not be mistaken for a malformed
        // continuation of the current immutable ledger.  This is flow control
        // only; R3 and R6 retain all membership and authority ownership.
        io.publication_member_in.ready := !havePageReady &&
          !io.post_r6_page_ready_in.valid && !memberStreamPoisoned && memberNextOrdinal =/= 64.U
        io.post_r6_page_ready_in.ready := !havePageReady
        io.descriptor_grant_in.ready := !haveDescriptor
        io.s2_fill_lease_in.ready := !haveLease
        when(io.accepted_plan_in.fire) { plan := io.accepted_plan_in.bits; havePlan := true.B }
        when(io.publication_member_in.fire) {
          val member = io.publication_member_in.bits
          val firstMember = !haveMemberStream
          val memberMatches = (firstMember ||
            (member.layer === memberStreamLayer && member.transaction_group_tag === memberStreamTag)) &&
            member.group_member_ordinal === memberNextOrdinal
          when(memberMatches) {
            when(firstMember) {
              haveMemberStream := true.B
              memberStreamLayer := member.layer
              memberStreamTag := member.transaction_group_tag
            }
            memberNextOrdinal := memberNextOrdinal + 1.U
          }.otherwise {
            memberStreamPoisoned := true.B
          }
        }
        when(io.post_r6_page_ready_in.fire) { publication := io.post_r6_page_ready_in.bits; havePageReady := true.B }
        when(io.descriptor_grant_in.fire) { descriptor := io.descriptor_grant_in.bits; haveDescriptor := true.B }
        when(io.s2_fill_lease_in.fire) { lease := io.s2_fill_lease_in.bits; haveLease := true.B }
        when(havePageReady && (!recordsLegal || !memberStreamMatchesReady)) {
          rejected := true.B
          rejectedIdentity := plan.transaction_identity
          havePlan := false.B
          havePageReady := false.B
          haveDescriptor := false.B
          haveLease := false.B
          haveMemberStream := false.B
          memberStreamPoisoned := false.B
          memberNextOrdinal := 0.U
        }.elsewhen(havePlan && havePageReady && haveDescriptor && !descriptorMatchesHeldFacts) {
          // Never reserve scarce S2 state after a malformed/stale R5 fact.
          // The owner response is rejected before a lease request can escape.
          rejected := true.B
          rejectedIdentity := plan.transaction_identity
          havePlan := false.B
          havePageReady := false.B
          haveDescriptor := false.B
          haveLease := false.B
          haveMemberStream := false.B
          memberStreamPoisoned := false.B
          memberNextOrdinal := 0.U
        }.elsewhen(havePlan && havePageReady && haveDescriptor && haveLease && memberStreamMatchesReady) {
          state := Evaluate
        }
      }
      is(Evaluate) {
        when(joinedExactly) {
          state := Emit
        }.otherwise {
          rejected := true.B
          rejectedIdentity := plan.transaction_identity
          havePlan := false.B
          havePageReady := false.B
          haveDescriptor := false.B
          haveLease := false.B
          haveMemberStream := false.B
          memberStreamPoisoned := false.B
          memberNextOrdinal := 0.U
          state := Collect
        }
      }
      is(Emit) {
        io.demand_out.valid := !sentDemand
        io.demand_out.bits.transaction_identity := plan.transaction_identity
        io.demand_out.bits.page_ref := publication.page_ref
        // This is a local, monotonic materialization label only.  R2 still
        // owns the frozen eligibility/FIFO choice after it accepts the work.
        io.demand_out.bits.arrival_ordinal := demandOrdinal
        io.demand_out.bits.candidate_id := demandOrdinal
        io.demand_out.bits.eligibility_snapshot := packedEligibility
        // The existing functional core-memory target code remains opaque.  A
        // zero code is not an HBM channel/port/macro selection.
        io.demand_out.bits.destination_endpoint := 0.U
        io.publication_authorization_out.valid := !sentPublication
        io.publication_authorization_out.bits.transaction_identity := plan.transaction_identity
        io.publication_authorization_out.bits.page_ref := publication.page_ref
        io.publication_authorization_out.bits.transaction_group_tag := publication.transaction_group_tag
        io.publication_authorization_out.bits.valid_records := publication.valid_records
        io.publication_authorization_out.bits.packed_authoritative := true.B
        io.descriptor_grant_out.valid := !sentDescriptor
        io.s2_fill_lease_out.valid := !sentLease
        when(io.demand_out.fire) { sentDemand := true.B }
        when(io.publication_authorization_out.fire) { sentPublication := true.B }
        when(io.descriptor_grant_out.fire) { sentDescriptor := true.B }
        when(io.s2_fill_lease_out.fire) { sentLease := true.B }
        when((sentDemand || io.demand_out.fire) &&
          (sentPublication || io.publication_authorization_out.fire) &&
          (sentDescriptor || io.descriptor_grant_out.fire) &&
          (sentLease || io.s2_fill_lease_out.fire)) {
          demandOrdinal := demandOrdinal + 1.U
          havePlan := false.B
          havePageReady := false.B
          haveDescriptor := false.B
          haveLease := false.B
          haveMemberStream := false.B
          memberStreamPoisoned := false.B
          memberNextOrdinal := 0.U
          sentDemand := false.B
          sentPublication := false.B
          sentDescriptor := false.B
          sentLease := false.B
          state := Collect
        }
      }
    }
  }

  val heldDemand = RegEnable(io.demand_out.bits, io.demand_out.valid && !io.demand_out.ready)
  when(RegNext(io.demand_out.valid && !io.demand_out.ready, false.B)) {
    assert(io.demand_out.bits.asUInt === heldDemand.asUInt)
  }
  val heldPublication = RegEnable(io.publication_authorization_out.bits,
    io.publication_authorization_out.valid && !io.publication_authorization_out.ready)
  when(RegNext(io.publication_authorization_out.valid && !io.publication_authorization_out.ready, false.B)) {
    assert(io.publication_authorization_out.bits.asUInt === heldPublication.asUInt)
  }
  val heldDescriptor = RegEnable(io.descriptor_grant_out.bits,
    io.descriptor_grant_out.valid && !io.descriptor_grant_out.ready)
  when(RegNext(io.descriptor_grant_out.valid && !io.descriptor_grant_out.ready, false.B)) {
    assert(io.descriptor_grant_out.bits.asUInt === heldDescriptor.asUInt)
  }
  val heldLease = RegEnable(io.s2_fill_lease_out.bits, io.s2_fill_lease_out.valid && !io.s2_fill_lease_out.ready)
  when(RegNext(io.s2_fill_lease_out.valid && !io.s2_fill_lease_out.ready, false.B)) {
    assert(io.s2_fill_lease_out.bits.asUInt === heldLease.asUInt)
  }
  val heldDescriptorRequest = RegEnable(io.descriptor_location_request_out.bits,
    io.descriptor_location_request_out.valid && !io.descriptor_location_request_out.ready)
  when(RegNext(io.descriptor_location_request_out.valid && !io.descriptor_location_request_out.ready, false.B)) {
    assert(io.descriptor_location_request_out.bits.asUInt === heldDescriptorRequest.asUInt)
  }
  val heldLeaseRequest = RegEnable(io.s2_fill_lease_request_out.bits,
    io.s2_fill_lease_request_out.valid && !io.s2_fill_lease_request_out.ready)
  when(RegNext(io.s2_fill_lease_request_out.valid && !io.s2_fill_lease_request_out.ready, false.B)) {
    assert(io.s2_fill_lease_request_out.bits.asUInt === heldLeaseRequest.asUInt)
  }
}

/**
  * Production-shaped terminal association for one owner-materialized packed
  * read.  Every endpoint terminal reaches S2; only the final terminal becomes
  * the association terminal carrying the remembered PageRef/context ref.
  *
  * This is protocol association only.  It does not create a memory response,
  * decide success/fault, mark S2 READY, release a source, or retire a request.
  */
final class RouteAPackedReadTerminalBridge(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_packed_read_terminal_bridge"

  val io = IO(new Bundle {
    val work_in = Flipped(RouteAChannels.packed_s2_read_work(p))
    val work_out = RouteAChannels.packed_s2_read_work(p)
    val endpoint_terminal_in = Flipped(RouteAChannels.s2_fill_terminal(p))
    val s2_terminal_out = RouteAChannels.s2_fill_terminal(p)
    val association_terminal_out = RouteAChannels.packed_read_terminal(p)
  })

  val workActive = RegInit(false.B)
  val work = Reg(new PackedS2ReadWork(p))
  val terminalPending = RegInit(false.B)
  val terminal = Reg(new PackedReadTerminal(p))

  io.work_out.valid := io.work_in.valid && !workActive && !terminalPending
  io.work_out.bits := io.work_in.bits
  io.work_in.ready := io.work_out.ready && !workActive && !terminalPending
  when(io.work_in.fire) {
    work := io.work_in.bits
    workActive := true.B
  }

  val endpoint = io.endpoint_terminal_in.bits
  val endpointMatches = workActive && !terminalPending &&
    endpoint.transaction_identity.asUInt === work.transaction_identity.asUInt &&
    endpoint.s2_slot === work.s2_slot &&
    endpoint.source_generation === work.source_generation
  io.s2_terminal_out.valid := io.endpoint_terminal_in.valid && endpointMatches
  io.s2_terminal_out.bits := endpoint
  io.endpoint_terminal_in.ready := io.s2_terminal_out.ready && endpointMatches
  when(io.endpoint_terminal_in.fire && endpoint.last) {
    terminal.transaction_identity := work.transaction_identity
    terminal.page_ref := work.page_ref
    terminal.s2_slot := work.s2_slot
    terminal.source_generation := work.source_generation
    terminal.delivery_context_ref := work.delivery_context_ref
    terminal.status := endpoint.status
    terminalPending := true.B
  }

  io.association_terminal_out.valid := terminalPending
  io.association_terminal_out.bits := terminal
  when(io.association_terminal_out.fire) {
    terminalPending := false.B
    workActive := false.B
  }

  val heldWork = RegEnable(io.work_out.bits, io.work_out.valid && !io.work_out.ready)
  when(RegNext(io.work_out.valid && !io.work_out.ready, false.B)) {
    assert(io.work_out.bits.asUInt === heldWork.asUInt)
  }
  val heldS2Terminal = RegEnable(io.s2_terminal_out.bits,
    io.s2_terminal_out.valid && !io.s2_terminal_out.ready)
  when(RegNext(io.s2_terminal_out.valid && !io.s2_terminal_out.ready, false.B)) {
    assert(io.s2_terminal_out.bits.asUInt === heldS2Terminal.asUInt)
  }
  val heldAssociationTerminal = RegEnable(io.association_terminal_out.bits,
    io.association_terminal_out.valid && !io.association_terminal_out.ready)
  when(RegNext(io.association_terminal_out.valid && !io.association_terminal_out.ready, false.B)) {
    assert(io.association_terminal_out.bits.asUInt === heldAssociationTerminal.asUInt)
  }
}

/**
  * Lossless two-owner allocation join for the existing packed allocation lane.
  * The payload association and its later sidecar read are mutually exclusive
  * by contract; this module rejects a simultaneous offer rather than creating
  * a local priority policy.
  */
final class RouteAPackedAllocationOwnerMux(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_packed_allocation_owner_mux"
  val io = IO(new Bundle {
    val payload_allocate_in = Flipped(RouteAChannels.delivery_context_allocate(p))
    val payload_ordinal_in = Input(UInt(p.candidateOrdinalWidth.W))
    val payload_candidate_id_in = Input(UInt(p.candidateIdWidth.W))
    val payload_ack_out = RouteAChannels.delivery_context_allocation_ack(p)
    val sidecar_allocate_in = Flipped(RouteAChannels.delivery_context_allocate(p))
    val sidecar_ordinal_in = Input(UInt(p.candidateOrdinalWidth.W))
    val sidecar_candidate_id_in = Input(UInt(p.candidateIdWidth.W))
    val sidecar_ack_out = RouteAChannels.delivery_context_allocation_ack(p)
    val allocate_out = RouteAChannels.delivery_context_allocate(p)
    val ordinal_out = Output(UInt(p.candidateOrdinalWidth.W))
    val candidate_id_out = Output(UInt(p.candidateIdWidth.W))
    val ack_in = Flipped(RouteAChannels.delivery_context_allocation_ack(p))
  })
  val sidecarSelected = RegInit(false.B)
  val active = RegInit(false.B)
  val held = Reg(new DeliveryContextAllocation(p))
  val simultaneous = io.payload_allocate_in.valid && io.sidecar_allocate_in.valid
  assert(!simultaneous, "packed allocation mux requires one owner at a time")
  val chooseSidecar = io.sidecar_allocate_in.valid && !io.payload_allocate_in.valid
  io.allocate_out.valid := !active && (io.payload_allocate_in.valid || io.sidecar_allocate_in.valid) && !simultaneous
  io.allocate_out.bits := Mux(chooseSidecar, io.sidecar_allocate_in.bits, io.payload_allocate_in.bits)
  io.ordinal_out := Mux(chooseSidecar, io.sidecar_ordinal_in, io.payload_ordinal_in)
  io.candidate_id_out := Mux(chooseSidecar, io.sidecar_candidate_id_in, io.payload_candidate_id_in)
  io.payload_allocate_in.ready := io.allocate_out.fire && !chooseSidecar
  io.sidecar_allocate_in.ready := io.allocate_out.fire && chooseSidecar
  when(io.allocate_out.fire) { held := io.allocate_out.bits; sidecarSelected := chooseSidecar; active := true.B }
  val ackMatches = io.ack_in.bits.allocation.asUInt === held.asUInt
  io.ack_in.ready := active && ackMatches && Mux(sidecarSelected, io.sidecar_ack_out.ready, io.payload_ack_out.ready)
  io.payload_ack_out.valid := active && !sidecarSelected && io.ack_in.valid && ackMatches
  io.payload_ack_out.bits := io.ack_in.bits
  io.sidecar_ack_out.valid := active && sidecarSelected && io.ack_in.valid && ackMatches
  io.sidecar_ack_out.bits := io.ack_in.bits
  when(active && io.ack_in.valid) { assert(ackMatches) }
  when(io.ack_in.fire) { active := false.B }
}

/**
  * RTL3.8.2 functional sidecar delivery owner.
  *
  * It receives an immutable sidecar obligation only from an accepted packed
  * association, waits for that association's payload terminal observation,
  * and then allocates/issues one typed sidecar read through the existing
  * packed R2 class.  The module deliberately creates neither a PageRef,
  * sidecar handle, S2 lease, delivery context, memory response, nor a new R2
  * scheduling class.  A payload fault consumes the obligation without issue;
  * malformed release or allocation acknowledgement remains backpressured.
  */
final class RouteAFunctionalSidecarDeliveryAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_functional_sidecar_delivery_adapter"

  val io = IO(new Bundle {
    val work_in = Flipped(RouteAChannels.sidecar_read_work(p))
    val payload_release_in = Flipped(RouteAChannels.packed_read_release_observation(p))
    val registry_allocate_out = RouteAChannels.delivery_context_allocate(p)
    val registry_allocation_arrival_ordinal_out = Output(UInt(p.candidateOrdinalWidth.W))
    val registry_allocation_candidate_id_out = Output(UInt(p.candidateIdWidth.W))
    val registry_allocation_ack_in = Flipped(RouteAChannels.delivery_context_allocation_ack(p))
    val read_issue_out = RouteAChannels.read_issue_descriptor(p)
  })

  private val Idle = 0.U(2.W)
  private val AwaitPayloadTerminal = 1.U(2.W)
  private val AwaitAllocationAck = 2.U(2.W)
  private val EmitReadIssue = 3.U(2.W)
  val state = RegInit(Idle)
  val work = Reg(new SidecarReadWork(p))

  private def sameIdentity(left: TransactionIdentity, right: TransactionIdentity): Bool =
    left.asUInt === right.asUInt
  private def samePage(left: PageRef, right: PageRef): Bool = left.asUInt === right.asUInt

  val workLegal = io.work_in.bits.valid_records =/= 0.U && io.work_in.bits.valid_records <= 64.U
  io.work_in.ready := state === Idle && workLegal
  io.payload_release_in.ready := false.B
  io.registry_allocate_out.valid := false.B
  io.registry_allocate_out.bits := 0.U.asTypeOf(new DeliveryContextAllocation(p))
  io.registry_allocation_arrival_ordinal_out := work.arrival_ordinal
  io.registry_allocation_candidate_id_out := work.candidate_id
  io.registry_allocation_ack_in.ready := false.B
  io.read_issue_out.valid := false.B
  io.read_issue_out.bits := 0.U.asTypeOf(new ReadIssueDescriptor(p))

  when(io.work_in.fire) {
    work := io.work_in.bits
    state := AwaitPayloadTerminal
  }

  val payloadReleaseMatches =
    sameIdentity(io.payload_release_in.bits.transaction_identity, work.transaction_identity) &&
      samePage(io.payload_release_in.bits.page_ref, work.page_ref) &&
      io.payload_release_in.bits.s2_slot === work.s2_slot &&
      io.payload_release_in.bits.source_generation === work.source_generation

  val allocation = Wire(new DeliveryContextAllocation(p))
  allocation.candidate_class := p.r2S2PackedClassCode.U
  allocation.transaction_identity := work.transaction_identity
  allocation.target_kind := RouteADeliveryTargetKind.S2PackedSidecar.U
  allocation.target_identity_generation := work.source_generation
  allocation.expected_fragment_count := work.valid_records
  allocation.target_descriptor.write_endpoint := 0.U
  allocation.target_descriptor.p3_layer := 0.U
  allocation.target_descriptor.p3_stage_generation := 0.U
  allocation.target_descriptor.transaction_group_tag := 0.U
  allocation.target_descriptor.descriptor_kind := 0.U
  allocation.target_descriptor.descriptor_page_ref := work.page_ref
  allocation.target_descriptor.descriptor_line := work.sidecar_handle_or_address
  allocation.target_descriptor.s2_slot := work.s2_slot
  allocation.target_descriptor.source_generation := work.source_generation
  allocation.target_descriptor.requires_sidecar := true.B
  allocation.target_descriptor.pending_ordinal := 0.U
  allocation.target_descriptor.p3_member_payload_ref := 0.U
  allocation.target_descriptor.direct_source_last := false.B
  allocation.target_descriptor.direct_pending_association := 0.U.asTypeOf(new DirectPendingAssociationId(p))
  allocation.target_descriptor.direct_pending_storage_generation := 0.U
  allocation.target_descriptor.direct_pending_association_valid := false.B
  allocation.target_descriptor.pending_explicit_empty := false.B

  val allocationAckMatches = io.registry_allocation_ack_in.bits.allocation.asUInt === allocation.asUInt

  when(state === AwaitPayloadTerminal) {
    io.payload_release_in.ready := payloadReleaseMatches
    when(io.payload_release_in.fire) {
      when(io.payload_release_in.bits.status === p.coreMemoryOkStatusCode.U) {
        state := AwaitAllocationAck
      }.otherwise {
        // Payload must have completed successfully before position sidecar
        // traffic may start. A fault remains an S2 fault path, never a
        // sidecar completion or a fallback request.
        state := Idle
      }
    }
  }
  when(state === AwaitAllocationAck) {
    io.registry_allocate_out.valid := true.B
    io.registry_allocate_out.bits := allocation
    when(io.registry_allocate_out.fire) { state := EmitReadIssue }
  }
  when(state === EmitReadIssue) {
    io.read_issue_out.valid := io.registry_allocation_ack_in.valid && allocationAckMatches
    io.read_issue_out.bits.delivery_context_ref := io.registry_allocation_ack_in.bits.delivery_context_ref
    io.read_issue_out.bits.candidate_class := p.r2S2PackedClassCode.U
    io.read_issue_out.bits.arrival_ordinal := work.arrival_ordinal
    io.read_issue_out.bits.candidate_id := work.candidate_id
    io.read_issue_out.bits.eligibility_snapshot := work.eligibility_snapshot
    io.read_issue_out.bits.transaction_identity := work.transaction_identity
    io.read_issue_out.bits.source_kind := RouteASourceKind.Packed.U
    io.read_issue_out.bits.payload_handle_or_address := work.sidecar_handle_or_address
    io.read_issue_out.bits.valid_count := work.valid_records
    io.read_issue_out.bits.expected_generation_or_validity := work.source_generation
    io.read_issue_out.bits.destination_endpoint := work.destination_endpoint
    io.read_issue_out.bits.expected_fragment_count := work.valid_records
    io.read_issue_out.bits.target_descriptor := allocation.target_descriptor
    // The acknowledgement and issue form a single lossless handoff: the
    // source adapter may not consume the ack unless R2 can accept its exact
    // immutable candidate in this same transaction.
    io.registry_allocation_ack_in.ready := allocationAckMatches && io.read_issue_out.ready
    when(io.read_issue_out.fire) { state := Idle }
  }

  val heldAllocation = RegEnable(io.registry_allocate_out.bits,
    io.registry_allocate_out.valid && !io.registry_allocate_out.ready)
  when(RegNext(io.registry_allocate_out.valid && !io.registry_allocate_out.ready, false.B)) {
    assert(io.registry_allocate_out.bits.asUInt === heldAllocation.asUInt)
  }
  val heldIssue = RegEnable(io.read_issue_out.bits,
    io.read_issue_out.valid && !io.read_issue_out.ready)
  when(RegNext(io.read_issue_out.valid && !io.read_issue_out.ready, false.B)) {
    assert(io.read_issue_out.bits.asUInt === heldIssue.asUInt)
  }
}

/** Strict non-arbitrating merge for sequential payload and sidecar R2 reads. */
final class RouteAExclusivePackedS2ReadIngress(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_exclusive_packed_s2_read_ingress"
  val io = IO(new Bundle {
    val payload_in = Flipped(RouteAChannels.source_candidate(p))
    val sidecar_in = Flipped(RouteAChannels.source_candidate(p))
    val out = RouteAChannels.source_candidate(p)
  })
  val simultaneous = io.payload_in.valid && io.sidecar_in.valid
  assert(!simultaneous, "payload and sidecar packed reads must be sequenced")
  io.out.valid := (io.payload_in.valid || io.sidecar_in.valid) && !simultaneous
  io.out.bits := Mux(io.payload_in.valid, io.payload_in.bits, io.sidecar_in.bits)
  io.payload_in.ready := io.out.ready && !io.sidecar_in.valid
  io.sidecar_in.ready := io.out.ready && !io.payload_in.valid
}

/** Strict terminal join; a sidecar fault may fault S2 but never make it READY. */
final class RouteAExclusiveS2FillTerminalIngress(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_exclusive_s2_fill_terminal_ingress"
  val io = IO(new Bundle {
    val payload_in = Flipped(RouteAChannels.s2_fill_terminal(p))
    val sidecar_in = Flipped(RouteAChannels.s2_fill_terminal(p))
    val out = RouteAChannels.s2_fill_terminal(p)
  })
  val simultaneous = io.payload_in.valid && io.sidecar_in.valid
  assert(!simultaneous, "payload and sidecar terminals must be sequenced")
  io.out.valid := (io.payload_in.valid || io.sidecar_in.valid) && !simultaneous
  io.out.bits := Mux(io.payload_in.valid, io.payload_in.bits, io.sidecar_in.bits)
  io.payload_in.ready := io.out.ready && !io.sidecar_in.valid
  io.sidecar_in.ready := io.out.ready && !io.payload_in.valid
}
