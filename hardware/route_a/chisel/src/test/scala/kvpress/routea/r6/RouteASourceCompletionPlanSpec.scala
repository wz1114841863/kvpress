package kvpress.routea.r6

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAHotSourcePath
import kvpress.routea.incremental.RouteALifecycleAdapter
import kvpress.routea.incremental.RouteAMergeBoundary
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Test-only I3 composition harness for one real hot-owner release path.  It
  * deliberately exposes packet ingress as a stimulus and owns no production
  * source mux, numeric core, payload path, or scheduler.
  */
private final class RouteAHotR4R6Harness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val lifecycle_status = Flipped(RouteAChannels.component_status(p))
    val source_plan = Flipped(RouteAChannels.source_completion_plan(p))
    val hot_open = Flipped(RouteAChannels.hot_source_open(p))
    val r4_header = Flipped(RouteAChannels.r4_partial_header)
    val r4_sideband = Flipped(RouteAChannels.r4_source_instance_sideband(p))
    val r4_numeric_fault = Flipped(RouteAChannels.r4_numeric_fault)
    val attention_terminal = RouteAChannels.attention_terminal_rsp
  })

  val lifecycle = Module(new RouteALifecycleAdapter(p))
  val hot = Module(new RouteAHotSourcePath(p))
  val merge = Module(new RouteAMergeBoundary(p))

  lifecycle.io.frontend_lifecycle_req <> io.frontend
  lifecycle.io.component_status_in <> io.lifecycle_status
  io.attention_terminal <> lifecycle.io.attention_terminal_rsp
  StructuralTieOff.source(lifecycle.io.runtime_retire_req)
  StructuralTieOff.sink(lifecycle.io.session_retire_ack)
  StructuralTieOff.sink(lifecycle.io.reclaim_permit_out)
  hot.io.lifecycle_control_in <> lifecycle.io.hot_control_out
  hot.io.hot_source_open_in <> io.hot_open
  lifecycle.io.source_completion_plan_in <> io.source_plan
  lifecycle.io.source_completion_plan_copy_out.ready := true.B
  lifecycle.io.hot_source_release_in <> hot.io.hot_release_out
  StructuralTieOff.source(lifecycle.io.pending_source_release_in)
  StructuralTieOff.source(lifecycle.io.packed_source_release_in)
  StructuralTieOff.source(lifecycle.io.merge_ready_in)
  StructuralTieOff.sink(lifecycle.io.authority_transition_out)
  StructuralTieOff.sink(lifecycle.io.admission_context_out)
  StructuralTieOff.source(lifecycle.io.authority_transition_in)
  StructuralTieOff.sink(lifecycle.io.s2_service_req)
  StructuralTieOff.sink(lifecycle.io.direct_pending_open)
  StructuralTieOff.sink(lifecycle.io.metadata_publish_req)
  StructuralTieOff.source(lifecycle.io.metadata_publish_ack_in)
  lifecycle.io.r5_reclaim_complete_in := false.B

  merge.io.drain_collection_enable := false.B
  StructuralTieOff.source(merge.io.source_partial_in)
  merge.io.r4_partial_header_in <> io.r4_header
  merge.io.r4_source_instance_in <> io.r4_sideband
  StructuralTieOff.source(merge.io.r4_value_fragment_in)
  merge.io.r4_accepted_partial_packet_out.ready := true.B
  StructuralTieOff.source(merge.io.r4_result_stub_in)
  merge.io.r4_numeric_fault_in <> io.r4_numeric_fault
  hot.io.gqa_consumer_commit_in.valid := merge.io.consumer_partial_commit.valid &&
    merge.io.consumer_partial_commit.bits.source_instance.source_kind === RouteASourceKind.Hot.U
  hot.io.gqa_consumer_commit_in.bits := merge.io.consumer_partial_commit.bits
  merge.io.consumer_partial_commit.ready := hot.io.gqa_consumer_commit_in.ready
  merge.io.merge_req_in <> lifecycle.io.merge_req
  lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault
  StructuralTieOff.sink(merge.io.component_status_out)
}

