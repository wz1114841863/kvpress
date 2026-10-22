# MR-2 M2 entry/update-data provenance gap

**Status:** bounded production-provenance audit complete; RTL storage realization
is blocked pending one separately authorized typed update carrier.

## Scope and conclusion

This audit examines only the frozen M2 `head_control_rmw` and
`span_owner_rmw` semantic members after the bounded production control owner
at `9c7541a`. It does not reopen R3 publication, admission, pruning, R6
authority, R2 arbitration, M2 organization, macro selection, or PPA.

The existing production path supplies enough identity and control provenance to
accept the two member operations, but **does not supply entry/update-data
provenance**. A real M2 array must therefore not be implemented by treating
`opaque_address_ref`, `owner`, a group tag, or a test fixture as entry contents
or a write operand.

## Audited facts

| Required fact | Existing production carrier / accepted event | Audit result |
|---|---|---|
| Bank identity | `kv_head`, retained by R3 and accepted through `pending_payload_read_binding_in.fire` with admission/authority | Present; it selects the frozen logical head-affine bank only. |
| Object identity | The two fixed member values `head_control_rmw` and `span_owner_rmw` | Present; this fixes object class, not its data layout. |
| Group identity | `(layer, stage_generation, transaction_group_tag, member)` on `M2GroupMemberRequest.fire` | Present. |
| Logical mapping provenance | `m2_group_opaque_address_ref`, `m2_group_owner`, supplied by the outer pending-payload/location boundary and checked by the accepted R3 group | Present but explicitly opaque; it is neither a physical/local entry key nor entry data. |
| Entry layout and width | No production field; A4's 59/50 raw and 64/64 padded figures are accounting envelopes, not pointer-bearing entry definitions | **Absent.** |
| Old entry value / RMW operand or canonical transform | No production field or owner | **Absent.** |
| New entry value, valid bit, byte/bit mask, write enable | No production field or owner | **Absent.** |
| Storage fault source | R3 can consume a matching member `fault` response, but the bounded control owner emits only `ok` and has no typed storage-error producer | **Absent for a real storage wrapper.** |

The only current origin of the mapping fields is the explicit outer
`pending_payload_read_binding_in` boundary of `RouteAMeasurementDut`; source
tests drive its values as fixtures. There is no internal Scala producer of a
typed M2 entry declaration, and neither `M2GroupMemberRequest` nor
`M2GroupMemberResponse` contains data, mask, read value, or update operand.

## Minimum missing interface decision

No existing production owner can currently be named as the unique producer of
entry/update data. Before RTL may continue, a separately approved carrier must
name that owner and define one accepted event, conceptually:

`M2EntryUpdateDeclaration.fire` before the corresponding
`M2GroupMemberRequest.fire`.

Its minimum semantic content must be determined by the named producer rather
than inferred by R3 or the storage wrapper:

1. exact logical entry key/scoping rule for each `head_control` and
   `span_owner` object, distinct from the existing opaque mapping reference;
2. defined entry layout/width and valid-state meaning;
3. old-value read requirement plus either canonical RMW operand/function or
   exact new-value and write-mask/enable semantics;
4. the group identity and immutable provenance used to bind the declaration to
   exactly one of the two existing member requests; and
5. accepted `ok`/fault response rules, including backpressure and reset
   invalidation.

The designated consumer would be the M2 storage/wrapper only. R3 would keep
its existing request ordering and status-only completion acceptance; it must
not derive, transform, or own entry contents. The storage wrapper must retain
head-control's atomic dual-replica update, keep span-owner independent, and
return a matching typed fault before any publication candidate can proceed.

## Authorization boundary

Adding this declaration would be a narrow realization-interface extension, not
an intended change to pruning, admission, R3's one atomic publication point,
R6 authority, or R2 scheduling. Nonetheless, the current frozen contract does
not define its producer or data semantics, so the extension requires explicit
authorization before Chisel edits. Until then:

- `RouteAM2ProductionControlOwner` remains the accepted bounded control owner;
- an M2 entry/data array, update response, and array-only split are not
  implemented;
- M2 storage/wrapper/queue-staging cost remains `unestimated_not_zero`; and
- no macro, DC/CACTI, timing, area, energy, or PPA conclusion is permitted.

## Evidence consulted

- `analysis/architecture_spec.md`, §8: M2 object classes, opaque logical
  request contract, fault/reset requirements, and non-selection boundary.
- `analysis/route_a4120_metadata_interface_inventory_contract.md`: 59/50 and
  64/64 values are accounting envelopes and do not define pointer/handle
  widths.
- `PendingPayloadReadBinding`, `M2GroupMemberRequest`, and
  `M2GroupMemberResponse` in
  `hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala`.
- `RouteAMeasurementDut` and `RouteAM2P3Wrapper` production wiring, plus the
  existing directed-test fixture drivers.
