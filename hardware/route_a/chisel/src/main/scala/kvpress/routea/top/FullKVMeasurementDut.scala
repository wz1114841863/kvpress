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
class FullKVMeasurementDut(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val full_kv_read_work_in = Flipped(Decoupled(new FullKVReadWork(p)))
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
    val source_ready_out = Output(Valid(new FullKVSourceReady(p)))
    // Owner-only source-service access to an already READY baseline S2 slot.
    // It is neither an attention PE nor a Route-A source/sidecar interface.
    val full_kv_payload_read_req_in = Flipped(Decoupled(new FullKVPayloadReadRequest(p)))
    val full_kv_payload_read_rsp_out = Decoupled(new FullKVPayloadReadResponse(p))
    // The outer source-service provider supplies only the four accepted
    // consumer-completion facts.  It is not an attention PE or numeric model.
    val full_kv_consumer_commit_in = Flipped(Decoupled(new FullKVGqaConsumerCommit(p)))
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val session_retire_ack = RouteAChannels.session_retire_ack
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
  val statusCollector = Module(new FullKVStatusCollector(p))

  producer.io.service_enable := terminal.io.service_enable
  producer.io.work_in <> io.full_kv_read_work_in
  bridge.io.candidate_in <> producer.io.candidate_out
  s2.io.fill_open_in <> producer.io.fill_open_out
  arbiter.io.read_candidate_in <> bridge.io.candidate_out
  // Full-KV owns no R3/R5 write-class producer.  The common R2 fabric keeps
  // that input structurally explicit, but this baseline contour admits reads
  // only from the named FullKVReadProducer above; no outer legacy candidate
  // can bypass it.
  inactive(arbiter.io.candidate_in)
  // Full-KV has no Route-A direct-pending descriptor owner or lease.  Keep
  // the shared R2 fabric inert on the Route-A-only sideband rather than
  // letting the baseline acquire or account for an invented authority.
  discard(arbiter.io.direct_lease_eligibility_query_out)
  inactive(arbiter.io.direct_lease_eligibility_in)
  discard(arbiter.io.direct_lease_commit_out)
  inactive(arbiter.io.direct_candidate_cancel_in)
  discard(arbiter.io.direct_candidate_cancel_ack_out)
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
  s2.io.payload_read_req_in <> io.full_kv_payload_read_req_in
  io.full_kv_payload_read_rsp_out <> s2.io.payload_read_rsp_out
  registry.io.release_in <> router.io.release_out
  bridge.io.release_event_in := router.io.release_event_out
  s2.io.mem_init_done := core.io.r1_init_complete
  s2.io.drain_collection_enable := terminal.io.drain_collection_enable
  io.source_ready_out := s2.io.source_ready_out
  s2.io.consumer_commit_in <> io.full_kv_consumer_commit_in
  terminal.io.source_release_in <> s2.io.source_release_out
  terminal.io.source_fault_in <> s2.io.fault_terminal_out
  terminal.io.component_status_in <> statusCollector.io.status_out
  io.attention_terminal_rsp <> terminal.io.attention_terminal_rsp
  terminal.io.runtime_retire_req <> io.runtime_retire_req
  io.session_retire_ack <> terminal.io.session_retire_ack
  core.io.r1_drain_permitted := statusCollector.io.r1_drain_permitted
  arbiter.io.drain_collection_enable := terminal.io.drain_collection_enable
  arbiter.io.reclaim_maintenance_enable := false.B
  statusCollector.io.drain_collection_enable := terminal.io.drain_collection_enable
  statusCollector.io.sources(0) <> core.io.component_status_out
  statusCollector.io.sources(1) <> arbiter.io.payload_drain_status_out
  statusCollector.io.sources(2) <> arbiter.io.descriptor_drain_status_out
  statusCollector.io.sources(3) <> s2.io.component_status_out
  // These Route-A-only typed egresses remain structurally present in the
  // shared router but have no Full-KV producer or consumer in this contour.
  discard(router.io.r3_packed_write_out)
  discard(router.io.r5_append_out)
  discard(router.io.r5_reclaim_out)
}

/**
  * Parameterized Full-KV control projection for a future synthesis-input
  * generator. It intentionally has no default parameter profile: callers
  * must supply an explicitly approved RouteASkeletonParameters instance.
  */
final class FullKVControlProjection(p: RouteASkeletonParameters)
    extends FullKVMeasurementDut(p) {
  override def desiredName: String = "full_kv_control_projection"
}
