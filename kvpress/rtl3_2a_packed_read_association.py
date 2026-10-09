"""Validation rules for the RTL3.2-A packed-read association-owner closure."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


VERSION = "kvzap-route-a-rtl3-2a-packed-read-association-1.0"
STATUS = "complete_executable_association_owner_contract_pre_rtl3_2_payload"
GRANTS = (
    ("PackedSourceDemand", "upstream_preselected_packed_source_boundary"),
    ("PublicationReadAuthorization", "route_a_m2_p3_wrapper"),
    ("DescriptorLocationGrant", "route_a_page_manager"),
    ("S2FillLease", "route_a_s2_gqa_source_wrapper"),
)


class RTL32AssociationManifestError(ValueError):
    """Raised when RTL3.2-A would broaden the packed-read association boundary."""


def load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL32AssociationManifestError("RTL3.2-A manifest root must be an object")
    return value


def validate(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != VERSION or manifest.get("status") != STATUS:
        raise RTL32AssociationManifestError("unexpected RTL3.2-A version or status")
    if manifest.get("association_owner") != "route_a_packed_read_association_owner":
        raise RTL32AssociationManifestError("packed-read association owner drift")
    grants = manifest.get("grant_interfaces")
    if not isinstance(grants, list) or tuple((item.get("name"), item.get("producer")) for item in grants if isinstance(item, Mapping)) != GRANTS:
        raise RTL32AssociationManifestError("grant-owner inventory drift")
    publication = grants[1]
    if "live publication authorization" not in str(publication.get("rule", "")) or "replayed publication event" not in str(publication.get("rule", "")):
        raise RTL32AssociationManifestError("R3 publication authorization must remain live, not event replay")
    descriptor = grants[2]
    if "live_reference_held" not in descriptor.get("fields", []) or "R5 retains" not in str(descriptor.get("rule", "")):
        raise RTL32AssociationManifestError("R5 live-reference contract drift")
    lease = grants[3]
    if "requires_sidecar" not in lease.get("fields", []) or "S2 owns" not in str(lease.get("rule", "")):
        raise RTL32AssociationManifestError("S2 lease ownership drift")
    required_join = {
        "all identity values match", "all PageRef values including generation match",
        "publication packed_authoritative is true", "descriptor live_reference_held is true",
        "lease requires_sidecar is true",
    }
    if not required_join <= set(manifest.get("exact_join", [])):
        raise RTL32AssociationManifestError("exact join contract incomplete")
    if manifest.get("resolved_rtl3_0_stop") != "packed_read_association_owner" or manifest.get("remaining_rtl3_0_stop") != "partial_provider_query_position_contract blocks rtl3_5":
        raise RTL32AssociationManifestError("RTL3 stop disposition drift")
    forbidden = set(manifest.get("forbidden", []))
    required_forbidden = {
        "scheduler or page-source selection", "second metadata or residency authority",
        "S2 allocation or release policy", "R2 arbitration credit FIFO or delivery-context ownership change",
        "metadata publication or atomic-commit change", "new A4 DSE", "Full-KV fallback",
    }
    if not required_forbidden <= forbidden:
        raise RTL32AssociationManifestError("RTL3.2-A evidence boundary drift")


def validate_hashes(manifest: Mapping[str, Any], root: str | Path) -> None:
    base = Path(root).resolve()
    hashes = manifest.get("source_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise RTL32AssociationManifestError("RTL3.2-A must hash-bind sources")
    for relative, expected in hashes.items():
        path = (base / str(relative)).resolve()
        if base not in path.parents or not path.is_file() or not isinstance(expected, str) or len(expected) != 64:
            raise RTL32AssociationManifestError("invalid RTL3.2-A source hash")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RTL32AssociationManifestError(f"hash-bound source drift: {relative}")


def load_and_validate(manifest_path: str | Path, root: str | Path) -> None:
    manifest = load(manifest_path)
    validate(manifest)
    validate_hashes(manifest, root)
