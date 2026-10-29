#!/usr/bin/env python3
"""Check the split Route-A successor HDL before proxy/DC preparation.

The checker is intentionally source-only: it validates the exact emitted
split-Verilog closure and emits a portable relative filelist.  It does not
select a macro, launch synthesis, or treat an external service as zero cost.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path


TOP = "route_a_control_projection"
SPLIT = "route_a_control_projection_split"
OUT_FILELIST = "route_a_control_projection_successor.f"
OLD_BACKING = ("descriptorEntryImage", "descriptorReadable", "descriptorValidRecords")
REQUIRED_TOKENS = (
    "functional_r5_descriptor_service_request_valid",
    "functional_r5_descriptor_service_response_valid",
)
RETAINED_PARENTS = ("route_a_page_manager", "route_a_m2_p3_wrapper", "route_a_s2_gqa_source_wrapper")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise RuntimeError(message)


def module_body(text: str, module: str) -> str:
    match = re.search(r"^module\s+" + re.escape(module) + r"\b", text, re.MULTILINE)
    if match is None:
        fail(f"missing module {module}")
    header_end = text.find(");", match.end())
    if header_end < 0:
        fail(f"unterminated header for {module}")
    end = re.search(r"^endmodule\b", text[header_end + 2 :], re.MULTILINE)
    if end is None:
        fail(f"missing endmodule for {module}")
    return text[header_end + 2 : header_end + 2 + end.start()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    split = root / SPLIT
    if not split.is_dir():
        fail(f"missing split directory: {split}")
    files = sorted(path for path in split.glob("*.sv") if path.is_file())
    if not files:
        fail("split directory has no SV files")
    relative = [str(path.relative_to(root)) for path in files]
    if len(relative) != len(set(relative)):
        fail("duplicate successor filelist entry")
    if not all((root / item).is_file() for item in relative):
        fail("successor filelist is not closed")
    (root / OUT_FILELIST).write_text("\n".join(relative) + "\n", encoding="utf-8")

    texts = {path.name: path.read_text(encoding="utf-8") for path in files}
    top_hits = [name for name, text in texts.items()
                if re.search(r"^module\s+" + TOP + r"\b", text, re.MULTILINE)]
    if len(top_hits) != 1:
        fail(f"expected exactly one top module, found {top_hits}")
    top_text = texts[top_hits[0]]
    for token in REQUIRED_TOKENS:
        if token not in top_text:
            fail(f"missing required typed top port token: {token}")
    for token in OLD_BACKING:
        if any(token in text for text in texts.values()):
            fail(f"functional descriptor backing leaked into successor HDL: {token}")
    parents = {}
    for parent in RETAINED_PARENTS:
        owner = next((name for name, text in texts.items()
                      if re.search(r"^module\s+" + re.escape(parent) + r"\b", text, re.MULTILINE)), None)
        if owner is None:
            fail(f"missing retained parent control: {parent}")
        body = module_body(texts[owner], parent)
        if not body.strip() or "syn_black_box" in body:
            fail(f"retained parent control is empty or black-boxed: {parent}")
        parents[parent] = owner

    aggregate = hashlib.sha256()
    for item in relative:
        aggregate.update(item.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(sha256_file(root / item).encode("ascii"))
        aggregate.update(b"\n")
    report = {
        "schema_version": "kvzap-r5-descriptor-externalization-successor-v1",
        "top": TOP,
        "filelist": OUT_FILELIST,
        "file_count": len(relative),
        "sv_bytes": sum((root / item).stat().st_size for item in relative),
        "closure_sha256": aggregate.hexdigest(),
        "top_source": relative[[path.name for path in files].index(top_hits[0])],
        "required_typed_ports": list(REQUIRED_TOKENS),
        "excluded_functional_backing": list(OLD_BACKING),
        "retained_parents": parents,
        "pass": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("KVZAP_R5_DESCRIPTOR_SUCCESSOR_CHECK_PASS " + str(args.report))


if __name__ == "__main__":
    main()
