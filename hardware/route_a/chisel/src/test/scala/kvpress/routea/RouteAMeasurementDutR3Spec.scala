package kvpress.routea

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.interfaces.RouteASourceKind
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.RouteAMeasurementDut
import org.scalatest.funspec.AnyFunSpec

/**
  * W0-R3 same-instance Route-A closure witness.
  *
  * The three replaceable outer environments remain explicit: functional core
  * memory, functional source partials, and the functional R4 result boundary.
  * In particular, this test never provides publication, R6 authority, S2
  * lease, source-release, terminal, reclaim, or drain facts.
  */
final class RouteAMeasurementDutR3Spec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3,
    coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 32,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 2,
    transactionGroupTagWidth = 2, p3StageGenerationWidth = 2, r5AllocatorEntries = 8,
    r5StreamSlots = 8, sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def inactive(d: RouteAMeasurementDut): Unit = {
    d.io.frontend_lifecycle_req.valid.poke(false.B)
    d.io.runtime_retire_req.valid.poke(false.B)
    d.io.source_plan_declaration_in.valid.poke(false.B)
    d.io.pending_source_descriptor_registration_in.valid.poke(false.B)
    d.io.hot_payload_fragment_in.valid.poke(false.B)
    d.io.hot_position_sidecar_in.valid.poke(false.B)
    d.io.pending_payload_read_binding_in.valid.poke(false.B)
    d.io.functional_partial_hot_offer_in.valid.poke(false.B)
    d.io.functional_partial_pending_offer_in.valid.poke(false.B)
    d.io.functional_partial_packed_offer_in.valid.poke(false.B)
    d.io.functional_partial_hot_fragment_in.valid.poke(false.B)
    d.io.functional_partial_pending_fragment_in.valid.poke(false.B)
    d.io.functional_partial_packed_fragment_in.valid.poke(false.B)
    d.io.functional_r4_result_in.valid.poke(false.B)
    d.io.functional_r4_numeric_fault_in.valid.poke(false.B)
    d.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)
    d.io.external_core_mem_if_v1.request.ready.poke(false.B)
    d.io.external_core_mem_if_v1.response.valid.poke(false.B)
    d.io.functional_r4_accepted_packet_out.ready.poke(true.B)
    d.io.functional_r4_merge_work_out.ready.poke(false.B)
    d.io.functional_direct_pending_payload_fragment_out.ready.poke(true.B)
    d.io.attention_terminal_rsp.ready.poke(false.B)
    d.io.session_retire_ack.ready.poke(true.B)
  }

  private def await(max: Int, message: String)(predicate: => Boolean)(step: => Unit): Unit = {
    var waited = 0
    while (!predicate && waited < max) { step; waited += 1 }
    require(waited < max, message)
  }

  private def initialize(d: RouteAMeasurementDut): Unit = {
    inactive(d)
    d.clock.step()
    d.io.external_core_mem_if_v1.init_ack.bits.adapter_epoch_ready.poke(true.B)
    d.io.external_core_mem_if_v1.init_ack.valid.poke(true.B)
    await(64, "timed out waiting for R1 init acknowledgement")(
      d.io.external_core_mem_if_v1.init_ack.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.external_core_mem_if_v1.init_ack.valid.poke(false.B)

    // The production collector, not the fixture, delivers R1/M2/R5 init
    // facts into R6.  Ready is request-dependent, so present the legal
    // session-start payload while waiting; its valid remains low.
    val f = d.io.frontend_lifecycle_req.bits
    f.event_kind.poke(p.r6.sessionStartEventCode.U); f.session_id.poke(false.B)
    f.context_tokens.poke(32768.U)
    f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U)
    f.payload_ref.poke(0.U); f.disposition.poke(false.B)
    f.transaction_identity.request_id.poke(0.U); f.transaction_identity.incarnation.poke(0.U)
    f.admission_group_tag.poke(0.U); f.admission_member_ordinal.poke(0.U)
    f.admission_group_valid_records.poke(0.U)
    await(128, "timed out waiting for production R6 initialization")(
      d.io.frontend_lifecycle_req.ready.peek().litToBoolean,
    )(d.clock.step())
    lifecycle(d, p.r6.sessionStartEventCode, requestId = 0, retain = false)
  }

  private def lifecycle(
    d: RouteAMeasurementDut,
    event: Int,
    requestId: Int,
    retain: Boolean,
    payloadRef: Int = 0,
    groupTag: Int = 0,
    ordinal: Int = 0,
    validRecords: Int = 0,
  ): Unit = {
    val f = d.io.frontend_lifecycle_req.bits
    f.event_kind.poke(event.U); f.session_id.poke(false.B)
    f.context_tokens.poke((if (event == p.r6.sessionStartEventCode) 32768 else 0).U)
    f.entry_id.poke(0.U); f.layer.poke(0.U); f.kv_head.poke(0.U); f.logical_position.poke(0.U)
    f.payload_ref.poke(payloadRef.U); f.disposition.poke(retain.B)
    f.transaction_identity.request_id.poke(requestId.U); f.transaction_identity.incarnation.poke(0.U)
    f.admission_group_tag.poke(groupTag.U); f.admission_member_ordinal.poke(ordinal.U)
    f.admission_group_valid_records.poke(validRecords.U)
    d.io.frontend_lifecycle_req.valid.poke(true.B)
    await(64, s"timed out waiting for lifecycle event $event")(
      d.io.frontend_lifecycle_req.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.frontend_lifecycle_req.valid.poke(false.B)
  }

  private def declarePackedPlan(d: RouteAMeasurementDut): Unit = {
    val plan = d.io.source_plan_declaration_in.bits
    plan.transaction_identity.request_id.poke(3.U); plan.transaction_identity.incarnation.poke(0.U)
    plan.source_presence.poke(4.U)
    plan.hot_instance.source_kind.poke(RouteASourceKind.Hot.U)
    plan.hot_instance.instance_coordinate.poke(0.U); plan.hot_instance.generation.poke(0.U)
    plan.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
    plan.pending_instance.instance_coordinate.poke(0.U); plan.pending_instance.generation.poke(0.U)
    plan.packed_instance.source_kind.poke(RouteASourceKind.Packed.U)
    plan.packed_instance.instance_coordinate.poke(1.U); plan.packed_instance.generation.poke(1.U)
    d.io.source_plan_declaration_in.valid.poke(true.B)
    await(64, "timed out waiting for named packed source-plan declaration")(
      d.io.source_plan_declaration_in.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.source_plan_declaration_in.valid.poke(false.B)
  }

  private def declareHotPlan(d: RouteAMeasurementDut): Unit = {
    val plan = d.io.source_plan_declaration_in.bits
    plan.transaction_identity.request_id.poke(3.U); plan.transaction_identity.incarnation.poke(0.U)
    plan.source_presence.poke(1.U)
    plan.hot_instance.source_kind.poke(RouteASourceKind.Hot.U)
    plan.hot_instance.instance_coordinate.poke(0.U); plan.hot_instance.generation.poke(1.U)
    plan.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
    plan.pending_instance.instance_coordinate.poke(0.U); plan.pending_instance.generation.poke(0.U)
    plan.packed_instance.source_kind.poke(RouteASourceKind.Packed.U)
    plan.packed_instance.instance_coordinate.poke(0.U); plan.packed_instance.generation.poke(0.U)
    d.io.source_plan_declaration_in.valid.poke(true.B)
    await(64, "timed out waiting for named hot source-plan declaration")(
      d.io.source_plan_declaration_in.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.source_plan_declaration_in.valid.poke(false.B)
  }

  /**
    * Immutable facts from the named pending-payload/location owner.  This is
    * deliberately a descriptor registration rather than an authority or a
    * testbench-created direct read: the production binder must still query,
    * match, and wait for R6's accepted source plan.
    */
  private def registerDirectPendingDescriptor(d: RouteAMeasurementDut): Unit = {
    val registration = d.io.pending_source_descriptor_registration_in.bits
    registration.transaction_identity.request_id.poke(3.U); registration.transaction_identity.incarnation.poke(0.U)
    registration.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
    registration.pending_instance.instance_coordinate.poke(0.U); registration.pending_instance.generation.poke(1.U)
    registration.key.pending_descriptor_ref.poke(1.U); registration.key.pending_descriptor_generation.poke(1.U)
    registration.entry_id.poke(0.U); registration.layer.poke(0.U); registration.kv_head.poke(0.U)
    registration.logical_position.poke(0.U); registration.payload_ref.poke(55.U)
    registration.transaction_group_tag.poke(1.U); registration.group_member_ordinal.poke(0.U)
    registration.group_valid_records.poke(1.U)
    registration.payload_handle_or_address.poke(55.U); registration.pending_storage_generation.poke(1.U)
    registration.destination_endpoint.poke(0.U); registration.pending_ordinal.poke(0.U)
    registration.source_last.poke(true.B); registration.valid_count.poke(1.U)
    d.io.pending_source_descriptor_registration_in.valid.poke(true.B)
    await(64, "timed out waiting for immutable direct-pending descriptor registration")(
      d.io.pending_source_descriptor_registration_in.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.pending_source_descriptor_registration_in.valid.poke(false.B)
  }

  private def declarePendingPlan(d: RouteAMeasurementDut): Unit = {
    val plan = d.io.source_plan_declaration_in.bits
    plan.transaction_identity.request_id.poke(3.U); plan.transaction_identity.incarnation.poke(0.U)
    plan.source_presence.poke(2.U)
    plan.hot_instance.source_kind.poke(RouteASourceKind.Hot.U)
    plan.hot_instance.instance_coordinate.poke(0.U); plan.hot_instance.generation.poke(0.U)
    plan.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
    plan.pending_instance.instance_coordinate.poke(0.U); plan.pending_instance.generation.poke(1.U)
    plan.packed_instance.source_kind.poke(RouteASourceKind.Packed.U)
    plan.packed_instance.instance_coordinate.poke(0.U); plan.packed_instance.generation.poke(0.U)
    plan.pending_descriptor_key.pending_descriptor_ref.poke(1.U)
    plan.pending_descriptor_key.pending_descriptor_generation.poke(1.U)
    d.io.source_plan_declaration_in.valid.poke(true.B)
    await(64, "timed out waiting for named pending source-plan declaration")(
      d.io.source_plan_declaration_in.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.source_plan_declaration_in.valid.poke(false.B)
  }

  private def bindAndMature(d: RouteAMeasurementDut): Unit = {
    lifecycle(d, p.r6.maturityDispositionEventCode, requestId = 0, retain = true,
      payloadRef = 55, groupTag = 1, ordinal = 0, validRecords = 1)
    val b = d.io.pending_payload_read_binding_in.bits
    b.transaction_identity.request_id.poke(3.U); b.transaction_identity.incarnation.poke(0.U)
    b.entry_id.poke(0.U); b.layer.poke(0.U); b.kv_head.poke(0.U); b.logical_position.poke(0.U)
    b.payload_ref.poke(55.U); b.transaction_group_tag.poke(1.U)
    b.group_member_ordinal.poke(0.U); b.group_valid_records.poke(1.U)
    b.payload_handle_or_address.poke(55.U); b.source_generation.poke(1.U); b.destination_endpoint.poke(0.U)
    d.io.pending_payload_read_binding_in.valid.poke(true.B)
    await(64, "timed out waiting for the source-owned pending payload binding")(
      d.io.pending_payload_read_binding_in.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.pending_payload_read_binding_in.valid.poke(false.B)
  }

  private def waitRequest(d: RouteAMeasurementDut, kind: Int, index: Int): (Int, Int) = {
    await(128, s"timed out waiting for request kind=$kind index=$index")(
      d.io.external_core_mem_if_v1.request.valid.peek().litToBoolean,
    )(d.clock.step())
    d.io.external_core_mem_if_v1.request.bits.request_kind.expect(kind.U)
    d.io.external_core_mem_if_v1.request.bits.fragment_index.expect(index.U)
    val id = d.io.external_core_mem_if_v1.request.bits.transaction_identity.request_id.peek().litValue.toInt
    val incarnation = d.io.external_core_mem_if_v1.request.bits.transaction_identity.incarnation.peek().litValue.toInt
    d.io.external_core_mem_if_v1.request.ready.poke(true.B); d.clock.step()
    d.io.external_core_mem_if_v1.request.ready.poke(false.B)
    (id, incarnation)
  }

  private def response(d: RouteAMeasurementDut, id: Int, index: Int, last: Boolean, fault: Boolean = false, incarnation: Int = 0): Unit = {
    val r = d.io.external_core_mem_if_v1.response.bits
    r.transaction_identity.request_id.poke(id.U); r.transaction_identity.incarnation.poke(incarnation.U)
    r.fragment_index.poke(index.U); r.last.poke(last.B)
    r.status.poke((if (fault) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode).U)
    r.data.poke((0x100 + index).U)
    d.io.external_core_mem_if_v1.response.valid.poke(true.B)
    await(64, "timed out waiting for functional-memory response acceptance")(
      d.io.external_core_mem_if_v1.response.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.external_core_mem_if_v1.response.valid.poke(false.B); d.clock.step(2)
  }

  private def materializeAndPublish(d: RouteAMeasurementDut): Unit = {
    val (pendingId, pendingIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
    (0 until 8).foreach(index => response(d, pendingId, index, index == 7, incarnation = pendingIncarnation))
    val (writeId, writeIncarnation) = waitRequest(d, p.coreMemoryWriteRequestCode, 0)
    (0 until 8).foreach(index => waitRequest(d, p.coreMemoryWriteDataCode, index))
    response(d, writeId, 0, last = true, incarnation = writeIncarnation)
    waitRequest(d, p.coreMemoryWriteRequestCode, 0)
    val (descriptorId, descriptorIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
    response(d, descriptorId, 0, last = true, incarnation = descriptorIncarnation)
  }

  /**
    * Stops after R1 accepted the descriptor data beat but before the matching
    * functional response.  R3 has all prior durability facts, while its
    * pending->packed transition remains unavailable.  This gives the real
    * direct candidate a legal pre-issue interval without fabricating a
    * transition or stalling any R3/R6 authority handshake.
    */
  private def materializeThroughDescriptorWrite(d: RouteAMeasurementDut): (Int, Int) = {
    val (pendingId, pendingIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
    (0 until 8).foreach(index => response(d, pendingId, index, index == 7, incarnation = pendingIncarnation))
    val (writeId, writeIncarnation) = waitRequest(d, p.coreMemoryWriteRequestCode, 0)
    (0 until 8).foreach(index => waitRequest(d, p.coreMemoryWriteDataCode, index))
    response(d, writeId, 0, last = true, incarnation = writeIncarnation)
    waitRequest(d, p.coreMemoryWriteRequestCode, 0)
    waitRequest(d, p.coreMemoryWriteDataCode, 0)
  }

  private def sendPackedPartial(d: RouteAMeasurementDut, consumer: Int): Unit = {
    val offer = d.io.functional_partial_packed_offer_in.bits
    offer.transaction_identity.request_id.poke(3.U); offer.transaction_identity.incarnation.poke(0.U)
    offer.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
    offer.source_instance.instance_coordinate.poke(1.U); offer.source_instance.generation.poke(1.U)
    offer.consumer_id.poke(consumer.U)
    offer.r4_header.poke(((BigInt(RouteASourceKind.Packed) << 64) | (BigInt(consumer) << 66) |
      (BigInt(1) << 69) | (BigInt(8) << 70)).U)
    offer.partial_present.poke(true.B)
    d.io.functional_partial_packed_offer_in.valid.poke(true.B)
    await(64, s"timed out waiting for packed partial offer $consumer")(
      d.io.functional_partial_packed_offer_in.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.functional_partial_packed_offer_in.valid.poke(false.B); d.clock.step()
    (0 until 8).foreach { index =>
      val fragment = d.io.functional_partial_packed_fragment_in.bits
      fragment.transaction_identity.request_id.poke(3.U); fragment.transaction_identity.incarnation.poke(0.U)
      fragment.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
      fragment.source_instance.instance_coordinate.poke(1.U); fragment.source_instance.generation.poke(1.U)
      fragment.consumer_id.poke(consumer.U); fragment.fragment_index.poke(index.U)
      fragment.last.poke((index == 7).B); fragment.data.poke((0x300 + consumer * 8 + index).U)
      d.io.functional_partial_packed_fragment_in.valid.poke(true.B)
      await(64, s"timed out waiting for packed partial fragment $consumer/$index")(
        d.io.functional_partial_packed_fragment_in.ready.peek().litToBoolean,
      )(d.clock.step())
      d.clock.step(); d.io.functional_partial_packed_fragment_in.valid.poke(false.B)
    }
  }

  private def sendHotPartial(d: RouteAMeasurementDut, consumer: Int): Unit = {
    val offer = d.io.functional_partial_hot_offer_in.bits
    offer.transaction_identity.request_id.poke(3.U); offer.transaction_identity.incarnation.poke(0.U)
    offer.source_instance.source_kind.poke(RouteASourceKind.Hot.U)
    offer.source_instance.instance_coordinate.poke(0.U); offer.source_instance.generation.poke(1.U)
    offer.consumer_id.poke(consumer.U)
    offer.r4_header.poke(((BigInt(RouteASourceKind.Hot) << 64) | (BigInt(consumer) << 66) |
      (BigInt(1) << 69) | (BigInt(8) << 70)).U)
    offer.partial_present.poke(true.B)
    d.io.functional_partial_hot_offer_in.valid.poke(true.B)
    await(64, s"timed out waiting for hot partial offer $consumer")(
      d.io.functional_partial_hot_offer_in.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.functional_partial_hot_offer_in.valid.poke(false.B); d.clock.step()
    (0 until 8).foreach { index =>
      val fragment = d.io.functional_partial_hot_fragment_in.bits
      fragment.transaction_identity.request_id.poke(3.U); fragment.transaction_identity.incarnation.poke(0.U)
      fragment.source_instance.source_kind.poke(RouteASourceKind.Hot.U)
      fragment.source_instance.instance_coordinate.poke(0.U); fragment.source_instance.generation.poke(1.U)
      fragment.consumer_id.poke(consumer.U); fragment.fragment_index.poke(index.U)
      fragment.last.poke((index == 7).B); fragment.data.poke((0x200 + consumer * 8 + index).U)
      d.io.functional_partial_hot_fragment_in.valid.poke(true.B)
      await(64, s"timed out waiting for hot partial fragment $consumer/$index")(
        d.io.functional_partial_hot_fragment_in.ready.peek().litToBoolean,
      )(d.clock.step())
      d.clock.step(); d.io.functional_partial_hot_fragment_in.valid.poke(false.B)
    }
  }

  private def returnR4Results(d: RouteAMeasurementDut): Unit = {
    (0 until 4).foreach { consumer =>
      await(64, s"timed out waiting for R4 work $consumer")(
        d.io.functional_r4_merge_work_out.valid.peek().litToBoolean,
      )(d.clock.step())
      d.io.functional_r4_merge_work_out.bits.transaction_identity.request_id.expect(3.U)
      d.io.functional_r4_merge_work_out.bits.consumer_id.expect(consumer.U)
      d.io.functional_r4_merge_work_out.ready.poke(true.B); d.clock.step()
      d.io.functional_r4_merge_work_out.ready.poke(false.B)
      val result = d.io.functional_r4_result_in.bits
      result.transaction_identity.request_id.poke(3.U); result.transaction_identity.incarnation.poke(0.U)
      result.consumer_id.poke(consumer.U); result.normalized_value.poke((0x400 + consumer).U)
      d.io.functional_r4_result_in.valid.poke(true.B)
      await(64, s"timed out waiting for R4 result acceptance $consumer")(
        d.io.functional_r4_result_in.ready.peek().litToBoolean,
      )(d.clock.step())
      d.clock.step(); d.io.functional_r4_result_in.valid.poke(false.B)
    }
  }

  private def retire(d: RouteAMeasurementDut): Unit = {
    val r = d.io.runtime_retire_req.bits
    r.session_id.poke(false.B); r.transaction_identity.request_id.poke(3.U); r.transaction_identity.incarnation.poke(0.U)
    d.io.runtime_retire_req.valid.poke(true.B)
    await(64, "timed out waiting for runtime retirement acceptance")(
      d.io.runtime_retire_req.ready.peek().litToBoolean,
    )(d.clock.step())
    d.clock.step(); d.io.runtime_retire_req.valid.poke(false.B)
  }

  private def prepareThroughPublication(d: RouteAMeasurementDut): Unit = {
    initialize(d)
    lifecycle(d, p.r6.attentionServiceEventCode, requestId = 3, retain = false)
    declarePackedPlan(d)
    bindAndMature(d)
    materializeAndPublish(d)
  }

  it("closes one production R3/R5/R6 packed path through source terminal and reclaim") {
    simulate(new RouteAMeasurementDut(p)) { d =>
      prepareThroughPublication(d)
      val (payloadId, payloadIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      (0 until 8).foreach(index => response(d, payloadId, index, index == 7, incarnation = payloadIncarnation))
      val (sidecarId, sidecarIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      response(d, sidecarId, 0, last = true, incarnation = sidecarIncarnation)
      (0 until 4).foreach(sendPackedPartial(d, _))
      returnR4Results(d)
      await(64, "timed out waiting for the unique R6 terminal")(
        d.io.attention_terminal_rsp.valid.peek().litToBoolean,
      )(d.clock.step())
      d.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(3.U)
      d.io.attention_terminal_rsp.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U)
      d.io.attention_terminal_rsp.ready.poke(true.B); d.clock.step(); d.io.attention_terminal_rsp.ready.poke(false.B)
      retire(d)
      waitRequest(d, p.coreMemoryWriteRequestCode, 0)
      val (reclaimId, reclaimIncarnation) = waitRequest(d, p.coreMemoryWriteDataCode, 0)
      response(d, reclaimId, 0, last = true, incarnation = reclaimIncarnation)
      await(128, "timed out waiting for R6 retire acknowledgement after R5 reclaim")(
        d.io.session_retire_ack.valid.peek().litToBoolean,
      )(d.clock.step())
      d.io.session_retire_ack.bits.transaction_identity.request_id.expect(3.U)
    }
  }

  it("opens hot only through the accepted plan and reaches the shared terminal after four commits") {
    simulate(new RouteAMeasurementDut(p)) { d =>
      initialize(d)
      lifecycle(d, p.r6.attentionServiceEventCode, requestId = 3, retain = false)
      declareHotPlan(d)
      (0 until 4).foreach(sendHotPartial(d, _))
      returnR4Results(d)
      await(64, "timed out waiting for the hot-source R6 terminal")(
        d.io.attention_terminal_rsp.valid.peek().litToBoolean,
      )(d.clock.step())
      d.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(3.U)
      d.io.attention_terminal_rsp.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U)
    }
  }

  it("fails closed when a stale first packed-read response arrives after publication") {
    simulate(new RouteAMeasurementDut(p)) { d =>
      prepareThroughPublication(d)
      val (payloadId, payloadIncarnation) = waitRequest(d, p.coreMemoryReadRequestCode, 0)
      response(d, payloadId + 1, 0, last = false, incarnation = payloadIncarnation)
      d.clock.step(12)
      d.io.attention_terminal_rsp.valid.expect(false.B)
      d.io.functional_r4_accepted_packet_out.valid.expect(false.B)
      d.io.functional_r4_merge_work_out.valid.expect(false.B)
      d.io.external_core_mem_if_v1.request.valid.expect(false.B)
    }
  }

  it("cancels a pre-issue direct candidate on the real accepted packed transition and lets R6 fault-terminal it") {
    simulate(new RouteAMeasurementDut(p)) { d =>
      initialize(d)
      lifecycle(d, p.r6.attentionServiceEventCode, requestId = 3, retain = false)
      registerDirectPendingDescriptor(d)
      bindAndMature(d)

      // R2/R1 has accepted all packing traffic through the descriptor write,
      // but its completion response is intentionally delayed.  A subsequent
      // legal pending plan therefore reaches the real R2 direct-class slot
      // before R3 can produce the accepted pending->packed transition.
      val (descriptorId, descriptorIncarnation) = materializeThroughDescriptorWrite(d)
      declarePendingPlan(d)
      await(128, "timed out waiting for the pre-issue direct R1 request")(
        d.io.external_core_mem_if_v1.request.valid.peek().litToBoolean,
      )(d.clock.step())
      d.io.external_core_mem_if_v1.request.bits.request_kind.expect(p.coreMemoryReadRequestCode.U)
      // Do not accept that direct request: it must remain a stored candidate
      // until the true R3/R6 transition withdraws eligibility.
      d.io.external_core_mem_if_v1.request.ready.poke(false.B)
      response(d, descriptorId, 0, last = true, incarnation = descriptorIncarnation)

      await(64, "timed out waiting for exact R2 pre-issue candidate cancellation")(
        !d.io.external_core_mem_if_v1.request.valid.peek().litToBoolean,
      )(d.clock.step())

      await(128, "timed out waiting for R6-owned direct-pending association fault terminal")(
        d.io.attention_terminal_rsp.valid.peek().litToBoolean,
      )(d.clock.step())
      d.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(3.U)
      d.io.attention_terminal_rsp.bits.terminal_status.expect(p.coreMemoryFaultStatusCode.U)
      d.io.functional_direct_pending_payload_fragment_out.valid.expect(false.B)
      d.io.functional_r4_accepted_packet_out.valid.expect(false.B)
      d.io.attention_terminal_rsp.ready.poke(true.B); d.clock.step(); d.io.attention_terminal_rsp.ready.poke(false.B)
      d.clock.step(4)
      d.io.external_core_mem_if_v1.request.valid.expect(false.B)
    }
  }
}
