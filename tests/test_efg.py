"""Tests for Energy Flow Graph construction and serialization.

Migrated from the GreenFactor repo, which was the only place the EFG had
coverage. Uses mock CFG nodes, so no tree-sitter parse is required.
"""

import json
import pytest
from pathlib import Path

from codegreen.analysis.efg import (
    EFGNode, EFGEdge, EnergyTier, Accuracy, EFGConfig,
    build_efg, efg_to_text, efg_to_dot, efg_to_mermaid, efg_to_json,
    classify_edge_probability, longest_path_dag, extract_callee_name,
    prorate_call_edges, mark_hot_edges, assign_tiers, dot_escape,
    truncate_label, find_sccs, compute_loop_depths, get_callee_calls,
    is_null_check, infer_uninstrumented_energy,
    configure_heuristics, DEFAULT_CONFIG,
    BL_LOOP_BACK, BL_ERROR, BL_DEFAULT, BL_NULL,
    RANK_WEIGHTS,
)
from codegreen.analysis.cfg.visualization import cfg_to_dot


class MockNode:
    def __init__(self, id, ntype, text, loop_depth=0):
        self.id = id
        self.ntype = type('NT', (), {'name': ntype})()
        self.text = text
        self.loop_depth = loop_depth


MOCK_NODES = [
    MockNode(0, 'ENTRY', 'applySchemaless'),
    MockNode(1, 'STMT', 'Map<String, Object> updatedValue = new HashMap<>()'),
    MockNode(2, 'LOOP', 'for (String field : value.keySet())'),
    MockNode(3, 'COND', 'if (filter(field))'),
    MockNode(4, 'STMT', 'updatedValue.put(renamed(field), value.get(field))'),
    MockNode(5, 'STMT', 'return updatedValue'),
    MockNode(6, 'EXIT', 'exit'),
]
MOCK_EDGES = [(0,1,''), (1,2,''), (2,3,'true'), (2,5,'false'),
              (3,4,'true'), (3,2,'false'), (4,2,''), (5,6,'')]

CG_ENTRY = {
    "energy_j": 5858.3, "exclusive_energy_j": 2929.15,
    "self_ratio": 0.50, "calls": 28054,
    "energy_per_call_uj": 388246, "verdict": "TYPE_2_INEFFICIENT",
}

CG_FUNCTIONS = {
    "ReplaceField.applySchemaless": CG_ENTRY,
    "ReplaceField.filter": {
        "energy_j": 4557.27, "exclusive_energy_j": 4557.27,
        "self_ratio": 1.0, "calls": 8812900, "verdict": "TYPE_1_DIRECT",
    },
    "ReplaceField.renamed": {
        "energy_j": 882.57, "exclusive_energy_j": 882.57,
        "self_ratio": 1.0, "calls": 1783112, "verdict": "TYPE_5_FREQUENCY",
    },
}


