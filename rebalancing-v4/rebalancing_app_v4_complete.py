"""
Return Stacking Engine
Version 4.0.0 — audited quantitative architecture

Single-file Streamlit application. Portfolio configuration, scenario assumptions,
market-data status and schema metadata can be exported/imported as JSON.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import math
import threading
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

APP_VERSION = "4.0.0"
CONFIG_SCHEMA_VERSION = 2
ROLE_OPTIONS = ["legacy_equity", "gold", "trend", "efficient_core", "custom"]
SLEEVE_OPTIONS = ["Legacy Core", "Return Stacking"]
PROXY_OPTIONS = ["", "VT", "AVUV", "SCZ", "MTUM", "BND", "GLD", "DBMF"]
FACTOR_NAMES = ["equity", "bond", "gold", "trend"]
FACTOR_LABELS = {
    "equity": "Azionario",
    "bond": "Bond",
    "gold": "Oro",
    "trend": "Trend",
}
PROXY_CONVERSION_MODE = {
    "BND": "rate_only",  # intentional approximation for the NTSG bond overlay
}
QUOTE_MAX_AGE_DAYS = 4
YF_LOCK = threading.RLock()

DEFAULT_STRESS = pd.DataFrame(
    [
        {"Scenario": "Shock COVID-19", "Equity %": -34.2, "Bond %": -10.4, "Gold %": -3.6, "Trend %": 2.1},
        {"Scenario": "Shock Tassi 2022", "Equity %": -18.0, "Bond %": -15.0, "Gold %": -0.8, "Trend %": 24.4},
        {"Scenario": "Shock stile 2008", "Equity %": -54.0, "Bond %": 5.2, "Gold %": 16.8, "Trend %": 18.0},
    ]
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "target_mode": "NAV Totale",
    "ntsg_is_plug": True,
    "risk_years": 5,
    "expected_returns_pct": {"equity": 7.5, "bond": 3.5, "gold": 5.0, "trend": 6.5, "cash": 2.5},
    "overlay_implementation_bps": 20.0,
    "stress_matrix": DEFAULT_STRESS.to_dict(orient="records"),
}

DEFAULT_PORTFOLIO = [
    {"ticker":"VWCE.DE","name":"Vanguard FTSE All-World Acc","sleeve":"Legacy Core","role":"legacy_equity","shares":1155,"pmc":118.50,"price":165.70,"price_asof":"","price_source":"Reference","target":0.0,"priority":5,"equity_lt":100.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"VT","bond_proxy":"","gold_proxy":"","trend_proxy":"","tax_rate":26.0},
    {"ticker":"IWDA.AS","name":"iShares Core MSCI World Acc","sleeve":"Legacy Core","role":"legacy_equity","shares":315,"pmc":88.30,"price":126.80,"price_asof":"","price_source":"Reference","target":0.0,"priority":5,"equity_lt":100.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"VT","bond_proxy":"","gold_proxy":"","trend_proxy":"","tax_rate":26.0},
    {"ticker":"CSSPX.MI","name":"iShares Core S&P 500 Acc","sleeve":"Legacy Core","role":"legacy_equity","shares":50,"pmc":490.00,"price":719.00,"price_asof":"","price_source":"Reference","target":0.0,"priority":5,"equity_lt":100.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"VT","bond_proxy":"","gold_proxy":"","trend_proxy":"","tax_rate":26.0},
    {"ticker":"ZPRV.DE","name":"SPDR MSCI USA Small Cap Value","sleeve":"Legacy Core","role":"legacy_equity","shares":219,"pmc":46.20,"price":81.90,"price_asof":"","price_source":"Reference","target":0.0,"priority":5,"equity_lt":100.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"AVUV","bond_proxy":"","gold_proxy":"","trend_proxy":"","tax_rate":26.0},
    {"ticker":"ZPRX.DE","name":"SPDR MSCI Europe Small Cap Value","sleeve":"Legacy Core","role":"legacy_equity","shares":255,"pmc":43.80,"price":56.40,"price_asof":"","price_source":"Reference","target":0.0,"priority":5,"equity_lt":100.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"SCZ","bond_proxy":"","gold_proxy":"","trend_proxy":"","tax_rate":26.0},
    {"ticker":"AVWS.DE","name":"Avantis Global Small Cap Value","sleeve":"Legacy Core","role":"legacy_equity","shares":197,"pmc":22.10,"price":25.50,"price_asof":"","price_source":"Reference","target":0.0,"priority":5,"equity_lt":100.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"AVUV","bond_proxy":"","gold_proxy":"","trend_proxy":"","tax_rate":26.0},
    {"ticker":"IWMO.MI","name":"iShares Edge MSCI World Momentum","sleeve":"Legacy Core","role":"legacy_equity","shares":194,"pmc":76.50,"price":138.20,"price_asof":"","price_source":"Reference","target":0.0,"priority":5,"equity_lt":100.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"MTUM","bond_proxy":"","gold_proxy":"","trend_proxy":"","tax_rate":26.0},
    {"ticker":"SGLN.MI","name":"iShares Physical Gold ETC","sleeve":"Return Stacking","role":"gold","shares":0,"pmc":75.00,"price":75.20,"price_asof":"","price_source":"Reference","target":10.0,"priority":1,"equity_lt":0.0,"bond_lt":0.0,"gold_lt":100.0,"trend_lt":0.0,"equity_proxy":"","bond_proxy":"","gold_proxy":"GLD","trend_proxy":"","tax_rate":26.0},
    {"ticker":"DBMFE.PA","name":"iMGP DBi Managed Futures Trend UCITS (EUR)","sleeve":"Return Stacking","role":"trend","shares":0,"pmc":132.70,"price":132.70,"price_asof":"","price_source":"Reference","target":10.0,"priority":1,"equity_lt":0.0,"bond_lt":0.0,"gold_lt":0.0,"trend_lt":100.0,"equity_proxy":"","bond_proxy":"","gold_proxy":"","trend_proxy":"DBMF","tax_rate":26.0},
    {"ticker":"NTSG.DE","name":"WisdomTree Global Efficient Core UCITS (EUR)","sleeve":"Return Stacking","role":"efficient_core","shares":0,"pmc":28.87,"price":28.87,"price_asof":"","price_source":"Reference","target":0.0,"priority":2,"equity_lt":90.0,"bond_lt":60.0,"gold_lt":0.0,"trend_lt":0.0,"equity_proxy":"VT","bond_proxy":"BND","gold_proxy":"","trend_proxy":"","tax_rate":20.6},
]

REQUIRED_COLS = [
    "ticker","name","sleeve","role","shares","pmc","price","price_asof","price_source",
    "target","priority","equity_lt","bond_lt","gold_lt","trend_lt",
    "equity_proxy","bond_proxy","gold_proxy","trend_proxy","tax_rate",
]
NUMERIC_COLS = ["shares","pmc","price","target","priority","equity_lt","bond_lt","gold_lt","trend_lt","tax_rate"]


def _deepcopy_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    base = json.loads(json.dumps(DEFAULT_SETTINGS))
    if settings:
        for k, v in settings.items():
            base[k] = v
    return base


def infer_role_from_exposures(row: pd.Series) -> str:
    sleeve = str(row.get("sleeve", ""))
    eq = float(row.get("equity_lt", 0) or 0)
    bnd = float(row.get("bond_lt", 0) or 0)
    gld = float(row.get("gold_lt", 0) or 0)
    trd = float(row.get("trend_lt", 0) or 0)
    if sleeve == "Legacy Core" and eq > 0 and bnd == 0 and gld == 0 and trd == 0:
        return "legacy_equity"
    if gld > 0 and eq == 0 and bnd == 0 and trd == 0:
        return "gold"
    if trd > 0 and eq == 0 and bnd == 0 and gld == 0:
        return "trend"
    if eq > 0 and bnd > 0 and sleeve == "Return Stacking":
        return "efficient_core"
    return "custom"


def migrate_portfolio(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Migrate legacy schema without mutating economic values silently."""
    if not isinstance(raw, pd.DataFrame):
        raise ValueError("Configurazione portafoglio non tabellare.")
    df = raw.copy()
    notes: list[str] = []
    if "role" not in df:
        df["role"] = df.apply(infer_role_from_exposures, axis=1)
        notes.append("Ruoli ricavati dalle esposizioni look-through del vecchio schema.")
    if "price_asof" not in df:
        df["price_asof"] = ""
    if "price_source" not in df:
        df["price_source"] = "Imported legacy"
    old_proxy = df["proxy"].astype(str).str.upper() if "proxy" in df else pd.Series("", index=df.index)
    for factor in FACTOR_NAMES:
        pcol = f"{factor}_proxy"
        lcol = f"{factor}_lt"
        if pcol not in df:
            df[pcol] = np.where(pd.to_numeric(df.get(lcol, 0), errors="coerce").fillna(0) > 0, old_proxy, "")
    # Explicit migration for multi-factor efficient-core rows: the old one-proxy schema cannot represent them.
    ec = df["role"].astype(str).eq("efficient_core")
    if ec.any():
        df.loc[ec & pd.to_numeric(df["equity_lt"], errors="coerce").gt(0), "equity_proxy"] = "VT"
        df.loc[ec & pd.to_numeric(df["bond_lt"], errors="coerce").gt(0), "bond_proxy"] = "BND"
        notes.append("Efficient Core migrato a VT (equity) + BND (bond proxy approssimativo).")
    if "proxy" in df:
        df = df.drop(columns=["proxy"])
    return df, notes


