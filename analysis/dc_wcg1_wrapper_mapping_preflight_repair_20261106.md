# WCG1 real-wrapper native preflight hierarchy repair

Run `wcg1_wrapper_mapping_sta_d860732_20261106_r1` is preserved with outer
exit **7**. Compile/export, 366,336-bit field/row checks, same-header/state
comparison and explicit inline/P3 closure passed. DC then linked 4,608 native
gates and found their E pins/characterization, but rejected size-only
application to a native leaf inside the multiply instantiated inline module:

```text
Error: -all_instances option must be used with instance cells when the parent instance is not unique. (UID-192)
Error: Cannot set size_only on cell 'native_gate'. (UID-457)
```

DC returned a false command status rather than raising the outer Tcl catch.
The later binding marker alone was therefore insufficient. The runner's
independent native Error scan correctly rejected the preflight before either
reference or gated formal mapping started. Neither side's mapping directory
exists. This is a flow hierarchy-attribute failure, not a functional, area,
setup or hold result.

The preserved preflight native log SHA-256 is
`967fbabc36e77080f7f12d39d8cafe8e9f4d46927ab460c9ffd3c73745b38fcc`.
The runner's fail-closed error gate and old exit/status/files remain unchanged.

The installed DC O-2018.06-SP1 command reference
`/opt/synopsys/dc2018/O-2018.06-SP1/doc/syn/man/cat2/set_size_only.2`
confirms the syntax `set_size_only [-all_instances] object_list [true|false]`.
For multiply instantiated subdesigns, `-all_instances` applies the setting to
corresponding leaf cells in every instance. That is exactly the intended
4,608-gate sizing-only policy; it does not change a gate, net or RTL function.

The versioned successor changes only that command to
`set_size_only -all_instances $gates true` and explicitly checks its return
status before claiming native-binding success. Existing error scanning remains
mandatory. No uniqueness expansion, gate removal, clock exception, timing
relaxation, data reduction or production RTL change is introduced.
Two ordinary-Tcl regression cases reproduce the native command contract:
all-instance application is mandatory and false status must stop preflight.
Together with prior source/postcheck tests, **36 cases pass**.

The authorized retry must use a new immutable archive, root, log and tmux.
Do not edit or resume r1's frozen package. The new launch record will carry
its exact identities and observations; binding success remains pending until
the successor's native error-free preflight completes. RD1+PM1 is not queried,
modified or restarted. No new area/timing/PPA conclusion follows.
