# Python Quant Finance Library Map

This note captures the candidate Python libraries for the `ultimate-portfolio` research stack, plus the adoption analysis for backtesting, Monte Carlo, risk metrics, and portfolio research.

## Recommended Adoption Plan

## Current Implementation Status

The repo now has a dependency-light Phase 1 research harness:

- `ultimate_portfolio.research` computes transparent backtest metrics from price CSV data.
- The `backtest` CLI command reports CAGR, volatility, Sharpe, Sortino, Calmar, drawdowns, VaR/CVaR, benchmark-relative beta/correlation, tracking error, and information ratio.
- The `download-prices` CLI command is ready for `yfinance` ingestion once the `research` extras are installed.
- The `research-suite` CLI command adds rebalance frequency comparison, rolling diagnostics, contribution analysis, and historical-return Monte Carlo.
- Proxy-regime research is supported through `--proxy-map`, keeping actual-current evidence separate from synthetic proxy evidence.

This keeps the core math testable even before the full quant stack is installed.

### Phase 1: Reliable Research Core

Use this first. It gives the project transparent, testable analytics without pulling in a giant framework too early.

- `pandas`: baseline time-series data handling, returns, resampling, joins, and rolling windows.
- `numpy`: vectorized math, simulations, random sampling, covariance operations.
- `scipy`: statistical distributions, optimization helpers, confidence intervals, and numerical routines.
- `yfinance`: free historical market data ingestion, with local caching and clear data caveats.
- FRED via `requests`: risk-free rates and macro series for Sharpe, excess returns, and regime inputs.
- `matplotlib`: static charts for saved research reports.
- Internal metrics module: implement Sharpe, Sortino, CAGR, drawdown, VaR/CVaR, and benchmark comparison directly first so the math is transparent and covered by tests.

### Phase 2: Tear Sheets & Portfolio Risk

Add after the core pipeline works end to end.

- `pyfolio-reloaded`: performance tear sheets, drawdown plots, rolling risk diagnostics, and visual reporting.
- `Riskfolio-Lib`: CVaR, drawdown-aware optimization, hierarchical risk parity, HERC, risk contribution, and advanced portfolio constraints.
- `PyPortfolioOpt`: efficient frontier, mean-variance optimization, Black-Litterman experiments, shrinkage covariance, and quick allocation prototypes.
- `empyrical`: core risk/performance ratios; useful as a validation cross-check against our internal metrics.

### Phase 3: Advanced Modeling

Use once we have enough clean return history or proxy history to justify deeper modeling.

- `statsmodels`: factor regressions, beta, rolling exposures, econometric tests, and time-series diagnostics.
- `arch`: volatility clustering, GARCH-style volatility models, and stress-test volatility assumptions.
- `vectorbt`: fast parameter sweeps for rebalance thresholds, DCA windows, circuit-breaker settings, and large vectorized experiments.
- `optuna`: hyperparameter search for policy variants, only after strict anti-overfitting guardrails are defined.

### Defer For Now

These are good tools, but they are not the first layer for this portfolio.

- `Lean`: institutional-grade and useful for live/event-driven strategies, but heavy for quarterly ETF allocation research.
- `backtrader`: flexible event-driven retail backtesting, but less necessary for slow-moving allocation policy.
- `zipline-reloaded`: useful for Quantopian-style algorithmic backtests, but adds complexity before the research harness needs it.
- `QuantLib-Python`: excellent for derivatives and fixed-income math, but unnecessary unless we start pricing instruments directly.
- `dask`: unnecessary until datasets exceed local memory.
- `ccxt`: crypto exchange data; not relevant unless the strategy expands into crypto.
- `openbb-sdk` / OpenBB Platform: promising as a unified data layer later, but start simpler with direct, cached data ingestion.
- `polars`: very attractive for speed and lazy queries, but not required until the pandas pipeline becomes a bottleneck.

## Full Library Catalog

## Data & High-Performance Computing

### `polars`

High-speed DataFrame library and a faster alternative to pandas for many analytical workloads.

Best use in this project:

- Large cached price datasets.
- Fast joins and feature engineering.
- Lazy query pipelines once research data grows.

Current recommendation: watchlist / later adoption. Start with pandas because the surrounding quant ecosystem is still pandas-first.

### `pandas`

The industry standard for time-series data.

Best use in this project:

- Daily adjusted price series.
- Portfolio return construction.
- Monthly and quarterly rebalance calendars.
- Rolling Sharpe, rolling correlation, rolling beta.
- Benchmark alignment and missing-data handling.

Current recommendation: core dependency for the first research build.

### `numpy`

Fast numerical operations and vectorized math.

Best use in this project:

- Monte Carlo simulations.
- Return arrays and covariance math.
- Bootstrap sampling.
- Random path generation.
- Efficient risk metric implementation.

Current recommendation: core dependency.

### `scipy`

Scientific computing and optimization.

Best use in this project:

- Student-t and other fat-tail distributions.
- Optimization and root-finding.
- Statistical intervals and distribution fitting.
- Robust Monte Carlo assumptions.

Current recommendation: core dependency.

### `dask`

Parallel computing for datasets that do not fit in memory.

Best use in this project:

- Large universe research.
- Multi-asset parameter sweeps across many ETFs and equities.
- Out-of-core analytics.

Current recommendation: defer. The current strategy universe is small enough for local pandas/numpy.

## Backtesting Engines

### `vectorbt`

Vectorized backtesting engine designed for high-speed parameter optimization and large-scale testing.

Best use in this project:

- Fast sweeps of drift thresholds, DCA windows, and circuit-breaker variants.
- Comparing monthly versus quarterly internal rebalancing.
- Testing multiple proxy portfolios at once.

