package kvpress.routea.params

/**
  * Widths that remain intentionally opaque in the RTL0.2 logical-port
  * manifest. There are deliberately no deployment defaults: an integration
  * must name an encoding before elaborating a concrete top-level instance.
  */
final case class RouteASkeletonParameters(
  frontendEventKindWidth: Int,
  componentStatusNameWidth: Int,
  hotControlKindWidth: Int,
  pendingDescriptorRefWidth: Int,
  pendingValidityWidth: Int,
  candidateClassWidth: Int,
  candidateOrdinalWidth: Int,
  candidateIdWidth: Int,
  candidatePredicateWidth: Int,
  r2S2FullClassCode: Int,
  r2S2PackedClassCode: Int,
  r2DirectPendingClassCode: Int,
  r2PackReadClassCode: Int,
  r2PackWriteClassCode: Int,
  r2DescriptorMaintenanceClassCode: Int,
  r2CandidateSlotsPerClass: Int,
  coreMemoryRequestKindWidth: Int,
  coreMemoryDestinationWidth: Int,
  coreMemoryAddressRefWidth: Int,
  coreMemoryFragmentCountWidth: Int,
  coreMemoryFragmentIndexWidth: Int,
  coreMemoryReadRequestCode: Int,
  coreMemoryWriteRequestCode: Int,
  coreMemoryWriteDataCode: Int,
  coreMemoryOkStatusCode: Int,
  coreMemoryFaultStatusCode: Int,
  sourceDeliveryOpaqueWidth: Int,
  transactionGroupTagWidth: Int,
  p3StageGenerationWidth: Int,
  r5AllocatorEntries: Int,
  r5StreamSlots: Int,
  sourceGenerationWidth: Int,
  r6: RouteAR6Encoding,
) {
  private val allOpaqueWidths = Seq(
    frontendEventKindWidth,
    componentStatusNameWidth,
    hotControlKindWidth,
    pendingDescriptorRefWidth,
    pendingValidityWidth,
    candidateClassWidth,
    candidateOrdinalWidth,
    candidateIdWidth,
    candidatePredicateWidth,
    coreMemoryRequestKindWidth,
    coreMemoryDestinationWidth,
    coreMemoryAddressRefWidth,
    coreMemoryFragmentCountWidth,
    coreMemoryFragmentIndexWidth,
    sourceDeliveryOpaqueWidth,
    transactionGroupTagWidth,
    p3StageGenerationWidth,
    sourceGenerationWidth,
  )

  require(allOpaqueWidths.forall(_ > 0), "Every opaque logical-field width must be supplied and positive")

  require(candidatePredicateWidth >= 10, "R2 eligibility snapshot requires its ten frozen semantic bits")
  private val candidateClassLimit = 1 << candidateClassWidth
  private val r2ClassCodes = Seq(
    r2S2FullClassCode,
    r2S2PackedClassCode,
    r2DirectPendingClassCode,
    r2PackReadClassCode,
    r2PackWriteClassCode,
    r2DescriptorMaintenanceClassCode,
  )
  require(
    r2ClassCodes.forall(code => code >= 0 && code < candidateClassLimit) && r2ClassCodes.distinct.size == r2ClassCodes.size,
    "Every R2 candidate-class code must fit the supplied width and be distinct",
  )
  require(r2CandidateSlotsPerClass > 0, "R2 candidate storage bound must be supplied and positive")

  private val requestKindLimit = 1 << coreMemoryRequestKindWidth
  require(
    Seq(coreMemoryReadRequestCode, coreMemoryWriteRequestCode, coreMemoryWriteDataCode)
      .forall(code => code >= 0 && code < requestKindLimit),
    "Every R1 request-kind code must fit the supplied opaque request-kind width",
  )
  require(
    Set(coreMemoryReadRequestCode, coreMemoryWriteRequestCode, coreMemoryWriteDataCode).size == 3,
    "R1 read/write-request/write-data codes must be distinct",
  )
  private val terminalStatusLimit = 1 << RouteAAnchorWidths.TerminalStatusWidth
  require(
    Seq(coreMemoryOkStatusCode, coreMemoryFaultStatusCode)
      .forall(code => code >= 0 && code < terminalStatusLimit),
    "Every R1 terminal-status code must fit the selected terminal-status width",
  )
  require(coreMemoryOkStatusCode != coreMemoryFaultStatusCode, "R1 OK and fault status codes must differ")
  require(r5AllocatorEntries > 0 && r5AllocatorEntries <= 146880,
    "R5 allocator control bound must be positive and no larger than the selected logical anchor")
  require(r5StreamSlots > 0 && r5StreamSlots <= 288,
    "R5 stream control bound must be positive and no larger than the selected logical anchor")

  private def fits(width: Int, value: Int): Boolean = value >= 0 && value < (1 << width)
  require(
    Seq(
      r6.sessionStartEventCode,
      r6.kvArrivalEventCode,
      r6.maturityDispositionEventCode,
      r6.attentionServiceEventCode,
    ).forall(fits(frontendEventKindWidth, _)) &&
      r6.frontendEventCodes.distinct.size == r6.frontendEventCodes.size,
    "R6 frontend event codes must fit the supplied width and be distinct",
  )
  require(
    Seq(r6.hotArrivalControlCode, r6.hotDropControlCode, r6.hotRetainControlCode)
      .forall(fits(hotControlKindWidth, _)) &&
      r6.hotControlCodes.distinct.size == r6.hotControlCodes.size,
    "R6 hot-control codes must fit the supplied width and be distinct",
  )
  require(
    r6.componentStatusCodes.forall(fits(componentStatusNameWidth, _)) &&
      r6.componentStatusCodes.distinct.size == r6.componentStatusCodes.size,
    "R6 component-status codes must fit the supplied width and be distinct",
  )
  require(r6.attentionTrackerEntries > 0 && r6.attentionTrackerEntries <= 32,
    "R6 attention tracker entries must be positive and fit the selected A3 identity namespace")
}

