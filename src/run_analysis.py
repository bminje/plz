"""Full analysis pipeline: Seoul city bus route-stop graph and bus-stop usage around
schools / universities in Dongdaemun-gu.

    python src/run_analysis.py --data-dir data --inputs-dir inputs --out-dir outputs
"""
import argparse
import json
import os
import sys

import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import AL, BO, INPUT_FILES, load_hourly, load_stops, resolve  # noqa: E402
from geo import hav, tm_to_wgs  # noqa: E402
from matching import match_stops  # noqa: E402
from network import lspace_edges, lspace_metrics, pspace_metrics  # noqa: E402
import stat_tests as stt  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

for _n in ["Noto Sans CJK KR", "Noto Sans CJK JP", "NanumGothic", "Malgun Gothic", "AppleGothic"]:
    if _n in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.family"] = _n
        break
plt.rcParams["axes.unicode_minus"] = False

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default="data")
ap.add_argument("--inputs-dir", default="inputs")
ap.add_argument("--out-dir", default="outputs")
ap.add_argument("--seed", type=int, default=2026)
ap.add_argument("--n-perm", type=int, default=20000)
args = ap.parse_args()
OUT = args.out_dir.rstrip("/") + "/"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(args.seed)
S = {"seed": args.seed}

# ------------------------------------------------------------------ load
h = load_hourly(resolve(args.data_dir, "hourly"))
st = load_stops(resolve(args.data_dir, "stops"))
sg = pd.read_csv(resolve(args.data_dir, "signals"), encoding="cp949", dtype=str)
# Signal coordinates: EPSG:5186 (Korea 2000 / Central Belt 2010), as stated in the Seoul Open Data Plaza
# description of the signal dataset. Inverse transverse Mercator implemented in geo.py.
sg["lon"], sg["lat"] = tm_to_wgs(pd.to_numeric(sg["X좌표"]), pd.to_numeric(sg["Y좌표"]))
sc = pd.read_csv(os.path.join(args.inputs_dir, INPUT_FILES["schools"]), dtype=str, encoding="utf-8-sig")
sc = sc.rename(columns={"부지번호": "site", "학생수": "n"})
sc["n"] = pd.to_numeric(sc["n"])
sc["lat"] = pd.to_numeric(sc["위도"])
sc["lon"] = pd.to_numeric(sc["경도"])
un = pd.read_csv(os.path.join(args.inputs_dir, INPUT_FILES["universities"]), dtype=str, encoding="utf-8-sig")
un = un.rename(columns={"대학명": "univ"})
un["lat"] = pd.to_numeric(un["위도"])
un["lon"] = pd.to_numeric(un["경도"])
S.update(school_n=len(sc), school_sites=int(sc.site.nunique()), school_students=int(sc.n.sum()),
         school_mid=int((sc.학교급 == "중학교").sum()), school_high=int((sc.학교급 == "고등학교").sum()),
         sg_rows=len(sg), sg_gu=int(sg.시군구명.nunique()), sg_dd=int((sg.시군구명 == "동대문구").sum()), h_rows=len(h),
         st_rows=int(len(st)))

# ------------------------------------------------------------------ stop aggregates
stop_h = h.groupby("sid")[BO + AL].sum()
stop_h["board"] = stop_h[BO].sum(axis=1)
stop_h["alight"] = stop_h[AL].sum(axis=1)
pairs = h[["route", "sid"]].drop_duplicates()
S["routes"], S["stops"], S["pairs"] = int(pairs.route.nunique()), int(pairs.sid.nunique()), len(pairs)
rc = pairs.groupby("sid").route.nunique().rename("n_routes")

