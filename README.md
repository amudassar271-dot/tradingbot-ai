# Tradingbot AI

Initial stock analysis bot for Oslo Bors and US-listed stocks.

This project produces analysis reports only. It does not place orders, use leverage,
trade derivatives, or connect to any brokerage.

## Features

- Loads a stock watchlist from `data/watchlist.csv`
- Fetches six months of daily price history with `yfinance`
- Calculates SMA20, SMA50, 30-day momentum, and volatility
- Produces BUY, HOLD, and SELL signals
- Applies conservative portfolio constraints:
  - Portfolio size: 20,000 NOK
  - Max positions: 5
  - No leverage
  - No derivatives
  - No automatic trading
- Writes `reports/daily_report.md`

## Setup

Use Python 3.10 or newer. On this machine, make sure `python` points to Python 3
before running the commands below.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

```powershell
python main.py
```

The default watchlist is stored at `data/watchlist.csv`. Oslo Bors tickers use the
Yahoo Finance `.OL` suffix, such as `EQNR.OL`.

## Project Layout

```text
main.py
modules/
  market_data.py
  strategy.py
  risk.py
  report.py
data/
  watchlist.csv
reports/
  daily_report.md
logs/
tests/
```

## Disclaimer

This software is for research and education only. Signals are not financial advice.
Always review the underlying business, liquidity, fees, currency exposure, and tax
implications before making investment decisions.
