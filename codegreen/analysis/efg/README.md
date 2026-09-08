# Energy Flow Graph (EFG)

CFG nodes annotated with measured CodeGreen energy: which statement, branch,
or call actually burned the joules, not just which method.

## Status

This module is functional but not finished. It was pulled into the repo as
part of a bulk cleanup rather than shipped as a feature, so it was missing
its package exports, its CLI wiring, and its test coverage until this
reorganization. Those gaps are now closed:

- Imports and exports work (`from codegreen.analysis.efg import ...`).
- A bridge from a real tree-sitter CFG to `build_efg` exists (`adapter.py`).
- A runnable example exists with no measurement pipeline required
  (`example/`).
- 119 of 120 tests pass (1 skips without a live CodeGreen data file), including
  5 new ones that exercise a real CFG instead of the mock objects the other
  115 use.

What is not done: six known defects listed below, no CLI verb, and no
production wiring to a live `codegreen project ...` energy run (the example
fabricates its energy numbers). This is intended as a starting project: pick
one issue, reproduce it with the example, fix it, extend the tests. Nothing
here is load-bearing for another part of the codebase yet, so there is room
to change the API if a fix needs it.

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

`cg_entry` and `cg_functions` come from a real `codegreen project ...` run in
production. `example/demo.py` fabricates them so the module can be run
without one.

## Layout

| file | owns |
|---|---|
| `types.py` | `EFGNode`, `EFGEdge`, `EnergyFlowGraph`, `Accuracy`, `EnergyTier` |
| `heuristics.py` | Ball and Larus branch probabilities, `EFGConfig`, tunables |
| `graph.py` | `build_efg` and the annotation passes it runs |
| `paths.py` | Tarjan SCC collapse and longest path hot path extraction |
| `serialize.py` | `efg_to_text`, `efg_to_dot`, `efg_to_mermaid`, `efg_to_json` |
| `adapter.py` | bridges `codegreen.analysis.cfg` (`CFG`/`CNode`) into `build_efg`'s plain lists |
| `example/` | `Sample.java` and `demo.py`, runnable without a live measurement pipeline |

`codegreen.analysis.cfg.energy_flow` still resolves every name in this
package. It is a forwarding shim for old imports, not a second copy of the
code.

## Known issues

Each of these reproduces on `example/demo.py`. All predate this
reorganization: the logic is unchanged from before the split. Verified by
running the code, not by reading it. All 115 pre-existing tests use
`MockNode` fixtures and never exercise a real tree-sitter CFG, so none of
these were caught before now.

1. **`compute_loop_depths` treats an `if` block as a loop.** Its back-edge
   check is "does any node point back at me," which is true for ordinary
   control-flow merges, not only loop back-edges. On `example/Sample.java`,
   the `if` node is flagged as a loop header, and `collect_body` does not
   stop at the loop's real boundary, so it also pulls in unrelated nodes
   after the loop ends. In the demo output, the `String s = new String(...)`
   line sits after the loop but reports `loop_depth=1`. Fix needs a real
   back-edge check (dominance, or trust the CFG builder's own loop
   labeling), not "any predecessor exists."

2. **`find_sccs` crashes past about 1000 CFG nodes.** It implements Tarjan's
   algorithm recursively. A straight-line chain of exactly 999 nodes raises
   `RecursionError` against Python's default recursion limit. `collect_body`
   right next to it is already iterative for this same reason, so the fix
   pattern already exists in the file. Needs an iterative Tarjan or an
   explicit stack.

3. **`EnergyFlowGraph.accuracy` is never set from real data.** It defaults to
   `MEASURED` in the dataclass and nothing in `build_efg` ever assigns it.
   Build an EFG with zero energy data and `efg_to_json()["accuracy"]` still
   says `"MEASURED"`, even while every individual node in that same graph is
   correctly marked `UNKNOWN`. Should be derived from whether `cg_entry`
   actually had nonzero energy.

4. **Four `EFGNode` fields are always `0.0`.** `self_ratio`, `energy_pct`,
   `energy_per_call_uj`, and `exclusive_energy_j` are never assigned anywhere
   in `graph.py`. They exist in the dataclass and get serialized into every
   JSON output, always zero. Either wire them up from `cg_functions` and
   `cg_entry`, or drop them so the schema stops implying data that is not
   there.

5. **Dead parameters and a redundant string heuristic.**
   `build_edges(cg_functions, fn_name, fn_calls)` never reads its last three
   arguments. `classify_edge_probability(dst_node)` never reads `dst_node`.
   Separately, `build_efg` re-derives `has_alloc` and `has_call` by string
   matching (`'new ' in text`, `'(' in text`), even though the real `CNode`
   already carries tree-sitter-derived `has_alloc` and `calls` fields. On
   `example/Sample.java`, the string heuristic over-counts calls: it flags
   `return total + s.length()` and the `new String(...)` allocation as
   calls, where tree-sitter found exactly one. Prefer the real `CNode`
   fields on the common path (through `adapter.py`) and fall back to the
   heuristic only for callers that pass something else.

6. **`strip_to_short` mis-splits a fqn that carries a JVM descriptor.** For
   `"Class.method:(I)Ljava/lang/String;"` it returns the descriptor
   (`"(I)Ljava/lang/String;"`), not `"method"`, because it splits on `.`
   before it splits on `:`. This only matters if a caller ever passes a
   colon-suffixed fqn. `adapter.py` carried this over unchanged from the
   code it replaces (`context_tools.py`'s `_strip_to_short` in the
   downstream consumer repo). `TestAdapter::test_strip_to_short` in
   `tests/test_efg.py` documents the current behavior, not the intended one.

None of these are structural. `build_efg`'s three-pass design (rank, then
tiers, then edges, then hot path) is sound, and the split into this package
should make each issue independently ownable and testable. Start with 1 and
2: issue 1 produces silently wrong output, issue 2 is a crash on any real
method of nontrivial size.
