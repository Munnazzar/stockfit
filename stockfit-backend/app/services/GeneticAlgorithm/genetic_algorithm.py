import numpy as np
from typing import Optional
from scipy import stats

try:
    from .constants import (
        N_PARENTS, TOURNAMENT_SIZE, BLX_ALPHA, GENE_MIN, GENE_MAX,
        CXPB, MUTPB, INDPB, HOF_SIZE, N_GENERATIONS, POP_SIZE,
    )
    from .portfolio_evaluation import evaluate_population
    from .integration import build_forward_stats_dict
except ImportError:  # pragma: no cover - allows running as a script
    from constants import (
        N_PARENTS, TOURNAMENT_SIZE, BLX_ALPHA, GENE_MIN, GENE_MAX,
        CXPB, MUTPB, INDPB, HOF_SIZE, N_GENERATIONS, POP_SIZE,
    )
    from portfolio_evaluation import evaluate_population
    from integration import build_forward_stats_dict

def compute_statistics_from_returns(returns: np.ndarray) -> dict[str, np.ndarray]:
    """
    Derive µ, Σ, skewness vector, and kurtosis vector from a historical return matrix.

    Parameters:
        2-D array of shape (T, N) — T time periods, N assets.

    Returns:
        dict with keys: 'mu', 'cov', 'skew_vec', 'kurt_vec'
    """
    mu       = np.mean(returns, axis=0)            # per-stock mean return
    cov      = np.cov(returns, rowvar=False)        # sample covariance  [ASSUMPTION A3]
    skew_vec = stats.skew(returns, axis=0)          # per-stock skewness [ASSUMPTION A2]
    kurt_vec = stats.kurtosis(returns, axis=0)      # per-stock excess kurtosis [ASSUMPTION A2]

    return {"mu": mu, "cov": cov, "skew_vec": skew_vec, "kurt_vec": kurt_vec}

# SELECTION — Tournament Selection
def tournament_selection(evaluated_population: list[dict], n_parents: int = N_PARENTS, tournament_size: int = TOURNAMENT_SIZE, rng: Optional[np.random.Generator] = None,) -> list[np.ndarray]:
    """
    Tournament selection with replacement.

    For each parent slot:
        1. Draw `tournament_size` individuals at random (with replacement).
        2. The individual with the LOWEST fitness wins (we minimise).

    Parameters:
        evaluated_population : output of evaluate_population() — list of result dicts,
                            each containing 'fitness' and 'weight_dict'.
        n_parents            : how many parents to select in total.
        tournament_size      : number of competitors per tournament (default 3).
        rng                  : numpy random generator (for reproducibility).

    Returns:
        List of selected chromosomes (np.ndarray), length = n_parents.
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(evaluated_population)
    selected = []

    for _ in range(n_parents):
        # Draw tournament_size indices with replacement
        competitor_indices = rng.integers(0, n, size=tournament_size)
        competitors = [evaluated_population[i] for i in competitor_indices]

        # Winner = lowest fitness (minimisation problem)
        winner = min(competitors, key=lambda ind: ind["fitness"])

        # Return the raw chromosome (reconstruct from weight_dict)
        # We store chromosomes separately — see run_generation() for how they're paired
        selected.append(winner["_chromosome"])

    return selected


# CROSSOVER — Blend Crossover BLX-α
def blx_alpha_crossover(parent1: np.ndarray, parent2: np.ndarray, alpha: float = BLX_ALPHA, gene_min: float = GENE_MIN, gene_max: float = GENE_MAX, rng: Optional[np.random.Generator] = None,) -> tuple[np.ndarray, np.ndarray]:
    """
    BLX-α (Blend Crossover) operator.

    Parameters:
        parent1, parent2 : chromosomes of two parents, same length N.
        alpha            : BLX-α exploration parameter.
        gene_min/max     : bounds for clipping offspring genes. [ASSUMPTION A13]

    Returns:
        Two offspring chromosomes (child1, child2).
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(parent1)
    child1 = np.empty(n)
    child2 = np.empty(n)

    for i in range(n):
        lo = min(parent1[i], parent2[i])
        hi = max(parent1[i], parent2[i])
        d  = hi - lo                        # gap between the two parent genes

        # Expanded range: stretch by α on each side
        sample_lo = lo - alpha * d
        sample_hi = hi + alpha * d

        # Draw two independent offspring genes from this range
        child1[i] = rng.uniform(sample_lo, sample_hi)
        child2[i] = rng.uniform(sample_lo, sample_hi)

    # Clip to permissible gene range
    child1 = np.clip(child1, gene_min, gene_max)
    child2 = np.clip(child2, gene_min, gene_max)

    return child1, child2


