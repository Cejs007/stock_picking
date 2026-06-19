"""AutoResearch: empirical, overfit-guarded tuning of the valuation ensemble.

See docs/AUTORESEARCH.md for the methodology (Karpathy-style propose -> evaluate
-> keep-if-better-on-validation loop, single scalar objective, per-sector
templates with a default fallback).
"""
