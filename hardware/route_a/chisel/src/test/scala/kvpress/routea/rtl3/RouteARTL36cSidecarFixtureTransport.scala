package kvpress.routea.rtl3

import chisel3._
import chisel3.util.{Enum, RegEnable, log2Ceil}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec
import chisel3.simulator.scalatest.ChiselSim

/** Test-only projection of an already accepted RTL3.2 packed-read allocation. */
final class RouteARTL36cSidecarFixtureObligation(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
  val sidecar_handle_or_address = UInt(p.coreMemoryAddressRefWidth.W)
  val sidecar_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
}

/**
  * Testbench-only lossless allocation fanout. It observes no descriptor image
  * and derives no address: `descriptor_line`, page/slot/generation, and the
  * frozen eight-fragments-per-record count are copied from the accepted
  * RTL3.2 allocation into a sidecar-fixture obligation.
  */
final class RouteARTL36cAllocationSidecarTap(p: RouteASkeletonParameters) extends Module {
  override def desiredName: String = "testbench_route_a_rtl3_6c_allocation_sidecar_tap"
  val io = IO(new Bundle {
    val allocation_in = Flipped(RouteAChannels.delivery_context_allocate(p))
    val registry_allocation_out = RouteAChannels.delivery_context_allocate(p)
    val sidecar_obligation_out = chisel3.util.Decoupled(new RouteARTL36cSidecarFixtureObligation(p))
    val invalid_obligation = Output(Bool())
  })

  val held = Reg(new DeliveryContextAllocation(p))
  val haveHeld = RegInit(false.B)
  val registrySent = RegInit(false.B)
  val obligationSent = RegInit(false.B)
  val obligationLegal = RegInit(false.B)
  val fragments = io.allocation_in.bits.expected_fragment_count
  val records = fragments >> 3
  val incomingLegal = io.allocation_in.bits.candidate_class === p.r2S2PackedClassCode.U &&
    io.allocation_in.bits.target_kind === RouteADeliveryTargetKind.S2PackedFill.U &&
    io.allocation_in.bits.target_descriptor.requires_sidecar &&
    fragments =/= 0.U && fragments(2, 0) === 0.U && records <= 64.U

  io.allocation_in.ready := !haveHeld
  io.registry_allocation_out.valid := haveHeld && !registrySent
  io.registry_allocation_out.bits := held
  io.sidecar_obligation_out.valid := haveHeld && obligationLegal && !obligationSent
  io.sidecar_obligation_out.bits.transaction_identity := held.transaction_identity
  io.sidecar_obligation_out.bits.page_ref := held.target_descriptor.descriptor_page_ref
  io.sidecar_obligation_out.bits.s2_slot := held.target_descriptor.s2_slot
  io.sidecar_obligation_out.bits.source_generation := held.target_descriptor.source_generation
  io.sidecar_obligation_out.bits.sidecar_handle_or_address := held.target_descriptor.descriptor_line
  io.sidecar_obligation_out.bits.sidecar_records := held.expected_fragment_count >> 3
  io.invalid_obligation := haveHeld && !obligationLegal

  when(io.allocation_in.fire) {
    held := io.allocation_in.bits
    haveHeld := true.B
    registrySent := false.B
    obligationSent := false.B
    obligationLegal := incomingLegal
  }
  when(io.registry_allocation_out.fire) { registrySent := true.B }
  when(io.sidecar_obligation_out.fire) { obligationSent := true.B }
  when(haveHeld && (registrySent || io.registry_allocation_out.fire) &&
    (!obligationLegal || obligationSent || io.sidecar_obligation_out.fire)) {
    haveHeld := false.B
  }

  val heldRegistry = RegEnable(io.registry_allocation_out.bits,
    io.registry_allocation_out.valid && !io.registry_allocation_out.ready)
  when(RegNext(io.registry_allocation_out.valid && !io.registry_allocation_out.ready, false.B)) {
    assert(io.registry_allocation_out.valid && io.registry_allocation_out.bits.asUInt === heldRegistry.asUInt)
  }
  val heldObligation = RegEnable(io.sidecar_obligation_out.bits,
    io.sidecar_obligation_out.valid && !io.sidecar_obligation_out.ready)
  when(RegNext(io.sidecar_obligation_out.valid && !io.sidecar_obligation_out.ready, false.B)) {
    assert(io.sidecar_obligation_out.valid && io.sidecar_obligation_out.bits.asUInt === heldObligation.asUInt)
  }
}