# ------------------------------------------------------------------ coordinate matching (rules 1-3)
hs = h.groupby("sid").agg(ars=("ars", "first"), name=("name", "first")).reset_index()
hs["rid"] = (stop_h.board + stop_h.alight).reindex(hs.sid).values
mt, mrep = match_stops(hs, st)
S["match"] = mrep
mt = mt.set_index("sid")
stop_name = st.set_index("sid")["정류소명"].reindex(mt.index).fillna(pd.Series(mt["name"]))
stop_tab = stop_h.join(rc).join(mt[["lat", "lon", "method", "unmatched_kind"]])
stop_tab["정류소명"] = stop_name
stop_tab["정류소타입"] = st.set_index("sid")["정류소타입"].reindex(stop_tab.index)
S["stops_with_xy"] = int(stop_tab.lat.notna().sum())
S["stops_by_id"] = int((stop_tab.method == "id").sum())
S["stops_virtual"] = int(mrep["unmatched_by_kind"].get("virtual", 0))
S["stops_outside"] = int(mrep["unmatched_by_kind"].get("outside_seoul_id", 0))
S["stops_seoul_unmatched"] = int(mrep["unmatched_by_kind"].get("seoul_unmatched", 0))
hub = lambda k: "단일" if k == 1 else ("소형" if k == 2 else ("중형" if k < 10 else "대형"))  # noqa: E731
stop_tab["hub"] = stop_tab.n_routes.map(hub)
S["hub_counts"] = stop_tab.hub.value_counts().to_dict()
S["transfer"] = int((stop_tab.n_routes >= 2).sum())
S["max_hub"] = int(stop_tab.n_routes.max())
S["top_hubs"] = [(str(i), str(r["정류소명"]), int(r["n_routes"])) for i, r in stop_tab.sort_values("n_routes", ascending=False).head(5).iterrows()]
S["mean_routes_per_stop"] = round(float(stop_tab.n_routes.mean()), 2)

# ------------------------------------------------------------------ route level
mode = h.groupby("route").교통수단타입명.agg(lambda s: s.value_counts().index[0])
rs = pairs.groupby("route").sid.nunique().rename("n_stops")
rh = h.groupby("route")[BO + AL].sum()
rh["board"] = rh[BO].sum(axis=1)
rh["alight"] = rh[AL].sum(axis=1)
rt = rh[["board", "alight"]].join(rs).join(mode.rename("mode"))
bo_arr = rh[BO].values
rt["peak_share"] = (bo_arr[:, [7, 8, 17, 18]].sum(axis=1)) / np.maximum(bo_arr.sum(axis=1), 1)
q = rt.n_stops.quantile([1 / 3, 2 / 3]).values
rt["len_cls"] = pd.cut(rt.n_stops, [0, q[0], q[1], 1e9], labels=["짧음", "보통", "김"])
S.update(route_stops_q=[round(float(x), 1) for x in q], route_stops_mean=round(float(rt.n_stops.mean()), 1),
         route_stops_med=float(rt.n_stops.median()), route_stops_max=int(rt.n_stops.max()),
         len_cls=rt.len_cls.value_counts().to_dict(), mode_counts=rt["mode"].value_counts().to_dict())
pq = rt[rt["mode"] != "서울심야버스"].peak_share.quantile([1 / 3, 2 / 3]).values
rt["peak_cls"] = np.where(rt["mode"] == "서울심야버스", "심야", np.where(rt.peak_share <= pq[0], "분산형", np.where(rt.peak_share <= pq[1], "보통", "집중형")))
S.update(peak_q=[round(float(x), 3) for x in pq], peak_cls=rt.peak_cls.value_counts().to_dict(),
         peak_by_mode=rt.groupby("mode").peak_share.median().round(3).to_dict(),
         peak_share_all=round(float(bo_arr[:, [7, 8, 17, 18]].sum() / bo_arr.sum()), 3),
         board_total=float(h[BO].sum().sum()), alight_total=float(h[AL].sum().sum()))
S["top_routes_board"] = [(r, int(v)) for r, v in rt.board.sort_values(ascending=False).head(5).items()]
S["top5_share"] = round(float(rt.board.sort_values(ascending=False).head(5).sum() / rt.board.sum()), 3)

# ------------------------------------------------------------------ graphs: C-space, L-space, P-space
rid = {r: i for i, r in enumerate(sorted(pairs.route.unique()))}
sidx = {s: i for i, s in enumerate(sorted(pairs.sid.unique()))}
B = sparse.csr_matrix((np.ones(len(pairs), dtype=np.float32), ([rid[r] for r in pairs.route], [sidx[s] for s in pairs.sid])), shape=(len(rid), len(sidx)))
W = (B @ B.T).tocoo()
G = nx.Graph()
G.add_nodes_from(rid.keys())
inv = {v: k for k, v in rid.items()}
for i, j, w in zip(W.row, W.col, W.data):
    if i < j:
        G.add_edge(inv[i], inv[j], weight=float(w))
