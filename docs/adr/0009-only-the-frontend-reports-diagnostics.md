# Only the frontend reports diagnostics

Every user-facing diagnostic comes from a language frontend, on its AST: name lookup, type checking, constraint violations, warnings and "not yet supported". Lowering from the AST to HIR, and every lowering below it, cannot fail on input the frontend accepted. A failure there is a bug in Forge, caught by assertions and IR verifiers, not reported as a diagnostic. When the backend can't yet handle a construct, the frontend rejects it as "not yet supported". This keeps every lowering infallible and keeps the knowledge of what is supported in one place, instead of spread across five layers.

## Consequences

- Growing the backend means widening the frontend's "not yet supported" checks in step.
- Lowerings don't return `forge::expected`. Their preconditions are what the previous layer's verifier checks.
- Failures in tools Forge runs, such as the host assembler (ADR 0007), are reported as bugs in Forge, not as user errors.
