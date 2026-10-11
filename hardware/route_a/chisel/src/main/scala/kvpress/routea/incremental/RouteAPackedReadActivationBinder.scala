package kvpress.routea.incremental

import chisel3._
import chisel3.util.{RegEnable, Valid, is, switch}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

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
    // R3 emits this only after its atomic publication boundary.  The carrier
    // has no query identity; the binder binds it to the accepted R6 identity
    // only after PageRef/record-count checks below.
    val publication_commit_in = Flipped(RouteAChannels.publication_commit_observation(p))
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
  val havePublication = RegInit(false.B)
  val haveDescriptor = RegInit(false.B)
  val haveLease = RegInit(false.B)
  val plan = Reg(new SourceCompletionPlan(p))
  val publication = Reg(new PublicationCommitObservation(p))
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
  io.publication_commit_in.ready := false.B
  io.descriptor_grant_in.ready := false.B
  io.s2_fill_lease_in.ready := false.B
  io.descriptor_location_request_out.valid := havePlan && havePublication && !haveDescriptor
  io.descriptor_location_request_out.bits.transaction_identity := plan.transaction_identity
  io.descriptor_location_request_out.bits.page_ref := publication.page_ref
  io.descriptor_location_request_out.bits.valid_records := publication.valid_records
  // Reserve scarce S2 state only after R5 has proved that the exact published
  // descriptor is readable.  A stale/unpublished page therefore cannot leak
  // a FILLING slot while the binder waits for an impossible R5 response.
  io.s2_fill_lease_request_out.valid := havePlan && havePublication && haveDescriptor &&
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
    havePublication := false.B
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
        io.publication_commit_in.ready := !havePublication
        io.descriptor_grant_in.ready := !haveDescriptor
        io.s2_fill_lease_in.ready := !haveLease
        when(io.accepted_plan_in.fire) { plan := io.accepted_plan_in.bits; havePlan := true.B }
        when(io.publication_commit_in.fire) { publication := io.publication_commit_in.bits; havePublication := true.B }
        when(io.descriptor_grant_in.fire) { descriptor := io.descriptor_grant_in.bits; haveDescriptor := true.B }
        when(io.s2_fill_lease_in.fire) { lease := io.s2_fill_lease_in.bits; haveLease := true.B }
        when(havePlan && havePublication && haveDescriptor && !descriptorMatchesHeldFacts) {
          // Never reserve scarce S2 state after a malformed/stale R5 fact.
          // The owner response is rejected before a lease request can escape.
          rejected := true.B
          rejectedIdentity := plan.transaction_identity
          havePlan := false.B
          havePublication := false.B
          haveDescriptor := false.B
          haveLease := false.B
        }.elsewhen(havePlan && havePublication && haveDescriptor && haveLease) {
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
          havePublication := false.B
          haveDescriptor := false.B
          haveLease := false.B
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
          havePublication := false.B
          haveDescriptor := false.B
          haveLease := false.B
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
