package kvpress.routea.r5

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.DecoupledIO
import chisel3.util.experimental.BoringUtils
import kvpress.routea.RouteAPersistentPageReadTestParameters
import kvpress.routea.incremental.RouteAPageManager
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters
import org.scalatest.funspec.AnyFunSpec

/**
  * Real R5 parent and real availability child. R3 facts and R1 descriptor
  * terminals are explicit unit environments; no state or child is replaced.
  * The unused rich candidate branches stay below this narrow DPI boundary.
  */
final class RouteAR5PersistentReadParentHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val allocation_in = Flipped(RouteAChannels.page_allocation_req(p))
    val allocation_out = RouteAChannels.page_allocation_rsp(p)
    val payload_durable_in = Flipped(RouteAChannels.p3_payload_durable(p))
    val descriptor_prerequisite_out = RouteAChannels.descriptor_durability_prerequisite(p)
    val visibility_in = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val visibility_ack_out = RouteAChannels.metadata_publish_visibility_ack
    val append_valid = Output(Bool())
    val append_ready = Input(Bool())
    val append_kind = Output(UInt(p.coreMemoryRequestKindWidth.W))
    val append_candidate_id = Output(UInt(p.candidateIdWidth.W))
    val append_identity = Output(new TransactionIdentity)
    val append_terminal_valid = Input(Bool())
    val append_terminal_ready = Output(Bool())
    val append_terminal_candidate_id = Input(UInt(p.candidateIdWidth.W))
    val append_terminal_identity = Input(new TransactionIdentity)
    val scan_outstanding = Output(Bool())
    val scan_allowed = Output(Bool())
    val availability_request_fire = Output(Bool())
    val v2_owns_response = Output(Bool())
  })
  val persistent = IO(new PersistentReadR5Port(p))
  val parent = Module(new RouteAPageManager(p, persistentReadEnabled = true))
  parent.io.mem_init_done := true.B
  parent.io.drain_collection_enable := false.B
  parent.io.page_allocation_req_in <> io.allocation_in
  io.allocation_out <> parent.io.page_allocation_rsp
  parent.io.p3_payload_durable_in <> io.payload_durable_in
  io.descriptor_prerequisite_out <> parent.io.descriptor_durability_prerequisite_out
  parent.io.metadata_publish_visibility_in <> io.visibility_in
  io.visibility_ack_out <> parent.io.metadata_publish_visibility_ack
  persistent <> parent.persistentRead.get

  private def inactive[T <: Data](channel: DecoupledIO[T]): Unit = {
    channel.valid := false.B
    channel.bits := 0.U.asTypeOf(channel.bits)
  }
  private def sink[T <: Data](channel: DecoupledIO[T]): Unit = channel.ready := true.B
  inactive(parent.io.reclaim_permit_in)
  inactive(parent.io.reclaim_delivery_in)
  inactive(parent.io.descriptor_maintenance_terminal_in)
  inactive(parent.io.descriptor_location_request_in)
  sink(parent.io.reclaim_candidate_out)
  sink(parent.io.allocator_release_out)
  sink(parent.io.descriptor_location_grant_out)
  sink(parent.io.component_status_out)

  io.append_valid := parent.io.append_candidate_out.valid
  parent.io.append_candidate_out.ready := io.append_ready
  io.append_kind := parent.io.append_candidate_out.bits.r1_request.request_kind
  io.append_candidate_id := parent.io.append_candidate_out.bits.candidate_id
  io.append_identity := parent.io.append_candidate_out.bits.r1_request.transaction_identity
  parent.io.append_delivery_in.valid := io.append_terminal_valid
  parent.io.append_delivery_in.bits := 0.U.asTypeOf(parent.io.append_delivery_in.bits)
  parent.io.append_delivery_in.bits.candidate_class := p.r2DescriptorMaintenanceClassCode.U
  parent.io.append_delivery_in.bits.candidate_id := io.append_terminal_candidate_id
  parent.io.append_delivery_in.bits.r1_response.transaction_identity := io.append_terminal_identity
  parent.io.append_delivery_in.bits.r1_response.status := p.coreMemoryOkStatusCode.U
  parent.io.append_delivery_in.bits.r1_response.last := true.B
  io.append_terminal_ready := parent.io.append_delivery_in.ready

  private def tap[T <: Data](value: T): T = BoringUtils.tapAndRead(value)
  io.scan_outstanding := tap(parent.scanOutstanding)
  io.scan_allowed := tap(parent.scanAllowed)
  io.availability_request_fire := tap(parent.availabilityStorage.io.availability_lookup_req.valid) &&
    tap(parent.availabilityStorage.io.availability_lookup_req.ready)
  io.v2_owns_response := tap(parent.persistentAvailabilityOutstanding)
}

