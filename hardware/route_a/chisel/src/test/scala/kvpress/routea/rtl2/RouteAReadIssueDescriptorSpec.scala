package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAReadIssueCandidateAdapter
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** Interface-only elaboration harness; it introduces no production owner or state. */
final class RouteAReadIssueDescriptorHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val issue_in = Input(new ReadIssueDescriptor(p))
    val issue_out = Output(new ReadIssueDescriptor(p))
  })
  io.issue_out := io.issue_in
}

/** Isolated RTL2.3.1 harness: no R2/R1/top integration is activated here. */
final class RouteAReadIssueCandidateAdapterHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val issue = Flipped(RouteAChannels.read_issue_descriptor(p))
    val candidate = RouteAChannels.source_candidate(p)
  })
  val adapter = Module(new RouteAReadIssueCandidateAdapter(p))
  adapter.io.read_issue_in <> io.issue
  io.candidate <> adapter.io.candidate_out
}

final class RouteAReadIssueDescriptorSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 2, candidateIdWidth = 3, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  it("preserves every frozen read-issue fact without decoding an opaque handle") {
    simulate(new RouteAReadIssueDescriptorHarness(p)) { dut =>
      val in = dut.io.issue_in
      in.delivery_context_ref.poke(2.U); in.candidate_class.poke(p.r2S2PackedClassCode.U)
      in.arrival_ordinal.poke(2.U); in.candidate_id.poke(6.U); in.eligibility_snapshot.poke("h155".U)
      in.transaction_identity.request_id.poke(3.U); in.transaction_identity.incarnation.poke(1.U)
      in.source_kind.poke(RouteASourceKind.Packed.U); in.payload_handle_or_address.poke("hA5".U)
      in.valid_count.poke(64.U); in.expected_generation_or_validity.poke(2.U)
      in.destination_endpoint.poke(1.U); in.expected_fragment_count.poke(3.U)
      in.target_descriptor.write_endpoint.poke(RouteAWriteDeliveryEndpoint.P3PackedWrite.U)
      in.target_descriptor.p3_layer.poke(4.U); in.target_descriptor.p3_stage_generation.poke(1.U)
      in.target_descriptor.transaction_group_tag.poke(3.U); in.target_descriptor.descriptor_kind.poke(0.U)
      in.target_descriptor.descriptor_page_ref.page_id.poke(17.U); in.target_descriptor.descriptor_page_ref.generation.poke(5.U)
      in.target_descriptor.descriptor_line.poke(9.U); in.target_descriptor.s2_slot.poke(1.U)
      in.target_descriptor.source_generation.poke(2.U); in.target_descriptor.requires_sidecar.poke(true.B)
      in.target_descriptor.pending_ordinal.poke(11.U); in.target_descriptor.pending_explicit_empty.poke(false.B)
      dut.clock.step()
      val out = dut.io.issue_out
      out.delivery_context_ref.expect(2.U); out.candidate_class.expect(p.r2S2PackedClassCode.U)
      out.arrival_ordinal.expect(2.U); out.candidate_id.expect(6.U); out.eligibility_snapshot.expect("h155".U)
      out.transaction_identity.request_id.expect(3.U); out.transaction_identity.incarnation.expect(1.U)
      out.source_kind.expect(RouteASourceKind.Packed.U); out.payload_handle_or_address.expect("hA5".U)
      out.valid_count.expect(64.U); out.expected_generation_or_validity.expect(2.U)
      out.destination_endpoint.expect(1.U); out.expected_fragment_count.expect(3.U)
      out.target_descriptor.descriptor_page_ref.page_id.expect(17.U)
      out.target_descriptor.descriptor_page_ref.generation.expect(5.U)
      out.target_descriptor.requires_sidecar.expect(true.B)
    }
  }

  private def driveIssue(d: RouteAReadIssueCandidateAdapterHarness, cls: Int, source: Int, validCount: Int, fragments: Int, explicitEmpty: Boolean): Unit = {
    val i = d.io.issue.bits
    i.delivery_context_ref.poke(2.U); i.candidate_class.poke(cls.U)
    i.arrival_ordinal.poke(2.U); i.candidate_id.poke(6.U); i.eligibility_snapshot.poke("h155".U)
    i.transaction_identity.request_id.poke(3.U); i.transaction_identity.incarnation.poke(1.U)
    i.source_kind.poke(source.U); i.payload_handle_or_address.poke("hA5".U)
    i.valid_count.poke(validCount.U); i.expected_generation_or_validity.poke(2.U)
    i.destination_endpoint.poke(1.U); i.expected_fragment_count.poke(fragments.U)
    i.target_descriptor.write_endpoint.poke(RouteAWriteDeliveryEndpoint.P3PackedWrite.U)
    i.target_descriptor.p3_layer.poke(4.U); i.target_descriptor.p3_stage_generation.poke(1.U)
    i.target_descriptor.transaction_group_tag.poke(3.U); i.target_descriptor.descriptor_kind.poke(0.U)
    i.target_descriptor.descriptor_page_ref.page_id.poke(17.U); i.target_descriptor.descriptor_page_ref.generation.poke(5.U)
    i.target_descriptor.descriptor_line.poke(9.U); i.target_descriptor.s2_slot.poke(1.U)
    i.target_descriptor.source_generation.poke(2.U); i.target_descriptor.requires_sidecar.poke(true.B)
    i.target_descriptor.pending_ordinal.poke(11.U); i.target_descriptor.pending_explicit_empty.poke(explicitEmpty.B)
  }

  it("forms one stable R2 read candidate by copying every producer-owned issue fact") {
    simulate(new RouteAReadIssueCandidateAdapterHarness(p)) { dut =>
      dut.io.issue.valid.poke(false.B); dut.io.candidate.ready.poke(false.B)
      driveIssue(dut, p.r2PackReadClassCode, RouteASourceKind.Pending, 64, 3, explicitEmpty = false)
      dut.io.issue.valid.poke(true.B); dut.io.candidate.valid.expect(true.B)
      dut.io.candidate.bits.candidate_class.expect(p.r2PackReadClassCode.U)
      dut.io.candidate.bits.arrival_ordinal.expect(2.U); dut.io.candidate.bits.candidate_id.expect(6.U)
      dut.io.candidate.bits.eligibility_snapshot.expect("h155".U)
      dut.io.candidate.bits.delivery_context_ref.expect(2.U)
      dut.io.candidate.bits.r1_request.transaction_identity.request_id.expect(3.U)
      dut.io.candidate.bits.r1_request.transaction_identity.incarnation.expect(1.U)
      dut.io.candidate.bits.r1_request.request_kind.expect(p.coreMemoryReadRequestCode.U)
      dut.io.candidate.bits.r1_request.destination.expect(1.U); dut.io.candidate.bits.r1_request.address_ref.expect("hA5".U)
      dut.io.candidate.bits.r1_request.expected_fragment_count.expect(3.U)
      dut.io.candidate.bits.r1_request.fragment_index.expect(0.U); dut.io.candidate.bits.r1_request.last.expect(false.B)
      dut.io.candidate.bits.r1_request.data.expect(0.U)
      dut.clock.step(); dut.io.candidate.valid.expect(true.B)
      dut.io.candidate.ready.poke(true.B); dut.io.issue.ready.expect(true.B); dut.clock.step()
    }
  }

  it("fails closed before candidate creation for non-read, hot, empty, or explicit-empty issues") {
    simulate(new RouteAReadIssueCandidateAdapterHarness(p)) { dut =>
      dut.io.candidate.ready.poke(true.B); dut.io.issue.valid.poke(true.B)
      driveIssue(dut, p.r2PackWriteClassCode, RouteASourceKind.Pending, 1, 1, explicitEmpty = false)
      dut.io.issue.ready.expect(false.B); dut.io.candidate.valid.expect(false.B)
      driveIssue(dut, p.r2PackReadClassCode, RouteASourceKind.Hot, 1, 1, explicitEmpty = false)
      dut.io.issue.ready.expect(false.B); dut.io.candidate.valid.expect(false.B)
      driveIssue(dut, p.r2PackReadClassCode, RouteASourceKind.Pending, 0, 1, explicitEmpty = false)
      dut.io.issue.ready.expect(false.B); dut.io.candidate.valid.expect(false.B)
      driveIssue(dut, p.r2PackReadClassCode, RouteASourceKind.Pending, 65, 1, explicitEmpty = false)
      dut.io.issue.ready.expect(false.B); dut.io.candidate.valid.expect(false.B)
      driveIssue(dut, p.r2DirectPendingClassCode, RouteASourceKind.Pending, 1, 1, explicitEmpty = true)
      dut.io.issue.ready.expect(false.B); dut.io.candidate.valid.expect(false.B)
    }
  }
}
