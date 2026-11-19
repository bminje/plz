"""Shared constants and loaders (see README for the expected input files)."""
import os
import re

import numpy as np
import pandas as pd

BO = [f"{i}시승차총승객수" if i > 0 else "00시승차총승객수" for i in range(24)]
AL = [f"{i}시하차총승객수" if i > 0 else "00시하차총승객수" for i in range(24)]

# File names expected inside --data-dir (rename your downloads to these names)
DATA_FILES = dict(hourly="bus_hourly_202610.csv", stops="bus_stops.xlsx", signals="signals.csv")
# Hand-entered coordinates, shipped with the repository
INPUT_FILES = dict(schools="schools_dongdaemun.csv", universities="universities_dongdaemun.csv")


def norm_name(s: str) -> str:
    """Normalise a stop name for comparison (drop sequence suffix, spaces and separators)."""
    s = re.sub(r"\(\d+\)\s*$", "", str(s))
    return re.sub(r"[\s.·,\-()]", "", s)


def load_hourly(path: str) -> pd.DataFrame:
    """Route x stop x hour boarding/alighting table (CP949).

    The trailing "(NNNNN)" of the 역명 column is the stop sequence of the route
    (checked on route 470: 1..87 along the route), which is used to build the L-space graph.
    """
    h = pd.read_csv(path, encoding="cp949", dtype=str)
    for c in h.columns[:6]:
        h[c] = h[c].str.strip()
    h[BO + AL] = h[BO + AL].apply(pd.to_numeric, errors="coerce").fillna(0)
    h = h.rename(columns={"표준버스정류장ID": "sid", "노선번호": "route", "버스정류장ARS번호": "ars"})
    h["seq"] = pd.to_numeric(h["역명"].str.extract(r"\((\d+)\)\s*$")[0], errors="coerce")
    h["name"] = h["역명"].str.replace(r"\(\d+\)\s*$", "", regex=True)
    return h


def load_stops(path: str) -> pd.DataFrame:
    st = pd.read_excel(path, dtype=str)
    st = st.rename(columns={"NODE_ID": "sid", "ARS_ID": "ars"})
    st["lon"] = pd.to_numeric(st["X좌표"])
    st["lat"] = pd.to_numeric(st["Y좌표"])
    st = st[st["정류소타입"] != "한강선착장"].drop_duplicates("sid")
    return st


def resolve(data_dir: str, key: str) -> str:
    path = os.path.join(data_dir, DATA_FILES[key])
    if not os.path.exists(path):
        raise SystemExit(
            f"[입력 파일 없음] {path}\n"
            f"  '{DATA_FILES[key]}' 파일을 data 폴더에 두어야 합니다. 자세한 내용은 data/README.md 를 보세요.\n"
            f"  (다른 폴더에 두었다면 --data-dir 로 지정)\n"
            f"  Input file not found: put '{DATA_FILES[key]}' into the data folder (see data/README.md).")
    return path