/**
  * Logical R6 encodings supplied by a concrete integration/test instantiation.
  * They do not select an external wire protocol or a physical controller
  * encoding. Deployment values remain a later integration parameter.
  */
final case class RouteAR6Encoding(
  sessionStartEventCode: Int,
  kvArrivalEventCode: Int,
  maturityDispositionEventCode: Int,
  attentionServiceEventCode: Int,
  hotArrivalControlCode: Int,
  hotDropControlCode: Int,
  hotRetainControlCode: Int,
  memInitDoneStatusCode: Int,
  m2P3InitDoneStatusCode: Int,
  pageManagerInitDoneStatusCode: Int,
  r1MemoryDrainedStatusCode: Int,
  r2PayloadDrainedStatusCode: Int,
  r2DescriptorDrainedStatusCode: Int,
  r3M2P3DrainedStatusCode: Int,
  r5PageManagerDrainedStatusCode: Int,
  s2GqaDrainedStatusCode: Int,
  directPendingDrainedStatusCode: Int,
  mergeDrainedStatusCode: Int,
  attentionTrackerEntries: Int,
) {
  def frontendEventCodes: Seq[Int] = Seq(
    sessionStartEventCode, kvArrivalEventCode, maturityDispositionEventCode, attentionServiceEventCode,
  )
  def hotControlCodes: Seq[Int] = Seq(hotArrivalControlCode, hotDropControlCode, hotRetainControlCode)
  def componentStatusCodes: Seq[Int] = Seq(
    memInitDoneStatusCode, m2P3InitDoneStatusCode, pageManagerInitDoneStatusCode,
    r1MemoryDrainedStatusCode, r2PayloadDrainedStatusCode, r2DescriptorDrainedStatusCode,
    r3M2P3DrainedStatusCode, r5PageManagerDrainedStatusCode, s2GqaDrainedStatusCode,
    directPendingDrainedStatusCode, mergeDrainedStatusCode,
  )
}

object RouteAR6Encoding {
  /** Concrete test elaboration only; not a selected deployment configuration. */
  val testOnlyAnchor: RouteAR6Encoding = RouteAR6Encoding(
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
    attentionTrackerEntries = 4,
  )
}

/** Selected Route-A anchor widths, sourced from the Gate-A3/R4/R5 contracts. */
object RouteAAnchorWidths {
  final val ContextTokensWidth = 16
  final val EntryIdWidth = 24
  final val LayerWidth = 6
  final val KvHeadWidth = 3
  final val LogicalPositionWidth = 15
  final val PayloadRefWidth = 64
  final val RequestIdWidth = 3
  final val IncarnationWidth = 2
  final val PageIdWidth = 18
  final val PageGenerationWidth = 8
  final val S2SlotWidth = 1
  final val SourceKindWidth = 2
  final val ConsumerIdWidth = 2
  final val SourcePresenceWidth = 3
  final val CoreDataWidth = 512
  final val MergePartialHeaderWidth = 128
  final val MergeValueFragmentWidth = 512
  final val NormalizedValueWidth = 128 * 32
  final val TerminalStatusWidth = 1
  final val PublicationStatusWidth = 1
  final val P3ValidRecordsWidth = 7
  final val P3FragmentIndexWidth = 9
  final val P3StateWidth = 3
  // MR-2 bounded M2 storage-unit realization widths.  These are explicit
  // Route-A measurement-DUT choices, not A4's historical 59/50-bit accounting
  // envelope or a physical macro selection.
  final val M2EntryWordWidth = 128
  final val M2SpanSlotWidth = 10
  final val M2SpanGenerationWidth = 8
  final val M2LifecycleOperationIdWidth = 16
  final val M2FaultReasonWidth = 3
}

/** Fixed semantic encodings, not physical controller/M2/P3 encodings. */
object RouteAPublicationStatus {
  final val Published = 0
  final val Fault = 1
}

object RouteAM2GroupMember {
  final val HeadControlRmw = 0
  final val SpanOwnerRmw = 1
}

object RouteADescriptorOperationKind {
  final val NewPage = 0
  final val TailLink = 1
  final val Invalidate = 2
}
