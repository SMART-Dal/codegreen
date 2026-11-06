"""One registry of language adapters for every sampler a metric provider uses.

A LanguageAdapter bundles a language's components: `events` (an EventSampler: stacks of any event, a CPU timer or a
hardware event, normalized to (scope, name, line) frames) and `lines` (a LineSampler: line-level CPU samples with frame,
library and irreducible patterns as data). Components register independently from the module that implements them, so a
new language, or a new component of an existing language, is one registration; nothing in the core branches on a language.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional

from codegreen.analysis.metrics import Availability, Registry

COMPONENTS = ("events", "lines")


@dataclass(frozen=True)
class LanguageAdapter:
    name: str
    events: Optional[Any] = None   # sampling.EventSampler
    lines: Optional[Any] = None    # line_sampling.LineAdapter

    def probe(self) -> Availability:
        parts = [c for c in COMPONENTS if getattr(self, c) is not None]
        if not parts:
            return Availability(self.name, False, "no sampler component registered")
        details: dict = {"components": parts}
        if self.lines is not None:
            details["lines"] = self.lines.probe({})
        return Availability(self.name, True, details=details)


LANGUAGES: Registry = Registry("language")


def add(name: str, **parts) -> LanguageAdapter:
    """Register `parts` (events=..., lines=...) for `name`, creating its adapter on first use; registering the same
    component twice raises."""
    unknown = set(parts) - set(COMPONENTS)
    if unknown:
        raise ValueError(f"unknown language component(s) {sorted(unknown)}; known: {COMPONENTS}")
    cur = LANGUAGES.get(name) if name in LANGUAGES.names() else LanguageAdapter(name)
    for c, part in parts.items():
        if getattr(cur, c) is not None:
            raise ValueError(f"language {name!r} already has a {c} component")
        cur = replace(cur, **{c: part})
    LANGUAGES.put(cur)
    return cur


def get(name: str) -> LanguageAdapter:
    return LANGUAGES.get(name)


def component(name: str, part: str):
    """The `part` component of `name`, raising KeyError when the language or that component is not registered."""
    c = get(name) if name in LANGUAGES.names() else None
    if c is None or getattr(c, part) is None:
        raise KeyError(f"no {part} sampler for language {name!r}; languages with one: {supporting(part)}")
    return getattr(c, part)


def supporting(part: str) -> list[str]:
    return sorted(a.name for a in LANGUAGES.all() if getattr(a, part) is not None)
