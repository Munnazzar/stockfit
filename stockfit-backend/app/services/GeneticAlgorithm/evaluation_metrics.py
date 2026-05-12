import numpy as np
from constants import CVAR_ALPHA, SEMIVARIANCE_TARGET

# ─────────────────────────────────────────────────────────────────────────────
# HYPERPARAMETER CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

CVAR_ALPHA        = 0.05   # confidence level tail for CVaR (5% worst days) [ASSUMPTION A19]
SEMIVARIANCE_TARGET = 0.0  # threshold for downside deviation [ASSUMPTION A18]


# HELPER — build portfolio return series from weight dict + test returns
def compute_portfolio_returns(weight_dict: dict[str, float], test_returns: np.ndarray, asset_names: list[str],) -> np.ndarray:
    """
    Compute the daily portfolio return series over the test period.

    portfolio_return[t] = Σ_i  w_i * asset_return[t, i]

    Parameters
    ----------
    weight_dict  : {asset_name: weight} from GA output.
    test_returns : array of shape (T_test, N) — unseen test period returns.
    asset_names  : list of N asset names aligned with test_returns columns.

    Returns
    -------
    1-D array of daily portfolio returns, length T_test.  [ASSUMPTION A17]
    """
    # Build weight vector aligned with asset_names column order
    weights = np.array([weight_dict.get(name, 0.0) for name in asset_names])
    portfolio_returns = test_returns @ weights   # (T_test, N) @ (N,) → (T_test,)
    return portfolio_returns


# METRIC 1 — Average Daily Return
def average_daily_return(portfolio_returns: np.ndarray) -> float:
    """
    Arithmetic mean of daily portfolio returns.

    Interpretation: expected gain per trading day.
    """
    return float(np.mean(portfolio_returns))


# METRIC 2 — Cumulative Return
def cumulative_return(portfolio_returns: np.ndarray) -> float:
    """
    Total compounded return over the test period.

        Cumulative return = Π(1 + r_t) - 1

    Interpretation: total wealth growth from start to end of test period.
    """
    return float(np.prod(1 + portfolio_returns) - 1)


def cumulative_return_series(portfolio_returns: np.ndarray) -> np.ndarray:
    """
    Running cumulative return at each time step — useful for plotting drawdown.

        cum_series[t] = Π_{s=0}^{t} (1 + r_s) - 1
    """
    return np.cumprod(1 + portfolio_returns) - 1


# METRIC 3 — Daily Volatility
def daily_volatility(portfolio_returns: np.ndarray) -> float:
    """
    Standard deviation of daily portfolio returns.

    Interpretation: average day-to-day variability of returns.
    Uses ddof=1 (sample standard deviation).
    """
    return float(np.std(portfolio_returns, ddof=1))


# METRIC 4 — Maximum Drawdown
def maximum_drawdown(portfolio_returns: np.ndarray) -> float:
    """
    Largest peak-to-trough decline in the cumulative return series.

        MDD = max over all t of [ (peak_before_t - value_at_t) / (1 + peak_before_t) ]

    Interpretation: worst loss an investor would have suffered if they bought
    at the peak and held to the trough. [ASSUMPTION A20]

    Returns a positive number representing the magnitude of the drawdown
    (e.g. 0.15 means a 15% drawdown).
    """
    # Work with wealth index (starts at 1.0)
    wealth = np.cumprod(1 + portfolio_returns)

    # Running maximum wealth up to each point
    running_peak = np.maximum.accumulate(wealth)

    # Drawdown at each point = drop from the running peak
    drawdowns = (running_peak - wealth) / running_peak

    return float(np.max(drawdowns))


# METRIC 5 — Semivariance
def semivariance(portfolio_returns: np.ndarray, target: float = SEMIVARIANCE_TARGET,) -> float:
    """
    Semivariance — variance computed only over returns that fall BELOW the target.

        SV = (1 / T) * Σ  min(r_t - target, 0)²

    Interpretation: captures only downside risk, ignoring positive deviations.
    More informative than variance when return distributions are asymmetric,
    which is common in financial returns. [ASSUMPTION A18]

    Parameters
    ----------
    portfolio_returns : daily return series.
    target           : threshold below which returns are considered losses (default 0).
    """
    downside = np.minimum(portfolio_returns - target, 0)   # zero out positive days
    return float(np.mean(downside ** 2))


# METRIC 6 — CVaR (Conditional Value at Risk / Expected Shortfall)
def cvar(portfolio_returns: np.ndarray, alpha: float = CVAR_ALPHA,) -> float:
    """
    Conditional Value at Risk (CVaR), also known as Expected Shortfall.

        CVaR_α = -E[ r_t | r_t ≤ VaR_α ]

    Steps:
        1. Find the α-quantile of returns (VaR threshold).
        2. Average all returns at or below that threshold.
        3. Negate so CVaR is reported as a positive loss magnitude.

    Interpretation: average loss on the worst α% of trading days.
    A CVaR of 0.03 means: on the worst 5% of days, the average loss was 3%.
    [ASSUMPTION A19]: alpha = 0.05 (95% confidence level).

    Parameters
    ----------
    portfolio_returns : daily return series.
    alpha            : tail probability (default 0.05 = worst 5% of days).
    """
    var_threshold = np.quantile(portfolio_returns, alpha)       # VaR at level alpha
    tail_returns  = portfolio_returns[portfolio_returns <= var_threshold]
    return float(-np.mean(tail_returns))                        # positive = loss


# COMBINED — Run all metrics at once
def backtest_portfolio(weight_dict: dict[str, float], test_returns: np.ndarray, asset_names: list[str], cvar_alpha: float = CVAR_ALPHA, semivariance_target: float = SEMIVARIANCE_TARGET,) -> dict[str, float]:
    """
    Full backtesting evaluation of an optimal portfolio over the test period.

    Parameters:
        weight_dict  : optimal portfolio weights from the GA  {asset_name: weight}.
        test_returns : unseen test period return matrix, shape (T_test, N).
        asset_names  : list of N asset names aligned with test_returns columns.
        cvar_alpha   : tail probability for CVaR.
        semivariance_target : downside threshold for semivariance.

    Returns:
        dict of all six backtesting metrics.
    """
    # Build the portfolio's daily return series over the test period
    port_returns = compute_portfolio_returns(weight_dict, test_returns, asset_names)

    return {
        "avg_daily_return":  average_daily_return(port_returns),
        "cumulative_return": cumulative_return(port_returns),
        "daily_volatility":  daily_volatility(port_returns),
        "max_drawdown":      maximum_drawdown(port_returns),
        "semivariance":      semivariance(port_returns, target=semivariance_target),
        "cvar":              cvar(port_returns, alpha=cvar_alpha),
    }



def validation_score(backtest_results: dict) -> float:
    avg_return  = backtest_results["avg_daily_return"]
    volatility  = backtest_results["daily_volatility"]
    drawdown    = backtest_results["max_drawdown"]
    cvar        = backtest_results["cvar"]
    semivar     = backtest_results["semivariance"]

    if volatility < 1e-10:
        return float("inf")

    sharpe = avg_return / volatility

    # Penalise portfolios with negative or near-zero average daily return
    # A portfolio that loses money should never score well regardless of risk metrics
    return_penalty = max(0, -avg_return) * 50  # scales with how negative the return is

    return (
        - sharpe
        + 1.5  * drawdown
        + 1.5  * cvar
        + 100  * semivar
        + return_penalty      # hard discouragement of loss-making portfolios
    )