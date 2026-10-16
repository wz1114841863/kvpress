package kvpress.routea.baseline

import chisel3._
import kvpress.routea.interfaces.TransactionIdentity
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * Baseline-local carriers for the Full-KV measurement path.
  *
  * These bundles deliberately do not enter Route-A's Hot/Pending/Packed source
  * vocabulary.  They name one Full-KV source service, not a fourth Route-A
  * source and not a physical memory or numeric interface.
  */
final class FullKVReadWork(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val arrival_ordinal = UInt(p.candidateOrdinalWidth.W)
  val candidate_id = UInt(p.candidateIdWidth.W)
  val eligibility_snapshot = UInt(p.candidatePredicateWidth.W)
  val payload_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val destination_endpoint = UInt(p.coreMemoryDestinationWidth.W)
  val expected_fragment_count = UInt(p.coreMemoryFragmentCountWidth.W)
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
}

final class FullKVFillOpen(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val expected_fragment_count = UInt(p.coreMemoryFragmentCountWidth.W)
}

final class FullKVPayloadFragment(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val fragment_index = UInt(p.coreMemoryFragmentIndexWidth.W)
  val data = UInt(RouteAAnchorWidths.CoreDataWidth.W)
}

final class FullKVFillTerminal(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val status = UInt(RouteAAnchorWidths.TerminalStatusWidth.W)
}

final class FullKVSourceInstance(p: RouteASkeletonParameters) extends Bundle {
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
}

final class FullKVSourceReady(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new FullKVSourceInstance(p)
}

final class FullKVGqaConsumerCommit(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new FullKVSourceInstance(p)
  val consumer_id = UInt(RouteAAnchorWidths.ConsumerIdWidth.W)
}

final class FullKVSourceRelease(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val source_instance = new FullKVSourceInstance(p)
}
