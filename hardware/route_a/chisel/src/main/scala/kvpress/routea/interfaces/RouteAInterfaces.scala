package kvpress.routea.interfaces

import chisel3._
import chisel3.util.{Decoupled, DecoupledIO}
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/** Common ready/valid tie-offs used only by the inert RTL1.0 structural shell. */
object StructuralTieOff {
  def source[T <: Data](channel: DecoupledIO[T]): Unit = {
    channel.valid := false.B
    channel.bits := 0.U.asTypeOf(channel.bits)
  }

  def sink[T <: Data](channel: DecoupledIO[T]): Unit = {
    channel.ready := false.B
  }
}

/** Fixed semantic positions in the RTL1.2 R2 eligibility snapshot. */
object RouteAR2PredicateBits {
  final val FifoPredecessor = 0
  final val Ownership = 1
  final val SourceCredit = 2
  final val DestinationReady = 3
  final val PackedMetadataPublished = 4
  final val PendingAuthoritative = 5
  final val P3StageReadyOwned = 6
  final val PageAllocated = 7
  final val P3StageComplete = 8
  final val P3StageOwned = 9
}

/**
  * Legacy RTL2.1b write-router keys retained only by direct historical
  * harnesses. The production top uses the RTL2.2.2 registry-resolved typed
  * router and must not treat these values as a deployed encoding.
  */
object RouteARTL2WriteDeliveryContext {
  final val R5Reclaim = 0
  final val R5Append = 1
  final val R3PackedWrite = 2
}

/**
  * Semantic target classes held by the RTL2.2 delivery-context registry.
  * These names freeze routing meaning only; they select no endpoint layout,
  * physical port, storage implementation, or service rate.
  */
object RouteADeliveryTargetKind {
  final val Width = 3
  final val P3PendingRead = 0
  final val S2FullFill = 1
  final val S2PackedFill = 2
  final val DirectPendingRead = 3
  final val PackedWriteTerminal = 4
  final val DescriptorMaintenanceTerminal = 5
  // Logical sidecar-response route for the already selected packed source.
  // It reuses the frozen packed read class and selects no new R2 class.
  final val S2PackedSidecar = 6
}

/** Registry-selected write endpoint; it is not a physical crossbar encoding. */
object RouteAWriteDeliveryEndpoint {
  final val Width = 2
  final val P3PackedWrite = 0
  final val R5Append = 1
  final val R5Reclaim = 2
}

final class TransactionIdentity extends Bundle {
  val request_id = UInt(RouteAAnchorWidths.RequestIdWidth.W)
  val incarnation = UInt(RouteAAnchorWidths.IncarnationWidth.W)
}

/**
  * Immutable identity used only to correlate one pending descriptor, one R2
  * direct-class candidate, and the endpoint generation opened for it. It is
  * neither a payload address nor a second authority record.
  */
final class DirectPendingAssociationId(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val key = new PendingDescriptorKey(p)
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
}

/** R2's exact stored-candidate observation for the MR-1B direct class. */
final class DirectPendingCandidateAccepted(p: RouteASkeletonParameters) extends Bundle {
  val association_id = new DirectPendingAssociationId(p)
}

/** Descriptor-owner observation that one accepted association lost pending-read eligibility. */
final class DirectPendingAssociationWithdrawal(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val key = new PendingDescriptorKey(p)
  val pending_storage_generation = UInt(p.sourceGenerationWidth.W)
}

/** Exact R2 stored-candidate removal before the joint R2/R1 issue edge. */
final class DirectPendingCandidateCancel(p: RouteASkeletonParameters) extends Bundle {
  val association_id = new DirectPendingAssociationId(p)
  val reason = UInt(2.W)
}

/** R2 acknowledges that it removed precisely the named pre-issue direct slot. */
final class DirectPendingCandidateCancelAck(p: RouteASkeletonParameters) extends Bundle {
  val association_id = new DirectPendingAssociationId(p)
}

/** Read-only descriptor-owner proof request for one stored R2 direct slot. */
final class DirectPendingLeaseEligibilityQuery(p: RouteASkeletonParameters) extends Bundle {
  val association_id = new DirectPendingAssociationId(p)
  val pending_storage_generation = UInt(p.sourceGenerationWidth.W)
}

/** Immutable response to an eligibility query; it never creates lease state. */
final class DirectPendingLeaseEligibility(p: RouteASkeletonParameters) extends Bundle {
  val association_id = new DirectPendingAssociationId(p)
  val eligible = Bool()
  val permanent_failure = Bool()
}

/** One lease-state request that is legal only on the joint R2/R1 issue fire. */
final class DirectPendingLeaseCommit(p: RouteASkeletonParameters) extends Bundle {
  val association_id = new DirectPendingAssociationId(p)
  val pending_storage_generation = UInt(p.sourceGenerationWidth.W)
}

/**
  * Immutable typed routing descriptor supplied by the named producer before
  * R2 sees a candidate. R2 transports but never decodes it; the registry
  * retains the authoritative copy and the later router consumes only that
  * copy. Read-owner fields are present for the frozen interface but remain
  * unconnected to functional S2/direct/P3-read endpoints until later RTL2
  * slices.
  */