def apply_crossover(parents: list[np.ndarray], cxpb: float = CXPB, alpha: float = BLX_ALPHA, n_offspring: int = POP_SIZE, rng: Optional[np.random.Generator] = None,) -> list[np.ndarray]:
    """
    Apply BLX-α crossover to the parent pool, cycling through it repeatedly
    until exactly n_offspring children have been produced.

    Parameters:
        parents    : list of selected parent chromosomes (length = N_PARENTS).
        cxpb       : crossover probability per pair.
        n_offspring: exact number of offspring to generate (default = POP_SIZE).
        rng        : numpy random generator.

    Returns:
        List of offspring chromosomes, length = n_offspring.
    """
    if rng is None:
        rng = np.random.default_rng()

    n = len(parents)
    offspring = []
    pair_index = 0  # cycles through parent pairs via modulo

    while len(offspring) < n_offspring:
        p1 = parents[pair_index % n].copy()
        p2 = parents[(pair_index + 1) % n].copy()
        pair_index += 2

        if rng.random() < cxpb:
            c1, c2 = blx_alpha_crossover(p1, p2, alpha=alpha, rng=rng)
        else:
            c1, c2 = p1.copy(), p2.copy()

        offspring.append(c1)
        if len(offspring) < n_offspring:   # avoid adding one extra on odd n_offspring
            offspring.append(c2)

    return offspring


# 3. MUTATION — Uniform Mutation
def uniform_mutation(chromosome: np.ndarray, indpb: float = INDPB, gene_min: float = GENE_MIN, gene_max: float = GENE_MAX, rng: Optional[np.random.Generator] = None,) -> np.ndarray:
    """
    Uniform mutation operator.


    For each gene:
        - Draw a random value u ~ Uniform(0, 1).
        - If u < indpb, replace the gene with a new random value
          drawn from Uniform(gene_min, gene_max).

    Parameters
    ----------
    chromosome : individual to mutate (modified in place on a copy).
    indpb      : per-gene mutation probability.
    gene_min/max: permissible gene range. [ASSUMPTION A13]

    Returns
    -------
    Mutated chromosome (new array, original unchanged).
    """
    if rng is None:
        rng = np.random.default_rng()

    mutant = chromosome.copy()
    for i in range(len(mutant)):
        if rng.random() < indpb:
            mutant[i] = rng.uniform(gene_min, gene_max)

    return mutant


def apply_mutation(offspring: list[np.ndarray], mutpb: float = MUTPB, indpb: float = INDPB, rng: Optional[np.random.Generator] = None,) -> list[np.ndarray]:
    """
    Apply uniform mutation to an offspring pool.

    Parameters:
        offspring : list of chromosomes from the crossover step.
        mutpb     : probability that a given individual is mutated at all.
        indpb     : per-gene mutation probability (used inside uniform_mutation).

    Returns:
        List of (possibly mutated) chromosomes.
    """
    if rng is None:
        rng = np.random.default_rng()

    mutated = []
    for individual in offspring:
        if rng.random() < mutpb:
            individual = uniform_mutation(individual, indpb=indpb, rng=rng)
        mutated.append(individual)

    return mutated

