package kvpress.routea.incremental

import chisel3._
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}

/**
  * RTL1.0 structural shell only. Authority, terminal association, and global
  * retirement behavior remain unimplemented until their respective RTL1 phases.
  */
final class RouteALifecycleAdapter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_lifecycle_adapter"

  val io = IO(new Bundle {
    val frontend_lifecycle_req = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val session_retire_ack = RouteAChannels.session_retire_ack
    val component_status_in = Flipped(RouteAChannels.component_status(p))
    val hot_control_out = RouteAChannels.hot_control(p)
    val s2_service_req = RouteAChannels.s2_service_req
    val direct_pending_open = RouteAChannels.direct_pending_open(p)
    val merge_req = RouteAChannels.merge_req
    val merge_terminal_in = Flipped(RouteAChannels.merge_terminal_rsp)
    val metadata_publish_req = RouteAChannels.metadata_publish_req(p)
    val metadata_publish_ack_in = Flipped(RouteAChannels.metadata_publish_ack(p))
  })

  StructuralTieOff.sink(io.frontend_lifecycle_req)
  StructuralTieOff.sink(io.runtime_retire_req)
  StructuralTieOff.source(io.attention_terminal_rsp)
  StructuralTieOff.source(io.session_retire_ack)
  StructuralTieOff.sink(io.component_status_in)
  StructuralTieOff.source(io.hot_control_out)
  StructuralTieOff.source(io.s2_service_req)
  StructuralTieOff.source(io.direct_pending_open)
  StructuralTieOff.source(io.merge_req)
  StructuralTieOff.sink(io.merge_terminal_in)
  StructuralTieOff.source(io.metadata_publish_req)
  StructuralTieOff.sink(io.metadata_publish_ack_in)
}

/** RTL1.0 structural shell only; no pending transport state or stale filtering exists here. */
final class RouteADirectPendingEndpointV1(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_direct_pending_endpoint_v1"

  val io = IO(new Bundle {
    val pending_source_open_in = Flipped(RouteAChannels.direct_pending_open(p))
  })

  StructuralTieOff.sink(io.pending_source_open_in)
}

/** RTL1.3.0 carrier shell; local inputs remain inactive until RTL1.3 control state. */
final class RouteAM2P3Wrapper(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_m2_p3_wrapper"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val p3_claim_in = Flipped(RouteAChannels.p3_claim(p))
    val p3_pending_fragment_in = Flipped(RouteAChannels.p3_pending_fragment(p))
    val p3_sidecar_bind_in = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val p3_packed_write_terminal_in = Flipped(RouteAChannels.p3_packed_write_terminal(p))
    val m2_group_member_rsp_in = Flipped(RouteAChannels.m2_group_member_rsp(p))
    val p3_observe_layer = Input(UInt(RouteAAnchorWidths.LayerWidth.W))
    val p3_observe_state = Output(UInt(RouteAAnchorWidths.P3StateWidth.W))
    val p3_observe_generation = Output(UInt(p.p3StageGenerationWidth.W))
    val m2_publish_req_in = Flipped(RouteAChannels.metadata_publish_req(p))
    val metadata_publish_visibility_apply = RouteAChannels.metadata_publish_visibility(p)
    val metadata_publish_visibility_ack_in = Flipped(RouteAChannels.metadata_publish_visibility_ack)
    val m2_publish_ack = RouteAChannels.metadata_publish_ack(p)
  })

  StructuralTieOff.sink(io.p3_claim_in)
  StructuralTieOff.sink(io.p3_pending_fragment_in)
  StructuralTieOff.sink(io.p3_sidecar_bind_in)
  StructuralTieOff.sink(io.p3_packed_write_terminal_in)
  StructuralTieOff.sink(io.m2_group_member_rsp_in)
  io.p3_observe_state := 0.U
  io.p3_observe_generation := 0.U
  StructuralTieOff.sink(io.m2_publish_req_in)
  StructuralTieOff.source(io.metadata_publish_visibility_apply)
  StructuralTieOff.sink(io.metadata_publish_visibility_ack_in)
  StructuralTieOff.source(io.m2_publish_ack)
}

/** RTL1.3.0 carrier shell; descriptor HBM traffic remains on the frozen R2/R1 path. */
final class RouteAPageManager(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_page_manager"

  val io = IO(new Bundle {
    val mem_init_done = Input(Bool())
    val page_allocation_req_in = Flipped(RouteAChannels.page_allocation_req(p))
    val page_allocation_rsp = RouteAChannels.page_allocation_rsp(p)
    val descriptor_maintenance_terminal_in = Flipped(RouteAChannels.descriptor_maintenance_terminal(p))
    val metadata_publish_visibility_in = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val metadata_publish_visibility_ack = RouteAChannels.metadata_publish_visibility_ack
  })

  StructuralTieOff.sink(io.page_allocation_req_in)
  StructuralTieOff.source(io.page_allocation_rsp)
  StructuralTieOff.sink(io.descriptor_maintenance_terminal_in)
  StructuralTieOff.sink(io.metadata_publish_visibility_in)
  StructuralTieOff.source(io.metadata_publish_visibility_ack)
}

/**
  * Replaceable R4 boundary shell only. It does not implement merge arithmetic,
  * partial state, numeric-fault detection, source release, or terminal policy.
  */
final class RouteAMergeBoundary extends Module {
  override def desiredName: String = "route_a_merge_boundary"

  val io = IO(new Bundle {
    val source_partial_in = Flipped(RouteAChannels.source_partial)
    val consumer_partial_commit = RouteAChannels.consumer_partial_commit
    val merge_req_in = Flipped(RouteAChannels.merge_req)
    val merge_rsp_or_numeric_fault = RouteAChannels.merge_terminal_rsp
  })

  StructuralTieOff.sink(io.source_partial_in)
  StructuralTieOff.source(io.consumer_partial_commit)
  StructuralTieOff.sink(io.merge_req_in)
  StructuralTieOff.source(io.merge_rsp_or_numeric_fault)
}
