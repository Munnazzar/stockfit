import numpy as np


def average_master_predictions(master_outputs: np.ndarray) -> np.ndarray:
    """
    Reduce MASTER's multi-date prediction array to a single signal per stock.

    Averaging over multiple prediction dates reduces noise from any single
    prediction, producing a more stable forward-looking signal for the GA.
    For example, a single day's Z-scores may be driven by transient market
    micro-structure; averaging across D recent days smooths this out.

    Parameters
    ----------
    master_outputs : np.ndarray, shape (D, N)
        MASTER Z-score predictions for N KSE 30 / PSX stocks over D recent
        trading days. Positive values indicate the stock is predicted to
        outperform the market on that date.

    Returns
    -------
    np.ndarray, shape (N,)
        Mean Z-score signal averaged across all D prediction dates.

    Raises
    ------
    ValueError
        If master_outputs is not a 2-D array.
    """
    if master_outputs.ndim != 2:
        raise ValueError(
            f"master_outputs must be 2D with shape (D, N), got shape {master_outputs.shape}"
        )
    return np.mean(master_outputs, axis=0)


def rescale_master_to_return_space(
    master_rankings: np.ndarray,
    mu_historical: np.ndarray,
    method: str = "std_match",
    signal_scale: float = 3.0,
) -> np.ndarray:
    """
    Rescale MASTER Z-scores into the same numerical scale as historical returns.

    MASTER outputs are Z-score normalised signals (dimensionless, ~N(0,1));
    historical mu values are daily return fractions (e.g. 0.0008). Direct
    blending without rescaling would let the MASTER signal swamp the historical
    estimates and distort the GA fitness function. This function aligns both
    signals to the same mean and standard deviation before blending.

    Method "std_match":
        1. Centre master_rankings at zero by subtracting its own mean.
        2. Scale its std to signal_scale × mu_historical's std.
           signal_scale > 1 amplifies the MASTER correction so it has a
           meaningful effect on tournament selection relative to the
           volatility term (which otherwise dominates the fitness function
           by ~5–8×).
        3. Shift the result to mu_historical's mean.

    Parameters
    ----------
    master_rankings : np.ndarray, shape (N,)
        Averaged MASTER Z-scores for N KSE 30 / PSX stocks (output of
        average_master_predictions).
    mu_historical : np.ndarray, shape (N,)
        Historical mean daily returns from stats_dict["mu"].
    method : str
        Rescaling method. Currently only "std_match" is supported.
    signal_scale : float
        Multiplier applied to mu_historical's std when rescaling. Default 3.0
        ensures the MASTER correction is large enough to influence tournament
        selection despite the volatility term dominating the fitness function.
        Set to 1.0 to recover the original same-std behaviour.

    Returns
    -------
    np.ndarray, shape (N,)
        Rescaled signal expressed in the same units and scale as mu_historical.
        Returns mu_historical unchanged if all MASTER predictions are identical
        (std < 1e-10), since no ordinal information can be recovered.
    """
    if master_rankings.std() < 1e-10:
        return mu_historical.copy()

    centred = master_rankings - master_rankings.mean()
    scaled = centred * (signal_scale * mu_historical.std() / master_rankings.std())
    return scaled + mu_historical.mean()


def blend_expected_returns(
    mu_historical: np.ndarray,
    master_rankings: np.ndarray,
    alpha: float = 0.3,
    rescale_method: str = "std_match",
    signal_scale: float = 3.0,
) -> np.ndarray:
    """
    Blend historical mean returns with a rescaled MASTER signal.

    The blended vector replaces stats_dict["mu"] inside the GA fitness
    function, allowing MASTER's forward-looking predictions to tilt
    portfolio selection without fully discarding the stability of
    historical return estimates.

    At alpha=0.0 the function returns mu_historical exactly, so the GA
    behaves identically to the baseline run_ga with the same seed.

    Parameters
    ----------
    mu_historical : np.ndarray, shape (N,)
        Historical mean daily returns for N KSE 30 / PSX stocks.
    master_rankings : np.ndarray, shape (N,)
        Averaged MASTER Z-scores, already reduced to shape (N,) by
        average_master_predictions.
    alpha : float
        Blending weight for the MASTER signal, must be in [0.0, 1.0].
        0.0 → pure historical; 1.0 → fully MASTER-driven (rescaled).
    rescale_method : str
        Passed through to rescale_master_to_return_space.

    Returns
    -------
    np.ndarray, shape (N,)
        Blended expected-return vector: (1 - alpha) * mu_historical
        + alpha * rescaled_master.

    Raises
    ------
    ValueError
        If alpha is outside [0.0, 1.0].
    """
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(f"alpha must be in [0.0, 1.0], got {alpha}")

    master_rescaled = rescale_master_to_return_space(
        master_rankings, mu_historical, method=rescale_method, signal_scale=signal_scale
    )
    return (1.0 - alpha) * mu_historical + alpha * master_rescaled


def build_forward_stats_dict(
    stats_dict: dict,
    master_outputs: np.ndarray,
    alpha: float = 0.3,
    rescale_method: str = "std_match",
    signal_scale: float = 3.0,
) -> dict:
    """
    Build a forward-looking stats dict by replacing mu with a MASTER-blended signal.

    Accepts the raw 2D MASTER output (D, N), averages it internally to (N,),
    rescales it to return space, then blends it with the historical mu. All
    other statistical quantities — covariance, skewness, kurtosis — are carried
    over unchanged so the rest of the GA fitness function is unaffected.

    Parameters
    ----------
    stats_dict : dict
        Output of compute_statistics_from_returns. Must contain keys
        "mu", "cov", "skew_vec", "kurt_vec".
    master_outputs : np.ndarray, shape (D, N)
        Raw MASTER Z-score predictions for N KSE 30 / PSX stocks over D
        recent trading days.
    alpha : float
        Blending weight for the MASTER signal in [0.0, 1.0].
    rescale_method : str
        Passed through to rescale_master_to_return_space.

    Returns
    -------
    dict
        Shallow copy of stats_dict with only the "mu" key replaced by the
        blended expected-return vector. Keys "cov", "skew_vec", and
        "kurt_vec" are identical to the originals.
    """
    master_avg = average_master_predictions(master_outputs)
    blended_mu = blend_expected_returns(
        stats_dict["mu"], master_avg, alpha=alpha,
        rescale_method=rescale_method, signal_scale=signal_scale,
    )
    forward_stats = dict(stats_dict)
    forward_stats["mu"] = blended_mu
    return forward_stats