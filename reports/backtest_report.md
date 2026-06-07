# Backtest Strategy Comparison

This is a historical simulation for research only. It is not financial advice.
News and AI analysis do not affect these trading signals.

## Comparison

| Mode | Gross return before commission | Net return after commission | Total commissions paid | Number of trades | Buy trades | Sell trades | Average holding period | Maximum drawdown | Ending capital | Cash remaining |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| robust_current | -8.44% | -12.65% | 841.00 NOK | 29 | 15 | 14 | 39.9 days | -14.30% | 17,470.18 NOK | 8,909.56 NOK |
| ultra_selective | -6.11% | -7.70% | 319.00 NOK | 11 | 6 | 5 | 40.0 days | -18.87% | 18,459.86 NOK | 3,136.37 NOK |
| max_3_trades | -15.17% | -16.04% | 174.00 NOK | 6 | 3 | 3 | 25.3 days | -16.40% | 16,791.77 NOK | 16,791.77 NOK |

## Commission Correction Impact

| Mode | 75 NOK net return | 29 NOK net return | Net return change | 75 NOK commissions | 29 NOK commissions | Commission savings | Ending capital change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| robust_current | -19.11% | -12.65% | 6.46% | 2,175.00 NOK | 841.00 NOK | 1,334.00 NOK | 1,291.55 NOK |
| ultra_selective | -10.23% | -7.70% | 2.53% | 825.00 NOK | 319.00 NOK | 506.00 NOK | 505.99 NOK |
| max_3_trades | -17.42% | -16.04% | 1.38% | 450.00 NOK | 174.00 NOK | 276.00 NOK | 275.99 NOK |

## Interpretation

Best net return after commission: ultra_selective (-7.70%). Lowest drawdown: robust_current (-14.30%). All tested modes were negative after the corrected 29 NOK commission, so the current strategy still appears unsuitable for a 20,000 NOK portfolio.

## Current Simulated Holdings

### robust_current

| Ticker | Name | Market | Shares | Entry | Stop | Target | Score | Confidence | Volatility |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GOOGL | Alphabet | US | 23.2291 | 384.80 | 354.02 | 446.37 | 88 | 76 | 30.67% |

### ultra_selective

| Ticker | Name | Market | Shares | Entry | Stop | Target | Score | Confidence | Volatility |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GOOGL | Alphabet | US | 41.5800 | 384.80 | 354.02 | 446.37 | 88 | 76 | 30.67% |

### max_3_trades

No open simulated holdings.
