import numpy as np
import pandas as pd
import itertools
from IPython.display import display
from data_pre_processing import DataSplit
from genetic_algorithm import run_ga, run_ga_forward
from evaluation_metrics import backtest_portfolio, validation_score
from constants import N_GENERATIONS, POP_SIZE, GENE_UPPER_BOUND

def run_default(data: DataSplit, seed: int = 42) -> dict:
    """
    Returns:
        result dict with keys: best_result, val_metrics, val_score, history
    """
    N = len(data.asset_names)

    print("=" * 60)
    print("  RUNNING GA WITH DEFAULT PARAMETERS")
    print("=" * 60)
    print(f"  Assets         : {N}")
    print(f"  Training days  : {len(data.train_dates)}")
    print(f"  Validation days: {len(data.val_dates)}")
    print(f"  Generations    : {N_GENERATIONS}")
    print(f"  Population     : {POP_SIZE}")
    print()

    # Initial population — random genes in [0, 1]
    initial_pop = np.random.default_rng(seed).uniform(0, 1, size=(POP_SIZE, N))

    # Run GA on training data (Cycle-1: returns + MASTER predictions)
    best_result, history,_ = run_ga_forward(
        initial_population = initial_pop,
        asset_names        = data.asset_names,
        returns            = data.train,
        master_outputs     = data.train_master,
        seed               = seed,
    )

    # Evaluate best portfolio on validation data
    best_weights = best_result["weight_dict"]
    val_metrics  = backtest_portfolio(best_weights, data.val, data.asset_names)
    val_score    = validation_score(val_metrics)

    print("\n Best Portfolio Fitness: ", best_result["fitness"])
    print()

    # ── Print weights table ───────────────────────────────────────────────────
    print("\n── Best Portfolio Weights ───────────────────────────────────")
    weights_df = pd.DataFrame([
        {"Asset": k, "Weight": f"{v:.4f}", "Weight (%)": f"{v*100:.2f}%"}
        for k, v in sorted(best_weights.items(), key=lambda x: -x[1])
    ])
    display(weights_df.style.hide(axis="index"))

    # ── Print validation metrics table ────────────────────────────────────────
    print("\n── Validation Metrics ───────────────────────────────────────")
    metrics_df = pd.DataFrame([
        {"Metric":              "Avg Daily Return",
         "Value":               f"{val_metrics['avg_daily_return']:+.6f}",
         "Interpretation":      "Mean gain per trading day"},
        {"Metric":              "Cumulative Return",
         "Value":               f"{val_metrics['cumulative_return']:+.4%}",
         "Interpretation":      "Total compounded return over validation period"},
        {"Metric":              "Daily Volatility",
         "Value":               f"{val_metrics['daily_volatility']:.6f}",
         "Interpretation":      "Std dev of daily returns (lower = more stable)"},
        {"Metric":              "Max Drawdown",
         "Value":               f"{val_metrics['max_drawdown']:.4%}",
         "Interpretation":      "Worst peak-to-trough loss (lower = better)"},
        {"Metric":              "Semivariance",
         "Value":               f"{val_metrics['semivariance']:.8f}",
         "Interpretation":      "Downside-only risk (lower = better)"},
        {"Metric":              "CVaR (95%)",
         "Value":               f"{val_metrics['cvar']:.6f}",
         "Interpretation":      "Avg loss on worst 5% of days (lower = better)"},
        {"Metric":              "Validation Score",
         "Value":               f"{val_score:.6f}",
         "Interpretation":      "Composite score — lower is better"},
    ])
    display(metrics_df.style.hide(axis="index"))

    return {"best_result": best_result, "val_metrics": val_metrics, "val_score": val_score, "history": history}


