package kvpress.routea.rtl3

/** Replay the real R3 materialization/packing/terminal regression with WCG1
  * and a reference wrapper sharing every input and ready/backpressure leaf.
  * This selects only the candidate test harness, never a production top.
  */
final class RouteAWCG1WrapperSpec extends RouteARTL39AMaterializationSpec {
  override protected def gateCompactMembershipWords: Boolean = true
}
