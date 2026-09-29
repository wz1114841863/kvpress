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

/** The only top-level Route-A-to-external-memory carrier; CDC/controller remain outside. */
final class CoreMemoryExternalPort(p: RouteASkeletonParameters) extends Bundle {
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

object RouteAChannels {
  def frontend_lifecycle_req(p: RouteASkeletonParameters) = Decoupled(new FrontendLifecycleRequest(p))
  def runtime_retire_req = Decoupled(new RuntimeRetireRequest)
  def attention_terminal_rsp = Decoupled(new AttentionTerminalResponse)
  def session_retire_ack = Decoupled(new SessionRetireAck)
  def component_status(p: RouteASkeletonParameters) = Decoupled(new ComponentStatus(p))
  def hot_control(p: RouteASkeletonParameters) = Decoupled(new HotControl(p))
  def s2_service_req = Decoupled(new S2ServiceRequest)
  def direct_pending_open(p: RouteASkeletonParameters) = Decoupled(new DirectPendingOpen(p))
  def source_partial = Decoupled(new SourcePartial)
  def consumer_partial_commit = Decoupled(new ConsumerPartialCommit)
  def merge_req = Decoupled(new MergeRequest)
  def merge_terminal_rsp = Decoupled(new MergeTerminalResponse)
  def source_candidate(p: RouteASkeletonParameters) = Decoupled(new SourceCandidate(p))
  def core_mem_req(p: RouteASkeletonParameters) = Decoupled(new CoreMemoryRequest(p))
  def core_mem_rsp(p: RouteASkeletonParameters) = Decoupled(new CoreMemoryResponse(p))
  def source_delivery(p: RouteASkeletonParameters) = Decoupled(new SourceDelivery(p))
  def metadata_publish_req(p: RouteASkeletonParameters) = Decoupled(new MetadataPublishRequest(p))
  def metadata_publish_visibility(p: RouteASkeletonParameters) = Decoupled(new MetadataPublishVisibility(p))
  def metadata_publish_visibility_ack = Decoupled(new MetadataPublishVisibilityAck)
  def metadata_publish_ack(p: RouteASkeletonParameters) = Decoupled(new MetadataPublishAck(p))
}
