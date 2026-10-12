package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.common.RouteAFunctionalPartialProviderBoundary
import kvpress.routea.interfaces.{RouteASourceKind, SourceServicePartialOffer, SourceServiceValueFragment}
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/** RTL3.8.3 boundary-only tests; they perform no attention arithmetic. */
final class RouteAFunctionalPartialProviderBoundarySpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1,
    candidateClassWidth = 3, candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3, coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  private def offer(bits: SourceServicePartialOffer, kind: Int): Unit = {
    bits.transaction_identity.request_id.poke(3.U); bits.transaction_identity.incarnation.poke(1.U)
    bits.source_instance.source_kind.poke(kind.U); bits.source_instance.instance_coordinate.poke(1.U)
    bits.source_instance.generation.poke(2.U); bits.consumer_id.poke(0.U)
    bits.r4_header.poke("h2".U)
    bits.partial_present.poke(true.B)
  }
  private def fragment(bits: SourceServiceValueFragment, kind: Int): Unit = {
    bits.transaction_identity.request_id.poke(3.U); bits.transaction_identity.incarnation.poke(1.U)
    bits.source_instance.source_kind.poke(kind.U); bits.source_instance.instance_coordinate.poke(1.U)
    bits.source_instance.generation.poke(2.U); bits.consumer_id.poke(2.U)
    bits.fragment_index.poke(7.U); bits.last.poke(true.B); bits.data.poke("h55".U)
  }

  private def idle(d: RouteAFunctionalPartialProviderBoundary): Unit = {
    d.io.hot_offer_in.valid.poke(false.B); d.io.pending_offer_in.valid.poke(false.B); d.io.packed_offer_in.valid.poke(false.B)
    d.io.hot_fragment_in.valid.poke(false.B); d.io.pending_fragment_in.valid.poke(false.B); d.io.packed_fragment_in.valid.poke(false.B)
    d.io.hot_offer_out.ready.poke(false.B); d.io.pending_offer_out.ready.poke(false.B); d.io.packed_offer_out.ready.poke(false.B)
    d.io.hot_fragment_out.ready.poke(false.B); d.io.pending_fragment_out.ready.poke(false.B); d.io.packed_fragment_out.ready.poke(false.B)
  }

  it("forwards a stalled hot offer exactly without selecting or computing a partial") {
    simulate(new RouteAFunctionalPartialProviderBoundary(p)) { d =>
      idle(d); offer(d.io.hot_offer_in.bits, RouteASourceKind.Hot); d.io.hot_offer_in.valid.poke(true.B)
      d.io.hot_offer_out.valid.expect(true.B); d.io.hot_offer_out.bits.transaction_identity.request_id.expect(3.U)
      d.io.hot_offer_out.bits.source_instance.source_kind.expect(RouteASourceKind.Hot.U)
      d.clock.step(); d.io.hot_offer_out.valid.expect(true.B)
      d.io.hot_offer_out.bits.r4_header.expect("h2".U)
      d.io.hot_offer_out.ready.poke(true.B); d.io.hot_offer_in.ready.expect(true.B); d.clock.step()
    }
  }

  it("keeps each source lane distinct while forwarding a packed value fragment") {
    simulate(new RouteAFunctionalPartialProviderBoundary(p)) { d =>
      idle(d); fragment(d.io.packed_fragment_in.bits, RouteASourceKind.Packed)
      d.io.packed_fragment_in.valid.poke(true.B); d.io.packed_fragment_out.ready.poke(true.B)
      d.io.packed_fragment_out.valid.expect(true.B); d.io.packed_fragment_out.bits.source_instance.source_kind.expect(RouteASourceKind.Packed.U)
      d.io.packed_fragment_out.bits.consumer_id.expect(2.U); d.io.packed_fragment_out.bits.fragment_index.expect(7.U)
      d.io.hot_fragment_out.valid.expect(false.B); d.io.pending_fragment_out.valid.expect(false.B)
      d.io.packed_fragment_in.ready.expect(true.B); d.clock.step()
    }
  }
}
