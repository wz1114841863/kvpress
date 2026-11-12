"""Compatibility imports for the Route-A software reference.

The shared implementation lives in :mod:`kvpress.research.route_a`.
"""

from kvpress.research.route_a import (
    DenseSameMaskAttentionState, RouteALifecycleTransitionRecorder,
    RouteALogicalEventRecorder, RouteAPackedAttentionState, RouteAPolicy,
    _attention, _PackedPages, _Record, dense_same_mask_attention,
    online_softmax_merge, policy_attention,
)
