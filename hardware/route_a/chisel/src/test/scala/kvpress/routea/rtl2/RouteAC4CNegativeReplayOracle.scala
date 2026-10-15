package kvpress.routea.rtl2

/** Host-only C4-C checks for accepted-event prefixes on negative scenarios. */
object RouteAC4CNegativeReplayOracle {
  private def names(events: Seq[RouteAC4BAcceptedEvent]): Seq[String] = events.map(_.name)

  def staleOrMismatch(events: Seq[RouteAC4BAcceptedEvent]): Unit =
    require(names(events) == Seq("authority_transition"),
      s"stale/mismatch may retain only its earlier authority prefix, got ${names(events)}")

  def numericFault(events: Seq[RouteAC4BAcceptedEvent], faultCode: BigInt): Unit = {
    require(names(events) == Seq("authority_transition", "attention_terminal"),
      s"numeric fault must terminate once without free/retire events, got ${names(events)}")
    val terminal = events(1).asInstanceOf[RouteAC4BTerminalAccepted]
    require(terminal.requestId == 3 && terminal.incarnation == 0 && terminal.terminalStatus == faultCode,
      s"unexpected numeric-fault terminal $terminal")
  }

  def reset(events: Seq[RouteAC4BAcceptedEvent]): Unit =
    require(events.isEmpty, s"reset must clear an unaccepted event rather than replay it: ${names(events)}")
}
