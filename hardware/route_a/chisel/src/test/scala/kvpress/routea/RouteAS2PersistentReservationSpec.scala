package kvpress.routea

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.{Decoupled, DecoupledIO}
import kvpress.routea.common.RouteAS2GqaSourceWrapper
import kvpress.routea.interfaces._
import org.scalatest.funspec.AnyFunSpec

/** The real S2 owner; the harness supplies only its ordinary reservation client. */
final class RouteAS2PersistentReservationHarness extends Module {
  private val p = RouteAPersistentPageReadTestParameters.small
  val io = IO(new Bundle {
    val reservation = Flipped(Decoupled(new S2FillLeaseRequest(p)))
    val result = Decoupled(new S2ReservationResultV2(p))
    val drain = Input(Bool())
    val state = Output(UInt(3.W))
    val generation = Output(UInt(p.sourceGenerationWidth.W))
  })
  val s2 = Module(new RouteAS2GqaSourceWrapper(p, persistentReadEnabled = true))
  private def inactive[T <: Data](channel: DecoupledIO[T]): Unit = {
    channel.valid := false.B; channel.bits := 0.U.asTypeOf(channel.bits)
  }
  private def sink[T <: Data](channel: DecoupledIO[T]): Unit = channel.ready := true.B
  s2.io.mem_init_done := true.B
  s2.io.drain_collection_enable := io.drain
  s2.io.s2_observe_slot := 1.U
  s2.persistentRead.get.v2_reservation_request_in <> io.reservation
  io.result <> s2.persistentRead.get.v2_reservation_result_out
  io.state := s2.io.s2_observe_state
  io.generation := s2.io.s2_observe_generation
  inactive(s2.io.service_req_in); inactive(s2.io.s2_fill_lease_request_in)
  sink(s2.io.s2_fill_lease_out); inactive(s2.io.s2_fill_open_in)
  inactive(s2.io.s2_payload_fragment_in); inactive(s2.io.s2_sidecar_fragment_in)
  inactive(s2.io.s2_fill_terminal_in); inactive(s2.io.s2_sidecar_complete_in)
  inactive(s2.io.s2_payload_read_req_in); sink(s2.io.s2_payload_read_rsp_out)
  inactive(s2.io.s2_sidecar_read_req_in); sink(s2.io.s2_sidecar_read_rsp_out)
  inactive(s2.io.gqa_consumer_commit_in); sink(s2.io.s2_release_out)
  sink(s2.io.component_status_out)
}

final class RouteAS2PersistentReservationSpec extends AnyFunSpec with ChiselSim {
  it("separates invalid from busy and holds a granted real reservation through response backpressure") {
    simulate(new RouteAS2PersistentReservationHarness) { d =>
      d.io.reservation.valid.poke(false.B); d.io.result.ready.poke(false.B); d.io.drain.poke(false.B)
      d.clock.step(2)
      def request(kind: Int, coordinate: BigInt, generation: Int, expected: Int): Unit = {
        val x = d.io.reservation.bits
        x.transaction_identity.request_id.poke(3.U); x.transaction_identity.incarnation.poke(0.U)
        x.page_ref.page_id.poke(0.U); x.page_ref.generation.poke(0.U)
        x.selected_instance.source_kind.poke(kind.U)
        x.selected_instance.instance_coordinate.poke(coordinate.U)
        x.selected_instance.generation.poke(generation.U)
        d.io.reservation.valid.poke(true.B)
        var cycles = 0
        while (!d.io.reservation.ready.peek().litToBoolean && cycles < 32) { d.clock.step(); cycles += 1 }
        d.io.reservation.ready.expect(true.B)
        d.clock.step(); d.io.reservation.valid.poke(false.B)
        d.io.result.valid.expect(true.B); d.io.result.bits.status.expect(expected.U)
      }
      def consume(): Unit = {
        d.io.result.ready.poke(true.B); d.clock.step(); d.io.result.ready.poke(false.B)
        d.io.result.valid.expect(false.B)
      }
      request(RouteASourceKind.Hot, 1, 1, S2ReservationStatusV2.Invalid)
      d.io.state.expect(0.U); d.io.generation.expect(0.U); consume()
      request(RouteASourceKind.Packed, 1, 2, S2ReservationStatusV2.Invalid)
      d.io.state.expect(0.U); d.io.generation.expect(0.U); consume()
      request(RouteASourceKind.Packed, BigInt(1) << 20, 1, S2ReservationStatusV2.Invalid)
      d.io.state.expect(0.U); d.io.generation.expect(0.U); consume()
      request(RouteASourceKind.Packed, 1, 1, S2ReservationStatusV2.Granted)
      d.io.state.expect(1.U); d.io.generation.expect(1.U)
      d.io.drain.poke(true.B)
      (0 until 16).foreach { _ =>
        d.io.result.valid.expect(true.B); d.io.result.bits.status.expect(S2ReservationStatusV2.Granted.U)
        d.io.result.bits.lease.transaction_identity.request_id.expect(3.U)
        d.io.result.bits.lease.page_ref.page_id.expect(0.U)
        d.io.result.bits.lease.page_ref.generation.expect(0.U)
        d.io.result.bits.lease.s2_slot.expect(1.U)
        d.io.result.bits.lease.source_generation.expect(1.U)
        d.io.result.bits.lease.requires_sidecar.expect(true.B)
        d.io.state.expect(1.U); d.io.generation.expect(1.U); d.clock.step()
      }
      consume()
      // A busy slot does not hide a definitively stale generation as backpressure.
      request(RouteASourceKind.Packed, 1, 1, S2ReservationStatusV2.Invalid)
      d.io.state.expect(1.U); d.io.generation.expect(1.U); consume()
      request(RouteASourceKind.Packed, 1, 2, S2ReservationStatusV2.Busy)
      d.io.state.expect(1.U); d.io.generation.expect(1.U); consume()
      println("KVZAP_PERSISTENT_READ_S2_OWNER_PASS invalid=4 busy=1 granted=1 held_cycles=16 generation=1 " +
        "R6_authorization_integration=WHOLE_DUT_TEST real_fill_or_reclaim=NOT_TESTED_IN_THIS_UNIT")
    }
  }
}
