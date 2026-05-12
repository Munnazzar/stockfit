import numpy as np

try:
    from .constants import (
        MAX_ASSETS, WEIGHT_DECIMALS, GENE_UPPER_BOUND, MAX_WEIGHT,
        ALPHA, BETA, GAMMA, DELTA, MODERATE_PENALTY, SEVERE_PENALTY,
        APPLY_BLUE_CHIP, BLUE_CHIP_STOCKS, BLUE_CHIP_BONUS,
    )
except ImportError:  # pragma: no cover - allows running as a script
    from constants import (
        MAX_ASSETS, WEIGHT_DECIMALS, GENE_UPPER_BOUND, MAX_WEIGHT,
        ALPHA, BETA, GAMMA, DELTA, MODERATE_PENALTY, SEVERE_PENALTY,
        APPLY_BLUE_CHIP, BLUE_CHIP_STOCKS, BLUE_CHIP_BONUS,
    )

def decode_chromosome(chromosome: np.ndarray, asset_names: list[str], max_assets: int = MAX_ASSETS, weight_decimals: int = WEIGHT_DECIMALS) -> dict[str, float]:
    """
    Convert a raw chromosome (relative-priority genes) into a valid weight vector.

    Parameters:
        chromosome    : 1-D array of raw gene values (length = number of assets N).
        asset_names   : list of asset ticker / name strings, length N.
        max_assets    : maximum number of assets allowed in a single portfolio.
        weight_decimals: decimal places for rounding weights.

    Returns:
        dict mapping asset_name to portfolio weight (non-zero entries only).
    """
    n = len(chromosome)
    assert n == len(asset_names), "chromosome length must equal number of assets"

    weights = chromosome.copy().astype(float)

    # zero-out all but the top max_assets genes
    if max_assets < n:
        top_indices = np.argsort(weights)[-max_assets:]
        mask = np.zeros(n, dtype=bool)
        mask[top_indices] = True
        weights[~mask] = 0.0

    # Make all negative values zero
    weights = np.clip(weights, 0.0, None)

    # normalise all weights to sum = 1
    total = weights.sum()
    if total == 0:
        # Degenerate individual: assign equal weight to all assets (fallback)
        weights = np.ones(n) / n
    else:
        weights /= total

    # Decimal adjustment
    weights = np.round(weights, weight_decimals)
    # Re-normalise after rounding
    total = weights.sum()
    if total > 0:
        weights /= total
        weights = np.round(weights, weight_decimals)

    return {name: w for name, w in zip(asset_names, weights) if w > 0}

def compute_portfolio_metrics(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, skew_vec: np.ndarray, kurt_vec: np.ndarray) -> dict[str, float]:
    """
    Compute the four portfolio-level statistics used in the fitness function.
    Formulae (from the paper):

    Parameters:
        weights   : 1-D array of portfolio weights, length N.
        mu        : 1-D array of asset expected returns, length N.
        cov       : 2-D covariance matrix, shape (N, N).
        skew_vec  : 1-D array of per-asset skewness values, length N.
        kurt_vec  : 1-D array of per-asset excess kurtosis values, length N.

    Returns:
        dict with keys: 'mu_p', 'sigma_p', 'skew_p', 'kurt_p'
    """
    w = np.asarray(weights, dtype=float)

    mu_p    = float(mu @ w)                          # µ_p = µ̃ᵀ · w̃
    var_p   = float(w @ cov @ w)                     # variance
    sigma_p = float(np.sqrt(max(var_p, 0.0)))        # σ_p = √(w̃ᵀ Σ w̃)
    skew_p  = float(skew_vec @ w)                    # Skew_p = s̃ᵀ · w̃
    kurt_p  = float(kurt_vec @ w)                    # Kurt_p = k̃ᵀ · w̃

    return {
        "mu_p":    mu_p,
        "sigma_p": sigma_p,
        "skew_p":  skew_p,
        "kurt_p":  kurt_p,
    }

# OBJECTIVE / FITNESS FUNCTION
def fitness_function(mu_p: float, sigma_p: float, skew_p: float, kurt_p: float) -> float:
    """
    The core fitness formula (Equation 1, Section 3.2.2):
    Objective: MINIMISE FO: maximise return & positive skewness, minimise volatility & kurtosis.

    Parameters:
        mu_p    : portfolio expected return
        sigma_p : portfolio volatility
        skew_p  : portfolio skewness
        kurt_p  : portfolio kurtosis

    Returns:
        float: fitness value
    """
    fitness = -(ALPHA * mu_p  -  BETA * sigma_p  +  GAMMA * skew_p  -  DELTA * kurt_p)
    return fitness