def validate_portfolio(raw: pd.DataFrame, ntsg_is_plug: bool | None = None) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise ValueError("Il portafoglio non può essere vuoto.")
    migrated, _ = migrate_portfolio(raw)
    missing = [c for c in REQUIRED_COLS if c not in migrated.columns]
    if missing:
        raise ValueError(f"Colonne mancanti: {', '.join(missing)}")
    df = migrated[REQUIRED_COLS].copy()
    for c in ["ticker","name","sleeve","role","price_asof","price_source","equity_proxy","bond_proxy","gold_proxy","trend_proxy"]:
        df[c] = df[c].astype("string").fillna("").str.strip()
    df["ticker"] = df["ticker"].str.upper()
    for c in ["equity_proxy","bond_proxy","gold_proxy","trend_proxy"]:
        df[c] = df[c].str.upper()
    for c in NUMERIC_COLS:
        df[c] = pd.to_numeric(df[c], errors="raise")
    if not np.isfinite(df[NUMERIC_COLS].to_numpy(dtype=float)).all():
        raise ValueError("NaN o ±Inf non sono ammessi nei campi numerici.")
    if df["ticker"].eq("").any() or df["name"].eq("").any():
        raise ValueError("Ticker e nome non possono essere vuoti.")
    dup = df.loc[df["ticker"].duplicated(keep=False), "ticker"].unique().tolist()
    if dup:
        raise ValueError(f"Ticker duplicati: {', '.join(dup)}")
    if not df["sleeve"].isin(SLEEVE_OPTIONS).all():
        raise ValueError("Sleeve non valido.")
    if not df["role"].isin(ROLE_OPTIONS).all():
        raise ValueError("Ruolo funzionale non valido.")
    # Functional roles are explicit model contracts, not labels inferred from tickers.
    if (df["role"].eq("legacy_equity") & ~df["sleeve"].eq("Legacy Core")).any():
        raise ValueError("legacy_equity deve appartenere a Legacy Core.")
    if (df["role"].isin(["gold","trend","efficient_core"]) & ~df["sleeve"].eq("Return Stacking")).any():
        raise ValueError("gold/trend/efficient_core devono appartenere a Return Stacking.")
    if (df["role"].eq("gold") & ~df["gold_lt"].gt(0)).any():
        raise ValueError("Il ruolo gold richiede gold_lt > 0.")
    if (df["role"].eq("trend") & ~df["trend_lt"].gt(0)).any():
        raise ValueError("Il ruolo trend richiede trend_lt > 0.")
    if (df["role"].eq("efficient_core") & ~(df["equity_lt"].gt(0) & df["bond_lt"].gt(0))).any():
        raise ValueError("efficient_core richiede esposizione sia equity sia bond.")
    if (df["shares"] < 0).any() or not np.allclose(df["shares"], np.floor(df["shares"])):
        raise ValueError("Le quote devono essere interi >= 0.")
    if (df["pmc"] <= 0).any() or (df["price"] <= 0).any():
        raise ValueError("PMC e prezzo devono essere > 0.")
    if ((df["target"] < 0) | (df["target"] > 100)).any():
        raise ValueError("Target fuori intervallo 0–100%.")
    if df.loc[df["sleeve"].eq("Legacy Core"), "target"].gt(1e-12).any():
        raise ValueError("I target sono ammessi solo nel Return Stacking.")
    if float(df.loc[df["sleeve"].eq("Return Stacking"), "target"].sum()) > 100.0 + 1e-9:
        raise ValueError("I target Return Stacking superano il 100%.")
    if ((df["priority"] < 1) | (df["priority"] > 5)).any() or not np.allclose(df["priority"], np.floor(df["priority"])):
        raise ValueError("Priorità: intero 1–5.")
    if ((df["tax_rate"] < 0) | (df["tax_rate"] > 100)).any():
        raise ValueError("Aliquota fiscale fuori intervallo 0–100%.")
    for factor in FACTOR_NAMES:
        lcol, pcol = f"{factor}_lt", f"{factor}_proxy"
        if (df[lcol] < 0).any():
            raise ValueError("Look-through negativi non ammessi.")
        bad = df[lcol].gt(0) & df[pcol].eq("")
        if bad.any():
            raise ValueError(f"Proxy {factor} mancante per: {', '.join(df.loc[bad,'ticker'])}")
    if ntsg_is_plug:
        plug = df["role"].eq("efficient_core") & df["sleeve"].eq("Return Stacking")
        if int(plug.sum()) != 1:
            raise ValueError("Con plug attivo serve esattamente un efficient_core nel Return Stacking.")
        if df.loc[plug, "target"].gt(1e-12).any():
            raise ValueError("Efficient Core non può avere un target esplicito mentre è attivo come plug.")
    df["shares"] = df["shares"].astype("int64")
    df["priority"] = df["priority"].astype("int64")
    for c in [x for x in NUMERIC_COLS if x not in {"shares","priority"}]:
        df[c] = df[c].astype(float)
    return df.reset_index(drop=True)


def apply_role_target(df: pd.DataFrame, role: str, total_target: float, priority: int = 1) -> pd.DataFrame:
    out = df.copy()
    mask = out["role"].eq(role) & out["sleeve"].eq("Return Stacking")
    n = int(mask.sum())
    if n == 0:
        raise ValueError(f"Nessuno strumento con ruolo {role}.")
    previous = out.loc[mask, "target"].astype(float)
    if previous.sum() > 0:
        weights = previous / previous.sum()
    else:
        weights = pd.Series(1.0 / n, index=previous.index)
    out.loc[mask, "target"] = weights * float(total_target)
    out.loc[mask, "priority"] = int(priority)
    return out