n, e = G.number_of_nodes(), G.number_of_edges()
S.update(P_edges=e, density=round(2 * e / (n * (n - 1)), 4), avg_deg=round(2 * e / n, 1))
cc = sorted(nx.connected_components(G), key=len, reverse=True)
S.update(components=len(cc), largest=len(cc[0]), isolated=int(sum(1 for c in cc if len(c) == 1)))
btw = nx.betweenness_centrality(G)
top = sorted(btw.items(), key=lambda t: -t[1])[:5]
S["top_btw"] = [(r, round(v, 4), int(rt.n_stops.get(r, 0)), G.degree(r)) for r, v in top]
S["top_deg"] = [(r, d) for r, d in sorted(G.degree, key=lambda t: -t[1])[:3]]
S["avg_clust"] = round(nx.average_clustering(G), 3)
Gl = G.subgraph(cc[0])
S["C_apl"] = round(nx.average_shortest_path_length(Gl), 2)
S["C_diam"] = int(nx.diameter(Gl))
S["C_deg_max"] = int(max(d for _, d in G.degree))
rt["btw"] = pd.Series(btw)
rt["deg"] = pd.Series(dict(G.degree))

L_edges = lspace_edges(h)
GL = nx.Graph()
GL.add_nodes_from(pairs.sid.unique())
GL.add_edges_from(L_edges)
names = stop_tab["정류소명"].to_dict()
S["L"], degL = lspace_metrics(GL, names, rc.to_dict(), rng)
S["Pspace"], degP = pspace_metrics(B, rng)

# ------------------------------------------------------------------ stop morning flow class
am_b = stop_h[["7시승차총승객수", "8시승차총승객수"]].sum(axis=1)
am_a = stop_h[["7시하차총승객수", "8시하차총승객수"]].sum(axis=1)
net = (am_a - am_b) / (am_a + am_b).replace(0, np.nan)
stop_tab["am_net"] = net
stop_tab["am_cls"] = np.where(net > 0.2, "도착형", np.where(net < -0.2, "출발형", "균형형"))
stop_tab.loc[(am_a + am_b) < 50, "am_cls"] = "저이용"
S["am_cls_seoul"] = stop_tab.am_cls.value_counts().to_dict()
tot_b, tot_a = h[BO].sum().values, h[AL].sum().values
S["base_am_alight"] = round(float(tot_a[[7, 8]].sum() / tot_a.sum()), 4)
S["base_pm_board_1516"] = round(float(tot_b[[15, 16]].sum() / tot_b.sum()), 4)
S["base_pm_board_1718"] = round(float(tot_b[[17, 18]].sum() / tot_b.sum()), 4)
S["peak_hours_board"] = [int(np.argmax(tot_b)), int(np.argsort(-tot_b)[1])]

# ------------------------------------------------------------------ signals
sgd = sg.copy()
sgd["gx"] = (sgd.lon * 1e4).round().astype(int)
sgd["gy"] = (sgd.lat * 1e4).round().astype(int)  # ~10 m grid
sgd_pts = sgd.drop_duplicates(["gx", "gy"])
veh = sgd[sgd.신호등종류.isin(["3색등", "4색등", "3색등(종형)", "차량보조등3색", "버스전용3색등"])].drop_duplicates(["gx", "gy"])
S["sg_points"], S["sg_veh_points"] = len(sgd_pts), len(veh)
S["sg_types"] = sg.신호등종류.value_counts().head(10).to_dict()
# sanity check of the coordinate conversion: signal -> nearest stop distance
sx = stop_tab.dropna(subset=["lat"]).reset_index()
slat, slon = sx.lat.values, sx.lon.values
samp = sgd[sgd.시군구명 == "동대문구"].sample(500, random_state=1)
S["sg_to_stop_median_m"] = round(float(np.median([hav(r.lat, r.lon, slat, slon).min() for r in samp.itertuples()])), 1)