def evaluate_individual(chromosome: np.ndarray, asset_names: list[str], stats_dict: dict, max_assets: int = MAX_ASSETS, gene_upper_bound: float = GENE_UPPER_BOUND, max_weight: float = MAX_WEIGHT, weight_decimals: int = WEIGHT_DECIMALS, apply_blue_chip: bool = APPLY_BLUE_CHIP) -> dict:
    """
    Two-stage evaluation of a single individual. Convert genotype to phenotype, then phenotype to fitness.

    Parameters:
        chromosome      : raw gene array, length N.
        asset_names     : list of N asset names (order matches chromosome / returns columns).
        stats_dict      : pre-computed statistics dictionary from compute_statistics_from_returns().
        max_assets      : maximum number of assets allowed in portfolio.
        gene_upper_bound: upper bound for each gene (e.g. 0.8 = 80%).
        max_weight      : per-asset upper bound (e.g. 0.30 = 30%).
        weight_decimals : decimal places for weight rounding.
        apply_blue_chip : whether to enable the blue chip incentive bonus.

    Returns:
        dict with keys:
            'weight_dict'       : decoded portfolio weights
            'metrics'           : µ_p, σ_p, Skew_p, Kurt_p
            'base_fitness'      : fitness before penalties / blue chip bonus
            'fitness'           : final fitness (after penalties and optional blue chip bonus)
            'penalties'         : list of penalty reasons applied (empty if none)
            'blue_chip_applied' : bool
    """

    # Decode chromosome into portfolio weights
    weight_dict = decode_chromosome(chromosome, asset_names, max_assets, weight_decimals)

    # Build full-length weight vector aligned with asset_names
    w_full = np.array([weight_dict.get(name, 0.0) for name in asset_names])

    # Compute portfolio-level metrics
    mu       = stats_dict["mu"]
    cov      = stats_dict["cov"]
    skew_vec = stats_dict["skew_vec"]
    kurt_vec = stats_dict["kurt_vec"]
    metrics = compute_portfolio_metrics(w_full, mu, cov, skew_vec, kurt_vec)

    # Base fitness from objective function
    base_fitness = fitness_function(metrics["mu_p"], metrics["sigma_p"], metrics["skew_p"], metrics["kurt_p"])
    fitness  = base_fitness
    penalties = []

    # CONSTRAINT CHECKS
    # Gene upper-bound check: moderate penalty (soft)
    if np.any(chromosome > gene_upper_bound):
        fitness += MODERATE_PENALTY
        penalties.append(f"Gene upper-bound violated (max allowed per gene: {max_weight}). Moderate penalty added: {MODERATE_PENALTY}")

    # Max weight per asset: severe penalty (hard)
    if any(w > max_weight + 1e-9 for w in weight_dict.values()):
        fitness = SEVERE_PENALTY
        penalties.append(f"Max-weight-per-asset constraint violated (limit: {max_weight}). Severe penalty applied: {SEVERE_PENALTY}")

    # Blue chip bonus: only apply bonus if the individual is not already penalised
    blue_chip_applied = False
    if apply_blue_chip and len(penalties) == 0:
        holds_blue_chip = any(name in BLUE_CHIP_STOCKS and w > 0 for name, w in weight_dict.items())
        if holds_blue_chip:
            fitness -= BLUE_CHIP_BONUS
            blue_chip_applied = True

    return {
        "weight_dict":        weight_dict,
        "metrics":            metrics,
        "base_fitness":       base_fitness,
        "fitness":            fitness,
        "penalties":          penalties,
        "blue_chip_applied":  blue_chip_applied,
    }

# POPULATION-LEVEL EVALUATION  (evaluate every individual in the population)
def evaluate_population(population: np.ndarray, asset_names: list[str], stats_dict: dict, max_assets: int= MAX_ASSETS, gene_upper_bound: float = GENE_UPPER_BOUND, max_weight: float = MAX_WEIGHT, weight_decimals: int = WEIGHT_DECIMALS, apply_blue_chip: bool = APPLY_BLUE_CHIP,) -> list[dict]:
    """
    Evaluate all individuals in a population.

    Parameters:
        population  : 2-D arr
        ay of shape (POP_SIZE, N).
        (all other params same as evaluate_individual)

    Returns:
        List of result dicts (one per individual), sorted by ascending fitness.
    """
    results = []
    for i, chromosome in enumerate(population):
        result = evaluate_individual(
            chromosome=chromosome,
            asset_names=asset_names,
            stats_dict=stats_dict,
            max_assets=max_assets,
            gene_upper_bound=gene_upper_bound,
            max_weight=max_weight,
            weight_decimals=weight_decimals,
            apply_blue_chip=apply_blue_chip
        )
        result["individual_index"] = i
        result["_chromosome"] = chromosome
        results.append(result)

    results.sort(key=lambda r: r["fitness"])
    return results