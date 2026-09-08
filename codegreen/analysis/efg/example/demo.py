#!/usr/bin/env python
"""Runnable EFG quickstart. From the repo root: python -m codegreen.analysis.efg.example.demo

Builds the EFG for Sample.hot() using fabricated CodeGreen energy data (a real
integration reads that data from an actual codegreen run instead) and prints
every serialization format so a new contributor can see the shapes without
needing a live measurement pipeline first.
"""

from pathlib import Path

from codegreen.analysis.efg import build_efg_for_method, efg_to_dot, efg_to_json, efg_to_mermaid, efg_to_text

SOURCE = (Path(__file__).parent / "Sample.java").read_text()

# Stand-in for what a real `codegreen project java ...` run would report.
CG_ENTRY = {"energy_j": 10.0, "exclusive_energy_j": 6.0, "calls": 100, "verdict": "TYPE_1_DIRECT"}
CG_FUNCTIONS = {"compute": {"calls": 5000, "energy_j": 4.0, "exclusive_energy_j": 4.0}}

if __name__ == "__main__":
    efg = build_efg_for_method(SOURCE, "hot", "Sample.java", CG_ENTRY, CG_FUNCTIONS)
    print(efg_to_text(efg))
    print("\n--- JSON ---")
    print(efg_to_json(efg))
    print("\n--- DOT (first 3 lines) ---")
    print("\n".join(efg_to_dot(efg).splitlines()[:3]))
    print("\n--- Mermaid (first 3 lines) ---")
    print("\n".join(efg_to_mermaid(efg).splitlines()[:3]))
