# Capital Comparison Report

This is a historical simulation for research only. It is not financial advice.
Fixed Nordnet Mini commission: 29 NOK per trade.

| Capital | Mode | Gross return | Net return | Ending capital | Total commissions | Commissions as % of capital | Number of trades | Max drawdown | Average holding period |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20,000 NOK | max_3_trades | -15.17% | -16.04% | 16,791.78 NOK | 174.00 NOK | 0.87% | 6 | -16.40% | 25.3 days |
| 20,000 NOK | robust_current | -8.44% | -12.65% | 17,470.18 NOK | 841.00 NOK | 4.21% | 29 | -14.30% | 39.9 days |
| 20,000 NOK | ultra_selective | -6.11% | -7.70% | 18,459.87 NOK | 319.00 NOK | 1.59% | 11 | -18.87% | 40.0 days |
| 30,000 NOK | max_3_trades | -15.17% | -15.75% | 25,274.66 NOK | 174.00 NOK | 0.58% | 6 | -16.16% | 25.3 days |
| 30,000 NOK | robust_current | -8.49% | -11.29% | 26,612.40 NOK | 841.00 NOK | 2.80% | 29 | -13.79% | 39.9 days |
| 30,000 NOK | ultra_selective | -6.11% | -7.17% | 27,849.30 NOK | 319.00 NOK | 1.06% | 11 | -18.64% | 40.0 days |

## Interpretation

Best mode for 20,000 NOK: ultra_selective (-7.70% net return).

Best mode for 30,000 NOK: ultra_selective (-7.17% net return).

Increasing to 30,000 NOK improved the best-mode net return by 0.53%, but it did not make the strategy viable because the best 30,000 NOK result remains negative.

The main issue is strategy performance: the best gross return before commission is still negative, so lower commission alone cannot fix the tested rules.
