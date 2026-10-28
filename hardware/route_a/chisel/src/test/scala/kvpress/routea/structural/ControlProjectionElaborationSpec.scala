package kvpress.routea.structural

import circt.stage.ChiselStage
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.{FullKVControlProjectionGenerator, RouteAControlProjectionGenerator}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

/**
  * Parameterized projection-elaboration guard.  The values below are the
  * bounded paired 9-bit functional profile only; no source imports them as a
  * synthesis/deployment default and this test writes no HDL artifact.
  */
final class ControlProjectionElaborationSpec extends AnyFlatSpec with Matchers {
  private val pairedFunctionalParameters = RouteASkeletonParameters(
    frontendEventKindWidth = 3, componentStatusNameWidth = 4, hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1, pendingValidityWidth = 1, candidateClassWidth = 3,
    candidateOrdinalWidth = 4, candidateIdWidth = 4, candidatePredicateWidth = 10,
    r2S2FullClassCode = 0, r2S2PackedClassCode = 1, r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3, r2PackWriteClassCode = 4, r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2, coreMemoryRequestKindWidth = 3,
    coreMemoryDestinationWidth = 2, coreMemoryAddressRefWidth = 64,
    coreMemoryFragmentCountWidth = 10, coreMemoryFragmentIndexWidth = 9,
    coreMemoryReadRequestCode = 0, coreMemoryWriteRequestCode = 1,
    coreMemoryWriteDataCode = 2, coreMemoryOkStatusCode = 0, coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 2, transactionGroupTagWidth = 2, p3StageGenerationWidth = 2,
    r5AllocatorEntries = 8, r5StreamSlots = 8, sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  behavior of "paired synthesis-control projections"

  it should "elaborate both parameterized projections without a functional reference child" in {
    val fullKv = ChiselStage.emitCHIRRTL(
      FullKVControlProjectionGenerator.construct(pairedFunctionalParameters),
    )
    val routeA = ChiselStage.emitCHIRRTL(
      RouteAControlProjectionGenerator.construct(pairedFunctionalParameters),
    )

    fullKv should include("module full_kv_control_projection")
    routeA should include("module route_a_control_projection")
    routeA should include("route_a_r4_external_protocol_adapter")
    routeA should not include "route_a_functional_sidecar_delivery_adapter"
    routeA should not include "route_a_functional_partial_provider_boundary"
    routeA should not include "route_a_functional_r4_reference_boundary"
    Seq(
      "functional_sidecar_work_out",
      "functional_sidecar_payload_release_out",
      "functional_sidecar_registry_allocate_in",
      "functional_sidecar_registry_allocation_ack_out",
      "functional_sidecar_read_issue_in",
      "functional_r4_accepted_packet_out",
      "functional_r4_merge_work_out",
      "functional_r4_result_in",
      "functional_r4_numeric_fault_in",
    ).foreach(routeA should include(_))
  }
}
