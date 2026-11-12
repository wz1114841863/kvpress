"""Offline pending capacity and FIFO ownership models, not physical measurements."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

def consecutive_max(opportunities: list[int]) -> int:
    best = run = 0
    previous: int | None = None
    for value in opportunities:
        run = run + 1 if previous == value - 1 else 1
        best = max(best, run)
        previous = value
    return best

def snapshot(*, pending: list[int], total_budget: int, organization: str, private_quota: int = 0) -> dict[str, int]:
    """Pure capacity ownership accounting for one layer/opportunity snapshot."""
    if total_budget < 0 or private_quota < 0 or not pending or min(pending) < 0:
        raise ValueError("invalid logical capacity snapshot")
    head_count = len(pending)
    total_pending = sum(pending)
    if organization == "head_local_equal_quota":
        if total_budget % head_count:
            raise ValueError("head-local equal quota requires budget divisible by head count")
        quota = total_budget // head_count
        overflow_demand = sum(max(0, value - quota) for value in pending)
        private_reserved = total_budget
        shared_capacity = 0
        unused_private = sum(max(0, quota - value) for value in pending)
    elif organization == "layer_shared":
        quota = 0
        overflow_demand = total_pending
        private_reserved = 0
        shared_capacity = total_budget
        unused_private = 0
    elif organization == "hierarchical_private_plus_shared_overflow":
        private_reserved = head_count * private_quota
        if private_reserved > total_budget:
            raise ValueError("hierarchical private quota exceeds equal total budget")
        quota = private_quota
        overflow_demand = sum(max(0, value - quota) for value in pending)
        shared_capacity = total_budget - private_reserved
        unused_private = sum(max(0, quota - value) for value in pending)
    else:
        raise ValueError(f"unknown organization {organization}")
    excess = max(0, overflow_demand - shared_capacity)
    # "Stranded" is deliberately only private capacity inaccessible while this
    # same snapshot breaches.  Idle capacity without a breach is ordinary slack.
    stranded = unused_private if excess else 0
    return {
        "head_count": head_count,
        "total_pending": total_pending,
        "total_budget": total_budget,
        "private_quota_per_head": quota,
        "private_reserved": private_reserved,
        "shared_overflow_capacity": shared_capacity,
        "overflow_demand": overflow_demand,
        "peak_excess": excess,
        "unused_private_reservation": unused_private,
        "stranded_private_reservation": stranded,
    }

def organization_summary(*, samples: dict[int, list[tuple[int, list[int]]]], total_budget: int, organization: str, private_quota: int = 0, include_per_layer: bool = False) -> dict[str, Any]:
    """Summarize one organization at a fixed, equal per-layer budget C."""
    per_layer: list[dict[str, Any]] = []
    all_breach_opportunities = 0
    breached_layer_count = 0
    all_stranded_opportunities = 0
    total_stranded = 0
    peak_stranded = 0
    peak_excess = 0
    max_duration = 0
    for layer, rows in sorted(samples.items()):
        values = [snapshot(pending=pending, total_budget=total_budget, organization=organization, private_quota=private_quota) for _, pending in rows]
        breaches = [opportunity for (opportunity, _), value in zip(rows, values) if value["peak_excess"] > 0]
        stranded = [value["stranded_private_reservation"] for value in values if value["peak_excess"] > 0]
        layer_peak = max(value["peak_excess"] for value in values)
        peak_excess = max(peak_excess, layer_peak)
        max_duration = max(max_duration, consecutive_max(breaches))
        all_breach_opportunities += len(breaches)
        breached_layer_count += bool(breaches)
        all_stranded_opportunities += sum(value > 0 for value in stranded)
        total_stranded += sum(stranded)
        peak_stranded = max(peak_stranded, max(stranded, default=0))
        if include_per_layer:
            per_layer.append({
                "layer": layer,
                "breach_opportunity_count": len(breaches),
                "first_breach_opportunity": breaches[0] if breaches else None,
                "peak_excess": layer_peak,
                "max_consecutive_breach_duration": consecutive_max(breaches),
                "stranded_private_reservation_during_breach_total": sum(stranded),
                "stranded_private_reservation_peak_during_breach": max(stranded, default=0),
            })
    result: dict[str, Any] = {
        "organization": organization,
        "total_logical_capacity_budget_per_layer": total_budget,
        "private_quota_per_head": private_quota,
        "shared_overflow_capacity_per_layer": total_budget - private_quota * len(next(iter(samples.values()))[0][1]),
        "breached_layer_count": breached_layer_count,
        "breach_layer_opportunity_count": all_breach_opportunities,
        "peak_excess_logical_tokens": peak_excess,
        "max_consecutive_breach_duration": max_duration,
        "stranded_private_reservation_during_breach_total": total_stranded,
        "stranded_private_reservation_peak_during_breach": peak_stranded,
        "stranded_breach_layer_opportunity_count": all_stranded_opportunities,
    }
    if include_per_layer:
        result["per_layer"] = per_layer
    return result

def zero_breach_budget(*, samples: dict[int, list[tuple[int, list[int]]]], organization: str, private_quota: int = 0) -> int:
    """Exact Cmin for zero breach under a named fixed ownership arrangement."""
    head_count = len(next(iter(samples.values()))[0][1])
    if organization == "head_local_equal_quota":
        return head_count * max(max(pending) for rows in samples.values() for _, pending in rows)
    if organization == "layer_shared":
        return max(sum(pending) for rows in samples.values() for _, pending in rows)
    if organization == "hierarchical_private_plus_shared_overflow":
        overflow = max(sum(max(0, value - private_quota) for value in pending) for rows in samples.values() for _, pending in rows)
        return head_count * private_quota + overflow
    raise ValueError(f"unknown organization {organization}")

def meets_target(summary: dict[str, Any], target: dict[str, int]) -> bool:
    return summary["peak_excess_logical_tokens"] <= target["maximum_peak_excess_logical_tokens"] and summary["max_consecutive_breach_duration"] <= target["maximum_consecutive_breach_duration"]

def min_budget_for_target(*, samples: dict[int, list[tuple[int, list[int]]]], organization: str, target: dict[str, int], private_quota: int = 0) -> int:
    """Find minimum C for a monotone bounded-breach observer target."""
    head_count = len(next(iter(samples.values()))[0][1])
    high = zero_breach_budget(samples=samples, organization=organization, private_quota=private_quota)
    if organization == "head_local_equal_quota":
        low_quota, high_quota = 0, high // head_count
        while low_quota < high_quota:
            middle = (low_quota + high_quota) // 2
            result = organization_summary(samples=samples, total_budget=middle * head_count, organization=organization)
            if meets_target(result, target):
                high_quota = middle
            else:
                low_quota = middle + 1
        return low_quota * head_count
    low = head_count * private_quota if organization == "hierarchical_private_plus_shared_overflow" else 0
    while low < high:
        middle = (low + high) // 2
        if organization == "hierarchical_private_plus_shared_overflow" and middle < head_count * private_quota:
            low = head_count * private_quota
            continue
        result = organization_summary(samples=samples, total_budget=middle, organization=organization, private_quota=private_quota)
        if meets_target(result, target):
            high = middle
        else:
            low = middle + 1
    return low

@dataclass
class Segment:
    birth_opportunity: int
    sequence_start: int
    count: int

    @property
    def key(self) -> tuple[int, int]:
        return self.birth_opportunity, self.sequence_start

    def consume(self, count: int) -> None:
        if count <= 0 or count > self.count:
            raise ValueError("invalid segment consumption")
        self.sequence_start += count
        self.count -= count

class PendingOwnershipState:
    """One head's immutable-source ownership state and canonical FIFO oracle."""

    def __init__(self, *, organization: str, private_quota: int | None) -> None:
        if organization not in {"head_local", "layer_shared", "hierarchical"}:
            raise ValueError("unknown ownership organization")
        if organization == "hierarchical" and (private_quota is None or private_quota < 0):
            raise ValueError("hierarchical organization requires nonnegative private quota")
        self.organization = organization
        self.private_quota = private_quota
        self.canonical: deque[Segment] = deque()
        self.sources: dict[str, deque[Segment]] = {"private": deque(), "shared": deque()}
        self.live: dict[str, int] = {"private": 0, "shared": 0}
        self.next_sequence = 0
        self.max_pending = 0
        self.max_active_spans = 0
        self.max_active_sources = 0
        self.source_age_inversion_count = 0
        self.migration_event_count = 0
        self.operation_counts: dict[str, int] = defaultdict(int)

    @property
    def pending(self) -> int:
        return self.live["private"] + self.live["shared"]

    def active_spans(self) -> int:
        return len(self.sources["private"]) + len(self.sources["shared"])

    def active_sources(self) -> int:
        return sum(bool(self.sources[source]) for source in ("private", "shared"))

    def _append(self, *, source: str, count: int, birth_opportunity: int) -> dict[str, int]:
        if source not in self.sources or count <= 0:
            raise ValueError("invalid source append")
        segment = Segment(birth_opportunity=birth_opportunity, sequence_start=self.next_sequence, count=count)
        self.next_sequence += count
        self.canonical.append(Segment(birth_opportunity=segment.birth_opportunity, sequence_start=segment.sequence_start, count=count))
        self.sources[source].append(segment)
        self.live[source] += count
        self.operation_counts[f"{source}_enqueue_token_units"] += count
        self.operation_counts[f"{source}_enqueue_segment_count"] += 1
        return {"source": source, "count": count}

    def enqueue(self, *, count: int, birth_opportunity: int) -> list[dict[str, int]]:
        """Assign source once at enqueue; no later private/shared migration exists."""
        if count < 0 or birth_opportunity < 0:
            raise ValueError("invalid enqueue")
        events: list[dict[str, int]] = []
        if not count:
            return events
        if self.organization == "head_local":
            events.append(self._append(source="private", count=count, birth_opportunity=birth_opportunity))
        elif self.organization == "layer_shared":
            events.append(self._append(source="shared", count=count, birth_opportunity=birth_opportunity))
        else:
            assert self.private_quota is not None
            private_count = min(count, max(0, self.private_quota - self.live["private"]))
            if private_count:
                events.append(self._append(source="private", count=private_count, birth_opportunity=birth_opportunity))
            if count - private_count:
                events.append(self._append(source="shared", count=count - private_count, birth_opportunity=birth_opportunity))
        self.max_pending = max(self.max_pending, self.pending)
        self.max_active_spans = max(self.max_active_spans, self.active_spans())
        self.max_active_sources = max(self.max_active_sources, self.active_sources())
        return events

    def dequeue(self, *, count: int) -> list[dict[str, int | bool]]:
        """Consume exact canonical FIFO order by comparing private/shared fronts."""
        if count < 0 or count > self.pending:
            raise ValueError("invalid dequeue grant")
        chunks: list[dict[str, int | bool]] = []
        previous_source: str | None = None
        while count:
            candidates = [source for source in ("private", "shared") if self.sources[source]]
            if not candidates:
                raise AssertionError("pending accounting lost a source segment")
            compared_sources = len(candidates) == 2
            if compared_sources:
                self.operation_counts["oldest_source_comparison_count"] += 1
            source = min(candidates, key=lambda item: self.sources[item][0].key)
            selected = self.sources[source][0]
            for other in candidates:
                if self.sources[other][0].key < selected.key:
                    self.source_age_inversion_count += 1
                    raise AssertionError("source-age inversion")
            canonical = self.canonical[0]
            if selected.key != canonical.key:
                self.source_age_inversion_count += 1
                raise AssertionError("selected source is not canonical oldest entry")
            amount = min(count, selected.count, canonical.count)
            switched = previous_source is not None and previous_source != source
            if switched:
                self.operation_counts["cross_source_switch_count"] += 1
            selected.consume(amount)
            canonical.consume(amount)
            self.live[source] -= amount
            self.operation_counts[f"{source}_dequeue_token_units"] += amount
            count -= amount
            released = selected.count == 0
            if released:
                self.sources[source].popleft()
                self.operation_counts[f"{source}_release_segment_count"] += 1
            if canonical.count == 0:
                self.canonical.popleft()
            chunks.append({"source": source, "count": amount, "compared_sources": compared_sources, "source_switch": switched, "released_segment": released})
            previous_source = source
        if self.pending != sum(segment.count for segment in self.canonical):
            raise AssertionError("source and canonical pending totals diverged")
        return chunks
