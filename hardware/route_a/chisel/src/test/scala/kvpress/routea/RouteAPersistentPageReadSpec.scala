package kvpress.routea

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.DecoupledIO
import chisel3.util.experimental.BoringUtils
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.rtl3.{RouteAFunctionalMemoryEnvironment, RouteAFunctionalMemoryStore}
import kvpress.routea.top.RouteAMeasurementDut
import org.scalatest.funspec.AnyFunSpec

/** Complete production-v2 DUT with ordinary outer services and read-only taps. */
final class RouteAPersistentPageReadHarness(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val frontend_lifecycle_req = Flipped(RouteAChannels.frontend_lifecycle_req(p))
    val runtime_retire_req = Flipped(RouteAChannels.runtime_retire_req)
    val attention_terminal_rsp = RouteAChannels.attention_terminal_rsp
    val session_retire_ack = RouteAChannels.session_retire_ack
    val source_plan_declaration_in = Flipped(RouteAChannels.source_plan_declaration(p))
    val pending_source_descriptor_registration_in = Flipped(RouteAChannels.pending_source_descriptor_registration(p))
    val hot_payload_fragment_in = Flipped(RouteAChannels.p3_pending_fragment(p))
    val hot_position_sidecar_in = Flipped(RouteAChannels.p3_sidecar_bind(p))
    val pending_payload_read_binding_in = Flipped(RouteAChannels.pending_payload_read_binding(p))
    val functional_partial_hot_offer_in = Flipped(RouteAChannels.source_service_partial_offer(p))
    val functional_partial_pending_offer_in = Flipped(RouteAChannels.source_service_partial_offer(p))
    val functional_partial_packed_offer_in = Flipped(RouteAChannels.source_service_partial_offer(p))
    val functional_partial_hot_fragment_in = Flipped(RouteAChannels.source_service_value_fragment(p))
    val functional_partial_pending_fragment_in = Flipped(RouteAChannels.source_service_value_fragment(p))
    val functional_partial_packed_fragment_in = Flipped(RouteAChannels.source_service_value_fragment(p))
    val functional_r4_accepted_packet_out = RouteAChannels.r4_accepted_partial_packet(p)
    val functional_r4_merge_work_out = RouteAChannels.merge_req
    val functional_r4_result_in = Flipped(RouteAChannels.r4_result_stub)
    val functional_r4_numeric_fault_in = Flipped(RouteAChannels.r4_numeric_fault)
    val functional_direct_pending_payload_fragment_out = RouteAChannels.direct_pending_payload_fragment(p)
    val external_core_mem_if_v1 = new CoreMemoryExternalPort(p)
  })

  val dut = Module(new RouteAMeasurementDut(p, persistentReadEnabled = true))
  val persistent = IO(chiselTypeOf(dut.persistentRead.get))
  persistent <> dut.persistentRead.get
  dut.io.frontend_lifecycle_req <> io.frontend_lifecycle_req
  dut.io.runtime_retire_req <> io.runtime_retire_req
  io.attention_terminal_rsp <> dut.io.attention_terminal_rsp
  io.session_retire_ack <> dut.io.session_retire_ack
  dut.io.source_plan_declaration_in <> io.source_plan_declaration_in
  dut.io.pending_source_descriptor_registration_in <> io.pending_source_descriptor_registration_in
  dut.io.hot_payload_fragment_in <> io.hot_payload_fragment_in
  dut.io.hot_position_sidecar_in <> io.hot_position_sidecar_in
  dut.io.pending_payload_read_binding_in <> io.pending_payload_read_binding_in
  dut.io.functional_partial_hot_offer_in <> io.functional_partial_hot_offer_in
  dut.io.functional_partial_pending_offer_in <> io.functional_partial_pending_offer_in
  dut.io.functional_partial_packed_offer_in <> io.functional_partial_packed_offer_in
  dut.io.functional_partial_hot_fragment_in <> io.functional_partial_hot_fragment_in
  dut.io.functional_partial_pending_fragment_in <> io.functional_partial_pending_fragment_in
  dut.io.functional_partial_packed_fragment_in <> io.functional_partial_packed_fragment_in
  io.functional_r4_accepted_packet_out <> dut.io.functional_r4_accepted_packet_out
  io.functional_r4_merge_work_out <> dut.io.functional_r4_merge_work_out
  dut.io.functional_r4_result_in <> io.functional_r4_result_in
  dut.io.functional_r4_numeric_fault_in <> io.functional_r4_numeric_fault_in
  io.functional_direct_pending_payload_fragment_out <>
    dut.io.functional_direct_pending_payload_fragment_out
  dut.io.external_core_mem_if_v1 <> io.external_core_mem_if_v1

  dut.io.functional_sidecar_work_out.ready := false.B
  dut.io.functional_sidecar_payload_release_out.ready := false.B
  dut.io.functional_sidecar_registry_allocate_in.valid := false.B
  dut.io.functional_sidecar_registry_allocate_in.bits :=
    0.U.asTypeOf(dut.io.functional_sidecar_registry_allocate_in.bits)
  dut.io.functional_sidecar_registry_allocation_ordinal_in := 0.U
  dut.io.functional_sidecar_registry_allocation_candidate_id_in := 0.U
  dut.io.functional_sidecar_registry_allocation_ack_out.ready := false.B
  dut.io.functional_sidecar_read_issue_in.valid := false.B
  dut.io.functional_sidecar_read_issue_in.bits :=
    0.U.asTypeOf(dut.io.functional_sidecar_read_issue_in.bits)
  dut.io.functional_r5_descriptor_service.request.ready := false.B
  dut.io.functional_r5_descriptor_service.response.valid := false.B
  dut.io.functional_r5_descriptor_service.response.bits :=
    0.U.asTypeOf(dut.io.functional_r5_descriptor_service.response.bits)

  private def tap[T <: Data](x: T): T = BoringUtils.tapAndRead(x)
  private def fire[T <: Data](x: DecoupledIO[T]): Bool = tap(x.valid) && tap(x.ready)
  val observation = IO(Output(new Bundle {
    val r6_state = UInt(3.W)
    val attention_live = Bool()
    val preflight_busy = Bool()
    val declaration_live = Bool()
    val preflight_state = UInt(4.W)
    val r5_scan_outstanding = Bool()
    val r5_scan_allowed = Bool()
    val r5_v2_response_owner = Bool()
    val r5_shared_request_fire = Bool()
    val r5_shared_response_fire = Bool()
    val r5_query_request_fire = Bool()
    val r5_mark_request_fire = Bool()
    val publication_fire = Bool()
    val publication_status = UInt(2.W)
    val page_ready_fire = Bool()
    val materialized_sidecar_fire = Bool()
    val materialized_position = UInt(15.W)
    val descriptor_grant_fire = Bool()
    val descriptor_payload_handle = UInt(p.coreMemoryAddressRefWidth.W)
    val descriptor_sidecar_handle = UInt(p.coreMemoryAddressRefWidth.W)
    val s2_slot_state = UInt(3.W)
    val s2_slot_generation = UInt(p.sourceGenerationWidth.W)
    val s2_any_live = Bool()
    val s2_release_fire = Bool()
    val consumer_commit_fire = Bool()
    val payload_fragment_fire = Bool()
    val payload_fragment_index = UInt(9.W)
    val payload_fragment_data = UInt(512.W)
    val sidecar_fragment_fire = Bool()
    val sidecar_fragment_data = UInt(64.W)
    val page0_readable = Bool()
    val descriptor_line0_allocated = Bool()
  }))
  observation.r6_state := tap(dut.lifecycle.state)
  observation.attention_live := tap(dut.lifecycle.attentionValid).asUInt.orR
  observation.preflight_busy := tap(dut.persistentActivation.get.io.busy)
  observation.declaration_live := tap(dut.sourcePlanBinder.haveDeclaration)
  observation.preflight_state := tap(dut.persistentActivation.get.state)
  observation.r5_scan_outstanding := tap(dut.pageManager.scanOutstanding)
  observation.r5_scan_allowed := tap(dut.pageManager.scanAllowed)
  observation.r5_v2_response_owner := tap(dut.pageManager.persistentAvailabilityOutstanding)
  observation.r5_shared_request_fire := fire(dut.pageManager.availabilityStorage.io.availability_lookup_req)
  observation.r5_shared_response_fire := fire(dut.pageManager.availabilityStorage.io.availability_lookup_rsp)
  observation.r5_query_request_fire := fire(dut.pageManager.persistentRead.get.query_in)
  observation.r5_mark_request_fire := fire(dut.pageManager.persistentRead.get.mark_ready_in)
  observation.publication_fire := fire(dut.m2P3.io.m2_publish_ack)
  observation.publication_status := tap(dut.m2P3.io.m2_publish_ack.bits.status)
  observation.page_ready_fire := fire(dut.m2P3.io.post_r6_packed_page_ready_observation)
  observation.materialized_sidecar_fire := fire(dut.m2P3.io.p3_materialized_sidecar_out)
  observation.materialized_position := tap(dut.m2P3.io.p3_materialized_sidecar_out.bits.logical_position)
  private val readResult = dut.pageManager.persistentRead.get.query_result_out
  observation.descriptor_grant_fire := fire(readResult) && tap(readResult.bits.status) === PersistentReadStatus.OK.U
  observation.descriptor_payload_handle := tap(readResult.bits.grant.payload_handle_or_address)
  observation.descriptor_sidecar_handle := tap(readResult.bits.grant.sidecar_handle_or_address)
  observation.s2_slot_state := tap(dut.s2.slotState(1))
  observation.s2_slot_generation := tap(dut.s2.slotGeneration(1))
  observation.s2_any_live := tap(dut.s2.slotState).asUInt.orR
  observation.s2_release_fire := fire(dut.s2.io.s2_release_out)
  observation.consumer_commit_fire := fire(dut.s2.io.gqa_consumer_commit_in)
  observation.payload_fragment_fire := fire(dut.s2.io.s2_payload_fragment_in)
  observation.payload_fragment_index := tap(dut.s2.io.s2_payload_fragment_in.bits.fragment_index)
  observation.payload_fragment_data := tap(dut.s2.io.s2_payload_fragment_in.bits.data)
  observation.sidecar_fragment_fire := fire(dut.s2.io.s2_sidecar_fragment_in)
  observation.sidecar_fragment_data := tap(dut.s2.io.s2_sidecar_fragment_in.bits.data)
  observation.page0_readable := tap(dut.pageManager.descriptorReadable.get(0))
  observation.descriptor_line0_allocated := tap(dut.pageManager.allocatedLine(0))
}

