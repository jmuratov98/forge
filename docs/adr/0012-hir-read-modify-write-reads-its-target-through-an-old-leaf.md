# HIR read-modify-write reads its target through an `old` leaf

HIR has one `assign(target, value)` node, which yields the stored value, and a `post_assign` that yields the value the target held before. Inside `value`, an `old` leaf reads the target's current value. Compound assignment and `++`/`--` are built from these three nodes and the ordinary operators: `x += u`, with `int x` and `unsigned u`, is `assign(%x, convert.s32(add.u32(convert.u32(old), %u)))`, and `x++` is `post_assign(%x, add.s32(old, 1))`. ADR 0008 says AST → HIR makes every conversion explicit, and a compound assignment hides two of them: the target's value converted to the computation type, and the result converted back. With `old` they stay ordinary `convert` nodes, and HIR → FIR has no C conversion rule to apply. The target is still evaluated only once, which matters once targets such as `a[f()]` exist.

## Considered Options

- **A compound-assignment node with a computation type** (clang's `CompoundAssignOperator`), plus four `++`/`--` nodes. More familiar, but the usual arithmetic conversions stay implicit inside the node, and HIR → FIR has to know them.
- **Desugaring to `x = x op e`** (GCC's `MODIFY_EXPR`, with `SAVE_EXPR` for the target). Exact while every target is a plain variable, but it evaluates the target twice, and `x++` needs a temporary to yield the old value.

## Consequences

- `old` binds to the nearest enclosing `assign` or `post_assign`, so `x += (y += 1)` nests correctly. The verifier checks that every `old` has an enclosing assignment and the type of that assignment's target.
- `old` reads the target where it sits in left-to-right evaluation order. C leaves that order open for `x += f()`.
- In the slice a target is a local or a global, named directly. Pointers will bring place expressions, which become the target, and `old` reads the place once it has been evaluated.
