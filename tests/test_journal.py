from datetime import date

import pytest

from stock_picking.journal import Journal, Purchase, SnapshotRow


@pytest.fixture
def journal() -> Journal:
    return Journal(db_path=":memory:")


def _row(ticker: str, rank: int, master_score: float, price: float = 100.0) -> SnapshotRow:
    return SnapshotRow(
        ticker=ticker,
        rank=rank,
        fair_value_composite=price * 1.2,
        current_price=price,
        master_score=master_score,
        signal="BUY" if master_score > 0 else "WAIT",
    )


# ── #1 ──────────────────────────────────────────────────────────────────────
def test_save_snapshot_returns_int_id(journal: Journal) -> None:
    rows = [_row("AAPL", 1, 20.0), _row("MSFT", 2, 15.0)]
    snapshot_id = journal.save_snapshot(rows, date(2024, 1, 10))
    assert isinstance(snapshot_id, int)


# ── #2 ──────────────────────────────────────────────────────────────────────
def test_two_snapshots_have_different_ids(journal: Journal) -> None:
    id1 = journal.save_snapshot([_row("AAPL", 1, 20.0)], date(2024, 1, 10))
    id2 = journal.save_snapshot([_row("AAPL", 1, 20.0)], date(2024, 2, 10))
    assert id1 != id2


# ── #3 ──────────────────────────────────────────────────────────────────────
def test_log_purchase_returns_int_id(journal: Journal) -> None:
    purchase_id = journal.log_purchase(
        Purchase(purchase_date=date(2024, 3, 1), ticker="AAPL", price_paid=150.0)
    )
    assert isinstance(purchase_id, int)


# ── #5 ──────────────────────────────────────────────────────────────────────
def test_log_purchase_no_prior_snapshot_links_none(journal: Journal) -> None:
    # Purchase with no snapshot ever saved → snapshot_id is None, retro has no rank.
    purchase_id = journal.log_purchase(
        Purchase(purchase_date=date(2024, 3, 1), ticker="AAPL", price_paid=150.0)
    )
    retro = journal.get_retrospective(purchase_id, {"AAPL": 160.0})
    assert retro.rank_at_purchase is None
    assert retro.alternatives == []


# ── #10 ─────────────────────────────────────────────────────────────────────
def test_get_retrospective_no_snapshot_returns_null_rank_and_no_alts(journal: Journal) -> None:
    pid = journal.log_purchase(
        Purchase(purchase_date=date(2024, 3, 1), ticker="AAPL", price_paid=150.0)
    )
    retro = journal.get_retrospective(pid, {"AAPL": 170.0})
    assert retro.rank_at_purchase is None
    assert retro.alternatives == []
    assert retro.delta is None


# ── #11 ─────────────────────────────────────────────────────────────────────
def test_get_retrospective_fewer_than_10_alternatives(journal: Journal) -> None:
    # Only 3 tickers in snapshot; bought one → 2 alternatives returned (not 10).
    journal.save_snapshot(
        [_row("AAPL", 1, 30.0), _row("MSFT", 2, 20.0), _row("GOOG", 3, 10.0)],
        date(2024, 1, 10),
    )
    pid = journal.log_purchase(
        Purchase(purchase_date=date(2024, 1, 15), ticker="AAPL", price_paid=100.0)
    )
    retro = journal.get_retrospective(pid, {"AAPL": 110.0, "MSFT": 220.0, "GOOG": 150.0})
    assert len(retro.alternatives) == 2


