package kvpress.routea.rtl2

/** Host-side test-only record of one accepted C4 event. */
sealed trait RouteAC4BAcceptedEvent { def name: String }
final case class RouteAC4BAuthorityAccepted(
  entryId: BigInt, groupTag: BigInt, fromAuthority: BigInt, toAuthority: BigInt,
) extends RouteAC4BAcceptedEvent { override val name = "authority_transition" }
final case class RouteAC4BTerminalAccepted(
  requestId: BigInt, incarnation: BigInt, terminalStatus: BigInt,
) extends RouteAC4BAcceptedEvent { override val name = "attention_terminal" }
final case class RouteAC4BPageFreeAccepted(
  pageId: BigInt, generation: BigInt,
) extends RouteAC4BAcceptedEvent { override val name = "page_free" }
final case class RouteAC4BRetireAckAccepted(
  sessionId: Boolean, requestId: BigInt, incarnation: BigInt,
) extends RouteAC4BAcceptedEvent { override val name = "retire_ack" }

/**
  * Replays only events observed at an actual C4 event/output acceptance in the
  * C3b witness. This is host-side verification state, not a Chisel owner,
  * event buffer, scheduler, or production scoreboard.
  */
object RouteAC4BEventReplayOracle {
  private val ExpectedOrder = Seq("authority_transition", "attention_terminal", "page_free", "retire_ack")

  def replay(events: Seq[RouteAC4BAcceptedEvent], pendingCode: BigInt, packedCode: BigInt, okCode: BigInt): Unit = {
    require(events.map(_.name) == ExpectedOrder,
      s"expected one accepted C4 event in order ${ExpectedOrder.mkString(" -> ")}, got ${events.map(_.name).mkString(" -> ")}")
    require(events.map(_.name).distinct.size == events.size, "accepted C4 event trace replayed an event")

    val authority = events.head.asInstanceOf[RouteAC4BAuthorityAccepted]
    val terminal = events(1).asInstanceOf[RouteAC4BTerminalAccepted]
    val pageFree = events(2).asInstanceOf[RouteAC4BPageFreeAccepted]
    val retireAck = events(3).asInstanceOf[RouteAC4BRetireAckAccepted]
    require(authority.entryId == 0 && authority.groupTag == 1,
      s"unexpected authority identity entry=${authority.entryId} tag=${authority.groupTag}")
    require(authority.fromAuthority == pendingCode && authority.toAuthority == packedCode,
      s"unexpected authority transition ${authority.fromAuthority} -> ${authority.toAuthority}")
    require(terminal.requestId == 3 && terminal.incarnation == 0 && terminal.terminalStatus == okCode,
      s"unexpected terminal record $terminal")
    require(pageFree.pageId == 0 && pageFree.generation == 0, s"unexpected old PageRef $pageFree")
    require(!retireAck.sessionId && retireAck.requestId == terminal.requestId && retireAck.incarnation == terminal.incarnation,
      s"retire acknowledgement does not match terminal: terminal=$terminal ack=$retireAck")
  }
}