def allocate_cash(df_current: pd.DataFrame, cash_injection: float, target_mode: str, ntsg_is_plug: bool):
    df = validate_portfolio(df_current, ntsg_is_plug=ntsg_is_plug)
    cash = float(cash_injection)
    if not np.isfinite(cash) or cash < 0:
        raise ValueError("La nuova liquidità deve essere >= 0.")
    df["current_value"] = df["shares"] * df["price"]
    nav_pre = float(df["current_value"].sum())
    nav_theoretical = nav_pre + cash
    if nav_theoretical <= 0:
        raise ValueError("NAV post-iniezione non valido.")
    stacking = df[df["sleeve"].eq("Return Stacking")].copy()
    if target_mode == "NAV Totale":
        stacking["budget_eur"] = (nav_theoretical * stacking["target"] / 100.0 - stacking["current_value"]).clip(lower=0.0)
    elif target_mode == "Nuova Cassa":
        stacking["budget_eur"] = cash * stacking["target"] / 100.0
    else:
        raise ValueError("Modalità target non riconosciuta.")
    qty = pd.Series(0, index=df["ticker"].tolist(), dtype="int64")
    available = cash
    explicit_spent = 0.0
    required_total = float(stacking.loc[stacking["target"].gt(0), "budget_eur"].sum())
    for _, grp in stacking[stacking["target"].gt(0)].groupby("priority", sort=True):
        required = float(grp["budget_eur"].sum())
        if available <= 1e-12 or required <= 1e-12:
            continue
        group_budget = min(available, required)
        ideal = (grp["budget_eur"] * (group_budget / required)).to_numpy(dtype=float)
        prices = grp["price"].to_numpy(dtype=float)
        q = np.floor(ideal / prices).astype("int64")
        spend = q * prices
        group_left = float(group_budget - spend.sum())
        while group_left + 1e-12 >= float(prices.min()):
            improvement = np.abs(ideal - spend) - np.abs(ideal - (spend + prices))
            improvement = np.where(prices <= group_left + 1e-12, improvement, -np.inf)
            best = int(np.argmax(improvement))
            if not np.isfinite(improvement[best]) or improvement[best] <= 1e-12:
                break
            q[best] += 1
            spend[best] += prices[best]
            group_left -= prices[best]
        for ticker, units in zip(grp["ticker"], q):
            qty.loc[ticker] += int(units)
        group_spend = float(spend.sum())
        explicit_spent += group_spend
        available -= group_spend
    plug_spent = 0.0
    if ntsg_is_plug and available > 1e-12:
        plug = stacking[stacking["role"].eq("efficient_core")]
        r = plug.iloc[0]
        q = int(math.floor(available / float(r["price"])))
        qty.loc[r["ticker"]] += q
        plug_spent = q * float(r["price"])
        available -= plug_spent
    out = df.copy()
    out["shares_delta"] = out["ticker"].map(qty).fillna(0).astype("int64")
    out["new_shares"] = out["shares"] + out["shares_delta"]
    out["post_value"] = out["new_shares"] * out["price"]
    final_nav = float(out["post_value"].sum() + available)
    if not np.isclose(final_nav, nav_theoretical, atol=1e-6, rtol=0):
        raise RuntimeError("Invariante NAV violata.")
    out["post_weight"] = out["post_value"] / final_nav * 100.0
    orders = out.assign(action=np.where(out["shares_delta"].gt(0), "BUY", "HOLD"), total_eur=out["shares_delta"]*out["price"])[
        ["ticker","name","role","action","shares_delta","price","price_asof","price_source","total_eur"]
    ]
    target_budget = min(cash, required_total)
    rounding_after_targets = max(0.0, target_budget - explicit_spent)
    deliberate_unallocated = 0.0 if ntsg_is_plug else max(0.0, cash - target_budget)
    diagnostics = {
        "required_target_eur": required_total,
        "target_budget_eur": target_budget,
        "explicit_spent_eur": explicit_spent,
        "plug_spent_eur": plug_spent,
        "rounding_after_targets_eur": rounding_after_targets,
        "deliberate_unallocated_eur": deliberate_unallocated,
        "final_cash_eur": float(max(available, 0.0)),
    }
    return orders, out, float(max(available, 0.0)), final_nav, diagnostics


def build_exposure_model(df_post: pd.DataFrame, nav: float):
    rows = []
    macro = {f: 0.0 for f in FACTOR_NAMES}
    for _, r in df_post.iterrows():
        value = float(r["post_value"])
        for factor in FACTOR_NAMES:
            lt = float(r[f"{factor}_lt"])
            if lt <= 0:
                continue
            proxy = str(r[f"{factor}_proxy"]).strip().upper()
            exposure = value * lt / 100.0
            macro[factor] += exposure
            rows.append({"proxy": proxy, "factor": factor, "exposure_eur": exposure})
    detail = pd.DataFrame(rows)
    if detail.empty:
        return pd.Series(dtype=float), macro, detail
    proxy_exp = detail.groupby("proxy", as_index=True)["exposure_eur"].sum().sort_index()
    if nav <= 0:
        raise ValueError("NAV non valido.")
    return proxy_exp, macro, detail


def euler_risk_from_nav(exposure_eur, nav_eur: float, cov_annual, eps: float = 1e-12):
    e = np.asarray(exposure_eur, dtype=float)
    cov = np.asarray(cov_annual, dtype=float)
    nav = float(nav_eur)
    if nav <= 0 or cov.shape != (e.size, e.size):
        raise ValueError("Dimensioni/NAV non validi nel risk engine.")
    if not np.isfinite(e).all() or not np.isfinite(cov).all():
        raise ValueError("NaN/Inf nel risk engine.")
    cov = (cov + cov.T) / 2.0
    if float(np.linalg.eigvalsh(cov).min()) < -1e-10:
        raise ValueError("Matrice di covarianza non PSD.")
    x = e / nav
    variance = float(x @ cov @ x)
    if variance < -eps:
        raise ValueError("Varianza negativa oltre tolleranza.")
    sigma = math.sqrt(max(variance, 0.0))
    gross = float(np.abs(x).sum())
    if sigma <= eps:
        return sigma, gross, np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)
    mcr = cov @ x / sigma
    rc = x * mcr
    if not np.isclose(float(rc.sum()), sigma, rtol=1e-8, atol=1e-10):
        raise RuntimeError("Decomposizione Euler non chiude.")
    return sigma, gross, mcr, rc, rc / sigma * 100.0


def aggregate_rc_by_factor(proxy_rc: pd.Series, detail: pd.DataFrame) -> dict[str, float]:
    result = {f: 0.0 for f in FACTOR_NAMES}
    if detail.empty:
        return result
    for proxy, grp in detail.groupby("proxy"):
        rc = float(proxy_rc.get(proxy, 0.0))
        tot = float(grp["exposure_eur"].sum())
        if tot <= 0:
            continue
        by_factor = grp.groupby("factor")["exposure_eur"].sum()
        for factor, exp in by_factor.items():
            result[str(factor)] += rc * float(exp) / tot
    return result


def expected_portfolio_return(macro_exposure_eur: dict[str,float], nav: float, cash_eur: float, expected_pct: dict[str,float]) -> float:
    if nav <= 0:
        return np.nan
    total = 0.0
    for factor in FACTOR_NAMES:
        total += macro_exposure_eur.get(factor, 0.0) / nav * float(expected_pct[factor]) / 100.0
    total += cash_eur / nav * float(expected_pct["cash"]) / 100.0
    return total


def historical_tail_metrics(portfolio_daily_returns: pd.Series, horizon_days: int = 252) -> tuple[float, float]:
    s = pd.to_numeric(portfolio_daily_returns, errors="coerce").dropna()
    if len(s) < horizon_days + 30:
        return np.nan, np.nan
    annual = (1.0 + s).rolling(horizon_days).apply(np.prod, raw=True) - 1.0
    annual = annual.dropna()
    q05 = float(annual.quantile(0.05))
    tail = annual[annual <= q05]
    var95 = max(0.0, -q05)
    es95 = max(0.0, -float(tail.mean())) if not tail.empty else np.nan
    return var95, es95


def stress_portfolio(macro_exposure_eur: dict[str,float], nav: float, shock_row: pd.Series) -> float:
    if nav <= 0:
        return np.nan
    mapping = {"equity":"Equity %","bond":"Bond %","gold":"Gold %","trend":"Trend %"}
    return sum(macro_exposure_eur[f] / nav * float(shock_row[mapping[f]]) / 100.0 for f in FACTOR_NAMES)


def quote_is_fresh(asof: str, source: str, today: dt.date | None = None, max_age_days: int = QUOTE_MAX_AGE_DAYS) -> bool:
    if str(source) != "Yahoo" or not asof:
        return False
    try:
        qd = dt.date.fromisoformat(str(asof))
    except Exception:
        return False
    today = today or dt.date.today()
    age = (today - qd).days
    return 0 <= age <= max_age_days


