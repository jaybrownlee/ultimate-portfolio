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

### Candidate Screen

Purpose: maintain the living research bench of current champions and challengers.

The candidate screen combines same-role replacement math with ticker-level diagnostics:

- 63/126/252-period momentum
- 126-period volatility-adjusted momentum
- 200-period moving-average trend state
- current drawdown from trailing high
- correlation to incumbent when a replacement target exists
- beta and correlation to the ticker-level benchmark symbol
- replacement-test deltas for CAGR, Sharpe, and max drawdown
- reason codes that explain why each ticker received its priority label
- role summaries that identify current incumbents, best challengers, and the next review action

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli screen-candidates data/cache/candidate_prices.csv examples/asset_universe.csv --proxy-map BAI=QQQ,ELFY=GRID --benchmark-symbol QQQ --annualization 252 --risk-free-rate 0.04 --report docs/research/candidate-screen.md
```

The screen is a research triage tool. It should promote candidates to deeper review, not directly authorize trades.

Priority labels are role-aware:

- Cash candidates need capital stability first; tiny Sharpe improvements are not enough if drawdown worsens.
- Hedge candidates need low benchmark beta and/or differentiated behavior versus the incumbent.
- Core equity candidates need risk-adjusted improvement without turning the defensive core into a high-beta growth sleeve.
- Satellite candidates can tolerate higher beta, but they still need role fit, momentum, and acceptable replacement math.

Reason codes are intentionally plain text so the report can be audited later. Examples include `better_sharpe`, `better_drawdown`, `lower_cagr`, `low_incumbent_correlation`, `high_benchmark_beta`, `below_200d_average`, `deep_current_drawdown`, `capital_stability`, and `hedge_like_beta`.

The role summary should be used as the first pass for "what deserves a memo?" A `high` challenger means "research this", not "trade this." A monitored incumbent means the current holding has a trend or drawdown issue that should be reviewed at the next quarterly checkpoint.

Future signal layers can extend this command without changing the decision workflow:

- macro regime feeds from FRED for rates, inflation, yield curve, credit spreads, dollar, and commodities
- SEC and fundamentals feeds for free-cash-flow yield, margins, debt, ROE, capex, and dividend quality
- news/event feeds for issuer updates, earnings guidance changes, product-cycle news, regulatory changes, and ETF methodology changes
- implementation feeds for AUM, average volume, spreads, expense ratio, and inception age

These inputs should produce documented flags and notes, not automatic trades.

## Candidate Status

Candidate tests classify each replacement:

- `pass`: improved or preserved Sharpe, did not materially worsen drawdown, and did not sacrifice meaningful CAGR
- `watch`: improved at least one major dimension but introduced tradeoffs
- `reject`: failed to improve the role on the tested evidence
- `no_data`: insufficient complete price history for a window-matched comparison

These are research classifications, not trade orders.

## Core Equity Sleeve Review

COWZ is the default core equity anchor because the portfolio is trying to own cash-generative, valuation-aware companies rather than the most exciting growth stories. The role is anti-hype equity exposure, not income maximization.

SCHD should stay in the research universe, but it should be treated as a dividend-quality candidate rather than a pure free-cash-flow substitute. Its evidence threshold should answer whether dividend quality improves the core sleeve's total-portfolio behavior versus the current free-cash-flow anchor.

Quarterly reviews should test:

- COWZ-only core equity anchor
- SCHD replacing COWZ
- other free-cash-flow/value candidates such as VFLO and DSTL
- broad value or quality alternatives when data is available

Useful evidence includes:

- performance during tech multiple compression
- correlation and beta versus QQQ and the benchmark blend
- Sharpe, Sortino, max drawdown, worst month, and CVaR
- contribution during equity drawdowns
- whether dividend quality reduces drawdown without sacrificing too much cash-flow-value exposure

Decision rule:

- Keep COWZ as the default unless a candidate improves portfolio-level risk-adjusted performance while preserving the anti-hype core equity role.
- Treat SCHD as a credible adjacent-role candidate, not an automatic replacement, because dividend policy and free-cash-flow yield are related but not identical.

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