# ------------------------------------------------------------------ schools
rows, nearby_ids = [], {}
for r in sc.itertuples():
    d = hav(r.lat, r.lon, slat, slon)
    near = sx.sid.values[d <= 300]
    nearby_ids[r.학교명] = near
    s300 = stop_tab.loc[stop_tab.index.isin(near)]
    dsig = hav(r.lat, r.lon, sgd_pts.lat.values, sgd_pts.lon.values)
    dveh = hav(r.lat, r.lon, veh.lat.values, veh.lon.values)
    ra = pairs[pairs.sid.isin(near)].route.nunique()
    amA, alA = s300[["7시하차총승객수", "8시하차총승객수"]].sum().sum(), s300.alight.sum()
    pmB, alB = s300[["15시승차총승객수", "16시승차총승객수"]].sum().sum(), s300.board.sum()
    nst_sig = sum(1 for _, sr in s300.dropna(subset=["lat"]).iterrows() if hav(sr.lat, sr.lon, veh.lat.values, veh.lon.values).min() <= 50)
    rows.append(dict(site=r.site, school=r.학교명, level=r.학교급, students=r.n, lat=r.lat, lon=r.lon, nearest_m=float(d.min()),
                     stops300=int((d <= 300).sum()), stops500=int((d <= 500).sum()), routes300=int(ra), am_alight=float(amA),
                     am_alight_share=float(amA / alA) if alA else np.nan, pm_board_1516=float(pmB),
                     pm_share_1516=float(pmB / alB) if alB else np.nan, sig200=int((dsig <= 200).sum()), vehsig200=int((dveh <= 200).sum()),
                     stops_with_sig=nst_sig))
sch = pd.DataFrame(rows)
sch["am_ratio"] = sch.am_alight_share / S["base_am_alight"]
sch["pm_ratio"] = sch.pm_share_1516 / S["base_pm_board_1516"]
sch.to_csv(OUT + "dongdaemun_school_metrics.csv", index=False, encoding="utf-8-sig")
S.update(nearest_med=round(float(sch.nearest_m.median()), 0), nearest_mean=round(float(sch.nearest_m.mean()), 0), nearest_max=round(float(sch.nearest_m.max()), 0))
for k in (100, 200, 300):
    S[f"le{k}"] = int((sch.nearest_m <= k).sum())
S.update(stops300_med=float(sch.stops300.median()), stops300_min=int(sch.stops300.min()), stops300_max=int(sch.stops300.max()),
         routes300_med=float(sch.routes300.median()), routes300_max=int(sch.routes300.max()), routes300_min=int(sch.routes300.min()),
         am_ratio_med=round(float(sch.am_ratio.median()), 2), am_ratio_max=round(float(sch.am_ratio.max()), 2), am_ratio_min=round(float(sch.am_ratio.min()), 2),
         n_am_above=int((sch.am_ratio > 1).sum()), pm_ratio_med=round(float(sch.pm_ratio.median()), 2),
         sig200_med=float(sch.sig200.median()), vehsig200_med=float(sch.vehsig200.median()), vehsig200_zero=int((sch.vehsig200 == 0).sum()))
S["far_min"] = round(float(sch[sch.nearest_m > 300].nearest_m.min()), 0) if (sch.nearest_m > 300).any() else None
S["far_max"] = round(float(sch[sch.nearest_m > 300].nearest_m.max()), 0) if (sch.nearest_m > 300).any() else None
sch_mid, sch_hi = sch[sch.level == "중학교"], sch[sch.level == "고등학교"]
S["by_level"] = {k: dict(n=len(g), nearest=round(float(g.nearest_m.median()), 0), stops300=float(g.stops300.median()), routes300=float(g.routes300.median()),
                         am=round(float(g.am_ratio.median()), 2), pm=round(float(g.pm_ratio.median()), 2), vsig=float(g.vehsig200.median()))
                 for k, g in (("중학교", sch_mid), ("고등학교", sch_hi))}
S["top_am"] = [(r.school, round(r.am_ratio, 2), int(r.am_alight)) for r in sch.sort_values("am_ratio", ascending=False).head(5).itertuples()]
S["low_am"] = [(r.school, round(r.am_ratio, 2)) for r in sch.sort_values("am_ratio").head(3).itertuples()]
S["top_pm"] = [(r.school, round(r.pm_ratio, 2)) for r in sch.sort_values("pm_ratio", ascending=False).head(3).itertuples()]
S["corr_students_am"] = round(float(np.corrcoef(sch.students, sch.am_alight)[0, 1]), 2)
S["students_far"] = int(sch.loc[sch.nearest_m > 300, "students"].sum())