def broker_data_status(df: pd.DataFrame, active_orders: pd.DataFrame, today: dt.date | None = None) -> tuple[bool, list[str]]:
    needed = set(df.loc[df["shares"].gt(0), "ticker"].astype(str))
    needed.update(active_orders.loc[active_orders["action"].eq("BUY"), "ticker"].astype(str))
    problems = []
    for ticker in sorted(needed):
        row = df.loc[df["ticker"].eq(ticker)].iloc[0]
        if not quote_is_fresh(str(row["price_asof"]), str(row["price_source"]), today=today):
            problems.append(f"{ticker}: quotazione non verificata/fresca ({row['price_source']} {row['price_asof'] or 'N/D'})")
    return not problems, problems


def role_target_report(df_post: pd.DataFrame, role: str, final_nav: float) -> dict[str, Any]:
    mask = df_post["role"].eq(role)
    current = float(df_post.loc[mask, "post_value"].sum())
    weight = current / final_nav * 100.0 if final_nav > 0 else np.nan
    target = float(df_post.loc[mask, "target"].sum())
    diff_pp = weight - target
    diff_eur = current - final_nav * target / 100.0
    prices = df_post.loc[mask, "price"].astype(float)
    one_quote_pp = float(prices.min() / final_nav * 100.0) if not prices.empty and final_nav > 0 else np.nan
    if target <= 0:
        status = "nessun target"
    elif diff_pp > max(one_quote_pp if np.isfinite(one_quote_pp) else 0, 1e-9):
        status = "sovrappeso — buy-only: nessuna vendita"
    elif abs(diff_pp) <= (one_quote_pp if np.isfinite(one_quote_pp) else 0) + 1e-9:
        status = "entro l'impatto di una quota"
    else:
        status = "sotto target"
    return {"weight":weight,"target":target,"diff_pp":diff_pp,"diff_eur":diff_eur,"one_quote_pp":one_quote_pp,"status":status}


def annual_simulation(df_post: pd.DataFrame, starting_cash: float, annual_contribution: float, years: int, target_mode: str, plug: bool, expected_pct: dict[str,float]) -> pd.DataFrame:
    # Role buckets keep the trajectory understandable while using each role's actual look-through.
    work = df_post.copy()
    role_values = work.groupby("role")["post_value"].sum().to_dict()
    cash = float(starting_cash)
    role_lt = {}
    for role, grp in work.groupby("role"):
        value = float(grp["post_value"].sum())
        if value > 0:
            role_lt[role] = {f: float((grp["post_value"] * grp[f"{f}_lt"] / 100.0).sum() / value) for f in FACTOR_NAMES}
        else:
            # use configured LT even before the first purchase
            role_lt[role] = {f: float(grp[f"{f}_lt"].mean() / 100.0) for f in FACTOR_NAMES}
    target_by_role = work.groupby("role")["target"].sum().to_dict()
    rows=[]
    for year in range(years + 1):
        nav = sum(role_values.values()) + cash
        legacy = role_values.get("legacy_equity",0.0)
        stacking = nav - legacy - cash
        macro = {f:0.0 for f in FACTOR_NAMES}
        for role, val in role_values.items():
            for f in FACTOR_NAMES:
                macro[f] += val * role_lt.get(role,{}).get(f,0.0)
        rows.append({"Anno":year,"NAV":nav,"Legacy":legacy,"Return Stacking":stacking,"Cash":cash,
                     "Legacy %":legacy/nav*100 if nav else 0,"Stacking %":stacking/nav*100 if nav else 0,
                     "Equity LT %":macro["equity"]/nav*100 if nav else 0,"Bond LT %":macro["bond"]/nav*100 if nav else 0,
                     "Gold LT %":macro["gold"]/nav*100 if nav else 0,"Trend LT %":macro["trend"]/nav*100 if nav else 0,
                     "Leva Lorda":sum(abs(v) for v in macro.values())/nav if nav else 0})
        if year == years:
            break
        # Grow each role using the same factor assumptions used by the expected-return engine.
        for role in list(role_values):
            r = sum(role_lt.get(role,{}).get(f,0.0) * float(expected_pct[f])/100.0 for f in FACTOR_NAMES)
            role_values[role] *= (1.0 + r)
        cash *= (1.0 + float(expected_pct["cash"])/100.0)
        contribution = float(annual_contribution)
        cash += contribution
        nav_after = sum(role_values.values()) + cash
        for role in ["gold","trend"]:
            t = float(target_by_role.get(role,0.0))
            if t <= 0:
                continue
            desired = nav_after*t/100.0 if target_mode == "NAV Totale" else contribution*t/100.0 + role_values.get(role,0.0)
            deficit = max(0.0, desired-role_values.get(role,0.0))
            buy = min(cash, deficit)
            role_values[role] = role_values.get(role,0.0)+buy
            cash -= buy
        if plug and cash > 0 and "efficient_core" in role_lt:
            role_values["efficient_core"] = role_values.get("efficient_core",0.0)+cash
            cash = 0.0
    return pd.DataFrame(rows)


def parse_config_bytes(raw: bytes) -> tuple[pd.DataFrame, dict[str,Any], list[str]]:
    obj = json.loads(raw.decode("utf-8"))
    notes=[]
    if isinstance(obj, list):
        portfolio = pd.DataFrame(obj)
        settings = _deepcopy_settings()
        notes.append("Importato JSON legacy privo di settings/versione.")
    elif isinstance(obj, dict):
        if "portfolio" not in obj:
            raise ValueError("JSON privo di 'portfolio'.")
        portfolio = pd.DataFrame(obj["portfolio"])
        settings = _deepcopy_settings(obj.get("settings",{}))
        if int(obj.get("schema_version",1)) < CONFIG_SCHEMA_VERSION:
            notes.append(f"Schema migrato a v{CONFIG_SCHEMA_VERSION}.")
    else:
        raise ValueError("Formato JSON non riconosciuto.")
    portfolio, migration_notes = migrate_portfolio(portfolio)
    notes.extend(migration_notes)
    portfolio = validate_portfolio(portfolio, ntsg_is_plug=bool(settings.get("ntsg_is_plug",True)))
    return portfolio, settings, notes


def export_config(df: pd.DataFrame, settings: dict[str,Any]) -> str:
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "exported_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "portfolio": df.to_dict(orient="records"),
        "settings": settings,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


@lru_cache(maxsize=8)
def fetch_fx_rate(symbol: str) -> tuple[float,str]:
    import yfinance as yf
    symbol = str(symbol).strip().upper()
    with YF_LOCK:
        data = yf.download(symbol, period="10d", auto_adjust=False, progress=False, threads=False, repair=False, timeout=10)
    close = data["Close"] if "Close" in data else data
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:,0]
    s = pd.to_numeric(close, errors="coerce").dropna()
    if s.empty or float(s.iloc[-1]) <= 0:
        raise RuntimeError(f"Cambio {symbol} non disponibile.")
    return float(s.iloc[-1]), pd.Timestamp(s.index[-1]).date().isoformat()


@lru_cache(maxsize=256)
def fetch_live_quote(ticker_symbol: str) -> dict[str,Any]:
    import yfinance as yf
    symbol = str(ticker_symbol).strip().upper()
    if not symbol:
        raise ValueError("Ticker vuoto.")
    with YF_LOCK:
        t = yf.Ticker(symbol)
        hist = t.history(period="10d", auto_adjust=False, repair=False, timeout=10)
        if hist.empty or "Close" not in hist:
            raise RuntimeError(f"{symbol}: storico prezzi assente.")
        close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        raw_price = float(close.iloc[-1])
        try:
            fast = t.fast_info
            raw_currency = str(fast.get("currency") or "").strip() if fast is not None else ""
        except Exception:
            raw_currency = ""
        if not raw_currency:
            try:
                raw_currency = str((t.info or {}).get("currency") or "").strip()
            except Exception:
                raw_currency = ""
    if not raw_currency:
        raise RuntimeError(f"{symbol}: valuta non determinabile.")
    ccy = raw_currency.upper()
    if raw_currency == "GBp" or ccy == "GBX":
        fx,_ = fetch_fx_rate("EURGBP=X"); price_eur=(raw_price/100.0)/fx
    elif ccy == "GBP":
        fx,_ = fetch_fx_rate("EURGBP=X"); price_eur=raw_price/fx
    elif ccy == "USD":
        fx,_ = fetch_fx_rate("EURUSD=X"); price_eur=raw_price/fx
    elif ccy == "EUR":
        price_eur=raw_price
    else:
        raise RuntimeError(f"{symbol}: valuta {raw_currency} non supportata.")
    return {"ticker":symbol,"price_eur":float(price_eur),"currency":raw_currency,"asof":pd.Timestamp(close.index[-1]).date().isoformat()}


