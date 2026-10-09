"""Unit tests for the hotspot-taxonomy verdict classifier.

Verifies _classify_hotspot_verdict in codegreen.cli.cli matches the
documented contract for each verdict type and respects user overrides
from config["hotspot_taxonomy"]. No subprocess execution; pure logic.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codegreen.cli.cli import _classify_hotspot_verdict, _DEFAULT_HOTSPOT_TAXONOMY


def test_wrapper_low_self_ratio():
    """Function attributes inclusive energy but body does little work."""
    v = _classify_hotspot_verdict(self_ratio=0.1, inc_pct=12.0, exc_pct=1.0,
                                   calls=100, efficiency_ratio=0.5)
    assert v == "wrapper"


def test_type1_direct_high_exclusive():
    """Body-heavy hotspot with exclusive >= 10%."""
    v = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=15.0, exc_pct=14.0,
                                   calls=100, efficiency_ratio=1.0)
    assert v == "TYPE_1_DIRECT"


def test_type2_inefficient_high_per_call():
    """Exclusive >= 5% AND per-call energy is >3x the median."""
    v = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=8.0, exc_pct=8.0,
                                   calls=50, efficiency_ratio=4.5)
    assert v == "TYPE_2_INEFFICIENT"


def test_type5_frequency_many_cheap_calls():
    """High call count, modest per-call cost, modest aggregate share."""
    v = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=4.0, exc_pct=4.0,
                                   calls=1_000_000, efficiency_ratio=1.2)
    assert v == "TYPE_5_FREQUENCY"


def test_type1_direct_relaxed_fallback():
    """Exclusive between 3% and 10%, no other rule matches -> Type 1."""
    v = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=4.0, exc_pct=4.0,
                                   calls=10, efficiency_ratio=1.0)
    assert v == "TYPE_1_DIRECT"


def test_minor_below_all_thresholds():
    """Below the 3% relaxed-Type-1 floor -> minor."""
    v = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=2.0, exc_pct=1.5,
                                   calls=10, efficiency_ratio=1.0)
    assert v == "minor"


def test_wrapper_takes_precedence_over_type1():
    """A wrapper with high inclusive energy should still be classified as
    wrapper, not Type-1 -- otherwise agent wastes a turn optimising it."""
    v = _classify_hotspot_verdict(self_ratio=0.05, inc_pct=40.0, exc_pct=0.5,
                                   calls=10, efficiency_ratio=1.0)
    assert v == "wrapper"


def test_user_override_lowers_type1_threshold():
    """User can lower TYPE_1_DIRECT.exclusive_pct_min via per-verdict
    config block to be more sensitive on workloads with diffuse energy."""
    cfg = {"hotspot_taxonomy": {"TYPE_1_DIRECT": {"exclusive_pct_min": 4.0}}}
    v = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=5.0, exc_pct=5.0,
                                   calls=10, efficiency_ratio=1.0, config=cfg)
    assert v == "TYPE_1_DIRECT"


def test_user_override_raises_wrapper_threshold():
    """User can raise wrapper.self_ratio_max so functions with
    self_ratio=0.3 are still considered wrappers (test workloads where
    almost everything is a thin dispatcher)."""
    cfg = {"hotspot_taxonomy": {"wrapper": {"self_ratio_max": 0.5}}}
    v = _classify_hotspot_verdict(self_ratio=0.3, inc_pct=10.0, exc_pct=2.0,
                                   calls=10, efficiency_ratio=1.0, config=cfg)
    assert v == "wrapper"


def test_ocp_add_new_verdict_via_rules_param():
    """OCP: a user can add a brand-new verdict (e.g., TYPE_6_LOCK_BOUND)
    by passing an extra rule entry to _classify_hotspot_verdict, without
    modifying the dispatch code or the existing rule list."""
    from codegreen.cli.cli import _HOTSPOT_RULES
    custom = list(_HOTSPOT_RULES) + [{
        "verdict": "TYPE_6_LOCK_BOUND",
        "priority": 25,  # between wrapper and Type-2
        "thresholds": {"calls_min": 1000, "efficiency_ratio_max": 0.5},
        "predicate": lambda m, t: (m["calls"] > t["calls_min"]
                                   and m["efficiency_ratio"] < t["efficiency_ratio_max"]),
    }]
    v = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=8.0, exc_pct=8.0,
                                   calls=2000, efficiency_ratio=0.3,
                                   rules=custom)
    assert v == "TYPE_6_LOCK_BOUND"
    # Original behaviour intact when same metrics evaluated without the rule
    v_default = _classify_hotspot_verdict(self_ratio=0.9, inc_pct=8.0, exc_pct=8.0,
                                           calls=2000, efficiency_ratio=0.3)
    assert v_default == "TYPE_1_DIRECT"  # falls through to relaxed Type-1


def test_defaults_dict_consistent_with_helper():
    """If a user passes config=None, the helper must use the same values
    as _DEFAULT_HOTSPOT_TAXONOMY -- no drift between the two sources."""
    # Boundary: exactly at type1 threshold (10%) -> TYPE_1_DIRECT
    assert _classify_hotspot_verdict(0.9, 10.0, 10.0, 10, 1.0) == "TYPE_1_DIRECT"
    # Just below threshold -> falls through to relaxed/minor
    assert _classify_hotspot_verdict(0.9, 9.99, 9.99, 10, 1.0) == "TYPE_1_DIRECT"  # relaxed
    assert _classify_hotspot_verdict(0.9, 2.99, 2.99, 10, 1.0) == "minor"


if __name__ == "__main__":
    fns = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    fails = []
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            fails.append(fn.__name__)
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - len(fails)}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