# school-adjacent vs rest-of-area stops
allnear = set(np.concatenate(list(nearby_ids.values())))
S["n_school_stops"] = len(allnear)
dd = sgd[sgd.시군구명 == "동대문구"]
box = (dd.lat.min(), dd.lat.max(), dd.lon.min(), dd.lon.max())
area = stop_tab.dropna(subset=["lat"])
area = area[(area.lat >= box[0]) & (area.lat <= box[1]) & (area.lon >= box[2]) & (area.lon <= box[3])]
adj, rest = area[area.index.isin(allnear)], area[~area.index.isin(allnear)]
S.update(area_stops=len(area), adj_stops=len(adj), rest_stops=len(rest))
prof = lambda df, cols: df[cols].sum().values / df[cols].sum().values.sum()  # noqa: E731
pa_adj, pa_rest, pb_adj, pb_rest = prof(adj, AL), prof(rest, AL), prof(adj, BO), prof(rest, BO)
tb, ta = np.array(tot_b) / np.sum(tot_b), np.array(tot_a) / np.sum(tot_a)
S.update(adj_am_alight=round(float(pa_adj[[7, 8]].sum()), 4), rest_am_alight=round(float(pa_rest[[7, 8]].sum()), 4),
         adj_pm_board=round(float(pb_adj[[15, 16]].sum()), 4), rest_pm_board=round(float(pb_rest[[15, 16]].sum()), 4),
         adj_mean_routes=round(float(adj.n_routes.mean()), 1), rest_mean_routes=round(float(rest.n_routes.mean()), 1),
         adj_am_cls=adj.am_cls.value_counts().to_dict(), adj_board=float(adj.board.sum()), adj_alight=float(adj.alight.sum()),
         adj_hub10=int((adj.n_routes >= 10).sum()))
S["top_adj_am"] = [(str(i), str(r["정류소명"]), int(r[["7시하차총승객수", "8시하차총승객수"]].sum()), int(r["n_routes"]))
                   for i, r in adj.assign(_a=adj[["7시하차총승객수", "8시하차총승객수"]].sum(axis=1)).sort_values("_a", ascending=False).head(5).iterrows()]

# ------------------------------------------------------------------ universities (comparison group)
SHORT = {"한국외국어대학교": "한국외대", "경희대학교": "경희대", "서울시립대학교": "서울시립대", "삼육보건대학교": "삼육보건대", "경희사이버대학교": "경희사이버대"}
urows, uids = [], {}
for r in un.itertuples():
    d = hav(r.lat, r.lon, slat, slon)
    near = sx.sid.values[d <= 300]
    uids[r.univ] = near
    s3 = stop_tab.loc[stop_tab.index.isin(near)]
    s5 = stop_tab.loc[stop_tab.index.isin(sx.sid.values[d <= 500])]
    dveh = hav(r.lat, r.lon, veh.lat.values, veh.lon.values)

    def idx(df):
        if len(df) == 0 or df.alight.sum() == 0:
            return (np.nan, np.nan)
        return (df[["7시하차총승객수", "8시하차총승객수"]].sum().sum() / df.alight.sum() / S["base_am_alight"],
                df[["15시승차총승객수", "16시승차총승객수"]].sum().sum() / df.board.sum() / S["base_pm_board_1516"])
    a3, p3 = idx(s3)
    a5, p5 = idx(s5)
    urows.append(dict(univ=SHORT.get(r.univ, r.univ), nearest_m=float(d.min()), stops300=int((d <= 300).sum()), stops500=int((d <= 500).sum()),
                      routes300=int(pairs[pairs.sid.isin(near)].route.nunique()), am300=a3, pm300=p3, am500=a5, pm500=p5,
                      vehsig200=int((dveh <= 200).sum()), am_alight300=float(s3[["7시하차총승객수", "8시하차총승객수"]].sum().sum())))
