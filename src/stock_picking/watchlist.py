import json
import sqlite3
from datetime import UTC, datetime

from pydantic import BaseModel


class WatchlistEntry(BaseModel):
    ticker: str
    company_name: str | None = None
    currency: str | None = None
    added_at: datetime


class TickerOverrides(BaseModel):
    mos_override: float | None = None
    dcf_growth_override: float | None = None
    dcf_wacc_override: float | None = None
    dcf_terminal_g: float = 0.03
    dcf_years: int = 10


class ValuationResult(BaseModel):
    ticker: str
    fair_value_dcf: float | None = None
    fair_value_graham: float | None = None
    fair_value_pe: float | None = None
    fair_value_ev_ebitda: float | None = None
    fair_value_composite: float | None = None
    current_price: float
    master_score: float | None = None
    buy_target: float | None = None
    signal: str
    warnings: list[str] = []
    calculated_at: datetime = datetime.now(UTC)


class Watchlist:
    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS valuations (
                ticker TEXT PRIMARY KEY,
                fair_value_dcf REAL,
                fair_value_graham REAL,
                fair_value_pe REAL,
                fair_value_ev_ebitda REAL,
                fair_value_composite REAL,
                current_price REAL NOT NULL,
                master_score REAL,
                buy_target REAL,
                signal TEXT NOT NULL,
                warnings TEXT NOT NULL DEFAULT '[]',
                calculated_at TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY,
                company_name TEXT,
                currency TEXT,
                mos_override REAL,
                dcf_growth_override REAL,
                dcf_wacc_override REAL,
                dcf_terminal_g REAL NOT NULL DEFAULT 0.03,
                dcf_years INTEGER NOT NULL DEFAULT 10,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

    def add(self, ticker: str, company_name: str | None = None, currency: str | None = None) -> None:
        self._conn.execute(
            """
            INSERT INTO watchlist (ticker, company_name, currency)
            VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO NOTHING
            """,
            (ticker, company_name, currency),
        )
        self._conn.commit()

    def remove(self, ticker: str) -> None:
        self._conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        self._conn.commit()

    def tickers(self) -> list[str]:
        rows = self._conn.execute("SELECT ticker FROM watchlist").fetchall()
        return [r[0] for r in rows]

    def get_all_entries(self) -> list[WatchlistEntry]:
        rows = self._conn.execute(
            "SELECT ticker, company_name, currency, added_at FROM watchlist"
        ).fetchall()
        return [
            WatchlistEntry(
                ticker=r[0],
                company_name=r[1],
                currency=r[2],
                added_at=datetime.fromisoformat(r[3]),
            )
            for r in rows
        ]

    def set_overrides(self, ticker: str, overrides: TickerOverrides) -> None:
        exists = self._conn.execute(
            "SELECT 1 FROM watchlist WHERE ticker = ?", (ticker,)
        ).fetchone()
        if exists is None:
            raise KeyError(ticker)
        self._conn.execute(
            """
            UPDATE watchlist
            SET mos_override = ?,
                dcf_growth_override = ?,
                dcf_wacc_override = ?,
                dcf_terminal_g = ?,
                dcf_years = ?
            WHERE ticker = ?
            """,
            (
                overrides.mos_override,
                overrides.dcf_growth_override,
                overrides.dcf_wacc_override,
                overrides.dcf_terminal_g,
                overrides.dcf_years,
                ticker,
            ),
        )
        self._conn.commit()

    def get_overrides(self, ticker: str) -> TickerOverrides | None:
        row = self._conn.execute(
            "SELECT mos_override, dcf_growth_override, dcf_wacc_override, dcf_terminal_g, dcf_years"
            " FROM watchlist WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if row is None:
            return None
        return TickerOverrides(
            mos_override=row[0],
            dcf_growth_override=row[1],
            dcf_wacc_override=row[2],
            dcf_terminal_g=row[3],
            dcf_years=row[4],
        )

    def save_valuation(self, result: ValuationResult) -> None:
        self._conn.execute(
            """
            INSERT INTO valuations (
                ticker, fair_value_dcf, fair_value_graham, fair_value_pe,
                fair_value_ev_ebitda, fair_value_composite, current_price,
                master_score, buy_target, signal, warnings, calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                fair_value_dcf = excluded.fair_value_dcf,
                fair_value_graham = excluded.fair_value_graham,
                fair_value_pe = excluded.fair_value_pe,
                fair_value_ev_ebitda = excluded.fair_value_ev_ebitda,
                fair_value_composite = excluded.fair_value_composite,
                current_price = excluded.current_price,
                master_score = excluded.master_score,
                buy_target = excluded.buy_target,
                signal = excluded.signal,
                warnings = excluded.warnings,
                calculated_at = excluded.calculated_at
            """,
            (
                result.ticker,
                result.fair_value_dcf,
                result.fair_value_graham,
                result.fair_value_pe,
                result.fair_value_ev_ebitda,
                result.fair_value_composite,
                result.current_price,
                result.master_score,
                result.buy_target,
                result.signal,
                json.dumps(result.warnings),
                result.calculated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_valuations(self) -> list[ValuationResult]:
        rows = self._conn.execute(
            """
            SELECT ticker, fair_value_dcf, fair_value_graham, fair_value_pe,
                   fair_value_ev_ebitda, fair_value_composite, current_price,
                   master_score, buy_target, signal, warnings, calculated_at
            FROM valuations
            """
        ).fetchall()
        return [
            ValuationResult(
                ticker=r[0],
                fair_value_dcf=r[1],
                fair_value_graham=r[2],
                fair_value_pe=r[3],
                fair_value_ev_ebitda=r[4],
                fair_value_composite=r[5],
                current_price=r[6],
                master_score=r[7],
                buy_target=r[8],
                signal=r[9],
                warnings=json.loads(r[10]),
                calculated_at=datetime.fromisoformat(r[11]),
            )
            for r in rows
        ]