@lru_cache(maxsize=128)
def lookup_asset(symbol: str) -> dict[str,Any]:
    import yfinance as yf
    quote = fetch_live_quote(symbol)
    with YF_LOCK:
        t = yf.Ticker(quote["ticker"])
        try:
            info = t.info or {}
        except Exception:
            info = {}
    name = str(info.get("shortName") or info.get("longName") or quote["ticker"])
    return {**quote, "name":name}


@lru_cache(maxsize=16)
def get_historical_proxy_returns(proxy_tuple: tuple[str,...], years: int) -> tuple[pd.DataFrame, dict[str,Any]]:
    import yfinance as yf
    proxies = [p for p in proxy_tuple if p]
    if not proxies:
        raise ValueError("Nessun proxy richiesto.")
    need_fx = any(PROXY_CONVERSION_MODE.get(p,"usd_eur") == "usd_eur" for p in proxies)
    symbols = list(dict.fromkeys(proxies + (["EURUSD=X"] if need_fx else [])))
    end = dt.date.today() + dt.timedelta(days=1)
    start = end - dt.timedelta(days=int(years*365.25)+45)
    with YF_LOCK:
        data = yf.download(symbols, start=start, end=end, progress=False, auto_adjust=True, threads=False, repair=False, timeout=20)
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data
    if isinstance(close, pd.Series):
        close = close.to_frame(symbols[0])
    close = close.reindex(columns=symbols).apply(pd.to_numeric, errors="coerce").replace([np.inf,-np.inf],np.nan)
    usd_eur = (1.0/close["EURUSD=X"]).pct_change(fill_method=None) if need_fx else None
    returns = pd.DataFrame(index=close.index)
    for p in proxies:
        r = close[p].pct_change(fill_method=None)
        if PROXY_CONVERSION_MODE.get(p,"usd_eur") == "rate_only":
            returns[p] = r
        else:
            returns[p] = (1.0+r)*(1.0+usd_eur)-1.0
    returns = returns.dropna()
    if len(returns) < 252:
        raise RuntimeError(f"Storico comune insufficiente: {len(returns)} sedute.")
    meta = {"start":pd.Timestamp(returns.index[0]).date().isoformat(),"end":pd.Timestamp(returns.index[-1]).date().isoformat(),"n":len(returns),"requested_years":years}
    return returns, meta


def clear_market_caches():
    fetch_fx_rate.cache_clear(); fetch_live_quote.cache_clear(); lookup_asset.cache_clear(); get_historical_proxy_returns.cache_clear()