# HYPERPARAMETER TUNING
def build_param_grid() -> list[dict]:
    """
    Build all combinations of the four hyperparameters to tune.

    Ranges:
        CXPB         : 0.1 to 0.9 in steps of 0.2  → [0.1, 0.3, 0.5, 0.7, 0.9]
        MUTPB        : 0.1 to 0.9 in steps of 0.2  → [0.1, 0.3, 0.5, 0.7, 0.9]
        indpb        : [0.05, 0.15]
        master_alpha : [0.1, 0.3, 0.5, 0.7]  (blend weight for MASTER signal)

    Total combinations: 5 × 5 × 2 × 4 = 200
    """
    cxpb_values         = [round(v, 2) for v in np.arange(0.1, 1.0, 0.2)]  # [0.1, 0.3, 0.5, 0.7, 0.9]
    mutpb_values        = [round(v, 2) for v in np.arange(0.1, 1.0, 0.2)]  # [0.1, 0.3, 0.5, 0.7, 0.9]
    indpb_values        = [0.05, 0.15]
    master_alpha_values = [0.1, 0.3, 0.5, 0.7]

    grid = [
        {"cxpb": cxpb, "mutpb": mutpb, "indpb": indpb, "master_alpha": ma}
        for cxpb, mutpb, indpb, ma in itertools.product(
            cxpb_values, mutpb_values, indpb_values, master_alpha_values
        )
    ]

    print(f"  Parameter grid: {len(cxpb_values)} CXPB × "
          f"{len(mutpb_values)} MUTPB × "
          f"{len(indpb_values)} INDPB × "
          f"{len(master_alpha_values)} MASTER_ALPHA = {len(grid)} combinations\n")
    return grid

def tune_hyperparameters(data: DataSplit, seed: int = 42, n_seeds: int = 5) -> dict:
    N            = len(data.asset_names)
    seeds_to_use = [seed + k * 100 for k in range(n_seeds)]

    print("=" * 60)
    print("  HYPERPARAMETER TUNING")
    print(f"  Seeds per combination : {seeds_to_use}")
    print("=" * 60)

    param_grid = build_param_grid()
    total      = len(param_grid)
    log        = []

    for i, params in enumerate(param_grid, 1):
        print(f"[{i:>3}/{total}]  CXPB={params['cxpb']}  MUTPB={params['mutpb']}  "
              f"indpb={params['indpb']}  alpha={params['master_alpha']}: ", end="")

        seed_scores        = []
        seed_metrics       = []
        seed_best_fitnesses = []  # ← track raw GA fitness per seed

        for s in seeds_to_use:
            initial_pop = np.random.default_rng(s).uniform(
                0, GENE_UPPER_BOUND, size=(POP_SIZE, N)
            )

            best_result, best_per_gen, mean_per_gen = run_ga_forward(
                initial_population = initial_pop,
                asset_names        = data.asset_names,
                returns            = data.train,
                master_outputs     = data.train_master,
                master_alpha       = params["master_alpha"],
                cxpb               = params["cxpb"],
                mutpb              = params["mutpb"],
                indpb              = params["indpb"],
                seed               = s,
            )

            val_metrics = backtest_portfolio(
                best_result["weight_dict"], data.val, data.asset_names
            )
            score = validation_score(val_metrics)

            seed_scores.append(score)
            seed_metrics.append(val_metrics)
            seed_best_fitnesses.append(best_result["fitness"])  # ← collect

            # print(f"    seed={s}  fitness={best_result['fitness']:.6f}  "
            #       f"val_score={score:.6f}")

        # ── Aggregate across seeds ────────────────────────────────────────────
        def avg_metric(key):
            return sum(m[key] for m in seed_metrics) / len(seed_metrics)

        avg_score       = float(np.mean(seed_scores))
        std_score       = float(np.std(seed_scores))
        avg_fitness     = float(np.mean(seed_best_fitnesses))
        best_fitness    = float(np.min(seed_best_fitnesses))   # best across seeds

        print(f"avg_score={avg_score:.6f}  std={std_score:.6f} avg_fit={avg_fitness:.6f}  best_fit={best_fitness:.6f}")

        log.append({
            "cxpb":              params["cxpb"],
            "mutpb":             params["mutpb"],
            "indpb":             params["indpb"],
            "master_alpha":      params["master_alpha"],
            "val_score":         avg_score,
            "val_score_std":     std_score,
            "avg_fitness":       avg_fitness,   # mean GA fitness across seeds
            "best_fitness":      best_fitness,  # best single GA fitness seen
            "avg_daily_return":  avg_metric("avg_daily_return"),
            "cumulative_return": avg_metric("cumulative_return"),
            "daily_volatility":  avg_metric("daily_volatility"),
            "max_drawdown":      avg_metric("max_drawdown"),
            "semivariance":      avg_metric("semivariance"),
            "cvar":              avg_metric("cvar"),
        })

    # ── Sort and display ──────────────────────────────────────────────────────
    results_df = pd.DataFrame(log).sort_values("val_score").reset_index(drop=True)
    results_df.index += 1

    display_df = results_df.copy()
    display_df["rank"] = display_df.index

    display_df["avg_daily_return"]  = display_df["avg_daily_return"].map("{:+.6f}".format)
    display_df["cumulative_return"] = display_df["cumulative_return"].map("{:+.4%}".format)
    display_df["daily_volatility"]  = display_df["daily_volatility"].map("{:.6f}".format)
    display_df["max_drawdown"]      = display_df["max_drawdown"].map("{:.4%}".format)
    display_df["semivariance"]      = display_df["semivariance"].map("{:.8f}".format)
    display_df["cvar"]              = display_df["cvar"].map("{:.6f}".format)
    display_df["val_score"]         = display_df["val_score"].map("{:.6f}".format)
    display_df["val_score_std"]     = display_df["val_score_std"].map("{:.6f}".format)
    display_df["avg_fitness"]       = display_df["avg_fitness"].map("{:.6f}".format)
    display_df["best_fitness"]      = display_df["best_fitness"].map("{:.6f}".format)

    display_df = display_df[[
        "rank", "cxpb", "mutpb", "indpb", "master_alpha",
        "best_fitness", "avg_fitness",
        "val_score", "val_score_std",
        "avg_daily_return", "cumulative_return",
        "daily_volatility", "max_drawdown",
        "semivariance", "cvar",
    ]]

    print("\n── Hyperparameter Tuning Results (sorted by avg validation score) ──")
    display(display_df.style.hide(axis="index"))

    best_row    = results_df.iloc[0]
    best_params = {
        "cxpb":         best_row["cxpb"],
        "mutpb":        best_row["mutpb"],
        "indpb":        best_row["indpb"],
        "master_alpha": best_row["master_alpha"],
    }

    print(f"\n── Best Parameters ──────────────────────────────────────────")
    print(f"  CXPB             = {best_params['cxpb']}")
    print(f"  MUTPB            = {best_params['mutpb']}")
    print(f"  indpb            = {best_params['indpb']}")
    print(f"  master_alpha     = {best_params['master_alpha']}")
    print(f"  Avg val score    = {best_row['val_score']:.6f}")
    print(f"  Std val score    = {best_row['val_score_std']:.6f}")
    print(f"  Avg GA fitness   = {best_row['avg_fitness']:.6f}")
    print(f"  Best GA fitness  = {best_row['best_fitness']:.6f}")

    return {
        "best_params": best_params,
        "all_results": results_df,
    }