/** Parent-level progress test for the r1 shared-request ownership failure. */
final class RouteAR5PersistentReadParentSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteAPersistentPageReadTestParameters.small

  it("keeps scanner ownership separate across mark two queries and allocation interleaving") {
    simulate(new RouteAR5PersistentReadParentHarness(p)) { d =>
      def bit(value: Bool): Boolean = value.peek().litToBoolean
      def number(value: UInt): BigInt = value.peek().litValue
      var scanRequests = 0
      var v2Requests = 0
      var allocations = 0
      var markAcks = 0
      var queryReplies = 0
      var overlapSeen = false
      def tick(): Unit = {
        if (bit(d.persistent.query_in.valid) && bit(d.persistent.query_in.ready) && bit(d.io.scan_outstanding)) {
          overlapSeen = true
        }
        if (bit(d.io.availability_request_fire)) {
          if (bit(d.io.scan_allowed)) scanRequests += 1 else v2Requests += 1
        }
        // A v2 request cannot create a scanner-owned outstanding response.
        // This assertion fails on the frozen r1 implementation before mark ACK.
        if (bit(d.io.v2_owns_response)) d.io.scan_outstanding.expect(false.B)
        d.clock.step()
      }
      def until(clue: String, bound: Int = 128)(condition: => Boolean): Unit = {
        var clocks = 0
        while (!condition && clocks < bound) { tick(); clocks += 1 }
        assert(condition, s"R5 parent bounded wait: $clue scanOutstanding=${bit(d.io.scan_outstanding)}")
      }
      def page(value: PageRef, id: Int = 0): Unit = {
        value.page_id.poke(id.U); value.generation.poke(0.U)
      }
      def identity(value: TransactionIdentity, id: Int): Unit = {
        value.request_id.poke(id.U); value.incarnation.poke(0.U)
      }
      def offerAllocation(head: Int, tag: Int): Unit = {
        d.io.allocation_in.bits.layer.poke(0.U)
        d.io.allocation_in.bits.kv_head.poke(head.U)
        d.io.allocation_in.bits.valid_records.poke(1.U)
        d.io.allocation_in.bits.transaction_group_tag.poke(tag.U)
        d.io.allocation_in.valid.poke(true.B)
      }
      def acceptAllocation(expectedPage: Int): Unit = {
        until("allocation request")(bit(d.io.allocation_in.ready))
        tick(); d.io.allocation_in.valid.poke(false.B)
        until("allocation response")(bit(d.io.allocation_out.valid))
        d.io.allocation_out.bits.page_ref.page_id.expect(expectedPage.U)
        d.io.allocation_out.bits.page_ref.generation.expect(0.U)
        d.io.allocation_out.bits.requires_tail_link.expect(false.B)
        allocations += 1
        d.io.allocation_out.ready.poke(true.B); tick(); d.io.allocation_out.ready.poke(false.B)
      }
      def offerQuery(id: Int): Unit = {
        identity(d.persistent.query_in.bits.transaction_identity, id)
        page(d.persistent.query_in.bits.page_ref)
        d.persistent.query_in.bits.layer.poke(0.U)
        d.persistent.query_in.bits.kv_head.poke(0.U)
        d.persistent.query_in.valid.poke(true.B)
      }
      def checkResult(id: Int): Unit = {
        val response = d.persistent.query_result_out.bits
        d.persistent.query_result_out.valid.expect(true.B)
        response.status.expect(PersistentReadStatus.OK.U)
        response.layer.expect(0.U); response.kv_head.expect(0.U)
        response.transaction_group_tag.expect(1.U)
        response.grant.transaction_identity.request_id.expect(id.U)
        response.grant.transaction_identity.incarnation.expect(0.U)
        response.grant.page_ref.page_id.expect(0.U); response.grant.page_ref.generation.expect(0.U)
        response.grant.valid_records.expect(1.U); response.grant.sidecar_records.expect(1.U)
        response.grant.payload_handle_or_address.expect(0.U)
        response.grant.sidecar_handle_or_address.expect(32768.U)
        response.grant.live_reference_held.expect(true.B)
        d.io.scan_outstanding.expect(false.B)
      }

      d.io.allocation_in.valid.poke(false.B); d.io.allocation_out.ready.poke(false.B)
      d.io.payload_durable_in.valid.poke(false.B); d.io.descriptor_prerequisite_out.ready.poke(false.B)
      d.io.visibility_in.valid.poke(false.B); d.io.visibility_ack_out.ready.poke(false.B)
      d.io.append_ready.poke(false.B); d.io.append_terminal_valid.poke(false.B)
      d.io.append_terminal_candidate_id.poke(0.U); identity(d.io.append_terminal_identity, 0)
      d.persistent.mark_ready_in.valid.poke(false.B); d.persistent.mark_ready_ack_out.ready.poke(false.B)
      d.persistent.query_in.valid.poke(false.B); d.persistent.query_result_out.ready.poke(false.B)
      tick()

      offerAllocation(head = 0, tag = 1); acceptAllocation(expectedPage = 0)
      val durable = d.io.payload_durable_in.bits
      durable.layer.poke(0.U); durable.kv_head.poke(0.U); page(durable.page_ref)
      durable.stage_generation.poke(1.U)
      durable.transaction_group_tag.poke(1.U); durable.status.poke(p.coreMemoryOkStatusCode.U)
      d.io.payload_durable_in.valid.poke(true.B)
      until("payload durable fact")(bit(d.io.payload_durable_in.ready))
      tick(); d.io.payload_durable_in.valid.poke(false.B)

      // Accept the actual descriptor request and data before returning its
      // exact R1 terminal. No direct maintenance shortcut or parent state poke.
      until("descriptor write request")(bit(d.io.append_valid))
      d.io.append_kind.expect(p.coreMemoryWriteRequestCode.U)
      val candidate = number(d.io.append_candidate_id)
      val requestId = number(d.io.append_identity.request_id)
      val incarnation = number(d.io.append_identity.incarnation)
      d.io.append_ready.poke(true.B); tick()
      d.io.append_valid.expect(true.B); d.io.append_kind.expect(p.coreMemoryWriteDataCode.U)
      d.io.append_candidate_id.expect(candidate.U); tick(); d.io.append_ready.poke(false.B)
      d.io.append_terminal_candidate_id.poke(candidate.U)
      d.io.append_terminal_identity.request_id.poke(requestId.U)
      d.io.append_terminal_identity.incarnation.poke(incarnation.U)
      d.io.append_terminal_valid.poke(true.B)
      until("descriptor durable terminal")(bit(d.io.append_terminal_ready))
      tick(); d.io.append_terminal_valid.poke(false.B)
      until("descriptor prerequisite")(bit(d.io.descriptor_prerequisite_out.valid))
      d.io.descriptor_prerequisite_out.bits.descriptor_prepared.expect(true.B)
      d.io.descriptor_prerequisite_out.bits.status.expect(p.coreMemoryOkStatusCode.U)
      d.io.descriptor_prerequisite_out.ready.poke(true.B); tick()
      d.io.descriptor_prerequisite_out.ready.poke(false.B)
      page(d.io.visibility_in.bits.page_ref); d.io.visibility_in.bits.transaction_group_tag.poke(1.U)
      d.io.visibility_in.valid.poke(true.B)
      until("publication visibility")(bit(d.io.visibility_in.ready))
      tick(); d.io.visibility_in.valid.poke(false.B)
      until("publication visibility ACK")(bit(d.io.visibility_ack_out.valid))
      d.io.visibility_ack_out.bits.status.expect(0.U)
      d.io.visibility_ack_out.ready.poke(true.B); tick(); d.io.visibility_ack_out.ready.poke(false.B)

      val receipt = d.persistent.mark_ready_in.bits
      receipt.p3_layer.poke(0.U); receipt.kv_head.poke(0.U); page(receipt.page_ref)
      receipt.p3_stage_generation.poke(1.U); receipt.transaction_group_tag.poke(1.U)
      receipt.valid_records.poke(1.U); d.persistent.mark_ready_in.valid.poke(true.B)
      until("mark receipt acceptance")(bit(d.persistent.mark_ready_in.ready))
      tick(); d.persistent.mark_ready_in.valid.poke(false.B)
      until("mark receipt acknowledgement")(bit(d.persistent.mark_ready_ack_out.valid))
      for (_ <- 0 until 3) {
        d.persistent.mark_ready_ack_out.bits.status.expect(PersistentReadStatus.OK.U)
        d.io.scan_outstanding.expect(false.B); tick()
      }
      d.persistent.mark_ready_ack_out.ready.poke(true.B); tick()
      d.persistent.mark_ready_ack_out.ready.poke(false.B); markAcks += 1

      offerQuery(3); until("first query accepted")(bit(d.persistent.query_in.ready))
      tick(); d.persistent.query_in.valid.poke(false.B)
      until("first query result")(bit(d.persistent.query_result_out.valid))
      // A later legal allocation must wait while the query result is held.
      offerAllocation(head = 1, tag = 2)
      for (_ <- 0 until 4) { checkResult(3); d.io.allocation_in.ready.expect(false.B); tick() }
      d.persistent.query_result_out.ready.poke(true.B); tick()
      d.persistent.query_result_out.ready.poke(false.B); queryReplies += 1
      acceptAllocation(expectedPage = 1)

      // The real scanner restarts after allocation. Present the second read
      // while its registered response is still owned by that scanner.
      until("real scanner response outstanding")(bit(d.io.scan_outstanding))
      offerQuery(4); until("second query accepted")(bit(d.persistent.query_in.ready))
      tick(); d.persistent.query_in.valid.poke(false.B)
      until("second query after scanner response")(bit(d.persistent.query_result_out.valid))
      checkResult(4)
      d.persistent.query_result_out.ready.poke(true.B); tick()
      d.persistent.query_result_out.ready.poke(false.B); queryReplies += 1
      assert(allocations == 2 && markAcks == 1 && queryReplies == 2)
      assert(scanRequests > 0 && v2Requests == 3 && overlapSeen)
      println("KVZAP_PERSISTENT_READ_R5_PARENT_PASS real_parent=1 allocations=2 marks=1 queries=2 scan_overlap=1 held_result_cycles=4 ghost_scan_outstanding=0 owner_facts_mocked=1")
    }
  }
}