class HallOfFame:
    """
    Archive that records the best individuals found across all generations.

    Internally stores up to `max_size` result dicts, always keeping those
    with the lowest (best) fitness values.
    """

    def __init__(self, max_size: int = HOF_SIZE):
        self.max_size = max_size
        self.members: list[dict] = []   # list of result dicts, sorted best-first

    def update(self, evaluated_population: list[dict]) -> None:
        # Merge current HOF with new candidates
        candidates = self.members + evaluated_population
        # Sort by fitness ascending (lowest = best)
        candidates.sort(key=lambda r: r["fitness"])
        # Deduplicate: keep only the first occurrence of each unique weight_dict
        seen: set = set()
        unique: list[dict] = []
        for r in candidates:
            key = frozenset(r["weight_dict"].items())
            if key not in seen:
                seen.add(key)
                unique.append(r)
        self.members = unique[: self.max_size]

    @property
    def best(self) -> dict:
        """Return the single best individual ever seen."""
        return self.members[0] if self.members else {}

    def __repr__(self) -> str:
        lines = [f"HallOfFame (top {len(self.members)}/{self.max_size}):"]
        for rank, m in enumerate(self.members, 1):
            lines.append(f"  #{rank}  fitness={m['fitness']:.6f}  "
                         f"weights={m['weight_dict']}")
        return "\n".join(lines)


# ONE GENERATION
def run_generation(population: np.ndarray, asset_names: list[str], stats_dict: dict, n_parents: int = N_PARENTS, tournament_size: int = TOURNAMENT_SIZE, cxpb: float = CXPB, blx_alpha: float = BLX_ALPHA, mutpb: float = MUTPB, indpb: float = INDPB, rng: Optional[np.random.Generator] = None, apply_blue_chip: bool = False,) -> tuple[np.ndarray, list[dict]]:
    """
    Execute one full generation of the GA.

    Steps (mirroring DEAP's eaSimple logic)
        1. Evaluate the current population.
        2. Select parents via tournament selection.
        3. Apply BLX-α crossover to parent pairs.
        4. Apply uniform mutation to offspring.
        5. Full generational replacement: offspring become the new population.

    Parameters:
        population   : current population array, shape (POP_SIZE, N).
        asset_names  : list of N asset name strings.
        stats_dict   : precomputed return statistics.
        n_parents    : number of parents to select.
        tournament_size : competitors per tournament.
        cxpb         : crossover probability per pair.
        blx_alpha    : BLX-α exploration parameter.
        mutpb        : per-individual mutation probability.
        indpb        : per-gene mutation probability.
        rng          : numpy random generator.

    Returns:
        new_population : offspring array, shape (POP_SIZE, N).
        evaluated      : list of evaluated result dicts for the current population (used by HOF and for logging).
    """
    if rng is None:
        rng = np.random.default_rng()

    # Evaluate current population
    evaluated = evaluate_population(population, asset_names, stats_dict, apply_blue_chip=apply_blue_chip)

    # Tournament selection
    parents = tournament_selection(evaluated, n_parents, tournament_size, rng)

    # BLX-α crossover — parents cycle until exactly pop_size offspring are produced
    pop_size = len(population)
    offspring = apply_crossover(parents, cxpb=cxpb, alpha=blx_alpha, n_offspring=pop_size, rng=rng)

    # Uniform mutation
    offspring = apply_mutation(offspring, mutpb=mutpb, indpb=indpb, rng=rng)

    # Full generational replacement: offspring become the new population
    new_population = np.array(offspring)

    return new_population, evaluated

# 6. FULL GA LOOP
def run_ga(initial_population: np.ndarray, asset_names: list[str], returns: np.ndarray, n_generations: int = N_GENERATIONS, n_parents: int = N_PARENTS, tournament_size: int = TOURNAMENT_SIZE, cxpb: float = CXPB, blx_alpha: float = BLX_ALPHA, mutpb: float = MUTPB, indpb: float = INDPB, hof_size: int = HOF_SIZE, seed: Optional[int] = None, apply_blue_chip: bool = False,) -> tuple[dict, list[float], list[float]]:
    """
    Returns:
        best_result  : result dict of the best individual ever found.
        best_per_gen : list of best (minimum) fitness per generation.
        mean_per_gen : list of mean fitness per generation.
    """
    rng        = np.random.default_rng(seed)
    stats_dict = compute_statistics_from_returns(returns)
    hof        = HallOfFame(max_size=hof_size)
    population = initial_population.copy()

    best_per_gen = []
    mean_per_gen = []

    for _ in range(1, n_generations + 1):
        population, evaluated = run_generation(
            population, asset_names, stats_dict,
            n_parents, tournament_size, cxpb, blx_alpha, mutpb, indpb, rng,
            apply_blue_chip=apply_blue_chip,
        )

        hof.update(evaluated)

        fitnesses = [r["fitness"] for r in evaluated]
        best_per_gen.append(min(fitnesses))
        mean_per_gen.append(sum(fitnesses) / len(fitnesses))

        # print(f"Gen {gen:>3d} | best: {best_per_gen[-1]:.6f} "
        #       f"| mean: {mean_per_gen[-1]:.6f} "
        #       f"| HOF: {hof.best.get('fitness', float('nan')):.6f}")

    return hof.best, best_per_gen, mean_per_gen