um = pd.DataFrame(urows)
um.to_csv(OUT + "dongdaemun_university_metrics.csv", index=False, encoding="utf-8-sig")
S["univ"] = urows
uall = set(np.concatenate(list(uids.values())))
S["univ_all"] = len(uall)
uadj = area[area.index.isin(uall)]
S["univ_stops"] = len(uadj)
S["univ_overlap_school_stops"] = len(uall & allnear)
S["univ_am_alight"] = round(float(prof(uadj, AL)[[7, 8]].sum()), 4)
S["univ_pm_board"] = round(float(prof(uadj, BO)[[15, 16]].sum()), 4)
S["univ_am_cls"] = uadj.am_cls.value_counts().to_dict()
S["univ_mean_routes"] = round(float(uadj.n_routes.mean()), 1)
prof_u_a, prof_u_b = prof(uadj, AL), prof(uadj, BO)
uonly = uadj[~uadj.index.isin(allnear)]
sonly = adj[~adj.index.isin(uall)]
S["univ_only_stops"], S["school_only_stops"] = len(uonly), len(sonly)
S["sonly_peak_alight_hr"], S["sonly_peak_board_hr"] = int(np.argmax(prof(sonly, AL))), int(np.argmax(prof(sonly, BO)))
S["uonly_peak_alight_hr"], S["uonly_peak_board_hr"] = int(np.argmax(prof(uonly, AL))), int(np.argmax(prof(uonly, BO)))
S["adj_peak_alight_hr"], S["univ_peak_alight_hr"] = int(np.argmax(pa_adj)), int(np.argmax(prof_u_a))
S["adj_peak_board_hr"], S["univ_peak_board_hr"] = int(np.argmax(pb_adj)), int(np.argmax(prof_u_b))
S["adj_alight_09_12"], S["univ_alight_09_12"] = round(float(pa_adj[9:12].sum()), 4), round(float(prof_u_a[9:12].sum()), 4)
S["adj_board_19_22"], S["univ_board_19_22"] = round(float(pb_adj[19:22].sum()), 4), round(float(prof_u_b[19:22].sum()), 4)

# ------------------------------------------------------------------ statistical tests
tests = []
t1 = stt.two_group(adj, rest, "alight_0708", rng, n_perm=args.n_perm)
t2 = stt.two_group(adj, rest, "board_1516", rng, n_perm=args.n_perm)
t3 = stt.two_group(sonly, uonly, "alight_0708", rng, n_perm=args.n_perm)
t4 = stt.two_group(sonly, uonly, "alight_0911", rng, n_perm=args.n_perm)
t5 = stt.two_group(sonly, uonly, "board_1921", rng, n_perm=args.n_perm)
labels = ["학교 주변 vs 다른 정류장, 7~8시 하차 비중", "학교 주변 vs 다른 정류장, 15~16시 승차 비중",
          "학교 전용 vs 대학 전용 정류장, 7~8시 하차 비중", "학교 전용 vs 대학 전용 정류장, 9~11시 하차 비중", "학교 전용 vs 대학 전용 정류장, 19~21시 승차 비중"]
res = [t1, t2, t3, t4, t5]
# Holm correction within each family of questions (A: school vs rest, B: university vs school)
adjA = stt.holm([r["p_perm"] for r in res[:2]])
adjB = stt.holm([r["p_perm"] for r in res[2:]])
for r, lab, ap_ in zip(res, labels, adjA + adjB):
    r["label"], r["p_holm"] = lab, ap_
S["tests"] = res
dist = np.array([hav(a, b, area.lat.values, area.lon.values) for a, b in zip(area.lat.values, area.lon.values)])
mask_obs = area.index.isin(allnear)
n_sites = int(sc.site.nunique())
S["pseudo"] = [stt.pseudo_school_test(area, dist, mask_obs, n_sites, k, rng, n_iter=5000) for k in ("alight_0708", "board_1516")]
S["school_level"] = dict(am=stt.school_level(sch.am_ratio.values, rng), pm=stt.school_level(sch.pm_ratio.values, rng))
S["n_pseudo_sites"] = n_sites

