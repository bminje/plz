"""Network structure: L-space (consecutive stops), P-space (stops sharing a route),
C-space (routes sharing a stop) and the summary statistics used in the thesis."""
import itertools

import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse, stats
from scipy.sparse import csgraph
from scipy.special import zeta


def lspace_edges(h: pd.DataFrame):
    """Link stops that are consecutive along a route.

    One route variant = (노선번호, 노선명). Stops with the same sequence number
    (listed more than once) form one level; every stop of a level is linked to
    every stop of the next existing level."""
    edges = set()
    for _, g in h.dropna(subset=["seq"]).groupby(["route", "노선명"]):
        levels = g.sort_values("seq").groupby("seq").sid.agg(lambda s: sorted(set(s)))
        lv = list(levels.values)
        for a, b in zip(lv[:-1], lv[1:]):
            for u, v in itertools.product(a, b):
                if u != v:
                    edges.add((u, v) if u < v else (v, u))
    return sorted(edges)


def fit_powerlaw(x, min_tail=50):
    """Discrete power-law tail fit (Clauset et al. 2009 approximation) with KS-selected xmin,
    plus a likelihood-ratio comparison against a discrete exponential tail (Vuong test)."""
    x = np.asarray(x)
    x = x[x >= 1]
    best = None
    for xmin in sorted(set(x[x >= 1]))[:30]:
        tail = x[x >= xmin]
        if len(tail) < min_tail:
            break
        alpha = 1 + len(tail) / np.sum(np.log(tail / (xmin - 0.5)))
        ks_vals = np.arange(xmin, tail.max() + 1)
        pmf = ks_vals ** (-alpha) / zeta(alpha, xmin)
        cdf_m = 1 - np.cumsum(pmf) + pmf  # P(X >= k)
        emp = np.array([(tail >= k).mean() for k in ks_vals])
        ks = np.max(np.abs(emp - cdf_m))
        if best is None or ks < best["ks"]:
            best = dict(xmin=int(xmin), alpha=float(alpha), ks=float(ks), n_tail=int(len(tail)))
    if best is None:
        return None
    tail = x[x >= best["xmin"]]
    ll_pl = -best["alpha"] * np.log(tail) - np.log(zeta(best["alpha"], best["xmin"]))
    lam = np.log(1 + len(tail) / np.sum(tail - best["xmin"])) if np.sum(tail - best["xmin"]) > 0 else np.inf
    ll_ex = np.log(1 - np.exp(-lam)) + lam * best["xmin"] - lam * tail
    d = ll_pl - ll_ex
    R = float(d.sum())
    z = float(R / (np.sqrt(len(d)) * d.std())) if d.std() > 0 else np.nan
    best.update(lam=float(lam), R=R, vuong_p=float(2 * (1 - stats.norm.cdf(abs(z)))) if z == z else np.nan)
    return best


def _avg_path_sample(adj, n_src, rng):
    """Mean shortest-path length (hops) and the reachable fraction, from sampled sources."""
    n = adj.shape[0]
    src = rng.choice(n, size=min(n_src, n), replace=False)
    d = csgraph.shortest_path(adj, method="D", unweighted=True, directed=False, indices=src)
    fin = np.isfinite(d) & (d > 0)
    return float(d[fin].mean()), float(fin.sum() / (len(src) * (n - 1))), float(d[fin].max()), d


def lspace_metrics(G, stop_names, route_count, rng, k_btw=500):
    n, m = G.number_of_nodes(), G.number_of_edges()
    deg = np.array([d for _, d in G.degree()])
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    nodes = list(G.nodes())
    adj = nx.to_scipy_sparse_array(G, nodelist=nodes, format="csr")
    apl, reach, diam, _ = _avg_path_sample(adj, 1000, rng)
    C = nx.average_clustering(G)
    k_mean = 2 * m / n
    C_rand, L_rand = k_mean / n, np.log(n) / np.log(k_mean)
    btw = nx.betweenness_centrality(G, k=k_btw, seed=1)
    bser = pd.Series(btw)
    kser = pd.Series(dict(G.degree()))
    rser = pd.Series(route_count).reindex(bser.index)
    comm = nx.community.louvain_communities(G, seed=1)
    top_b = [(s, stop_names.get(s, s), round(float(v), 4), int(G.degree(s))) for s, v in bser.sort_values(ascending=False).head(5).items()]
    top_d = [(s, stop_names.get(s, s), int(d)) for s, d in sorted(G.degree(), key=lambda t: -t[1])[:5]]
    return dict(
        n=n, m=m, k_mean=round(k_mean, 2), k_max=int(deg.max()), k_med=float(np.median(deg)),
        share_deg_le3=float((deg <= 3).mean()), components=len(comps), largest=len(comps[0]),
        clustering=round(C, 3), clustering_random=round(C_rand, 5), apl=round(apl, 1), apl_random=round(L_rand, 1),
        diam_lb=int(diam), sigma=round((C / C_rand) / (apl / L_rand), 1), assort=round(nx.degree_assortativity_coefficient(G), 3),
        modularity=round(nx.community.modularity(G, comm), 3), n_comm=len(comm),
        btw_k=k_btw, top_btw=top_b, top_deg=top_d,
        rho_btw_deg=round(float(stats.spearmanr(bser, kser.reindex(bser.index))[0]), 2),
        rho_btw_routes=round(float(stats.spearmanr(bser, rser)[0]), 2),
        powerlaw=fit_powerlaw(deg), deg_counts={int(k): int(v) for k, v in pd.Series(deg).value_counts().sort_index().items()},
    ), deg


def pspace_metrics(B, rng):
    """B: routes x stops 0/1 sparse matrix. Stops are adjacent when a route serves both."""
    A = ((B.T @ B) > 0).astype(np.float32).tocsr()
    A.setdiag(0)
    A.eliminate_zeros()
    n = A.shape[0]
    deg = np.asarray(A.sum(axis=1)).ravel()
    m = int(A.nnz // 2)
    # exact local clustering, in row chunks: C_i = sum_j A_ij (A^2)_ij / (k_i (k_i - 1))
    clus = np.zeros(n)
    for s in range(0, n, 400):
        rows = A[s:s + 400]
        t = np.asarray((rows @ A).multiply(rows).sum(axis=1)).ravel()
        k = deg[s:s + 400]
        clus[s:s + 400] = np.where(k > 1, t / np.maximum(k * (k - 1), 1), 0)
    # degree assortativity (Newman 2003) from the sparse adjacency matrix
    k = deg.astype(float)
    s1, s2, s3 = float((k * (A @ k)).sum()), float((k ** 2).sum()), float((k ** 3).sum())
    twoM = float(k.sum())
    assort = (s1 / twoM - (s2 / twoM) ** 2) / (s3 / twoM - (s2 / twoM) ** 2)
    apl, reach, diam, dmat = _avg_path_sample(A, 500, rng)
    fin = np.isfinite(dmat) & (dmat > 0)
    rides = dmat[fin]
    return dict(
        n=n, m=m, k_mean=round(2 * m / n, 1), k_max=int(deg.max()), k_med=float(np.median(deg)),
        clustering=round(float(clus.mean()), 3), assort=round(float(assort), 3), apl=round(apl, 2), transfers=round(apl - 1, 2), reach=round(reach, 4),
        frac_direct=round(float((rides == 1).mean()), 3), frac_le1_transfer=round(float((rides <= 2).mean()), 3),
        frac_le2_transfer=round(float((rides <= 3).mean()), 3), diam_lb=int(diam),
        powerlaw=fit_powerlaw(deg.astype(int)), n_src=500,
    ), deg
