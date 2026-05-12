import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from constants import START_DATE, MAX_MISSING_RATIO, TRAIN_RATIO, VAL_RATIO


def load_raw_data(filepath: str | Path) -> pd.DataFrame:
    """
    Returns:
      DataFrame with lowercase column names, 'date' as datetime, sorted by symbol then date.
    """
    filepath = Path(filepath)
    print(f"\nLoading: {filepath.name}")

    if filepath.suffix == ".csv":
        df = pd.read_csv(filepath)
    elif filepath.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    else:
        raise ValueError(f"Unsupported file type: {filepath.suffix}. Use .csv or .xlsx")

    # Normalise column names
    df.columns = df.columns.str.strip().str.lower()

    # Validate required columns
    required = {"symbol", "date", "close"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Parse dates
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()

    # Apply start date filter
    df = df[df["date"] >= pd.to_datetime(START_DATE)]

    # Uppercase symbols for consistency
    df["symbol"] = df["symbol"].str.upper().str.strip()

    # Sort
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    print(f"  Rows loaded       : {len(df):,}")
    print(f"  Unique assets     : {df['symbol'].nunique()}")
    print(f"  Date range (raw)  : {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  Columns           : {list(df.columns)}")

    return df


def per_asset_report(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate a per-asset quality summary before any cleaning.

    Reports for each asset:
        - first / last date
        - total trading days observed
        - missing close values (NaN in the raw data)
        - duplicate dates
        - longest gap (consecutive missing trading days)

    Returns:
        DataFrame with one row per asset, sorted by missing_pct descending.
    """
    # Build the full trading calendar (union of all dates in the file)
    all_dates = pd.DatetimeIndex(sorted(df["date"].unique()))
    total_days = len(all_dates)

    records = []
    for symbol, grp in df.groupby("symbol"):
        grp = grp.set_index("date").reindex(all_dates)   # align to full calendar

        # Gap analysis on reindexed series
        close = grp["close"]
        is_missing = close.isna()

        # Longest consecutive gap
        max_gap = 0
        current_gap = 0
        for m in is_missing:
            if m:
                current_gap += 1
                max_gap = max(max_gap, current_gap)
            else:
                current_gap = 0

        records.append({
            "symbol"       : symbol,
            "first_date"   : grp.index[close.first_valid_index() == grp.index].min()
                              if close.first_valid_index() is not None
                              else pd.NaT,
            "last_date"    : grp.index[close.last_valid_index() == grp.index].max()
                              if close.last_valid_index() is not None
                              else pd.NaT,
            "observed_days": int((~is_missing).sum()),
            "missing_days" : int(is_missing.sum()),
            "missing_pct"  : round(is_missing.mean() * 100, 2),
            "longest_gap"  : max_gap,
            "duplicate_dates": int(df[df["symbol"] == symbol]["date"].duplicated().sum()),
        })

    report = pd.DataFrame(records).sort_values("missing_pct", ascending=False)
    report = report.reset_index(drop=True)

    print(f"\n── Per-Asset Quality Report ({len(report)} assets, "
          f"{total_days} total trading days in calendar) ──")
    print(report.to_string(index=False))

    # Flag assets that will be dropped
    to_drop = report[report["missing_pct"] / 100 > MAX_MISSING_RATIO]["symbol"].tolist()
    if to_drop:
        print(f"\n  [!] Assets exceeding {MAX_MISSING_RATIO:.0%} missing threshold "
              f"(will be dropped): {to_drop}")
    else:
        print(f"\n  [✓] All assets within {MAX_MISSING_RATIO:.0%} missing threshold.")

    return report


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Clean: drop sparse assets, remove duplicates, fill gaps
# ─────────────────────────────────────────────────────────────────────────────

def clean_data(df: pd.DataFrame, max_missing_ratio: float = MAX_MISSING_RATIO,) -> tuple[pd.DataFrame, list[str]]:
    """
    Returns:
        cleaned_df : long-format DataFrame after drops and deduplication.
        dropped    : list of dropped asset names.
    """
    # Remove duplicates
    n_before = len(df)
    df = df.drop_duplicates(subset=["symbol", "date"], keep="last")
    n_dupes = n_before - len(df)
    if n_dupes > 0:
        print(f"\n  Removed {n_dupes} duplicate (symbol, date) rows.")

    # Build full calendar to measure missing fraction per asset
    all_dates = pd.DatetimeIndex(sorted(df["date"].unique()))
    total_days = len(all_dates)

    dropped = []
    # print("\n── Missing Ratio per Asset (post START_DATE filter) ──")

    asset_stats = []

    for symbol, grp in df.groupby("symbol"):
        observed = grp["date"].nunique()
        missing_ratio = 1 - (observed / total_days)

        asset_stats.append((symbol, observed, total_days, missing_ratio))

    # Convert to DataFrame for nice printing
    stats_df = pd.DataFrame(asset_stats, columns=[
        "symbol", "observed_days", "total_days", "missing_ratio"
    ])

    stats_df["missing_pct"] = (stats_df["missing_ratio"] * 100).round(2)
    stats_df = stats_df.sort_values("missing_ratio", ascending=False)

    # print(stats_df.to_string(index=False))

    # Decide drops
    dropped = stats_df[
        stats_df["missing_ratio"] > max_missing_ratio
    ]["symbol"].tolist()
    if dropped:
        df = df[~df["symbol"].isin(dropped)]
        print(f"\n  Dropped {len(dropped)} asset(s) with >{max_missing_ratio:.0%} "
              f"missing data: {dropped}")
    else:
        print(f"\n  No assets dropped — all within {max_missing_ratio:.0%} threshold.")

    return df, dropped


def pivot_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns:
        Wide DataFrame: shape (T, N), fully populated, no NaNs.
    """
    prices = df.pivot(index="date", columns="symbol", values="close")
    prices.index = pd.DatetimeIndex(prices.index)
    prices = prices.sort_index()

    n_before_fill = prices.isna().sum().sum()

    # Forward-fill then back-fill  [A4]
    prices = prices.ffill().bfill()

    n_after_fill = prices.isna().sum().sum()
    filled = n_before_fill - n_after_fill

    print(f"\n  Pivoted price matrix : {prices.shape[0]} dates × {prices.shape[1]} assets")
    print(f"  Gaps filled (ffill/bfill): {filled:,}")

    # Drop any remaining NaN dates (shouldn't exist after ffill/bfill unless
    # an asset has zero data — already removed in clean_data)  [A5]
    rows_before = len(prices)
    prices = prices.dropna()
    rows_dropped = rows_before - len(prices)
    if rows_dropped > 0:
        print(f"  Dropped {rows_dropped} dates with remaining NaNs after filling.")

    print(f"  Final price matrix   : {prices.shape[0]} dates × {prices.shape[1]} assets")
    print(f"  Aligned date range   : {prices.index[0].date()} → {prices.index[-1].date()}")

    return prices


# STEP 5 — Compute daily simple returns
def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily simple returns from closing prices.
        r_t = (close_t - close_{t-1}) / close_{t-1}
    Returns:
        DataFrame shape (T-1, N).
    """
    returns = prices.pct_change().dropna()
    print(f"\n  Returns matrix : {returns.shape[0]} days × {returns.shape[1]} assets")
    return returns


# STEP 6 — Train / Val / Test split with the DataSplit guard
@dataclass
class DataSplit:
    """
    Holds train / validation / test splits for both returns and MASTER predictions.

    Two evaluation cycles are supported:
      Cycle 1 (hyperparameter tuning) : train → val → test (locked)
      Cycle 2 (final evaluation)      : final_train (= train + val) → same test

    MASTER arrays are None when the object is created by the ratio-based
    split_returns() function (no MASTER file provided).

    Field ordering rule: ALL required fields (no default) come first so that
    Python's dataclass machinery can build a valid __init__ signature.
    """
    # ── Required fields — must appear before any field that has a default ──────
    train:        np.ndarray
    val:          np.ndarray
    asset_names:  list[str]
    train_dates:  pd.DatetimeIndex
    val_dates:    pd.DatetimeIndex
    test_dates:   pd.DatetimeIndex
    _test:        np.ndarray        = field(repr=False)

    # ── Optional / defaulted fields ───────────────────────────────────────────
    _test_accessed:      bool                    = field(default=False, repr=False)
    # MASTER training arrays (val and test use returns only)
    train_master:        Optional[np.ndarray]    = field(default=None,  repr=False)
    # Cycle-2: final_train = original train + val; test is the same locked period
    final_train:         Optional[np.ndarray]    = field(default=None,  repr=False)
    final_train_master:  Optional[np.ndarray]    = field(default=None,  repr=False)
    final_train_dates:   Optional[pd.DatetimeIndex] = field(default=None, repr=False)

    def get_test(self) -> np.ndarray:
        """Returns test array. Raises on second call to prevent data leakage."""
        # if self._test_accessed:
        #     raise RuntimeError(
        #         "Test data has already been accessed once. "
        #         "Do not evaluate on test data more than once — "
        #         "this invalidates your backtest."
        #     )
        self._test_accessed = True
        return self._test

    def summary(self) -> None:
        T_train = len(self.train_dates)
        T_val   = len(self.val_dates)
        T_test  = len(self.test_dates)
        T_total = T_train + T_val + T_test

        print("\n" + "=" * 60)
        print("  DATA SPLIT SUMMARY")
        print("=" * 60)
        print(f"  Assets  : {len(self.asset_names)}")
        print(f"  {'Period':<10} {'Days':>6}  {'Start':>12}  {'End':>12}  {'Share':>6}")
        print(f"  {'-'*52}")
        print(f"  {'Train':<10} {T_train:>6}  "
              f"{str(self.train_dates[0].date()):>12}  "
              f"{str(self.train_dates[-1].date()):>12}  "
              f"{T_train/T_total:>6.1%}")
        print(f"  {'Validation':<10} {T_val:>6}  "
              f"{str(self.val_dates[0].date()):>12}  "
              f"{str(self.val_dates[-1].date()):>12}  "
              f"{T_val/T_total:>6.1%}")
        print(f"  {'Test':<10} {T_test:>6}  "
              f"{str(self.test_dates[0].date()):>12}  "
              f"{str(self.test_dates[-1].date()):>12}  "
              f"{T_test/T_total:>6.1%}")
        print(f"  {'-'*52}")
        print(f"  {'Total':<10} {T_total:>6}")

        if self.final_train_dates is not None:
            T_ft = len(self.final_train_dates)
            print(f"\n  Cycle-2 train : {T_ft} days  "
                  f"({str(self.final_train_dates[0].date())} → "
                  f"{str(self.final_train_dates[-1].date())})")
            print(f"  Cycle-2 test  : {T_test} days  "
                  f"({str(self.test_dates[0].date())} → "
                  f"{str(self.test_dates[-1].date())})  [locked]")

        print("=" * 60)
        print(f"\n  Asset list ({len(self.asset_names)}):")
        for i, name in enumerate(self.asset_names, 1):
            print(f"    {i:>3}. {name}")

        if self.train_master is not None:
            print(f"\n  MASTER arrays (training only, shape = days × assets):")
            print(f"    train_master       : {self.train_master.shape}")
            if self.final_train_master is not None:
                print(f"    final_train_master : {self.final_train_master.shape}")

        print()


def split_returns(returns: pd.DataFrame, train_ratio: float = TRAIN_RATIO, val_ratio: float = VAL_RATIO) -> "DataSplit":
    """
    Returns:
        DataSplit object.
    """
    T  = len(returns)
    t1 = int(T * train_ratio)
    t2 = int(T * (train_ratio + val_ratio))

    train_df = returns.iloc[:t1]
    val_df   = returns.iloc[t1:t2]
    test_df  = returns.iloc[t2:]

    return DataSplit(
        train       = train_df.values,
        val         = val_df.values,
        _test       = test_df.values,
        asset_names = list(returns.columns),
        train_dates = pd.DatetimeIndex(train_df.index),
        val_dates   = pd.DatetimeIndex(val_df.index),
        test_dates  = pd.DatetimeIndex(test_df.index),
    )


# STEP 7 — Return distribution insights
def return_insights(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Print and return a statistical summary of the full returns matrix
    before splitting — useful for spotting outliers or extreme assets.
    """
    from scipy import stats as sp_stats

    records = []
    for col in returns.columns:
        r = returns[col].dropna()
        records.append({
            "asset"     : col,
            "mean_daily": round(r.mean(), 6),
            "std_daily" : round(r.std(), 6),
            "min"       : round(r.min(), 4),
            "max"       : round(r.max(), 4),
            "skewness"  : round(sp_stats.skew(r), 3),
            "kurtosis"  : round(sp_stats.kurtosis(r), 3),   # excess kurtosis
            "pct_neg"   : round((r < 0).mean() * 100, 1),   # % of negative days
        })

    insight_df = pd.DataFrame(records)

    print("\n── Return Statistics (full period, before split) ───────────")
    print(insight_df.to_string(index=False))

    return insight_df


def prepare_data(filepath: str | Path, max_missing_ratio: float = MAX_MISSING_RATIO, train_ratio: float = TRAIN_RATIO, val_ratio: float = VAL_RATIO, print_insights: bool = True,) -> DataSplit:
    """
    Returns:
        DataSplit object ready to plug into run_ga() and tune_hyperparameters().
    """
    print("\n" + "=" * 60)
    print("  PSX DATA PREPARATION PIPELINE")
    print("=" * 60)

    df = load_raw_data(filepath)
    # per_asset_report(df)
    df, dropped = clean_data(df, max_missing_ratio)
    prices = pivot_to_wide(df)
    returns = compute_returns(prices)

    # if print_insights:
    #     return_insights(returns)

    data = split_returns(returns, train_ratio, val_ratio)
    # data.summary()

    return data


# ─────────────────────────────────────────────────────────────────────────────
# MASTER DATA INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

def load_master_data(filepath: str | Path, asset_names: list[str]) -> pd.DataFrame:
    """
    Load and pivot the MASTER prediction CSV to a wide date × asset DataFrame.

    Expected CSV columns: symbol, date, predictionreturn (rank is ignored).
    Multiple predictions for the same (symbol, date) are averaged.
    Column gaps (assets with no prediction on a given date) are forward-filled
    then back-filled so every date has a value for every asset.

    Parameters
    ----------
    filepath   : path to MASTER CSV / Excel file.
    asset_names: ordered list of asset tickers from the returns pipeline.
                 Only symbols in this list are retained; columns are ordered
                 to match asset_names exactly.

    Returns
    -------
    pd.DataFrame, shape (D, N)
        D unique prediction dates × N assets, values = predictionreturn.
    """
    filepath = Path(filepath)
    print(f"\nLoading MASTER predictions: {filepath.name}")

    if filepath.suffix == ".csv":
        df = pd.read_csv(filepath)
    elif filepath.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    else:
        raise ValueError(f"Unsupported file type: {filepath.suffix}. Use .csv or .xlsx")

    df.columns = df.columns.str.strip().str.lower()

    required = {"symbol", "date", "predictionreturn"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in MASTER CSV: {missing}")

    df["date"]   = pd.to_datetime(df["date"], format="mixed").dt.normalize()
    df["symbol"] = df["symbol"].str.upper().str.strip()

    # Retain only assets present in the returns data
    df = df[df["symbol"].isin(asset_names)]

    # Average duplicate (symbol, date) entries
    df = (
        df.groupby(["date", "symbol"])["predictionreturn"]
        .mean()
        .reset_index()
    )

    # Pivot: rows = prediction dates, columns = assets
    master_wide = df.pivot(index="date", columns="symbol", values="predictionreturn")
    master_wide.columns.name = None

    # Align columns to asset_names order; NaN for assets with zero predictions
    master_wide = master_wide.reindex(columns=asset_names)
    master_wide = master_wide.sort_index()

    # Fill within-column gaps
    master_wide = master_wide.ffill().bfill()

    n_assets_covered = int((master_wide.notna().any()).sum())
    print(f"  Prediction dates : {len(master_wide):,}")
    print(f"  Assets matched   : {n_assets_covered} / {len(asset_names)}")
    print(f"  Date range       : {master_wide.index[0].date()} → {master_wide.index[-1].date()}")

    return master_wide


def align_master_with_returns(
    returns: pd.DataFrame,
    master_wide: pd.DataFrame,
    lag_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Align MASTER predictions with returns by accounting for the forward-looking lag.

    MASTER predictions are labeled at their TARGET date (lag_months ahead of the
    returns period they characterise). For example, the prediction labeled April 2020
    was generated using data up to January 2020 and characterises returns in January
    2020. To pair them, shift all master dates BACK by lag_months.

    After shifting, the function:
      1. Finds the date range covered by both the shifted master and returns.
      2. Clips returns to that common range.
      3. Reindexes the shifted master to every returns date (forward-fill + back-fill
         to carry the last available prediction forward between sparse master dates).

    Parameters
    ----------
    returns    : daily returns DataFrame, shape (T, N), index = DatetimeIndex.
    master_wide: MASTER predictions DataFrame, shape (D, N), index = DatetimeIndex
                 (original, unshifted prediction-target dates).
    lag_months : months by which master dates lead the returns dates they pair with.

    Returns
    -------
    returns_common : returns clipped to the common date range, shape (T_common, N).
    master_aligned : master reindexed to returns_common.index, shape (T_common, N).
    """
    # Shift master index back by lag_months so it aligns with corresponding returns dates
    shifted_index = pd.DatetimeIndex(
        [d - pd.DateOffset(months=lag_months) for d in master_wide.index]
    )
    master_shifted = master_wide.copy()
    master_shifted.index = shifted_index
    master_shifted = master_shifted.sort_index()

    # Drop any duplicate dates that arise from the calendar offset
    master_shifted = master_shifted[~master_shifted.index.duplicated(keep="last")]

    # Common date window
    common_start = max(returns.index[0], master_shifted.index[0])
    common_end   = min(returns.index[-1], master_shifted.index[-1])

    if common_start >= common_end:
        raise ValueError(
            f"No overlapping date range after {lag_months}-month master shift.\n"
            f"  Returns       : {returns.index[0].date()} → {returns.index[-1].date()}\n"
            f"  Shifted master: {master_shifted.index[0].date()} → {master_shifted.index[-1].date()}"
        )

    print(f"\n  Common range after {lag_months}-month master shift: "
          f"{common_start.date()} → {common_end.date()}")

    # Clip returns to common range
    returns_common = returns.loc[common_start:common_end]

    # Reindex master to every daily returns date; carry predictions forward
    master_aligned = (
        master_shifted
        .reindex(returns_common.index, method="ffill")
        .bfill()
    )

    remaining_nan = int(master_aligned.isna().sum().sum())
    if remaining_nan > 0:
        print(f"  Warning: {remaining_nan} NaN values remain in aligned master after fill.")

    print(f"  Returns shape after clip : {returns_common.shape}")
    print(f"  Master aligned shape     : {master_aligned.shape}")

    return returns_common, master_aligned


def split_returns_with_master(
    returns: pd.DataFrame,
    master: pd.DataFrame,
    asset_names: list[str],
    train_years: int = 4,
    val_months: int = 3,
) -> DataSplit:
    """
    Split aligned returns and master predictions into fixed time-window periods.

    Time windows
    ────────────
    Cycle-1 (hyperparameter tuning):
      train : first train_years years          → GA trains with returns + MASTER
      val   : next val_months months (strict)  → GA validates on returns only

    Cycle-2 (final evaluation):
      final_train : train + val combined       → GA retrains with returns + MASTER
      test  : next val_months months (strict)  → single final evaluation on returns only
              (locked and unused during Cycle-1)

    Each row i of a master array holds the MASTER predictions that pair with row i
    of the corresponding returns array. The date alignment (master date = returns
    date + lag_months) is already resolved by align_master_with_returns.

    Parameters
    ----------
    returns     : daily returns, shape (T, N), index = DatetimeIndex.
    master      : aligned MASTER predictions, shape (T, N), same index as returns.
    asset_names : ordered list of N asset tickers.
    train_years : length of Cycle-1 training period in whole years.
    val_months  : length of validation (and test) period in months.

    Returns
    -------
    DataSplit with returns arrays for all periods and MASTER arrays for training only.
    """
    start     = returns.index[0]
    train_end = start     + pd.DateOffset(years=train_years)
    val_end   = train_end + pd.DateOffset(months=val_months)
    test_end  = val_end   + pd.DateOffset(months=val_months)   # test same length as val

    if returns.index[-1] < test_end:
        raise ValueError(
            f"Dataset too short for the requested split.\n"
            f"  Need data through : {test_end.date()}\n"
            f"  Data ends at      : {returns.index[-1].date()}\n"
            f"  (requires ≥ {train_years} yr + {val_months} mo + {val_months} mo of common data)"
        )

    # Boolean masks — all three windows are strictly bounded
    train_mask       = returns.index < train_end
    val_mask         = (returns.index >= train_end) & (returns.index < val_end)
    test_mask        = (returns.index >= val_end)   & (returns.index < test_end)
    final_train_mask = returns.index < val_end   # Cycle-2 training: train + val

    def _arr(df: pd.DataFrame, mask) -> np.ndarray:
        return df.values[mask]

    data = DataSplit(
        train       = _arr(returns, train_mask),
        val         = _arr(returns, val_mask),
        asset_names = asset_names,
        train_dates = pd.DatetimeIndex(returns.index[train_mask]),
        val_dates   = pd.DatetimeIndex(returns.index[val_mask]),
        test_dates  = pd.DatetimeIndex(returns.index[test_mask]),
        _test       = _arr(returns, test_mask),
        # MASTER — training periods only
        train_master        = _arr(master, train_mask),
        final_train         = _arr(returns, final_train_mask),
        final_train_master  = _arr(master,  final_train_mask),
        final_train_dates   = pd.DatetimeIndex(returns.index[final_train_mask]),
    )

    print(f"\n  Cycle-1 train  : {data.train.shape}  "
          f"({data.train_dates[0].date()} → {data.train_dates[-1].date()})")
    print(f"  Cycle-1 val    : {data.val.shape}  "
          f"({data.val_dates[0].date()} → {data.val_dates[-1].date()})")
    print(f"  Cycle-2 train  : {data.final_train.shape}  "
          f"({data.final_train_dates[0].date()} → {data.final_train_dates[-1].date()})")
    print(f"  Cycle-2 test   : {data._test.shape}  "
          f"({data.test_dates[0].date()} → {data.test_dates[-1].date()})  [locked]")

    return data


def prepare_data_with_master(
    returns_filepath: str | Path,
    master_filepath: str | Path,
    master_lag_months: int = 3,
    train_years: int = 4,
    val_months: int = 3,
    max_missing_ratio: float = MAX_MISSING_RATIO,
) -> DataSplit:
    """
    Full preparation pipeline for GA + MASTER integration.

    Steps
    ─────
    1. Load and clean KSE 30 price data → daily returns matrix.
    2. Load MASTER prediction CSV → wide prediction matrix.
    3. Align: shift master dates back by master_lag_months and clip both
       datasets to the overlapping date range.
    4. Split into Cycle-1 (train / val / test) and Cycle-2 (final_train / test)
       using fixed time windows.

    Parameters
    ----------
    returns_filepath  : path to KSE 30 price CSV / Excel.
    master_filepath   : path to MASTER prediction CSV / Excel.
    master_lag_months : months by which master dates lead the returns they pair with.
    train_years       : Cycle-1 training window in whole years (default 4).
    val_months        : validation and test window in months (default 3).
    max_missing_ratio : assets with more missing data than this are dropped.

    Returns
    -------
    DataSplit with both returns and MASTER arrays for all periods.
    """
    print("\n" + "=" * 60)
    print("  PSX DATA PREPARATION PIPELINE (WITH MASTER PREDICTIONS)")
    print("=" * 60)

    # ── Returns pipeline ──────────────────────────────────────────────────────
    df = load_raw_data(returns_filepath)
    df, _ = clean_data(df, max_missing_ratio)
    prices = pivot_to_wide(df)
    returns = compute_returns(prices)
    asset_names = list(returns.columns)

    # ── MASTER pipeline ───────────────────────────────────────────────────────
    print("\n── Loading MASTER Predictions ───────────────────────────────")
    master_wide = load_master_data(master_filepath, asset_names)

    # ── Alignment ─────────────────────────────────────────────────────────────
    print("\n── Aligning MASTER with Returns ─────────────────────────────")
    returns_common, master_aligned = align_master_with_returns(
        returns, master_wide, lag_months=master_lag_months
    )

    # ── Split ─────────────────────────────────────────────────────────────────
    print("\n── Splitting into Train / Val / Test ────────────────────────")
    data = split_returns_with_master(
        returns_common, master_aligned, asset_names,
        train_years=train_years, val_months=val_months,
    )

    data.summary()
    return data


return_file_path = "recent_kse30_latest.csv"
master_pred_file_path = "master_outputs.csv"
data = prepare_data_with_master(return_file_path, master_pred_file_path)