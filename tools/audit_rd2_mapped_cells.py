#!/usr/bin/env python3
"""Read existing flat mapped HDL; count cells and syntactic fanout without EDA."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re


def audit(path, expected_cells):
    start = re.compile(r"^\s*(\w+BWP12T30P140LVT)\s+(\S+)\s*\(")
    pin_pattern = re.compile(r"\.(\w+)\s*\(\s*([^()]+?)\s*\)")
    refs, loads, inverse_sources, buffer_sources = Counter(), Counter(), Counter(), Counter()
    drivers = {}
    active = None
    text = ""
    with path.open() as stream:
        for line in stream:
            if active is None:
                match = start.match(line)
                if not match:
                    continue
                active = match.group(1)
                text = line[match.end():]
            else:
                text += line
            if ");" not in text:
                continue
            refs[active] += 1
            pins = pin_pattern.findall(text)
            assert pins, "native cell has no parsed pins"
            for pin, net in pins:
                if "'" in net:
                    continue
                if pin in ("Z", "ZN", "Q", "QN"):
                    drivers[net] = active
                else:
                    loads[net] += 1
                if pin == "I" and active.startswith(("INV", "BUFF")):
                    kind = ("member_input" if net.startswith("io_entries_") else
                            "suffix_input" if net.startswith("io_suffixes_") else
                            "other_input" if net.startswith("io_") else "internal_net")
                    (inverse_sources if active.startswith("INV") else buffer_sources)[kind] += 1
            active = None
            text = ""
    assert active is None, "unterminated native instance"
    assert sum(refs.values()) == expected_cells, "parsed cells disagree with native report"
    return dict(cell_counts=dict(sorted(refs.items())), total_cells=sum(refs.values()),
                inverter_input_sources=dict(inverse_sources), buffer_input_sources=dict(buffer_sources),
                fanout_policy="syntactic input-pin counts; excludes port loads and assign alias resolution; not STA fanout",
                largest_syntactic_fanouts=[dict(net=net, input_pins=count, driver=drivers.get(net, "top_input_or_assign")) for net, count in loads.most_common(10)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapped_hdl", type=Path)
    parser.add_argument("--expected-cells", required=True, type=int)
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("audit assertions require Python without -O")
    print(json.dumps(audit(args.mapped_hdl, args.expected_cells), indent=2))


if __name__ == "__main__":
    main()