# FINAL EVALUATION — use test data exactly once after tuning


def final_evaluation(data: DataSplit, tuning_result: dict, seed: int = 19) -> dict:
    """
    Returns:
        dict with keys: hof, ga_metrics, benchmark_metrics, comparison_df, test_score
    """
    best_params = tuning_result["best_params"]
    # best_params= {'cxpb': np.float64(0.5), 'mutpb': np.float64(0.3), 'indpb': np.float64(0.15)}

    N           = len(data.asset_names)

    print("=" * 60)
    print("  FINAL EVALUATION ON TEST DATA")
    print("  (test data accessed for the first and only time)")
    print("=" * 60)
    print(f"  Best hyperparameters : {best_params}")
    print(f"  Assets               : {N}")
    print(f"  Cycle-2 train days   : {len(data.final_train_dates)}")
    print(f"  Cycle-2 train period : {data.final_train_dates[0].date()} → {data.final_train_dates[-1].date()}")
    print(f"  Test days            : {len(data.test_dates)}")
    print(f"  Test period          : {data.test_dates[0].date()} → {data.test_dates[-1].date()}\n")

    # ── Re-run GA+MASTER on Cycle-2 training data with best hyperparameters ──
    print("  Running GA+MASTER with best hyperparameters on Cycle-2 training data...")
    initial_pop = np.random.default_rng(seed).uniform(0, GENE_UPPER_BOUND, size=(POP_SIZE, N))
    best_result, history, _ = run_ga_forward(
        initial_population = initial_pop,
        asset_names        = data.asset_names,
        returns            = data.final_train,
        master_outputs     = data.final_train_master,
        **best_params,
        seed               = seed,
    )
    ga_master_weights = best_result["weight_dict"]

    # ── Re-run GA without MASTER (same GA hyperparameters, no signal) ─────────
    print("  Running GA (no MASTER) with best hyperparameters on Cycle-2 training data...")
    ga_only_params = {k: v for k, v in best_params.items() if k != "master_alpha"}
    best_result_no_master, history_no_master, _ = run_ga(
        initial_population = initial_pop,
        asset_names        = data.asset_names,
        returns            = data.final_train,
        **ga_only_params,
        seed               = seed,
    )
    ga_only_weights = best_result_no_master["weight_dict"]

    # ── Re-run GA+MASTER+Blue Chips (MASTER signal + blue chip incentive) ─────
    print("  Running GA+MASTER+Blue Chips with best hyperparameters on Cycle-2 training data...")
    best_result_bc, history_bc, _ = run_ga_forward(
        initial_population = initial_pop,
        asset_names        = data.asset_names,
        returns            = data.final_train,
        master_outputs     = data.final_train_master,
        apply_blue_chip    = True,
        **best_params,
        seed               = seed,
    )
    ga_bc_weights = best_result_bc["weight_dict"]

    # ── Equal-weight benchmark ────────────────────────────────────────────────
    benchmark_weights = {asset: 1 / N for asset in data.asset_names}

    # ── Unlock test data — exactly once ───────────────────────────────────────
    test_returns = data.get_test()

    # ── Evaluate all four portfolios on test data ─────────────────────────────
    ga_master_metrics = backtest_portfolio(ga_master_weights, test_returns, data.asset_names)
    ga_only_metrics   = backtest_portfolio(ga_only_weights,   test_returns, data.asset_names)
    ga_bc_metrics     = backtest_portfolio(ga_bc_weights,     test_returns, data.asset_names)
    benchmark_metrics = backtest_portfolio(benchmark_weights, test_returns, data.asset_names)

    ga_master_score = validation_score(ga_master_metrics)
    ga_only_score   = validation_score(ga_only_metrics)
    ga_bc_score     = validation_score(ga_bc_metrics)
    benchmark_score = validation_score(benchmark_metrics)

    # ── Weights tables ────────────────────────────────────────────────────────
    def _weights_table(label: str, weights: dict) -> None:
        print(f"\n── {label} Weights ──────────────────────────────────────")
        df = pd.DataFrame([
            {"Asset": k, "Weight": f"{v:.4f}", "Allocation": f"{v*100:.2f}%"}
            for k, v in sorted(weights.items(), key=lambda x: -x[1])
        ])
        display(df.style.hide(axis="index"))

    _weights_table("GA+MASTER",            ga_master_weights)
    _weights_table("GA (no MASTER)",       ga_only_weights)
    _weights_table("GA+MASTER+Blue Chips", ga_bc_weights)

    # ── Four-way comparison table ─────────────────────────────────────────────
    higher_is_better = {"avg_daily_return", "cumulative_return"}

    def _winner(metric: str, gam: float, ga: float, gabc: float, ew: float) -> str:
        vals = {"GA+MASTER": gam, "GA": ga, "GA+BC": gabc, "EW": ew}
        best = (max if metric in higher_is_better else min)(vals, key=vals.get)
        return f"{best} ✓"

    rows = [
        {
            "Metric":               "Avg Daily Return",
            "GA+MASTER":            f"{ga_master_metrics['avg_daily_return']:+.6f}",
            "GA (no MASTER)":       f"{ga_only_metrics['avg_daily_return']:+.6f}",
            "GA+MASTER+Blue Chips": f"{ga_bc_metrics['avg_daily_return']:+.6f}",
            "Equal Weight":         f"{benchmark_metrics['avg_daily_return']:+.6f}",
            "Best": _winner("avg_daily_return",
                            ga_master_metrics["avg_daily_return"],
                            ga_only_metrics["avg_daily_return"],
                            ga_bc_metrics["avg_daily_return"],
                            benchmark_metrics["avg_daily_return"]),
        },
        {
            "Metric":               "Cumulative Return",
            "GA+MASTER":            f"{ga_master_metrics['cumulative_return']:+.4%}",
            "GA (no MASTER)":       f"{ga_only_metrics['cumulative_return']:+.4%}",
            "GA+MASTER+Blue Chips": f"{ga_bc_metrics['cumulative_return']:+.4%}",
            "Equal Weight":         f"{benchmark_metrics['cumulative_return']:+.4%}",
            "Best": _winner("cumulative_return",
                            ga_master_metrics["cumulative_return"],
                            ga_only_metrics["cumulative_return"],
                            ga_bc_metrics["cumulative_return"],
                            benchmark_metrics["cumulative_return"]),
        },
        {
            "Metric":               "Daily Volatility",
            "GA+MASTER":            f"{ga_master_metrics['daily_volatility']:.6f}",
            "GA (no MASTER)":       f"{ga_only_metrics['daily_volatility']:.6f}",
            "GA+MASTER+Blue Chips": f"{ga_bc_metrics['daily_volatility']:.6f}",
            "Equal Weight":         f"{benchmark_metrics['daily_volatility']:.6f}",
            "Best": _winner("daily_volatility",
                            ga_master_metrics["daily_volatility"],
                            ga_only_metrics["daily_volatility"],
                            ga_bc_metrics["daily_volatility"],
                            benchmark_metrics["daily_volatility"]),
        },
        {
            "Metric":               "Max Drawdown",
            "GA+MASTER":            f"{ga_master_metrics['max_drawdown']:.4%}",
            "GA (no MASTER)":       f"{ga_only_metrics['max_drawdown']:.4%}",
            "GA+MASTER+Blue Chips": f"{ga_bc_metrics['max_drawdown']:.4%}",
            "Equal Weight":         f"{benchmark_metrics['max_drawdown']:.4%}",
            "Best": _winner("max_drawdown",
                            ga_master_metrics["max_drawdown"],
                            ga_only_metrics["max_drawdown"],
                            ga_bc_metrics["max_drawdown"],
                            benchmark_metrics["max_drawdown"]),
        },
        {
            "Metric":               "Semivariance",
            "GA+MASTER":            f"{ga_master_metrics['semivariance']:.8f}",
            "GA (no MASTER)":       f"{ga_only_metrics['semivariance']:.8f}",
            "GA+MASTER+Blue Chips": f"{ga_bc_metrics['semivariance']:.8f}",
            "Equal Weight":         f"{benchmark_metrics['semivariance']:.8f}",
            "Best": _winner("semivariance",
                            ga_master_metrics["semivariance"],
                            ga_only_metrics["semivariance"],
                            ga_bc_metrics["semivariance"],
                            benchmark_metrics["semivariance"]),
        },
        {
            "Metric":               "CVaR (95%)",
            "GA+MASTER":            f"{ga_master_metrics['cvar']:.6f}",
            "GA (no MASTER)":       f"{ga_only_metrics['cvar']:.6f}",
            "GA+MASTER+Blue Chips": f"{ga_bc_metrics['cvar']:.6f}",
            "Equal Weight":         f"{benchmark_metrics['cvar']:.6f}",
            "Best": _winner("cvar",
                            ga_master_metrics["cvar"],
                            ga_only_metrics["cvar"],
                            ga_bc_metrics["cvar"],
                            benchmark_metrics["cvar"]),
        },
        {
            "Metric":               "Fitness Score",
            "GA+MASTER":            f"{ga_master_score:.6f}",
            "GA (no MASTER)":       f"{ga_only_score:.6f}",
            "GA+MASTER+Blue Chips": f"{ga_bc_score:.6f}",
            "Equal Weight":         f"{benchmark_score:.6f}",
            "Best": _winner("fitness",
                            ga_master_score,
                            ga_only_score,
                            ga_bc_score,
                            benchmark_score),
        },
    ]

    comparison_df = pd.DataFrame(rows)

    gam_wins  = sum(1 for r in rows if r["Best"].startswith("GA+MASTER "))
    ga_wins   = sum(1 for r in rows if r["Best"].startswith("GA "))
    gabc_wins = sum(1 for r in rows if r["Best"].startswith("GA+BC"))
    ew_wins   = sum(1 for r in rows if r["Best"].startswith("EW"))

    print("\n── Test Period Comparison: GA+MASTER vs GA vs GA+MASTER+Blue Chips vs Equal-Weight ──")
    display(comparison_df.style.hide(axis="index"))

    print(f"\n  GA+MASTER wins            : {gam_wins} / {len(rows)} metrics")
    print(f"  GA (no MASTER) wins       : {ga_wins} / {len(rows)} metrics")
    print(f"  GA+MASTER+Blue Chips wins : {gabc_wins} / {len(rows)} metrics")
    print(f"  Equal-Weight wins         : {ew_wins} / {len(rows)} metrics")

    return {
        "optimized_portfolio":      best_result,
        "ga_master_weights":        ga_master_weights,
        "ga_only_weights":          ga_only_weights,
        "ga_bc_weights":            ga_bc_weights,
        "benchmark_weights":        benchmark_weights,
        "ga_master_metrics":        ga_master_metrics,
        "ga_only_metrics":          ga_only_metrics,
        "ga_bc_metrics":            ga_bc_metrics,
        "benchmark_metrics":        benchmark_metrics,
        "ga_master_score":          ga_master_score,
        "ga_only_score":            ga_only_score,
        "ga_bc_score":              ga_bc_score,
        "benchmark_score":          benchmark_score,
        "comparison_df":            comparison_df,
        "history":                  history,
        "history_no_master":        history_no_master,
        "history_bc":               history_bc,
    }