package kvpress.routea.rtl3

import scala.collection.mutable.ArrayBuffer

/**
  * Host-side, testbench-only event order oracle for RTL3.7-C directed
  * witnesses. Events are recorded only after the test has observed the named
  * ready/valid fact; this is neither an RTL block nor a timing model.
  */
final class RouteARTL37cEventScoreboard {
  private val events = ArrayBuffer.empty[String]

  def record(event: String): Unit = events += event
  def observed: Vector[String] = events.toVector

  def requireOrdered(expected: Seq[String]): Unit = {
    var cursor = 0
    events.foreach { event =>
      if (cursor < expected.size && event == expected(cursor)) cursor += 1
    }
    require(cursor == expected.size,
      s"RTL3.7-C event order missing expected=$expected observed=${events.toVector}")
  }
}