/** I3 R6 source-plan/release control; no source mux, payload, or timing model. */
final class RouteASourceCompletionPlanSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 8, coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1, p3StageGenerationWidth = 1, r5AllocatorEntries = 8, r5StreamSlots = 8,
    sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(dut: RouteALifecycleAdapter): Unit = {
    dut.io.frontend_lifecycle_req.valid.poke(false.B); dut.io.runtime_retire_req.valid.poke(false.B)
    dut.io.component_status_in.valid.poke(false.B); dut.io.authority_transition_in.valid.poke(false.B)
    dut.io.merge_ready_in.valid.poke(false.B); dut.io.merge_terminal_in.valid.poke(false.B)
    dut.io.source_completion_plan_in.valid.poke(false.B); dut.io.hot_source_release_in.valid.poke(false.B)
    dut.io.source_completion_plan_copy_out.ready.poke(true.B)
    dut.io.pending_source_release_in.valid.poke(false.B); dut.io.packed_source_release_in.valid.poke(false.B)
    dut.io.hot_control_out.ready.poke(true.B); dut.io.authority_transition_out.ready.poke(true.B); dut.io.admission_context_out.ready.poke(true.B)
    dut.io.merge_req.ready.poke(true.B); dut.io.attention_terminal_rsp.ready.poke(true.B); dut.io.session_retire_ack.ready.poke(true.B)
    dut.io.s2_service_req.ready.poke(true.B); dut.io.direct_pending_open.ready.poke(true.B); dut.io.metadata_publish_req.ready.poke(true.B); dut.io.metadata_publish_ack_in.valid.poke(false.B)
    dut.io.reclaim_permit_out.ready.poke(true.B)
    dut.io.r5_reclaim_complete_in.poke(false.B)
    dut.io.component_status_in.bits.asserted.poke(false.B)
  }

  private def status(dut: RouteALifecycleAdapter, code: Int): Unit = {
    dut.io.component_status_in.bits.acknowledgement_name.poke(code.U); dut.io.component_status_in.bits.asserted.poke(true.B)
    dut.io.component_status_in.valid.poke(true.B); dut.io.component_status_in.ready.expect(true.B); dut.clock.step(); dut.io.component_status_in.valid.poke(false.B)
  }

  private def frontend(dut: RouteALifecycleAdapter, event: Int, rid: Int): Unit = {
    val in = dut.io.frontend_lifecycle_req.bits
    in.event_kind.poke(event.U); in.session_id.poke(false.B); in.context_tokens.poke(32768.U); in.entry_id.poke(0.U)
    in.layer.poke(0.U); in.kv_head.poke(0.U); in.logical_position.poke(0.U); in.payload_ref.poke(0.U); in.disposition.poke(false.B)
    in.transaction_identity.request_id.poke(rid.U); in.transaction_identity.incarnation.poke(0.U)
    in.admission_group_tag.poke(0.U); in.admission_member_ordinal.poke(0.U); in.admission_group_valid_records.poke(1.U)
    dut.io.frontend_lifecycle_req.valid.poke(true.B); dut.io.frontend_lifecycle_req.ready.expect(true.B); dut.clock.step(); dut.io.frontend_lifecycle_req.valid.poke(false.B)
  }

  private def driveInstance(instance: kvpress.routea.interfaces.SourceInstance, kind: Int, coordinate: Int, generation: Int): Unit = {
    instance.source_kind.poke(kind.U); instance.instance_coordinate.poke(coordinate.U); instance.generation.poke(generation.U)
  }

  private def plan(dut: RouteALifecycleAdapter, rid: Int, presence: Int): Unit = {
    val in = dut.io.source_completion_plan_in.bits
    in.transaction_identity.request_id.poke(rid.U); in.transaction_identity.incarnation.poke(0.U); in.source_presence.poke(presence.U)
    driveInstance(in.hot_instance, 0, 100 + rid, 1); driveInstance(in.pending_instance, 1, 0, 1); driveInstance(in.packed_instance, 2, 0, 1)
    dut.io.source_completion_plan_in.valid.poke(true.B); dut.io.source_completion_plan_in.ready.expect(true.B); dut.clock.step(); dut.io.source_completion_plan_in.valid.poke(false.B)
  }

  private def release(dut: RouteALifecycleAdapter, kind: Int, rid: Int): Unit = {
    val channel = kind match {
      case 0 => dut.io.hot_source_release_in
      case 1 => dut.io.pending_source_release_in
      case _ => dut.io.packed_source_release_in
    }
    channel.bits.transaction_identity.request_id.poke(rid.U); channel.bits.transaction_identity.incarnation.poke(0.U)
    driveInstance(channel.bits.source_instance, kind, if (kind == 0) 100 + rid else 0, 1)
    channel.valid.poke(true.B); channel.ready.expect(true.B); dut.clock.step(); channel.valid.poke(false.B)
  }

  it("emits merge readiness only after every planned source release for all seven nonempty masks") {
    simulate(new RouteALifecycleAdapter(p)) { dut =>
      init(dut)
      Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach(status(dut, _))
      frontend(dut, p.r6.sessionStartEventCode, 0)
      for (presence <- 1 to 7) {
        frontend(dut, p.r6.attentionServiceEventCode, presence); plan(dut, presence, presence)
        if ((presence & 4) != 0 && presence == 4) {
          val stale = dut.io.packed_source_release_in
          stale.bits.transaction_identity.request_id.poke(presence.U); stale.bits.transaction_identity.incarnation.poke(0.U)
          driveInstance(stale.bits.source_instance, 2, 0, 0); stale.valid.poke(true.B); stale.ready.expect(false.B); stale.valid.poke(false.B)
        }
        for (kind <- 0 to 2 if (presence & (1 << kind)) != 0) release(dut, kind, presence)
        dut.io.merge_req.valid.expect(true.B); dut.io.merge_req.bits.transaction_identity.request_id.expect(presence.U); dut.io.merge_req.bits.source_presence.expect(presence.U)
        dut.clock.step()
        dut.io.merge_terminal_in.bits.transaction_identity.request_id.poke(presence.U); dut.io.merge_terminal_in.bits.transaction_identity.incarnation.poke(0.U)
        dut.io.merge_terminal_in.bits.status.poke(p.coreMemoryFaultStatusCode.U); dut.io.merge_terminal_in.valid.poke(true.B); dut.io.merge_terminal_in.ready.expect(true.B)
        dut.clock.step(); dut.io.merge_terminal_in.valid.poke(false.B)
        dut.io.attention_terminal_rsp.valid.expect(true.B); dut.io.attention_terminal_rsp.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U); dut.clock.step()
      }
    }
  }

  it("routes four hot R4 commits through the owner release into one R6 numeric-fault terminal") {
    simulate(new RouteAHotR4R6Harness(p)) { dut =>
      dut.io.frontend.valid.poke(false.B); dut.io.lifecycle_status.valid.poke(false.B)
      dut.io.source_plan.valid.poke(false.B); dut.io.hot_open.valid.poke(false.B)
      dut.io.r4_header.valid.poke(false.B); dut.io.r4_sideband.valid.poke(false.B)
      dut.io.r4_numeric_fault.valid.poke(false.B); dut.io.attention_terminal.ready.poke(true.B)
      Seq(p.r6.memInitDoneStatusCode, p.r6.m2P3InitDoneStatusCode, p.r6.pageManagerInitDoneStatusCode).foreach { code =>
        dut.io.lifecycle_status.bits.acknowledgement_name.poke(code.U); dut.io.lifecycle_status.bits.asserted.poke(true.B)
        dut.io.lifecycle_status.valid.poke(true.B); dut.io.lifecycle_status.ready.expect(true.B); dut.clock.step(); dut.io.lifecycle_status.valid.poke(false.B)
      }

      val frontend = dut.io.frontend.bits
      frontend.event_kind.poke(p.r6.sessionStartEventCode.U); frontend.session_id.poke(false.B); frontend.context_tokens.poke(32768.U)
      frontend.entry_id.poke(0.U); frontend.layer.poke(0.U); frontend.kv_head.poke(0.U); frontend.logical_position.poke(0.U); frontend.payload_ref.poke(0.U)
      frontend.disposition.poke(false.B); frontend.transaction_identity.request_id.poke(0.U); frontend.transaction_identity.incarnation.poke(0.U)
      frontend.admission_group_tag.poke(0.U); frontend.admission_member_ordinal.poke(0.U); frontend.admission_group_valid_records.poke(1.U)
      dut.io.frontend.valid.poke(true.B); dut.io.frontend.ready.expect(true.B); dut.clock.step(); dut.io.frontend.valid.poke(false.B)
      frontend.event_kind.poke(p.r6.attentionServiceEventCode.U); frontend.transaction_identity.request_id.poke(1.U)
      dut.io.frontend.valid.poke(true.B); dut.io.frontend.ready.expect(true.B); dut.clock.step(); dut.io.frontend.valid.poke(false.B)

      val hot = dut.io.hot_open.bits
      hot.transaction_identity.request_id.poke(1.U); hot.transaction_identity.incarnation.poke(0.U)
      driveInstance(hot.source_instance, 0, 41, 1)
      dut.io.hot_open.valid.poke(true.B); dut.io.hot_open.ready.expect(true.B); dut.clock.step(); dut.io.hot_open.valid.poke(false.B)

      val plan = dut.io.source_plan.bits
      plan.transaction_identity.request_id.poke(1.U); plan.transaction_identity.incarnation.poke(0.U); plan.source_presence.poke(1.U)
      driveInstance(plan.hot_instance, 0, 41, 1); driveInstance(plan.pending_instance, 1, 0, 1); driveInstance(plan.packed_instance, 2, 0, 1)
      dut.io.source_plan.valid.poke(true.B); dut.io.source_plan.ready.expect(true.B); dut.clock.step(); dut.io.source_plan.valid.poke(false.B)

      for (consumer <- 0 until 4) {
        val header = BigInt("ff800000", 16) | (BigInt(consumer) << 66)
        dut.io.r4_header.bits.transaction_identity.request_id.poke(1.U); dut.io.r4_header.bits.transaction_identity.incarnation.poke(0.U)
        dut.io.r4_header.bits.header.poke(header.U); dut.io.r4_header.valid.poke(true.B)
        dut.io.r4_sideband.bits.transaction_identity.request_id.poke(1.U); dut.io.r4_sideband.bits.transaction_identity.incarnation.poke(0.U)
        driveInstance(dut.io.r4_sideband.bits.source_instance, 0, 41, 1); dut.io.r4_sideband.bits.consumer_id.poke(consumer.U); dut.io.r4_sideband.valid.poke(true.B)
        dut.io.r4_header.ready.expect(true.B); dut.io.r4_sideband.ready.expect(true.B); dut.clock.step()
        dut.io.r4_header.valid.poke(false.B); dut.io.r4_sideband.valid.poke(false.B)
        dut.clock.step() // The matching R4 commit fires into the hot owner.
      }
      dut.clock.step() // hot release fires into R6 and creates the merge request.
      dut.clock.step() // R6 merge request fires into R4.
      dut.io.r4_numeric_fault.bits.transaction_identity.request_id.poke(1.U); dut.io.r4_numeric_fault.bits.transaction_identity.incarnation.poke(0.U)
      dut.io.r4_numeric_fault.valid.poke(true.B); dut.io.r4_numeric_fault.ready.expect(true.B); dut.clock.step(); dut.io.r4_numeric_fault.valid.poke(false.B)
      dut.clock.step() // R4 terminal fires into R6.
      dut.io.attention_terminal.valid.expect(true.B); dut.io.attention_terminal.bits.transaction_identity.request_id.expect(1.U)
      dut.io.attention_terminal.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U); dut.clock.step()
    }
  }
}
