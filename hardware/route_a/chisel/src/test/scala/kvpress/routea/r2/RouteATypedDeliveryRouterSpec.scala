package kvpress.routea.r2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.{RouteADeliveryContextRegistry, RouteATypedDeliveryRouter}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL2.2.2 direct resolver/router checks; no endpoint payload backing or timing model. */
final class RouteATypedDeliveryHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val allocate = Flipped(RouteAChannels.delivery_context_allocate(p))
    val allocation_ack = RouteAChannels.delivery_context_allocation_ack(p)
    val delivery = Flipped(RouteAChannels.source_delivery(p))
    val r3_delivery = RouteAChannels.source_delivery(p)
    val append_delivery = RouteAChannels.source_delivery(p)
    val reclaim_delivery = RouteAChannels.source_delivery(p)
  })
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  registry.io.mem_init_done := io.mem_init_done
  registry.io.allocation_in <> io.allocate
  io.allocation_ack <> registry.io.allocation_ack_out
  registry.io.resolve_in <> io.delivery
  router.io.resolved_in <> registry.io.resolved_out
  registry.io.release_in <> router.io.release_out
  io.r3_delivery <> router.io.r3_packed_write_out
  io.append_delivery <> router.io.r5_append_out
  io.reclaim_delivery <> router.io.r5_reclaim_out
  StructuralTieOff.sink(router.io.read_fragment_out)
}

final class RouteATypedDeliveryRouterSpec extends AnyFunSpec with ChiselSim {
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

