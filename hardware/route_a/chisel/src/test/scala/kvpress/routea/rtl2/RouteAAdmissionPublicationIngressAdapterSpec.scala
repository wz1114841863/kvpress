package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAAdmissionPublicationIngressAdapter
import kvpress.routea.interfaces.RouteAAuthorityStateCode
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL2.1a directed retained-group checks.  These observe control associations
  * only: no payload fragments, R1 transaction, descriptor terminal, or M2
  * publication signal is present in this harness.
  */
final class RouteAAdmissionPublicationIngressAdapterSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(dut: RouteAAdmissionPublicationIngressAdapter): Unit = {
    dut.io.r6_admission_context_in.valid.poke(false.B)
    dut.io.r6_authority_in.valid.poke(false.B)
    dut.io.pending_payload_binding_in.valid.poke(false.B)
    dut.io.r5_allocation_req.ready.poke(false.B)
    dut.io.r5_allocation_rsp_in.valid.poke(false.B)
    dut.io.r3_p3_claim.ready.poke(false.B)
    dut.io.r3_p3_claim_ack_in.valid.poke(false.B)
    dut.io.r3_admission_context_out.ready.poke(false.B)
    dut.io.r3_admission_authority_out.ready.poke(false.B)
    dut.io.r3_pending_payload_binding_out.ready.poke(false.B)
    dut.io.r5_allocation_rsp_in.bits.layer.poke(0.U)
    dut.io.r5_allocation_rsp_in.bits.kv_head.poke(0.U)
    dut.io.r5_allocation_rsp_in.bits.page_ref.page_id.poke(0.U)
    dut.io.r5_allocation_rsp_in.bits.page_ref.generation.poke(0.U)
    dut.io.r5_allocation_rsp_in.bits.requires_tail_link.poke(false.B)
    dut.io.r5_allocation_rsp_in.bits.transaction_group_tag.poke(0.U)
    dut.io.r3_p3_claim_ack_in.bits.layer.poke(0.U)
    dut.io.r3_p3_claim_ack_in.bits.stage_generation.poke(0.U)
    dut.io.pending_payload_binding_in.bits.transaction_identity.request_id.poke(0.U)
    dut.io.pending_payload_binding_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.pending_payload_binding_in.bits.entry_id.poke(0.U)
    dut.io.pending_payload_binding_in.bits.layer.poke(0.U)
    dut.io.pending_payload_binding_in.bits.kv_head.poke(0.U)
    dut.io.pending_payload_binding_in.bits.logical_position.poke(0.U)
    dut.io.pending_payload_binding_in.bits.payload_ref.poke(0.U)
    dut.io.pending_payload_binding_in.bits.transaction_group_tag.poke(0.U)
    dut.io.pending_payload_binding_in.bits.group_member_ordinal.poke(0.U)
    dut.io.pending_payload_binding_in.bits.group_valid_records.poke(0.U)
    dut.io.pending_payload_binding_in.bits.payload_handle_or_address.poke(0.U)
    dut.io.pending_payload_binding_in.bits.source_generation.poke(0.U)
    dut.io.pending_payload_binding_in.bits.destination_endpoint.poke(0.U)
    dut.io.pending_payload_binding_in.bits.m2_group_opaque_address_ref.poke(0.U)
    dut.io.pending_payload_binding_in.bits.m2_group_owner.poke(0.U)
  }

  private def driveMember(
    dut: RouteAAdmissionPublicationIngressAdapter,
    ordinal: Int,
    records: Int,
    position: Int,
    tag: Int = 1,
    authorityTo: Int = RouteAAuthorityStateCode.Pending,
  ): Unit = {
    val entry = position * 288
    val context = dut.io.r6_admission_context_in.bits
    context.entry_id.poke(entry.U); context.layer.poke(0.U); context.kv_head.poke(0.U)
    context.logical_position.poke(position.U); context.payload_ref.poke((position + 10).U)
    context.transaction_group_tag.poke(tag.U); context.group_member_ordinal.poke(ordinal.U); context.group_valid_records.poke(records.U)
    val authority = dut.io.r6_authority_in.bits
    authority.entry_id.poke(entry.U); authority.from_authority.poke(RouteAAuthorityStateCode.Hot.U)
    authority.to_authority.poke(authorityTo.U); authority.transaction_group_tag.poke(tag.U)
    val binding = dut.io.pending_payload_binding_in.bits
    binding.transaction_identity.request_id.poke((ordinal + 1).U); binding.transaction_identity.incarnation.poke(0.U)
    binding.entry_id.poke(entry.U); binding.layer.poke(0.U); binding.kv_head.poke(0.U)
    binding.logical_position.poke(position.U); binding.payload_ref.poke((position + 10).U)
    binding.transaction_group_tag.poke(tag.U); binding.group_member_ordinal.poke(ordinal.U); binding.group_valid_records.poke(records.U)
    binding.payload_handle_or_address.poke((0x40 + ordinal).U); binding.source_generation.poke(1.U); binding.destination_endpoint.poke(0.U)
    binding.m2_group_opaque_address_ref.poke("h5a".U); binding.m2_group_owner.poke(6.U)
  }

  private def offerMember(dut: RouteAAdmissionPublicationIngressAdapter, ordinal: Int, records: Int, position: Int): Unit = {
    driveMember(dut, ordinal, records, position)
    dut.io.r6_admission_context_in.valid.poke(true.B); dut.io.r6_authority_in.valid.poke(true.B); dut.io.pending_payload_binding_in.valid.poke(true.B)
    dut.io.r6_admission_context_in.ready.expect(true.B); dut.io.r6_authority_in.ready.expect(true.B); dut.io.pending_payload_binding_in.ready.expect(true.B)
    dut.clock.step()
    dut.io.r6_admission_context_in.valid.poke(false.B); dut.io.r6_authority_in.valid.poke(false.B); dut.io.pending_payload_binding_in.valid.poke(false.B)
  }

  private def offerAllocation(dut: RouteAAdmissionPublicationIngressAdapter, pageId: Int, tag: Int = 1): Unit = {
    val allocation = dut.io.r5_allocation_rsp_in.bits
    allocation.layer.poke(0.U); allocation.kv_head.poke(0.U); allocation.page_ref.page_id.poke(pageId.U)
    allocation.page_ref.generation.poke(0.U); allocation.requires_tail_link.poke(false.B); allocation.transaction_group_tag.poke(tag.U)
    dut.io.r5_allocation_rsp_in.valid.poke(true.B); dut.io.r5_allocation_rsp_in.ready.expect(true.B)
    dut.clock.step(); dut.io.r5_allocation_rsp_in.valid.poke(false.B)
  }

  private def offerClaimAck(dut: RouteAAdmissionPublicationIngressAdapter, generation: Int): Unit = {
    dut.io.r3_p3_claim_ack_in.bits.layer.poke(0.U); dut.io.r3_p3_claim_ack_in.bits.stage_generation.poke(generation.U)
    dut.io.r3_p3_claim_ack_in.valid.poke(true.B); dut.io.r3_p3_claim_ack_in.ready.expect(true.B)
    dut.clock.step(); dut.io.r3_p3_claim_ack_in.valid.poke(false.B)
  }

  it("collects non-contiguous immutable members, then allocates, claims, and relays original pairs once") {
    simulate(new RouteAAdmissionPublicationIngressAdapter(p)) { dut =>
      init(dut)
      // Ordinal order is arbitrary; entry IDs are intentionally not a span.
      offerMember(dut, ordinal = 1, records = 2, position = 7)
      dut.io.r5_allocation_req.valid.expect(false.B)
      offerMember(dut, ordinal = 0, records = 2, position = 2)

      dut.io.r5_allocation_req.valid.expect(true.B)
      dut.io.r5_allocation_req.bits.layer.expect(0.U); dut.io.r5_allocation_req.bits.kv_head.expect(0.U)
      dut.io.r5_allocation_req.bits.valid_records.expect(2.U); dut.io.r5_allocation_req.bits.transaction_group_tag.expect(1.U)
      dut.clock.step()
      dut.io.r5_allocation_req.valid.expect(true.B)
      dut.io.r5_allocation_req.bits.valid_records.expect(2.U)
      dut.io.r5_allocation_req.ready.poke(true.B); dut.clock.step(); dut.io.r5_allocation_req.ready.poke(false.B)

      // A wrong allocation response cannot open the P3 claim.
      dut.io.r5_allocation_rsp_in.bits.transaction_group_tag.poke(2.U)
      dut.io.r5_allocation_rsp_in.valid.poke(true.B); dut.io.r5_allocation_rsp_in.ready.expect(false.B)
      dut.io.r5_allocation_rsp_in.valid.poke(false.B)
      offerAllocation(dut, pageId = 3)

      dut.io.r3_p3_claim.valid.expect(true.B)
      dut.io.r3_p3_claim.bits.owner.expect(0.U); dut.io.r3_p3_claim.bits.page_ref.page_id.expect(3.U)
      dut.io.r3_p3_claim.bits.valid_records.expect(2.U); dut.clock.step()
      dut.io.r3_p3_claim.bits.m2_group_opaque_address_ref.expect("h5a".U)
      dut.io.r3_p3_claim.bits.m2_group_owner.expect(6.U)
      dut.io.r3_p3_claim.valid.expect(true.B)
      dut.io.r3_p3_claim.ready.poke(true.B); dut.clock.step(); dut.io.r3_p3_claim.ready.poke(false.B)

      // An acknowledgement for a different R3 layer cannot trigger relay.
      dut.io.r3_p3_claim_ack_in.bits.layer.poke(1.U); dut.io.r3_p3_claim_ack_in.bits.stage_generation.poke(3.U)
      dut.io.r3_p3_claim_ack_in.valid.poke(true.B); dut.io.r3_p3_claim_ack_in.ready.expect(false.B)
      dut.io.r3_p3_claim_ack_in.valid.poke(false.B)
      offerClaimAck(dut, generation = 3)

      // Relay canonical ordinal order, not arrival order; both R3 facts must fire together.
      dut.io.r3_admission_context_out.valid.expect(true.B); dut.io.r3_admission_authority_out.valid.expect(true.B); dut.io.r3_pending_payload_binding_out.valid.expect(true.B)
      dut.io.r3_admission_context_out.bits.entry_id.expect((2 * 288).U)
      dut.io.r3_admission_context_out.bits.payload_ref.expect(12.U)
      dut.clock.step()
      dut.io.r3_admission_context_out.bits.entry_id.expect((2 * 288).U)
      dut.io.r3_admission_context_out.ready.poke(true.B); dut.io.r3_admission_authority_out.ready.poke(true.B); dut.io.r3_pending_payload_binding_out.ready.poke(true.B)
      dut.clock.step()
      dut.io.r3_admission_context_out.ready.poke(false.B); dut.io.r3_admission_authority_out.ready.poke(false.B); dut.io.r3_pending_payload_binding_out.ready.poke(false.B)
      dut.io.r3_admission_context_out.valid.expect(true.B)
      dut.io.r3_admission_context_out.bits.entry_id.expect((7 * 288).U)
      dut.io.r3_admission_authority_out.bits.from_authority.expect(RouteAAuthorityStateCode.Hot.U)
      dut.io.r3_admission_authority_out.bits.to_authority.expect(RouteAAuthorityStateCode.Pending.U)
      dut.io.r3_admission_context_out.ready.poke(true.B); dut.io.r3_admission_authority_out.ready.poke(true.B); dut.io.r3_pending_payload_binding_out.ready.poke(true.B)
      dut.clock.step()
      dut.io.r3_admission_context_out.ready.poke(false.B); dut.io.r3_admission_authority_out.ready.poke(false.B); dut.io.r3_pending_payload_binding_out.ready.poke(false.B)
      dut.io.r3_admission_context_out.valid.expect(false.B); dut.io.r3_admission_authority_out.valid.expect(false.B)
    }
  }

  it("fails closed for split/mismatched RETAIN inputs and destructive reset removes a partial group") {
    simulate(new RouteAAdmissionPublicationIngressAdapter(p)) { dut =>
      init(dut)
      driveMember(dut, ordinal = 0, records = 2, position = 0)
      dut.io.r6_admission_context_in.valid.poke(true.B); dut.io.r6_authority_in.valid.poke(false.B)
      dut.io.r6_admission_context_in.ready.expect(false.B)
      dut.io.r6_admission_context_in.valid.poke(false.B)

      // An opaque payload handle/generation may vary, but the immutable
      // admission coordinate cannot.  A mismatched binding must not consume
      // either half of the RETAIN pair.
      driveMember(dut, ordinal = 0, records = 2, position = 0)
      dut.io.pending_payload_binding_in.bits.payload_ref.poke(99.U)
      dut.io.r6_admission_context_in.valid.poke(true.B); dut.io.r6_authority_in.valid.poke(true.B); dut.io.pending_payload_binding_in.valid.poke(true.B)
      dut.io.r6_admission_context_in.ready.expect(false.B); dut.io.r6_authority_in.ready.expect(false.B); dut.io.pending_payload_binding_in.ready.expect(false.B)
      dut.io.r6_admission_context_in.valid.poke(false.B); dut.io.r6_authority_in.valid.poke(false.B); dut.io.pending_payload_binding_in.valid.poke(false.B)

      driveMember(dut, ordinal = 0, records = 2, position = 0, authorityTo = RouteAAuthorityStateCode.Packed)
      dut.io.r6_admission_context_in.valid.poke(true.B); dut.io.r6_authority_in.valid.poke(true.B)
      dut.io.r6_admission_context_in.ready.expect(false.B); dut.io.r6_authority_in.ready.expect(false.B)
      dut.io.r6_admission_context_in.valid.poke(false.B); dut.io.r6_authority_in.valid.poke(false.B)

      offerMember(dut, ordinal = 0, records = 2, position = 0)
      // The logical M2 mapping is a group-level immutable fact.  A second
      // retained member with a different mapping cannot be folded into the
      // accepted group, even though its ordinary admission coordinates match.
      driveMember(dut, ordinal = 1, records = 2, position = 1)
      dut.io.pending_payload_binding_in.bits.m2_group_opaque_address_ref.poke("h6b".U)
      dut.io.r6_admission_context_in.valid.poke(true.B); dut.io.r6_authority_in.valid.poke(true.B); dut.io.pending_payload_binding_in.valid.poke(true.B)
      dut.io.r6_admission_context_in.ready.expect(false.B); dut.io.r6_authority_in.ready.expect(false.B); dut.io.pending_payload_binding_in.ready.expect(false.B)
      dut.io.r6_admission_context_in.valid.poke(false.B); dut.io.r6_authority_in.valid.poke(false.B); dut.io.pending_payload_binding_in.valid.poke(false.B)
      // The first ordinal is now occupied; a duplicate cannot complete or
      // mutate the partially assembled association.
      driveMember(dut, ordinal = 0, records = 2, position = 0)
      dut.io.r6_admission_context_in.valid.poke(true.B); dut.io.r6_authority_in.valid.poke(true.B)
      dut.io.r6_admission_context_in.ready.expect(false.B); dut.io.r6_authority_in.ready.expect(false.B)
      dut.io.r6_admission_context_in.valid.poke(false.B); dut.io.r6_authority_in.valid.poke(false.B)
      dut.reset.poke(true.B); dut.clock.step(); dut.reset.poke(false.B); dut.clock.step()
      dut.io.r5_allocation_req.valid.expect(false.B)
      dut.io.r5_allocation_rsp_in.valid.poke(true.B); dut.io.r5_allocation_rsp_in.ready.expect(false.B)
      dut.io.r5_allocation_rsp_in.valid.poke(false.B)
      dut.io.r3_p3_claim_ack_in.valid.poke(true.B); dut.io.r3_p3_claim_ack_in.ready.expect(false.B)
      dut.io.r3_p3_claim_ack_in.valid.poke(false.B)
    }
  }
}
