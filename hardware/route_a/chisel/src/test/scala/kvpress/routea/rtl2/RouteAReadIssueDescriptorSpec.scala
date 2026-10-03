package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
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
      out.transaction_identity.request_id.expect(3.U); out.transaction_identity.incarnation.expect(1.U)
      out.source_kind.expect(RouteASourceKind.Packed.U); out.payload_handle_or_address.expect("hA5".U)
      out.valid_count.expect(64.U); out.expected_generation_or_validity.expect(2.U)
      out.destination_endpoint.expect(1.U); out.expected_fragment_count.expect(3.U)
      out.target_descriptor.descriptor_page_ref.page_id.expect(17.U)
      out.target_descriptor.descriptor_page_ref.generation.expect(5.U)
      out.target_descriptor.requires_sidecar.expect(true.B)
    }
  }
}
