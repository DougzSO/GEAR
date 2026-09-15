"""
GEAR v3 Phase 6 -- RNG-stream utility, per-country-scenario granularity.

``docs/rework/PHASE6_DESIGN.md`` Section 3 left the RNG granularity question
(per-country vs. per-country-scenario) explicitly open, and asked for
whichever answer is confirmed to be written as a small, isolated,
explicitly-parameterized utility rather than hardcoded into a simulation
loop. The author has since confirmed (session decision, not re-derived
here): **per-country-scenario**, not per-country -- every downstream output
this project reports is already split by ``water_scenario`` (``bau``/
``opt``/``pes``, ``src.config.AQUEDUCT_SCENARIOS``), so the randomness
source should match that granularity to avoid injecting spurious
correlation across scenarios that are supposed to be statistically
independent draws.

Mirrors ``src/index/monte_carlo.py``'s ``country_rng(country, magnitude)``
in shape exactly (``zlib.crc32`` key -> ``numpy.random.SeedSequence`` spawn
off ``config.RANDOM_SEED`` -> ``default_rng``), extended with one more key
segment (``scenario``) and a free-text ``purpose`` segment so the same
``(country, scenario)`` pair can still produce independent, reproducible
streams for different uses (e.g. a general-MC draw stream vs. some other
future Phase 6 use) without colliding.

Deliberately kept OUT of ``sensitivity_recompute.py`` (that module's own
docstring says it does not resolve RNG granularity) and out of the Sobol
driver (``sobol_sensitivity.py``): SALib's own sampler generates its design
matrix via its own ``seed`` argument, not through this utility -- see
``sobol_sensitivity.py``'s module docstring for why a per-country-scenario
key has no attachment point there. This utility's real consumer is the
general Monte Carlo uncertainty-propagation driver
(``general_mc.py``, Phase 6.1), one stream per ``(country, water_scenario)``
pair.
"""

from __future__ import annotations

import zlib

import numpy as np

from src.config import RANDOM_SEED


def phase6_rng(country: str, scenario: str, purpose: str) -> np.random.Generator:
    """Independent, reproducible RNG stream keyed by ``(country, scenario,
    purpose)``. Same inputs -> same stream, always (determinism); different
    inputs on any one of the three segments -> a statistically independent
    stream (``numpy.random.SeedSequence``'s spawn-key guarantee), mirroring
    ``monte_carlo.country_rng``'s own crc32+SeedSequence construction."""
    key = zlib.crc32(f"{country}|{scenario}|{purpose}".encode("utf-8"))
    seed_sequence = np.random.SeedSequence(RANDOM_SEED, spawn_key=(key,))
    return np.random.default_rng(seed_sequence)