# ------------------------------------------------------------------ graph queries answered two ways (graph traversal vs table aggregation)
bip = nx.Graph()
bip.add_edges_from((("R", r), ("S", s)) for r, s in zip(pairs.route, pairs.sid))
qres = {}
# Q1 stop with most routes
deg_stop = {s: d for (k, s), d in bip.degree() if k == "S"}
g_top = max(deg_stop, key=deg_stop.get)
qres["q1_graph"] = (g_top, deg_stop[g_top])
qres["q1_table"] = (rc.idxmax(), int(rc.max()))
qres["q2_graph"] = sum(1 for d in deg_stop.values() if d >= 10)
qres["q2_table"] = int((rc >= 10).sum())
# Q6: multi-hop reachability from the stops within 300 m of HUFS
hufs_ids = list(uids["한국외국어대학교"])
json.dump([str(x) for x in hufs_ids], open(OUT + "hufs_stops.json", "w"))
src = [("S", s) for s in hufs_ids]
dist_g = nx.multi_source_dijkstra_path_length(bip, src, cutoff=4)
reach0 = {n_[1] for n_, d_ in dist_g.items() if n_[0] == "S" and d_ <= 2}   # one ride (no transfer)
reach1 = {n_[1] for n_, d_ in dist_g.items() if n_[0] == "S" and d_ <= 4}   # at most one transfer
sidx_inv = {v: k for k, v in sidx.items()}
v0 = np.zeros(len(sidx)); v0[[sidx[s] for s in hufs_ids]] = 1
r1 = (B @ v0) > 0
s1 = (B.T @ r1.astype(np.float32)) > 0
r2 = (B @ s1.astype(np.float32)) > 0
s2 = (B.T @ r2.astype(np.float32)) > 0
qres.update(q6_src=len(hufs_ids), q6_graph_0=len(reach0), q6_graph_1=len(reach1), q6_table_0=int(s1.sum()), q6_table_1=int(s2.sum()))
S["queries"] = qres

# ------------------------------------------------------------------ save tables
stop_tab.reset_index().to_csv(OUT + "seoul_stop_table.csv", index=False, encoding="utf-8-sig")
rt.reset_index().to_csv(OUT + "seoul_route_table.csv", index=False, encoding="utf-8-sig")
pairs.to_csv(OUT + "seoul_edges_route_stop.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(L_edges, columns=["sid_a", "sid_b"]).to_csv(OUT + "seoul_edges_lspace.csv", index=False, encoding="utf-8-sig")
sgd_pts[["시군구명", "lat", "lon", "신호등종류"]].query("시군구명=='동대문구'").to_csv(OUT + "dongdaemun_signal_points.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(S["tests"]).to_csv(OUT + "stat_tests.csv", index=False, encoding="utf-8-sig")

# ------------------------------------------------------------------ figures
C1, C2, C3 = "#1f77b4", "#d62728", "#7f7f7f"
cnt = stop_tab.n_routes.value_counts().sort_index()
fig, ax = plt.subplots(figsize=(6.6, 3.2))
xs = np.arange(1, 21)
ys = [int(cnt.get(i, 0)) for i in xs[:-1]] + [int((stop_tab.n_routes >= 20).sum())]
ax.bar(xs, ys, color=C1)
ax.set_yscale("log")
ax.set_xticks(xs)
ax.set_xticklabels([str(i) for i in xs[:-1]] + ["20+"], fontsize=8)
ax.set_xlabel("정류장을 경유하는 노선 수")
ax.set_ylabel("정류장 수(로그 눈금)")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig(OUT + "fig_s1_hub.png", dpi=200); plt.close()

hrs = np.arange(24)
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.1))
for ax, (a, b, t, u) in zip(axs, [(ta, pa_adj, "하차(도착)", prof_u_a), (tb, pb_adj, "승차(출발)", prof_u_b)]):
    ax.plot(hrs, a * 100, color=C3, lw=1.8, label="서울 전체")
    ax.plot(hrs, b * 100, color=C2, lw=1.8, label="학교 300m 이내 정류장")
    ax.plot(hrs, u * 100, color="#2ca02c", lw=1.8, ls="--", label="대학 300m 이내 정류장")
    ax.axvspan(6.5, 8.5, color="#f1c40f", alpha=.18)
    ax.axvspan(14.5, 16.5, color="#2ecc71", alpha=.15)
    ax.set_title(t, fontsize=10); ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("시간대(시)"); ax.spines[["top", "right"]].set_visible(False)
axs[0].set_ylabel("일 합계 대비 비중(%)")
axs[0].legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.0))
axs[0].set_ylim(0, 14)
plt.tight_layout(); plt.savefig(OUT + "fig_s2_hourly.png", dpi=200); plt.close()

