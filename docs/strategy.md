# Master Strategy

## 80/20 Hierarchical AI Infrastructure & Adopter Portfolio

Objective: capture the AI/robotics hardware cycle while maintaining a defensive, non-correlated core.

## Architecture

The portfolio is split into two buckets and managed hierarchically.

### 80% Core

Goal: capital preservation, stability, and roughly 11.2% expected return.

- 35% COWZ: free cash flow / anti-hype equity anchor
- 15% AI adopter basket: WMT, JPM, DE at 5% each
- 25% DBMF: managed futures shock absorber
- 12.5% SGOV: T-bill liquidity / dry powder
- 12.5% TLT: long-duration recession and deflation hedge

Optional overlay: if stagflation risk increases, source 5% GLDM from SGOV and TLT.

Core equity note: COWZ is favored for the core equity slot because the strategy wants free-cash-flow yield discipline rather than dividend policy. COWZ is still an equity holding, so it should not be treated as truly non-correlated like SGOV or managed futures. Its job is to be anti-hype: favor companies that generate substantial current free cash flow relative to enterprise value, which can counterbalance the satellite's dependence on AI multiple expansion.

SCHD is a legitimate candidate, but it is an adjacent-role fund rather than a perfect COWZ substitute. SCHD emphasizes durable dividend quality, dividend growth, profitability, and balance-sheet strength. That can be attractive, but dividend history is not the same thing as free-cash-flow yield. Companies can generate substantial free cash flow and still prefer buybacks, reinvestment, debt reduction, or acquisitions over dividends. Quarterly reviews should test SCHD as a dividend-quality core candidate against COWZ, VFLO, DSTL, and broad value alternatives before changing the free-cash-flow anchor.

Managed-futures note: DBMF is the default hedge sleeve, but CTA remains an active same-role candidate. CTA should be judged by whether it adds differentiated hedge behavior versus DBMF, not merely by whether it has higher recent returns. The preferred research test is DBMF-only versus CTA-only versus a DBMF/CTA blend, with emphasis on rolling correlation, equity-drawdown behavior, TLT-drawdown behavior, Sharpe, max drawdown, worst month, and total-portfolio hedge reliability.

### 20% Satellite

Goal: high-beta AI and robotics hardware exposure with roughly 28.5% expected return.

- 40% SPRX: semiconductor and industrial hardware supply chain
- 35% ARKQ: embodied AI, automation, and energy storage
- 15% ELFY: power infrastructure and grid cooling
- 10% BAI: global AI tech stack

## Rebalancing Logic

- Rebalance internal weights within buckets quarterly.
- Do not cross the 80/20 boundary unless the master trigger fires.
- If satellite reaches 25% or 15% of total portfolio value, rebalance the master buckets back to 80/20.
- If total portfolio drawdown breaches 20% from peak, move satellite exposure to SGOV and perform a structural hardware-cycle review.

## Tactical Entry

- Deploy 25% immediately into defensive core holdings: SGOV, DBMF, and COWZ.
- Deploy the remaining 75% with DCA over 3-6 months.
- DCA installments are allocated to the remaining gaps required to reach final target weights.

## Review Protocol

Monthly review:

- Monte Carlo stress test
- satellite relative strength versus QQQ
- portfolio performance versus 80% balanced index plus 20% Nasdaq 100
- adopter basket screen

Adopter screen requires 2 of 3:

- IT capex growth greater than 10%
- declining SG&A intensity
- gross margin expansion greater than 50 bps

## Research Evidence Discipline

The AI infrastructure trade was not in play for the full historical test period, and several current funds have limited live history. Research must separate:

- actual-current evidence: current holdings only, short but real
- proxy-regime evidence: longer history using documented proxies
- thesis-inception evidence: windows that start near the AI regime shift

Interpretation rule:

```text
Longer backtest = better for risk regime behavior.
Thesis-inception backtest = better for AI trade validity.
Actual-current backtest = better for live implementation monitoring.
```

See [research-methodology.md](research-methodology.md) for the full research discipline.

See [assessment-process.md](assessment-process.md) for the monthly and quarterly operating workflow.
