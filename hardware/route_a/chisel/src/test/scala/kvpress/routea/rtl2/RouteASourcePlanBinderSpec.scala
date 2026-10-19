package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteASourcePlanBinder
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL2.3-C6 directed contract checks; no attention or source scheduling. */
final class RouteASourcePlanBinderSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=8, coreMemoryFragmentCountWidth=3, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=1, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def driveInstance(instance: SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = {
    instance.source_kind.poke(kind.U); instance.instance_coordinate.poke(coordinate.U); instance.generation.poke(generation.U)
  }

  private def driveDeclaration(dut: RouteASourcePlanBinder, rid: Int, presence: Int, hotKind: Int = 0, pendingKind: Int = 1, packedKind: Int = 2): Unit = {
    val declaration = dut.io.declaration_in.bits
    declaration.transaction_identity.request_id.poke(rid.U); declaration.transaction_identity.incarnation.poke(1.U)
    declaration.source_presence.poke(presence.U)
    driveInstance(declaration.hot_instance, hotKind, 10, 1)
    driveInstance(declaration.pending_instance, pendingKind, 11, 2)
    driveInstance(declaration.packed_instance, packedKind, 12, 3)
    declaration.pending_descriptor_key.pending_descriptor_ref.poke(0.U)
    declaration.pending_descriptor_key.pending_descriptor_generation.poke(0.U)
  }

  private def driveAssociation(dut: RouteASourcePlanBinder, rid: Int): Unit = {
    val association = dut.io.association_declaration_in.bits
    association.transaction_identity.request_id.poke(rid.U); association.transaction_identity.incarnation.poke(1.U)
    driveInstance(association.pending_instance, RouteASourceKind.Pending, 11, 2)
    association.key.pending_descriptor_ref.poke(0.U); association.key.pending_descriptor_generation.poke(0.U)
    association.payload_handle_or_address.poke(3.U); association.pending_storage_generation.poke(2.U)
    association.destination_endpoint.poke(0.U); association.pending_ordinal.poke(0.U)
    association.source_last.poke(true.B); association.valid_count.poke(1.U)
  }

  private def acceptPendingAssociation(dut: RouteASourcePlanBinder, rid: Int, presence: Int): Unit = {
    if ((presence & (1 << RouteASourceKind.Pending)) != 0) {
      dut.io.association_query_out.valid.expect(true.B)
      dut.clock.step()
      driveAssociation(dut, rid)
      dut.io.association_declaration_in.valid.poke(true.B)
      dut.io.association_declaration_in.ready.expect(true.B)
      dut.clock.step()
      dut.io.association_declaration_in.valid.poke(false.B)
    }
  }

  private def init(dut: RouteASourcePlanBinder): Unit = {
    dut.io.declaration_in.valid.poke(false.B); dut.io.completion_plan_out.ready.poke(false.B)
    dut.io.association_query_out.ready.poke(true.B); dut.io.association_declaration_in.valid.poke(false.B)
    dut.io.accepted_pending_association_out.ready.poke(true.B)
    driveDeclaration(dut, 0, 1)
    driveAssociation(dut, 0)
  }

  private def expectPlan(dut: RouteASourcePlanBinder, rid: Int, presence: Int): Unit = {
    val plan = dut.io.completion_plan_out.bits
    dut.io.completion_plan_out.valid.expect(true.B)
    plan.transaction_identity.request_id.expect(rid.U); plan.transaction_identity.incarnation.expect(1.U)
    plan.source_presence.expect(presence.U)
    plan.hot_instance.source_kind.expect(0.U); plan.hot_instance.instance_coordinate.expect(10.U); plan.hot_instance.generation.expect(1.U)
    plan.pending_instance.source_kind.expect(1.U); plan.pending_instance.instance_coordinate.expect(11.U); plan.pending_instance.generation.expect(2.U)
    plan.packed_instance.source_kind.expect(2.U); plan.packed_instance.instance_coordinate.expect(12.U); plan.packed_instance.generation.expect(3.U)
  }

  it("binds all seven nonempty immutable source masks without choosing a source") {
    simulate(new RouteASourcePlanBinder(p)) { dut =>
      init(dut)
      for (presence <- 1 to 7) {
        driveDeclaration(dut, presence, presence)
        dut.io.declaration_in.valid.poke(true.B); dut.io.declaration_in.ready.expect(true.B)
        dut.clock.step(); dut.io.declaration_in.valid.poke(false.B)
        acceptPendingAssociation(dut, presence, presence)
        expectPlan(dut, presence, presence)
        dut.io.completion_plan_out.ready.poke(true.B); dut.clock.step(); dut.io.completion_plan_out.ready.poke(false.B)
        if ((presence & (1 << RouteASourceKind.Pending)) != 0) { dut.clock.step() }
        dut.io.completion_plan_out.valid.expect(false.B)
      }
    }
  }

  it("fails closed on an empty declaration or a noncanonical source-kind tuple") {
    simulate(new RouteASourcePlanBinder(p)) { dut =>
      init(dut)
      driveDeclaration(dut, 1, 0)
      dut.io.declaration_in.valid.poke(true.B); dut.io.declaration_in.ready.expect(false.B)
      dut.clock.step(); dut.io.declaration_in.valid.poke(false.B); dut.io.completion_plan_out.valid.expect(false.B)

      driveDeclaration(dut, 2, 1, hotKind = 1)
      dut.io.declaration_in.valid.poke(true.B); dut.io.declaration_in.ready.expect(false.B)
      dut.clock.step(); dut.io.declaration_in.valid.poke(false.B); dut.io.completion_plan_out.valid.expect(false.B)
    }
  }

  it("holds the exact accepted plan while R6 applies backpressure") {
    simulate(new RouteASourcePlanBinder(p)) { dut =>
      init(dut)
      driveDeclaration(dut, 6, 5)
      dut.io.declaration_in.valid.poke(true.B); dut.io.declaration_in.ready.expect(true.B)
      dut.clock.step(); dut.io.declaration_in.valid.poke(false.B)
      acceptPendingAssociation(dut, 6, 5)
      expectPlan(dut, 6, 5)
      driveDeclaration(dut, 7, 2)
      dut.io.declaration_in.ready.expect(false.B)
      dut.clock.step(); expectPlan(dut, 6, 5)
      dut.io.completion_plan_out.ready.poke(true.B); dut.clock.step(); dut.io.completion_plan_out.ready.poke(false.B)
      dut.io.completion_plan_out.valid.expect(false.B)
    }
  }
}
