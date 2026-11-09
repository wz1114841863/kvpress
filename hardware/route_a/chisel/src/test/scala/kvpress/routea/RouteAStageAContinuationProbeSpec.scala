package kvpress.routea

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.DecoupledIO
import chisel3.util.experimental.BoringUtils
import kvpress.routea.interfaces.RouteASourceKind
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.rtl3.{RouteAFunctionalMemoryEnvironment, RouteAFunctionalMemoryStore}
import org.scalatest.funspec.AnyFunSpec

/** Read-only observation around the unchanged complete production DUT harness. */
final class RouteAStageAContinuationProbeHarness(p: RouteASkeletonParameters) extends Module {
  val original = Module(new RouteAMeasurementDutR3Harness(p))
  val io = IO(chiselTypeOf(original.io))
  io <> original.io
  private val dut = original.dut
  private def tap[T <: Data](x: T): T = BoringUtils.tapAndRead(x)
  private def fire[T <: Data](x: DecoupledIO[T]): Bool = tap(x.valid) && tap(x.ready)
  val observation = IO(Output(new Bundle {
    val r6_state = UInt(3.W)
    val r6_control_pending = Bool()
    val r6_attention_live = Bool()
    val admission_state = UInt(3.W)
    val r6_context_valid = Bool()
    val r6_context_ready = Bool()
    val r6_authority_valid = Bool()
    val admission_join_fire = Bool()
    val r3_admission_fire = Bool()
    val publication_fire = Bool()
    val publication_status = UInt(2.W)
    val member_fire = Bool()
    val page_ready_fire = Bool()
    val page_id = UInt(18.W)
    val page_generation = UInt(8.W)
    val journal_ordinal0_present = Bool()
    val binder_have_plan = Bool()
    val binder_have_page_ready = Bool()
    val binder_have_member_stream = Bool()
    val descriptor_request_valid = Bool()
    val descriptor_grant_fire = Bool()
    val descriptor_payload_handle = UInt(p.coreMemoryAddressRefWidth.W)
    val descriptor_sidecar_handle = UInt(p.coreMemoryAddressRefWidth.W)
    val lease_request_valid = Bool()
    val s2_slot_state = UInt(3.W)
    val s2_slot_generation = UInt(p.sourceGenerationWidth.W)
    val s2_slot_page_id = UInt(18.W)
    val s2_slot_page_generation = UInt(8.W)
    val s2_release_fire = Bool()
    val consumer_commit_fire = Bool()
    val payload_fragment_fire = Bool()
    val payload_fragment_index = UInt(9.W)
    val payload_fragment_data = UInt(512.W)
    val sidecar_fragment_fire = Bool()
    val sidecar_fragment_data = UInt(64.W)
    val materialized_sidecar_fire = Bool()
    val materialized_position = UInt(15.W)
    val metadata_handoff = Bool()
    val metadata_group0_active = Bool()
    val metadata_local_credit0 = UInt(6.W)
    val page0_readable = Bool()
    val descriptor_line0_allocated = Bool()
  }))
  observation.r6_state := tap(dut.lifecycle.state)
  observation.r6_control_pending := tap(dut.lifecycle.controlPending)
  observation.r6_attention_live := tap(dut.lifecycle.attentionValid).asUInt.orR
  observation.admission_state := tap(dut.admission.state)
  observation.r6_context_valid := tap(dut.admission.io.r6_admission_context_in.valid)
  observation.r6_context_ready := tap(dut.admission.io.r6_admission_context_in.ready)
  observation.r6_authority_valid := tap(dut.admission.io.r6_authority_in.valid)
  observation.admission_join_fire := fire(dut.admission.io.r6_admission_context_in)
  observation.r3_admission_fire := fire(dut.admission.io.r3_admission_context_out)
  observation.publication_fire := fire(dut.m2P3.io.m2_publish_ack)
  observation.publication_status := tap(dut.m2P3.io.m2_publish_ack.bits.status)
  observation.member_fire := fire(dut.m2P3.io.publication_member_observation)
  observation.page_ready_fire := fire(dut.m2P3.io.post_r6_packed_page_ready_observation)
  observation.page_id := tap(dut.m2P3.io.post_r6_packed_page_ready_observation.bits.page_ref.page_id)
  observation.page_generation := tap(dut.m2P3.io.post_r6_packed_page_ready_observation.bits.page_ref.generation)
  observation.journal_ordinal0_present := tap(dut.m2P3.reconciliationPresent(0))
  observation.binder_have_plan := tap(dut.activationBinder.havePlan)
  observation.binder_have_page_ready := tap(dut.activationBinder.havePageReady)
  observation.binder_have_member_stream := tap(dut.activationBinder.haveMemberStream)
  observation.descriptor_request_valid := tap(dut.activationBinder.io.descriptor_location_request_out.valid)
  observation.descriptor_grant_fire := fire(dut.pageManager.io.descriptor_location_grant_out)
  observation.descriptor_payload_handle := tap(dut.pageManager.io.descriptor_location_grant_out.bits.payload_handle_or_address)
  observation.descriptor_sidecar_handle := tap(dut.pageManager.io.descriptor_location_grant_out.bits.sidecar_handle_or_address)
  observation.lease_request_valid := tap(dut.activationBinder.io.s2_fill_lease_request_out.valid)
  observation.s2_slot_state := tap(dut.s2.slotState(1))
  observation.s2_slot_generation := tap(dut.s2.slotGeneration(1))
  observation.s2_slot_page_id := tap(dut.s2.slotPageRef(1).page_id)
  observation.s2_slot_page_generation := tap(dut.s2.slotPageRef(1).generation)
  observation.s2_release_fire := fire(dut.s2.io.s2_release_out)
  observation.consumer_commit_fire := fire(dut.s2.io.gqa_consumer_commit_in)
  observation.payload_fragment_fire := fire(dut.s2.io.s2_payload_fragment_in)
  observation.payload_fragment_index := tap(dut.s2.io.s2_payload_fragment_in.bits.fragment_index)
  observation.payload_fragment_data := tap(dut.s2.io.s2_payload_fragment_in.bits.data)
  observation.sidecar_fragment_fire := fire(dut.s2.io.s2_sidecar_fragment_in)
  observation.sidecar_fragment_data := tap(dut.s2.io.s2_sidecar_fragment_in.bits.data)
  observation.materialized_sidecar_fire := fire(dut.m2P3.io.p3_materialized_sidecar_out)
  observation.materialized_position := tap(dut.m2P3.io.p3_materialized_sidecar_out.bits.logical_position)
  observation.metadata_handoff := tap(dut.m2P3.io.metadata_membership_handoff_observation.valid)
  observation.metadata_group0_active := tap(dut.metadataAdmission.groupActive(0))
  observation.metadata_local_credit0 := tap(dut.metadataAdmission.localCredit(0))
  observation.page0_readable := tap(dut.pageManager.descriptorReadable.get(0))
  observation.descriptor_line0_allocated := tap(dut.pageManager.allocatedLine(0))
}

