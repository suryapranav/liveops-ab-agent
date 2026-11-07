"""Deterministic A/B analysis toolkit (step 1 of the LiveOps agent project)."""
from .bootstrap import BootstrapResult, bootstrap_diff_ci
from .data import ARMS, CONTROL, OUTCOME_METRICS, TREATMENT, arm_counts, load_cookie_cats
from .peeking import PeekingResult, simulate_aa_peeking
from .power import achieved_power, minimum_detectable_effect, required_sample_size
from .proportions import TwoProportionResult, two_proportion_ztest
from .srm import DEFAULT_SRM_ALPHA, SRMResult, srm_check
