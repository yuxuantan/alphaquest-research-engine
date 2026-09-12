# Canonical literature records

This directory is the version-controlled, append-only P3 metadata store. Only
the 13 schema-governed family directories may appear beside this README.
Captured bytes and derived text are content-addressed under the ignored
`run-store/literature/` root and are verified whenever a terminal capture is
read for validation or claim extraction.

Do not hand-edit canonical JSON. Use `alphaquest literature` so global and
object hash chains, idempotency, exact references, and reservation conflicts
are checked under the P3 lock.
