# Route-A Chisel boundary

No Chisel or RTL is implemented through A4.14.  This directory exists so future
implementation artifacts share the version-controlled Route-A hardware
workspace instead of being introduced through an ignored scratch directory.

The A4.14.1 conditional disposition authorizes writing, reviewing and freezing
an architecture specification; it is not itself that freeze.  An RTL entry
therefore still requires the completed specification and a separate RTL gate.
Until then, A4.12--A4.14 outputs are analytical/proxy inputs only; they are not
an RTL interface, timing contract, or implementation authorization.
