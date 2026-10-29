#!/usr/bin/env python3
"""Verify a materialized DC proxy tree without launching DC."""

import argparse
import json
import re
from pathlib import Path


def locate_module(text, module):
    start = re.search(r"^module\s+" + re.escape(module) + r"\b", text, re.MULTILINE)
    if start is None:
        raise RuntimeError("missing module " + module)
    header_end = text.find(");", start.end()) + 2
    end = re.search(r"^endmodule\b", text[header_end:], re.MULTILINE)
    if header_end == 1 or end is None:
        raise RuntimeError("bad module " + module)
    return start.start(), header_end, header_end + end.end()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--proxy-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.load(args.manifest.open("r"))
    report = {"schema_version": "kvzap-dc-array-proxy-check-v1", "boundaries": [], "pass": False}
    for boundary in manifest["boundaries"]:
        path = args.proxy_root / boundary["source_member"]
        text = path.read_text(encoding="utf-8")
        start, header_end, end = locate_module(text, boundary["module"])
        body = text[header_end:end]
        marker = text[max(0, start - 96):start]
        if "syn_black_box" not in marker or body.strip() != "endmodule":
            raise RuntimeError("boundary is not an empty typed proxy: " + boundary["module"])
        for parent in boundary["parent_controls"]:
            parent_path = args.proxy_root / parent["source_member"]
            parent_text = parent_path.read_text(encoding="utf-8")
            parent_start, parent_header_end, parent_end = locate_module(parent_text, parent["module"])
            parent_body = parent_text[parent_header_end:parent_end]
            if "syn_black_box" in parent_text[max(0, parent_start - 96):parent_start] or parent_body.strip() == "endmodule":
                raise RuntimeError("parent control was incorrectly proxied: " + parent["module"])
        report["boundaries"].append({"id": boundary["id"], "module": boundary["module"], "proxy": True})
    for root, filelist, expected in [
        (args.proxy_root, "full_kv_control_projection.f", 1),
        (args.proxy_root / "route_a_control_projection_split", "route_a_control_projection.f", 182),
    ]:
        entries = [line.strip() for line in (root / filelist).read_text().splitlines() if line.strip()]
        if len(entries) != expected or any(not (root / entry).is_file() for entry in entries):
            raise RuntimeError("filelist broken: " + str(root / filelist))
    report["pass"] = True
    with args.report.open("w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("KVZAP_DC_ARRAY_PROXY_CHECK_PASS")


if __name__ == "__main__":
    main()
