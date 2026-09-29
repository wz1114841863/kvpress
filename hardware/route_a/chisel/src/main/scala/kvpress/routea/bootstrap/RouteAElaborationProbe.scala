package kvpress.routea.bootstrap

import chisel3.{Bool, Clock, IO, Input, RawModule}

/**
  * Host-toolchain smoke probe only.
  *
  * This intentionally owns no Route-A state and is not part of the frozen
  * RTL1 hierarchy. It permits a no-model elaboration check before RTL1.0
  * introduces architecture module skeletons.
  */
final class RouteAElaborationProbe extends RawModule {
  val coreClock = IO(Input(Clock()))
  val destructiveReset = IO(Input(Bool()))
}
