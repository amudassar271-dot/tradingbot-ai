# Benchmark Comparison Report

This is a historical research comparison only. It is not financial advice.
Fixed Nordnet Mini commission: 29 NOK per buy and 29 NOK per final sell.

| Strategy / Benchmark | Capital | Gross return | Net return after commission | Ending capital | Max drawdown | Number of trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Buy and hold AAPL | 20,000 NOK | 59.40% | 59.02% | 31,804.89 NOK | -33.36% | 2 |
| Buy and hold DNB.OL | 20,000 NOK | 58.71% | 58.33% | 31,666.59 NOK | -14.48% | 2 |
| Buy and hold EQNR.OL | 20,000 NOK | 40.10% | 39.76% | 27,951.31 NOK | -21.81% | 2 |
| Buy and hold MSFT | 20,000 NOK | -0.31% | -0.60% | 19,880.76 NOK | -33.91% | 2 |
| Buy and hold NVDA | 20,000 NOK | 69.80% | 69.41% | 33,881.81 NOK | -36.88% | 2 |
| Equal-weight buy and hold watchlist | 20,000 NOK | 64.45% | 55.63% | 31,126.21 NOK | -18.39% | 46 |
| Nasdaq proxy: QQQ (QQQ) | 20,000 NOK | 53.83% | 53.46% | 30,692.44 NOK | -22.77% | 2 |
| Oslo Bors proxy (OBX.OL) | 20,000 NOK | 47.49% | 47.13% | 29,425.79 NOK | -12.21% | 2 |
| S&P 500 proxy: SPY (SPY) | 20,000 NOK | 41.30% | 40.95% | 28,190.96 NOK | -18.76% | 2 |
| Bot: max_3_trades | 20,000 NOK | -15.17% | -16.04% | 16,791.78 NOK | -16.40% | 6 |
| Bot: robust_current | 20,000 NOK | -8.44% | -12.65% | 17,470.19 NOK | -14.30% | 29 |
| Bot: ultra_selective | 20,000 NOK | -6.11% | -7.70% | 18,459.87 NOK | -18.87% | 11 |
| Buy and hold AAPL | 30,000 NOK | 59.40% | 59.15% | 47,744.95 NOK | -33.36% | 2 |
| Buy and hold DNB.OL | 30,000 NOK | 58.71% | 58.46% | 47,537.40 NOK | -14.48% | 2 |
| Buy and hold EQNR.OL | 30,000 NOK | 40.10% | 39.87% | 41,961.77 NOK | -21.81% | 2 |
| Buy and hold MSFT | 30,000 NOK | -0.31% | -0.50% | 29,850.10 NOK | -33.91% | 2 |
| Buy and hold NVDA | 30,000 NOK | 69.80% | 69.54% | 50,861.84 NOK | -36.88% | 2 |
| Equal-weight buy and hold watchlist | 30,000 NOK | 64.45% | 58.57% | 47,571.25 NOK | -18.39% | 46 |
| Nasdaq proxy: QQQ (QQQ) | 30,000 NOK | 53.83% | 53.58% | 46,075.47 NOK | -22.77% | 2 |
| Oslo Bors proxy (OBX.OL) | 30,000 NOK | 47.49% | 47.25% | 44,174.57 NOK | -12.21% | 2 |
| S&P 500 proxy: SPY (SPY) | 30,000 NOK | 41.30% | 41.07% | 42,321.43 NOK | -18.76% | 2 |
| Bot: max_3_trades | 30,000 NOK | -15.17% | -15.75% | 25,274.67 NOK | -16.16% | 6 |
| Bot: robust_current | 30,000 NOK | -8.49% | -11.29% | 26,612.40 NOK | -13.79% | 29 |
| Bot: ultra_selective | 30,000 NOK | -6.11% | -7.17% | 27,849.30 NOK | -18.64% | 11 |

## Interpretation

The best bot mode did not beat the best single-stock buy-and-hold benchmark: Bot: ultra_selective (-7.17%) vs Buy and hold NVDA (69.54%).

The best bot mode did not beat the broad market/proxy benchmark: Bot: ultra_selective (-7.17%) vs Equal-weight buy and hold watchlist (58.57%).

The best passive benchmark was Buy and hold NVDA at 69.54% net return.

The bot did not add value versus passive investing in this historical window.
