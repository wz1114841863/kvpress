package kvpress.routea

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.incremental.{RouteALifecycleAdapter, RouteAPersistentPackedReadController}
import kvpress.routea.interfaces._
import org.scalatest.funspec.AnyFunSpec

/** Narrow real-R6 unit harness. Source-release and init service are explicit unit inputs. */
final class RouteAPersistentR6ContextHarness(p: kvpress.routea.params.RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val status = Flipped(RouteAChannels.component_status(p))
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val plan = Flipped(RouteAChannels.source_completion_plan(p))
    val release = Flipped(RouteAChannels.source_release(p))
    val context = Flipped(chisel3.util.Decoupled(new R6PreflightContextQueryV2))
    val result = chisel3.util.Decoupled(new R6PreflightContextResultV2)
    val merge = RouteAChannels.merge_req
  })
  val dut = Module(new RouteALifecycleAdapter(p, persistentReadEnabled = true))
  dut.io.component_status_in <> io.status
  dut.io.frontend_lifecycle_req <> io.frontend
  dut.io.source_completion_plan_in <> io.plan
  dut.io.packed_source_release_in <> io.release
  dut.persistentRead.get.context_query_in <> io.context
  io.result <> dut.persistentRead.get.context_result_out
  io.merge <> dut.io.merge_req
  private def quiet[T <: Data](x: chisel3.util.DecoupledIO[T]): Unit = {
    x.valid := false.B; x.bits := 0.U.asTypeOf(x.bits)
  }
  quiet(dut.io.runtime_retire_req)
  quiet(dut.io.authority_transition_in)
  quiet(dut.io.merge_ready_in)
  quiet(dut.io.pending_source_failure_in)
  quiet(dut.io.hot_source_release_in)
  quiet(dut.io.pending_source_release_in)
  quiet(dut.io.merge_terminal_in)
  quiet(dut.io.metadata_publish_ack_in)
  quiet(dut.persistentRead.get.preplan_reject_in)
  dut.persistentRead.get.owners_drained := true.B
  dut.io.r5_reclaim_complete_in := false.B
  dut.io.attention_terminal_rsp.ready := false.B
  dut.io.session_retire_ack.ready := false.B
  dut.io.reclaim_permit_out.ready := false.B
  dut.io.hot_control_out.ready := true.B
  dut.io.authority_transition_out.ready := true.B
  dut.io.admission_context_out.ready := true.B
  dut.io.source_completion_plan_copy_out.ready := true.B
  dut.io.s2_service_req.ready := false.B
  dut.io.direct_pending_open.ready := false.B
  dut.io.metadata_publish_req.ready := false.B
}

