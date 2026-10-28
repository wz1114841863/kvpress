package kvpress.routea

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.FullKVMeasurementDut
import org.scalatest.funspec.AnyFunSpec

/** W0 transaction-level Full-KV baseline proof; no controller or PE model. */
final class FullKVMeasurementDutSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 2, candidateIdWidth = 2, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1, coreMemoryRequestKindWidth = 3,
    coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 3, coreMemoryFragmentIndexWidth = 3,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1, p3StageGenerationWidth = 1, r5AllocatorEntries = 8,
    r5StreamSlots = 8, sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def init(d: FullKVMeasurementDut): Unit = {
    d.io.full_kv_read_work_in.valid.poke(false.B)
    d.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)
    d.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(false.B)
    d.io.external_core_mem_if_v1.request.ready.poke(true.B)
    d.io.external_core_mem_if_v1.response.valid.poke(false.B)
    d.io.full_kv_payload_read_req_in.valid.poke(false.B)
    d.io.full_kv_payload_read_rsp_out.ready.poke(false.B)
    d.io.full_kv_consumer_commit_in.valid.poke(false.B)
    d.io.runtime_retire_req.valid.poke(false.B)
    d.io.attention_terminal_rsp.ready.poke(true.B)
    // Hold the final acknowledgement so tests can prove it is withheld until
    // the actual R1/R2/S2 drain facts have crossed the local lifecycle.
    d.io.session_retire_ack.ready.poke(false.B)
    d.clock.step()
    d.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.external_core_mem_if_v1.init_ack.valid.poke(true.B)
    d.io.external_core_mem_if_v1.init_ack.ready.expect(true.B)
    d.clock.step(); d.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)
    // R1 init is first captured by the one-record collector and then
    // accepted by the lifecycle; leave explicit cycles for both handshakes.
    d.clock.step(6)
  }

  private def work(d: FullKVMeasurementDut, id: Int = 1, generation: Int = 1): Unit = {
    val w = d.io.full_kv_read_work_in.bits
    w.transaction_identity.request_id.poke(id.U); w.transaction_identity.incarnation.poke(1.U)
    w.arrival_ordinal.poke(0.U); w.candidate_id.poke(0.U); w.eligibility_snapshot.poke("b0000001111".U)
    w.payload_handle_or_address.poke(7.U); w.destination_endpoint.poke(0.U)
    w.expected_fragment_count.poke(1.U); w.s2_slot.poke(0.U); w.source_generation.poke(generation.U)
    d.io.full_kv_read_work_in.valid.poke(true.B); d.io.full_kv_read_work_in.ready.expect(true.B)
    d.clock.step(); d.io.full_kv_read_work_in.valid.poke(false.B)
  }

  private def response(d: FullKVMeasurementDut, id: Int, fragment: Int = 0, last: Boolean = true, status: Int = 0): Unit = {
    val r = d.io.external_core_mem_if_v1.response.bits
    r.transaction_identity.request_id.poke(id.U); r.transaction_identity.incarnation.poke(1.U)
    r.fragment_index.poke(fragment.U); r.last.poke(last.B); r.status.poke(status.U); r.data.poke(0x55.U)
    d.io.external_core_mem_if_v1.response.valid.poke(true.B)
    d.clock.step(); d.io.external_core_mem_if_v1.response.valid.poke(false.B)
  }

  private def awaitSourceReady(d: FullKVMeasurementDut): Unit = {
    var wait = 0
    while (!d.io.source_ready_out.valid.peek().litToBoolean && wait < 20) {
      d.clock.step(); wait += 1
    }
    d.io.source_ready_out.valid.expect(true.B)
  }

  private def commit(d: FullKVMeasurementDut, consumer: Int, id: Int = 1): Unit = {
    val c = d.io.full_kv_consumer_commit_in.bits
    c.transaction_identity.request_id.poke(id.U); c.transaction_identity.incarnation.poke(1.U)
    c.source_instance.s2_slot.poke(0.U); c.source_instance.source_generation.poke(1.U); c.consumer_id.poke(consumer.U)
    d.io.full_kv_consumer_commit_in.valid.poke(true.B); d.io.full_kv_consumer_commit_in.ready.expect(true.B)
    d.clock.step(); d.io.full_kv_consumer_commit_in.valid.poke(false.B)
  }

  private def readPayload(d: FullKVMeasurementDut, id: Int = 1, generation: Int = 1, expected: Int = 0x55): Unit = {
    val read = d.io.full_kv_payload_read_req_in.bits
    read.transaction_identity.request_id.poke(id.U); read.transaction_identity.incarnation.poke(1.U)
    read.s2_slot.poke(0.U); read.source_generation.poke(generation.U); read.fragment_index.poke(0.U)
    d.io.full_kv_payload_read_req_in.valid.poke(true.B); d.io.full_kv_payload_read_req_in.ready.expect(true.B)
    d.clock.step(); d.io.full_kv_payload_read_req_in.valid.poke(false.B)
    var wait = 0
    while (!d.io.full_kv_payload_read_rsp_out.valid.peek().litToBoolean && wait < 16) {
      d.clock.step(); wait += 1
    }
    d.io.full_kv_payload_read_rsp_out.valid.expect(true.B)
    d.io.full_kv_payload_read_rsp_out.bits.request.transaction_identity.request_id.expect(id.U)
    d.io.full_kv_payload_read_rsp_out.bits.request.source_generation.expect(generation.U)
    d.io.full_kv_payload_read_rsp_out.bits.data.expect(expected.U)
    // The parent, rather than the array child, holds a response stable while
    // the source-service side applies backpressure.
    d.io.full_kv_payload_read_rsp_out.ready.poke(false.B); d.clock.step()
    d.io.full_kv_payload_read_rsp_out.bits.data.expect(expected.U)
    d.io.full_kv_payload_read_rsp_out.ready.poke(true.B); d.clock.step(); d.io.full_kv_payload_read_rsp_out.ready.poke(false.B)
  }

  private def retire(d: FullKVMeasurementDut, id: Int = 1): Unit = {
    d.io.runtime_retire_req.bits.session_id.poke(false.B)
    d.io.runtime_retire_req.bits.transaction_identity.request_id.poke(id.U)
    d.io.runtime_retire_req.bits.transaction_identity.incarnation.poke(1.U)
    d.io.runtime_retire_req.valid.poke(true.B); d.io.runtime_retire_req.ready.expect(true.B)
    d.clock.step(); d.io.runtime_retire_req.valid.poke(false.B)
  }

  private def awaitRetireAck(d: FullKVMeasurementDut): Unit = {
    var wait = 0
    while (!d.io.session_retire_ack.valid.peek().litToBoolean && wait < 24) {
      d.clock.step(); wait += 1
    }
    d.io.session_retire_ack.valid.expect(true.B)
  }

  it("reaches READY only after a matching full read, then retires after four commits") {
    simulate(new FullKVMeasurementDut(p)) { d =>
      init(d); d.io.external_core_mem_if_v1.request.ready.poke(false.B); work(d)
      d.clock.step(8)
      d.io.external_core_mem_if_v1.request.valid.expect(true.B)
      d.io.external_core_mem_if_v1.request.bits.request_kind.expect(p.coreMemoryReadRequestCode.U)
      d.io.external_core_mem_if_v1.request.bits.expected_fragment_count.expect(1.U)
      d.io.external_core_mem_if_v1.request.ready.poke(true.B); d.clock.step()
      response(d, id = 1); awaitSourceReady(d)
      readPayload(d)
      (0 until 3).foreach(commit(d, _))
      d.io.attention_terminal_rsp.ready.poke(false.B)
      commit(d, 3); d.clock.step()
      d.io.attention_terminal_rsp.valid.expect(true.B)
      d.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(1.U)
      d.io.attention_terminal_rsp.ready.poke(true.B); d.clock.step()
      retire(d)
      // The retire acknowledgement cannot collapse into the immediate
      // runtime-retire handshake: real R1/R2/S2 drain facts cross after it.
      d.io.session_retire_ack.valid.expect(false.B)
      awaitRetireAck(d)
      d.io.session_retire_ack.bits.transaction_identity.request_id.expect(1.U)
      d.io.session_retire_ack.ready.poke(true.B); d.clock.step()
    }
  }

  it("fails closed for a stale response and a duplicate consumer") {
    simulate(new FullKVMeasurementDut(p)) { d =>
      init(d); d.io.external_core_mem_if_v1.request.ready.poke(false.B); work(d); d.clock.step(8)
      d.io.external_core_mem_if_v1.request.valid.expect(true.B)
      d.io.external_core_mem_if_v1.request.ready.poke(true.B); d.clock.step()
      response(d, id = 2) // R1 consumes it as stale; it cannot reach S2.
      d.clock.step(3); d.io.source_ready_out.valid.expect(false.B)
      response(d, id = 1); awaitSourceReady(d)
      val staleRead = d.io.full_kv_payload_read_req_in.bits
      staleRead.transaction_identity.request_id.poke(2.U); staleRead.transaction_identity.incarnation.poke(1.U)
      staleRead.s2_slot.poke(0.U); staleRead.source_generation.poke(1.U); staleRead.fragment_index.poke(0.U)
      d.io.full_kv_payload_read_req_in.valid.poke(true.B); d.io.full_kv_payload_read_req_in.ready.expect(false.B)
      d.io.full_kv_payload_read_req_in.valid.poke(false.B)
      commit(d, 0)
      d.io.full_kv_consumer_commit_in.bits.transaction_identity.request_id.poke(1.U)
      d.io.full_kv_consumer_commit_in.bits.transaction_identity.incarnation.poke(1.U)
      d.io.full_kv_consumer_commit_in.bits.source_instance.s2_slot.poke(0.U)
      d.io.full_kv_consumer_commit_in.bits.source_instance.source_generation.poke(1.U)
      d.io.full_kv_consumer_commit_in.bits.consumer_id.poke(0.U)
      d.io.full_kv_consumer_commit_in.valid.poke(true.B)
      d.io.full_kv_consumer_commit_in.ready.expect(false.B)
      d.clock.step(); d.io.full_kv_consumer_commit_in.valid.poke(false.B)
      d.io.attention_terminal_rsp.valid.expect(false.B)
    }
  }

  it("forwards one matching memory fault to terminal/retire without READY or release") {
    simulate(new FullKVMeasurementDut(p)) { d =>
      init(d); d.io.external_core_mem_if_v1.request.ready.poke(false.B); work(d); d.clock.step(8)
      d.io.external_core_mem_if_v1.request.valid.expect(true.B)
      d.io.external_core_mem_if_v1.request.ready.poke(true.B); d.clock.step()
      d.io.attention_terminal_rsp.ready.poke(false.B)
      response(d, id = 1, status = p.coreMemoryFaultStatusCode)
      var terminalWait = 0
      while (!d.io.attention_terminal_rsp.valid.peek().litToBoolean && terminalWait < 16) {
        d.clock.step(); terminalWait += 1
      }
      d.io.source_ready_out.valid.expect(false.B)
      d.io.full_kv_consumer_commit_in.valid.poke(true.B)
      d.io.full_kv_consumer_commit_in.ready.expect(false.B)
      d.io.full_kv_consumer_commit_in.valid.poke(false.B)
      d.io.attention_terminal_rsp.valid.expect(true.B)
      d.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(1.U)
      d.io.attention_terminal_rsp.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
      d.io.attention_terminal_rsp.ready.poke(true.B); d.clock.step()
      retire(d)
      d.io.session_retire_ack.valid.expect(false.B)
      awaitRetireAck(d)
      d.io.session_retire_ack.ready.poke(true.B); d.clock.step()
    }
  }

  it("rejects work after reset until a fresh R1 init fact reaches the lifecycle") {
    simulate(new FullKVMeasurementDut(p)) { d =>
      init(d); d.io.full_kv_read_work_in.bits.expected_fragment_count.poke(1.U)
      d.io.full_kv_read_work_in.ready.expect(true.B)
      d.reset.poke(true.B); d.clock.step(); d.reset.poke(false.B)
      d.io.full_kv_read_work_in.bits.expected_fragment_count.poke(1.U)
      d.io.full_kv_read_work_in.valid.poke(true.B)
      d.io.full_kv_read_work_in.ready.expect(false.B)
      d.io.full_kv_read_work_in.valid.poke(false.B)
      // An old reply is stale at the reset R1 boundary and cannot reopen S2.
      d.io.external_core_mem_if_v1.response.valid.poke(true.B)
      d.io.external_core_mem_if_v1.response.ready.expect(true.B)
      d.clock.step(); d.io.external_core_mem_if_v1.response.valid.poke(false.B)
      init(d); d.io.full_kv_read_work_in.bits.expected_fragment_count.poke(1.U)
      d.io.full_kv_read_work_in.ready.expect(true.B)
    }
  }

  it("retains real drain facts when runtime retire arrives after drain collection") {
    simulate(new FullKVMeasurementDut(p)) { d =>
      init(d); d.io.external_core_mem_if_v1.request.ready.poke(false.B); work(d)
      d.clock.step(8); d.io.external_core_mem_if_v1.request.valid.expect(true.B)
      d.io.external_core_mem_if_v1.request.ready.poke(true.B); d.clock.step()
      response(d, id = 1); awaitSourceReady(d)
      (0 until 3).foreach(commit(d, _))
      d.io.attention_terminal_rsp.ready.poke(false.B)
      commit(d, 3); d.clock.step(); d.io.attention_terminal_rsp.valid.expect(true.B)
      d.io.attention_terminal_rsp.ready.poke(true.B); d.clock.step()
      // Let collector/lifecycle accept its four actual drain facts while the
      // environment deliberately withholds runtime-retire.
      d.clock.step(16)
      d.io.session_retire_ack.valid.expect(false.B)
      retire(d)
      d.io.session_retire_ack.valid.expect(true.B)
      d.io.session_retire_ack.ready.poke(true.B); d.clock.step()
    }
  }
}