class TestBuildEfg:
    def test_basic_construction(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test.method", "Test.java", CG_ENTRY)
        assert efg.function == "test.method"
        assert efg.exclusive_energy_j == 2929.15
        assert efg.total_energy_j == 5858.3
        assert len(efg.nodes) == 7
        assert len(efg.edges) == 8

    def test_node_rank_scores(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        assert efg.nodes[1].rank_score == 5  # ALLOC (new HashMap)
        assert efg.nodes[4].rank_score == 3  # CALL (put/renamed)
        assert efg.nodes[2].rank_score == 3  # LOOP
        assert efg.nodes[0].rank_score == 0  # ENTRY
        assert efg.nodes[6].rank_score == 0  # EXIT

    def test_no_joule_values_on_statements(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        for node in efg.nodes.values():
            assert node.energy_j == 0.0

    def test_accuracy_labels(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        assert efg.nodes[1].accuracy == Accuracy.HEURISTIC
        assert efg.nodes[0].accuracy == Accuracy.UNKNOWN
        assert efg.nodes[6].accuracy == Accuracy.UNKNOWN

    def test_tier_assignment(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        assert len(efg.hot_nodes()) > 0
        assert efg.nodes[0].tier == EnergyTier.ZERO
        assert efg.nodes[6].tier == EnergyTier.ZERO

    def test_loop_depth_from_mock(self):
        nodes = [MockNode(0, 'ENTRY', 'e'), MockNode(1, 'LOOP', 'for', loop_depth=1),
                 MockNode(2, 'STMT', 'x()', loop_depth=2), MockNode(3, 'EXIT', 'x')]
        edges = [(0, 1, ''), (1, 2, 'true'), (2, 1, ''), (1, 3, 'false')]
        efg = build_efg(nodes, edges, "ld", "L.java", {"energy_j": 1, "calls": 1})
        assert efg.nodes[1].loop_depth == 1
        assert efg.nodes[2].loop_depth == 2

    def test_loop_depth_computed_from_edges(self):
        nodes = [MockNode(0, 'ENTRY', 'e'), MockNode(1, 'LOOP', 'for'),
                 MockNode(2, 'STMT', 'x()'), MockNode(3, 'EXIT', 'x')]
        edges = [(0, 1, ''), (1, 2, 'true'), (2, 1, ''), (1, 3, 'false')]
        efg = build_efg(nodes, edges, "ld", "L.java", {"energy_j": 1, "calls": 1})
        assert efg.nodes[2].loop_depth >= 1

    def test_empty_cfg(self):
        efg = build_efg([], [], "empty", "E.java", {"energy_j": 0, "calls": 1})
        assert len(efg.nodes) == 0
        assert len(efg.edges) == 0

    def test_custom_config(self):
        cfg = EFGConfig(node_text_max=20, tier_hot=0.5)
        nodes = [MockNode(0, 'STMT', 'a' * 50)]
        efg = build_efg(nodes, [], "c", "C.java", {"energy_j": 1, "calls": 1}, config=cfg)
        assert len(efg.nodes[0].text) == 20

    def test_instrumentation_filtered(self):
        nodes = [MockNode(0, 'STMT', 'CodeGreenStandaloneRuntime.checkpoint("x")'),
                 MockNode(1, 'STMT', 'real_work()')]
        efg = build_efg(nodes, [], "i", "I.java", {"energy_j": 1, "calls": 1})
        assert efg.nodes[0].rank_score == 0
        assert efg.nodes[0].accuracy == Accuracy.UNKNOWN
        assert efg.nodes[1].rank_score > 0

    def test_calls_field_set(self):
        efg = build_efg(MOCK_NODES[:1], [], "t", "T.java", {"energy_j": 1, "calls": 500})
        assert efg.nodes[0].calls == 500


class TestCalleeRanking:
    def test_rank_from_callee_calls(self):
        nodes = [MockNode(0, 'ENTRY', 'applySchemaless'),
                 MockNode(1, 'STMT', 'result = filter(field)'),
                 MockNode(2, 'EXIT', 'exit')]
        edges = [(0, 1, ''), (1, 2, '')]
        efg = build_efg(nodes, edges, "ReplaceField.applySchemaless", "R.java",
                        CG_ENTRY, CG_FUNCTIONS)
        assert efg.nodes[1].rank_score == 8812900
        assert efg.nodes[1].accuracy == Accuracy.ESTIMATED

    def test_rank_fallback_without_cg_functions(self):
        nodes = [MockNode(0, 'STMT', 'result = filter(field)')]
        efg = build_efg(nodes, [], "test", "T.java", CG_ENTRY)
        assert efg.nodes[0].rank_score == 3


class TestLoopIterations:
    def test_loop_iteration_estimation(self):
        nodes = [MockNode(0, 'ENTRY', 'applySchemaless'),
                 MockNode(1, 'LOOP', 'for (field : keys)'),
                 MockNode(2, 'STMT', 'filter(field)'),
                 MockNode(3, 'EXIT', 'exit')]
        edges = [(0, 1, ''), (1, 2, 'true'), (2, 1, ''), (1, 3, 'false')]
        efg = build_efg(nodes, edges, "ReplaceField.applySchemaless", "R.java",
                        CG_ENTRY, CG_FUNCTIONS)
        assert efg.nodes[1].estimated_iterations is not None
        assert abs(efg.nodes[1].estimated_iterations - 8812900 / 28054) < 1.0
        assert efg.nodes[1].accuracy == Accuracy.ESTIMATED

    def test_loop_unknown_without_callee_data(self):
        nodes = [MockNode(0, 'LOOP', 'for (x : y)'),
                 MockNode(1, 'STMT', 'doSomething()'),
                 MockNode(2, 'EXIT', 'exit')]
        edges = [(0, 1, 'true'), (1, 0, ''), (0, 2, 'false')]
        efg = build_efg(nodes, edges, "test", "T.java", {"energy_j": 1, "calls": 100})
        assert efg.nodes[0].estimated_iterations is None
        assert efg.nodes[0].accuracy == Accuracy.UNKNOWN

    def test_multiple_callees_picks_highest(self):
        nodes = [MockNode(0, 'LOOP', 'for'),
                 MockNode(1, 'STMT', 'filter(x)'),
                 MockNode(2, 'STMT', 'renamed(y)'),
                 MockNode(3, 'EXIT', 'exit')]
        edges = [(0, 1, 'true'), (1, 2, ''), (2, 0, ''), (0, 3, 'false')]
        efg = build_efg(nodes, edges, "ReplaceField.applySchemaless", "R.java",
                        CG_ENTRY, CG_FUNCTIONS)
        # filter=8812900 > renamed=1783112, so iterations = 8812900/28054
        assert efg.nodes[0].estimated_iterations is not None
        assert efg.nodes[0].estimated_iterations > 300


class TestEdgeProbability:
    def test_sequential_edge(self):
        assert classify_edge_probability("", None, None) == 1.0

    def test_loop_back_edge(self):
        loop_node = EFGNode(id=2, text="for", ntype="LOOP")
        assert classify_edge_probability("true", loop_node, None) == BL_LOOP_BACK

    def test_loop_exit_edge(self):
        loop_node = EFGNode(id=2, text="for", ntype="LOOP")
        p = classify_edge_probability("false", loop_node, None)
        assert abs(p - (1.0 - BL_LOOP_BACK)) < 0.001

    def test_exception_edge(self):
        assert classify_edge_probability("exception", None, None) == BL_ERROR
        assert classify_edge_probability("catch", None, None) == BL_ERROR

    def test_default_branch(self):
        cond_node = EFGNode(id=3, text="if (x > 0)", ntype="COND")
        assert classify_edge_probability("true", cond_node, None) == BL_DEFAULT

    def test_null_check_heuristic(self):
        null_node = EFGNode(id=3, text="if (obj == null)", ntype="COND")
        p_true = classify_edge_probability("true", null_node, None)
        p_false = classify_edge_probability("false", null_node, None)
        assert p_true == 1.0 - BL_NULL
        assert p_false == BL_NULL
        assert abs(p_true + p_false - 1.0) < 0.001

    def test_unknown_label(self):
        assert classify_edge_probability("maybe", None, None) == 1.0

    def test_src_node_none_with_label(self):
        assert classify_edge_probability("true", None, None) == BL_DEFAULT


class TestCallEdgeProrating:
    def test_prorate_call_edge(self):
        nodes = [MockNode(0, 'ENTRY', 'applySchemaless'),
                 MockNode(1, 'STMT', 'x = filter(field)'),
                 MockNode(2, 'EXIT', 'exit')]
        edges = [(0, 1, ''), (1, 2, '')]
        efg = build_efg(nodes, edges, "ReplaceField.applySchemaless", "R.java",
                        CG_ENTRY, CG_FUNCTIONS)
        call_edges = [e for e in efg.edges if e.energy_j > 0]
        assert len(call_edges) >= 1
        expected = (4557.27 / 8812900) * 28054
        assert abs(call_edges[0].energy_j - expected) < 1.0
        assert call_edges[0].accuracy == Accuracy.MEASURED

    def test_no_prorate_without_cg_functions(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        assert all(e.energy_j == 0.0 for e in efg.edges)

    def test_recursive_uses_exclusive(self):
        cg_fns = {"Foo.bar": {"energy_j": 100, "exclusive_energy_j": 30, "calls": 10}}
        nodes_dict = {0: EFGNode(0, "bar(x)", "STMT", has_call=True, calls=10)}
        edges = [EFGEdge(src=0, dst=1)]
        prorate_call_edges(edges, nodes_dict, cg_fns, "Foo.bar")
        # Recursive: should use exclusive=30, not inclusive=100
        assert abs(edges[0].energy_j - 30.0) < 0.01

    def test_no_callee_found(self):
        cg_fns = {"Other.method": {"energy_j": 100, "calls": 10}}
        nodes_dict = {0: EFGNode(0, "unknown(x)", "STMT", has_call=True, calls=10)}
        edges = [EFGEdge(src=0, dst=1)]
        prorate_call_edges(edges, nodes_dict, cg_fns, "Foo.bar")
        assert edges[0].energy_j == 0.0


class TestAssignTiers:
    def test_single_node(self):
        nodes = {0: EFGNode(0, "x", "STMT", rank_score=5)}
        assign_tiers(nodes, 0.3, 0.7)
        assert nodes[0].tier == EnergyTier.HOT

    def test_two_nodes(self):
        nodes = {0: EFGNode(0, "a", "STMT", rank_score=10),
                 1: EFGNode(1, "b", "STMT", rank_score=1)}
        assign_tiers(nodes, 0.3, 0.7)
        assert nodes[0].tier == EnergyTier.HOT
        assert nodes[1].tier == EnergyTier.COLD

    def test_all_zero_rank(self):
        nodes = {0: EFGNode(0, "e", "ENTRY", rank_score=0),
                 1: EFGNode(1, "x", "EXIT", rank_score=0)}
        assign_tiers(nodes, 0.3, 0.7)
        assert all(n.tier == EnergyTier.ZERO for n in nodes.values())

    def test_ten_nodes_distribution(self):
        nodes = {i: EFGNode(i, f"n{i}", "STMT", rank_score=10 - i) for i in range(10)}
        assign_tiers(nodes, 0.3, 0.7)
        tiers = [nodes[i].tier for i in range(10)]
        assert tiers[0] == EnergyTier.HOT
        assert EnergyTier.WARM in tiers
        assert EnergyTier.COLD in tiers

    def test_custom_thresholds(self):
        nodes = {i: EFGNode(i, f"n{i}", "STMT", rank_score=5) for i in range(5)}
        assign_tiers(nodes, 0.5, 0.8)
        # All same rank: first is HOT, rest distributed by position


class TestMarkHotEdges:
    def test_single_edge(self):
        nodes = {0: EFGNode(0, "x", "STMT", rank_score=5)}
        edges = [EFGEdge(src=0, dst=1, probability=1.0)]
        mark_hot_edges(edges, nodes, 5)
        assert edges[0].is_hot

    def test_empty_edges(self):
        mark_hot_edges([], {}, 5)  # should not crash

    def test_all_same_score(self):
        nodes = {i: EFGNode(i, f"n{i}", "STMT", rank_score=3) for i in range(5)}
        edges = [EFGEdge(src=i, dst=i+1, probability=1.0) for i in range(4)]
        mark_hot_edges(edges, nodes, 5)
        assert all(e.is_hot for e in edges)  # all equal, all above threshold


class TestHotPath:
    def test_longest_path_simple(self):
        nodes = {0: EFGNode(0, "entry", "ENTRY", rank_score=0),
                 1: EFGNode(1, "a", "STMT", rank_score=5),
                 2: EFGNode(2, "b", "STMT", rank_score=1),
                 3: EFGNode(3, "c", "STMT", rank_score=10),
                 4: EFGNode(4, "exit", "EXIT", rank_score=0)}
        edges = [EFGEdge(0, 1, probability=1.0), EFGEdge(0, 2, probability=1.0),
                 EFGEdge(1, 4, probability=1.0), EFGEdge(2, 3, probability=1.0),
                 EFGEdge(3, 4, probability=1.0)]
        path = longest_path_dag(nodes, edges)
        assert 3 in path
        # Path includes 0->2->3 (highest score route); node 4 (rank=0) may or may not trail
        assert path[:3] == [0, 2, 3]

    def test_empty_graph(self):
        assert longest_path_dag({}, []) == []

    def test_single_node(self):
        nodes = {0: EFGNode(0, "x", "STMT", rank_score=5)}
        path = longest_path_dag(nodes, [])
        assert path == [0]

    def test_with_back_edge(self):
        """Back-edge (loop) should be handled via SCC collapse, not dropped."""
        nodes = {0: EFGNode(0, "e", "ENTRY", rank_score=0),
                 1: EFGNode(1, "loop", "LOOP", rank_score=3),
                 2: EFGNode(2, "body", "STMT", rank_score=5),
                 3: EFGNode(3, "x", "EXIT", rank_score=0)}
        edges = [EFGEdge(0, 1, probability=1.0), EFGEdge(1, 2, probability=0.88),
                 EFGEdge(2, 1, probability=1.0),  # back-edge
                 EFGEdge(1, 3, probability=0.12)]
        path = longest_path_dag(nodes, edges)
        # SCC {1,2} should be collapsed; path should include both
        assert 1 in path
        assert 2 in path

    def test_diamond_path(self):
        nodes = {0: EFGNode(0, "cond", "COND", rank_score=2),
                 1: EFGNode(1, "a", "STMT", rank_score=1),
                 2: EFGNode(2, "b", "STMT", rank_score=10),
                 3: EFGNode(3, "exit", "EXIT", rank_score=0)}
        edges = [EFGEdge(0, 1, probability=0.5), EFGEdge(0, 2, probability=0.5),
                 EFGEdge(1, 3, probability=1.0), EFGEdge(2, 3, probability=1.0)]
        path = longest_path_dag(nodes, edges)
        assert 2 in path  # higher rank_score path


class TestSCCs:
    def test_simple_cycle(self):
        nodes = {0: EFGNode(0, "a", "STMT"), 1: EFGNode(1, "b", "STMT")}
        edges = [EFGEdge(0, 1), EFGEdge(1, 0)]
        sccs = find_sccs(nodes, edges)
        assert len(sccs) == 1
        assert sccs[0] == {0, 1}

    def test_no_cycle(self):
        nodes = {0: EFGNode(0, "a", "STMT"), 1: EFGNode(1, "b", "STMT")}
        edges = [EFGEdge(0, 1)]
        sccs = find_sccs(nodes, edges)
        assert len(sccs) == 0

    def test_nested_cycles(self):
        nodes = {i: EFGNode(i, f"n{i}", "STMT") for i in range(4)}
        edges = [EFGEdge(0, 1), EFGEdge(1, 2), EFGEdge(2, 0),  # outer cycle
                 EFGEdge(1, 3), EFGEdge(3, 1)]  # inner cycle
        sccs = find_sccs(nodes, edges)
        # All 4 nodes are in one big SCC
        assert len(sccs) == 1
        assert len(sccs[0]) == 4


class TestComputeLoopDepths:
    def test_simple_loop(self):
        edges = [(0, 1, ''), (1, 2, 'true'), (2, 1, ''), (1, 3, 'false')]
        depths = compute_loop_depths(edges, {0, 1, 2, 3})
        assert depths[2] >= 1
        assert depths[0] == 0
        assert depths[3] == 0

    def test_no_loops(self):
        edges = [(0, 1, ''), (1, 2, '')]
        depths = compute_loop_depths(edges, {0, 1, 2})
        assert all(d == 0 for d in depths.values())


class TestExtractCalleeName:
    def test_simple_call(self):
        assert extract_callee_name("filter(field)") == "filter"

    def test_method_call_with_receiver(self):
        assert extract_callee_name("obj.method(x)") == "method"

    def test_assignment_call(self):
        assert extract_callee_name("x = compute(y)") == "compute"

    def test_no_call(self):
        assert extract_callee_name("x = 5") is None

    def test_constructor(self):
        assert extract_callee_name("new ArrayList<>()") == "ArrayList<>"

    def test_chained_call(self):
        assert extract_callee_name("foo.bar.baz(x)") == "baz"

    def test_empty_string(self):
        assert extract_callee_name("") is None


class TestGetCalleeCalls:
    def test_qualified_match(self):
        result = get_callee_calls("filter(x)", CG_FUNCTIONS, "ReplaceField.apply")
        assert result == 8812900

    def test_no_match(self):
        result = get_callee_calls("unknown(x)", CG_FUNCTIONS, "ReplaceField.apply")
        assert result is None

    def test_empty_functions(self):
        assert get_callee_calls("filter(x)", {}, "test") is None

    def test_none_functions(self):
        assert get_callee_calls("filter(x)", None, "test") is None

    def test_no_paren(self):
        assert get_callee_calls("x = 5", CG_FUNCTIONS, "test") is None


class TestDotEscape:
    def test_quotes(self):
        assert dot_escape('"hello"') == '\\"hello\\"'

    def test_newlines(self):
        assert dot_escape("a\nb") == "a b"

    def test_backslash(self):
        assert dot_escape("C:\\path") == "C:\\\\path"

    def test_carriage_return(self):
        assert dot_escape("a\rb") == "ab"

    def test_empty(self):
        assert dot_escape("") == ""

    def test_combined(self):
        assert dot_escape('a\n"b"\r') == 'a \\"b\\"'


class TestTruncateLabel:
    def test_short_text(self):
        assert truncate_label("hello", 50) == "hello"

    def test_truncate_at_semicolon(self):
        text = "int x = 0; int y = 1; int z = 2;"
        result = truncate_label(text, 20)
        assert result.endswith("...")
        assert len(result) < 25

    def test_truncate_at_paren(self):
        text = "method(very_long_argument_name_here)"
        result = truncate_label(text, 15)
        assert result.endswith("...")

    def test_hard_truncate(self):
        text = "abcdefghijklmnop"
        result = truncate_label(text, 10)
        assert result == "abcdefghij..."


class TestSerialization:
    def test_to_text_contains_structure(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        text = efg_to_text(efg)
        assert "EFG: test" in text
        assert "TYPE_2_INEFFICIENT" in text
        assert "Hot path:" in text
        assert "Branches:" in text

    def test_to_text_sorted_by_rank(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        text = efg_to_text(efg)
        lines = [ln for ln in text.split('\n') if 'rank=' in ln]
        ranks = []
        for ln in lines:
            idx = ln.index('rank=')
            end = ln.index(' ', idx)
            ranks.append(float(ln[idx+5:end]))
        assert ranks == sorted(ranks, reverse=True)

    def test_to_text_branch_probabilities(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        text = efg_to_text(efg)
        assert "p=0.88" in text or "p=0.50" in text

    def test_to_text_custom_min_rank(self):
        cfg = EFGConfig(min_rank_display=10)
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        text = efg_to_text(efg, config=cfg)
        # No nodes have rank >= 10, so only header + branches
        assert "rank=" not in text.split("Branches:")[0].split("\n", 2)[-1]

    def test_to_dot_valid_syntax(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "dot", "D.java", CG_ENTRY)
        dot = efg_to_dot(efg)
        assert dot.startswith('digraph')
        assert dot.endswith('}')
        assert dot.count('{') == dot.count('}')

    def test_to_dot_contains_all_nodes(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "dot", "D.java", CG_ENTRY)
        dot = efg_to_dot(efg)
        for nid in efg.nodes:
            assert f'  {nid} [label=' in dot

    def test_to_dot_font_and_splines(self):
        efg = build_efg(MOCK_NODES[:2], MOCK_EDGES[:1], "f", "F.java", CG_ENTRY)
        dot = efg_to_dot(efg)
        assert "fontname=" in dot
        assert "splines=" in dot
        assert "nodesep=" in dot

    def test_to_dot_subgraph_for_loops(self):
        nodes = [MockNode(0, 'ENTRY', 'e'), MockNode(1, 'LOOP', 'for'),
                 MockNode(2, 'STMT', 'x()'), MockNode(3, 'EXIT', 'x')]
        edges = [(0, 1, ''), (1, 2, 'true'), (2, 1, ''), (1, 3, 'false')]
        efg = build_efg(nodes, edges, "lp", "L.java", {"energy_j": 1, "calls": 1})
        dot = efg_to_dot(efg)
        if efg.nodes[2].loop_depth > 0:
            assert "subgraph cluster_loop" in dot

    def test_to_dot_hot_edges(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "h", "H.java", CG_ENTRY)
        dot = efg_to_dot(efg)
        hot = [e for e in efg.edges if e.is_hot]
        if hot:
            assert "penwidth=" in dot

    def test_to_dot_custom_colors(self):
        cfg = EFGConfig(tier_colors={
            EnergyTier.HOT: "#000000", EnergyTier.WARM: "#111111",
            EnergyTier.COLD: "#222222", EnergyTier.ZERO: "#333333",
        })
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "c", "C.java", CG_ENTRY)
        dot = efg_to_dot(efg, config=cfg)
        assert "#000000" in dot or "#333333" in dot

    def test_to_dot_energy_label(self):
        nodes = [MockNode(0, 'ENTRY', 'e'),
                 MockNode(1, 'STMT', 'x = filter(field)'),
                 MockNode(2, 'EXIT', 'exit')]
        edges = [(0, 1, ''), (1, 2, '')]
        efg = build_efg(nodes, edges, "ReplaceField.applySchemaless", "R.java",
                        CG_ENTRY, CG_FUNCTIONS)
        dot = efg_to_dot(efg)
        assert "taillabel=" in dot  # energy label on edge

    def test_to_dot_label_truncation(self):
        nodes = [MockNode(0, 'STMT', 'a' * 100)]
        efg = build_efg(nodes, [], "t", "T.java", {"energy_j": 1, "calls": 1})
        dot = efg_to_dot(efg)
        assert "..." in dot

    def test_to_json_all_node_fields(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        j = efg_to_json(efg)
        required = {"id", "text", "ntype", "rank_score", "energy_j",
                     "exclusive_energy_j", "self_ratio", "energy_pct",
                     "energy_per_call_uj", "estimated_iterations",
                     "tier", "accuracy", "has_alloc", "has_call",
                     "loop_depth", "calls"}
        for node in j["nodes"]:
            assert required.issubset(node.keys()), f"Missing: {required - node.keys()}"

    def test_to_json_all_edge_fields(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        j = efg_to_json(efg)
        required = {"src", "dst", "label", "probability", "energy_j", "accuracy", "is_hot"}
        for edge in j["edges"]:
            assert required.issubset(edge.keys())

    def test_to_json_enum_as_string(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        j = efg_to_json(efg)
        assert isinstance(j["accuracy"], str)
        for node in j["nodes"]:
            assert isinstance(node["tier"], str)
            assert isinstance(node["accuracy"], str)

    def test_to_json_serializable(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        j = efg_to_json(efg)
        s = json.dumps(j)
        parsed = json.loads(s)
        assert parsed["function"] == "test"

    def test_to_mermaid_valid(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "test", "T.java", CG_ENTRY)
        m = efg_to_mermaid(efg)
        assert m.startswith('graph TD')
        assert 'classDef hot' in m
        assert 'classDef warm' in m
        assert 'classDef cold' in m
        assert 'classDef zero' in m

    def test_to_mermaid_escapes_angle_brackets(self):
        nodes = [MockNode(0, 'STMT', 'Map<String, Object> x = new HashMap<>()')]
        efg = build_efg(nodes, [], "m", "M.java", {"energy_j": 1, "calls": 1})
        m = efg_to_mermaid(efg)
        assert "&lt;" in m
        assert "&gt;" in m

    def test_to_mermaid_all_nodes(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "m", "M.java", CG_ENTRY)
        m = efg_to_mermaid(efg)
        for nid in efg.nodes:
            assert f'N{nid}[' in m


class TestVisualization:
    def test_cfg_to_dot(self):
        dot = cfg_to_dot(MOCK_NODES, MOCK_EDGES, "test_method")
        assert "digraph" in dot
        assert "test_method" in dot
        assert "ENTRY" in dot

    def test_cfg_to_dot_edge_labels(self):
        dot = cfg_to_dot(MOCK_NODES, MOCK_EDGES, "m")
        assert "true" in dot
        assert "false" in dot


class TestEdgeCases:
    def test_single_node_graph(self):
        nodes = [MockNode(0, 'ENTRY', 'main')]
        efg = build_efg(nodes, [], "single", "S.java", {"energy_j": 1.0, "calls": 1})
        assert len(efg.nodes) == 1
        assert efg.hot_path == [0]

    def test_all_zero_rank(self):
        nodes = [MockNode(0, 'ENTRY', 'e'), MockNode(1, 'EXIT', 'x')]
        edges = [(0, 1, '')]
        efg = build_efg(nodes, edges, "zero", "Z.java", {"energy_j": 0, "calls": 0})
        assert all(n.tier == EnergyTier.ZERO for n in efg.nodes.values())

    def test_large_graph(self):
        nodes = [MockNode(i, 'STMT', f'stmt_{i}') for i in range(100)]
        edges = [(i, i+1, '') for i in range(99)]
        efg = build_efg(nodes, edges, "large", "L.java", {"energy_j": 100, "calls": 1000})
        assert len(efg.nodes) == 100
        assert len(efg.edges) == 99
        assert len(efg.hot_path) > 0

    def test_diamond_branch(self):
        nodes = [MockNode(0, 'COND', 'if (x)'), MockNode(1, 'STMT', 'a = 1'),
                 MockNode(2, 'STMT', 'a = 2'), MockNode(3, 'STMT', 'return a')]
        edges = [(0, 1, 'true'), (0, 2, 'false'), (1, 3, ''), (2, 3, '')]
        efg = build_efg(nodes, edges, "diamond", "D.java", {"energy_j": 10, "calls": 100})
        branch_edges = [e for e in efg.edges if e.label in ('true', 'false')]
        assert len(branch_edges) == 2
        assert abs(sum(e.probability for e in branch_edges) - 1.0) < 0.01

    def test_alloc_detection(self):
        nodes = [MockNode(0, 'STMT', 'List<String> x = new ArrayList<>()')]
        efg = build_efg(nodes, [], "alloc", "A.java", {"energy_j": 1, "calls": 1})
        assert efg.nodes[0].has_alloc is True
        assert efg.nodes[0].rank_score == 5

    def test_call_detection(self):
        nodes = [MockNode(0, 'STMT', 'result = compute(x, y)')]
        efg = build_efg(nodes, [], "call", "C.java", {"energy_j": 1, "calls": 1})
        assert efg.nodes[0].has_call is True
        assert efg.nodes[0].rank_score == 3

    def test_empty_cg_entry(self):
        efg = build_efg(MOCK_NODES, MOCK_EDGES, "empty", "E.java", {})
        assert efg.exclusive_energy_j == 0
        assert efg.calls == 1


class TestConfigurableHeuristics:
    def test_configure_loop_back(self):
        original = BL_LOOP_BACK
        configure_heuristics({"loop_back": 0.90})
        from codegreen.analysis.efg import BL_LOOP_BACK as new_val
        assert new_val == 0.90
        configure_heuristics({"loop_back": original})

    def test_configure_error(self):
        original = BL_ERROR
        configure_heuristics({"error": 0.05})
        from codegreen.analysis.efg import BL_ERROR as new_val
        assert new_val == 0.05
        configure_heuristics({"error": original})

    def test_configure_null_check(self):
        original = BL_NULL
        configure_heuristics({"null_check": 0.99})
        from codegreen.analysis.efg import BL_NULL as new_val
        assert new_val == 0.99
        configure_heuristics({"null_check": original})

    def test_configure_default(self):
        original = BL_DEFAULT
        configure_heuristics({"default": 0.60})
        from codegreen.analysis.efg import BL_DEFAULT as new_val
        assert new_val == 0.60
        configure_heuristics({"default": original})

    def test_configure_all_at_once(self):
        originals = {"loop_back": BL_LOOP_BACK, "error": BL_ERROR,
                     "null_check": BL_NULL, "default": BL_DEFAULT}
        configure_heuristics({"loop_back": 0.9, "error": 0.02, "null_check": 0.98, "default": 0.55})
        import codegreen.analysis.efg as m
        assert m.BL_LOOP_BACK == 0.9
        assert m.BL_ERROR == 0.02
        assert m.BL_NULL == 0.98
        assert m.BL_DEFAULT == 0.55
        configure_heuristics(originals)

    def test_rank_weights_extensible(self):
        assert "SWITCH" in RANK_WEIGHTS
        assert "CASE" in RANK_WEIGHTS


class TestEFGConfig:
    def test_default_config(self):
        cfg = DEFAULT_CONFIG
        assert cfg.tier_hot == 0.3
        assert cfg.dot_font_name == "Courier"

    def test_custom_config(self):
        cfg = EFGConfig(tier_hot=0.5, dot_font_size=16)
        assert cfg.tier_hot == 0.5
        assert cfg.dot_font_size == 16
        assert cfg.tier_warm == 0.7  # default

    def test_config_rank_weights_independent(self):
        cfg = EFGConfig()
        cfg.rank_weights["CUSTOM"] = 10
        assert "CUSTOM" not in RANK_WEIGHTS


class TestNullCheck:
    def test_null_equality(self):
        assert is_null_check("if (obj == null)")
        assert is_null_check("if (obj != null)")
        assert is_null_check("if (null == obj)")

    def test_not_null_substring(self):
        assert not is_null_check("if (nullable)")
        assert not is_null_check("if (annulled)")
        assert not is_null_check("getNullableValue()")

    def test_edge_probability_with_real_null(self):
        node = EFGNode(id=0, text="if (obj == null)", ntype="COND")
        assert classify_edge_probability("true", node, None) == 1.0 - BL_NULL

    def test_edge_probability_false_positive_avoided(self):
        node = EFGNode(id=0, text="if (getNullableValue())", ntype="COND")
        assert classify_edge_probability("true", node, None) == BL_DEFAULT


class TestInferredEnergy:
    def test_uninstrumented_callee_gets_inferred(self):
        nodes = {
            0: EFGNode(0, "unknown_callee(x)", "STMT", has_call=True),
            1: EFGNode(1, "exit", "EXIT"),
        }
        # inclusive=100, exclusive=30 -> 70J gap, no instrumented callees
        infer_uninstrumented_energy(nodes, 100, 30, {}, "Foo.bar")
        # No cg_functions -> should not infer (need data to check)
        assert nodes[0].energy_j == 0.0

    def test_inferred_with_gap(self):
        cg = {"Foo.known": {"energy_j": 20, "calls": 5}}
        nodes = {
            0: EFGNode(0, "known(x)", "STMT", has_call=True),
            1: EFGNode(1, "mystery(y)", "STMT", has_call=True),
        }
        # inclusive=100, exclusive=30 -> gap=70, known_callee=20 -> remaining=50
        infer_uninstrumented_energy(nodes, 100, 30, cg, "Foo.bar")
        assert nodes[1].energy_j == 50.0
        assert nodes[1].accuracy == Accuracy.INFERRED
        assert nodes[0].energy_j == 0.0  # known callee not inferred

    def test_no_gap_no_inference(self):
        nodes = {0: EFGNode(0, "x()", "STMT", has_call=True)}
        infer_uninstrumented_energy(nodes, 100, 100, {}, "Foo.bar")
        assert nodes[0].energy_j == 0.0

    def test_inferred_in_full_build(self):
        nodes = [MockNode(0, 'ENTRY', 'e'),
                 MockNode(1, 'STMT', 'mystery_callee(x)'),
                 MockNode(2, 'EXIT', 'x')]
        edges = [(0, 1, ''), (1, 2, '')]
        cg_entry = {"energy_j": 100, "exclusive_energy_j": 30, "calls": 10}
        # Pass non-empty cg_functions that doesn't contain mystery_callee
        cg_fns = {"Other.known": {"energy_j": 5, "calls": 1}}
        efg = build_efg(nodes, edges, "Foo.bar", "F.java", cg_entry, cg_fns)
        assert efg.nodes[1].accuracy == Accuracy.INFERRED
        assert efg.nodes[1].energy_j == 70.0


class TestInferredAccuracy:
    def test_inferred_accuracy_available(self):
        assert Accuracy.INFERRED.name == "INFERRED"


class TestWithRealData:
    def test_from_codegreen_json(self):
        path = Path("data/experiments/codegreen_kafka_9bb2f78.json")
        if not path.exists():
            pytest.skip("No CodeGreen data available")
        with open(path) as f:
            cg = json.load(f)
        functions = cg.get("runs", [{}])[0].get("functions", {})
        top_fn = max(functions.items(), key=lambda x: x[1].get("exclusive_energy_j", 0))
        efg = build_efg(MOCK_NODES, MOCK_EDGES, top_fn[0], "ReplaceField.java",
                        top_fn[1], functions)
        assert efg.exclusive_energy_j > 0
        assert efg.verdict in ("TYPE_1_DIRECT", "TYPE_2_INEFFICIENT",
                                "TYPE_5_FREQUENCY", "wrapper", "minor")
        j = efg_to_json(efg)
        assert "self_ratio" in j["nodes"][0]
        assert "energy_pct" in j["nodes"][0]


class TestAdapter:
    """Coverage for adapter.py, which bridges the real tree-sitter CFG into
    build_efg. Nothing else in this file exercises a real CFG -- everything
    above uses MockNode -- so this is the only place a regression in the CFG
    shape (succs/edge_labels/CNode fields) would be caught."""

    SOURCE = '''
    public class Sample {
        public static int hot(int n) {
            int total = 0;
            for (int i = 0; i < n; i++) {
                if (i % 2 == 0) { total += compute(i); }
                else { total -= 1; }
            }
            String s = new String("x");
            return total + s.length();
        }
        static int compute(int x) { return x * x; }
    }
    '''

    def test_build_efg_for_method_by_short_name(self):
        from codegreen.analysis.efg import build_efg_for_method
        efg = build_efg_for_method(self.SOURCE, "hot", "Sample.java",
                                   {"energy_j": 10.0, "exclusive_energy_j": 6.0,
                                    "calls": 100, "verdict": "TYPE_1_DIRECT"})
        assert efg.function == "hot"
        assert efg.exclusive_energy_j == 6.0
        assert len(efg.nodes) > 0
        assert efg.hot_path

    def test_build_efg_for_method_by_qualified_name(self):
        from codegreen.analysis.efg import build_efg_for_method
        efg = build_efg_for_method(self.SOURCE, "Sample.hot", "Sample.java")
        assert efg.function == "Sample.hot"

    def test_build_efg_for_method_unknown_raises_with_candidates(self):
        from codegreen.analysis.efg import build_efg_for_method
        with pytest.raises(KeyError, match="hot"):
            build_efg_for_method(self.SOURCE, "doesNotExist", "Sample.java")

    def test_cfg_to_efg_inputs_shape(self):
        from codegreen.analysis.cfg.builder import build_per_method_cfgs
        from codegreen.analysis.efg import cfg_to_efg_inputs
        per_method = build_per_method_cfgs(self.SOURCE)
        _, cfg = next(t for t in per_method if t[0] == "hot")
        nodes, edges = cfg_to_efg_inputs(cfg)
        assert all(hasattr(n, "id") for n in nodes)
        assert all(isinstance(e, tuple) and len(e) == 3 for e in edges)

    def test_strip_to_short(self):
        from codegreen.analysis.efg import strip_to_short
        assert strip_to_short("Sample.hot") == "hot"
        assert strip_to_short("hot") == "hot"
        assert strip_to_short("Sample.hot:()I") == "()I"
