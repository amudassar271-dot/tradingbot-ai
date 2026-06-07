# Momentum Portfolio Strategy Report

This is a historical research simulation only. It is not financial advice.
The momentum portfolio is research-only and does not place trades.
Fixed Nordnet Mini commission: 29 NOK per trade.

| Strategy / Benchmark | Capital | Gross return | Net return after commission | Ending capital | Total commissions | Trades | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Buy and hold NVDA | 20,000 NOK | 69.80% | 69.41% | 33,881.81 NOK | 58.00 NOK | 2 | -36.88% |
| Buy and hold OBX.OL | 20,000 NOK | 47.49% | 47.13% | 29,425.79 NOK | 58.00 NOK | 2 | -12.21% |
| Buy and hold QQQ | 20,000 NOK | 53.83% | 53.46% | 30,692.44 NOK | 58.00 NOK | 2 | -22.77% |
| Buy and hold SPY | 20,000 NOK | 41.30% | 40.95% | 28,190.96 NOK | 58.00 NOK | 2 | -18.76% |
| Equal-weight buy and hold watchlist | 20,000 NOK | 64.45% | 55.63% | 31,126.21 NOK | 1,334.00 NOK | 46 | -18.39% |
| max_3_trades | 20,000 NOK | -15.17% | -16.04% | 16,791.78 NOK | 174.00 NOK | 6 | -16.40% |
| robust_current | 20,000 NOK | -8.44% | -12.65% | 17,470.18 NOK | 841.00 NOK | 29 | -14.30% |
| ultra_selective | 20,000 NOK | -6.11% | -7.70% | 18,459.87 NOK | 319.00 NOK | 11 | -18.87% |
| momentum_portfolio | 20,000 NOK | 101.55% | 91.26% | 38,251.72 NOK | 2,059.00 NOK | 71 | -29.84% |
| Buy and hold NVDA | 30,000 NOK | 69.80% | 69.54% | 50,861.83 NOK | 58.00 NOK | 2 | -36.88% |
| Buy and hold OBX.OL | 30,000 NOK | 47.49% | 47.25% | 44,174.57 NOK | 58.00 NOK | 2 | -12.21% |
| Buy and hold QQQ | 30,000 NOK | 53.83% | 53.58% | 46,075.47 NOK | 58.00 NOK | 2 | -22.77% |
| Buy and hold SPY | 30,000 NOK | 41.30% | 41.07% | 42,321.43 NOK | 58.00 NOK | 2 | -18.76% |
| Equal-weight buy and hold watchlist | 30,000 NOK | 64.45% | 58.57% | 47,571.25 NOK | 1,334.00 NOK | 46 | -18.39% |
| max_3_trades | 30,000 NOK | -15.17% | -15.75% | 25,274.66 NOK | 174.00 NOK | 6 | -16.16% |
| robust_current | 30,000 NOK | -8.49% | -11.29% | 26,612.40 NOK | 841.00 NOK | 29 | -13.79% |
| ultra_selective | 30,000 NOK | -6.11% | -7.17% | 27,849.30 NOK | 319.00 NOK | 11 | -18.64% |
| momentum_portfolio | 30,000 NOK | 102.06% | 94.43% | 58,327.88 NOK | 2,291.00 NOK | 79 | -29.67% |

## Current Simulated Holdings

| Capital | Strategy | Holdings |
| ---: | --- | --- |
| 20,000 NOK | max_3_trades | Cash only |
| 20,000 NOK | momentum_portfolio | AAPL (42.61 shares), AMD (32.59 shares), NHY.OL (85.81 shares) |
| 20,000 NOK | robust_current | GOOGL (23.23 shares) |
| 20,000 NOK | ultra_selective | GOOGL (41.58 shares) |
| 30,000 NOK | max_3_trades | Cash only |
| 30,000 NOK | momentum_portfolio | AAPL (64.93 shares), AMD (49.60 shares), NHY.OL (131.32 shares) |
| 30,000 NOK | robust_current | GOOGL (35.36 shares) |
| 30,000 NOK | ultra_selective | GOOGL (62.37 shares) |

## Interpretation

For 20,000 NOK, momentum_portfolio beat the best existing bot mode: 91.26% vs ultra_selective at -7.70%.

For 20,000 NOK, momentum_portfolio beat the equal-weight watchlist benchmark: 91.26% vs 55.63%.

For 20,000 NOK, momentum_portfolio beat SPY/QQQ: 91.26% vs Buy and hold QQQ at 53.46%.

For 20,000 NOK, momentum_portfolio beat NVDA buy and hold: 91.26% vs 69.41%.

For 20,000 NOK, momentum_portfolio was economically viable after commission in this historical window, but the drawdown is high and would need risk controls before treating it as robust: 91.26% net return, -29.84% max drawdown, and 71 trades.

For 30,000 NOK, momentum_portfolio beat the best existing bot mode: 94.43% vs ultra_selective at -7.17%.

For 30,000 NOK, momentum_portfolio beat the equal-weight watchlist benchmark: 94.43% vs 58.57%.

For 30,000 NOK, momentum_portfolio beat SPY/QQQ: 94.43% vs Buy and hold QQQ at 53.58%.

For 30,000 NOK, momentum_portfolio beat NVDA buy and hold: 94.43% vs 69.54%.

For 30,000 NOK, momentum_portfolio was economically viable after commission in this historical window, but the drawdown is high and would need risk controls before treating it as robust: 94.43% net return, -29.67% max drawdown, and 79 trades.
