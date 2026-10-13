import json
import math
import sqlite3
from datetime import UTC, datetime

from pydantic import BaseModel, Field

_WATCHLIST_DDL = """
    CREATE TABLE IF NOT EXISTS watchlist (
        ticker TEXT PRIMARY KEY,
        company_name TEXT,
        currency TEXT,
        mos_override REAL,
        dcf_growth_override REAL,
        dcf_wacc_override REAL,
        dcf_terminal_g REAL,
        dcf_years INTEGER,
        added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""


class WatchlistEntry(BaseModel):
    ticker: str
    company_name: str | None = None
    currency: str | None = None
    added_at: datetime


class TickerOverrides(BaseModel):
    mos_override: float | None = None
    dcf_growth_override: float | None = None
    dcf_wacc_override: float | None = None
    dcf_terminal_g: float | None = None
    dcf_years: int | None = None


class ValuationResult(BaseModel):
    ticker: str
    # Per-model fair value per share, keyed by MODEL_REGISTRY name.
    fair_values: dict[str, float | None] = Field(default_factory=dict)
    fair_value_composite: float | None = None
    # Range and coefficient of variation of the active composite models.
    fair_value_low: float | None = None
    fair_value_high: float | None = None
    fair_value_cv: float | None = None
    current_price: float
    # Quote currency of current_price and every fair value above. None only for
    # rows saved before the currency column existed.
    currency: str | None = None
    master_score: float | None = None
    buy_target: float | None = None
    signal: str
    warnings: list[str] = []
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Watchlist:
    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS valuations (
                ticker TEXT PRIMARY KEY,
                fair_values TEXT NOT NULL DEFAULT '{}',
                fair_value_composite REAL,
                current_price REAL NOT NULL,
                master_score REAL,
                buy_target REAL,
                signal TEXT NOT NULL,
                warnings TEXT NOT NULL DEFAULT '[]',
                calculated_at TEXT NOT NULL
            )
        """)
        self._migrate_fair_values_column()
        self._add_missing_columns(
            "valuations",
            {
                "fair_value_low": "REAL",
                "fair_value_high": "REAL",
                "fair_value_cv": "REAL",
                "currency": "TEXT",
            },
        )
        self._conn.execute(_WATCHLIST_DDL)
        self._conn.commit()
        self._migrate_nullable_dcf_overrides()

    def _migrate_nullable_dcf_overrides(self) -> None:
        # Before #18 these columns were NOT NULL DEFAULT 0.03 / 10, so "never set"
        # was stored as the old hardcoded default. Rebuild them nullable and treat
        # those exact values as unset, so the global Settings apply.
        notnull = {r[1]: r[3] for r in self._conn.execute("PRAGMA table_info(watchlist)")}
        if not notnull.get("dcf_terminal_g"):
            return
        self._conn.executescript(f"""
            BEGIN;
            ALTER TABLE watchlist RENAME TO watchlist_legacy;
            {_WATCHLIST_DDL};
            INSERT INTO watchlist (
                ticker, company_name, currency, mos_override, dcf_growth_override,
                dcf_wacc_override, dcf_terminal_g, dcf_years, added_at
            )
            SELECT ticker, company_name, currency, mos_override, dcf_growth_override,
                   dcf_wacc_override, NULLIF(dcf_terminal_g, 0.03), NULLIF(dcf_years, 10),
                   added_at
            FROM watchlist_legacy;
            DROP TABLE watchlist_legacy;
            COMMIT;
        """)

    def _migrate_fair_values_column(self) -> None:
        # Pre-registry DBs stored one REAL column per model; fold them into the
        # fair_values JSON keyed by registry name. Legacy columns are left unused.
        columns = {r[1] for r in self._conn.execute("PRAGMA table_info(valuations)")}
        if "fair_values" in columns:
            return
        self._conn.execute(
            "ALTER TABLE valuations ADD COLUMN fair_values TEXT NOT NULL DEFAULT '{}'"
        )
        self._conn.execute("""
            UPDATE valuations SET fair_values = json_object(
                'graham', fair_value_graham,
                'pe_relative', fair_value_pe,
                'ev_ebitda', fair_value_ev_ebitda,
                'dcf', fair_value_dcf
            )
        """)

    def _add_missing_columns(self, table: str, columns: dict[str, str]) -> None:
        # Additive migration for columns introduced after a DB was created.
        # Table and column names are code constants, never user input.
        existing = {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")}
        for column, sql_type in columns.items():
            if column not in existing:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")

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
                ticker, fair_values, fair_value_composite, current_price,
                master_score, buy_target, signal, warnings, calculated_at,
                fair_value_low, fair_value_high, fair_value_cv, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                fair_values = excluded.fair_values,
                fair_value_composite = excluded.fair_value_composite,
                current_price = excluded.current_price,
                master_score = excluded.master_score,
                buy_target = excluded.buy_target,
                signal = excluded.signal,
                warnings = excluded.warnings,
                calculated_at = excluded.calculated_at,
                fair_value_low = excluded.fair_value_low,
                fair_value_high = excluded.fair_value_high,
                fair_value_cv = excluded.fair_value_cv,
                currency = excluded.currency
            """,
            (
                result.ticker,
                json.dumps(
                    {
                        name: fv if fv is not None and math.isfinite(fv) else None
                        for name, fv in result.fair_values.items()
                    }
                ),
                result.fair_value_composite,
                result.current_price,
                result.master_score,
                result.buy_target,
                result.signal,
                json.dumps(result.warnings),
                result.calculated_at.isoformat(),
                result.fair_value_low,
                result.fair_value_high,
                result.fair_value_cv,
                result.currency,
            ),
        )
        self._conn.commit()

    def get_valuations(self) -> list[ValuationResult]:
        rows = self._conn.execute(
            """
            SELECT ticker, fair_values, fair_value_composite, current_price,
                   master_score, buy_target, signal, warnings, calculated_at,
                   fair_value_low, fair_value_high, fair_value_cv, currency
            FROM valuations
            """
        ).fetchall()
        return [
            ValuationResult(
                ticker=r[0],
                fair_values=json.loads(r[1]),
                fair_value_composite=r[2],
                current_price=r[3],
                master_score=r[4],
                buy_target=r[5],
                signal=r[6],
                warnings=json.loads(r[7]),
                calculated_at=datetime.fromisoformat(r[8]),
                fair_value_low=r[9],
                fair_value_high=r[10],
                fair_value_cv=r[11],
                currency=r[12],
            )
            for r in rows
        ]