/** Immutable test fixture, deliberately not a sidecar physical layout. */
final case class RouteARTL36cSidecarFixture(handle: BigInt, records: Vector[BigInt]) {
  require(handle >= 0 && records.nonEmpty && records.size <= 64 && records.forall(_ >= 0))
}
object RouteARTL36cSidecarFixture {
  val Default: RouteARTL36cSidecarFixture = RouteARTL36cSidecarFixture(BigInt(0xaa), Vector(BigInt(0x900), BigInt(0x901)))
}

/**
  * Named testbench-only sidecar transport owner. It consumes one exact
  * obligation, waits for the matching S2 FILLING/fill-open observation, and
  * replays its fixture's position records followed by one complete event.
  * A bad fixture handle/count or stale S2 observation enters fail-closed
  * state and cannot write a sidecar fragment or make S2 READY.
  */
final class RouteARTL36cSidecarFixtureTransport(
    p: RouteASkeletonParameters,
    fixture: RouteARTL36cSidecarFixture = RouteARTL36cSidecarFixture.Default,
) extends Module {
  override def desiredName: String = "testbench_route_a_rtl3_6c_sidecar_fixture_transport"
  val io = IO(new Bundle {
    val obligation_in = Flipped(chisel3.util.Decoupled(new RouteARTL36cSidecarFixtureObligation(p)))
    val observed_filling = Input(Bool())
    val observed_fill_open = Input(Bool())
    val observed_identity = Input(new TransactionIdentity)
    val observed_page_ref = Input(new PageRef)
    val observed_generation = Input(UInt(p.sourceGenerationWidth.W))
    val sidecar_fragment_out = RouteAChannels.s2_sidecar_fragment(p)
    val sidecar_complete_out = RouteAChannels.s2_sidecar_complete(p)
    val complete = Output(Bool())
    val faulted = Output(Bool())
  })

  val idle :: waitForFill :: fragments :: complete :: done :: faulted :: Nil = Enum(6)
  val state = RegInit(idle)
  val obligation = Reg(new RouteARTL36cSidecarFixtureObligation(p))
  val ordinal = RegInit(0.U(RouteAAnchorWidths.P3ValidRecordsWidth.W))
  val data = VecInit(fixture.records.map(_.U(64.W)))
  private val fixtureIndexWidth = math.max(1, log2Ceil(fixture.records.size))
  private val selectedFixtureData = if (fixture.records.size == 1) {
    fixture.records.head.U(64.W)
  } else {
    data(ordinal(fixtureIndexWidth - 1, 0))
  }

  private def sameIdentity(left: TransactionIdentity, right: TransactionIdentity): Bool = left.asUInt === right.asUInt
  private def samePage(left: PageRef, right: PageRef): Bool = left.asUInt === right.asUInt
  val fixtureMatches = io.obligation_in.bits.sidecar_handle_or_address === fixture.handle.U &&
    io.obligation_in.bits.sidecar_records === fixture.records.size.U
  io.obligation_in.ready := state === idle
  when(io.obligation_in.fire) {
    obligation := io.obligation_in.bits
    when(fixtureMatches) { state := waitForFill }.otherwise { state := faulted }
  }

  val observationMatches = io.observed_filling && io.observed_fill_open &&
    sameIdentity(io.observed_identity, obligation.transaction_identity) &&
    samePage(io.observed_page_ref, obligation.page_ref) &&
    io.observed_generation === obligation.source_generation
  when(state === waitForFill && io.observed_filling && io.observed_fill_open) {
    when(observationMatches) { state := fragments }.otherwise { state := faulted }
  }

  io.sidecar_fragment_out.valid := state === fragments
  io.sidecar_fragment_out.bits.transaction_identity := obligation.transaction_identity
  io.sidecar_fragment_out.bits.s2_slot := obligation.s2_slot
  io.sidecar_fragment_out.bits.source_generation := obligation.source_generation
  io.sidecar_fragment_out.bits.record_ordinal := ordinal
  io.sidecar_fragment_out.bits.data := selectedFixtureData
  when(io.sidecar_fragment_out.fire) {
    when(ordinal === (fixture.records.size - 1).U) { state := complete }
      .otherwise { ordinal := ordinal + 1.U }
  }

  io.sidecar_complete_out.valid := state === complete
  io.sidecar_complete_out.bits.transaction_identity := obligation.transaction_identity
  io.sidecar_complete_out.bits.s2_slot := obligation.s2_slot
  io.sidecar_complete_out.bits.source_generation := obligation.source_generation
  when(io.sidecar_complete_out.fire) { state := done }
  io.complete := state === done
  io.faulted := state === faulted

  val heldFragment = RegEnable(io.sidecar_fragment_out.bits,
    io.sidecar_fragment_out.valid && !io.sidecar_fragment_out.ready)
  when(RegNext(io.sidecar_fragment_out.valid && !io.sidecar_fragment_out.ready, false.B)) {
    assert(io.sidecar_fragment_out.valid && io.sidecar_fragment_out.bits.asUInt === heldFragment.asUInt)
  }
  val heldComplete = RegEnable(io.sidecar_complete_out.bits,
    io.sidecar_complete_out.valid && !io.sidecar_complete_out.ready)
  when(RegNext(io.sidecar_complete_out.valid && !io.sidecar_complete_out.ready, false.B)) {
    assert(io.sidecar_complete_out.valid && io.sidecar_complete_out.bits.asUInt === heldComplete.asUInt)
  }
  assert(!(io.sidecar_fragment_out.valid && io.sidecar_complete_out.valid))
}

