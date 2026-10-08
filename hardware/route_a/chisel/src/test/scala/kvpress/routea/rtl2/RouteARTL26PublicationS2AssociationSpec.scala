package kvpress.routea.rtl2

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import chisel3.util.{Decoupled, RegEnable}
import kvpress.routea.interfaces._
import kvpress.routea.params.{RouteAAnchorWidths, RouteAR6Encoding, RouteASkeletonParameters}
import org.scalatest.funspec.AnyFunSpec

/**
  * Explicit testbench association required to join R3's publication-only
  * carrier with an attention request identity and selected S2 slot.  R3's
  * carrier intentionally does not contain either of those fields.  This
  * bundle is verification scope only and is not a production read scheduler.
  */
final class VerificationPackedS2Association(p: RouteASkeletonParameters) extends Bundle {
  val transaction_identity = new TransactionIdentity
  val page_ref = new PageRef
  val transaction_group_tag = UInt(p.transactionGroupTagWidth.W)
  val valid_records = UInt(RouteAAnchorWidths.P3ValidRecordsWidth.W)
  val s2_slot = UInt(RouteAAnchorWidths.S2SlotWidth.W)
  val source_generation = UInt(p.sourceGenerationWidth.W)
}

/**
  * RTL2.6.3 test-only carrier join.  A service request exists only after the
  * real R3 publication observation, the matching real R3 pending-to-packed
  * authority event, and one explicitly supplied verification association.
  * It neither emits PackedS2ReadWork nor belongs in the production top.
  */
final class RouteARTL26PublicationS2Association(p: RouteASkeletonParameters) extends Module {
  val io = IO(new Bundle {
    val publicationCommitIn = Flipped(RouteAChannels.publication_commit_observation(p))
    val authorityTransitionIn = Flipped(RouteAChannels.r6_authority_transition(p))
    val verificationAssociationIn = Flipped(Decoupled(new VerificationPackedS2Association(p)))
    val s2ServiceOut = RouteAChannels.s2_service_req
  })

  val commitHeld = RegInit(false.B)
  val commit = Reg(new PublicationCommitObservation(p))
  val authorityHeld = RegInit(false.B)
  val serviceHeld = RegInit(false.B)
  val service = Reg(new S2ServiceRequest)

  io.publicationCommitIn.ready := !commitHeld && !serviceHeld
  when(io.publicationCommitIn.fire) {
    commit := io.publicationCommitIn.bits
    commitHeld := true.B
  }

  val authority = io.authorityTransitionIn.bits
  val authorityMatches = commitHeld && authority.transaction_group_tag === commit.transaction_group_tag &&
    authority.from_authority === RouteAAuthorityStateCode.Pending.U &&
    authority.to_authority === RouteAAuthorityStateCode.Packed.U
  io.authorityTransitionIn.ready := !authorityHeld && !serviceHeld && authorityMatches
  when(io.authorityTransitionIn.fire) { authorityHeld := true.B }

  val association = io.verificationAssociationIn.bits
  val associationMatches = commitHeld && authorityHeld && !serviceHeld &&
    association.page_ref.asUInt === commit.page_ref.asUInt &&
    association.transaction_group_tag === commit.transaction_group_tag &&
    association.valid_records === commit.valid_records
  io.verificationAssociationIn.ready := associationMatches
  when(io.verificationAssociationIn.fire) {
    service.transaction_identity := association.transaction_identity
    service.page_ref := association.page_ref
    service.s2_slot := association.s2_slot
    serviceHeld := true.B
  }

  io.s2ServiceOut.valid := serviceHeld
  io.s2ServiceOut.bits := service
  when(io.s2ServiceOut.fire) { serviceHeld := false.B; commitHeld := false.B; authorityHeld := false.B }

  val heldService = RegEnable(io.s2ServiceOut.bits, io.s2ServiceOut.valid && !io.s2ServiceOut.ready)
  when(RegNext(io.s2ServiceOut.valid && !io.s2ServiceOut.ready, false.B)) {
    assert(io.s2ServiceOut.bits.asUInt === heldService.asUInt)
  }
}