# ── #9 ──────────────────────────────────────────────────────────────────────
def test_get_retrospective_computes_delta(journal: Journal) -> None:
    # AAPL (bought): paid 100, now 110  → +10 %
    # MSFT (best alt, higher score): snapshot 200, now 240 → +20 %
    # GOOG (lower score): snapshot 100, now 150 → +50 %
    # best alt by master_score is MSFT (score 25) → delta = 10 - 20 = -10
    journal.save_snapshot(
        [
            _row("AAPL", 3, 5.0, 100.0),
            _row("MSFT", 1, 25.0, 200.0),
            _row("GOOG", 2, 15.0, 100.0),
        ],
        date(2024, 1, 10),
    )
    pid = journal.log_purchase(
        Purchase(purchase_date=date(2024, 1, 15), ticker="AAPL", price_paid=100.0)
    )
    retro = journal.get_retrospective(
        pid, {"AAPL": 110.0, "MSFT": 240.0, "GOOG": 150.0}
    )
    assert retro.delta == pytest.approx(-10.0)


# ── #8 ──────────────────────────────────────────────────────────────────────
def test_get_retrospective_computes_return_pct(journal: Journal) -> None:
    # paid 200, current 250 → return = 25 %
    journal.save_snapshot([_row("AAPL", 1, 10.0)], date(2024, 1, 10))
    pid = journal.log_purchase(
        Purchase(purchase_date=date(2024, 1, 15), ticker="AAPL", price_paid=200.0)
    )
    retro = journal.get_retrospective(pid, {"AAPL": 250.0})
    assert retro.return_pct == pytest.approx(25.0)


# ── #7 ──────────────────────────────────────────────────────────────────────
def test_get_retrospective_alternatives_sorted_by_master_score_desc(journal: Journal) -> None:
    # 12 tickers in snapshot; AAPL bought. Remaining 11 → top 10 returned, in score order.
    tickers = ["AAPL"] + [f"T{i}" for i in range(11)]
    rows = [_row(tickers[0], 1, 50.0)] + [
        _row(tickers[i + 1], i + 2, float(i * 5)) for i in range(11)
    ]
    journal.save_snapshot(rows, date(2024, 1, 10))
    pid = journal.log_purchase(
        Purchase(purchase_date=date(2024, 1, 15), ticker="AAPL", price_paid=100.0)
    )
    prices = {t: 110.0 for t in tickers}
    retro = journal.get_retrospective(pid, prices)

    assert len(retro.alternatives) == 10
    scores = [a.master_score for a in retro.alternatives]
    assert scores == sorted(scores, reverse=True)


# ── #6 ──────────────────────────────────────────────────────────────────────
def test_get_retrospective_returns_rank_of_bought_ticker(journal: Journal) -> None:
    journal.save_snapshot(
        [_row("AAPL", 1, 30.0), _row("MSFT", 2, 20.0), _row("GOOG", 3, 10.0)],
        date(2024, 1, 10),
    )
    pid = journal.log_purchase(
        Purchase(purchase_date=date(2024, 1, 15), ticker="MSFT", price_paid=300.0)
    )
    retro = journal.get_retrospective(pid, {"AAPL": 180.0, "MSFT": 330.0, "GOOG": 120.0})
    assert retro.rank_at_purchase == 2


# ── #4 ──────────────────────────────────────────────────────────────────────
def test_log_purchase_links_to_most_recent_prior_snapshot(journal: Journal) -> None:
    # Two snapshots: Jan and Feb. Purchase is in March → links to Feb snapshot.
    snap_jan = journal.save_snapshot(
        [_row("AAPL", 1, 20.0), _row("MSFT", 2, 15.0)], date(2024, 1, 10)
    )
    snap_feb = journal.save_snapshot(
        [_row("AAPL", 1, 22.0), _row("MSFT", 2, 17.0)], date(2024, 2, 10)
    )
    purchase_id = journal.log_purchase(
        Purchase(purchase_date=date(2024, 3, 1), ticker="AAPL", price_paid=150.0)
    )
    retro = journal.get_retrospective(purchase_id, {"AAPL": 160.0, "MSFT": 200.0})
    # rank_at_purchase comes from the Feb snapshot
    assert retro.rank_at_purchase == 1
    _ = snap_jan  # referenced so linter doesn't complain