  private def driveDescriptor(d: DeliveryTargetDescriptor, endpoint: Int, tag: Int = 0): Unit = {
    d.write_endpoint.poke(endpoint.U); d.p3_layer.poke(1.U); d.p3_stage_generation.poke(2.U)
    d.transaction_group_tag.poke(tag.U); d.descriptor_kind.poke(0.U)
    d.descriptor_page_ref.page_id.poke(3.U); d.descriptor_page_ref.generation.poke(1.U)
    d.descriptor_line.poke(0.U); d.s2_slot.poke(0.U); d.source_generation.poke(0.U)
    d.requires_sidecar.poke(false.B); d.pending_ordinal.poke(0.U); d.pending_explicit_empty.poke(false.B)
  }
  private def driveAllocation(dut: RouteATypedDeliveryHarness, cls: Int, rid: Int, inc: Int, kind: Int, endpoint: Int): Unit = {
    val a = dut.io.allocate.bits
    a.candidate_class.poke(cls.U); a.transaction_identity.request_id.poke(rid.U); a.transaction_identity.incarnation.poke(inc.U)
    a.target_kind.poke(kind.U); a.target_identity_generation.poke(0.U); driveDescriptor(a.target_descriptor, endpoint, 1)
  }
  private def driveDelivery(dut: RouteATypedDeliveryHarness, ref: Int, cls: Int, id: Int, rid: Int, inc: Int, last: Boolean = true): Unit = {
    val d = dut.io.delivery.bits
    d.candidate_id.poke(id.U); d.candidate_class.poke(cls.U); d.destination.poke(0.U); d.delivery_context_ref.poke(ref.U)
    d.r1_response.transaction_identity.request_id.poke(rid.U); d.r1_response.transaction_identity.incarnation.poke(inc.U)
    d.r1_response.fragment_index.poke(0.U); d.r1_response.last.poke(last.B); d.r1_response.status.poke(p.coreMemoryOkStatusCode.U); d.r1_response.data.poke(0x55.U)
  }
  private def init(dut: RouteATypedDeliveryHarness): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.allocate.valid.poke(false.B); dut.io.allocation_ack.ready.poke(false.B)
    dut.io.delivery.valid.poke(false.B); dut.io.r3_delivery.ready.poke(false.B); dut.io.append_delivery.ready.poke(false.B); dut.io.reclaim_delivery.ready.poke(false.B)
    driveAllocation(dut, p.r2PackWriteClassCode, 0, 0, RouteADeliveryTargetKind.PackedWriteTerminal, RouteAWriteDeliveryEndpoint.P3PackedWrite)
    driveDelivery(dut, 0, p.r2PackWriteClassCode, 0, 0, 0)
  }
  private def allocate(dut: RouteATypedDeliveryHarness, cls: Int, rid: Int, inc: Int, kind: Int, endpoint: Int): Int = {
    driveAllocation(dut, cls, rid, inc, kind, endpoint); dut.io.allocate.valid.poke(true.B); dut.io.allocate.ready.expect(true.B); dut.clock.step()
    dut.io.allocate.valid.poke(false.B); dut.io.allocation_ack.valid.expect(true.B)
    val ref = dut.io.allocation_ack.bits.delivery_context_ref.peek().litValue.toInt
    dut.io.allocation_ack.ready.poke(true.B); dut.clock.step(); dut.io.allocation_ack.ready.poke(false.B); ref
  }

  it("routes a registry-held packed-write descriptor exactly once and releases its ref only after endpoint acceptance") {
    simulate(new RouteATypedDeliveryHarness(p)) { dut =>
      init(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step()
      val ref = allocate(dut, p.r2PackWriteClassCode, 1, 0, RouteADeliveryTargetKind.PackedWriteTerminal, RouteAWriteDeliveryEndpoint.P3PackedWrite)
      driveDelivery(dut, ref, p.r2PackWriteClassCode, 7, 1, 0); dut.io.delivery.valid.poke(true.B); dut.io.delivery.ready.expect(true.B); dut.clock.step()
      dut.io.delivery.valid.poke(false.B); dut.io.r3_delivery.valid.expect(true.B); dut.io.r3_delivery.bits.candidate_id.expect(7.U)
      dut.io.r3_delivery.ready.poke(false.B); dut.clock.step(); dut.io.r3_delivery.valid.expect(true.B); dut.io.r3_delivery.bits.r1_response.data.expect(0x55.U)
      dut.io.r3_delivery.ready.poke(true.B); dut.clock.step(); dut.io.r3_delivery.ready.poke(false.B)
      dut.clock.step()
      val reused = allocate(dut, p.r2PackWriteClassCode, 1, 1, RouteADeliveryTargetKind.PackedWriteTerminal, RouteAWriteDeliveryEndpoint.P3PackedWrite)
      assert(reused == ref)
    }
  }

  it("fails closed on stale identity and routes descriptor terminals only to their stored append or reclaim owner") {
    simulate(new RouteATypedDeliveryHarness(p)) { dut =>
      init(dut); dut.io.mem_init_done.poke(true.B); dut.clock.step()
      val appendRef = allocate(dut, p.r2DescriptorMaintenanceClassCode, 2, 0,
        RouteADeliveryTargetKind.DescriptorMaintenanceTerminal, RouteAWriteDeliveryEndpoint.R5Append)
      driveDelivery(dut, appendRef, p.r2DescriptorMaintenanceClassCode, 2, 2, 1); dut.io.delivery.valid.poke(true.B); dut.io.delivery.ready.expect(false.B)
      dut.io.delivery.valid.poke(false.B)
      driveDelivery(dut, appendRef, p.r2DescriptorMaintenanceClassCode, 2, 2, 0); dut.io.delivery.valid.poke(true.B); dut.io.delivery.ready.expect(true.B); dut.clock.step()
      dut.io.delivery.valid.poke(false.B); dut.io.append_delivery.valid.expect(true.B); dut.io.reclaim_delivery.valid.expect(false.B)
      dut.io.append_delivery.ready.poke(true.B); dut.clock.step(); dut.io.append_delivery.ready.poke(false.B); dut.clock.step()

      val reclaimRef = allocate(dut, p.r2DescriptorMaintenanceClassCode, 3, 0,
        RouteADeliveryTargetKind.DescriptorMaintenanceTerminal, RouteAWriteDeliveryEndpoint.R5Reclaim)
      driveDelivery(dut, reclaimRef, p.r2DescriptorMaintenanceClassCode, 3, 3, 0); dut.io.delivery.valid.poke(true.B); dut.io.delivery.ready.expect(true.B); dut.clock.step()
      dut.io.delivery.valid.poke(false.B); dut.io.reclaim_delivery.valid.expect(true.B); dut.io.append_delivery.valid.expect(false.B)
    }
  }
}
