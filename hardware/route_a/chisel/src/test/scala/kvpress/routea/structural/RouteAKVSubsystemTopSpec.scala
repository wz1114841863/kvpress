package kvpress.routea.structural

import circt.stage.ChiselStage
import kvpress.routea.params.{RouteAAnchorWidths, RouteAR6Encoding, RouteASkeletonParameters}
import kvpress.routea.top.RouteAKVSubsystemTop
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

/**
  * RTL1.0 structural check only. The opaque widths below are elaboration-local
  * test values, not a deployed encoding, queue depth, controller parameter, or
  * revision of the RTL0.2 logical port contract.
  */
final class RouteAKVSubsystemTopSpec extends AnyFlatSpec with Matchers {
  private val structuralTestParameters = RouteASkeletonParameters(
    frontendEventKindWidth = 3,
    componentStatusNameWidth = 4,
    hotControlKindWidth = 2,
    pendingDescriptorRefWidth = 1,
    pendingValidityWidth = 1,
    candidateClassWidth = 3,
    candidateOrdinalWidth = 1,
    candidateIdWidth = 1,
    candidatePredicateWidth = 10,
    r2S2FullClassCode = 0,
    r2S2PackedClassCode = 1,
    r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3,
    r2PackWriteClassCode = 4,
    r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 1,
    coreMemoryRequestKindWidth = 3,
    coreMemoryDestinationWidth = 2,
    coreMemoryAddressRefWidth = 1,
    coreMemoryFragmentCountWidth = 1,
    coreMemoryFragmentIndexWidth = 1,
    coreMemoryReadRequestCode = 0,
    coreMemoryWriteRequestCode = 1,
    coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0,
    coreMemoryFaultStatusCode = 1,
    sourceDeliveryOpaqueWidth = 1,
    transactionGroupTagWidth = 1,
    p3StageGenerationWidth = 1,
    r5AllocatorEntries = 8,
    r5StreamSlots = 8,
    sourceGenerationWidth = 2,
    r6 = RouteAR6Encoding.testOnlyAnchor,
  )

  behavior of "RouteAKVSubsystemTop RTL1.0 structural skeleton"

  it should "elaborate every frozen hierarchy module after the R1 behavioral replacement" in {
    val chirrtl = ChiselStage.emitCHIRRTL(new RouteAKVSubsystemTop(structuralTestParameters))
    val systemVerilog = ChiselStage.emitSystemVerilog(new RouteAKVSubsystemTop(structuralTestParameters))

    Seq(
      "route_a_kv_subsystem_top",
      "route_a_lifecycle_adapter",
      "route_a_hot_source_path",
      "route_a_s2_gqa_source_wrapper",
      "route_a_direct_pending_endpoint_v1",
      "route_a_core_side_arbiter",
      "route_a_core_mem_if_v1",
      "route_a_m2_p3_wrapper",
      "route_a_page_manager",
      "route_a_admission_publication_ingress_adapter",
      "route_a_source_plan_binder",
      "route_a_source_service_packet_adapter",
      "route_a_source_commit_demultiplexer",
      "route_a_merge_boundary",
      "route_a_component_status_collector",
    ).foreach { moduleName =>
      chirrtl should include(s"module $moduleName")
    }

    Seq(
      "frontend_lifecycle_req",
      "runtime_retire_req",
      "source_plan_declaration_in",
      "attention_terminal_rsp",
      "session_retire_ack",
      "component_status_in",
      "hot_control_out",
      "s2_service_req",
      "direct_pending_open",
      "source_partial_to_merge",
      "consumer_partial_commit",
      "merge_req",
      "merge_rsp_or_numeric_fault",
      "reclaim_permit_out",
      "reclaim_candidate_out",
      "core_mem_req",
      "core_mem_rsp",
      "external_core_mem_if_v1",
      "source_delivery_out",
      "metadata_publish_req",
      "metadata_publish_visibility_apply",
      "metadata_publish_visibility_ack",
      "m2_publish_ack",
    ).foreach { manifestPortName =>
      chirrtl should include(manifestPortName)
    }

    systemVerilog should include("core_clk")
    systemVerilog should include("destructive_reset")
    systemVerilog should include("frontend_lifecycle_req_valid")
    systemVerilog should include("runtime_retire_req_valid")
    systemVerilog should include("attention_terminal_rsp_valid")
    systemVerilog should include("session_retire_ack_valid")
    systemVerilog should include("external_core_mem_if_v1_init_ack_ready")
    systemVerilog should include("external_core_mem_if_v1_request_valid")
    systemVerilog should include("source_packet_adapter")
    chirrtl should include("packed_observe_slot_out")
  }

  it should "preserve the selected, non-opaque Route-A anchor widths" in {
    RouteAAnchorWidths.RequestIdWidth shouldBe 3
    RouteAAnchorWidths.IncarnationWidth shouldBe 2
    RouteAAnchorWidths.PageIdWidth shouldBe 18
    RouteAAnchorWidths.PageGenerationWidth shouldBe 8
    RouteAAnchorWidths.CoreDataWidth shouldBe 512
    RouteAAnchorWidths.MergePartialHeaderWidth shouldBe 128
    RouteAAnchorWidths.MergeValueFragmentWidth shouldBe 512
    RouteAAnchorWidths.NormalizedValueWidth shouldBe 4096
  }

  it should "reject an unspecified opaque logical-field width" in {
    an[IllegalArgumentException] should be thrownBy {
      structuralTestParameters.copy(transactionGroupTagWidth = 0)
    }
  }
}
