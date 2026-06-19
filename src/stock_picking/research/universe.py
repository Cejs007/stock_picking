"""Multi-sector benchmark universe for AutoResearch.

Deliberately spread across sectors so the tuned weights are NOT overfit to one
slice of the market (the original 3-ticker benchmark was 2/3 big tech). Sector
labels here are the strings yfinance returns in info["sector"]; the harness
re-reads the live sector at collection time, so these are only a hint for what
the universe is meant to cover.

Edit freely — more names per sector = more reliable per-sector tuning. Sectors
with fewer than MIN_SECTOR_SAMPLES usable names are left on their prior template
(the "with fallback" behaviour).
"""

# Sector -> representative liquid tickers with long public history.
UNIVERSE: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "ORCL", "ADBE", "CSCO", "TXN", "ACN"],
    "Communication Services": ["GOOGL", "META", "VZ", "T", "DIS", "CMCSA"],
    "Healthcare": ["JNJ", "PFE", "MRK", "ABT", "UNH", "MDT"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "AXP", "BLK"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Basic Materials": ["LIN", "SHW", "FCX", "NUE", "DOW"],
    "Industrials": ["HON", "UNP", "CAT", "GE", "LMT", "UPS"],
    "Consumer Cyclical": ["HD", "MCD", "NKE", "SBUX", "LOW", "TJX"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "CL"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
    "Real Estate": ["PLD", "AMT", "SPG", "O", "PSA"],
}


def all_tickers() -> list[str]:
    seen: list[str] = []
    for tickers in UNIVERSE.values():
        for t in tickers:
            if t not in seen:
                seen.append(t)
    return seen