def main():
    import streamlit as st
    import plotly.express as px
    import plotly.graph_objects as go

    st.set_page_config(page_title="Return Stacking Engine", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
    if "portfolio_data" not in st.session_state:
        st.session_state.portfolio_data = validate_portfolio(pd.DataFrame(DEFAULT_PORTFOLIO), ntsg_is_plug=True)
    if "settings" not in st.session_state:
        st.session_state.settings = _deepcopy_settings()
    settings = st.session_state.settings

    with st.sidebar:
        st.markdown("### ⚙️ Configurazione")
        theme = st.radio("Tema", ["Diurno","Notturno"], horizontal=True)
    dark = theme == "Notturno"
    bg = "#0b0f17" if dark else "#f8fafc"; card = "#131b26" if dark else "#ffffff"; border = "#1e293b" if dark else "#e2e8f0"; text = "#f8fafc" if dark else "#0f172a"; muted = "#94a3b8" if dark else "#64748b"; accent = "#38bdf8" if dark else "#2563eb"; template = "plotly_dark" if dark else "plotly_white"
    st.markdown(f"""<style>html,body,[class*=css]{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:{text}}}.stApp{{background:{bg}}}.metric-card{{background:{card};border:1px solid {border};border-radius:12px;padding:14px 16px;margin-bottom:10px}}.metric-title{{font-size:.75rem;color:{muted};text-transform:uppercase;font-weight:700}}.metric-value{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:1.45rem;font-weight:700}}.metric-sub{{font-size:.78rem;color:{muted}}}</style>""", unsafe_allow_html=True)

    def card_metric(title, value, sub=""):
        st.markdown(f'<div class="metric-card"><div class="metric-title">{title}</div><div class="metric-value">{value}</div><div class="metric-sub">{sub}</div></div>', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("---")
        st.markdown("### ➕ Aggiungi strumento")
        search = st.text_input("Ticker da cercare", value="")
        if st.button("Cerca quotazione", width="stretch") and search.strip():
            clear_market_caches()
            found=None; errs=[]
            for sfx in ["", ".DE", ".MI", ".AS", ".PA", ".L"]:
                sym = search.strip().upper() if not sfx else search.strip().upper()+sfx
                try:
                    found=lookup_asset(sym); break
                except Exception as exc: errs.append(str(exc))
            if found:
                st.session_state.pending_asset=found
            else:
                st.error(errs[-1] if errs else "Ticker non trovato")
        pending=st.session_state.get("pending_asset")
        if pending:
            st.success(f"{pending['ticker']} — {pending['name']} — €{pending['price_eur']:.2f} ({pending['asof']})")
            with st.form("confirm_asset"):
                role=st.selectbox("Ruolo",ROLE_OPTIONS,index=4)
                sleeve=st.selectbox("Sleeve",SLEEVE_OPTIONS,index=1)
                tax=st.number_input("Aliquota fiscale metadata (%)",0.0,100.0,26.0,0.1)
                shares=st.number_input("Quote",min_value=0,value=0,step=1)
                pmc=st.number_input("PMC (€)",min_value=0.01,value=float(pending['price_eur']))
                custom=role=="custom"
                if custom:
                    eq=st.number_input("Equity LT %",0.0,300.0,0.0); bnd=st.number_input("Bond LT %",0.0,300.0,0.0); gld=st.number_input("Gold LT %",0.0,300.0,0.0); trd=st.number_input("Trend LT %",0.0,300.0,0.0)
                    ep=st.selectbox("Equity proxy",PROXY_OPTIONS,index=0); bp=st.selectbox("Bond proxy",PROXY_OPTIONS,index=0); gp=st.selectbox("Gold proxy",PROXY_OPTIONS,index=0); tp=st.selectbox("Trend proxy",PROXY_OPTIONS,index=0)
                if st.form_submit_button("Conferma inserimento"):
                    presets={"legacy_equity":(100,0,0,0,"VT","","",""),"gold":(0,0,100,0,"","","GLD",""),"trend":(0,0,0,100,"","","","DBMF"),"efficient_core":(90,60,0,0,"VT","BND","","")}
                    if not custom: eq,bnd,gld,trd,ep,bp,gp,tp=presets[role]
                    row={"ticker":pending['ticker'],"name":pending['name'],"sleeve":sleeve,"role":role,"shares":shares,"pmc":pmc,"price":pending['price_eur'],"price_asof":pending['asof'],"price_source":"Yahoo","target":0.0,"priority":2 if sleeve=="Return Stacking" else 5,"equity_lt":eq,"bond_lt":bnd,"gold_lt":gld,"trend_lt":trd,"equity_proxy":ep,"bond_proxy":bp,"gold_proxy":gp,"trend_proxy":tp,"tax_rate":tax}
                    try:
                        cand=pd.concat([st.session_state.portfolio_data,pd.DataFrame([row])],ignore_index=True)
                        st.session_state.portfolio_data=validate_portfolio(cand,ntsg_is_plug=bool(settings['ntsg_is_plug']))
                        st.session_state.pop("pending_asset",None); st.rerun()
                    except Exception as exc: st.error(str(exc))

        st.markdown("---")
        config_json=export_config(st.session_state.portfolio_data,settings)
        st.download_button("📥 Esporta configurazione",config_json,file_name=f"return_stacking_config_v{CONFIG_SCHEMA_VERSION}.json",mime="application/json",width="stretch")
        uploaded=st.file_uploader("Importa JSON",type=["json"])
        if uploaded is not None:
            raw=uploaded.getvalue(); digest=hashlib.sha256(raw).hexdigest()
            if st.session_state.get("cfg_digest") != digest:
                try:
                    p,s,notes=parse_config_bytes(raw)
                    st.session_state.portfolio_data=p; st.session_state.settings=s; st.session_state.cfg_digest=digest
                    st.session_state.pop("portfolio_editor",None)
                    st.session_state.import_notes=notes
                    st.rerun()
                except Exception as exc: st.error(f"Import non valido: {exc}")

    if st.session_state.get("import_notes"):
        for n in st.session_state.pop("import_notes"):
            st.info(n)
        st.success("Configurazione importata e validata.")

    # Global assumptions are the single source used by trajectory, expected return and benchmark.
    with st.expander("📐 Assunzioni di scenario", expanded=False):
        er=settings["expected_returns_pct"]
        c=st.columns(5)
        for i,(f,label) in enumerate([("equity","Azioni"),("bond","Bond"),("gold","Oro"),("trend","Trend"),("cash","Cash")]):
            er[f]=c[i].number_input(f"{label} rendimento atteso %",-20.0,30.0,float(er[f]),0.1,key=f"er_{f}")
        settings["expected_returns_pct"]=er

    df=validate_portfolio(st.session_state.portfolio_data,ntsg_is_plug=bool(settings["ntsg_is_plug"]))
    st.session_state.portfolio_data=df
    df["current_value"]=df["shares"]*df["price"]
    current_nav=float(df["current_value"].sum())
    pre_macro={f:float((df["current_value"]*df[f"{f}_lt"]/100).sum()) for f in FACTOR_NAMES}
    pre_lev=sum(abs(v) for v in pre_macro.values())/current_nav if current_nav else 0
    st.markdown(f"# RETURN STACKING **ENGINE** · v{APP_VERSION}")
    st.caption(f"NAV attuale €{current_nav:,.2f} · leva look-through {pre_lev:.2f}x · config schema v{CONFIG_SCHEMA_VERSION}")
    tab_cockpit,tab_risk,tab_traj,tab_overlay=st.tabs(["🏢 Cockpit Operativo","🔬 Rischio & Stress","⏳ Traiettoria PAC","⚡ Overlay & Benchmark"])

    with tab_cockpit:
        top=st.columns([1.2,2.5,1.2])
        with top[0]:
            if st.button("🔄 Aggiorna Quotazioni Yahoo",width="stretch"):
                clear_market_caches(); upd=st.session_state.portfolio_data.copy(); failures=[]
                for idx,ticker in upd["ticker"].items():
                    try:
                        q=fetch_live_quote(str(ticker)); upd.at[idx,"price"]=q["price_eur"]; upd.at[idx,"price_asof"]=q["asof"]; upd.at[idx,"price_source"]="Yahoo"
                    except Exception as exc: failures.append(f"{ticker}: {exc}")
                st.session_state.portfolio_data=validate_portfolio(upd,ntsg_is_plug=bool(settings["ntsg_is_plug"]))
                st.session_state.pop("portfolio_editor",None)
                if failures: st.warning("Aggiornamento parziale:\n"+"\n".join(f"• {x}" for x in failures))
                st.rerun()
        with top[1]:
            cc=st.columns([1,1,1])
            gold_now=float(df.loc[df["role"].eq("gold"),"target"].sum())
            trend_now=float(df.loc[df["role"].eq("trend"),"target"].sum())
            gold_set=cc[0].number_input("Target Oro %",0.0,100.0,gold_now,0.5)
            trend_set=cc[1].number_input("Target Trend %",0.0,100.0,trend_now,0.5)
            if cc[2].button("🎯 Applica target",width="stretch"):
                try:
                    p=apply_role_target(df,"gold",gold_set,1); p=apply_role_target(p,"trend",trend_set,1)
                    # do not touch unrelated targets; efficient_core remains 0 only when used as plug
                    if settings["ntsg_is_plug"]: p.loc[p["role"].eq("efficient_core"),"target"]=0.0
                    st.session_state.portfolio_data=validate_portfolio(p,ntsg_is_plug=bool(settings["ntsg_is_plug"])); st.session_state.pop("portfolio_editor",None); st.rerun()
                except Exception as exc: st.error(str(exc))
        with top[2]:
            total_target=float(df.loc[df["sleeve"].eq("Return Stacking"),"target"].sum()); card_metric("Target espliciti",f"{total_target:.1f}%",("Residuo → Efficient Core" if settings["ntsg_is_plug"] else "Residuo resta cash"))

        # Main editor stays operationally compact. Price manual edits invalidate Yahoo verification.
        visible=["ticker","name","sleeve","role","shares","price","target","priority"]
        base=df.copy()
        edited=st.data_editor(base,column_order=visible,hide_index=True,num_rows="fixed",width="stretch",key="portfolio_editor",column_config={
            "ticker":st.column_config.TextColumn("Ticker",disabled=True),"name":st.column_config.TextColumn("Strumento"),"sleeve":st.column_config.SelectboxColumn("Sleeve",options=SLEEVE_OPTIONS),"role":st.column_config.SelectboxColumn("Ruolo",options=ROLE_OPTIONS),"shares":st.column_config.NumberColumn("Quote",min_value=0,step=1),"price":st.column_config.NumberColumn("Prezzo EUR",min_value=0.01,format="€%.2f"),"target":st.column_config.NumberColumn("Target %",min_value=0.0,max_value=100.0,step=0.5),"priority":st.column_config.NumberColumn("Priorità",min_value=1,max_value=5,step=1)})
        if not edited[visible].equals(base[visible]):
            changed_price=~np.isclose(pd.to_numeric(edited["price"]),pd.to_numeric(base["price"]))
            edited.loc[changed_price,"price_source"]="Manuale"; edited.loc[changed_price,"price_asof"]=dt.date.today().isoformat()
            try:
                st.session_state.portfolio_data=validate_portfolio(edited,ntsg_is_plug=bool(settings["ntsg_is_plug"])); st.rerun()
            except Exception as exc: st.error(f"Modifica rifiutata: {exc}")

        with st.expander("Modello avanzato: look-through, proxy e metadata fiscali"):
            advcols=["ticker","equity_lt","equity_proxy","bond_lt","bond_proxy","gold_lt","gold_proxy","trend_lt","trend_proxy","pmc","tax_rate","price_asof","price_source"]
            adv=st.data_editor(df,column_order=advcols,hide_index=True,num_rows="fixed",width="stretch",key="advanced_editor",column_config={"ticker":st.column_config.TextColumn("Ticker",disabled=True),"price_asof":st.column_config.TextColumn("Data prezzo",disabled=True),"price_source":st.column_config.TextColumn("Fonte",disabled=True)})
            if not adv[advcols].equals(df[advcols]):
                try: st.session_state.portfolio_data=validate_portfolio(adv,ntsg_is_plug=bool(settings["ntsg_is_plug"])); st.session_state.pop("portfolio_editor",None); st.rerun()
                except Exception as exc: st.error(str(exc))
            st.caption("PMC e aliquota sono metadata: l'attuale motore buy-only non calcola plusvalenze, vendite o ottimizzazione fiscale.")

        st.markdown("#### ⚙️ Allocazione nuova cassa")
        cp=st.columns([1.4,1.5,1.2])
        cash_in=cp[0].number_input("Nuova liquidità (€)",min_value=0.0,value=200000.0,step=5000.0)
        settings["target_mode"]=cp[1].radio("Modalità target",["NAV Totale","Nuova Cassa"],index=0 if settings["target_mode"]=="NAV Totale" else 1,horizontal=True)
        plug_choice=cp[2].checkbox("Efficient Core come plug",value=bool(settings["ntsg_is_plug"]))
        if plug_choice != settings["ntsg_is_plug"]:
            settings["ntsg_is_plug"]=plug_choice
            try: st.session_state.portfolio_data=validate_portfolio(df,ntsg_is_plug=plug_choice)
            except Exception as exc: st.error(str(exc)); settings["ntsg_is_plug"]=not plug_choice
        try:
            orders,post,cash_left,final_nav,diag=allocate_cash(df,cash_in,settings["target_mode"],bool(settings["ntsg_is_plug"]))
        except Exception as exc:
            st.error(f"Allocazione bloccata: {exc}"); st.stop()
        m=st.columns(4)
        with m[0]: card_metric("NAV post",f"€{final_nav:,.0f}",f"+€{cash_in:,.0f}")
        with m[1]: card_metric("Acquisti target",f"€{diag['explicit_spent_eur']:,.0f}",f"fabbisogno €{diag['required_target_eur']:,.0f}")
        with m[2]: card_metric("Plug Efficient Core",f"€{diag['plug_spent_eur']:,.0f}","0 se plug disattivato")
        with m[3]: card_metric("Cash finale",f"€{cash_left:,.2f}",f"deliberata €{diag['deliberate_unallocated_eur']:,.0f}; quote intere ≈ €{max(0,cash_left-diag['deliberate_unallocated_eur']):,.2f}")
        repcols=st.columns(2)
        for col,role,label in [(repcols[0],"gold","Oro"),(repcols[1],"trend","Trend")]:
            r=role_target_report(post,role,final_nav)
            with col: card_metric(f"Target {label}",f"{r['weight']:.2f}% vs {r['target']:.2f}%",f"Δ {r['diff_pp']:+.3f} pp / €{r['diff_eur']:+,.0f} · {r['status']} · 1 quota ≈ {r['one_quote_pp']:.3f} pp")

        active=orders[orders["action"].eq("BUY")]
        ready,problems=broker_data_status(df,active)
        st.markdown("#### 📡 Stato dati")
        status=df[["ticker","price","price_asof","price_source"]].copy(); status["Fresca Yahoo"]=status.apply(lambda r: quote_is_fresh(str(r.price_asof),str(r.price_source)),axis=1)
        st.dataframe(status,hide_index=True,width="stretch")
        override=False
        if not ready:
            st.warning("Distinta indicativa bloccata: " + " | ".join(problems))
            override=st.checkbox("Override manuale: mostra comunque la distinta usando i prezzi presenti",value=False)
        if not active.empty and (ready or override):
            st.markdown("#### 📑 Distinta Operativa Indicativa")
            st.caption("Quantità calcolate sui prezzi mostrati; non sono quotazioni eseguibili garantite.")
            st.dataframe(active[["ticker","name","shares_delta","price","price_asof","price_source","total_eur"]],hide_index=True,width="stretch")
            lines=["=== DISTINTA INDICATIVA ==="]+[f"ACQUISTA {int(r.shares_delta)} {r.ticker} @ ~€{r.price:.2f} | €{r.total_eur:,.2f} | prezzo {r.price_source} {r.price_asof}" for _,r in active.iterrows()]
            st.code("\n".join(lines),language="text")

    with tab_risk:
        proxy_exp,macro,detail=build_exposure_model(post,final_nav)
        proxies=tuple(proxy_exp.index.tolist())
        rr=st.columns([1,3])
        settings["risk_years"]=rr[0].selectbox("Finestra richiesta",[1,3,5],index=[1,3,5].index(int(settings.get("risk_years",5))),format_func=lambda x:f"{x} anni")
        rr[1].caption("Il periodo effettivo può essere più corto se un proxy (es. DBMF) ha una storia disponibile inferiore.")
        risk_available=False; risk_error=""; hist=None; meta={}; cov=None; port_vol=np.nan; rc_pct=None; model_daily=None
        try:
            hist,meta=get_historical_proxy_returns(proxies,int(settings["risk_years"]))
            cov=hist[list(proxies)].cov()*252.0
            port_vol,gross,mcr,rc,rc_pct=euler_risk_from_nav(proxy_exp.values,final_nav,cov.values)
            proxy_rc=pd.Series(rc,index=proxies); macro_rc=aggregate_rc_by_factor(proxy_rc,detail)
            model_daily=hist[list(proxies)].mul(proxy_exp.values/final_nav,axis=1).sum(axis=1)
            risk_available=True
            st.success(f"Risk data: {meta['start']} → {meta['end']} · {meta['n']} sedute · proxy: {', '.join(proxies)}")
        except Exception as exc:
            gross=sum(abs(v) for v in macro.values())/final_nav; risk_error=str(exc); st.error(f"Risk engine indisponibile: {risk_error}")
        cards=st.columns(5)
        for i,f in enumerate(FACTOR_NAMES):
            with cards[i]: card_metric(f"{FACTOR_LABELS[f]} LT",f"{macro[f]/final_nav*100:.1f}%",f"€{macro[f]:,.0f}")
        with cards[4]: card_metric("Leva lorda",f"{gross:.2f}x",f"€{sum(abs(v) for v in macro.values()):,.0f}")

        if risk_available:
            c1,c2=st.columns(2)
            exp_df=pd.DataFrame({"Fattore":[FACTOR_LABELS[f] for f in FACTOR_NAMES],"Esposizione % NAV":[macro[f]/final_nav*100 for f in FACTOR_NAMES],"RC Euler % volatilità":[macro_rc[f]/port_vol*100 if port_vol else 0 for f in FACTOR_NAMES]})
            with c1:
                fig=go.Figure(); fig.add_trace(go.Bar(x=exp_df["Fattore"],y=exp_df["Esposizione % NAV"],name="Esposizione % NAV")); fig.add_trace(go.Bar(x=exp_df["Fattore"],y=exp_df["RC Euler % volatilità"],name="Risk contribution")); fig.update_layout(template=template,barmode="group",title="Look-through vs contributo al rischio",height=330); st.plotly_chart(fig,width="stretch")
            with c2:
                ptab=pd.DataFrame({"Proxy":proxies,"Esposizione €":proxy_exp.values,"Esposizione % NAV":proxy_exp.values/final_nav*100,"RC Euler %":rc_pct})
                st.dataframe(ptab,hide_index=True,width="stretch")

        st.markdown("#### 💶 VaR / Expected Shortfall")
        vm=st.columns(4)
        if risk_available:
            z95=1.6448536269514722; pvar=z95*port_vol; hvar,hes=historical_tail_metrics(model_daily)
            with vm[0]: card_metric("Volatilità ann.",f"{port_vol*100:.1f}%","")
            with vm[1]: card_metric("Parametric VaR 95% · 1Y",f"€{final_nav*pvar:,.0f}",f"{pvar*100:.1f}% · normale, zero drift")
            with vm[2]: card_metric("Historical VaR 95% · 1Y",("N/D" if not np.isfinite(hvar) else f"€{final_nav*hvar:,.0f}"),("rolling 252 sedute" if np.isfinite(hvar) else "storico insufficiente"))
            with vm[3]: card_metric("Historical ES 95% · 1Y",("N/D" if not np.isfinite(hes) else f"€{final_nav*hes:,.0f}"),"media della coda <= 5° percentile")
        else:
            for col in vm:
                with col: card_metric("Risk metric","N/D","storico/covarianza non disponibili")

        st.markdown("#### 🧪 Matrice stress modificabile")
        stress=pd.DataFrame(settings.get("stress_matrix",DEFAULT_STRESS.to_dict(orient="records")))
        stress_edit=st.data_editor(stress,hide_index=True,width="stretch",num_rows="dynamic",key="stress_editor")
        settings["stress_matrix"]=stress_edit.to_dict(orient="records")
        rows=[]
        for _,srow in stress_edit.iterrows():
            target=stress_portfolio(macro,final_nav,srow); sixty=(0.6*float(srow["Equity %"])+0.4*float(srow["Bond %"]))/100.0; eq=float(srow["Equity %"])/100.0
            rows.append({"Scenario":srow["Scenario"],"Target Stacking":f"{target*100:+.1f}%","100% Equity":f"{eq*100:+.1f}%","Classic 60/40":f"{sixty*100:+.1f}%"})
        st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
        st.caption("Sono scenari lineari configurabili, non backtest storici del portafoglio.")

        if risk_available:
            st.markdown("#### 🔗 Correlazione proxy")
            win=st.select_slider("Sedute",options=[30,90,252,min(756,len(hist))],value=min(252,len(hist)))
            corr=hist.tail(int(win)).corr().round(2); fig=px.imshow(corr,text_auto=True,aspect="auto",range_color=[-1,1],color_continuous_scale="RdBu_r"); fig.update_layout(template=template,height=350); st.plotly_chart(fig,width="stretch")

    with tab_traj:
        st.markdown("#### ⏳ Diluizione Legacy e PAC")
        tr=st.columns(2)
        pac=tr[0].number_input("PAC annuo (€)",min_value=0.0,value=50000.0,step=5000.0)
        years=tr[1].slider("Orizzonte anni",1,30,15)
        sim=annual_simulation(post,cash_left,pac,years,settings["target_mode"],bool(settings["ntsg_is_plug"]),settings["expected_returns_pct"])
        core_half=sim.loc[sim["Legacy %"].lt(50),"Anno"]
        cross=sim.loc[sim["Return Stacking"].gt(sim["Legacy"]),"Anno"]
        cc=st.columns(3)
        with cc[0]: card_metric("Core <50% NAV",("mai" if core_half.empty else f"anno {int(core_half.iloc[0])}"),"metrica NAV")
        with cc[1]: card_metric("Stacking > Legacy",("mai" if cross.empty else f"anno {int(cross.iloc[0])}"),"vero sorpasso dei due sleeve")
        with cc[2]: card_metric("Leva finale",f"{sim.iloc[-1]['Leva Lorda']:.2f}x",f"NAV €{sim.iloc[-1]['NAV']:,.0f}")
        c1,c2=st.columns(2)
        with c1:
            fig=go.Figure(); fig.add_trace(go.Scatter(x=sim["Anno"],y=sim["Legacy %"],name="Legacy % NAV")); fig.add_trace(go.Scatter(x=sim["Anno"],y=sim["Stacking %"],name="Return Stacking % NAV")); fig.update_layout(template=template,title="Diluizione sleeve",height=340,yaxis_title="% NAV"); st.plotly_chart(fig,width="stretch")
        with c2:
            fig=go.Figure(); fig.add_trace(go.Scatter(x=sim["Anno"],y=sim["Leva Lorda"],name="Leva lorda")); fig.update_layout(template=template,title="Leva look-through",height=340,yaxis_title="x NAV"); st.plotly_chart(fig,width="stretch")
        st.dataframe(sim.round(2),hide_index=True,width="stretch")
        st.caption("La simulazione usa i look-through effettivi configurati e le stesse assunzioni fattoriali del benchmark; la cassa remunera al rendimento Cash impostato.")

    with tab_overlay:
        proxy_exp,macro,detail=build_exposure_model(post,final_nav)
        st.markdown("#### ⚡ Overlay Contribution Sensitivity")
        ec_mask=post["role"].eq("efficient_core"); ec_value=float(post.loc[ec_mask,"post_value"].sum()); bond_overlay=float((post.loc[ec_mask,"post_value"]*post.loc[ec_mask,"bond_lt"]/100).sum())
        oo=st.columns(3)
        gross_bond=oo[0].number_input("Rendimento atteso lordo fattore bond %",-10.0,20.0,float(settings["expected_returns_pct"]["bond"]),0.1)
        settings["overlay_implementation_bps"]=oo[1].number_input("Drag implementazione overlay (bps/anno)",0.0,300.0,float(settings.get("overlay_implementation_bps",20.0)),5.0)
        net_overlay=gross_bond-settings["overlay_implementation_bps"]/100.0; overlay_eur=bond_overlay*net_overlay/100.0
        with oo[2]: card_metric("Contributo overlay stimato",f"{net_overlay:+.2f}%",f"nozionale bond €{bond_overlay:,.0f} · ≈ €{overlay_eur:+,.0f}/a")
        st.caption("Sensibilità del contributo dell'overlay, non replica della meccanica futures/collateral del fondo e non stima osservabile del carry.")

        st.markdown("#### ⚖️ Benchmark coerenti con il modello")
        er=settings["expected_returns_pct"]; target_er=expected_portfolio_return(macro,final_nav,cash_left,er)
        rows=[]
        # Re-use risk data if it exists in current Streamlit run; otherwise attempt it here.
        try:
            pexp,_,det=build_exposure_model(post,final_nav); prox=tuple(pexp.index.tolist()); h,met=get_historical_proxy_returns(prox,int(settings["risk_years"])); cv=h[list(prox)].cov()*252; pv,gl,_,_,_=euler_risk_from_nav(pexp.values,final_nav,cv.values)
        except Exception:
            pv=np.nan; gl=sum(abs(v) for v in macro.values())/final_nav
        sharpe=(target_er-er["cash"]/100.0)/pv if np.isfinite(pv) and pv>0 else np.nan
        rows.append({"Strategia":"Portafoglio Target Return Stacking","Leva":f"{gl:.2f}x","Rendimento atteso":f"{target_er*100:.2f}%","Volatilità":f"{pv*100:.1f}%" if np.isfinite(pv) else "N/D","Sharpe":f"{sharpe:.2f}" if np.isfinite(sharpe) else "N/D"})
        eq_pct=macro["equity"]/final_nav
        if 0 <= eq_pct <= 1:
            twin_er=eq_pct*er["equity"]/100+(1-eq_pct)*er["cash"]/100
            try:
                vt_hist,_=get_historical_proxy_returns(("VT",),int(settings["risk_years"])); vtvol=float(vt_hist["VT"].std()*math.sqrt(252)); twin_vol=eq_pct*vtvol
            except Exception: twin_vol=np.nan
            twin_sh=(twin_er-er["cash"]/100)/twin_vol if np.isfinite(twin_vol) and twin_vol>0 else np.nan
            rows.append({"Strategia":f"Cash-Funded Twin ({eq_pct*100:.0f}% Equity)","Leva":"1.00x","Rendimento atteso":f"{twin_er*100:.2f}%","Volatilità":f"{twin_vol*100:.1f}%" if np.isfinite(twin_vol) else "N/D","Sharpe":f"{twin_sh:.2f}" if np.isfinite(twin_sh) else "N/D"})
        eq_er=er["equity"]/100
        try:
            vt_hist,_=get_historical_proxy_returns(("VT",),int(settings["risk_years"])); vtvol=float(vt_hist["VT"].std()*math.sqrt(252)); vtsh=(eq_er-er["cash"]/100)/vtvol
        except Exception: vtvol=np.nan; vtsh=np.nan
        rows.append({"Strategia":"100% World Equity (VT proxy)","Leva":"1.00x","Rendimento atteso":f"{eq_er*100:.2f}%","Volatilità":f"{vtvol*100:.1f}%" if np.isfinite(vtvol) else "N/D","Sharpe":f"{vtsh:.2f}" if np.isfinite(vtsh) else "N/D"})
        st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")

    st.markdown(f"<div style='text-align:center;color:{muted};padding:18px;border-top:1px solid {border}'>Return Stacking Engine v{APP_VERSION} · schema {CONFIG_SCHEMA_VERSION} · quantitative decision-support prototype</div>",unsafe_allow_html=True)


if __name__ == "__main__":
    main()