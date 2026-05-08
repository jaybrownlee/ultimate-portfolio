# Assessment Process

The portfolio review process is designed to separate monitoring from decision-making.

## Cadence

### Daily Check

Purpose: monitor mechanical tripwires without encouraging daily discretionary strategy changes.

Default posture: hold unless a rule-based trigger fires.

Checks:

- satellite drift versus the 15%/25% master boundary
- near-boundary warning band before the master trigger fires
- current drawdown versus the 20% uncle point when `--peak-value` is supplied
- quarterly sweep due status

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli daily-check examples/positions.csv --as-of 2026-05-08 --peak-value 100000 --report docs/research/daily-check.md
```

The daily check should not test candidate replacements, run Monte Carlo, or make strategy changes. It is a tripwire monitor.

### Monthly Assessment

Purpose: monitor the portfolio and identify rule-based issues.

Default posture: hold unless a rule fires.

Checks:

- 80/20 master bucket drift
- quarterly sweep status
- current drawdown versus the 20% uncle point
- portfolio return, volatility, Sharpe, and max drawdown
- 63-period and 126-period rolling diagnostics
- satellite relative strength versus QQQ
- benchmark beta and correlation

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli monthly-assessment examples/positions.csv data/cache/current_prices.csv --as-of 2026-05-07 --annualization 252 --risk-free-rate 0.04 --report docs/research/monthly-assessment.md
```

### Quarterly Review

Purpose: rebalance internally, review candidates, and decide whether any role-level changes deserve deeper research.

Default posture: rebalance only according to policy; do not make structural changes without a decision memo.

Checks:

- monthly assessment checks
- forced internal bucket sweep
- rebalance frequency comparison
- same-role candidate replacement tests
- decision checklist

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli quarterly-review examples/positions.csv data/cache/candidate_prices.csv examples/asset_universe.csv --as-of 2026-05-07 --proxy-map BAI=QQQ,ELFY=GRID --annualization 252 --risk-free-rate 0.04 --report docs/research/quarterly-review.md
```

### Candidate Test

Purpose: test replacements within the same role while keeping total role weight constant.

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli candidate-test data/cache/candidate_prices.csv examples/asset_universe.csv --proxy-map BAI=QQQ,ELFY=GRID --annualization 252 --risk-free-rate 0.04
```

## Candidate Status

Candidate tests classify each replacement:

- `pass`: improved or preserved Sharpe, did not materially worsen drawdown, and did not sacrifice meaningful CAGR
- `watch`: improved at least one major dimension but introduced tradeoffs
- `reject`: failed to improve the role on the tested evidence
- `no_data`: insufficient complete price history for a window-matched comparison

These are research classifications, not trade orders.

## Managed Futures Sleeve Review

DBMF is the default managed-futures holding because its role is to provide broad trend-following hedge exposure inside the defensive core. CTA is not excluded from the strategy. It should be evaluated as a potential diversifier or partial replacement inside the managed-futures sleeve.

The key question is not whether CTA recently outperformed DBMF. The key question is whether CTA adds hedge behavior that does not always correlate with DBMF.

Quarterly reviews should test:

- DBMF-only managed-futures sleeve
- CTA-only managed-futures sleeve
- blended sleeves, such as 50/50 DBMF/CTA or 12.5% DBMF plus 7.5% CTA at the total-portfolio level

Useful evidence includes:

- CTA versus DBMF correlation, including rolling correlations
- CTA contribution during DBMF weak periods
- CTA contribution during equity drawdowns
- CTA contribution during TLT or duration-hedge drawdowns
- Sharpe, Sortino, max drawdown, worst month, and CVaR for the total portfolio
- Whether the DBMF/CTA blend improves portfolio hedge reliability versus either fund alone

CTA becomes more compelling when it wins across multiple review windows because that reduces the risk of chasing the latest trend regime. Review windows should include 63-period, 126-period, 252-period, since-CTA-inception, equity drawdown, duration drawdown, and choppy/non-trending periods when enough data is available.

Decision rule:

- Keep DBMF as the default unless CTA improves the managed-futures role without weakening portfolio-level drawdown, correlation, or liquidity.
- Move CTA from candidate to partial allocation if it beats DBMF in at least 2 of 3 major review windows while preserving or improving drawdown and correlation.
- Consider full CTA replacement only after the advantage persists across multiple quarterly reviews and stress windows.

## Decision Discipline

Every quarterly change should answer:

- Did a rule-based trigger fire, or is this discretionary?
- Which evidence mode supports the decision: actual-current, proxy-regime, or thesis-inception?
- Does the change improve the same role without breaking the 80/20 hierarchy?
- Did Sharpe, drawdown, beta, correlation, and CVaR improve or remain acceptable?
- Are taxes, spreads, liquidity, and position sizing acceptable?
- What rejected alternative should be recorded?

## Guardrail

Monthly reviews should mostly create awareness.

Quarterly reviews can create rebalance trades.

Structural strategy changes should require stronger evidence than a short actual-current backtest.
