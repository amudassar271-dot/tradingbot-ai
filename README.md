# Tradingbot AI

Initial stock analysis bot for Oslo Bors and US-listed stocks.

This project produces analysis reports only. It does not place orders, use leverage,
trade derivatives, or connect to any brokerage.

## Features

- Loads risk and portfolio settings from `config.yaml`
- Loads a stock watchlist from `data/watchlist.csv`
- Fetches six months of daily price history with `yfinance`
- Calculates SMA20, SMA50, 30-day momentum, and volatility
- Produces BUY, HOLD, and SELL signals
- Scores each stock from 0-100
- Calculates entry price, stop loss, target price, expected holding period, and confidence score
- Builds a portfolio allocation plan using configured position sizing
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

Run the normal daily analysis report:

```powershell
python main.py
```

Run the historical backtest simulation:

```powershell
python main.py --backtest
```

The backtest compares `robust_current`, `ultra_selective`, and `max_3_trades`
for a small high-commission portfolio.

The default watchlist is stored at `data/watchlist.csv`. Oslo Bors tickers use the
Yahoo Finance `.OL` suffix, such as `EQNR.OL`.

## Configuration

Edit `config.yaml` to change portfolio and risk settings:

```yaml
portfolio:
  capital_nok: 20000
  max_positions: 2
  position_sizing: score_weighted
  max_position_pct: 0.50
  cash_reserve_pct: 0.05

risk:
  stop_loss_pct: 0.08
  take_profit_pct: 0.16
  min_score_for_buy: 75
  minimum_buy_score: 75

transaction_cost:
  fixed_nok: 29

trading:
  min_trade_size_nok: 7500
  max_new_positions_per_rebalance: 1
  rebalance_frequency: monthly
  min_holding_days: 30
  min_score_for_buy: 82
  min_score_for_reentry: 88

backtest:
  history_period: 2y
  rebalance_frequency: monthly
  output_path: reports/backtest_report.md

news:
  enabled: true
  max_headlines_per_ticker: 3
  sentiment_enabled: true

report:
  schedule: daily
```

Supported `position_sizing` values are `score_weighted`, `risk_weighted`, and
`equal_weight`.

News is fetched from free yfinance ticker news when available. It only adjusts
reported confidence context and never creates BUY signals.

The AI News Analyst summarizes headlines, classifies sentiment, and lists risk
and opportunity flags in `reports/ai_analysis.md`. It does not affect signals or
portfolio allocation.

## Project Layout

```text
main.py
config.yaml
modules/
  config.py
  market_data.py
  strategy.py
  risk.py
  report.py
  backtest.py
  news.py
  ai_analyst.py
data/
  watchlist.csv
  news_cache.json
history/
  portfolio_history.csv
reports/
  daily_report.md
  backtest_report.md
  news_report.md
  ai_analysis.md
logs/
tests/
```

## Disclaimer

This software is for research and education only. Signals are not financial advice.
Backtests are historical simulations and do not predict future results. Always
review the underlying business, liquidity, fees, currency exposure, and tax
implications before making investment decisions.