final class DeliveryTargetDescriptor(p: RouteASkeletonParameters) extends Bundle {
  val write_endpoint = UInt(RouteAWriteDeliveryEndpoint.Width.W)
  val p3_layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val p3_stage_generation = UInt(p.p3StageGenerationWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val descriptor_kind = UInt(2.W)
  val descriptor_page_ref = new PageRef
  val descriptor_line = UInt(p.coreMemoryAddressRefWidth.W)
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val requires_sidecar = Bool()
  val pending_ordinal = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  // The immutable retained-member payload identity for a P3 pending-read
  // endpoint.  It is deliberately distinct from the parameterized opaque
  // core-side address/handle: the latter is transport-facing while this field
  // is the exact association P3 checks before functional deposition.
  val p3_member_payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  // Direct-pending source completion is distinct from the last fragment of a
  // 512-B record. This immutable flag reaches the typed endpoint unchanged.
  val direct_source_last = Bool()
  // MR-1B preserves the descriptor/accepted-source/endpoint association
  // through R2 and the registry. Non-direct classes leave these fields inert.
  val direct_pending_association = new DirectPendingAssociationId(p)
  val direct_pending_storage_generation = UInt(p.sourceGenerationWidth.W)
  val direct_pending_association_valid = Bool()
  val pending_explicit_empty = Bool()
}

final class PageRef extends Bundle {
  val page_id = UInt(RouteAAnchorWidths.PageIdWidth.W)
  val generation = UInt(RouteAAnchorWidths.PageGenerationWidth.W)
}

/**
  * R5-owned post-durability observation for one reclaimed allocator entry.
  *
  * The page reference is the *old* live generation.  This is not an allocator
  * request/grant and is never permission to free a page: R5 creates it only
  * after its matching descriptor-invalidation terminal has been accepted.
  * It exists so the testbench scoreboard does not infer page-free events from
  * a descriptor image or arbitrary R5 state.
  */
final class PageAllocatorRelease extends Bundle {
  val page_ref = new PageRef
}

/**
  * Carrier for the score-free frontend logical tagged union. event_kind is
  * intentionally width-parameterized: RTL1.0 does not select its encoding.
  */
final class FrontendLifecycleRequest(p: RouteASkeletonParameters) extends Bundle {
  val event_kind = UInt(p.frontendEventKindWidth.W)
  val session_id = Bool()
  val context_tokens = UInt(RouteAAnchorWidths.ContextTokensWidth.W)
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val logical_position = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val disposition = Bool()
  val transaction_identity = new TransactionIdentity
  // These fields are meaningful only on an accepted RETAIN maturity.  They
  // carry an upstream-frozen page-group association; R6 never chooses it.
  val admission_group_tag = UInt(p.transactionGroupTagWidth.W)
  val admission_member_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val admission_group_valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

final class RuntimeRetireRequest extends Bundle {
  val session_id = Bool()
  val transaction_identity = new TransactionIdentity
}

final class AttentionTerminalResponse extends Bundle {
  val transaction_identity = new TransactionIdentity
  val terminal_status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

final class SessionRetireAck extends Bundle {
  val session_id = Bool()
  val transaction_identity = new TransactionIdentity
}

/** Retirement-only R6-to-R5 association; it is not an allocator grant. */
final class ReclaimPermit extends Bundle {
  val transaction_identity = new TransactionIdentity
}

final class ComponentStatus(p: RouteASkeletonParameters) extends Bundle {
  val acknowledgement_name = UInt(p.componentStatusNameWidth.W)
  val asserted = Bool()
}

final class HotControl(p: RouteASkeletonParameters) extends Bundle {
  val control_kind = UInt(p.hotControlKindWidth.W)
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val logical_position = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val disposition = Bool()
}

/** Logical authority state codes for the R6 control carrier, not a storage encoding. */
object RouteAAuthorityStateCode {
  final val None = 0
  final val Hot = 1
  final val Pending = 2
  final val Packed = 3
}

/**
  * Lifecycle-originated or R3-confirmed authority handoff. This carries only
  * the event-level semantic association; it is not a second token-residency
  * table, M2 record, or packed-page payload interface.
  */
final class R6AuthorityTransition(p: RouteASkeletonParameters) extends Bundle {
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val from_authority = UInt(2.W)
  val to_authority = UInt(2.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
}

/**
  * Immutable, post-decision association for one retained record.  The group
  * fields are supplied by the admission owner; R3 validates and records them,
  * but neither re-runs KVzap admission nor substitutes a contiguous span.
  * This is a control association, never a payload transfer or authority copy.
  */
final class AdmissionContext(p: RouteASkeletonParameters) extends Bundle {
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val logical_position = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val group_member_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val group_valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/**
  * Immutable pending-payload location association for exactly one admitted
  * member.  The pending payload owner supplies the opaque handle and source
  * generation; R3 only validates, records, and later consumes this association.
  * It is neither a physical address format nor an R2 scheduling grant.
  */
final class PendingPayloadReadBinding(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val logical_position = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val group_member_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val group_valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
  // MR-2 M2 carrier provenance.  These are an immutable, group-scoped
  // logical M2 mapping fact supplied by the pending-payload/location owner
  // when the binding participates in R3 packing.  They are neither a payload
  // address nor a physical M2/SRAM address or owner encoding.
  val m2_group_opaque_address_ref = UInt(p.coreMemoryAddressRefWidth.W)
  val m2_group_owner = UInt(RouteAAnchorWidths.RequestIdWidth.W)
}

/**
  * Immutable identity of one pending-payload descriptor.  This is a
  * descriptor-directory key, not a payload address, R6 SourceInstance, or
  * residency authority.
  */
final class PendingDescriptorKey(p: RouteASkeletonParameters) extends Bundle {
  val pending_descriptor_ref = UInt(p.pendingDescriptorRefWidth.W)
  val pending_descriptor_generation = UInt(p.pendingValidityWidth.W)
}

/**
  * Pending-source descriptor facts produced by the pending payload/location
  * owner at pending maturity.  In MR-1B this is deliberately one record only:
  * `valid_count` must be exactly one and `source_last` is a literal
  * descriptor fact, never reconstructed from R1 fragments or R3 membership.
  */
final class PendingSourceDescriptorRegistration(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val key = new PendingDescriptorKey(p)
  // Immutable provenance from the same pending-payload/location owner that
  // formed this descriptor.  These fields do not select packing: they let R3
  // later prove whether this descriptor was actually accepted into its
  // retained-member ledger.
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val logical_position = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val group_member_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val group_valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val pending_storage_generation = UInt(p.sourceGenerationWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
  val pending_ordinal = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val source_last = Bool()
  val valid_count = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/** B2c's non-authoritative reconciliation state for one registered descriptor. */
object PendingPackingReconciliationState {
  final val Width = 2
  final val Unseen = 0
  final val PendingMember = 1
  final val TransitionedPacked = 2
}

/**
  * Read-only request from the pending descriptor owner to R3's bounded
  * accepted-admission journal.  The registration is echoed, never altered.
  */
final class PendingPackingReconciliationLookup(p: RouteASkeletonParameters) extends Bundle {
  val registration = new PendingSourceDescriptorRegistration(p)
}

/** Exact, read-only answer to a reconciliation lookup. */
final class PendingPackingReconciliationResult(p: RouteASkeletonParameters) extends Bundle {
  val registration = new PendingSourceDescriptorRegistration(p)
  val state = UInt(PendingPackingReconciliationState.Width.W)
}

/**
  * Non-backpressuring observation of an already accepted R3 admission member.
  * It is an observation only: it cannot delay, reject, or mutate the frozen
  * admission three-way join.
  */
final class AcceptedPendingPayloadBindingObservation(p: RouteASkeletonParameters) extends Bundle {
  val payload_binding = new PendingPayloadReadBinding(p)
}

/**
  * Read-only fanout of an already accepted R3-to-R6 pending-to-packed
  * transition. The binding is copied from R3's immutable accepted-member
  * journal so a direct descriptor can decide exact eligibility without using
  * `entry_id` as an ambiguous payload key. This is not a residency
  * transition, publication, or source-selection request.
  */
final class PendingToPackedReadEligibilityWithdrawal(p: RouteASkeletonParameters) extends Bundle {
  val payload_binding = new PendingPayloadReadBinding(p)
}

/** Read-only request pairing a selected pending SourceInstance with its key. */
final class PendingDirectAssociationQuery(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val key = new PendingDescriptorKey(p)
}

/**
  * Descriptor-owner validated association copied only after R6 accepts the
  * paired plan.  It carries facts; it is not a source-selection grant or a
  * second authority record.
  */
final class PendingDirectAssociationDeclaration(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val key = new PendingDescriptorKey(p)
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val pending_storage_generation = UInt(p.sourceGenerationWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
  val pending_ordinal = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val source_last = Bool()
  val valid_count = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/**
  * Control observation emitted only after the existing atomic metadata
  * publication acknowledgement.  It is not a second publication command.
  */
final class PublicationCommitObservation(p: RouteASkeletonParameters) extends Bundle {
  val p3_layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val p3_stage_generation = UInt(p.p3StageGenerationWidth.W)
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/** Per-record observation associated with one completed publication group. */
final class PublicationMemberObservation(p: RouteASkeletonParameters) extends Bundle {
  val entry_id = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val logical_position = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val group_member_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/**
  * Read-only R3 observation emitted only after a committed page's complete
  * immutable member ledger has seen its real R6 pending->packed acceptance
  * handshakes.  It is neither a second authority transition nor a new
  * publication command.
  */
final class PostR6PackedPageReadyObservation(p: RouteASkeletonParameters) extends Bundle {
  val p3_layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val p3_stage_generation = UInt(p.p3StageGenerationWidth.W)
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/**
  * Source-service evidence that the selected canonical source set has
  * completed all four GQA consumer updates and may enter R4. Bit positions are
  * the frozen hot/pending/packed order; there is deliberately no Full-KV bit.
  */
final class R6MergeReady extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_presence = UInt(RouteAAnchorWidths.SourcePresenceWidth.W)
}

/**
  * Immutable attention-local source expectation.  Presence bits use the
  * frozen canonical hot/pending/packed order; each descriptor is meaningful
  * only when its matching bit is set.  This is not a source scheduler.
  */
final class SourceCompletionPlan(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_presence = UInt(RouteAAnchorWidths.SourcePresenceWidth.W)
  val hot_instance = new SourceInstance(p)
  val pending_instance = new SourceInstance(p)
  val packed_instance = new SourceInstance(p)
}

/**
  * Immutable upstream declaration consumed by the C6 source-plan binder.
  * It declares an already-selected source set; it is neither a scheduler
  * command nor permission for the composition top to construct a plan.
  */
final class SourcePlanDeclaration(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_presence = UInt(RouteAAnchorWidths.SourcePresenceWidth.W)
  val hot_instance = new SourceInstance(p)
  val pending_instance = new SourceInstance(p)
  val packed_instance = new SourceInstance(p)
  // Meaningful only with pending presence. This key binds the already
  // selected pending source to descriptor-owner facts without extending R6's
  // frozen SourceCompletionPlan.
  val pending_descriptor_key = new PendingDescriptorKey(p)
}

final class S2ServiceRequest extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
}

final class DirectPendingOpen(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  // Exact R6-accepted pending SourceInstance; endpoint-local generation stays
  // distinct and is returned by DirectPendingOpenAck.
  val pending_instance = new SourceInstance(p)
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val ordered_pending_descriptor_ref = UInt(p.pendingDescriptorRefWidth.W)
  val expected_generation_or_validity = UInt(p.pendingValidityWidth.W)
}

/** Endpoint acknowledgement linking an accepted R6 instance to local transport generation. */
final class DirectPendingOpenAck(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val accepted_pending_instance = new SourceInstance(p)
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
}

/** Exact pre-issue endpoint cleanup request; it is not an R6 terminal. */
final class DirectPendingAbort(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
}

/** Endpoint acknowledgement for an exact pre-issue abort. */
final class DirectPendingAbortAck(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
}

/**
  * Owner-to-R6 notification after a cancelled candidate and aborted endpoint.
  * It is not a terminal; R6 alone turns this accepted failure into the outward
  * fault terminal for its live attention tracker.
  */
final class DirectPendingAssociationFailure(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val pending_instance = new SourceInstance(p)
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
  val reason = UInt(2.W)
}

/** Local S2 fill-control association; never a physical source-buffer port. */
final class S2FillOpen(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val expected_fragment_count = UInt(10.W)
  // Logical 8-B position-sidecar records. This is an endpoint contract, not
  // a physical S2 macro geometry or port selection.
  val expected_sidecar_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val requires_sidecar = Bool()
}

/** Local R2/R1 delivery observation for an S2 fill, without payload storage. */
final class S2FillTerminal(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val fragment_index = UInt(RouteAAnchorWidths.P3FragmentIndexWidth.W)
  val last = Bool()
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

final class S2SidecarComplete(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
}

/** One 64-B functional S2 payload-store write, distinct from terminal control. */
final class S2PayloadFragment(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val fragment_index = UInt(RouteAAnchorWidths.P3FragmentIndexWidth.W)
  val last = Bool()
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

/** One padded 8-B logical position-sidecar write into a functional S2 slot. */
final class S2SidecarFragment(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val record_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val data = UInt(64.W)
}

/** Owner-only functional payload read; source service is a later RTL2.4 client. */
final class S2PayloadReadRequest(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val fragment_index = UInt(RouteAAnchorWidths.P3FragmentIndexWidth.W)
}

final class S2PayloadReadResponse(p: RouteASkeletonParameters) extends Bundle {
  val request = new S2PayloadReadRequest(p)
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

/** Owner-only functional sidecar read; no physical layout claim. */
final class S2SidecarReadRequest(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val record_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

final class S2SidecarReadResponse(p: RouteASkeletonParameters) extends Bundle {
  val request = new S2SidecarReadRequest(p)
  val data = UInt(64.W)
}

/** Local direct-pending deliverability/close observation; K/V is not stored here. */
final class DirectPendingRecordTerminal(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
  val ordinal = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val last = Bool()
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
  val explicit_empty = Bool()
}

/**
  * One transient 64-B direct-pending fragment after exact typed endpoint
  * validation. It is not a pending payload buffer, source packet, R4 value
  * fragment, or physical transport claim.
  */
final class DirectPendingPayloadFragment(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
  val ordinal = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val fragment_index = UInt(p.coreMemoryFragmentIndexWidth.W)
  val record_last_fragment = Bool()
  val source_last = Bool()
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

/** Control-only activation for the hot owner; it carries no hot K/V payload. */
final class HotSourceOpen(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
}

/** Generation-bearing local refinement of the later R4 consumer-commit event. */
final class GqaConsumerCommit(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
}

/** Local release notification; it is not an R6 terminal outcome or credit return. */
final class SourceRelease(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
}

final class SourcePartial extends Bundle {
  val source_kind = UInt(RouteAAnchorWidths.SourceKindWidth.W)
  val merge_partial_header = UInt(RouteAAnchorWidths.MergePartialHeaderWidth.W)
  val merge_value_fragment = UInt(RouteAAnchorWidths.MergeValueFragmentWidth.W)
}

/** Read-only owner fact used by the protocol-only source packet adapter. */
final class SourceServiceAvailability(p: RouteASkeletonParameters) extends Bundle {
  val valid = Bool()
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
}

/**
  * Owner-provided structural R4 partial offer. Header/data semantics remain
  * outside this adapter; it only validates identity, source association, and
  * frozen packet structure.
  */
final class SourceServicePartialOffer(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val r4_header = UInt(RouteAAnchorWidths.MergePartialHeaderWidth.W)
  val partial_present = Bool()
}

/** One owner-provided fragment of an already-computed present source partial. */
final class SourceServiceValueFragment(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val fragment_index = UInt(3.W)
  val last = Bool()
  val data = UInt(RouteAAnchorWidths.MergeValueFragmentWidth.W)
}

/** Fixed semantic Route-A source codes; never a physical mux encoding. */
object RouteASourceKind {
  final val Hot = 0
  final val Pending = 1
  final val Packed = 2
}

/**
  * Source-owner identity that survives the R4 partial/commit round trip.
  * `instance_coordinate` uses the selected logical entry-coordinate width:
  * S2 encodes its slot there, direct encodes its one endpoint, and hot uses
  * its hot-owner coordinate.  It is not an address or payload reference.
  */
final class SourceInstance(p: RouteASkeletonParameters) extends Bundle {
  val source_kind = UInt(RouteAAnchorWidths.SourceKindWidth.W)
  val instance_coordinate = UInt(RouteAAnchorWidths.EntryIdWidth.W)
  val generation = UInt(p.sourceGenerationWidth.W)
}

/** Separate source-instance sideband for the frozen 128-bit R4 header. */
final class R4SourceInstanceSideband(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
}

final class ConsumerPartialCommit(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val source_kind = UInt(RouteAAnchorWidths.SourceKindWidth.W)
  val source_instance = new SourceInstance(p)
}

final class MergeRequest extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_presence = UInt(RouteAAnchorWidths.SourcePresenceWidth.W)
  // One group-level source-set completion yields one merge work item for each
  // legal GQA query-head consumer.  This is a logical association field, not
  // a PE lane, scheduler grant, or physical port selection.
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
}

final class MergeTerminalResponse extends Bundle {
  val transaction_identity = new TransactionIdentity
  // Must match the unique outstanding MergeRequest consumer association.
  // R6 aggregates these per-consumer outcomes into its sole group terminal.
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
  val normalized_value = UInt(RouteAAnchorWidths.NormalizedValueWidth.W)
}

/** R4 local packet header with the identity absent from the legacy opaque carrier. */
final class R4PartialHeader extends Bundle {
  val transaction_identity = new TransactionIdentity
  val header = UInt(RouteAAnchorWidths.MergePartialHeaderWidth.W)
}

/** One ordered logical 64-B R4 value fragment; never an HBM transaction. */
final class R4ValueFragment extends Bundle {
  val transaction_identity = new TransactionIdentity
  val fragment_index = UInt(3.W)
  val last = Bool()
  val data = UInt(RouteAAnchorWidths.MergeValueFragmentWidth.W)
}

/**
  * One structurally accepted R4 partial packet, reassembled solely for the
  * replaceable RTL3.4 functional-provider boundary.  This is a core-local
  * logical packet observation, never an HBM transaction, PE lane, or selected
  * storage realization.
  */
final class R4AcceptedPartialPacket(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new SourceInstance(p)
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val header = UInt(RouteAAnchorWidths.MergePartialHeaderWidth.W)
  val value_payload = UInt(RouteAAnchorWidths.NormalizedValueWidth.W)
}

/** Replaceable numeric-core success slot; R4 boundary forwards it without arithmetic. */
final class R4ResultStub extends Bundle {
  val transaction_identity = new TransactionIdentity
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val normalized_value = UInt(RouteAAnchorWidths.NormalizedValueWidth.W)
}

/** Explicit R4 fail-closed numeric-fault slot; R6 receives the existing fault status. */
final class R4NumericFault extends Bundle {
  val transaction_identity = new TransactionIdentity
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
}

/**
  * Existing RTL0.2 R2 candidate port, refined by RTL1.2.0. The nested request
  * is a core-side logical R1 carrier, not an HBM/controller command.
  */
final class SourceCandidate(p: RouteASkeletonParameters) extends Bundle {
  val candidate_class = UInt(p.candidateClassWidth.W)
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  // Opaque producer-owned context. R2 transports it but never resolves it.
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  // Producer-owned immutable descriptor copied into the registry before this
  // candidate can reach R2. R2 must not decode or reconstruct it.
  val delivery_target_descriptor = new DeliveryTargetDescriptor(p)
  val r1_request = new CoreMemoryRequest(p)
}

/**
  * This is a core-side logical carrier, never an HBM command/address encoding.
  * request_kind retains the unselected read/write and destination-tag encoding.
  */
final class CoreMemoryRequest(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val request_kind = UInt(p.coreMemoryRequestKindWidth.W)
  val destination = UInt(p.coreMemoryDestinationWidth.W)
  val address_ref = UInt(p.coreMemoryAddressRefWidth.W)
  val expected_fragment_count = UInt(p.coreMemoryFragmentCountWidth.W)
  // Used only by the R1 write-data variant. Read/write-request variants leave
  // these fields at their caller-defined inert values.
  val fragment_index = UInt(p.coreMemoryFragmentIndexWidth.W)
  val last = Bool()
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

/**
  * Immutable, producer-originated logical description of one future R1 read
  * issue.  This is deliberately not an R1 command, an HBM address format, or
  * a scheduler decision: a later named source owner materializes the existing
  * CoreMemoryRequest only after the R2-owned arbitration path accepts its
  * candidate.  `target_descriptor.requires_sidecar` plus the frozen PageRef
  * retain the sidecar obligation without selecting an address mapping or a
  * sidecar transport sequence.
  */
final class ReadIssueDescriptor(p: RouteASkeletonParameters) extends Bundle {
  // Existing R2 ownership key; it is not reconstructed from a response.
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  val candidate_class = UInt(p.candidateClassWidth.W)
  // Existing producer-owned R2 ordering/predicate facts.  The adapter below
  // copies them verbatim; it never selects a winner or derives eligibility.
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  val transaction_identity = new TransactionIdentity
  // Canonical Route-A source vocabulary (hot, pending, packed).  A future
  // core-read producer must reject hot because hot is not a core-memory read.
  val source_kind = UInt(RouteAAnchorWidths.SourceKindWidth.W)
  // Opaque core-side reference only, never an HBM/controller address claim.
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  // Frozen 0..64 page/pending semantic count; no endpoint-local default.
  val valid_count = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val expected_generation_or_validity = UInt(p.sourceGenerationWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
  val expected_fragment_count = UInt(p.coreMemoryFragmentCountWidth.W)
  // Retains P3/S2/direct endpoint-specific association and sidecar need.
  val target_descriptor = new DeliveryTargetDescriptor(p)
}

/**
  * One explicit R3-owned request to load the eight 64-B fragments of one
  * admitted pending member into its claimed P3 stage.  It fixes transaction
  * granularity and member association only.  It does not select how many
  * member reads may be outstanding, a physical address encoding, a memory
  * schedule, or a P3 storage realization.
  */
final class P3PackReadWork(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val member_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  // This must match the immutable R3 admission-member ledger.  It is carried
  // separately from the opaque handle so response data can never establish
  // or reconstruct a P3 member association.
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val transaction_identity = new TransactionIdentity
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
}

/** One R3-owned direct-pending 512-B record read, i.e. eight 64-B fragments. */
final class DirectPendingReadWork(p: RouteASkeletonParameters) extends Bundle {
  val association_id = new DirectPendingAssociationId(p)
  val transaction_identity = new TransactionIdentity
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val valid_count = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
  val pending_storage_generation = UInt(p.sourceGenerationWidth.W)
  val pending_ordinal = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val source_last = Bool()
}

/**
  * One packed-authoritative page read into an already-open logical S2 slot.
  * `valid_records` preserves a tail-page count; the semantic payload transfer
  * is exactly `valid_records * 8` 64-B fragments. It is neither a physical
  * HBM command nor an S2 macro/port selection.
  */
final class PackedS2ReadWork(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  // A nonzero value is an already acknowledged registry association supplied
  // by the RTL3.2 packed-read association owner.  The historical RTL2.3-C4
  // ingress leaves it at zero and is still bound by the common allocation
  // bridge; zero is therefore not a new validity encoding.
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
}

/**
  * Exact sidecar-read obligation copied from an accepted packed association.
  * This is not a physical sidecar layout or a new source-selection command.
  */
final class SidecarReadWork(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val sidecar_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
}

/**
  * Immutable, already-selected packed-source demand.  This is intentionally
  * not a scheduler request: the upstream boundary has selected the page and
  * R2 ordering facts before this carrier exists.
  */
final class PackedSourceDemand(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
}

/** R3/M2 current, identity-bound publication permission for one packed read. */
final class PublicationReadAuthorization(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val packed_authoritative = Bool()
}

/**
  * R5-owned opaque location facts.  The association owner transports these
  * facts only; it neither decodes a descriptor image nor derives addresses.
  */
final class DescriptorLocationGrant(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val sidecar_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val sidecar_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val live_reference_held = Bool()
}

/**
  * Identity-bound, read-only query for an already-published R5 descriptor.
  * The requester supplies no address or pointer and therefore cannot invent
  * the R5-owned payload/sidecar mapping.
  */
final class DescriptorLocationRequest(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/** S2-owned reservation facts for one future packed fill. */
final class S2FillLease(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val requires_sidecar = Bool()
}

/**
  * Request for S2 to validate and reserve the packed SourceInstance already
  * selected in the accepted R6 plan.  S2 remains the sole slot/generation
  * owner; the requester cannot infer a lease from PageRef.
  */
final class S2FillLeaseRequest(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val selected_instance = new SourceInstance(p)
}

/** Terminal release observation returned to the R5/S2 fact owners. */
final class PackedReadReleaseObservation(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

/** R5 invalidation notice that may cancel a packed association only pre-issue. */
final class PackedReadInvalidation extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
}

/** Typed packed-read endpoint terminal, before any S2 READY implication. */
final class PackedReadTerminal(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

final class CoreMemoryResponse(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val fragment_index = UInt(p.coreMemoryFragmentIndexWidth.W)
  val last = Bool()
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

/**
  * Reset-epoch acknowledgement emitted only by the external R1 adapter.
  *
  * This is deliberately distinct from an ordinary CoreMemoryResponse: the
  * latter is a live-transaction fragment/terminal carrier and can never be
  * reinterpreted as initialization. It selects neither native-controller
  * reset sequencing nor a CDC implementation.
  */
final class CoreMemoryInitAcknowledgement extends Bundle {
  val adapter_epoch_ready = Bool()
}

/** The only top-level Route-A-to-external-memory carrier; CDC/controller remain outside. */
final class CoreMemoryExternalPort(p: RouteASkeletonParameters) extends Bundle {
  val init_ack = Flipped(Decoupled(new CoreMemoryInitAcknowledgement))
  val request = Decoupled(new CoreMemoryRequest(p))
  val response = Flipped(Decoupled(new CoreMemoryResponse(p)))
}

/** Existing RTL0.2 routed-response port, refined by RTL1.2.0. */
final class SourceDelivery(p: RouteASkeletonParameters) extends Bundle {
  val candidate_id = UInt(p.candidateIdWidth.W)
  val candidate_class = UInt(p.candidateClassWidth.W)
  val destination = UInt(p.coreMemoryDestinationWidth.W)
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  val r1_response = new CoreMemoryResponse(p)
}

/** Registry-validated response plus its immutable stored target association. */
final class ResolvedDelivery(p: RouteASkeletonParameters) extends Bundle {
  val source_delivery = new SourceDelivery(p)
  val allocation = new DeliveryContextAllocation(p)
}

/**
  * RTL2.2.1 common association allocated before a future candidate is
  * presented to R2.  It deliberately carries only the common lookup key, not
  * an endpoint-specific payload/page/slot descriptor.  RTL2.2.2 owns that
  * typed resolution refinement.
  */
final class DeliveryContextAllocation(p: RouteASkeletonParameters) extends Bundle {
  val candidate_class = UInt(p.candidateClassWidth.W)
  val transaction_identity = new TransactionIdentity
  val target_kind = UInt(RouteADeliveryTargetKind.Width.W)
  val target_identity_generation = UInt(p.sourceGenerationWidth.W)
  // Immutable copy of the existing R1 request fact. A later read endpoint
  // requires it to validate ordinal/last coverage; this selects no port,
  // FIFO, endpoint implementation, or service-rate behavior.
  val expected_fragment_count = UInt(p.coreMemoryFragmentCountWidth.W)
  val target_descriptor = new DeliveryTargetDescriptor(p)
}

/** Exact immutable echo returned by the registry when association allocation succeeds. */
final class DeliveryContextAllocationAck(p: RouteASkeletonParameters) extends Bundle {
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  val allocation = new DeliveryContextAllocation(p)
}

/**
  * Target completion asks the registry to release an association only after
  * the future typed endpoint has accepted the terminal/last fragment.  A
  * mismatched or stale release is fail-closed and cannot free a live ref.
  */
final class DeliveryContextRelease(p: RouteASkeletonParameters) extends Bundle {
  val delivery_context_ref = UInt(p.sourceDeliveryOpaqueWidth.W)
  val allocation = new DeliveryContextAllocation(p)
}

final class MetadataPublishRequest(p: RouteASkeletonParameters) extends Bundle {
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val p3_layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val p3_stage_generation = UInt(p.p3StageGenerationWidth.W)
}

final class MetadataPublishVisibility(p: RouteASkeletonParameters) extends Bundle {
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
}

final class MetadataPublishVisibilityAck extends Bundle {
  val page_ref = new PageRef
  val status = UInt(RouteAAnchorWidths.PublicationStatusWidth.W)
}

final class MetadataPublishAck(p: RouteASkeletonParameters) extends Bundle {
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val status = UInt(RouteAAnchorWidths.PublicationStatusWidth.W)
}

/** RTL1.3.0 local P3 claim carrier; never an HBM command or P3 macro port. */
final class P3Claim(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val owner = UInt(RouteAAnchorWidths.RequestIdWidth.W)
  val page_ref = new PageRef
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  // R5 allocation fact; it freezes the two-bit descriptor prerequisite for
  // this append without letting R3 infer stream-tail state.
  val requires_tail_link = Bool()
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  // Immutable group-level M2 mapping carried through the one accepted R3
  // claim.  R3 records and later reflects it; R3 does not derive it from the
  // page reference, payload reference, layer, tag, or any physical address.
  val m2_group_opaque_address_ref = UInt(p.coreMemoryAddressRefWidth.W)
  val m2_group_owner = UInt(RouteAAnchorWidths.RequestIdWidth.W)
}

final class P3ClaimAck(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
}

/**
  * One 64-B fragment egressed by the hot/pending payload owner into R3's
  * replaceable functional P3 backing.  `payload_ref` is checked against the
  * immutable admitted member association; it is not an HBM address.  The
  * 512-bit `data` is functional/reference storage content only and does not
  * select a P3 macro, port count, or physical transport.
  */
final class P3PendingFragment(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val fragment_index = UInt(RouteAAnchorWidths.P3FragmentIndexWidth.W)
  val last = Bool()
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

/**
  * One logical position-sidecar binding from the hot/pending owner into R3's
  * functional P3 backing.  The selected 8-B sidecar representation is the
  * zero-extended logical position; it is not an HBM sidecar address/layout.
  */
final class P3SidecarBind(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val record_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val payload_ref = UInt(RouteAAnchorWidths.PayloadRefWidth.W)
  val logical_position = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
}

/** Associates an R1 packed-write terminal with a P3 stage/group, control only. */
final class P3PackedWriteTerminal(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
  val r1_payload_durable = Bool()
}

/** Records an accepted R2 pack-write launch before its later R1 terminal. */
final class P3PackedWriteIssue(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
}

/**
  * R3-only observation that one complete staged payload page is durable at
  * the unique R1 write boundary.  It carries no publication/authority effect.
  */
final class P3PayloadDurable(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val page_ref = new PageRef
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

/** A private result for one of the two fixed semantic M2 RMW members. */
final class M2GroupMemberRequest(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val member = UInt(1.W)
  val opaque_address_ref = UInt(p.coreMemoryAddressRefWidth.W)
  val owner = UInt(RouteAAnchorWidths.RequestIdWidth.W)
}

/** A private result for one of the two fixed semantic M2 RMW members. */
final class M2GroupMemberResponse(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val member = UInt(1.W)
  val opaque_address_ref = UInt(p.coreMemoryAddressRefWidth.W)
  val owner = UInt(RouteAAnchorWidths.RequestIdWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

/** R5-local allocation request; no physical descriptor/HBM command is implied. */
final class PageAllocationRequest(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
}

final class PageAllocationResponse(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val page_ref = new PageRef
  val requires_tail_link = Bool()
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
}

/** R5 observes only the terminal fact from the frozen R2/R1 maintenance path. */
final class DescriptorMaintenanceTerminal(p: RouteASkeletonParameters) extends Bundle {
  val kind = UInt(2.W)
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
  val r1_descriptor_durable = Bool()
}

/**
  * The sole R5-to-R3 aggregate append prerequisite.  The masks use the frozen
  * semantic bits (new_page, optional tail_link), never a descriptor layout or
  * physical maintenance-port encoding.
  */
final class DescriptorDurabilityPrerequisite(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val required_descriptor_operation_mask = UInt(2.W)
  val durable_descriptor_operation_mask = UInt(2.W)
  val descriptor_prepared = Bool()
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

object RouteAChannels {
  def frontend_lifecycle_req(p: RouteASkeletonParameters) = Decoupled(new FrontendLifecycleRequest(p))
  def runtime_retire_req = Decoupled(new RuntimeRetireRequest)
  def attention_terminal_rsp = Decoupled(new AttentionTerminalResponse)
  def session_retire_ack = Decoupled(new SessionRetireAck)
  def reclaim_permit = Decoupled(new ReclaimPermit)
  def component_status(p: RouteASkeletonParameters) = Decoupled(new ComponentStatus(p))
  def hot_control(p: RouteASkeletonParameters) = Decoupled(new HotControl(p))
  def hot_source_open(p: RouteASkeletonParameters) = Decoupled(new HotSourceOpen(p))
  def r6_authority_transition(p: RouteASkeletonParameters) = Decoupled(new R6AuthorityTransition(p))
  def admission_context(p: RouteASkeletonParameters) = Decoupled(new AdmissionContext(p))
  def pending_payload_read_binding(p: RouteASkeletonParameters) = Decoupled(new PendingPayloadReadBinding(p))
  def pending_source_descriptor_registration(p: RouteASkeletonParameters) = Decoupled(new PendingSourceDescriptorRegistration(p))
  def pending_packing_reconciliation_lookup(p: RouteASkeletonParameters) = Decoupled(new PendingPackingReconciliationLookup(p))
  def pending_packing_reconciliation_result(p: RouteASkeletonParameters) = Decoupled(new PendingPackingReconciliationResult(p))
  def pending_direct_association_query(p: RouteASkeletonParameters) = Decoupled(new PendingDirectAssociationQuery(p))
  def pending_direct_association_declaration(p: RouteASkeletonParameters) = Decoupled(new PendingDirectAssociationDeclaration(p))
  def publication_commit_observation(p: RouteASkeletonParameters) = Decoupled(new PublicationCommitObservation(p))
  def publication_member_observation(p: RouteASkeletonParameters) = Decoupled(new PublicationMemberObservation(p))
  def post_r6_packed_page_ready_observation(p: RouteASkeletonParameters) = Decoupled(new PostR6PackedPageReadyObservation(p))
  def r6_merge_ready = Decoupled(new R6MergeReady)
  def source_plan_declaration(p: RouteASkeletonParameters) = Decoupled(new SourcePlanDeclaration(p))
  def source_completion_plan(p: RouteASkeletonParameters) = Decoupled(new SourceCompletionPlan(p))
  def s2_service_req = Decoupled(new S2ServiceRequest)
  def direct_pending_open(p: RouteASkeletonParameters) = Decoupled(new DirectPendingOpen(p))
  def direct_pending_open_ack(p: RouteASkeletonParameters) = Decoupled(new DirectPendingOpenAck(p))
  def direct_pending_abort(p: RouteASkeletonParameters) = Decoupled(new DirectPendingAbort(p))
  def direct_pending_abort_ack(p: RouteASkeletonParameters) = Decoupled(new DirectPendingAbortAck(p))
  def s2_fill_open(p: RouteASkeletonParameters) = Decoupled(new S2FillOpen(p))
  def s2_fill_terminal(p: RouteASkeletonParameters) = Decoupled(new S2FillTerminal(p))
  def s2_sidecar_complete(p: RouteASkeletonParameters) = Decoupled(new S2SidecarComplete(p))
  def s2_payload_fragment(p: RouteASkeletonParameters) = Decoupled(new S2PayloadFragment(p))
  def s2_sidecar_fragment(p: RouteASkeletonParameters) = Decoupled(new S2SidecarFragment(p))
  def s2_payload_read_req(p: RouteASkeletonParameters) = Decoupled(new S2PayloadReadRequest(p))
  def s2_payload_read_rsp(p: RouteASkeletonParameters) = Decoupled(new S2PayloadReadResponse(p))
  def s2_sidecar_read_req(p: RouteASkeletonParameters) = Decoupled(new S2SidecarReadRequest(p))
  def s2_sidecar_read_rsp(p: RouteASkeletonParameters) = Decoupled(new S2SidecarReadResponse(p))
  def direct_pending_record_terminal(p: RouteASkeletonParameters) = Decoupled(new DirectPendingRecordTerminal(p))
  def gqa_consumer_commit(p: RouteASkeletonParameters) = Decoupled(new GqaConsumerCommit(p))
  def source_release(p: RouteASkeletonParameters) = Decoupled(new SourceRelease(p))
  def source_partial = Decoupled(new SourcePartial)
  def source_service_partial_offer(p: RouteASkeletonParameters) = Decoupled(new SourceServicePartialOffer(p))
  def source_service_value_fragment(p: RouteASkeletonParameters) = Decoupled(new SourceServiceValueFragment(p))
  def consumer_partial_commit(p: RouteASkeletonParameters) = Decoupled(new ConsumerPartialCommit(p))
  def r4_source_instance_sideband(p: RouteASkeletonParameters) = Decoupled(new R4SourceInstanceSideband(p))
  def merge_req = Decoupled(new MergeRequest)
  def merge_terminal_rsp = Decoupled(new MergeTerminalResponse)
  def r4_partial_header = Decoupled(new R4PartialHeader)
  def r4_value_fragment = Decoupled(new R4ValueFragment)
  def r4_accepted_partial_packet(p: RouteASkeletonParameters) = Decoupled(new R4AcceptedPartialPacket(p))
  def r4_result_stub = Decoupled(new R4ResultStub)
  def r4_numeric_fault = Decoupled(new R4NumericFault)
  def source_candidate(p: RouteASkeletonParameters) = Decoupled(new SourceCandidate(p))
  def read_issue_descriptor(p: RouteASkeletonParameters) = Decoupled(new ReadIssueDescriptor(p))
  def p3_pack_read_work(p: RouteASkeletonParameters) = Decoupled(new P3PackReadWork(p))
  def direct_pending_read_work(p: RouteASkeletonParameters) = Decoupled(new DirectPendingReadWork(p))
  def direct_pending_lease_eligibility_query(p: RouteASkeletonParameters) = Decoupled(new DirectPendingLeaseEligibilityQuery(p))
  def direct_pending_lease_eligibility(p: RouteASkeletonParameters) = Decoupled(new DirectPendingLeaseEligibility(p))
  def direct_pending_lease_commit(p: RouteASkeletonParameters) = Decoupled(new DirectPendingLeaseCommit(p))
  def direct_pending_association_withdrawal(p: RouteASkeletonParameters) = Decoupled(new DirectPendingAssociationWithdrawal(p))
  def direct_pending_candidate_cancel(p: RouteASkeletonParameters) = Decoupled(new DirectPendingCandidateCancel(p))
  def direct_pending_candidate_cancel_ack(p: RouteASkeletonParameters) = Decoupled(new DirectPendingCandidateCancelAck(p))
  def direct_pending_association_failure(p: RouteASkeletonParameters) = Decoupled(new DirectPendingAssociationFailure(p))
  def packed_s2_read_work(p: RouteASkeletonParameters) = Decoupled(new PackedS2ReadWork(p))
  def sidecar_read_work(p: RouteASkeletonParameters) = Decoupled(new SidecarReadWork(p))
  def packed_source_demand(p: RouteASkeletonParameters) = Decoupled(new PackedSourceDemand(p))
  def publication_read_authorization(p: RouteASkeletonParameters) = Decoupled(new PublicationReadAuthorization(p))
  def descriptor_location_grant(p: RouteASkeletonParameters) = Decoupled(new DescriptorLocationGrant(p))
  def descriptor_location_request(p: RouteASkeletonParameters) = Decoupled(new DescriptorLocationRequest(p))
  def s2_fill_lease(p: RouteASkeletonParameters) = Decoupled(new S2FillLease(p))
  def s2_fill_lease_request(p: RouteASkeletonParameters) = Decoupled(new S2FillLeaseRequest(p))
  def packed_read_release_observation(p: RouteASkeletonParameters) = Decoupled(new PackedReadReleaseObservation(p))
  def packed_read_terminal(p: RouteASkeletonParameters) = Decoupled(new PackedReadTerminal(p))
  def direct_pending_payload_fragment(p: RouteASkeletonParameters) = Decoupled(new DirectPendingPayloadFragment(p))
  def core_mem_req(p: RouteASkeletonParameters) = Decoupled(new CoreMemoryRequest(p))
  def core_mem_rsp(p: RouteASkeletonParameters) = Decoupled(new CoreMemoryResponse(p))
  def source_delivery(p: RouteASkeletonParameters) = Decoupled(new SourceDelivery(p))
  def resolved_delivery(p: RouteASkeletonParameters) = Decoupled(new ResolvedDelivery(p))
  def delivery_context_allocate(p: RouteASkeletonParameters) = Decoupled(new DeliveryContextAllocation(p))
  def delivery_context_allocation_ack(p: RouteASkeletonParameters) = Decoupled(new DeliveryContextAllocationAck(p))
  def delivery_context_release(p: RouteASkeletonParameters) = Decoupled(new DeliveryContextRelease(p))
  def metadata_publish_req(p: RouteASkeletonParameters) = Decoupled(new MetadataPublishRequest(p))
  def metadata_publish_visibility(p: RouteASkeletonParameters) = Decoupled(new MetadataPublishVisibility(p))
  def metadata_publish_visibility_ack = Decoupled(new MetadataPublishVisibilityAck)
  def metadata_publish_ack(p: RouteASkeletonParameters) = Decoupled(new MetadataPublishAck(p))
  def p3_claim(p: RouteASkeletonParameters) = Decoupled(new P3Claim(p))
  def p3_claim_ack(p: RouteASkeletonParameters) = Decoupled(new P3ClaimAck(p))
  def p3_pending_fragment(p: RouteASkeletonParameters) = Decoupled(new P3PendingFragment(p))
  def p3_sidecar_bind(p: RouteASkeletonParameters) = Decoupled(new P3SidecarBind(p))
  def p3_packed_write_terminal(p: RouteASkeletonParameters) = Decoupled(new P3PackedWriteTerminal(p))
  def p3_packed_write_issue(p: RouteASkeletonParameters) = Decoupled(new P3PackedWriteIssue(p))
  def p3_payload_durable(p: RouteASkeletonParameters) = Decoupled(new P3PayloadDurable(p))
  def m2_group_member_req(p: RouteASkeletonParameters) = Decoupled(new M2GroupMemberRequest(p))
  def m2_group_member_rsp(p: RouteASkeletonParameters) = Decoupled(new M2GroupMemberResponse(p))
  def page_allocation_req(p: RouteASkeletonParameters) = Decoupled(new PageAllocationRequest(p))
  def page_allocation_rsp(p: RouteASkeletonParameters) = Decoupled(new PageAllocationResponse(p))
  def allocator_release = Decoupled(new PageAllocatorRelease)
  def descriptor_maintenance_terminal(p: RouteASkeletonParameters) = Decoupled(new DescriptorMaintenanceTerminal(p))
  def descriptor_durability_prerequisite(p: RouteASkeletonParameters) = Decoupled(new DescriptorDurabilityPrerequisite(p))
}
