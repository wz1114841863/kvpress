package kvpress.routea

import chisel3.simulator.scalatest.ChiselSim
import kvpress.routea.params.{RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.FullKVMeasurementDut
import org.scalatest.funspec.AnyFunSpec

/** W0 elaboration smoke test; directed transaction coverage is added with W0 composition. */
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

  it("elaborates the baseline-local Full-KV control contour") {
    simulate(new FullKVMeasurementDut(p)) { dut => dut.clock.step() }
  }
}