final class RouteARTL26PublicationS2AssociationSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth=3, componentStatusNameWidth=4, hotControlKindWidth=2, pendingDescriptorRefWidth=1, pendingValidityWidth=1,
    candidateClassWidth=3, candidateOrdinalWidth=4, candidateIdWidth=4, candidatePredicateWidth=10,
    r2S2FullClassCode=0, r2S2PackedClassCode=1, r2DirectPendingClassCode=2, r2PackReadClassCode=3, r2PackWriteClassCode=4, r2DescriptorMaintenanceClassCode=5, r2CandidateSlotsPerClass=2,
    coreMemoryRequestKindWidth=3, coreMemoryDestinationWidth=2, coreMemoryAddressRefWidth=8, coreMemoryFragmentCountWidth=3, coreMemoryFragmentIndexWidth=3,
    coreMemoryReadRequestCode=0, coreMemoryWriteRequestCode=1, coreMemoryWriteDataCode=2, coreMemoryOkStatusCode=0, coreMemoryFaultStatusCode=1,
    sourceDeliveryOpaqueWidth=1, transactionGroupTagWidth=2, p3StageGenerationWidth=2, r5AllocatorEntries=8, r5StreamSlots=8, sourceGenerationWidth=2, r6=RouteAR6Encoding.testOnlyAnchor)

  private def init(d: RouteARTL26PublicationS2Association): Unit = {
    d.io.publicationCommitIn.valid.poke(false.B); d.io.authorityTransitionIn.valid.poke(false.B); d.io.verificationAssociationIn.valid.poke(false.B); d.io.s2ServiceOut.ready.poke(false.B)
  }
  private def publication(d: RouteARTL26PublicationS2Association, page: Int = 7, tag: Int = 1, records: Int = 1): Unit = {
    val x=d.io.publicationCommitIn.bits; x.p3_layer.poke(0.U); x.p3_stage_generation.poke(1.U); x.page_ref.page_id.poke(page.U); x.page_ref.generation.poke(1.U); x.transaction_group_tag.poke(tag.U); x.valid_records.poke(records.U)
    d.io.publicationCommitIn.valid.poke(true.B); d.io.publicationCommitIn.ready.expect(true.B); d.clock.step(); d.io.publicationCommitIn.valid.poke(false.B)
  }
  private def authority(d: RouteARTL26PublicationS2Association, tag: Int = 1, from: Int = RouteAAuthorityStateCode.Pending, to: Int = RouteAAuthorityStateCode.Packed): Unit = {
    val x=d.io.authorityTransitionIn.bits; x.entry_id.poke(0.U); x.from_authority.poke(from.U); x.to_authority.poke(to.U); x.transaction_group_tag.poke(tag.U)
    d.io.authorityTransitionIn.valid.poke(true.B)
  }
  private def association(d: RouteARTL26PublicationS2Association, rid: Int = 3, page: Int = 7, tag: Int = 1, records: Int = 1): Unit = {
    val x=d.io.verificationAssociationIn.bits; x.transaction_identity.request_id.poke(rid.U); x.transaction_identity.incarnation.poke(1.U); x.page_ref.page_id.poke(page.U); x.page_ref.generation.poke(1.U); x.transaction_group_tag.poke(tag.U); x.valid_records.poke(records.U); x.s2_slot.poke(0.U); x.source_generation.poke(1.U)
    d.io.verificationAssociationIn.valid.poke(true.B)
  }

  it("emits one stable S2 service request only after matching publication, authority, and explicit association") { simulate(new RouteARTL26PublicationS2Association(p)) { d =>
    init(d); publication(d); authority(d); d.io.authorityTransitionIn.ready.expect(true.B); d.clock.step(); d.io.authorityTransitionIn.valid.poke(false.B)
    association(d); d.io.verificationAssociationIn.ready.expect(true.B); d.clock.step(); d.io.verificationAssociationIn.valid.poke(false.B)
    d.io.s2ServiceOut.valid.expect(true.B); d.io.s2ServiceOut.bits.transaction_identity.request_id.expect(3.U); d.io.s2ServiceOut.bits.page_ref.page_id.expect(7.U)
    d.clock.step(); d.io.s2ServiceOut.valid.expect(true.B); d.io.s2ServiceOut.ready.poke(true.B); d.clock.step(); d.io.s2ServiceOut.ready.poke(false.B); d.io.s2ServiceOut.valid.expect(false.B)
  } }

  it("fails closed for stale authority or a mismatched page/tag/record association") { simulate(new RouteARTL26PublicationS2Association(p)) { d =>
    init(d); publication(d); authority(d, tag=0); d.io.authorityTransitionIn.ready.expect(false.B); d.io.authorityTransitionIn.valid.poke(false.B); d.io.s2ServiceOut.valid.expect(false.B)
  }; simulate(new RouteARTL26PublicationS2Association(p)) { d =>
    init(d); publication(d); authority(d); d.io.authorityTransitionIn.ready.expect(true.B); d.clock.step(); d.io.authorityTransitionIn.valid.poke(false.B)
    association(d, page=8); d.io.verificationAssociationIn.ready.expect(false.B); d.io.verificationAssociationIn.valid.poke(false.B)
    association(d, tag=0); d.io.verificationAssociationIn.ready.expect(false.B); d.io.verificationAssociationIn.valid.poke(false.B)
    association(d, records=2); d.io.verificationAssociationIn.ready.expect(false.B); d.io.verificationAssociationIn.valid.poke(false.B); d.io.s2ServiceOut.valid.expect(false.B)
  } }
}
