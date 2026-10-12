package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.{RouteAPackedReadTerminalBridge, RouteASourceCompletionPlanActivationFork}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * RTL3.8.1 composition checks for the production-shaped plan fanout and
  * packed terminal association.  These tests make no memory, numeric, timing,
  * or PPA claim.
  */
final class RouteAPackedActivationCompositionSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4,
    candidatePredicateWidth = 10, r2S2FullClassCode = 0, r2S2PackedClassCode = 1,
    r2DirectPendingClassCode = 2, r2PackReadClassCode = 3, r2PackWriteClassCode = 4,
    r2DescriptorMaintenanceClassCode = 5, r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8, coreMemoryFragmentCountWidth = 10,
    coreMemoryFragmentIndexWidth = 10, coreMemoryReadRequestCode = 0,
    coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 3,
    p3StageGenerationWidth = 2, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 3, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def drivePlan(plan: SourceCompletionPlan, packed: Boolean): Unit = {
    plan.transaction_identity.request_id.poke(3.U)
    plan.transaction_identity.incarnation.poke(1.U)
    plan.source_presence.poke((if (packed) 4 else 1).U)
    plan.hot_instance.source_kind.poke(RouteASourceKind.Hot.U)
    plan.hot_instance.instance_coordinate.poke(0.U)
    plan.hot_instance.generation.poke(0.U)
    plan.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
    plan.pending_instance.instance_coordinate.poke(0.U)
    plan.pending_instance.generation.poke(0.U)
    plan.packed_instance.source_kind.poke(RouteASourceKind.Packed.U)
    plan.packed_instance.instance_coordinate.poke(1.U)
    plan.packed_instance.generation.poke(2.U)
  }

  it("fans out an R6 plan exactly to the packet and packed-activation consumers under independent stall") {
    simulate(new RouteASourceCompletionPlanActivationFork(p)) { d =>
      d.io.accepted_plan_in.valid.poke(false.B)
      d.io.packet_plan_out.ready.poke(true.B)
      d.io.packed_activation_plan_out.ready.poke(false.B)
      drivePlan(d.io.accepted_plan_in.bits, packed = true)
      d.clock.step()

      d.io.accepted_plan_in.valid.poke(true.B)
      d.io.accepted_plan_in.ready.expect(true.B)
      d.clock.step()
      d.io.accepted_plan_in.valid.poke(false.B)

      d.io.packet_plan_out.valid.expect(true.B)
      d.io.packet_plan_out.bits.transaction_identity.request_id.expect(3.U)
      d.io.packed_activation_plan_out.valid.expect(true.B)
      d.io.packed_activation_plan_out.bits.packed_instance.instance_coordinate.expect(1.U)
      d.clock.step()
      d.io.packet_plan_out.valid.expect(false.B)
      d.io.packed_activation_plan_out.valid.expect(true.B)
      d.io.packed_activation_plan_out.bits.packed_instance.generation.expect(2.U)

      d.io.packed_activation_plan_out.ready.poke(true.B)
      d.clock.step()
      d.io.packed_activation_plan_out.valid.expect(false.B)

      drivePlan(d.io.accepted_plan_in.bits, packed = false)
      d.io.accepted_plan_in.valid.poke(true.B)
      d.io.accepted_plan_in.ready.expect(true.B)
      d.clock.step()
      d.io.accepted_plan_in.valid.poke(false.B)
      d.io.packet_plan_out.valid.expect(true.B)
      d.io.packed_activation_plan_out.valid.expect(false.B)
    }
  }

  private def driveWork(work: PackedS2ReadWork, rid: Int = 5): Unit = {
    work.transaction_identity.request_id.poke(rid.U)
    work.transaction_identity.incarnation.poke(1.U)
    work.page_ref.page_id.poke(7.U)
    work.page_ref.generation.poke(2.U)
    work.s2_slot.poke(1.U)
    work.source_generation.poke(3.U)
    work.valid_records.poke(2.U)
    work.arrival_ordinal.poke(1.U)
    work.candidate_id.poke(2.U)
    work.eligibility_snapshot.poke(0.U)
    work.payload_handle_or_address.poke(0x44.U)
    work.destination_endpoint.poke(0.U)
    work.delivery_context_ref.poke(2.U)
  }

  private def driveTerminal(t: S2FillTerminal, rid: Int, last: Boolean): Unit = {
    t.transaction_identity.request_id.poke(rid.U)
    t.transaction_identity.incarnation.poke(1.U)
    t.s2_slot.poke(1.U)
    t.source_generation.poke(3.U)
    t.fragment_index.poke(15.U)
    t.last.poke(last.B)
    t.status.poke(0.U)
  }

  it("forwards only matching endpoint terminals and materializes one final association terminal") {
    simulate(new RouteAPackedReadTerminalBridge(p)) { d =>
      d.io.work_in.valid.poke(false.B)
      d.io.work_out.ready.poke(true.B)
      d.io.endpoint_terminal_in.valid.poke(false.B)
      d.io.s2_terminal_out.ready.poke(true.B)
      d.io.association_terminal_out.ready.poke(false.B)
      driveWork(d.io.work_in.bits)
      d.clock.step()

      d.io.work_in.valid.poke(true.B)
      d.io.work_in.ready.expect(true.B)
      d.clock.step()
      d.io.work_in.valid.poke(false.B)

      driveTerminal(d.io.endpoint_terminal_in.bits, rid = 4, last = false)
      d.io.endpoint_terminal_in.valid.poke(true.B)
      d.io.endpoint_terminal_in.ready.expect(false.B)
      d.io.endpoint_terminal_in.valid.poke(false.B)

      driveTerminal(d.io.endpoint_terminal_in.bits, rid = 5, last = false)
      d.io.endpoint_terminal_in.valid.poke(true.B)
      d.io.endpoint_terminal_in.ready.expect(true.B)
      d.clock.step()
      d.io.endpoint_terminal_in.valid.poke(false.B)
      d.io.association_terminal_out.valid.expect(false.B)

      driveTerminal(d.io.endpoint_terminal_in.bits, rid = 5, last = true)
      d.io.endpoint_terminal_in.valid.poke(true.B)
      d.io.endpoint_terminal_in.ready.expect(true.B)
      d.clock.step()
      d.io.endpoint_terminal_in.valid.poke(false.B)
      d.io.association_terminal_out.valid.expect(true.B)
      d.io.association_terminal_out.bits.transaction_identity.request_id.expect(5.U)
      d.io.association_terminal_out.bits.page_ref.page_id.expect(7.U)
      d.io.association_terminal_out.bits.delivery_context_ref.expect(2.U)
      d.clock.step()
      d.io.association_terminal_out.bits.page_ref.generation.expect(2.U)
      d.io.association_terminal_out.ready.poke(true.B)
      d.clock.step()
      d.io.association_terminal_out.valid.expect(false.B)
    }
  }
}
