from tools.analyze_kvzap_route_a4670_pending_ownership_reference import PendingOwnershipState
from tools.analyze_kvzap_route_a4680_pending_representation_sufficiency import (
    BirthOrderedSourceSpanRepresentation,
    assert_representation_sufficient,
    run_negative_control,
)


def _enqueue(reference: PendingOwnershipState, representation: BirthOrderedSourceSpanRepresentation, count: int, birth: int) -> None:
    representation.enqueue_from_reference(events=reference.enqueue(count=count, birth_opportunity=birth), birth_opportunity=birth)
    assert_representation_sufficient(reference=reference, representation=representation)


def test_a4680_birth_ordered_spans_reconstruct_old_shared_before_new_private():
    reference = PendingOwnershipState(organization="hierarchical", private_quota=2)
    representation = BirthOrderedSourceSpanRepresentation()
    _enqueue(reference, representation, 5, 1)  # private [0,1], shared [2,3,4]
    expected = [(str(item["source"]), int(item["count"])) for item in reference.dequeue(count=3)]
    assert representation.dequeue(count=3) == expected
    assert_representation_sufficient(reference=reference, representation=representation)
    _enqueue(reference, representation, 2, 2)  # new private, while old shared remains
    assert representation.oldest()[0] == "shared"
    expected = [(str(item["source"]), int(item["count"])) for item in reference.dequeue(count=1)]
    assert representation.dequeue(count=1) == expected == [("shared", 1)]
    assert_representation_sufficient(reference=reference, representation=representation)


def test_a4680_span_descriptor_is_lossless_for_same_birth_contiguous_entries():
    reference = PendingOwnershipState(organization="layer_shared", private_quota=None)
    representation = BirthOrderedSourceSpanRepresentation()
    _enqueue(reference, representation, 7, 4)
    assert representation.reconstruct_canonical_runs() == [("shared", 4, 0, 7)]
    assert representation.created_span_count == 1


def test_a4680_source_counts_without_birth_order_are_explicitly_rejected():
    assert run_negative_control()


def test_a4680_invalid_representation_grant_is_rejected():
    representation = BirthOrderedSourceSpanRepresentation()
    representation.enqueue_from_reference(events=[{"source": "private", "count": 2}], birth_opportunity=0)
    try:
        representation.dequeue(count=3)
    except ValueError as error:
        assert "invalid representation dequeue" in str(error)
    else:
        raise AssertionError("representation must reject an overservice grant")
