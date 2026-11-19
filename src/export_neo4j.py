"""Export the route-stop graph as CSV files for Neo4j (LOAD CSV) -- optional.

NOTE: the author could not run Neo4j in the environment used to write the thesis, so the
Cypher in neo4j/*.cypher has NOT been executed. Compare your results with the
expected values printed in neo4j/README.md (computed with NetworkX and pandas).

    python src/export_neo4j.py --out-dir outputs --neo4j-dir neo4j
"""
import argparse
import json
import os

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--out-dir", default="outputs")
ap.add_argument("--neo4j-dir", default="neo4j")
a = ap.parse_args()
st = pd.read_csv(os.path.join(a.out_dir, "seoul_stop_table.csv"), dtype={"sid": str})
rt = pd.read_csv(os.path.join(a.out_dir, "seoul_route_table.csv"), dtype={"route": str})
pairs = pd.read_csv(os.path.join(a.out_dir, "seoul_edges_route_stop.csv"), dtype=str)
os.makedirs(a.neo4j_dir, exist_ok=True)
st[["sid", "정류소명", "lat", "lon", "n_routes"]].rename(columns={"정류소명": "name"}).to_csv(os.path.join(a.neo4j_dir, "stops.csv"), index=False)
rt[["route", "mode", "n_stops", "peak_share"]].to_csv(os.path.join(a.neo4j_dir, "routes.csv"), index=False)
pairs.to_csv(os.path.join(a.neo4j_dir, "passes.csv"), index=False)
import shutil
shutil.copy(os.path.join(a.out_dir, "hufs_stops.json"), os.path.join(a.neo4j_dir, "hufs_stops.json"))
S = json.load(open(os.path.join(a.out_dir, "stats.json"), encoding="utf-8"))
q = S["queries"]
print("expected:", q)
