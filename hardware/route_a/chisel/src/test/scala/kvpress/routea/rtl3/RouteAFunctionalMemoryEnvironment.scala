package kvpress.routea.rtl3

import chisel3._
import chisel3.simulator.PeekPokeAPI._
import kvpress.routea.common.RouteACoreMemIfV1
import kvpress.routea.interfaces.CoreMemoryExternalPort
import kvpress.routea.params.RouteASkeletonParameters

import scala.collection.mutable

/**
  * RTL3.1 testbench-only functional implementation of the R1 external-memory
  * environment.
  *
  * This is deliberately host-side test infrastructure, not a Chisel module
  * and not part of the Route-A production hierarchy.  It owns no Route-A
  * payload, metadata, residency, publication, or generation authority.  Its
  * only role is to turn accepted `core_mem_if_v1` transactions into deterministic
  * functional responses while preserving ordinary ready/valid backpressure.
  *
  * `generation` and `sidecarRecords` are explicit fixture metadata retained
  * with an address-ref object for later RTL3.2 association tests.  R1 carries
  * neither field, so this environment never infers, validates, or publishes
  * them through a response.
  */
final case class FunctionalPackedObject(
  generation: Option[BigInt],
  payloadFragments: Vector[BigInt],
  sidecarRecords: Vector[BigInt],
)

private object RouteAFunctionalMemoryEnvironment {
  final case class Identity(requestId: BigInt, incarnation: BigInt)
  final case class WriteTransaction(
    addressRef: BigInt,
    expectedFragments: Int,
    fragments: Vector[BigInt],
    faultOnTerminal: Boolean,
  )
  final case class PendingResponse(
    identity: Identity,
    fragmentIndex: BigInt,
    last: Boolean,
    status: Int,
    data: BigInt,
    onAccepted: () => Unit = () => (),
  )
}

final class RouteAFunctionalMemoryEnvironment(p: RouteASkeletonParameters) {
  import RouteAFunctionalMemoryEnvironment._

  private val objects = mutable.Map.empty[BigInt, FunctionalPackedObject]
  private val writes = mutable.Map.empty[Identity, WriteTransaction]
  private val responses = mutable.Queue.empty[PendingResponse]
  private var initPending = true
  private var requestAcceptanceEnabled = true
  private var nextReadFault = false
  private var nextWriteFault = false

  /** Preload fixture-only packed data before an accepted R1 read. */
  def preload(
    addressRef: BigInt,
    generation: Option[BigInt],
    payloadFragments: Vector[BigInt],
    sidecarRecords: Vector[BigInt],
  ): Unit = {
    require(addressRef >= 0, "functional address_ref must be non-negative")
    require(payloadFragments.nonEmpty, "functional packed object needs at least one payload fragment")
    require(payloadFragments.forall(_ >= 0), "functional payload fragments must be non-negative")
    require(sidecarRecords.forall(_ >= 0), "functional sidecar records must be non-negative")
    objects(addressRef) = FunctionalPackedObject(generation, payloadFragments, sidecarRecords)
  }

  def objectAt(addressRef: BigInt): Option[FunctionalPackedObject] = objects.get(addressRef)

  /** Legal environment backpressure only: disabling it cannot drop a request. */
  def setRequestAcceptance(enabled: Boolean): Unit = requestAcceptanceEnabled = enabled

  /** Inject exactly one terminal read fault for the next accepted read request. */
  def injectNextReadFault(): Unit = nextReadFault = true

  /** Inject exactly one terminal write fault for the next accepted write request. */
  def injectNextWriteFault(): Unit = nextWriteFault = true

  /**
    * Reset the environment-side ephemeral state when the test destructively
    * resets R1.  Functional object contents intentionally persist: this is
    * not a claim that a physical memory reset erases HBM.  Pending responses
    * and staged writes are suppressed so a test cannot manufacture an old
    * response after the next init acknowledgement.
    */
  def destructiveReset(): Unit = {
    initPending = true
    writes.clear()
    responses.clear()
    nextReadFault = false
    nextWriteFault = false
  }

  /** Drive all environment-owned signals for the current simulated cycle. */
  def drive(dut: RouteACoreMemIfV1): Unit = {
    drive(dut.io.external_core_mem_if_v1)
  }

  /** Bind the same test-only environment to a composed harness boundary. */
  def drive(port: CoreMemoryExternalPort): Unit = {
    port.init_ack.valid.poke(initPending.B)
    port.init_ack.bits.adapter_epoch_ready.poke(true.B)
    port.request.ready.poke(requestAcceptanceEnabled.B)

    responses.headOption match {
      case Some(response) =>
        port.response.valid.poke(true.B)
        port.response.bits.transaction_identity.request_id.poke(response.identity.requestId.U)
        port.response.bits.transaction_identity.incarnation.poke(response.identity.incarnation.U)
        port.response.bits.fragment_index.poke(response.fragmentIndex.U)
        port.response.bits.last.poke(response.last.B)
        port.response.bits.status.poke(response.status.U)
        port.response.bits.data.poke(response.data.U)
      case None =>
        port.response.valid.poke(false.B)
        port.response.bits.transaction_identity.request_id.poke(0.U)
        port.response.bits.transaction_identity.incarnation.poke(0.U)
        port.response.bits.fragment_index.poke(0.U)
        port.response.bits.last.poke(false.B)
        port.response.bits.status.poke(p.coreMemoryOkStatusCode.U)
        port.response.bits.data.poke(0.U)
    }
  }

