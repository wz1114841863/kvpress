package kvpress.routea

import chisel3.simulator.scalatest.ChiselSim
import java.nio.file.{Files, Paths}
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.{FullKVMeasurementDut, RouteAMeasurementDut}
import org.scalatest.funspec.AnyFunSpec

/** W0 composition smoke check: both independent contours elaborate. */
final class DualMeasurementDutStructuralSpec extends AnyFunSpec with ChiselSim {
  private val p = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 2, candidateIdWidth = 2, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1, coreMemoryRequestKindWidth = 3,
    coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 8,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1, coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1, sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1, p3StageGenerationWidth = 1, r5AllocatorEntries = 8,
    r5StreamSlots = 8, sourceGenerationWidth = 2, r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  it("elaborates independent Full-KV and Route-A measurement contours") {
    simulate(new FullKVMeasurementDut(p))(_.clock.step())
    simulate(new RouteAMeasurementDut(p))(_.clock.step())
  }

  it("keeps W0-R1 authorization owner-to-owner rather than at the DUT boundary") {
    val source = Files.readString(Paths.get(
      "src/main/scala/kvpress/routea/top/RouteAMeasurementDut.scala",
    ))
    assert(!source.contains("RouteAKVSubsystemTop"))
    assert(!source.contains("StructuralTieOff."))
    Seq(
      "packed_demand_in",
      "publication_authorization_in",
      "descriptor_grant_in",
      "owner_s2_lease_in",
    ).foreach(port => assert(!source.contains(s"val $port ="),
      s"legacy outer authorization remains at DUT IO: $port"))
    Seq(
      "planFork.io.accepted_plan_in <> lifecycle.io.source_completion_plan_copy_out",
      "activationBinder.io.publication_member_in <> m2P3.io.publication_member_observation",
      "activationBinder.io.post_r6_page_ready_in <> m2P3.io.post_r6_packed_page_ready_observation",
      "pageManager.io.descriptor_location_request_in <> activationBinder.io.descriptor_location_request_out",
      "delivery.io.r3_packed_write_in <> m2P3.io.p3_packed_write_candidate_out",
      "m2P3.io.p3_packed_write_delivery_in <> router.io.r3_packed_write_out",
      "lifecycle.io.packed_source_release_in <> s2.io.s2_release_out",
      "lifecycle.io.merge_terminal_in <> merge.io.merge_rsp_or_numeric_fault",
      "delivery.io.r5_reclaim_in <> pageManager.io.reclaim_candidate_out",
      "pageManager.io.reclaim_delivery_in <> router.io.r5_reclaim_out",
      "pendingDescriptorOwner.io.registration_in <> io.pending_source_descriptor_registration_in",
      "pendingDescriptorOwner.io.association_query_in <> sourcePlanBinder.io.association_query_out",
      "sourcePlanBinder.io.association_declaration_in <> pendingDescriptorOwner.io.association_declaration_out",
      "directAssociationMaterializer.io.accepted_association_in <> sourcePlanBinder.io.accepted_pending_association_out",
      "directPending.io.pending_source_open_in <> directAssociationMaterializer.io.direct_open_out",
      "directAssociationMaterializer.io.direct_open_ack_in <> directPending.io.pending_source_open_ack_out",
      "directPendingProducer.io.work_in <> directAssociationMaterializer.io.direct_work_out",
      "delivery.io.r3_direct_pending_in <> directPendingIssue.io.candidate_out",
      "readIngress.io.r3_direct_pending_in <> delivery.io.r3_direct_pending_out",
      "directPendingReadEndpoint.io.resolved_fragment_in <> endpointDemux.io.direct_pending_out",
    ).foreach(connection => assert(source.contains(connection), s"missing W0-R1 connection: $connection"))
  }
}
