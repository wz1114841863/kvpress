package kvpress.routea.top

import chisel3._
import chisel3.util.{Decoupled, DecoupledIO, Valid}
import kvpress.routea.baseline._
import kvpress.routea.common._
import kvpress.routea.interfaces._
import kvpress.routea.params.RouteASkeletonParameters

/**
  * Measurement-only Full-KV control composition.
  *
  * `core_mem_if_v1` and the source-partial/consumer boundary remain explicit
  * outer contracts.  This is neither a memory controller nor an attention PE.
  */
final class FullKVMeasurementDut(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val full_kv_read_work_in = Flipped(Decoupled(new FullKVReadWork(p)))
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
    val source_ready_out = Output(Valid(new FullKVSourceReady(p)))
    // The outer source-service provider supplies only the four accepted
    // consumer-completion facts.  It is not an attention PE or numeric model.
    val full_kv_consumer_commit_in = Flipped(Decoupled(new FullKVGqaConsumerCommit(p)))
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val session_retire_ack = RouteAChannels.session_retire_ack
    val r1_component_status_out = RouteAChannels.component_status(p)
    val r2_payload_drain_status_out = RouteAChannels.component_status(p)
    val r2_descriptor_drain_status_out = RouteAChannels.component_status(p)
  })
  private def inactive[T <: Data](channel: DecoupledIO[T]): Unit = {
    channel.valid := false.B
    channel.bits := 0.U.asTypeOf(channel.bits)
  }
  private def discard[T <: Data](channel: DecoupledIO[T]): Unit = channel.ready := true.B
  val producer = Module(new FullKVReadProducer(p))
  val bridge = Module(new FullKVDeliveryContextBridge(p))
  val arbiter = Module(new RouteACoreSideArbiter(p))
  val core = Module(new RouteACoreMemIfV1(p))
  val registry = Module(new RouteADeliveryContextRegistry(p))
  val router = Module(new RouteATypedDeliveryRouter(p))
  val endpoint = Module(new FullKVS2ReadEndpoint(p))
  val s2 = Module(new FullKVS2GqaSourceWrapper(p))
  val terminal = Module(new FullKVTerminalRetireAdapter(p))

  producer.io.work_in <> io.full_kv_read_work_in
  bridge.io.candidate_in <> producer.io.candidate_out
  s2.io.fill_open_in <> producer.io.fill_open_out
  arbiter.io.read_candidate_in <> bridge.io.candidate_out
  // Full-KV owns no R3/R5 write-class producer.  The common R2 fabric keeps
  // that input structurally explicit, but this baseline contour admits reads
  // only from the named FullKVReadProducer above; no outer legacy candidate
  // can bypass it.
  inactive(arbiter.io.candidate_in)
  core.io.core_mem_req_in <> arbiter.io.core_mem_req
  arbiter.io.core_mem_rsp_in <> core.io.core_mem_rsp
  core.io.external_core_mem_if_v1 <> io.external_core_mem_if_v1
  registry.io.mem_init_done := core.io.r1_init_complete
  bridge.io.allocation_out <> registry.io.allocation_in
  bridge.io.allocation_ack_in <> registry.io.allocation_ack_out
  registry.io.resolve_in <> arbiter.io.source_delivery_out
  router.io.resolved_in <> registry.io.resolved_out
  endpoint.io.resolved_in <> router.io.read_fragment_out
  s2.io.payload_in <> endpoint.io.payload_out
  s2.io.terminal_in <> endpoint.io.terminal_out
  registry.io.release_in <> router.io.release_out
  bridge.io.release_event_in := router.io.release_event_out
  s2.io.mem_init_done := core.io.r1_init_complete
  io.source_ready_out := s2.io.source_ready_out
  s2.io.consumer_commit_in <> io.full_kv_consumer_commit_in
  terminal.io.source_release_in <> s2.io.source_release_out
  io.attention_terminal_rsp <> terminal.io.attention_terminal_rsp
  terminal.io.runtime_retire_req <> io.runtime_retire_req
  io.session_retire_ack <> terminal.io.session_retire_ack
  core.io.r1_drain_permitted := terminal.io.drain_collection_enable
  arbiter.io.drain_collection_enable := terminal.io.drain_collection_enable
  arbiter.io.reclaim_maintenance_enable := false.B
  io.r1_component_status_out <> core.io.component_status_out
  io.r2_payload_drain_status_out <> arbiter.io.payload_drain_status_out
  io.r2_descriptor_drain_status_out <> arbiter.io.descriptor_drain_status_out
  // These Route-A-only typed egresses remain structurally present in the
  // shared router but have no Full-KV producer or consumer in this contour.
  discard(router.io.r3_packed_write_out)
  discard(router.io.r5_append_out)
  discard(router.io.r5_reclaim_out)
}
