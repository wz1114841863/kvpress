package kvpress.routea.incremental

import chisel3._
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

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

/** RTL1.0 structural shell only; no M2/P3 state, durability, or publication exists here. */
final class RouteAM2P3Wrapper(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_m2_p3_wrapper"

  val io = IO(new Bundle {
    val m2_publish_req_in = Flipped(RouteAChannels.metadata_publish_req(p))
    val metadata_publish_visibility_apply = RouteAChannels.metadata_publish_visibility(p)
    val metadata_publish_visibility_ack_in = Flipped(RouteAChannels.metadata_publish_visibility_ack)
    val m2_publish_ack = RouteAChannels.metadata_publish_ack(p)
  })

  StructuralTieOff.sink(io.m2_publish_req_in)
  StructuralTieOff.source(io.metadata_publish_visibility_apply)
  StructuralTieOff.sink(io.metadata_publish_visibility_ack_in)
  StructuralTieOff.source(io.m2_publish_ack)
}

/** RTL1.0 structural shell only; no descriptor/allocator/reclaim state exists here. */
final class RouteAPageManager(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_page_manager"

  val io = IO(new Bundle {
    val metadata_publish_visibility_in = Flipped(RouteAChannels.metadata_publish_visibility(p))
    val metadata_publish_visibility_ack = RouteAChannels.metadata_publish_visibility_ack
  })

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
