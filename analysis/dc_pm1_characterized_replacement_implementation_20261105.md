# PM1 characterized replacement implementation — 2026-11-05

## Implemented screen

The planned saved-DDC replacement screen is implemented by:

- `hardware/route_a/dc/run_pm1_characterized_replacement_screen.sh`;
- `hardware/route_a/dc/screen_pm1_characterized_replacement.tcl`.

The runner rejects an existing output root, requires the accepted entry-id
repair DDC SHA-256
`29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326`,
requires the accepted p19 candidate SHA-256
`dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671`,
rechecks the complete p19 hash manifest, and verifies the frozen library hash
from `dc_feasibility_fair_v1` before invoking DC.

The Tcl flow:

1. reads the accepted mapped Route-A DDC and captures immutable baseline child
   and top reports;
2. requires the unique hierarchical `pageManager` instance and 62,000 mapped
   Page Manager sequential cells;
3. analyzes only the contextual `route_a_page_manager_pm1` candidate;
4. requires 62,000 precompile candidate registers and exactly one retained R5
   availability-array proxy;
5. uses compatible `change_link pageManager route_a_page_manager_pm1` without
   `-force` or a pin map, then links the top;
6. characterizes the child from the real instance with timing, constraints and
   connections;
7. compiles only the candidate child with the same medium map effort;
8. requires 62,000 postcompile registers and the retained proxy, then writes
   candidate and relinked-top diagnostic reports.

The accepted mapped top is never compiled by this screen.

## Static verification

- runner `bash -n`: pass;
- runner `--help`: pass;
- Tcl structural completeness: pass;
- `git diff --check`: pass.

Pre-launch script SHA-256 values are:

- runner:
  `e03e2a8a5964c9afa7858f067a0c6945aee6a3edb3f09a4334fb8923487e16fe`;
- Tcl:
  `9d210958e95d618c8cfe8c232e90204615b54167c43c7b39d19d5cebc18f35a3`.

This implementation does not alter RTL, constraints, clock period, state,
parent control, array-proxy boundaries or accepted DDC content.  A successful
run will remain a bottom-up diagnostic screen, not final full-top or PPA
evidence.

## Stack-guard successor

The first execution exposed one runner omission: unlike the accepted full DC
runner, it entered DC with an 8,192 KiB stack and failed with explicit
`VER-30` stack overflow while analyzing the 146,880-bit release reduction.
The successor now raises the stack limit to unlimited, fails before DC if that
cannot be established, and emits
`KVZAP_PM1_CHARACTERIZED_STACK_PASS stack_kb=unlimited`.  No synthesis input,
Tcl command, constraint or acceptance gate changes with this correction.
The r2 runner SHA-256 is
`adb68b432b465019018ac00809f2ece6503a2cdffa30616064e7105bd2c66b5e`;
the Tcl SHA-256 remains unchanged.
