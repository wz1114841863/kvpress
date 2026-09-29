package kvpress.routea.common

import chisel3._
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/** RTL1.0 structural shell only; hot-residency behavior begins in a later phase. */
final class RouteAHotSourcePath(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_hot_source_path"

  val io = IO(new Bundle {
    val lifecycle_control_in = Flipped(RouteAChannels.hot_control(p))
  })

  StructuralTieOff.sink(io.lifecycle_control_in)
}

/** RTL1.0 structural shell only; no S2 state, generation, or GQA behavior exists here. */
final class RouteAS2GqaSourceWrapper extends Module {
  override def desiredName: String = "route_a_s2_gqa_source_wrapper"

  val io = IO(new Bundle {
    val service_req_in = Flipped(RouteAChannels.s2_service_req)
  })

  StructuralTieOff.sink(io.service_req_in)
}

/** RTL1.0 structural shell only; no R2 eligibility, credit, FIFO, or grant state exists here. */
final class RouteACoreSideArbiter(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_core_side_arbiter"

  val io = IO(new Bundle {
    val candidate_in = Flipped(RouteAChannels.source_candidate(p))
    val core_mem_req = RouteAChannels.core_mem_req(p)
    val core_mem_rsp_in = Flipped(RouteAChannels.core_mem_rsp(p))
    val source_delivery_out = RouteAChannels.source_delivery(p)
  })

  StructuralTieOff.sink(io.candidate_in)
  StructuralTieOff.source(io.core_mem_req)
  StructuralTieOff.sink(io.core_mem_rsp_in)
  StructuralTieOff.source(io.source_delivery_out)
}

/** RTL1.0 structural shell only; this is the single R1 boundary, not a controller. */
final class RouteACoreMemIfV1(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "route_a_core_mem_if_v1"

  val io = IO(new Bundle {
    val core_mem_req_in = Flipped(RouteAChannels.core_mem_req(p))
    val core_mem_rsp = RouteAChannels.core_mem_rsp(p)
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
  })

  StructuralTieOff.sink(io.core_mem_req_in)
  StructuralTieOff.source(io.core_mem_rsp)
  StructuralTieOff.source(io.external_core_mem_if_v1.request)
  StructuralTieOff.sink(io.external_core_mem_if_v1.response)
}