  /**
    * Observe accepted environment transactions before the test advances the
    * clock.  Call `drive`, then this method, then `dut.clock.step()` exactly
    * once per simulated cycle.  Response data remains stable until R1 accepts
    * it, so this helper has no hidden timing or service-rate behavior.
    */
  def observeAccepted(dut: RouteACoreMemIfV1): Unit = {
    observeAccepted(dut.io.external_core_mem_if_v1)
  }

  /** Observe a composed harness boundary; semantics are identical to R1 binding. */
  def observeAccepted(port: CoreMemoryExternalPort): Unit = {
    if (initPending && bool(port.init_ack.valid) && bool(port.init_ack.ready)) {
      initPending = false
    }

    if (responses.headOption.nonEmpty && bool(port.response.valid) && bool(port.response.ready)) {
      responses.dequeue().onAccepted()
    }

    if (bool(port.request.valid) && bool(port.request.ready)) {
      acceptRequest(port)
    }
  }

  private def bool(signal: Bool): Boolean = signal.peek().litToBoolean

  private def identity(port: CoreMemoryExternalPort): Identity = Identity(
    port.request.bits.transaction_identity.request_id.peek().litValue,
    port.request.bits.transaction_identity.incarnation.peek().litValue,
  )

  private def queueFault(identity: Identity): Unit = {
    responses.enqueue(PendingResponse(identity, fragmentIndex = 0, last = true, p.coreMemoryFaultStatusCode, data = 0))
  }

  private def acceptRequest(port: CoreMemoryExternalPort): Unit = {
    val request = port.request.bits
    val acceptedIdentity = identity(port)
    val kind = request.request_kind.peek().litValue.toInt
    val addressRef = request.address_ref.peek().litValue

    if (kind == p.coreMemoryReadRequestCode) {
      val expected = request.expected_fragment_count.peek().litValue.toInt
      val fault = nextReadFault
      nextReadFault = false
      objects.get(addressRef) match {
        case Some(objectValue) if !fault && objectValue.payloadFragments.size == expected =>
          objectValue.payloadFragments.zipWithIndex.foreach { case (data, index) =>
            responses.enqueue(PendingResponse(
              acceptedIdentity,
              fragmentIndex = index,
              last = index == objectValue.payloadFragments.size - 1,
              status = p.coreMemoryOkStatusCode,
              data = data,
            ))
          }
        case _ => queueFault(acceptedIdentity)
      }
    } else if (kind == p.coreMemoryWriteRequestCode) {
      val expected = request.expected_fragment_count.peek().litValue.toInt
      val fault = nextWriteFault
      nextWriteFault = false
      if (expected <= 0 || writes.contains(acceptedIdentity)) {
        queueFault(acceptedIdentity)
      } else {
        writes(acceptedIdentity) = WriteTransaction(addressRef, expected, Vector.empty, fault)
      }
    } else if (kind == p.coreMemoryWriteDataCode) {
      writes.get(acceptedIdentity) match {
        case Some(transaction) =>
          val fragmentIndex = request.fragment_index.peek().litValue.toInt
          val last = bool(request.last)
          val expectedLast = transaction.fragments.size == transaction.expectedFragments - 1
          if (fragmentIndex != transaction.fragments.size || last != expectedLast) {
            writes.remove(acceptedIdentity)
            queueFault(acceptedIdentity)
          } else {
            val nextFragments = transaction.fragments :+ request.data.peek().litValue
            if (last) {
              writes.remove(acceptedIdentity)
              val commit = () => {
                if (!transaction.faultOnTerminal) {
                  val old = objects.get(transaction.addressRef)
                  objects(transaction.addressRef) = FunctionalPackedObject(
                    generation = old.flatMap(_.generation),
                    payloadFragments = nextFragments,
                    sidecarRecords = old.map(_.sidecarRecords).getOrElse(Vector.empty),
                  )
                }
              }
              responses.enqueue(PendingResponse(
                acceptedIdentity,
                fragmentIndex = 0,
                last = true,
                status = if (transaction.faultOnTerminal) p.coreMemoryFaultStatusCode else p.coreMemoryOkStatusCode,
                data = 0,
                onAccepted = commit,
              ))
            } else {
              writes(acceptedIdentity) = transaction.copy(fragments = nextFragments)
            }
          }
        case None => queueFault(acceptedIdentity)
      }
    } else {
      queueFault(acceptedIdentity)
    }
  }
}
