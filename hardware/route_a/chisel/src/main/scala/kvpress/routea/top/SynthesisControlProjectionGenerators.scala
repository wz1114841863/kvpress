package kvpress.routea.top

import kvpress.routea.params.RouteASkeletonParameters

/**
  * Explicit construction points for the two future synthesis-control
  * projections.  They deliberately take a complete parameter object from the
  * caller: this source supplies no test, focused, or deployment default.
  *
  * A later approved emitter may pass either constructor to ChiselStage only
  * after the full parameter profile and external-boundary realization are
  * accepted.  These factories do not themselves emit HDL or select a tool.
  */
object FullKVControlProjectionGenerator {
  def construct(p: RouteASkeletonParameters): FullKVControlProjection =
    new FullKVControlProjection(p)
}

object RouteAControlProjectionGenerator {
  def construct(p: RouteASkeletonParameters): RouteAControlProjection =
    new RouteAControlProjection(p)
}
