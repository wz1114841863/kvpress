package kvpress.routea.params

/**
  * One explicit, bounded parameter profile for the paired synthesis-control
  * projections. It is intentionally named rather than made a default of
  * RouteASkeletonParameters: a different anchor must choose and record its
  * own capacities before elaboration.
  *
  * This profile is the Qwen3-8B, 32K-context, one-sequence A3 control anchor.
  * It selects logical control widths/capacities only. It selects neither a
  * memory macro, a physical port/latency implementation, an HBM controller,
  * clock/frequency, nor a PPA claim.
  */
object RouteASynthesisControlProjectionProfile {
  val profileId: String = "qwen3_8b_32k_s1_control_projection_v1"

  /**
    * Local logical encodings for the selected projection, deliberately
    * separate from the test-only anchor encoding. These values never define
    * an external runtime protocol.
    */
  val r6ControlEncoding: RouteAR6Encoding = RouteAR6Encoding(
    sessionStartEventCode = 0,
    kvArrivalEventCode = 1,
    maturityDispositionEventCode = 2,
    attentionServiceEventCode = 3,
    hotArrivalControlCode = 0,
    hotDropControlCode = 1,
    hotRetainControlCode = 2,
    memInitDoneStatusCode = 0,
    m2P3InitDoneStatusCode = 1,
    pageManagerInitDoneStatusCode = 2,
    r1MemoryDrainedStatusCode = 3,
    r2PayloadDrainedStatusCode = 4,
    r2DescriptorDrainedStatusCode = 5,
    r3M2P3DrainedStatusCode = 6,
    r5PageManagerDrainedStatusCode = 7,
    s2GqaDrainedStatusCode = 8,
    directPendingDrainedStatusCode = 9,
    mergeDrainedStatusCode = 10,
    // The A3 anchor has at most four live reads. This is a bounded tracker
    // capacity, not a throughput, outstanding-operation, or deployment claim.
    attentionTrackerEntries = 4,
  )

  /**
    * Complete paired parameter object. The six R2 classes retain the already
    * verified two candidate slots per class; the resulting twelve potential
    * candidates fit in the explicit sixteen-entry delivery-context namespace.
    */
  val parameters: RouteASkeletonParameters = RouteASkeletonParameters(
    frontendEventKindWidth = 2,
    componentStatusNameWidth = 4,
    hotControlKindWidth = 2,
    // Pending descriptor identity is an R5 page ID plus its generation; these
    // are logical associations, not a descriptor-HBM address mapping.
    pendingDescriptorRefWidth = RouteAAnchorWidths.PageIdWidth,
    pendingValidityWidth = RouteAAnchorWidths.PageGenerationWidth,
    candidateClassWidth = 3,
    // Preserve the 0..63 page-member order with one spare high value.
    candidateOrdinalWidth = 7,
    // 4 bits cover all 6 x 2 R2 candidate slots and retain a deterministic
    // arrival tie-break namespace.
    candidateIdWidth = 4,
    candidatePredicateWidth = 10,
    r2S2FullClassCode = 0,
    r2S2PackedClassCode = 1,
    r2DirectPendingClassCode = 2,
    r2PackReadClassCode = 3,
    r2PackWriteClassCode = 4,
    r2DescriptorMaintenanceClassCode = 5,
    r2CandidateSlotsPerClass = 2,
    coreMemoryRequestKindWidth = 3,
    // Five named producer/endpoint roles require more than the historical
    // focused two-bit test shell. Concrete endpoint code assignment remains
    // an external-interface responsibility.
    coreMemoryDestinationWidth = 3,
    coreMemoryAddressRefWidth = RouteAAnchorWidths.PayloadRefWidth,
    coreMemoryFragmentCountWidth = 10,
    coreMemoryFragmentIndexWidth = RouteAAnchorWidths.P3FragmentIndexWidth,
    coreMemoryReadRequestCode = 0,
    coreMemoryWriteRequestCode = 1,
    coreMemoryWriteDataCode = 2,
    coreMemoryOkStatusCode = 0,
    coreMemoryFaultStatusCode = 1,
    // 16 entries cover the twelve R2 candidate slots without silently making
    // the registry the narrower live-resource bound.
    sourceDeliveryOpaqueWidth = 4,
    // These are finite stale-association namespaces for the bounded anchor.
    // They do not establish continuous wrap/reuse evidence.
    transactionGroupTagWidth = 8,
    p3StageGenerationWidth = 8,
    r5AllocatorEntries = 146880,
    r5StreamSlots = 288,
    sourceGenerationWidth = 8,
    r6 = r6ControlEncoding,
  )
}