object RouteAPersistentPageReadTestParameters {
  val small = RouteASkeletonParameters(
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
    r5StreamSlots = 16, sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )
}

/** Protocol/data-continuity witnesses; the external numeric provider stays explicit. */
final class RouteAPersistentPageReadSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteAPersistentPageReadTestParameters.small
  private val PendingData = Vector.tabulate(8)(i => BigInt(0x100 + i))
  private val Scope = "persistent_v2=1 gate_compact=0 r5_stream_slots=16 " +
    "position_backing_external=1 numeric_correspondence=0"

  private final class Driver(val d: RouteAPersistentPageReadHarness) {
    val store = new RouteAFunctionalMemoryStore
    private val memory = new RouteAFunctionalMemoryEnvironment(p, store)
    // Only the original pending object is preloaded, never the packed payload.
    store.preload(BigInt(55), None, PendingData, Vector.empty)
    var publications = 0; var handoffs = 0; var notices = 0
    var consumers = 0; var releases = 0; var terminalsOk = 0; var terminalsFault = 0
    var readRequests = 0; var payloadFragments = 0; var sidecarFragments = 0
    var rejected = 0; var memoryFaults = 0
    var pageId: Option[BigInt] = None; var pageGeneration: Option[BigInt] = None
    var payloadHandle: Option[BigInt] = None; var sidecarHandle: Option[BigInt] = None
    var materializedPosition: Option[BigInt] = None
    def bool(x: Bool): Boolean = x.peek().litToBoolean
    def uint(x: UInt): BigInt = x.peek().litValue
    def tick(): Unit = {
      memory.drive(d.io.external_core_mem_if_v1)
      assert(!bool(d.persistent.receipt_fault_out.valid), "real R3 receipt was rejected by its R5 owner")
      val o = d.observation
      if (bool(o.publication_fire)) { assert(uint(o.publication_status) == 0); publications += 1 }
      if (bool(o.page_ready_fire)) handoffs += 1
      val notice = d.persistent.page_available_out
      if (bool(notice.valid) && bool(notice.ready)) {
        assert(uint(notice.bits.layer) == 0 && uint(notice.bits.kv_head) == 0)
        assert(uint(notice.bits.valid_records) == 1 && uint(notice.bits.transaction_group_tag) == 1)
        pageId = Some(uint(notice.bits.page_ref.page_id))
        pageGeneration = Some(uint(notice.bits.page_ref.generation)); notices += 1
      }
      if (bool(o.materialized_sidecar_fire)) materializedPosition = Some(uint(o.materialized_position))
      if (bool(o.descriptor_grant_fire)) {
        val payload = uint(o.descriptor_payload_handle); val sidecar = uint(o.descriptor_sidecar_handle)
        val pos = materializedPosition.getOrElse(fail("query preceded real R3 position materialization"))
        payloadHandle.foreach(old => assert(old == payload, "same PageRef changed payload location"))
        sidecarHandle match {
          case None =>
            // Explicit external position-backing service, not a hardware sidecar write.
            store.preload(sidecar, None, Vector(pos), Vector(pos))
          case Some(old) =>
            assert(old == sidecar && store.objectAt(old, 1).exists(_.payloadFragments == Vector(pos)))
        }
        payloadHandle = Some(payload); sidecarHandle = Some(sidecar)
      }
      if (bool(o.consumer_commit_fire)) consumers += 1
      if (bool(o.s2_release_fire)) releases += 1
      if (bool(o.payload_fragment_fire)) {
        val index = uint(o.payload_fragment_index).toInt
        assert(index < PendingData.size && uint(o.payload_fragment_data) == PendingData(index),
          "packed payload must remain the actual first write across reads")
        payloadFragments += 1
      }
      if (bool(o.sidecar_fragment_fire)) {
        assert(materializedPosition.contains(uint(o.sidecar_fragment_data))); sidecarFragments += 1
      }
      val mem = d.io.external_core_mem_if_v1
      if (bool(mem.request.valid) && bool(mem.request.ready) && uint(mem.request.bits.request_kind) == p.coreMemoryReadRequestCode)
        readRequests += 1
      if (bool(mem.response.valid) && bool(mem.response.ready) && uint(mem.response.bits.status) != p.coreMemoryOkStatusCode)
        memoryFaults += 1
      if (bool(d.persistent.rejected_out.valid) && bool(d.persistent.rejected_out.ready)) rejected += 1
      if (bool(d.io.attention_terminal_rsp.valid) && bool(d.io.attention_terminal_rsp.ready)) {
        uint(d.io.attention_terminal_rsp.bits.terminal_status).toInt match {
          case x if x == p.coreMemoryOkStatusCode => terminalsOk += 1
          case x if x == p.coreMemoryFaultStatusCode => terminalsFault += 1
          case x => fail(s"unknown terminal status $x")
        }
      }
      memory.observeAccepted(mem)
      d.clock.step()
    }
    def until(message: String, limit: Int = 1024)(predicate: => Boolean): Unit = {
      var waited = 0
      while (!predicate && waited < limit) { tick(); waited += 1 }
      val complete = predicate
      if (!complete) {
        val o = d.observation
        // Query actual read-only taps on failure; do not infer internal state
        // from a READY timeout or increase its original 2048-clock bound.
        println(s"KVZAP_PERSISTENT_READ_TIMEOUT waited=$waited preflight_state=${uint(o.preflight_state)} " +
          s"preflight_busy=${bool(o.preflight_busy)} declaration_live=${bool(o.declaration_live)} " +
          s"scan_outstanding=${bool(o.r5_scan_outstanding)} scan_allowed=${bool(o.r5_scan_allowed)} " +
          s"v2_response_owner=${bool(o.r5_v2_response_owner)} " +
          s"shared_req_fire=${bool(o.r5_shared_request_fire)} shared_rsp_fire=${bool(o.r5_shared_response_fire)} " +
          s"query_fire=${bool(o.r5_query_request_fire)} mark_fire=${bool(o.r5_mark_request_fire)} " +
          s"s2_state=${uint(o.s2_slot_state)} s2_generation=${uint(o.s2_slot_generation)} " +
          s"positive_grants=${payloadHandle.nonEmpty} payload_fragments=$payloadFragments " +
          s"sidecar_fragments=$sidecarFragments rejected=$rejected terminals_ok=$terminalsOk terminals_fault=$terminalsFault")
      }
      assert(complete, s"$message after $waited clocks")
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
      d.persistent.page_available_out.ready.poke(true.B); d.persistent.rejected_out.ready.poke(true.B)
      d.persistent.page_select_in.valid.poke(false.B)
      d.persistent.receipt_fault_out.ready.poke(true.B)
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
      until(s"frontend event $event blocked")(bool(d.io.frontend_lifecycle_req.ready))
      tick(); d.io.frontend_lifecycle_req.valid.poke(false.B)
    }
    def plan(rid: Int, sourceGeneration: Int, coordinate: BigInt = 1): Unit = {
      val x = d.io.source_plan_declaration_in.bits
      x.transaction_identity.request_id.poke(rid.U); x.transaction_identity.incarnation.poke(0.U)
      x.source_presence.poke(4.U)
      x.hot_instance.source_kind.poke(RouteASourceKind.Hot.U)
      x.hot_instance.instance_coordinate.poke(0.U); x.hot_instance.generation.poke(0.U)
      x.pending_instance.source_kind.poke(RouteASourceKind.Pending.U)
      x.pending_instance.instance_coordinate.poke(0.U); x.pending_instance.generation.poke(0.U)
      x.packed_instance.source_kind.poke(RouteASourceKind.Packed.U)
      x.packed_instance.instance_coordinate.poke(coordinate.U); x.packed_instance.generation.poke(sourceGeneration.U)
      x.pending_descriptor_key.pending_descriptor_ref.poke(0.U); x.pending_descriptor_key.pending_descriptor_generation.poke(0.U)
      d.io.source_plan_declaration_in.valid.poke(true.B)
      until("source declaration blocked")(bool(d.io.source_plan_declaration_in.ready))
      tick(); d.io.source_plan_declaration_in.valid.poke(false.B)
    }
    def select(rid: Int, generation: BigInt = 0): Unit = {
      val x = d.persistent.page_select_in.bits
      x.transaction_identity.request_id.poke(rid.U); x.transaction_identity.incarnation.poke(0.U)
      x.page_ref.page_id.poke(pageId.get.U); x.page_ref.generation.poke(generation.U)
      d.persistent.page_select_in.valid.poke(true.B)
      until("page selector blocked")(bool(d.persistent.page_select_in.ready))
      tick(); d.persistent.page_select_in.valid.poke(false.B)
    }
    def publishOne(): Unit = {
      idleInputs(); tick()
      lifecycle(p.r6.sessionStartEventCode, rid = 0)
      lifecycle(p.r6.kvArrivalEventCode, rid = 0, payload = 55)
      lifecycle(p.r6.maturityDispositionEventCode, rid = 0, retain = true, payload = 55, group = 1)
      val b = d.io.pending_payload_read_binding_in.bits
      b.transaction_identity.request_id.poke(3.U); b.transaction_identity.incarnation.poke(0.U)
      b.entry_id.poke(0.U); b.layer.poke(0.U); b.kv_head.poke(0.U); b.logical_position.poke(0.U)
      b.payload_ref.poke(55.U); b.transaction_group_tag.poke(1.U)
      b.group_member_ordinal.poke(0.U); b.group_valid_records.poke(1.U)
      b.payload_handle_or_address.poke(55.U); b.source_generation.poke(1.U); b.destination_endpoint.poke(0.U)
      b.m2_group_opaque_address_ref.poke(40.U); b.m2_group_owner.poke(3.U)
      d.io.pending_payload_read_binding_in.valid.poke(true.B)
      until("first admission binding blocked")(bool(d.io.pending_payload_read_binding_in.ready))
      tick(); d.io.pending_payload_read_binding_in.valid.poke(false.B)
      until("publication collector did not notify runtime without attention", 2048)(notices == 1)
      assert(publications == 1 && handoffs == 1 && pageId.contains(BigInt(0)) && pageGeneration.contains(BigInt(0)))
      assert(!bool(d.observation.attention_live) && !bool(d.observation.s2_any_live))
      val writes = store.committedWrites.filter(_.expectedFragments == 8)
      assert(writes.size == 1 && writes.head.payloadFragments == PendingData,
        "first packed payload must come from the actual accepted write")
      d.observation.page0_readable.expect(true.B)
    }
    def beginRead(rid: Int, generation: Int): Unit = {
      lifecycle(p.r6.attentionServiceEventCode, rid, position = 128 + generation)
      select(rid, pageGeneration.get); plan(rid, generation)
    }
    def partial(rid: Int, generation: Int, consumer: Int): Unit = {
      val x = d.io.functional_partial_packed_offer_in.bits
      x.transaction_identity.request_id.poke(rid.U); x.transaction_identity.incarnation.poke(0.U)
      x.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
      x.source_instance.instance_coordinate.poke(1.U); x.source_instance.generation.poke(generation.U)
      x.consumer_id.poke(consumer.U)
      x.r4_header.poke(((BigInt(RouteASourceKind.Packed) << 64) | (BigInt(consumer) << 66) |
        (BigInt(1) << 69) | (BigInt(8) << 70)).U)
      x.partial_present.poke(true.B)
      d.io.functional_partial_packed_offer_in.valid.poke(true.B)
      until("packed partial offer blocked")(bool(d.io.functional_partial_packed_offer_in.ready))
      tick(); d.io.functional_partial_packed_offer_in.valid.poke(false.B); tick()
      (0 until 8).foreach { index =>
        val f = d.io.functional_partial_packed_fragment_in.bits
        f.transaction_identity.request_id.poke(rid.U); f.transaction_identity.incarnation.poke(0.U)
        f.source_instance.source_kind.poke(RouteASourceKind.Packed.U)
        f.source_instance.instance_coordinate.poke(1.U); f.source_instance.generation.poke(generation.U)
        f.consumer_id.poke(consumer.U); f.fragment_index.poke(index.U)
        f.last.poke((index == 7).B); f.data.poke((0x300 + consumer * 8 + index).U)
        d.io.functional_partial_packed_fragment_in.valid.poke(true.B)
        until("partial fragment blocked")(bool(d.io.functional_partial_packed_fragment_in.ready))
        tick(); d.io.functional_partial_packed_fragment_in.valid.poke(false.B)
      }
    }
    def consumeTerminal(rid: Int, status: Int): Unit = {
      until("attention terminal missing")(bool(d.io.attention_terminal_rsp.valid))
      d.io.attention_terminal_rsp.bits.transaction_identity.request_id.expect(rid.U)
      d.io.attention_terminal_rsp.bits.terminal_status.expect(status.U)
      d.io.attention_terminal_rsp.ready.poke(true.B); tick(); d.io.attention_terminal_rsp.ready.poke(false.B)
      (0 until 4).foreach(_ => tick())
      d.observation.attention_live.expect(false.B)
    }
    def completeRead(rid: Int, generation: Int): Unit = {
      until("packed source did not reach READY", 2048)(uint(d.observation.s2_slot_state) == 2)
      (0 until 4).foreach(partial(rid, generation, _))
      (0 until 4).foreach { consumer =>
        until("R4 merge work missing")(bool(d.io.functional_r4_merge_work_out.valid))
        d.io.functional_r4_merge_work_out.bits.transaction_identity.request_id.expect(rid.U)
        d.io.functional_r4_merge_work_out.bits.consumer_id.expect(consumer.U)
        d.io.functional_r4_merge_work_out.ready.poke(true.B); tick(); d.io.functional_r4_merge_work_out.ready.poke(false.B)
        val r = d.io.functional_r4_result_in.bits
        r.transaction_identity.request_id.poke(rid.U); r.transaction_identity.incarnation.poke(0.U)
        r.consumer_id.poke(consumer.U); r.normalized_value.poke((0x400 + consumer).U)
        d.io.functional_r4_result_in.valid.poke(true.B)
        until("R4 result blocked")(bool(d.io.functional_r4_result_in.ready))
        tick(); d.io.functional_r4_result_in.valid.poke(false.B)
      }
      consumeTerminal(rid, p.coreMemoryOkStatusCode)
      d.observation.s2_slot_state.expect(0.U); d.observation.s2_slot_generation.expect(generation.U)
      d.observation.s2_any_live.expect(false.B)
    }
    def requestRetire(): Unit = {
      val r = d.io.runtime_retire_req.bits
      r.session_id.poke(false.B); r.transaction_identity.request_id.poke(0.U); r.transaction_identity.incarnation.poke(0.U)
      d.io.runtime_retire_req.valid.poke(true.B)
      until("runtime retirement request blocked")(bool(d.io.runtime_retire_req.ready))
      tick(); d.io.runtime_retire_req.valid.poke(false.B)
    }
    def finishRetire(): Unit = {
      until("retirement/reclaim failed to drain", 4096)(bool(d.io.session_retire_ack.valid))
      d.io.session_retire_ack.bits.transaction_identity.request_id.expect(0.U)
      d.observation.s2_any_live.expect(false.B); d.observation.attention_live.expect(false.B)
      d.observation.page0_readable.expect(false.B); d.observation.descriptor_line0_allocated.expect(false.B)
      d.io.session_retire_ack.ready.poke(true.B); tick(); d.io.session_retire_ack.ready.poke(false.B)
      d.observation.r6_state.expect(4.U)
    }
    def twoReadEvidence: String = {
      assert(publications == 1 && handoffs == 1 && notices == 1)
      assert(payloadFragments == 16 && sidecarFragments == 2 && consumers == 8 && releases == 2)
      assert(terminalsOk == 2 && terminalsFault == 0 && memoryFaults == 0)
      val writes = store.committedWrites.filter(_.expectedFragments == 8)
      assert(writes.size == 1 && payloadHandle.contains(writes.head.addressRef) && writes.head.payloadFragments == PendingData)
      s"publications=$publications handoffs=$handoffs payload_write_commits=${writes.size} payload_fragments=$payloadFragments " +
        s"sidecar_fragments=$sidecarFragments consumer_commits=$consumers terminals_ok=$terminalsOk terminals_fault=$terminalsFault " +
        s"source_releases=$releases s2_generation=${uint(d.observation.s2_slot_generation)} " +
        s"page_generation=${pageGeneration.get} retired=1 reclaimed=1 no_memory_fault=1 " + Scope
    }
    def badAttention(caseName: String, rid: Int, layer: Int = 0, pageGen: BigInt = 0,
                     coordinate: BigInt = 1, sourceGen: Int = 2): Unit = {
      assert(terminalsOk == 1 && pageGeneration.contains(BigInt(0)))
      d.observation.page0_readable.expect(true.B)
      val beforeFault = terminalsFault; val beforeReads = readRequests; val beforeRelease = releases; val beforeConsumers = consumers
      lifecycle(p.r6.attentionServiceEventCode, rid, layer = layer, position = 129)
      select(rid, pageGen); plan(rid, sourceGen, coordinate)
      consumeTerminal(rid, p.coreMemoryFaultStatusCode)
      assert(terminalsFault == beforeFault + 1 && readRequests == beforeReads && releases == beforeRelease && consumers == beforeConsumers)
      d.observation.s2_any_live.expect(false.B); d.observation.s2_slot_generation.expect(1.U)
      println(s"KVZAP_PERSISTENT_READ_RESULT case=$caseName outcome=PASS fault_delta=1 read_delta=0 release_delta=0 " +
        "consumer_delta=0 live_after=0 slot_state_after=0 first_terminal_ok=1 page_live=1 s2_generation=1 " + Scope)
    }
    def foreignDeclaration(): Unit = {
      val beforeReject = rejected; val beforeFault = terminalsFault; val beforeReads = readRequests
      val beforeConsumers = consumers; val beforeRelease = releases
      // No accepted attention with RID7 exists. A runtime declaration cannot make one.
      plan(7, sourceGeneration = 2)
      until("foreign declaration was not explicitly rejected")(rejected == beforeReject + 1)
      (0 until 32).foreach(_ => tick())
      assert(terminalsFault == beforeFault && readRequests == beforeReads && consumers == beforeConsumers && releases == beforeRelease)
      d.observation.attention_live.expect(false.B); d.observation.s2_any_live.expect(false.B)
      d.observation.preflight_busy.expect(false.B); d.observation.declaration_live.expect(false.B)
      assert(rejected == beforeReject + 1, "foreign declaration must cause one local rejection")
      d.io.attention_terminal_rsp.valid.expect(false.B)
      println("KVZAP_PERSISTENT_READ_RESULT case=FOREIGN_DECLARATION outcome=PASS fault_delta=0 read_delta=0 " +
        "release_delta=0 consumer_delta=0 live_after=0 slot_state_after=0 reject_delta=1 first_terminal_ok=1 page_live=1 " + Scope)
    }
  }

  it("reads one genuinely packed page twice and retires after both transient services drain") {
    simulate(new RouteAPersistentPageReadHarness(p)) { d =>
      val x = new Driver(d); x.publishOne()
      x.beginRead(rid = 3, generation = 1); x.completeRead(rid = 3, generation = 1)
      d.observation.r6_state.expect(2.U); d.observation.page0_readable.expect(true.B)
      x.beginRead(rid = 5, generation = 2); x.completeRead(rid = 5, generation = 2)
      x.requestRetire(); x.finishRetire()
      println("KVZAP_PERSISTENT_READ_RESULT case=SAME_PAGE_TWICE outcome=PASS " + x.twoReadEvidence)
    }
  }

  it("terminates bad page owner and S2 selections without inventing service or foreign attention") {
    simulate(new RouteAPersistentPageReadHarness(p)) { d =>
      val x = new Driver(d); x.publishOne()
      x.beginRead(rid = 3, generation = 1); x.completeRead(rid = 3, generation = 1)
      x.badAttention("BAD_PAGE_GENERATION", rid = 4, pageGen = 1)
      x.badAttention("BAD_OWNER", rid = 5, layer = 1)
      x.badAttention("BAD_S2_SLOT", rid = 6, coordinate = BigInt(1) << 20)
      x.badAttention("BAD_S2_GENERATION", rid = 1, sourceGen = 0)
      x.foreignDeclaration()
      // Failures must not consume the next legal S2 generation or prevent recovery.
      x.beginRead(rid = 2, generation = 2); x.completeRead(rid = 2, generation = 2)
      assert(x.terminalsOk == 2 && x.terminalsFault == 4)
      x.requestRetire(); x.finishRetire()
    }
  }

  it("finishes accepted preflight while retiring and only then permits page reclaim") {
    simulate(new RouteAPersistentPageReadHarness(p)) { d =>
      val x = new Driver(d); x.publishOne()
      x.beginRead(rid = 3, generation = 1); x.completeRead(rid = 3, generation = 1)
      x.lifecycle(p.r6.attentionServiceEventCode, rid = 5, position = 130)
      x.plan(rid = 5, sourceGeneration = 2)
      d.observation.attention_live.expect(true.B); d.observation.s2_any_live.expect(false.B)
      assert(x.payloadFragments == 8 && x.terminalsOk == 1)
      // This work has been accepted, but no selector/query/lease can yet complete.
      x.requestRetire(); d.observation.r6_state.expect(3.U)
      (0 until 16).foreach { _ =>
        d.io.session_retire_ack.valid.expect(false.B)
        d.observation.page0_readable.expect(true.B); x.tick()
      }
      x.select(5, x.pageGeneration.get)
      x.completeRead(rid = 5, generation = 2); x.finishRetire()
      println("KVZAP_PERSISTENT_READ_RESULT case=RETIRE_DURING_PREFLIGHT outcome=PASS " +
        "attention_accepted_before_retire=1 preflight_incomplete_at_retire=1 " + x.twoReadEvidence)
    }
  }
}
