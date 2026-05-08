# Research Methodology

This project must keep different kinds of evidence separate. The AI infrastructure trade did not exist as a fully formed market regime for the whole available ETF history, and several current holdings have short live records. A longer backtest is useful, but it is not automatically more truthful.

## Evidence Modes

### Actual-Current Evidence

Uses the current holdings only.

Best for:

- current portfolio monitoring
- live implementation behavior
- actual drawdown and volatility since all tickers have existed
- current correlation versus the benchmark blend

Weakness:

- short window
- too little history for durable Sharpe, Sortino, and max drawdown estimates
- heavily influenced by the current AI cycle

Use this mode when asking: "How is the portfolio behaving now?"

### Proxy-Regime Evidence

Uses older proxy instruments for current holdings with limited live history.

Examples:

- `BAI = QQQ`
- `ELFY = GRID`

Best for:

- rate shock behavior
- recession and deflation behavior
- drawdown and recovery behavior across more regimes
- broad correlation and beta estimates
- testing whether the defensive core plausibly dampens equity shocks

Weakness:

- not the same portfolio
- not the same thesis
- may understate or overstate the AI-specific inflection
- can create false confidence if presented as actual-current evidence

Use this mode when asking: "How would similar exposures have behaved across prior regimes?"

### Thesis-Inception Evidence

Starts around the AI regime shift rather than at earliest available fund history.

Candidate inception dates:

- 2022-11-30: ChatGPT public launch
- 2023-05-24: Nvidia's major AI data center guidance shock
- 2024-01-01: clean calendar-year start for the AI infrastructure phase

Best for:

- testing whether the strategy captured the actual AI trade
- comparing AI infrastructure exposure versus QQQ or semiconductors during the relevant regime
- monitoring whether the thesis is still working

Weakness:

- still short history
- regime-specific results can look better than a full-cycle estimate
- less useful for recession or rate-shock conclusions

Use this mode when asking: "Did this strategy capture the AI infrastructure trade?"

## Core Principle

Do not let proxy history masquerade as live strategy history.

Use this interpretation rule:

```text
Longer backtest = better for risk regime behavior.
Thesis-inception backtest = better for AI trade validity.
Actual-current backtest = better for live implementation monitoring.
```

## Reporting Requirements

Every generated research report should identify:

- evidence mode
- date window
- data source
- benchmark
- proxy map, if any
- annualization assumption
- risk-free rate assumption
- whether conclusions are live, proxy, or thesis-inception evidence

When proxy mappings are used, the report must explicitly state that it is synthetic proxy-regime research, not actual-current-holdings evidence.

## Practical Implication

The project should eventually report all three modes side by side:

- actual-current holdings
- proxy-regime history
- thesis-inception windows

The goal is not to find one magic backtest. The goal is to understand which conclusions survive across evidence types and which conclusions depend on a favorable regime definition.