fig, ax = plt.subplots(figsize=(6.0, 5.2))
dd_sig = sgd_pts[sgd_pts.시군구명 == "동대문구"]
ax.scatter(dd_sig.lon, dd_sig.lat, s=2, color="#c9c9c9", label="신호등 지점", zorder=1)
ax.scatter(area.lon, area.lat, s=5, color="#a6bddb", zorder=2)
sub = area[area.index.isin(allnear)].copy()
sub["am"] = sub[["7시하차총승객수", "8시하차총승객수"]].sum(axis=1)
sc_ = ax.scatter(sub.lon, sub.lat, s=10 + sub.am / sub.am.max() * 140, c=sub.am, cmap="OrRd", edgecolor="#555", linewidth=.3, zorder=3, label="학교 300m 이내 정류장")
for lv, g in sc.groupby("학교급"):
    ax.scatter(g.lon, g.lat, marker={"중학교": "s", "고등학교": "^"}[lv], s=60, color="#2c3e50", edgecolor="white", zorder=5, label=lv)
cb = plt.colorbar(sc_, ax=ax, fraction=.04, pad=.02)
cb.set_label("7~8시 하차 승객(월합계)", fontsize=8); cb.ax.tick_params(labelsize=7)
ax.ticklabel_format(axis="x", useOffset=False)
ax.set_xlabel("경도"); ax.set_ylabel("위도"); ax.legend(fontsize=7, loc="lower right", frameon=True)
ax.set_aspect(1 / np.cos(np.radians(37.58))); ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig(OUT + "fig_s3_map.png", dpi=200); plt.close()

g = sch.dropna(subset=["am_ratio"]).sort_values("am_ratio")
lab = [x.replace("동국대학교사범대학부속", "동국대사범대부속").replace("고등학교", "고교").replace("중학교", "중교") for x in g.school]
gu = um.dropna(subset=["am300"]).sort_values("am300")
labs = lab + [u + " (대학)" for u in gu.univ]
am_v, pm_v = list(g.am_ratio) + list(gu.am300), list(g.pm_ratio) + list(gu.pm300)
fig, ax = plt.subplots(figsize=(6.6, 5.2))
y = np.arange(len(labs))
b1 = ax.barh(y - .2, am_v, height=.38, color=C2, label="등교 시간대(7~8시) 하차 비중 지수")
b2 = ax.barh(y + .2, pm_v, height=.38, color=C1, label="하교 시간대(15~16시) 승차 비중 지수")
for i in range(len(lab), len(labs)):
    for b_ in (b1[i], b2[i]):
        b_.set_hatch("//"); b_.set_edgecolor("white")
ax.axvline(1, color="#333", lw=.8, ls="--"); ax.axhline(len(lab) - .5, color="#999", lw=.8)
ax.set_yticks(y); ax.set_yticklabels(labs, fontsize=7.2)
ax.set_xlabel("서울 전체 평균 대비 지수(1.0 = 평균)"); ax.legend(fontsize=7.5, frameon=False, loc="lower right"); ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig(OUT + "fig_s4_schools.png", dpi=200); plt.close()

# degree distributions (L-space and P-space) + betweenness vs degree
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
ukL = np.unique(degL[degL >= 1])
ccdfL = np.array([(degL >= k).mean() for k in ukL])
axs[0].loglog(ukL, ccdfL, "o", ms=4, color=C1)
pl = S["L"]["powerlaw"]
if pl:
    xx = np.arange(pl["xmin"], ukL.max() + 1)
    tail_frac = (degL >= pl["xmin"]).mean()
    from scipy.special import zeta
    axs[0].loglog(xx, tail_frac * zeta(pl["alpha"], xx) / zeta(pl["alpha"], pl["xmin"]), "-", color=C2, lw=1.4, label=f"멱함수 적합 (γ={pl['alpha']:.1f})")
    axs[0].legend(fontsize=7, frameon=False)
axs[0].set_xlabel("차수 k (연속한 정류장 연결)"); axs[0].set_ylabel("P(K ≥ k)"); axs[0].set_title("(a) L-space", fontsize=9.5)
ukP = np.unique(degP[degP >= 1])
axs[1].semilogy(ukP, [(degP >= k).mean() for k in ukP], ".", ms=3, color=C1)
axs[1].set_xlabel("차수 k (같은 노선으로 닿는 정류장 수)"); axs[1].set_title("(b) P-space", fontsize=9.5)
for ax in axs:
    ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig(OUT + "fig_s5_degree.png", dpi=200); plt.close()

json.dump(S, open(OUT + "stats.json", "w"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("done; stops with coordinates:", S["stops_with_xy"], "of", S["stops"])
