# Project Notes

## Goal

Build a conservative stock analysis bot for a 20,000 NOK portfolio covering Oslo
Bors and US stocks. The bot generates daily markdown reports and never trades
automatically.

## Scope

- Python command-line project
- Data source: `yfinance`
- Markets: Oslo Bors and US equities
- Portfolio limit: 20,000 NOK
- Position limit: 5 holdings
- No leverage
- No derivatives
- No automatic trading

## Signal Model

The first strategy version is intentionally simple and transparent:

- BUY: close price is above SMA20 and SMA50, SMA20 is above SMA50, and 30-day
  momentum is positive
- SELL: close price is below SMA20 and SMA50, or 30-day momentum is strongly
  negative
- HOLD: anything between those cases

Volatility is reported as annualized volatility based on daily returns. It is not
used as a hard filter in the first version, but it should be reviewed before any
manual investment decision.

## Report Output

`reports/daily_report.md` includes:

- Project constraints
- Summary of ranked signals
- Suggested manual allocation for BUY candidates
- Indicator table
- Errors or missing data notes

## Future Improvements

- Add FX conversion from USD to NOK for cleaner allocation sizing
- Add sector and currency exposure limits
- Add benchmark comparison, such as OSEBX and S&P 500
- Add unit tests around report generation and market-data edge cases
- Add scheduled local report generation without brokerage integrations
