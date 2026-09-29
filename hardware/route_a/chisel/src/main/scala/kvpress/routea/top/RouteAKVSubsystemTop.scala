package kvpress.routea.top

import chisel3._
import kvpress.routea.common._
import kvpress.routea.incremental._
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * Composition-only RTL1.0 skeleton for the frozen Route-A hierarchy.
  *
  * All non-environment cross-owner channels exist and are connected. Channels
  * without a functional producer/consumer are structurally tied inactive. No
  * mutable architecture state, protocol transition, publication, arbitration,
  * source release, retry, fallback, or numeric behavior is implemented here.
  */
final class RouteAKVSubsystemTop(p: RouteASkeletonParameters) extends RawModule {
  override def desiredName: String = "route_a_kv_subsystem_top"

  val core_clk = IO(Input(Clock()))
  // A Bool carrier avoids selecting synchronous versus asynchronous reset at
  // RTL1.0. This shell contains no sequential state or reset behavior.
  val destructive_reset = IO(Input(Bool()))

  val frontend_lifecycle_req = IO(Flipped(RouteAChannels.frontend_lifecycle_req(p)))
  val runtime_retire_req = IO(Flipped(RouteAChannels.runtime_retire_req))
  val attention_terminal_rsp = IO(RouteAChannels.attention_terminal_rsp)
  val session_retire_ack = IO(RouteAChannels.session_retire_ack)
  val external_core_mem_if_v1 = IO(new CoreMemoryExternalPort(p))

  withClockAndReset(core_clk, destructive_reset) {
    val lifecycle = Module(new RouteALifecycleAdapter(p))
    val hot = Module(new RouteAHotSourcePath(p))
    val s2 = Module(new RouteAS2GqaSourceWrapper)
    val direct_pending = Module(new RouteADirectPendingEndpointV1(p))
    val arbiter = Module(new RouteACoreSideArbiter(p))
    val core_memory = Module(new RouteACoreMemIfV1(p))
    val m2_p3 = Module(new RouteAM2P3Wrapper(p))
    val page_manager = Module(new RouteAPageManager(p))
    val merge = Module(new RouteAMergeBoundary)

    lifecycle.io.frontend_lifecycle_req <> frontend_lifecycle_req
    lifecycle.io.runtime_retire_req <> runtime_retire_req
    attention_terminal_rsp <> lifecycle.io.attention_terminal_rsp
    session_retire_ack <> lifecycle.io.session_retire_ack

    val component_status_in = Wire(RouteAChannels.component_status(p))
    StructuralTieOff.source(component_status_in)
    lifecycle.io.component_status_in <> component_status_in

    hot.io.lifecycle_control_in <> lifecycle.io.hot_control_out
    s2.io.service_req_in <> lifecycle.io.s2_service_req
    direct_pending.io.pending_source_open_in <> lifecycle.io.direct_pending_open

    val source_partial_to_merge = Wire(RouteAChannels.source_partial)
    StructuralTieOff.source(source_partial_to_merge)
    merge.io.source_partial_in <> source_partial_to_merge

    val merge_source_commit = Wire(RouteAChannels.consumer_partial_commit)
    merge_source_commit <> merge.io.consumer_partial_commit
    StructuralTieOff.sink(merge_source_commit)

    merge.io.merge_req_in <> lifecycle.io.merge_req
    lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault

    val source_candidate_to_r2 = Wire(RouteAChannels.source_candidate(p))
    StructuralTieOff.source(source_candidate_to_r2)
    arbiter.io.candidate_in <> source_candidate_to_r2

    core_memory.io.core_mem_req_in <> arbiter.io.core_mem_req
    arbiter.io.core_mem_rsp_in <> core_memory.io.core_mem_rsp
    // RTL1.1 verifies R1 in isolation. The top-level lifecycle/reset adapter
    // has not yet acquired its owner phase, so it deliberately cannot release
    // R1 traffic in this still nonfunctional integration skeleton.
    core_memory.io.mem_init_done := false.B
    external_core_mem_if_v1 <> core_memory.io.external_core_mem_if_v1

    val source_delivery = Wire(RouteAChannels.source_delivery(p))
    source_delivery <> arbiter.io.source_delivery_out
    StructuralTieOff.sink(source_delivery)

    m2_p3.io.m2_publish_req_in <> lifecycle.io.metadata_publish_req
    page_manager.io.metadata_publish_visibility_in <> m2_p3.io.metadata_publish_visibility_apply
    m2_p3.io.metadata_publish_visibility_ack_in <> page_manager.io.metadata_publish_visibility_ack
    lifecycle.io.metadata_publish_ack_in <> m2_p3.io.m2_publish_ack
  }
}