/** ScalaTest PASS qualifies a reproduced BLOCKED diagnostic, never capability PASS. */
final class RouteAStageAContinuationProbeSpec extends AnyFunSpec with ChiselSim {
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
    // stream8 = layer1/head0 must fit; no production parameter is changed.
    r5StreamSlots = 16, sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )
  private val ProbeCycles = 128
  private val PendingData = Vector.tabulate(8)(i => BigInt(0x100 + i))

  private final class Driver(val d: RouteAStageAContinuationProbeHarness) {
    val store = new RouteAFunctionalMemoryStore
    private val memory = new RouteAFunctionalMemoryEnvironment(p, store)
    // Initial pending-source fixture only; packed payload is never preloaded.
    store.preload(BigInt(55), None, PendingData, Vector.empty)
    var publications = 0; var handoffs = 0; var admissionJoins = 0; var r3Admissions = 0
    var consumers = 0; var releases = 0; var terminalCount = 0; var memoryFaults = 0
    var readRequests = 0; var payloadFragments = 0; var sidecarFragments = 0
    var materializedPosition: Option[BigInt] = None
    var pageId: Option[BigInt] = None; var pageGeneration: Option[BigInt] = None
    var payloadHandle: Option[BigInt] = None; var sidecarHandle: Option[BigInt] = None
    var descriptorGrants = 0
    def bool(x: Bool): Boolean = x.peek().litToBoolean
    def uint(x: UInt): BigInt = x.peek().litValue
    def bit(x: Bool): Int = if (bool(x)) 1 else 0
    def tick(): Unit = {
      memory.drive(d.io.external_core_mem_if_v1)
      val o = d.observation
      if (bool(o.publication_fire)) { assert(uint(o.publication_status) == 0); publications += 1 }
      if (bool(o.admission_join_fire)) admissionJoins += 1
      if (bool(o.r3_admission_fire)) r3Admissions += 1
      if (bool(o.page_ready_fire)) {
        handoffs += 1; pageId = Some(uint(o.page_id)); pageGeneration = Some(uint(o.page_generation))
      }
      if (bool(o.materialized_sidecar_fire)) materializedPosition = Some(uint(o.materialized_position))
      if (bool(o.descriptor_grant_fire)) {
        descriptorGrants += 1
        payloadHandle = Some(uint(o.descriptor_payload_handle)); sidecarHandle = Some(uint(o.descriptor_sidecar_handle))
        val pos = materializedPosition.getOrElse(fail("descriptor grant preceded actual R3 position binding"))
        // Explicit outer position-backing service, not a DUT HBM sidecar write.
        // The handle comes from R5 and the value from the accepted R3 binding.
        store.preload(sidecarHandle.get, None, Vector(pos), Vector(pos))
      }
      if (bool(o.consumer_commit_fire)) consumers += 1
      if (bool(o.s2_release_fire)) releases += 1
      if (bool(o.payload_fragment_fire)) {
        val index = uint(o.payload_fragment_index).toInt
        assert(index < PendingData.size && uint(o.payload_fragment_data) == PendingData(index), "packed payload data mismatch")
        payloadFragments += 1
      }
      if (bool(o.sidecar_fragment_fire)) {
        assert(materializedPosition.contains(uint(o.sidecar_fragment_data)), "actual R3 position versus sidecar mismatch")
        sidecarFragments += 1
      }
      val mem = d.io.external_core_mem_if_v1
      if (bool(mem.request.valid) && bool(mem.request.ready) && uint(mem.request.bits.request_kind) == p.coreMemoryReadRequestCode) readRequests += 1
      if (bool(mem.response.valid) && bool(mem.response.ready) && uint(mem.response.bits.status) != p.coreMemoryOkStatusCode) memoryFaults += 1
      if (bool(d.io.attention_terminal_rsp.valid) && bool(d.io.attention_terminal_rsp.ready)) {
        assert(uint(d.io.attention_terminal_rsp.bits.terminal_status) == p.coreMemoryOkStatusCode)
        terminalCount += 1
      }
      memory.observeAccepted(mem)
      d.clock.step()
    }
    def until(message: String, limit: Int = 512)(predicate: => Boolean): Unit = {
      var waited = 0
      while (!predicate && waited < limit) { tick(); waited += 1 }
      assert(predicate, s"$message after $waited clocks")
    }
    def idleInputs(): Unit = {
      d.io.frontend_lifecycle_req.valid.poke(false.B); d.io.runtime_retire_req.valid.poke(false.B)
      d.io.source_plan_declaration_in.valid.poke(false.B); d.io.pending_source_descriptor_registration_in.valid.poke(false.B)
      d.io.hot_payload_fragment_in.valid.poke(false.B); d.io.hot_position_sidecar_in.valid.poke(false.B)
      d.io.pending_payload_read_binding_in.valid.poke(false.B)
      d.io.functional_partial_hot_offer_in.valid.poke(false.B); d.io.functional_partial_pending_offer_in.valid.poke(false.B)
      d.io.functional_partial_packed_offer_in.valid.poke(false.B)
      d.io.functional_partial_hot_fragment_in.valid.poke(false.B); d.io.functional_partial_pending_fragment_in.valid.poke(false.B)
      d.io.functional_partial_packed_fragment_in.valid.poke(false.B)
      d.io.functional_r4_result_in.valid.poke(false.B); d.io.functional_r4_numeric_fault_in.valid.poke(false.B)
      d.io.functional_r4_accepted_packet_out.ready.poke(true.B); d.io.functional_r4_merge_work_out.ready.poke(false.B)
      d.io.functional_direct_pending_payload_fragment_out.ready.poke(true.B)
      d.io.attention_terminal_rsp.ready.poke(false.B); d.io.session_retire_ack.ready.poke(false.B)
    }
    def lifecycle(event: Int, rid: Int, layer: Int = 0, position: Int = 0,
                  retain: Boolean = false, payload: Int = 0, group: Int = 0): Unit = {
      val f = d.io.frontend_lifecycle_req.bits
      f.event_kind.poke(event.U); f.session_id.poke(false.B)
      f.context_tokens.poke((if (event == p.r6.sessionStartEventCode) 32768 else 0).U)
      f.entry_id.poke((position * 288 + layer * 8).U)
      f.layer.poke(layer.U); f.kv_head.poke(0.U); f.logical_position.poke(position.U)
      f.payload_ref.poke(payload.U); f.disposition.poke(retain.B)
      f.transaction_identity.request_id.poke(rid.U); f.transaction_identity.incarnation.poke(0.U)
      f.admission_group_tag.poke(group.U); f.admission_member_ordinal.poke(0.U)
      f.admission_group_valid_records.poke((if (retain) 1 else 0).U)
      d.io.frontend_lifecycle_req.valid.poke(true.B)
      until(s"frontend event $event not accepted")(bool(d.io.frontend_lifecycle_req.ready))
      tick(); d.io.frontend_lifecycle_req.valid.poke(false.B)
    }
    def plan(rid: Int, sourceGeneration: Int): Unit = {
      val x = d.io.source_plan_declaration_in.bits
      x.transaction_identity.request_id.poke(rid.U); x.transaction_identity.incarnation.poke(0.U)
      x.source_presence.poke(4.U)
      x.hot_instance.source_kind.poke(RouteASourceKind.Hot.U)
      x.hot_instance.instance_coordinate.poke(0.U); x.hot_instance.generation.poke(0.U)
      x.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
      x.pending_instance.instance_coordinate.poke(0.U); x.pending_instance.generation.poke(0.U)
      x.packed_instance.source_kind.poke(RouteASourceKind.Packed.U)
      x.packed_instance.instance_coordinate.poke(1.U); x.packed_instance.generation.poke(sourceGeneration.U)
      x.pending_descriptor_key.pending_descriptor_ref.poke(0.U); x.pending_descriptor_key.pending_descriptor_generation.poke(0.U)
      d.io.source_plan_declaration_in.valid.poke(true.B)
      until("source declaration not accepted")(bool(d.io.source_plan_declaration_in.ready))
      tick(); d.io.source_plan_declaration_in.valid.poke(false.B)
    }
    def offerBinding(layer: Int, payload: Int, group: Int, rid: Int): Unit = {
      val b = d.io.pending_payload_read_binding_in.bits
      b.transaction_identity.request_id.poke(rid.U); b.transaction_identity.incarnation.poke(0.U)
      b.entry_id.poke((layer * 8).U); b.layer.poke(layer.U); b.kv_head.poke(0.U); b.logical_position.poke(0.U)
      b.payload_ref.poke(payload.U); b.transaction_group_tag.poke(group.U)
      b.group_member_ordinal.poke(0.U); b.group_valid_records.poke(1.U)
      b.payload_handle_or_address.poke(payload.U); b.source_generation.poke(1.U); b.destination_endpoint.poke(0.U)
      b.m2_group_opaque_address_ref.poke((40 + layer).U); b.m2_group_owner.poke(rid.U)
      d.io.pending_payload_read_binding_in.valid.poke(true.B)
    }
    def partial(consumer: Int): Unit = {
      val x = d.io.functional_partial_packed_offer_in.bits
      x.transaction_identity.request_id.poke(3.U); x.transaction_identity.incarnation.poke(0.U)
      x.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
      x.source_instance.instance_coordinate.poke(1.U); x.source_instance.generation.poke(1.U)
      x.consumer_id.poke(consumer.U)
      x.r4_header.poke(((BigInt(RouteASourceKind.Packed) << 64) | (BigInt(consumer) << 66) |
        (BigInt(1) << 69) | (BigInt(8) << 70)).U)
      x.partial_present.poke(true.B)
      d.io.functional_partial_packed_offer_in.valid.poke(true.B)
      until("first packed partial offer blocked")(bool(d.io.functional_partial_packed_offer_in.ready))
      tick(); d.io.functional_partial_packed_offer_in.valid.poke(false.B); tick()
      (0 until 8).foreach { index =>
        val f = d.io.functional_partial_packed_fragment_in.bits
        f.transaction_identity.request_id.poke(3.U); f.transaction_identity.incarnation.poke(0.U)
        f.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
        f.source_instance.instance_coordinate.poke(1.U); f.source_instance.generation.poke(1.U)
        f.consumer_id.poke(consumer.U); f.fragment_index.poke(index.U)
        f.last.poke((index == 7).B); f.data.poke((0x300 + consumer * 8 + index).U)
        d.io.functional_partial_packed_fragment_in.valid.poke(true.B)
        until("first partial fragment blocked")(bool(d.io.functional_partial_packed_fragment_in.ready))
        tick(); d.io.functional_partial_packed_fragment_in.valid.poke(false.B)
      }
    }
    def firstUse(): Unit = {
      idleInputs(); tick()
      lifecycle(p.r6.sessionStartEventCode, rid = 0)
      // Post-decision fixture, not a complete 128-token frontend/predictor run.
      lifecycle(p.r6.kvArrivalEventCode, rid = 0, payload = 55)
      lifecycle(p.r6.attentionServiceEventCode, rid = 3, position = 128)
      plan(rid = 3, sourceGeneration = 1)
      lifecycle(p.r6.maturityDispositionEventCode, rid = 0, retain = true, payload = 55, group = 1)
      offerBinding(layer = 0, payload = 55, group = 1, rid = 3)
      until("first binding join blocked")(bool(d.io.pending_payload_read_binding_in.ready))
      tick(); d.io.pending_payload_read_binding_in.valid.poke(false.B)
      until("first packed source never reached READY", 2048)(uint(d.observation.s2_slot_state) == 2)
      assert(publications == 1 && handoffs == 1 && admissionJoins == 1 && r3Admissions == 1)
      assert(payloadFragments == 8 && sidecarFragments == 1 && pageId.contains(BigInt(0)) && descriptorGrants == 1)
      val packed = store.committedWrites.filter(_.expectedFragments == 8)
      assert(packed.size == 1 && packed.head.addressRef == payloadHandle.get && packed.head.payloadFragments == PendingData,
        "packed payload must come from the actual accepted write")
      assert(store.objectAt(payloadHandle.get, 8).exists(_.payloadFragments == PendingData))
      (0 until 4).foreach(partial)
      (0 until 4).foreach { consumer =>
        until("first R4 merge work blocked")(bool(d.io.functional_r4_merge_work_out.valid))
        d.io.functional_r4_merge_work_out.bits.transaction_identity.request_id.expect(3.U)
        d.io.functional_r4_merge_work_out.bits.consumer_id.expect(consumer.U)
        d.io.functional_r4_merge_work_out.ready.poke(true.B); tick(); d.io.functional_r4_merge_work_out.ready.poke(false.B)
        val r = d.io.functional_r4_result_in.bits
        r.transaction_identity.request_id.poke(3.U); r.transaction_identity.incarnation.poke(0.U)
        r.consumer_id.poke(consumer.U); r.normalized_value.poke((0x400 + consumer).U)
        d.io.functional_r4_result_in.valid.poke(true.B)
        until("first R4 result blocked")(bool(d.io.functional_r4_result_in.ready))
        tick(); d.io.functional_r4_result_in.valid.poke(false.B)
      }
      until("first outward terminal missing")(bool(d.io.attention_terminal_rsp.valid))
      d.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(3.U)
      d.io.attention_terminal_rsp.bits.terminal_status.expect(p.coreMemoryOkStatusCode.U)
      d.io.attention_terminal_rsp.ready.poke(true.B); tick(); d.io.attention_terminal_rsp.ready.poke(false.B)
      (0 until 4).foreach(_ => tick())
      assert(terminalCount == 1 && consumers == 4 && releases == 1 && memoryFaults == 0)
      d.observation.r6_state.expect(2.U); d.observation.r6_attention_live.expect(false.B)
      d.observation.s2_slot_state.expect(0.U); d.observation.s2_slot_generation.expect(1.U)
      d.observation.page0_readable.expect(true.B); d.observation.descriptor_line0_allocated.expect(true.B)
      d.observation.metadata_group0_active.expect(false.B); d.observation.metadata_local_credit0.expect(0.U)
      d.observation.journal_ordinal0_present.expect(true.B)
      println(s"KVZAP_STAGE_A_FIRST_USE_COMPLETE page_id=${pageId.get} page_generation=${pageGeneration.get} " +
        s"payload_write_commits=${packed.size} payload_fragments=$payloadFragments sidecar_fragments=$sidecarFragments " +
        s"publications=$publications handoffs=$handoffs consumers=$consumers terminals=$terminalCount " +
        "gate_compact=0 r5_stream_slots=16 position_backing_external=1 numeric_correspondence=0")
    }
    def commonEvidence: String = s"first_terminal=$terminalCount second_terminal=${terminalCount - 1} publications=$publications " +
      s"handoffs=$handoffs consumer_commits=$consumers payload_write_commits=${store.committedWrites.count(_.expectedFragments == 8)} " +
      s"payload_fragments=$payloadFragments sidecar_fragments=$sidecarFragments page_id=${pageId.get} " +
      s"page_generation=${pageGeneration.get} no_fault=${if (memoryFaults == 0) 1 else 0} bound_cycles=$ProbeCycles " +
      "capability_pass=0 gate_compact=0 r5_stream_slots=16 position_backing_external=1 numeric_correspondence=0"
  }

  it("qualifies the existing same-page repeat-read blocker without changing the RTL") {
    simulate(new RouteAStageAContinuationProbeHarness(p)) { d =>
      val x = new Driver(d); x.firstUse()
      val readsBefore = x.readRequests
      x.lifecycle(p.r6.attentionServiceEventCode, rid = 5, position = 129)
      x.plan(rid = 5, sourceGeneration = 2)
      x.until("second accepted plan never reached activation binder")(x.bool(d.observation.binder_have_plan))
      (0 until ProbeCycles).foreach { _ =>
        d.observation.r6_state.expect(2.U); d.observation.r6_attention_live.expect(true.B)
        d.observation.binder_have_plan.expect(true.B); d.observation.binder_have_page_ready.expect(false.B)
        d.observation.binder_have_member_stream.expect(false.B)
        d.observation.descriptor_request_valid.expect(false.B); d.observation.lease_request_valid.expect(false.B)
        d.observation.s2_slot_state.expect(0.U); d.observation.s2_slot_generation.expect(1.U)
        d.observation.page0_readable.expect(true.B); d.io.attention_terminal_rsp.valid.expect(false.B)
        x.tick()
      }
      assert(x.readRequests == readsBefore && x.descriptorGrants == 1 && x.publications == 1 && x.memoryFaults == 0)
      assert(x.terminalCount == 1 && x.consumers == 4 && x.releases == 1)
      d.observation.s2_slot_page_id.expect(x.pageId.get.U)
      d.observation.s2_slot_page_generation.expect(x.pageGeneration.get.U)
      val o = d.observation
      println("KVZAP_STAGE_A_PROBE_RESULT case=READ_REUSE outcome=BLOCKED blocker=ONE_SHOT_ACTIVATION " +
        s"second_attention_accepted=${x.bit(o.r6_attention_live)} second_plan_accepted=${x.bit(o.binder_have_plan)} " +
        s"r6_active=${if (x.uint(o.r6_state) == 2) 1 else 0} s2_empty=${if (x.uint(o.s2_slot_state) == 0) 1 else 0} " +
        s"page_live=${x.bit(o.page0_readable)} binder_have_plan=${x.bit(o.binder_have_plan)} " +
        s"binder_have_page_ready=${x.bit(o.binder_have_page_ready)} binder_have_member_stream=${x.bit(o.binder_have_member_stream)} " +
        s"descriptor_requests=${x.bit(o.descriptor_request_valid)} lease_requests=${x.bit(o.lease_request_valid)} " +
        s"s2_generation=${x.uint(o.s2_slot_generation)} second_read_requests=${x.readRequests - readsBefore} " + x.commonEvidence)
    }
  }

  it("qualifies the existing second-admission blocker in the same session without reset") {
    simulate(new RouteAStageAContinuationProbeHarness(p)) { d =>
      val x = new Driver(d); x.firstUse()
      x.lifecycle(p.r6.kvArrivalEventCode, rid = 0, layer = 1, payload = 77)
      x.lifecycle(p.r6.maturityDispositionEventCode, rid = 0, layer = 1, retain = true, payload = 77, group = 2)
      x.offerBinding(layer = 1, payload = 77, group = 2, rid = 4)
      val joinsBefore = x.admissionJoins
      (0 until ProbeCycles).foreach { _ =>
        d.observation.r6_state.expect(2.U); d.observation.r6_control_pending.expect(true.B)
        d.observation.admission_state.expect(7.U); d.observation.r6_context_valid.expect(true.B)
        d.observation.r6_authority_valid.expect(true.B); d.observation.r6_context_ready.expect(false.B)
        d.io.pending_payload_read_binding_in.ready.expect(false.B)
        d.observation.page0_readable.expect(true.B); d.observation.journal_ordinal0_present.expect(true.B)
        d.observation.metadata_group0_active.expect(false.B); d.observation.metadata_local_credit0.expect(0.U)
        d.io.attention_terminal_rsp.valid.expect(false.B)
        x.tick()
      }
      assert(x.admissionJoins == joinsBefore && joinsBefore == 1 && x.r3Admissions == 1)
      assert(x.publications == 1 && x.handoffs == 1 && x.memoryFaults == 0 && x.terminalCount == 1)
      val o = d.observation
      println("KVZAP_STAGE_A_PROBE_RESULT case=ADMISSION_REUSE outcome=BLOCKED blocker=INGRESS_DONE " +
        s"second_join_accepted=${x.admissionJoins - joinsBefore} r6_context_valid=${x.bit(o.r6_context_valid)} " +
        s"r6_authority_valid=${x.bit(o.r6_authority_valid)} binding_valid=${x.bit(d.io.pending_payload_read_binding_in.valid)} " +
        s"ingress_done=${if (x.uint(o.admission_state) == 7) 1 else 0} pending_binding_ready=${x.bit(d.io.pending_payload_read_binding_in.ready)} " +
        s"journal_ordinal0_present=${x.bit(o.journal_ordinal0_present)} local_credit=${x.uint(o.metadata_local_credit0)} " +
        s"r6_active=${if (x.uint(o.r6_state) == 2) 1 else 0} page_live=${x.bit(o.page0_readable)} " + x.commonEvidence)
    }
  }
}
