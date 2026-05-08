from __future__ import annotations

import csv
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timezone
import json
from pathlib import Path
import time as time_module
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def download_yahoo_chart_prices(
    tickers: list[str],
    start: date,
    end: date,
    output_path: Path,
    *,
    pause_seconds: float = 0.25,
) -> None:
    symbols = normalize_tickers(tickers)
    if end <= start:
        raise ValueError("End date must be after start date.")

    rows: list[tuple[str, str, float]] = []
    for symbol in symbols:
        rows.extend(fetch_yahoo_chart_symbol(symbol, start, end))
        time_module.sleep(pause_seconds)

    if not rows:
        raise ValueError("No price data returned from Yahoo chart endpoint.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("date", "ticker", "price"))
        for observation_date, symbol, price in sorted(rows):
            writer.writerow((observation_date, symbol, f"{price:.6f}"))


def fetch_yahoo_chart_symbol(symbol: str, start: date, end: date) -> list[tuple[str, str, float]]:
    period1 = unix_timestamp(start)
    period2 = unix_timestamp(end)
    url = (
        YAHOO_CHART_URL.format(ticker=symbol)
        + f"?period1={period1}&period2={period2}&interval=1d&events=history&includeAdjustedClose=true"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Yahoo chart request failed for {symbol}: HTTP {exc.code}") from exc

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"Yahoo chart request failed for {symbol}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo chart returned no results for {symbol}.")

    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    adjusted = ((indicators.get("adjclose") or [{}])[0]).get("adjclose")
    closes = ((indicators.get("quote") or [{}])[0]).get("close")
    prices = adjusted or closes
    if not prices:
        raise RuntimeError(f"Yahoo chart returned no adjusted close prices for {symbol}.")

    rows: list[tuple[str, str, float]] = []
    for timestamp, price in zip(timestamps, prices):
        if price is None:
            continue
        observation_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
        rows.append((observation_date, symbol, float(price)))
    return rows


def unix_timestamp(day: date) -> int:
    return int(datetime.combine(day, time.min, tzinfo=timezone.utc).timestamp())


def normalize_tickers(tickers: list[str]) -> list[str]:
    symbols = [ticker.upper().strip() for ticker in tickers if ticker.strip()]
    if not symbols:
        raise ValueError("At least one ticker is required.")
    return sorted(set(symbols))


def download_yfinance_prices(
    tickers: list[str],
    start: date,
    end: date,
    output_path: Path,
) -> None:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is not installed. Install the research extras before downloading prices: "
            "python3 -m pip install '.[research]'"
        ) from exc

    symbols = normalize_tickers(tickers)
    if end <= start:
        raise ValueError("End date must be after start date.")

    raw = yf.download(
        symbols,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if raw.empty:
        raise ValueError("No price data returned from yfinance.")

    if len(symbols) == 1:
        prices = raw[["Close"]].rename(columns={"Close": symbols[0]})
    else:
        prices = raw["Close"]

    long_prices = (
        prices.reset_index()
        .melt(id_vars="Date", var_name="ticker", value_name="price")
        .dropna(subset=["price"])
        .sort_values(["Date", "ticker"])
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    long_prices.rename(columns={"Date": "date"}).to_csv(output_path, index=False)
