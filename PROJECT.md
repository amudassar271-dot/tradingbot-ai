# Project Notes

## Goal

Build a conservative stock analysis bot for a 20,000 NOK portfolio covering Oslo
Bors and US stocks. The bot generates daily markdown reports and never trades
automatically.

## Scope

- Python command-line project
- Data source: `yfinance`
- Markets: Oslo Bors and US equities
- Portfolio and risk settings loaded from `config.yaml`
- No leverage
- No derivatives
- No automatic trading
- No AI or news analysis in this version
- No broker integration in this version

## Signal Model

The first strategy version is intentionally simple and transparent. Each stock is
scored from 0-100 using trend, momentum, and volatility:

- BUY: close price is above SMA20 and SMA50, SMA20 is above SMA50, 30-day
  momentum is positive, and the score is above the configured minimum buy score
- SELL: close price is below SMA20 and SMA50, or 30-day momentum is strongly
  negative based on the configured threshold
- HOLD: anything between those cases

Volatility is annualized from daily returns and is used in both the stock score
and confidence score.

## Risk Management

For each analyzed stock, the bot calculates:

- Entry price: latest adjusted close
- Stop loss: configured percentage below entry
- Target price: configured percentage above entry
- Expected holding period: estimated from score and volatility
- Confidence score: stock score adjusted for volatility

## Portfolio Construction

The allocation engine selects BUY candidates above the configured minimum score,
sorts by score and confidence, respects the max-position limit, keeps the
configured cash reserve, and applies the configured max-position cap.

Supported position sizing modes:

- `score_weighted`
- `risk_weighted`
- `equal_weight`

## Portfolio History

Each daily report run appends a research snapshot to
`history/portfolio_history.csv` with the run date, signal, score, confidence,
allocation, stop loss, target price, and expected holding period.

## Backtesting

`python main.py --backtest` runs a historical yfinance simulation using configured
capital, max positions, max position size, buy score threshold, stop loss, take
profit, and transaction costs. Signals are calculated only from data available on
or before each simulated trading day to avoid look-ahead bias.

The backtest rebalances monthly, allows at most one new position per rebalance,
and skips trades below the configured minimum size. Stop loss and target exits
can happen at any time; SELL-signal and score exits require the configured minimum
holding period first. After selling a ticker, the simulator waits 10 trading days
before re-entry and requires the configured re-entry score. Once an open position
is up more than 10%, the stop moves to breakeven; once it is up more than 15%,
the stop trails 8% below price.

## Report Output

`reports/daily_report.md` includes:

- Project constraints
- Summary of ranked signals
- Suggested manual allocation for BUY candidates with risk/reward fields
- Indicator table
- Errors or missing data notes

## Future Improvements

- Add FX conversion from USD to NOK for cleaner allocation sizing
- Add sector and currency exposure limits
- Add benchmark comparison, such as OSEBX and S&P 500
- Add unit tests around report generation and market-data edge cases
- Add scheduled local report generation without brokerage integrations
