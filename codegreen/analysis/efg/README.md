# Energy Flow Graph (EFG)

CFG nodes annotated with measured CodeGreen energy: which statement, branch, or
call actually burned the joules, not just which method.

## Quickstart

```
python -m codegreen.analysis.efg.example.demo
```

or from your own code:

```python
from codegreen.analysis.efg import build_efg_for_method, efg_to_text

source = open("MyClass.java").read()
cg_entry = {"energy_j": 10.0, "exclusive_energy_j": 6.0, "calls": 100, "verdict": "TYPE_1_DIRECT"}
efg = build_efg_for_method(source, "myMethod", "MyClass.java", cg_entry)
print(efg_to_text(efg))
```

`cg_entry` / `cg_functions` come from a real `codegreen project ...` run in
production; `example/demo.py` fabricates them so the module can be exercised
without one.

## Layout

| file | owns |
|---|---|
| `types.py` | `EFGNode`, `EFGEdge`, `EnergyFlowGraph`, `Accuracy`, `EnergyTier` |
| `heuristics.py` | Ball & Larus branch probabilities, `EFGConfig`, tunables |
| `graph.py` | `build_efg` and the annotation passes it runs |
| `paths.py` | Tarjan SCC collapse + longest-path hot-path extraction |
| `serialize.py` | `efg_to_text` / `efg_to_dot` / `efg_to_mermaid` / `efg_to_json` |
| `adapter.py` | bridges `codegreen.analysis.cfg` (`CFG`/`CNode`) into `build_efg`'s plain lists |
| `example/` | `Sample.java` + `demo.py`, runnable without a live measurement pipeline |

`codegreen.analysis.cfg.energy_flow` still resolves every name here — it is a
forwarding shim for old imports, not a second copy.

## Known issues

Everything below reproduces on `example/demo.py` and predates this reorganization
(diffed against the pre-split file; the logic is unchanged). Verified by direct
inspection, not just by the fact tests pass — **all 115 existing tests use
`MockNode` fixtures and never exercise a real tree-sitter CFG, so none of these
were caught.**

1. **`compute_loop_depths` misidentifies `if` blocks as loops** — its back-edge
   test ("does any node point back at me") is true for ordinary control-flow
   merges, not just loop backedges. On `example/Sample.java`, node 7 (the `if`)
   is flagged as a loop header, and `collect_body` doesn't stop at the true
   loop's boundary, so it also swallows unrelated nodes after the loop (see the
   `String s = new String(...)` line reporting `loop_depth=1` in the demo
   output, despite sitting after the loop closes). Fix needs a real backedge
   check (dominance, or trust the CFG builder's own loop labeling) rather than
   "any predecessor exists."

2. **`find_sccs` (Tarjan, recursive) crashes past ~1000 CFG nodes** —
   `RecursionError` at a straight-line chain of exactly 999 nodes against
   Python's default recursion limit. `collect_body` next to it is already
   iterative for the same reason. Needs an iterative Tarjan or an explicit
   stack.

3. **`EnergyFlowGraph.accuracy` is never set from data** — it defaults to
   `MEASURED` in the dataclass and nothing in `build_efg` ever assigns it, so
   `efg_to_json()["accuracy"]` says `"MEASURED"` even when built with zero
   energy data (see `example/demo.py`'s ENTRY/EXIT nodes, which are
   simultaneously `UNKNOWN` at the node level while the graph claims
   `MEASURED` overall). Should be derived from whether `cg_entry` actually had
   nonzero energy.

4. **Four `EFGNode` fields are always `0.0`**: `self_ratio`, `energy_pct`,
   `energy_per_call_uj`, `exclusive_energy_j`. No code path in `graph.py`
   assigns any of them; they exist in the dataclass and in
   `serialize.efg_to_json` but are dead. Either wire them up from
   `cg_functions`/`cg_entry` or drop them so the JSON schema stops implying
   data that isn't there.

5. **Dead parameters / string-heuristic duplication of real data** —
   `build_edges(cg_functions, fn_name, fn_calls)` uses none of its last three
   arguments; `classify_edge_probability(dst_node)` never reads `dst_node`.
   Separately, `build_efg` re-derives `has_alloc`/`has_call` from substring
   matching (`'new ' in text`, `'(' in text`) even though the real `CNode`
   already carries tree-sitter-derived `has_alloc` and `calls` fields — on
   `example/Sample.java` the substring heuristic over-counts calls (it flags
   `return total + s.length()` and the `new String(...)` allocation as calls)
   where tree-sitter found exactly one. Prefer the CNode fields when the input
   actually is a `CNode` (the common path, via `adapter.py`) and fall back to
   the heuristic only for callers passing something else.

6. **`strip_to_short` mis-splits a JVM-descriptor-suffixed fqn** — for
   `"Class.method:(I)Ljava/lang/String;"` it returns the descriptor
   (`"(I)Ljava/lang/String;"`), not `"method"`, because it splits on `.` before
   `:` and the descriptor's own slashes don't collide with that split but a
   trailing dot inside it would. Only matters if callers ever pass a
   colon-suffixed fqn; `adapter.py` inherited this verbatim from the
   downstream consumer it replaces (`context_tools.py:_strip_to_short`) rather
   than introducing it. `tests/test_efg.py::TestAdapter::test_strip_to_short`
   documents the current (surprising) behavior rather than the intended one.

None of these are structural — `build_efg`'s three-pass design (rank → tiers →
edges → hot path) is sound, and the split of this package should make each one
independently ownable and testable. Start with #1 and #2: #1 is silently wrong
output, #2 is a crash on any real method of nontrivial size.
