"""Permutation / bootstrap tests at the stop level.

Outcome: pooled share  T(S) = sum_{i in S} num_i / sum_{i in S} den_i
(e.g. share of a stop set's alighting passengers that fall in 07-08h).
The headline numbers in the text (16.2% vs 13.3%) are such pooled shares, so the tests
use the same statistic and weight stops by their passengers.
"""
import numpy as np
from scipy import stats

from common import AL, BO

WINDOWS = {
    "alight_0708": (AL, [7, 8]),
    "alight_0911": (AL, [9, 10, 11]),
    "board_1516": (BO, [15, 16]),
    "board_1921": (BO, [19, 20, 21]),
}


def _arrays(df, key):
    cols, hrs = WINDOWS[key]
    num = df[[cols[h] for h in hrs]].sum(axis=1).to_numpy(float)
    den = df[cols].sum(axis=1).to_numpy(float)
    return num, den


def pooled(num, den):
    s = den.sum()
    return float(num.sum() / s) if s > 0 else np.nan


def holm(pvals):
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()


def two_group(df_a, df_b, key, rng, n_perm=20000, n_boot=20000):
    """Difference in pooled share (A - B): label-permutation p-value, bootstrap 95% CI,
    and a Mann-Whitney check on per-stop shares (stops with >= 500 passengers in the window base)."""
    na, da = _arrays(df_a, key)
    nb, db = _arrays(df_b, key)
    obs = pooled(na, da) - pooled(nb, db)
    num = np.concatenate([na, nb])
    den = np.concatenate([da, db])
    n_a = len(na)
    N = len(num)
    cnt = 0
    for _ in range(n_perm):
        idx = rng.permutation(N)
        ia, ib = idx[:n_a], idx[n_a:]
        t = pooled(num[ia], den[ia]) - pooled(num[ib], den[ib])
        cnt += abs(t) >= abs(obs) - 1e-15
    p_perm = (cnt + 1) / (n_perm + 1)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        ia = rng.integers(0, len(na), len(na))
        ib = rng.integers(0, len(nb), len(nb))
        boots[b] = pooled(na[ia], da[ia]) - pooled(nb[ib], db[ib])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    sa = (na / np.where(da > 0, da, np.nan))[da >= 500]
    sb = (nb / np.where(db > 0, db, np.nan))[db >= 500]
    mw = stats.mannwhitneyu(sa, sb, alternative="two-sided") if len(sa) > 2 and len(sb) > 2 else None
    return dict(key=key, share_a=pooled(na, da), share_b=pooled(nb, db), diff=float(obs), ci_lo=float(lo), ci_hi=float(hi),
                p_perm=float(p_perm), n_a=int(n_a), n_b=int(len(nb)), mw_p=float(mw.pvalue) if mw is not None else None,
                mw_n=(int(len(sa)), int(len(sb))))


def pseudo_school_test(area, dist_mat, obs_set_mask, n_sites, key, rng, n_iter=5000):
    """Spatial null: draw n_sites random 'pseudo-school' centres among the area's stops, take
    every stop within 300 m of a centre, and compare (centre-adjacent minus the rest) with the
    observed school-adjacent difference. Controls for the fact that stops near any place differ
    from stops elsewhere in the area."""
    num, den = _arrays(area, key)
    obs = pooled(num[obs_set_mask], den[obs_set_mask]) - pooled(num[~obs_set_mask], den[~obs_set_mask])
    near = dist_mat <= 300
    N = len(num)
    null = np.empty(n_iter)
    for i in range(n_iter):
        c = rng.choice(N, size=n_sites, replace=False)
        m = near[c].any(axis=0)
        null[i] = pooled(num[m], den[m]) - pooled(num[~m], den[~m])
    p = (np.sum(null >= obs) + 1) / (n_iter + 1)
    return dict(key=key, obs=float(obs), null_mean=float(null.mean()), null_lo=float(np.percentile(null, 2.5)),
                null_hi=float(np.percentile(null, 97.5)), p_one_sided=float(p), n_sites=int(n_sites), n_iter=int(n_iter))


def school_level(ratios, rng, n_boot=20000):
    """One-sample Wilcoxon signed-rank test of index == 1 and bootstrap CI of the median."""
    r = np.asarray([x for x in ratios if x == x], float)
    w = stats.wilcoxon(r - 1.0, alternative="two-sided")
    med = np.median(r)
    boots = np.array([np.median(rng.choice(r, len(r), replace=True)) for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return dict(n=int(len(r)), median=float(med), ci_lo=float(lo), ci_hi=float(hi), wilcoxon_p=float(w.pvalue),
                n_above1=int((r > 1).sum()))
