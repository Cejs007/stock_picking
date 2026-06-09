import sqlite3
from datetime import date, datetime, UTC

from pydantic import BaseModel


class SnapshotRow(BaseModel):
    ticker: str
    rank: int
    fair_value_composite: float | None = None
    current_price: float
    master_score: float | None = None
    signal: str


class Purchase(BaseModel):
    purchase_date: date
    ticker: str
    price_paid: float
    quantity: float | None = None


class Alternative(BaseModel):
    ticker: str
    rank: int
    master_score: float | None
    snapshot_price: float
    return_pct: float | None


class RetroResult(BaseModel):
    purchase_id: int
    ticker: str
    price_paid: float
    rank_at_purchase: int | None
    return_pct: float | None
    alternatives: list[Alternative]
    delta: float | None


class Journal:
    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS snapshot_headers (
                id            INTEGER PRIMARY KEY,
                snapshot_date TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ranking_snapshots (
                id            INTEGER PRIMARY KEY,
                snapshot_id   INTEGER NOT NULL REFERENCES snapshot_headers(id),
                ticker        TEXT NOT NULL,
                rank          INTEGER,
                fair_value_composite REAL,
                current_price REAL NOT NULL,
                master_score  REAL,
                signal        TEXT
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id            INTEGER PRIMARY KEY,
                purchase_date TEXT NOT NULL,
                ticker        TEXT NOT NULL,
                price_paid    REAL NOT NULL,
                quantity      REAL,
                snapshot_id   INTEGER REFERENCES snapshot_headers(id)
            );
        """)
        self._conn.commit()

    def save_snapshot(self, rows: list[SnapshotRow], snapshot_date: date | None = None) -> int:
        if snapshot_date is None:
            snapshot_date = datetime.now(UTC).date()
        cur = self._conn.execute(
            "INSERT INTO snapshot_headers (snapshot_date) VALUES (?)",
            (snapshot_date.isoformat(),),
        )
        snapshot_id: int = cur.lastrowid  # type: ignore[assignment]
        self._conn.executemany(
            """
            INSERT INTO ranking_snapshots
                (snapshot_id, ticker, rank, fair_value_composite, current_price, master_score, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (snapshot_id, r.ticker, r.rank, r.fair_value_composite,
                 r.current_price, r.master_score, r.signal)
                for r in rows
            ],
        )
        self._conn.commit()
        return snapshot_id

    def log_purchase(self, purchase: Purchase) -> int:
        snapshot_id = self._find_snapshot_id(purchase.purchase_date)
        cur = self._conn.execute(
            """
            INSERT INTO purchases (purchase_date, ticker, price_paid, quantity, snapshot_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (purchase.purchase_date.isoformat(), purchase.ticker,
             purchase.price_paid, purchase.quantity, snapshot_id),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def _find_snapshot_id(self, purchase_date: date) -> int | None:
        row = self._conn.execute(
            """
            SELECT id FROM snapshot_headers
            WHERE snapshot_date <= ?
            ORDER BY snapshot_date DESC, id DESC
            LIMIT 1
            """,
            (purchase_date.isoformat(),),
        ).fetchone()
        return row[0] if row else None

    def get_retrospective(
        self, purchase_id: int, current_prices: dict[str, float]
    ) -> RetroResult:
        p = self._conn.execute(
            "SELECT ticker, price_paid, snapshot_id FROM purchases WHERE id = ?",
            (purchase_id,),
        ).fetchone()
        ticker, price_paid, snapshot_id = p[0], p[1], p[2]

        current_price = current_prices.get(ticker)
        return_pct = (
            (current_price - price_paid) / price_paid * 100
            if current_price is not None
            else None
        )

        if snapshot_id is None:
            return RetroResult(
                purchase_id=purchase_id,
                ticker=ticker,
                price_paid=price_paid,
                rank_at_purchase=None,
                return_pct=return_pct,
                alternatives=[],
                delta=None,
            )

        snap_rows = self._conn.execute(
            """
            SELECT ticker, rank, master_score, current_price
            FROM ranking_snapshots
            WHERE snapshot_id = ?
            ORDER BY rank ASC
            """,
            (snapshot_id,),
        ).fetchall()

        rank_at_purchase: int | None = None
        for r in snap_rows:
            if r[0] == ticker:
                rank_at_purchase = r[1]
                break

        alternatives: list[Alternative] = []
        for r in snap_rows:
            if r[0] == ticker:
                continue
            alt_current = current_prices.get(r[0])
            alt_return = (
                (alt_current - r[3]) / r[3] * 100
                if alt_current is not None
                else None
            )
            alternatives.append(
                Alternative(
                    ticker=r[0],
                    rank=r[1],
                    master_score=r[2],
                    snapshot_price=r[3],
                    return_pct=alt_return,
                )
            )

        alternatives.sort(
            key=lambda a: a.master_score if a.master_score is not None else float("-inf"),
            reverse=True,
        )
        alternatives = alternatives[:10]

        best_return = alternatives[0].return_pct if alternatives else None
        delta = (
            return_pct - best_return
            if return_pct is not None and best_return is not None
            else None
        )

        return RetroResult(
            purchase_id=purchase_id,
            ticker=ticker,
            price_paid=price_paid,
            rank_at_purchase=rank_at_purchase,
            return_pct=return_pct,
            alternatives=alternatives,
            delta=delta,
        )
