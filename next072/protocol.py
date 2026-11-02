"""Frozen constants. Policy decisions cannot read unrevealed pair outcomes."""

EXPERIMENT_ID = "NEXT072-20261102"
SOURCE_COMMIT = "bfa6eeea2bd145a1af2ec0127a2e808cc38456a9"
SOURCE_PATH = "source_data/suppl-qqplot.xlsx"
SOURCE_BLOB = "f35c9efe3bf0f917068b2aaf2c2236b593c06e2c"
SOURCE_BYTES = 10905627
SOURCE_URL = (
    "https://raw.githubusercontent.com/const-ae/"
    "linear_perturbation_prediction-Paper/" + SOURCE_COMMIT + "/" + SOURCE_PATH
)
SPLIT_SALT = "NEXT072-K1-v1|"
REFERENCE_FRACTION = 0.25
REVEAL_FRACTION = 0.25
TARGET_FRACTION = 0.25
MIN_TARGET_RECALL = 0.5
PRIMARY_POLICY = "probability_of_hit"
HIT_THRESHOLD_QUANTILE = 0.75
HIT_DEVIATION_FLOOR = 1e-12
BATCH_SIZE = 4
KERNEL_RIDGE = 0.1
LINEAR_RIDGES = (0.01, 0.1, 1.0, 10.0)
TOLERANCE = 1e-10

POLICIES = (
    "probability_of_hit",
    "sequential_kernel",
    "ordinary_equal_content",
    "static_probability_of_hit",
    "static_kernel",
    "kernel_exploitation",
    "linear_ridge",
    "additive_magnitude",
    "diversity",
    "constant_features",
) + tuple(f"hash_{i:02d}" for i in range(32))
