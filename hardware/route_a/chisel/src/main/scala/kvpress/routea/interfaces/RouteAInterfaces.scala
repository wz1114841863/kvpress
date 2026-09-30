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

final class TransactionIdentity extends Bundle {
  val request_id = UInt(RouteAAnchorWidths.RequestIdWidth.W)
  val incarnation = UInt(RouteAAnchorWidths.IncarnationWidth.W)
}

final class PageRef extends Bundle {
  val page_id = UInt(RouteAAnchorWidths.PageIdWidth.W)
  val generation = UInt(RouteAAnchorWidths.PageGenerationWidth.W)
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
  * Source-service evidence that the selected canonical source set has
  * completed all four GQA consumer updates and may enter R4. Bit positions are
  * the frozen hot/pending/packed order; there is deliberately no Full-KV bit.
  */
final class R6MergeReady extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_presence = UInt(RouteAAnchorWidths.SourcePresenceWidth.W)
}

final class S2ServiceRequest extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
}

final class DirectPendingOpen(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val kv_head = UInt(RouteAAnchorWidths.KvHeadWidth.W)
  val ordered_pending_descriptor_ref = UInt(p.pendingDescriptorRefWidth.W)
  val expected_generation_or_validity = UInt(p.pendingValidityWidth.W)
}

/** Local S2 fill-control association; never a physical source-buffer port. */
final class S2FillOpen(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val expected_fragment_count = UInt(10.W)
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

/** Local direct-pending deliverability/close observation; K/V is not stored here. */
final class DirectPendingRecordTerminal(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val endpoint_generation = UInt(p.sourceGenerationWidth.W)
  val ordinal = UInt(RouteAAnchorWidths.LogicalPositionWidth.W)
  val last = Bool()
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
  val explicit_empty = Bool()
}

/** Generation-bearing local refinement of the later R4 consumer-commit event. */
final class GqaConsumerCommit(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_is_direct = Bool()
  val source_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
}

/** Local release notification; it is not an R6 terminal outcome or credit return. */
final class SourceRelease(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_is_direct = Bool()
  val source_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
}

final class SourcePartial extends Bundle {
  val source_kind = UInt(RouteAAnchorWidths.SourceKindWidth.W)
  val merge_partial_header = UInt(RouteAAnchorWidths.MergePartialHeaderWidth.W)
  val merge_value_fragment = UInt(RouteAAnchorWidths.MergeValueFragmentWidth.W)
}

final class ConsumerPartialCommit extends Bundle {
  val transaction_identity = new TransactionIdentity
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
  val source_kind = UInt(RouteAAnchorWidths.SourceKindWidth.W)
}

final class MergeRequest extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_presence = UInt(RouteAAnchorWidths.SourcePresenceWidth.W)
}

final class MergeTerminalResponse extends Bundle {
  val transaction_identity = new TransactionIdentity
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

/** Replaceable numeric-core success slot; R4 boundary forwards it without arithmetic. */
final class R4ResultStub extends Bundle {
  val transaction_identity = new TransactionIdentity
  val normalized_value = UInt(RouteAAnchorWidths.NormalizedValueWidth.W)
}

/** Explicit R4 fail-closed numeric-fault slot; R6 receives the existing fault status. */
final class R4NumericFault extends Bundle {
  val transaction_identity = new TransactionIdentity
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
  val r1_response = new CoreMemoryResponse(p)
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
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
}

final class P3ClaimAck(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
}

/** Control-only observation of a delivered 64-B pending fragment. */
final class P3PendingFragment(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val fragment_index = UInt(RouteAAnchorWidths.P3FragmentIndexWidth.W)
  val last = Bool()
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

/** Position-sidecar completion carrier; position payload storage remains unselected. */
final class P3SidecarBind(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val record_ordinal = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
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

/** A private result for one of the two fixed semantic M2 RMW members. */
final class M2GroupMemberResponse(p: RouteASkeletonParameters) extends Bundle {
  val layer = UInt(RouteAAnchorWidths.LayerWidth.W)
  val stage_generation = UInt(p.p3StageGenerationWidth.W)
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val member = UInt(1.W)
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

object RouteAChannels {
  def frontend_lifecycle_req(p: RouteASkeletonParameters) = Decoupled(new FrontendLifecycleRequest(p))
  def runtime_retire_req = Decoupled(new RuntimeRetireRequest)
  def attention_terminal_rsp = Decoupled(new AttentionTerminalResponse)
  def session_retire_ack = Decoupled(new SessionRetireAck)
  def component_status(p: RouteASkeletonParameters) = Decoupled(new ComponentStatus(p))
  def hot_control(p: RouteASkeletonParameters) = Decoupled(new HotControl(p))
  def r6_authority_transition(p: RouteASkeletonParameters) = Decoupled(new R6AuthorityTransition(p))
  def admission_context(p: RouteASkeletonParameters) = Decoupled(new AdmissionContext(p))
  def publication_commit_observation(p: RouteASkeletonParameters) = Decoupled(new PublicationCommitObservation(p))
  def publication_member_observation(p: RouteASkeletonParameters) = Decoupled(new PublicationMemberObservation(p))
  def r6_merge_ready = Decoupled(new R6MergeReady)
  def s2_service_req = Decoupled(new S2ServiceRequest)
  def direct_pending_open(p: RouteASkeletonParameters) = Decoupled(new DirectPendingOpen(p))
  def s2_fill_open(p: RouteASkeletonParameters) = Decoupled(new S2FillOpen(p))
  def s2_fill_terminal(p: RouteASkeletonParameters) = Decoupled(new S2FillTerminal(p))
  def s2_sidecar_complete(p: RouteASkeletonParameters) = Decoupled(new S2SidecarComplete(p))
  def direct_pending_record_terminal(p: RouteASkeletonParameters) = Decoupled(new DirectPendingRecordTerminal(p))
  def gqa_consumer_commit(p: RouteASkeletonParameters) = Decoupled(new GqaConsumerCommit(p))
  def source_release(p: RouteASkeletonParameters) = Decoupled(new SourceRelease(p))
  def source_partial = Decoupled(new SourcePartial)
  def consumer_partial_commit = Decoupled(new ConsumerPartialCommit)
  def merge_req = Decoupled(new MergeRequest)
  def merge_terminal_rsp = Decoupled(new MergeTerminalResponse)
  def r4_partial_header = Decoupled(new R4PartialHeader)
  def r4_value_fragment = Decoupled(new R4ValueFragment)
  def r4_result_stub = Decoupled(new R4ResultStub)
  def r4_numeric_fault = Decoupled(new R4NumericFault)
  def source_candidate(p: RouteASkeletonParameters) = Decoupled(new SourceCandidate(p))
  def core_mem_req(p: RouteASkeletonParameters) = Decoupled(new CoreMemoryRequest(p))
  def core_mem_rsp(p: RouteASkeletonParameters) = Decoupled(new CoreMemoryResponse(p))
  def source_delivery(p: RouteASkeletonParameters) = Decoupled(new SourceDelivery(p))
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
  def m2_group_member_rsp(p: RouteASkeletonParameters) = Decoupled(new M2GroupMemberResponse(p))
  def page_allocation_req(p: RouteASkeletonParameters) = Decoupled(new PageAllocationRequest(p))
  def page_allocation_rsp(p: RouteASkeletonParameters) = Decoupled(new PageAllocationResponse(p))
  def descriptor_maintenance_terminal(p: RouteASkeletonParameters) = Decoupled(new DescriptorMaintenanceTerminal(p))
}