Current recommendation: Phase 3. Very useful once the basic research harness is stable.

### `Lean`

Event-driven institutional-grade engine used by QuantConnect, with support for live trading.

Best use in this project:

- Live or paper trading workflows.
- Intraday or event-driven execution.
- Brokerage-connected strategy deployment.

Current recommendation: defer. It is powerful but heavy for quarterly ETF policy research.

### `backtrader`

Event-driven backtesting framework that is flexible and popular with retail traders.

Best use in this project:

- Explicit order/execution simulations.
- Strategy logic with broker-like events.
- More realistic execution modeling than pure vectorized returns.

Current recommendation: defer. Useful later if we model execution in detail.

### `zipline-reloaded`

Modern continuation of the classic Quantopian event-driven backtesting engine.

Best use in this project:

- Algorithmic strategy research with event-driven portfolio accounting.
- Integration with pyfolio-style analysis.

Current recommendation: defer. Adds framework overhead before the allocation research needs it.

## Portfolio & Risk Analysis

### `Riskfolio-Lib`

Advanced asset allocation and risk modeling library.

Best use in this project:

- CVaR optimization.
- Drawdown-aware optimization.
- HRP and HERC portfolio construction.
- Risk parity experiments.
- Risk contribution by holding and bucket.
- Constraints by asset class, bucket, or thesis.

Current recommendation: Phase 2.

### `PyPortfolioOpt`

Mean-variance, Black-Litterman, shrinkage covariance, and portfolio optimization toolkit.

Best use in this project:

- Efficient frontier research.
- Max Sharpe and min volatility comparison portfolios.
- Black-Litterman blending of market-implied returns with our thesis.
- Weight sanity checks versus the fixed 80/20 system.

Current recommendation: Phase 2.

### `pyfolio-reloaded`

Performance tear sheets and risk diagnostics.

Best use in this project:

- Tear sheets for the actual portfolio and proxy portfolios.
- Drawdown charts.
- Rolling risk metrics.
- Benchmark-relative performance visualizations.

Current recommendation: Phase 2.

### `empyrical`

Core financial risk and performance ratios.

Best use in this project:

- Sharpe, Sortino, max drawdown, alpha/beta, annual returns, and related risk metrics.
- Cross-checking our internal metric implementation.

Current recommendation: Phase 2, but keep our own transparent metrics first.

## Quantitative Modeling & Simulations

### `QuantLib-Python`

Advanced pricing and quantitative finance library.

Best use in this project:

- Fixed-income instrument pricing.
- Yield curve construction.
- Derivatives pricing.
- Duration/convexity analysis beyond ETF-level proxies.

Current recommendation: defer. ETF-level portfolio research does not need it yet.

### `statsmodels`

Econometric modeling, regressions, and time-series analysis.

Best use in this project:

- Factor regressions versus QQQ, SPY, rates, value, momentum, and quality proxies.
- Rolling beta and rolling alpha.
- Correlation and cointegration diagnostics.
- Statistical tests on return series.

Current recommendation: Phase 3.

### `arch`

Autoregressive conditional heteroskedasticity models for volatility.

Best use in this project:

- GARCH volatility forecasts.
- Volatility clustering diagnostics.
- Stress-test volatility assumptions.
- More realistic Monte Carlo paths.

Current recommendation: Phase 3.

### `optuna`

Hyperparameter optimization framework.

Best use in this project:

- Searching rebalance thresholds.
- Testing DCA durations.
- Tuning circuit-breaker rules.
- Optimizing proxy assumptions.

Current recommendation: Phase 3, with strong overfitting controls.

## Market Data Access

### `openbb-sdk` / OpenBB Platform

Unified data connector for stocks, crypto, macro, and other datasets.

Best use in this project:

- One interface for multiple providers.
- Macro and market data expansion.
- Future research workbench integrations.

Current recommendation: defer. Start with direct data connectors and local caching.

### `yfinance`

Commonly used free Yahoo Finance data access.

Best use in this project:

- Historical daily adjusted prices.
- Quick first-pass portfolio backtests.
- Benchmark series.

Current recommendation: Phase 1, with clear caveats. Treat it as research/personal-use data, not institutional truth.

### `ccxt`

Cryptocurrency exchange data library.

Best use in this project:

- Crypto exchange price and market data.
- Multi-exchange crypto research.

Current recommendation: defer. Not relevant to the current ETF/equity strategy.

## Practical Environment Notes

The local system Python checked during planning was Python 3.9.6, and the core research stack was not installed yet. For the project research environment, prefer Python 3.11 or 3.12 because modern quant packages increasingly target newer Python versions.

Recommended first environment:

```text
pandas
numpy
scipy
matplotlib
yfinance
requests
```

Recommended second wave:

```text
pyfolio-reloaded
empyrical
pyportfolioopt
riskfolio-lib
statsmodels
arch
vectorbt
optuna
```

## Research Design Implication

The current holdings have uneven live histories. ELFY and BAI are especially new, so the app should keep two research modes separate:

- Actual-current-portfolio backtest: uses only live current holdings and starts when all selected tickers have data.
- Proxy-regime backtest: uses documented proxy instruments or indexes to extend history across more market regimes.
- Thesis-inception backtest: starts near the AI regime shift to evaluate whether the strategy captured the actual AI trade.

Never mix those two evidence types without labeling them clearly.

Interpretation rule:

```text
Longer backtest = better for risk regime behavior.
Thesis-inception backtest = better for AI trade validity.
Actual-current backtest = better for live implementation monitoring.
```

See [research-methodology.md](research-methodology.md) for the full framework.
