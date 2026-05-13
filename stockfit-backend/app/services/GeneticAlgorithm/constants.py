# ============================================================================================
# DATA PROCESSING CONSTANTS
# ============================================================================================
MAX_MISSING_RATIO = 0.10    # drop asset if fraction of trading days missing > this  [A3]
TRAIN_RATIO       = 0.60    # fraction of data used for GA training
VAL_RATIO         = 0.20    # fraction used for hyperparameter validation

START_DATE = "2016-01-01"

# ============================================================================================
# PORTOFOLIO EVALUATION CONSTANTS
# ============================================================================================

# Fitness function weights (Section 3.2.2, Equation 1)
ALPHA = 0.6   # weight on expected return
BETA  = 0.3   # weight on volatility
GAMMA = 0.2   # weight on skewness
DELTA = 0.1   # weight on kurtosis

# Penalty levels
MODERATE_PENALTY = 99      # applied when gene upper-bound constraint is violated
SEVERE_PENALTY   = 9999    # applied when maximum-investment-per-asset is violated

# Portfolio constraints
GENE_UPPER_BOUND = 0.7
MAX_WEIGHT = 0.40
MAX_ASSETS = 5
WEIGHT_DECIMALS = 4

# Blue chip bonus
BLUE_CHIP_BONUS = 0.02
APPLY_BLUE_CHIP = False
BLUE_CHIP_STOCKS = {
    "ATRL", "ENGROH", "FFC", "HUBC", "LUCK", "MARI",
    "MCB", "MEBL", "OGDC", "POL", "PPL", "SYS", "UBL", "HBL"
}

# ============================================================================================
# GA ITERATION CONSTANTS
# ============================================================================================

# Population
POP_SIZE   = 600       # number of individuals in the population (2o times assests)
N_PARENTS  = 125       # parents selected per generation (paper: 100–150)

# Tournament selection
TOURNAMENT_SIZE = 3    # individuals drawn per tournament (paper: "groups of three")

# BLX-α crossover
BLX_ALPHA = 0.5        # exploration parameter for BLX-α. (A common default. The paper does not specify the α value.)

# Mutation
GENE_MIN = 0.0
GENE_MAX = 1.0

# Hall of Fame
HOF_SIZE = 10          # number of best individuals to track. (The paper does not specify HOF capacity.)

# Number of generations to run
N_GENERATIONS =   30   # configurable; not fixed in this section of the paper

# Hyperparameters for GA Iteration
CXPB      = 0.9        # probability that a pair of parents undergoes crossover
MUTPB  = 0.9           # probability that an individual undergoes mutation
INDPB  = 0.15           # per-gene probability of being mutated (paper names this "indpb")