def run_ga_forward(
    initial_population: np.ndarray,
    asset_names: list[str],
    returns: np.ndarray,
    master_outputs: np.ndarray,
    master_alpha: float = 0.3,
    n_generations: int = N_GENERATIONS,
    n_parents: int = N_PARENTS,
    tournament_size: int = TOURNAMENT_SIZE,
    cxpb: float = CXPB,
    blx_alpha: float = BLX_ALPHA,
    mutpb: float = MUTPB,
    indpb: float = INDPB,
    hof_size: int = HOF_SIZE,
    seed: Optional[int] = None,
    apply_blue_chip: bool = False,
) -> tuple[dict, list[float], list[float]]:
    """
    Run the GA with MASTER transformer predictions blended into expected returns.

    Identical to run_ga except that stats_dict["mu"] is replaced by a weighted
    blend of historical mean returns and MASTER's forward-looking signal before
    the generation loop starts. All other GA mechanics — selection, crossover,
    mutation, Hall of Fame — are unchanged.

    When master_alpha=0.0 the blended mu equals mu_historical exactly, so
    run_ga_forward produces identical results to run_ga with the same seed.

    Parameters
    ----------
    initial_population : np.ndarray, shape (POP_SIZE, N)
        Starting chromosomes for the GA.
    asset_names : list[str]
        Ordered list of N KSE 30 / PSX asset tickers, aligned with the columns
        of both `returns` and `master_outputs`.
    returns : np.ndarray, shape (T, N)
        Historical training returns used to compute mu, cov, skew, and kurtosis.
    master_outputs : np.ndarray, shape (D, N)
        Raw MASTER Z-score predictions for N KSE 30 / PSX stocks over D recent
        trading days. Averaged internally to shape (N,) before blending.
    master_alpha : float
        Blending weight for the MASTER signal in [0.0, 1.0].
        0.0 → pure historical (identical to run_ga); 1.0 → fully MASTER-driven.
    n_generations : int
        Number of GA generations to run.
    n_parents : int
        Number of parents selected per generation via tournament selection.
    tournament_size : int
        Competitors drawn per tournament.
    cxpb : float
        Crossover probability per parent pair.
    blx_alpha : float
        BLX-α exploration parameter.
    mutpb : float
        Per-individual mutation probability.
    indpb : float
        Per-gene mutation probability.
    hof_size : int
        Maximum Hall of Fame capacity.
    seed : int or None
        Seed for the numpy random generator (for reproducibility).

    Returns
    -------
    best_result : dict
        Result dict of the best individual ever found across all generations.
    best_per_gen : list[float]
        Best (minimum) fitness recorded each generation.
    mean_per_gen : list[float]
        Mean fitness recorded each generation.
    """
    rng              = np.random.default_rng(seed)
    historical_stats = compute_statistics_from_returns(returns)
    stats_dict       = build_forward_stats_dict(
        historical_stats, master_outputs, alpha=master_alpha
    )
    hof        = HallOfFame(max_size=hof_size)
    population = initial_population.copy()

    best_per_gen = []
    mean_per_gen = []

    for _ in range(1, n_generations + 1):
        population, evaluated = run_generation(
            population, asset_names, stats_dict,
            n_parents, tournament_size, cxpb, blx_alpha, mutpb, indpb, rng,
            apply_blue_chip=apply_blue_chip,
        )

        hof.update(evaluated)

        fitnesses = [r["fitness"] for r in evaluated]
        best_per_gen.append(min(fitnesses))
        mean_per_gen.append(sum(fitnesses) / len(fitnesses))

    return hof.best, best_per_gen, mean_per_gen