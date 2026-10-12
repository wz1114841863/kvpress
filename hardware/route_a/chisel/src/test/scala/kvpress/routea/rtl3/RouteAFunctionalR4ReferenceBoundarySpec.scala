package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAFunctionalR4ReferenceBoundary
import kvpress.routea.interfaces.RouteASourceKind
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL3.8.4 protocol-only checks; no numeric arithmetic is evaluated here. */
final class RouteAFunctionalR4ReferenceBoundarySpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def header(kind: Int, consumer: Int): BigInt =
    (BigInt(kind) << 64) | (BigInt(consumer) << 66) | (BigInt(1) << 69) | (BigInt(8) << 70)

  private def init(d: RouteAFunctionalR4ReferenceBoundary): Unit = {
    d.io.accepted_packet_in.valid.poke(false.B)
    d.io.accepted_packet_in.bits.transaction_identity.request_id.poke(0.U)
    d.io.accepted_packet_in.bits.transaction_identity.incarnation.poke(0.U)
    d.io.accepted_packet_in.bits.source_instance.source_kind.poke(0.U)
    d.io.accepted_packet_in.bits.source_instance.instance_coordinate.poke(0.U)
    d.io.accepted_packet_in.bits.source_instance.generation.poke(0.U)
    d.io.accepted_packet_in.bits.consumer_id.poke(0.U)
    d.io.accepted_packet_in.bits.header.poke(0.U); d.io.accepted_packet_in.bits.value_payload.poke(0.U)
    d.io.accepted_packet_out.ready.poke(true.B)
    d.io.active_merge_observation_in.valid.poke(false.B)
    d.io.active_merge_observation_in.bits.transaction_identity.request_id.poke(0.U)
    d.io.active_merge_observation_in.bits.transaction_identity.incarnation.poke(0.U)
    d.io.active_merge_observation_in.bits.source_presence.poke(0.U)
    d.io.active_merge_observation_in.bits.consumer_id.poke(0.U)
    d.io.merge_work_out.ready.poke(false.B)
    d.io.functional_result_in.valid.poke(false.B)
    d.io.functional_result_in.bits.transaction_identity.request_id.poke(0.U)
    d.io.functional_result_in.bits.transaction_identity.incarnation.poke(0.U)
    d.io.functional_result_in.bits.consumer_id.poke(0.U)
    d.io.functional_result_in.bits.normalized_value.poke(0.U)
    d.io.functional_numeric_fault_in.valid.poke(false.B)
    d.io.functional_numeric_fault_in.bits.transaction_identity.request_id.poke(0.U)
    d.io.functional_numeric_fault_in.bits.transaction_identity.incarnation.poke(0.U)
    d.io.functional_numeric_fault_in.bits.consumer_id.poke(0.U)
    d.io.r4_result_stub_out.ready.poke(false.B)
    d.io.r4_numeric_fault_out.ready.poke(false.B)
  }

  private def sendPacket(d: RouteAFunctionalR4ReferenceBoundary, kind: Int, consumer: Int): Unit = {
    d.io.accepted_packet_in.bits.transaction_identity.request_id.poke(3.U)
    d.io.accepted_packet_in.bits.transaction_identity.incarnation.poke(1.U)
    d.io.accepted_packet_in.bits.source_instance.source_kind.poke(kind.U)
    d.io.accepted_packet_in.bits.source_instance.instance_coordinate.poke(1.U)
    d.io.accepted_packet_in.bits.source_instance.generation.poke(2.U)
    d.io.accepted_packet_in.bits.consumer_id.poke(consumer.U)
    d.io.accepted_packet_in.bits.header.poke(header(kind, consumer).U)
    d.io.accepted_packet_in.bits.value_payload.poke((BigInt(kind + 1) << 8).U)
    d.io.accepted_packet_in.valid.poke(true.B)
    d.io.accepted_packet_in.ready.expect(true.B)
    d.io.accepted_packet_out.valid.expect(true.B)
    d.io.accepted_packet_out.bits.source_instance.source_kind.expect(kind.U)
    d.clock.step()
    d.io.accepted_packet_in.valid.poke(false.B)
  }

  private def activate(d: RouteAFunctionalR4ReferenceBoundary, presence: Int, consumer: Int): Unit = {
    d.io.active_merge_observation_in.bits.transaction_identity.request_id.poke(3.U)
    d.io.active_merge_observation_in.bits.transaction_identity.incarnation.poke(1.U)
    d.io.active_merge_observation_in.bits.source_presence.poke(presence.U)
    d.io.active_merge_observation_in.bits.consumer_id.poke(consumer.U)
    d.io.active_merge_observation_in.valid.poke(true.B)
  }

  it("issues dynamic R4 work only after the exact selected packet set, then accepts one matching success") {
    simulate(new RouteAFunctionalR4ReferenceBoundary(p)) { d =>
      init(d)
      sendPacket(d, RouteASourceKind.Hot, consumer = 2)
      // A duplicate source packet is fail-closed and cannot mutate receipt state.
      d.io.accepted_packet_in.bits.transaction_identity.request_id.poke(3.U)
      d.io.accepted_packet_in.bits.transaction_identity.incarnation.poke(1.U)
      d.io.accepted_packet_in.bits.source_instance.source_kind.poke(RouteASourceKind.Hot.U)
      d.io.accepted_packet_in.bits.source_instance.instance_coordinate.poke(1.U)
      d.io.accepted_packet_in.bits.source_instance.generation.poke(2.U)
      d.io.accepted_packet_in.bits.consumer_id.poke(2.U)
      d.io.accepted_packet_in.bits.header.poke(header(RouteASourceKind.Hot, 2).U)
      d.io.accepted_packet_in.valid.poke(true.B)
      d.io.accepted_packet_in.ready.expect(false.B)
      d.io.accepted_packet_in.valid.poke(false.B)

      activate(d, presence = 0x3, consumer = 2)
      d.io.merge_work_out.valid.expect(false.B)
      sendPacket(d, RouteASourceKind.Pending, consumer = 2)
      // Receipt commits at the packet fire edge; the work record is then
      // captured on the following cycle from the exact committed mask.
      d.clock.step()
      d.io.merge_work_out.valid.expect(true.B)
      d.io.merge_work_out.bits.source_presence.expect(3.U)
      d.io.merge_work_out.bits.consumer_id.expect(2.U)
      d.clock.step(); d.io.merge_work_out.valid.expect(true.B)
      d.io.merge_work_out.ready.poke(true.B); d.clock.step(); d.io.merge_work_out.ready.poke(false.B)

      // A stale response cannot become an R4 terminal after work issue.
      d.io.functional_result_in.bits.transaction_identity.request_id.poke(2.U)
      d.io.functional_result_in.bits.transaction_identity.incarnation.poke(1.U)
      d.io.functional_result_in.bits.consumer_id.poke(2.U)
      d.io.functional_result_in.bits.normalized_value.poke("h55".U)
      d.io.functional_result_in.valid.poke(true.B)
      d.io.functional_result_in.ready.expect(false.B)
      d.io.r4_result_stub_out.valid.expect(false.B)
      d.io.functional_result_in.valid.poke(false.B)

      d.io.functional_result_in.bits.transaction_identity.request_id.poke(3.U)
      d.io.functional_result_in.valid.poke(true.B)
      d.io.r4_result_stub_out.valid.expect(true.B)
      d.io.r4_result_stub_out.bits.consumer_id.expect(2.U)
      d.clock.step(); d.io.r4_result_stub_out.valid.expect(true.B)
      d.io.r4_result_stub_out.ready.poke(true.B); d.io.functional_result_in.ready.expect(true.B)
      d.clock.step(); d.io.functional_result_in.valid.poke(false.B)
    }
  }

  it("maps only a matching issued work item to numeric fault and rejects simultaneous terminal kinds") {
    simulate(new RouteAFunctionalR4ReferenceBoundary(p)) { d =>
      init(d)
      sendPacket(d, RouteASourceKind.Packed, consumer = 1)
      activate(d, presence = 0x4, consumer = 1)
      d.clock.step(); d.io.merge_work_out.valid.expect(true.B)
      d.io.merge_work_out.ready.poke(true.B); d.clock.step(); d.io.merge_work_out.ready.poke(false.B)

      d.io.functional_result_in.bits.transaction_identity.request_id.poke(3.U)
      d.io.functional_result_in.bits.transaction_identity.incarnation.poke(1.U)
      d.io.functional_result_in.bits.consumer_id.poke(1.U)
      d.io.functional_result_in.bits.normalized_value.poke(1.U)
      d.io.functional_numeric_fault_in.bits.transaction_identity.request_id.poke(3.U)
      d.io.functional_numeric_fault_in.bits.transaction_identity.incarnation.poke(1.U)
      d.io.functional_numeric_fault_in.bits.consumer_id.poke(1.U)
      d.io.functional_result_in.valid.poke(true.B); d.io.functional_numeric_fault_in.valid.poke(true.B)
      d.io.r4_result_stub_out.valid.expect(false.B); d.io.r4_numeric_fault_out.valid.expect(false.B)
      d.io.functional_result_in.ready.expect(false.B); d.io.functional_numeric_fault_in.ready.expect(false.B)
      d.io.functional_result_in.valid.poke(false.B)

      d.io.r4_numeric_fault_out.valid.expect(true.B)
      d.clock.step(); d.io.r4_numeric_fault_out.valid.expect(true.B)
      d.io.r4_numeric_fault_out.ready.poke(true.B); d.io.functional_numeric_fault_in.ready.expect(true.B)
      d.clock.step(); d.io.functional_numeric_fault_in.valid.poke(false.B)
    }
  }
}
