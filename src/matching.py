"""Attach coordinates to the stops of the hourly file.

Rule 1  : 표준버스정류장ID == NODE_ID                         -> "id"
Rule 2  : ARS number matches AND the normalised names agree   -> "ars_name"
Rule 3  : Seoul-range ID (starts with '1'), not a virtual stop, the normalised
          name is unique in the stop file                    -> "name_unique"
Unmatched stops are classified as virtual (가상) stops, stops whose ID is outside
the Seoul range, or other unmatched Seoul-range stops.
"""
import numpy as np
import pandas as pd

from common import norm_name


def _names_agree(a: str, b: str) -> bool:
    a, b = norm_name(a), norm_name(b)
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 3 and (a in b or b in a))


def match_stops(hstops: pd.DataFrame, st: pd.DataFrame):
    """hstops: one row per sid with columns sid, ars, name, rid (total riders).
    st: stop location file (sid, ars, 정류소명, lat, lon).
    Returns (table, report)."""
    t = hstops.copy()
    st = st.copy()
    st["ars0"] = st["ars"].str.lstrip("0")
    st["nn"] = st["정류소명"].map(norm_name)
    by_id = st.set_index("sid")
    by_ars = st[st.ars0 != ""].drop_duplicates("ars0").set_index("ars0")
    name_counts = st["nn"].value_counts()
    by_name = st.drop_duplicates("nn").set_index("nn")

    t["ars0"] = t["ars"].str.lstrip("0")
    t["lat"] = np.nan
    t["lon"] = np.nan
    t["method"] = ""
    for i, r in t.iterrows():
        if r.sid in by_id.index:
            t.at[i, "lat"], t.at[i, "lon"], t.at[i, "method"] = by_id.at[r.sid, "lat"], by_id.at[r.sid, "lon"], "id"
            continue
        if r.ars0 and r.ars0 in by_ars.index and _names_agree(r["name"], by_ars.at[r.ars0, "정류소명"]):
            t.at[i, "lat"], t.at[i, "lon"], t.at[i, "method"] = by_ars.at[r.ars0, "lat"], by_ars.at[r.ars0, "lon"], "ars_name"
            continue
        nn = norm_name(r["name"])
        if r.sid.startswith("1") and "(가상)" not in r["name"] and name_counts.get(nn, 0) == 1:
            t.at[i, "lat"], t.at[i, "lon"], t.at[i, "method"] = by_name.at[nn, "lat"], by_name.at[nn, "lon"], "name_unique"
    virt = t["name"].str.contains(r"\(가상\)") | t.sid.str.startswith("99")
    t["unmatched_kind"] = np.where(t.method != "", "", np.where(virt, "virtual", np.where(~t.sid.str.startswith("1"), "outside_seoul_id", "seoul_unmatched")))

    # ---- hold-out validation of rules 2 and 3 on stops that rule 1 matched
    ok = t[t.method == "id"]
    ars_only = ok[(ok.ars0 != "") & ok.ars0.isin(by_ars.index)]
    ars_only_hit = np.mean([by_ars.at[a, "sid"] == s for a, s in zip(ars_only.ars0, ars_only.sid)])
    ars_name = ars_only[[_names_agree(n, by_ars.at[a, "정류소명"]) for n, a in zip(ars_only["name"], ars_only.ars0)]]
    ars_name_hit = np.mean([by_ars.at[a, "sid"] == s for a, s in zip(ars_name.ars0, ars_name.sid)])
    uniq = ok[[name_counts.get(norm_name(n), 0) == 1 for n in ok["name"]]]
    name_hit = np.mean([by_name.at[norm_name(n), "sid"] == s for n, s in zip(uniq["name"], uniq.sid)])
    report = dict(
        n_total=len(t), by_method=t.method.replace("", "none").value_counts().to_dict(),
        unmatched_by_kind=t[t.method == ""].unmatched_kind.value_counts().to_dict(),
        rid_share_unmatched=float(t[t.method == ""].rid.sum() / t.rid.sum()),
        rid_share_by_kind={k: float(t[(t.method == "") & (t.unmatched_kind == k)].rid.sum() / t.rid.sum()) for k in ("virtual", "outside_seoul_id", "seoul_unmatched")},
        holdout=dict(ars_only_n=int(len(ars_only)), ars_only_precision=float(ars_only_hit),
                     ars_name_n=int(len(ars_name)), ars_name_precision=float(ars_name_hit),
                     name_unique_n=int(len(uniq)), name_unique_precision=float(name_hit)),
    )
    return t, report