/** Narrow C1 fail-closed tests; no controller or physical-memory claim. */
final class RouteARTL36cSidecarFixtureTransportSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=32, coreMemoryFragmentCountWidth=10, coreMemoryFragmentIndexWidth=9,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=2, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=kvpress.routea.params.RouteAR6Encoding.testOnlyAnchor)
  private def identity(x: TransactionIdentity, request: Int = 3): Unit = { x.request_id.poke(request.U); x.incarnation.poke(1.U) }
  private def page(x: PageRef): Unit = { x.page_id.poke(7.U); x.generation.poke(1.U) }
  private def init(d: RouteARTL36cSidecarFixtureTransport): Unit = {
    d.io.obligation_in.valid.poke(false.B); d.io.observed_filling.poke(false.B); d.io.observed_fill_open.poke(false.B)
    identity(d.io.observed_identity); page(d.io.observed_page_ref); d.io.observed_generation.poke(1.U)
    d.io.sidecar_fragment_out.ready.poke(false.B); d.io.sidecar_complete_out.ready.poke(false.B)
  }
  private def obligation(d: RouteARTL36cSidecarFixtureTransport, handle: Int = 0xaa, records: Int = 2): Unit = {
    identity(d.io.obligation_in.bits.transaction_identity); page(d.io.obligation_in.bits.page_ref)
    d.io.obligation_in.bits.s2_slot.poke(0.U); d.io.obligation_in.bits.source_generation.poke(1.U)
    d.io.obligation_in.bits.sidecar_handle_or_address.poke(handle.U); d.io.obligation_in.bits.sidecar_records.poke(records.U)
    d.io.obligation_in.valid.poke(true.B); d.io.obligation_in.ready.expect(true.B); d.clock.step(); d.io.obligation_in.valid.poke(false.B)
  }
  it("fails closed on an unbound sidecar handle and does not emit a completion") { simulate(new RouteARTL36cSidecarFixtureTransport(p)) { d =>
    init(d); obligation(d, handle=0xab); d.io.faulted.expect(true.B); d.io.sidecar_fragment_out.valid.expect(false.B); d.io.sidecar_complete_out.valid.expect(false.B)
  } }
  it("fails closed when a stale observed generation reaches an otherwise valid fixture obligation") { simulate(new RouteARTL36cSidecarFixtureTransport(p)) { d =>
    init(d); obligation(d); d.io.observed_filling.poke(true.B); d.io.observed_fill_open.poke(true.B); d.io.observed_generation.poke(2.U); d.clock.step()
    d.io.faulted.expect(true.B); d.io.sidecar_fragment_out.valid.expect(false.B); d.io.sidecar_complete_out.valid.expect(false.B)
  } }
}
