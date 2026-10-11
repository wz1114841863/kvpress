package kvpress.routea.r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.RouteAPageManager
import kvpress.routea.params.{RouteADescriptorOperationKind, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL1-I4 / RTL2.5.4 directed reclaim control checks; no HBM or PPA model. */
final class RouteAReclaimSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8, coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1, p3StageGenerationWidth = 1, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(dut: RouteAPageManager): Unit = {
    dut.io.mem_init_done.poke(false.B); dut.io.drain_collection_enable.poke(false.B); dut.io.reclaim_permit_in.valid.poke(false.B)
    dut.io.reclaim_permit_in.bits.transaction_identity.request_id.poke(0.U); dut.io.reclaim_permit_in.bits.transaction_identity.incarnation.poke(0.U)
    dut.io.page_allocation_req_in.valid.poke(false.B); dut.io.page_allocation_rsp.ready.poke(true.B)
    dut.io.descriptor_location_request_in.valid.poke(false.B); dut.io.descriptor_location_grant_out.ready.poke(true.B)
    dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B); dut.io.metadata_publish_visibility_in.valid.poke(false.B)
    dut.io.metadata_publish_visibility_ack.ready.poke(true.B); dut.io.reclaim_candidate_out.ready.poke(false.B)
    dut.io.reclaim_delivery_in.valid.poke(false.B); dut.io.component_status_out.ready.poke(true.B)
    dut.io.allocator_release_out.ready.poke(false.B)
    dut.io.mem_init_done.poke(true.B); dut.clock.step(); dut.clock.step()
  }

  private def publishOne(dut: RouteAPageManager, head: Int = 0, tag: Int = 1, page: Int = 0): Unit = {
    val alloc = dut.io.page_allocation_req_in.bits
    alloc.layer.poke(0.U); alloc.kv_head.poke(head.U); alloc.valid_records.poke(1.U); alloc.transaction_group_tag.poke(tag.U)
    dut.io.page_allocation_req_in.valid.poke(true.B); dut.io.page_allocation_req_in.ready.expect(true.B)
    dut.clock.step(); dut.io.page_allocation_req_in.valid.poke(false.B)
    val terminal = dut.io.descriptor_maintenance_terminal_in.bits
    terminal.kind.poke(RouteADescriptorOperationKind.NewPage.U); terminal.page_ref.page_id.poke(page.U); terminal.page_ref.generation.poke(0.U)
    terminal.transaction_group_tag.poke(tag.U); terminal.status.poke(p.coreMemoryOkStatusCode.U); terminal.r1_descriptor_durable.poke(true.B)
    dut.io.descriptor_maintenance_terminal_in.valid.poke(true.B); dut.io.descriptor_maintenance_terminal_in.ready.expect(true.B)
    dut.clock.step(); dut.io.descriptor_maintenance_terminal_in.valid.poke(false.B)
    val visibility = dut.io.metadata_publish_visibility_in.bits
    visibility.page_ref.page_id.poke(page.U); visibility.page_ref.generation.poke(0.U); visibility.transaction_group_tag.poke(tag.U)
    dut.io.metadata_publish_visibility_in.valid.poke(true.B); dut.io.metadata_publish_visibility_in.ready.expect(true.B)
    dut.clock.step(); dut.io.metadata_publish_visibility_in.valid.poke(false.B); dut.clock.step()
  }

  private def issueLine(dut: RouteAPageManager, expectedImage: BigInt = BigInt(1) << 44): Unit = {
    dut.io.drain_collection_enable.poke(true.B); dut.io.reclaim_permit_in.valid.poke(true.B); dut.io.reclaim_permit_in.ready.expect(true.B); dut.clock.step()
    dut.io.reclaim_permit_in.valid.poke(false.B); dut.clock.step()
    dut.io.reclaim_candidate_out.valid.expect(true.B); dut.io.reclaim_candidate_out.bits.r1_request.request_kind.expect(p.coreMemoryWriteRequestCode.U)
    dut.io.reclaim_candidate_out.ready.poke(false.B); dut.clock.step()
    dut.io.reclaim_candidate_out.bits.r1_request.request_kind.expect(p.coreMemoryWriteRequestCode.U)
    dut.io.reclaim_candidate_out.ready.poke(true.B); dut.clock.step()
    dut.io.reclaim_candidate_out.valid.expect(true.B); dut.io.reclaim_candidate_out.bits.r1_request.request_kind.expect(p.coreMemoryWriteDataCode.U)
    // Allocated lanes receive next generation; all other fields/lanes are FREE/zero.
    dut.io.reclaim_candidate_out.bits.r1_request.data.expect(expectedImage.U)
    dut.clock.step()
  }

  private def terminalLine(dut: RouteAPageManager, fault: Boolean, sequence: Int = 0): Unit = {
    val rsp = dut.io.reclaim_delivery_in.bits
    rsp.candidate_id.poke(sequence.U); rsp.candidate_class.poke(p.r2DescriptorMaintenanceClassCode.U)
    rsp.destination.poke(0.U); rsp.delivery_context_ref.poke(0.U)
    rsp.r1_response.transaction_identity.request_id.poke(sequence.U); rsp.r1_response.transaction_identity.incarnation.poke(0.U)
    rsp.r1_response.fragment_index.poke(0.U); rsp.r1_response.last.poke(true.B)
    rsp.r1_response.status.poke((if (fault) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U); rsp.r1_response.data.poke(0.U)
    dut.io.reclaim_delivery_in.valid.poke(true.B); dut.io.reclaim_delivery_in.ready.expect(true.B)
    dut.clock.step(); dut.io.reclaim_delivery_in.valid.poke(false.B)
  }

  it("writes a complete 64-B invalidation line and frees only after its terminal") {
    simulate(new RouteAPageManager(p)) { dut =>
      init(dut); publishOne(dut); issueLine(dut)
      dut.io.reclaim_complete.expect(false.B)
      terminalLine(dut, fault = false)
      // The named observation carries the old reference only after the
      // matching durable terminal; it is not a new allocator command.
      dut.io.allocator_release_out.valid.expect(true.B)
      dut.io.allocator_release_out.bits.page_ref.page_id.expect(0.U)
      dut.io.allocator_release_out.bits.page_ref.generation.expect(0.U)
      dut.io.allocator_release_out.ready.poke(true.B); dut.clock.step()
      dut.io.allocator_release_out.valid.expect(false.B)
      dut.io.reclaim_complete.expect(true.B)
      dut.io.page_allocation_req_in.ready.expect(false.B)
    }
  }

  it("keeps page ownership on a faulted reclaim terminal") {
    simulate(new RouteAPageManager(p)) { dut =>
      init(dut); publishOne(dut); issueLine(dut); terminalLine(dut, fault = true)
      dut.io.reclaim_complete.expect(false.B)
      dut.io.component_status_out.valid.expect(false.B)
    }
  }

  it("updates every allocated lane of one 64-B descriptor line at one terminal") {
    simulate(new RouteAPageManager(p)) { dut =>
      init(dut)
      publishOne(dut, head = 0, tag = 1, page = 0)
      publishOne(dut, head = 1, tag = 0, page = 1)
      issueLine(dut, expectedImage = (BigInt(1) << 44) | (BigInt(1) << 172))
      terminalLine(dut, fault = false)
      dut.io.reclaim_complete.expect(true.B)
    }
  }

  it("rejects a stale reclaim terminal and leaves the allocated line live") {
    simulate(new RouteAPageManager(p)) { dut =>
      init(dut); publishOne(dut); issueLine(dut)
      val rsp = dut.io.reclaim_delivery_in.bits
      rsp.candidate_id.poke(1.U); rsp.candidate_class.poke(p.r2DescriptorMaintenanceClassCode.U)
      rsp.destination.poke(0.U); rsp.delivery_context_ref.poke(0.U)
      rsp.r1_response.transaction_identity.request_id.poke(0.U); rsp.r1_response.transaction_identity.incarnation.poke(0.U)
      rsp.r1_response.fragment_index.poke(0.U); rsp.r1_response.last.poke(true.B)
      rsp.r1_response.status.poke(p.coreMemoryOkStatusCode.U); rsp.r1_response.data.poke(0.U)
      dut.io.reclaim_delivery_in.valid.poke(true.B); dut.io.reclaim_delivery_in.ready.expect(false.B)
      dut.io.reclaim_delivery_in.valid.poke(false.B)
      dut.io.reclaim_complete.expect(false.B)
      terminalLine(dut, fault = false)
      dut.io.reclaim_complete.expect(true.B)
    }
  }

  it("does not let an old durable terminal free the next descriptor line or report R5 drained early") {
    simulate(new RouteAPageManager(p)) { dut =>
      init(dut)
      // Pages 0..3 share descriptor line 0; page 4 starts descriptor line 1.
      // Each stream is distinct, so this constructs five independent already-
      // visible allocations without adding a scheduler or source model.
      (0 until 5).foreach { page =>
        publishOne(dut, head = page, tag = page & 1, page = page)
      }
      val firstLineImage = Seq(44, 172, 300, 428).map(bit => BigInt(1) << bit).sum
      issueLine(dut, expectedImage = firstLineImage)
      dut.io.reclaim_complete.expect(false.B)
      dut.io.component_status_out.valid.expect(false.B)
      terminalLine(dut, fault = false, sequence = 0)
      // Line 1 remains allocated, so no R5 drain fact may yet be reported.
      dut.io.reclaim_complete.expect(false.B)
      dut.io.component_status_out.valid.expect(false.B)

      // The next line has a distinct immutable reclaim sequence.  Holding
      // candidate ready low exposes that identity without issuing a write.
      dut.io.reclaim_candidate_out.ready.poke(false.B)
      dut.clock.step()
      dut.io.reclaim_candidate_out.valid.expect(true.B)
      dut.io.reclaim_candidate_out.bits.candidate_id.expect(1.U)
      dut.io.reclaim_candidate_out.bits.r1_request.transaction_identity.request_id.expect(1.U)
      dut.io.reclaim_candidate_out.bits.r1_request.request_kind.expect(p.coreMemoryWriteRequestCode.U)
      dut.io.reclaim_candidate_out.ready.poke(true.B); dut.clock.step()
      dut.io.reclaim_candidate_out.valid.expect(true.B)
      dut.io.reclaim_candidate_out.bits.r1_request.request_kind.expect(p.coreMemoryWriteDataCode.U)
      dut.io.reclaim_candidate_out.bits.r1_request.data.expect((BigInt(1) << 44).U)
      dut.clock.step()

      // A delayed terminal from line 0 cannot match the live line-1
      // descriptor operation and therefore cannot free or advance it.
      val stale = dut.io.reclaim_delivery_in.bits
      stale.candidate_id.poke(0.U); stale.candidate_class.poke(p.r2DescriptorMaintenanceClassCode.U)
      stale.destination.poke(0.U); stale.delivery_context_ref.poke(0.U)
      stale.r1_response.transaction_identity.request_id.poke(0.U); stale.r1_response.transaction_identity.incarnation.poke(0.U)
      stale.r1_response.fragment_index.poke(0.U); stale.r1_response.last.poke(true.B)
      stale.r1_response.status.poke(p.coreMemoryOkStatusCode.U); stale.r1_response.data.poke(0.U)
      dut.io.reclaim_delivery_in.valid.poke(true.B); dut.io.reclaim_delivery_in.ready.expect(false.B)
      dut.io.reclaim_delivery_in.valid.poke(false.B)
      dut.io.reclaim_complete.expect(false.B)

      terminalLine(dut, fault = false, sequence = 1)
      dut.io.reclaim_complete.expect(true.B)
      dut.io.component_status_out.valid.expect(true.B)
      // Replaying an already-consumed terminal cannot perform a second free.
      dut.io.reclaim_delivery_in.valid.poke(true.B); dut.io.reclaim_delivery_in.ready.expect(false.B)
    }
  }
}
