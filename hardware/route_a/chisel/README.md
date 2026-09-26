# Route-A Chisel boundary

No Chisel or RTL is implemented in A4.12.  This directory exists so future
implementation artifacts share the version-controlled Route-A hardware
workspace instead of being introduced through an ignored scratch directory.

An RTL entry requires a separate architecture-spec gate.  Until then, A4.12
outputs are analytical macro/cycle inputs only; they are not an RTL interface,
timing contract, or implementation authorization.