/** Controller unit checks; owner responses are explicit mocks, not DUT authority evidence. */
final class RouteAPersistentPackedReadControllerSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteAPersistentPageReadTestParameters.small

  private final class Driver(val d: RouteAPersistentPackedReadController) {
    var contextPending: Option[Int] = None
    var planAccepts = 0
    var descriptorQueries = 0
    var reservations = 0
    var cancellations = 0
    var faultsToR6 = 0
    var localRejections = 0
    var demands = 0
    def bit(x: Bool): Boolean = x.peek().litToBoolean
    def number(x: UInt): Int = x.peek().litValue.toInt
    def identity(x: TransactionIdentity, rid: Int): Unit = {
      x.request_id.poke(rid.U); x.incarnation.poke(0.U)
    }
    def page(x: PageRef): Unit = { x.page_id.poke(0.U); x.generation.poke(0.U) }
    def plan(x: SourceCompletionPlan, rid: Int): Unit = {
      identity(x.transaction_identity, rid); x.source_presence.poke(5.U)
      x.hot_instance.source_kind.poke(RouteASourceKind.Hot.U)
      x.hot_instance.instance_coordinate.poke(1.U); x.hot_instance.generation.poke(1.U)
      x.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
      x.pending_instance.instance_coordinate.poke(0.U); x.pending_instance.generation.poke(1.U)
      x.packed_instance.source_kind.poke(RouteASourceKind.Packed.U)
      x.packed_instance.instance_coordinate.poke(0.U); x.packed_instance.generation.poke(1.U)
    }
    def grant(x: DescriptorLocationGrant, rid: Int, live: Boolean = true): Unit = {
      identity(x.transaction_identity, rid); page(x.page_ref)
      x.payload_handle_or_address.poke(55.U); x.sidecar_handle_or_address.poke(77.U)
      x.valid_records.poke(1.U); x.sidecar_records.poke(1.U); x.live_reference_held.poke(live.B)
    }
    def init(): Unit = {
      d.io.plan_in.valid.poke(false.B); plan(d.io.plan_in.bits, 0)
      d.io.plan_out.ready.poke(false.B)
      d.io.accepted_plan_in.valid.poke(false.B); plan(d.io.accepted_plan_in.bits, 0)
      d.io.page_select_in.valid.poke(false.B); identity(d.io.page_select_in.bits.transaction_identity, 0)
      page(d.io.page_select_in.bits.page_ref)
      d.io.context_query_out.ready.poke(true.B)
      d.io.context_result_in.valid.poke(false.B)
      identity(d.io.context_result_in.bits.transaction_identity, 0)
      d.io.context_result_in.bits.layer.poke(0.U); d.io.context_result_in.bits.kv_head.poke(0.U)
      d.io.context_result_in.bits.eligible.poke(false.B)
      d.io.r6_reject_out.ready.poke(false.B); d.io.binder_cancel_out.ready.poke(false.B)
      d.io.query_out.ready.poke(true.B); d.io.query_result_in.valid.poke(false.B)
      grant(d.io.query_result_in.bits.grant, 0)
      d.io.query_result_in.bits.layer.poke(0.U); d.io.query_result_in.bits.kv_head.poke(0.U)
      d.io.query_result_in.bits.transaction_group_tag.poke(1.U)
      d.io.query_result_in.bits.status.poke(PersistentReadStatus.OK.U)
      d.io.reservation_request_out.ready.poke(true.B)
      d.io.reservation_result_in.valid.poke(false.B)
      val lease = d.io.reservation_result_in.bits.lease
      identity(lease.transaction_identity, 0); page(lease.page_ref)
      lease.s2_slot.poke(0.U); lease.source_generation.poke(1.U); lease.requires_sidecar.poke(true.B)
      d.io.reservation_result_in.bits.status.poke(S2ReservationStatusV2.Granted.U)
      d.io.readiness_pending_in.valid.poke(false.B)
      val receipt = d.io.readiness_pending_in.bits
      receipt.p3_layer.poke(0.U); receipt.p3_stage_generation.poke(0.U); page(receipt.page_ref)
      receipt.transaction_group_tag.poke(1.U); receipt.valid_records.poke(1.U); receipt.kv_head.poke(0.U)
      d.io.attention_terminal_in.valid.poke(false.B); identity(d.io.attention_terminal_in.bits, 0)
      d.io.demand_out.ready.poke(false.B); d.io.publication_authorization_out.ready.poke(false.B)
      d.io.descriptor_grant_out.ready.poke(false.B); d.io.s2_fill_lease_out.ready.poke(false.B)
      d.io.rejected_out.ready.poke(false.B)
      tick()
    }
    def tick(): Unit = {
      d.io.context_result_in.valid.poke(contextPending.nonEmpty.B)
      contextPending.foreach { rid =>
        identity(d.io.context_result_in.bits.transaction_identity, rid)
        d.io.context_result_in.bits.eligible.poke((rid != 7).B)
      }
      var next = contextPending
      if (bit(d.io.context_result_in.valid) && bit(d.io.context_result_in.ready)) next = None
      if (bit(d.io.context_query_out.valid) && bit(d.io.context_query_out.ready)) {
        assert(contextPending.isEmpty, "one registered R6 context reply is outstanding")
        next = Some(number(d.io.context_query_out.bits.transaction_identity.request_id))
      }
      if (bit(d.io.plan_out.valid) && bit(d.io.plan_out.ready)) planAccepts += 1
      if (bit(d.io.query_out.valid) && bit(d.io.query_out.ready)) descriptorQueries += 1
      if (bit(d.io.reservation_request_out.valid) && bit(d.io.reservation_request_out.ready)) reservations += 1
      val cancel = bit(d.io.binder_cancel_out.valid) && bit(d.io.binder_cancel_out.ready)
      if (cancel) cancellations += 1
      if (bit(d.io.r6_reject_out.valid) && bit(d.io.r6_reject_out.ready)) faultsToR6 += 1
      if (bit(d.io.rejected_out.valid) && bit(d.io.rejected_out.ready)) localRejections += 1
      if (bit(d.io.demand_out.valid) && bit(d.io.demand_out.ready)) demands += 1
      d.clock.step()
      contextPending = next
      if (cancel) d.io.plan_in.valid.poke(false.B) // Model the binder's exact cancel ACK.
    }
    def until(clue: String)(condition: => Boolean): Unit = {
      var cycles = 0
      while (!condition && cycles < 80) { tick(); cycles += 1 }
      assert(condition, s"bounded controller wait: $clue")
    }
    def select(rid: Int): Unit = {
      identity(d.io.page_select_in.bits.transaction_identity, rid)
      page(d.io.page_select_in.bits.page_ref); d.io.page_select_in.valid.poke(true.B)
      until("selector ready")(bit(d.io.page_select_in.ready)); tick()
      d.io.page_select_in.valid.poke(false.B)
    }
    def declare(rid: Int): Unit = { plan(d.io.plan_in.bits, rid); d.io.plan_in.valid.poke(true.B) }
    def location(rid: Int, status: Int = PersistentReadStatus.OK): Unit = {
      until("R5 query")(bit(d.io.query_out.valid))
      d.io.query_out.bits.transaction_identity.request_id.expect(rid.U)
      d.io.query_out.bits.layer.expect(0.U); d.io.query_out.bits.kv_head.expect(0.U)
      tick()
      grant(d.io.query_result_in.bits.grant, rid, status == PersistentReadStatus.OK)
      d.io.query_result_in.bits.status.poke(status.U)
      d.io.query_result_in.valid.poke(true.B)
      until("R5 response accepted")(bit(d.io.query_result_in.ready)); tick()
      d.io.query_result_in.valid.poke(false.B)
    }
    def reserve(rid: Int): Unit = {
      until("S2 reservation")(bit(d.io.reservation_request_out.valid))
      d.io.reservation_request_out.bits.transaction_identity.request_id.expect(rid.U)
      tick()
      identity(d.io.reservation_result_in.bits.lease.transaction_identity, rid)
      d.io.reservation_result_in.valid.poke(true.B)
      until("S2 granted accepted")(bit(d.io.reservation_result_in.ready)); tick()
      d.io.reservation_result_in.valid.poke(false.B)
    }
  }

  it("holds one owner-granted reservation through joint-accept and accepted-copy backpressure") {
    simulate(new RouteAPersistentPackedReadController(p)) { d =>
      val driver = new Driver(d); driver.init()
      driver.select(1); driver.declare(1); driver.location(1); driver.reserve(1)
      for (_ <- 0 until 8) {
        d.io.plan_out.valid.expect(true.B); d.io.plan_in.ready.expect(false.B)
        d.io.plan_out.bits.transaction_identity.request_id.expect(1.U)
        d.io.plan_out.bits.source_presence.expect(5.U)
        d.io.plan_out.bits.packed_instance.generation.expect(1.U)
        d.io.query_out.valid.expect(false.B); d.io.reservation_request_out.valid.expect(false.B)
        d.io.demand_out.valid.expect(false.B); d.io.r6_reject_out.valid.expect(false.B)
        d.io.binder_cancel_out.valid.expect(false.B); driver.tick()
      }
      assert(driver.descriptorQueries == 1 && driver.reservations == 1 && driver.planAccepts == 0)
      d.io.plan_out.ready.poke(true.B); driver.tick()
      d.io.plan_in.valid.poke(false.B); d.io.plan_out.ready.poke(false.B)
      for (_ <- 0 until 5) {
        d.io.busy.expect(true.B); d.io.demand_out.valid.expect(false.B)
        d.io.r6_reject_out.valid.expect(false.B); driver.tick()
      }
      driver.plan(d.io.accepted_plan_in.bits, 1); d.io.accepted_plan_in.valid.poke(true.B)
      d.io.accepted_plan_in.ready.expect(true.B); driver.tick(); d.io.accepted_plan_in.valid.poke(false.B)
      for (_ <- 0 until 4) {
        d.io.descriptor_grant_out.valid.expect(true.B)
        d.io.descriptor_grant_out.bits.payload_handle_or_address.expect(55.U)
        d.io.descriptor_grant_out.bits.sidecar_handle_or_address.expect(77.U)
        d.io.s2_fill_lease_out.valid.expect(true.B)
        d.io.s2_fill_lease_out.bits.transaction_identity.request_id.expect(1.U)
        d.io.s2_fill_lease_out.bits.source_generation.expect(1.U)
        d.io.publication_authorization_out.bits.transaction_group_tag.expect(1.U)
        driver.tick()
      }
      d.io.demand_out.ready.poke(true.B); driver.tick(); d.io.demand_out.ready.poke(false.B)
      d.io.demand_out.valid.expect(false.B); d.io.s2_fill_lease_out.valid.expect(true.B)
      d.io.publication_authorization_out.ready.poke(true.B)
      d.io.descriptor_grant_out.ready.poke(true.B); d.io.s2_fill_lease_out.ready.poke(true.B)
      driver.tick(); d.io.busy.expect(false.B)
      assert(driver.planAccepts == 1 && driver.descriptorQueries == 1 && driver.reservations == 1)
      assert(driver.demands == 1 && driver.faultsToR6 == 0 && driver.cancellations == 0)
      println("PERSISTENT_READ_V2_PREFLIGHT_BACKPRESSURE_PASS plan_accepts=1 queries=1 reservations=1 demands=1 owner_mocks=1")
    }
  }

  it("joins skewed cancellation ACKs and rejects a foreign declaration without reserving or inventing an R6 fault") {
    simulate(new RouteAPersistentPackedReadController(p)) { d =>
      val driver = new Driver(d); driver.init()
      driver.select(2); driver.declare(2); driver.location(2, PersistentReadStatus.Invalid)
      driver.until("live rejection")(driver.bit(d.io.r6_reject_out.valid))
      for (_ <- 0 until 4) {
        d.io.plan_out.valid.expect(false.B); d.io.binder_cancel_out.valid.expect(true.B)
        d.io.reservation_request_out.valid.expect(false.B); driver.tick()
      }
      d.io.binder_cancel_out.ready.poke(true.B); driver.tick()
      d.io.binder_cancel_out.ready.poke(false.B)
      d.io.rejected_out.ready.poke(true.B)
      driver.until("local rejection consumed")(driver.localRejections == 1)
      for (_ <- 0 until 3) { d.io.r6_reject_out.valid.expect(true.B); driver.tick() }
      d.io.r6_reject_out.ready.poke(true.B); driver.tick(); d.io.r6_reject_out.ready.poke(false.B)
      driver.until("both cancel ACKs complete")(!driver.bit(d.io.busy))
      assert(driver.planAccepts == 0 && driver.reservations == 0 && driver.faultsToR6 == 1)

      // No selector is needed to discover that this declaration has no live
      // R6 attention. The foreign identity is not assigned a fault terminal.
      driver.declare(7); d.io.binder_cancel_out.ready.poke(true.B)
      driver.until("foreign rejection complete")(driver.localRejections == 2 && !driver.bit(d.io.busy))
      assert(driver.planAccepts == 0 && driver.reservations == 0 && driver.faultsToR6 == 1)
      assert(driver.cancellations == 2 && driver.descriptorQueries == 1)
      println("PERSISTENT_READ_V2_PREFLIGHT_REJECTION_PASS live_faults=1 foreign_faults=0 cancels=2 reservations=0 owner_mocks=1")
    }
  }

  it("keeps an already installed R6 plan ineligible while its completed sources wait for merge") {
    simulate(new RouteAPersistentR6ContextHarness(p)) { d =>
      def id(x: TransactionIdentity): Unit = { x.request_id.poke(2.U); x.incarnation.poke(0.U) }
      def waitFor(clue: String)(f: => Boolean): Unit = {
        var n = 0; while (!f && n < 40) { d.clock.step(); n += 1 }
        assert(f, clue)
      }
      d.io.status.valid.poke(false.B); d.io.frontend.valid.poke(false.B)
      d.io.plan.valid.poke(false.B); d.io.release.valid.poke(false.B)
      d.io.context.valid.poke(false.B); id(d.io.context.bits.transaction_identity)
      d.io.result.ready.poke(false.B); d.io.merge.ready.poke(false.B)
      for (code <- Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode)) {
        d.io.status.bits.acknowledgement_name.poke(code.U); d.io.status.bits.asserted.poke(true.B)
        d.io.status.valid.poke(true.B); waitFor("R6 init")(d.io.status.ready.peek().litToBoolean)
        d.clock.step(); d.io.status.valid.poke(false.B)
      }
      def frontend(event: Int, layer: Int): Unit = {
        val f = d.io.frontend.bits
        f.event_kind.poke(event.U); f.session_id.poke(false.B)
        f.context_tokens.poke((if (event == p.r6.sessionStartEventCode) 32768 else 0).U)
        f.entry_id.poke((layer * 8).U); f.layer.poke(layer.U); f.kv_head.poke(0.U)
        f.logical_position.poke(0.U); f.payload_ref.poke(0.U); f.disposition.poke(false.B)
        id(f.transaction_identity); f.admission_group_tag.poke(0.U)
        f.admission_member_ordinal.poke(0.U); f.admission_group_valid_records.poke(0.U)
        d.io.frontend.valid.poke(true.B); waitFor("R6 frontend")(d.io.frontend.ready.peek().litToBoolean)
        d.clock.step(); d.io.frontend.valid.poke(false.B)
      }
      def context(eligible: Boolean): Unit = {
        d.io.context.valid.poke(true.B); waitFor("context accepted")(d.io.context.ready.peek().litToBoolean)
        d.clock.step(); d.io.context.valid.poke(false.B)
        waitFor("context result")(d.io.result.valid.peek().litToBoolean)
        d.io.result.bits.eligible.expect(eligible.B)
        if (eligible) { d.io.result.bits.layer.expect(1.U); d.io.result.bits.kv_head.expect(0.U) }
        d.io.result.ready.poke(true.B); d.clock.step(); d.io.result.ready.poke(false.B)
      }
      frontend(p.r6.sessionStartEventCode, 0)
      frontend(p.r6.attentionServiceEventCode, 1)
      context(eligible = true)
      val plan = d.io.plan.bits
      id(plan.transaction_identity); plan.source_presence.poke(4.U)
      for ((instance, kind) <- Seq(plan.hot_instance -> 0, plan.pending_instance -> 1, plan.packed_instance -> 2)) {
        instance.source_kind.poke(kind.U); instance.instance_coordinate.poke(0.U); instance.generation.poke(1.U)
      }
      d.io.plan.valid.poke(true.B); d.io.plan.ready.expect(true.B)
      d.clock.step(); d.io.plan.valid.poke(false.B); d.clock.step()
      val release = d.io.release.bits
      id(release.transaction_identity); release.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
      release.source_instance.instance_coordinate.poke(0.U); release.source_instance.generation.poke(1.U)
      d.io.release.valid.poke(true.B); d.io.release.ready.expect(true.B)
      d.clock.step(); d.io.release.valid.poke(false.B)
      d.io.merge.valid.expect(true.B) // Keep AwaitMergeReady with sourcePlanValid now clear.
      context(eligible = false)
      d.io.plan.valid.poke(true.B)
      for (_ <- 0 until 4) { d.io.plan.ready.expect(false.B); d.io.merge.valid.expect(true.B); d.clock.step() }
      println("PERSISTENT_READ_V2_R6_NO_REPLAN_PASS real_r6=1 mocked_source_release=1 eligible_after_release=0 duplicate_plan_ready=0")
    }
  }
}
