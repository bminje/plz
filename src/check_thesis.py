"""논문에 적힌 수치와 재계산 결과(outputs/stats.json 등)를 대조한다.

사용법 (저장소 맨 위 폴더에서):
    python src/run_analysis.py                      # 먼저 재계산 (약 1분)
    python src/check_thesis.py                      # 논문 수치와 대조
    python src/check_thesis.py --out-dir outputs_rerun --data-dir data

- 개수, 순위, 거리처럼 결정적인 값은 논문과 정확히 같아야 한다(표시 자릿수 기준).
- 순열·부트스트랩·표본 근사처럼 난수를 쓰는 값은 허용 오차 안이면 일치로 본다.
  (같은 파이썬·라이브러리 버전이면 보통 완전히 같은 값이 나온다. README 의 '테스트한 환경' 참조.)
- 원자료 파일의 SHA-256 도 함께 확인한다. 다른 버전의 자료를 쓰면 값이 달라질 수 있다는 경고이다.
종료 코드: 0 = 전부 일치, 1 = 일치하지 않는 항목이 있음.

확인 대상은 초록, 2~3장 본문, 표 1~11 중 코드가 직접 계산한 핵심 수치이다(189개 항목).
선택 사항: 일별 승하차 파일(data/BUS_STATION_BOARDING_MONTH_202610.csv, 약 140MB)을 내려받아 두면
표 1·2.2절의 일별 자료 수치(1,233,359행, 10월 27일 누락, 월 합계 검증)도 함께 확인한다.
교육통계 학교 수(2,098)는 코드가 읽지 않는 자료라 data/README.md 의 방법으로 직접 확인한다.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

import pandas as pd

# 논문 작성에 쓴 원자료의 SHA-256 (data/README.md 와 같은 값)
EXPECTED_SHA256 = {
    "bus_hourly_202610.csv": "e5348cbcdfbe3fd33607bcc9b1fb9c92cbc2fa01b4f4ac171f3d46838ced8048",
    "bus_stops.xlsx": "73eb0a5f4fd0f6128237b5e23fa361fd1c6d8a31a83bcee2884e6a48481852bb",
    "signals.csv": "1df0135493dcc9450b2ffe270caeb4d15c0a16d120f5fea82b3111ceaba592e7",
}


class Report:
    def __init__(self, verbose):
        self.verbose = verbose
        self.n = 0
        self.bad = []
        self.approx = 0

    def add(self, where, what, thesis, actual, nd=None, tol=None):
        """thesis: 논문에 적힌 값, actual: 재계산 값.
        nd  : 논문이 표시한 소수 자릿수(반올림해서 비교). 정수·문자열은 None.
        tol : 난수를 쓰는 값의 허용 오차(절대값). 지정하면 |actual-thesis| <= tol 이면 일치."""
        self.n += 1
        try:
            if tol is not None:
                ok = abs(float(actual) - float(thesis)) <= tol + 1e-12
                if nd is not None:
                    exact = round(float(actual), nd) == round(float(thesis), nd)
                else:
                    exact = float(actual) == float(thesis)
            elif nd is not None:
                ok = exact = round(float(actual), nd) == round(float(thesis), nd)
            else:
                ok = exact = actual == thesis
        except (TypeError, ValueError):
            ok = exact = False
        if ok and tol is not None and not exact:
            self.approx += 1
        mark = "OK  " if ok else "다름"
        if ok and tol is not None and not exact:
            mark = "OK~ "  # 허용 오차 안에서 일치
        if not ok:
            self.bad.append((where, what, thesis, actual))
        if self.verbose or not ok:
            shown = actual if nd is None or not isinstance(actual, float) else round(actual, nd + 2)
            print(f"[{mark}] {where:<10} {what:<46} 논문 {thesis!s:<14} 재계산 {shown}")


def pct(x, nd=1):
    return round(100.0 * x, nd)


def check_hashes(data_dir, rep_lines):
    if not os.path.isdir(data_dir):
        rep_lines.append(f"  (참고) '{data_dir}' 폴더가 없어 원자료 해시 확인은 건너뜀")
        return True
    all_ok = True
    for name, want in EXPECTED_SHA256.items():
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            rep_lines.append(f"  [없음] {name}: data/README.md 를 보고 이 이름으로 data 폴더에 두세요")
            all_ok = False
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() == want:
            rep_lines.append(f"  [일치] {name}")
        else:
            rep_lines.append(f"  [다름] {name}: 논문에 쓴 파일과 내용이 다릅니다(다른 시점·다른 방식으로 내려받은 파일일 수 있음). "
                             f"이 경우 일부 수치가 논문과 다를 수 있습니다.")
            all_ok = False
    return all_ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="outputs", help="run_analysis.py 결과 폴더 (기본 outputs)")
    ap.add_argument("--data-dir", default="data", help="원자료 폴더 (기본 data)")
    ap.add_argument("--daily", default=None,
                    help="일별 승하차 파일 경로 (기본: data/BUS_STATION_BOARDING_MONTH_202610.csv, 있을 때만 확인)")
    ap.add_argument("-v", "--verbose", action="store_true", help="일치하는 항목도 모두 출력")
    a = ap.parse_args()

    sj = os.path.join(a.out_dir, "stats.json")
    if not os.path.exists(sj):
        sys.exit(f"[오류] {sj} 가 없습니다. 먼저 'python src/run_analysis.py' 를 실행하세요.\n"
                 f"(다른 폴더에 저장했다면 --out-dir 로 지정)")
    try:
        S = json.load(open(sj, encoding="utf-8"))
    except UnicodeDecodeError:  # 예전 버전 코드가 윈도우 기본 인코딩(cp949)으로 저장한 경우
        S = json.load(open(sj, encoding="cp949"))
    T = {}
    for i, t in enumerate(S["tests"]):
        T[i] = t
    sm = pd.read_csv(os.path.join(a.out_dir, "dongdaemun_school_metrics.csv"))
    R = Report(a.verbose)
    add = R.add

    # ---------------------------------------------------------------- 표 1, 2.2절 (자료 규모, 좌표 연결)
    add("표 1", "정류소 위치 파일 행 수(선착장 8곳 포함)", 11236, S["st_rows"] + 8)
    add("표 1", "시간대별 승하차 파일 행 수", 42782, S["h_rows"])
    add("표 1", "노선 수", 666, S["routes"])
    add("표 1", "정류장 수", 12529, S["stops"])
    add("표 1", "신호등 파일 행 수", 65001, S["sg_rows"])
    add("표 1", "신호등 파일의 구 수", 18, S["sg_gu"])
    add("표 1", "신호등 파일의 동대문구 행 수", 3457, S["sg_dd"])
    m = S["match"]
    add("2.2절", "ID 로 좌표를 붙인 정류장", 10656, m["by_method"]["id"])
    add("2.2절", "ID 일치 비율(%)", 85.1, pct(m["by_method"]["id"] / S["stops"]), nd=1)
    add("2.2절", "좌표를 못 붙인 정류장", 1873, m["by_method"]["none"])
    add("2.2절", "그중 서울 밖으로 보이는 ID", 1734, m["unmatched_by_kind"]["outside_seoul_id"])
    add("2.2절", "그중 가상 정류장", 126, m["unmatched_by_kind"]["virtual"])
    add("2.2절", "그중 서울 범위 ID 인데 위치 파일에 없는 것", 13, m["unmatched_by_kind"]["seoul_unmatched"])
    add("2.2절", "승객 수 기준 미연결 비중(%)", 4.8, pct(m["rid_share_unmatched"]), nd=1)
    add("2.2절", "승객 수 기준 서울 밖 비중(%)", 4.5, pct(m["rid_share_by_kind"]["outside_seoul_id"]), nd=1)
    add("2.2절", "승객 수 기준 가상 정류장 비중(%)", 0.2, pct(m["rid_share_by_kind"]["virtual"]), nd=1)
    add("2.2절", "승객 수 기준 서울 범위 미연결 비중(%)", 0.03, pct(m["rid_share_by_kind"]["seoul_unmatched"], 2), nd=2)
    add("2.2절", "신호등 좌표 변환 확인: 최근접 정류장 거리 중앙값(m)", 63, S["sg_to_stop_median_m"], nd=0, tol=3)
    add("2.2절", "신호 지점 수(약 10m 격자)", 23200, S["sg_points"])
    add("2.2절", "월 승차 합계(백만)", 150.5, round(S["board_total"] / 1e6, 1), nd=1)

    # ---------------------------------------------------------------- 표 2 (범주화)
    hc = S["hub_counts"]
    for k, v in (("단일", 5376), ("소형", 2120), ("중형", 4358), ("대형", 675)):
        add("표 2", f"정류장 허브 등급 {k}", v, hc[k])
    lc = S["len_cls"]
    for k, v in (("짧음", 222), ("보통", 223), ("김", 221)):
        add("표 2", f"노선 길이 등급 {k}", v, lc[k])
    add("표 2", "노선 길이 3분위 경계(정류장 수)", (34, 75), tuple(round(q) for q in S["route_stops_q"]))
    pc = S["peak_cls"]
    for k, v in (("분산형", 218), ("보통", 217), ("집중형", 217), ("심야", 14)):
        add("표 2", f"노선 피크 집중도 {k}", v, pc[k])
    add("표 2", "피크 집중도 3분위 경계", (0.289, 0.314), tuple(round(q, 3) for q in S["peak_q"]))
    ac = S["am_cls_seoul"]
    for k, v in (("도착형", 4322), ("출발형", 5355), ("균형형", 2339), ("저이용", 513)):
        add("표 2", f"정류장 아침 흐름형 {k}", v, ac[k])

    # ---------------------------------------------------------------- 표 3 (그래프 주요 지표)
    add("표 3", "노드 수(노선+정류장)", 13195, S["routes"] + S["stops"])
    add("표 3", "경유 관계 수", 39340, S["pairs"])
    add("표 3", "환승 정류장 수", 7153, S["transfer"])
    add("표 3", "환승 정류장 비율(%)", 57.1, pct(S["transfer"] / S["stops"]), nd=1)
    add("표 3", "대형 허브(노선 10개 이상)", 675, hc["대형"])
    add("표 3", "한 정류장을 지나는 최대 노선 수", 28, S["max_hub"])
    add("표 3", "정류장당 평균 노선 수", 3.14, S["mean_routes_per_stop"], nd=2)
    add("표 3", "C-space 간선 수", 15220, S["P_edges"])
    add("표 3", "C-space 밀도", 0.069, S["density"], nd=3)
    add("표 3", "노선당 평균 연결 노선 수", 45.7, S["avg_deg"], nd=1)
    add("표 3", "연결 요소 수", 7, S["components"])
    add("표 3", "최대 연결 요소의 노선 수", 658, S["largest"])
    add("3.1.1", "허브 1위 정류장", "홍대입구역", S["top_hubs"][0][1])
    for i, (nm, n) in enumerate((("홍대입구역", 28), ("명동.롯데영플라자", 26), ("서울성심병원", 25))):
        add("3.1.1", f"허브 {i + 1}위 노선 수 ({nm})", n, S["top_hubs"][i][2])
    add("3.1.1", "C-space 평균 거리", 2.38, S["C_apl"], nd=2)
    add("3.1.1", "C-space 지름", 6, S["C_diam"])
    add("3.1.1", "C-space 평균 군집 계수", 0.583, S["avg_clust"], nd=3)
    add("3.1.1", "매개 중심성 1위 노선", "N51", S["top_btw"][0][0])
    add("3.1.1", "그 값", 0.040, S["top_btw"][0][1], nd=3, tol=0.004)
    add("3.1.1", "그 노선의 정류장 수 / 연결 노선 수", (162, 207), (S["top_btw"][0][2], S["top_btw"][0][3]))

    # ---------------------------------------------------------------- 표 4, 3.1.2절 (정류장 연결망)
    L, P = S["L"], S["Pspace"]
    add("표 4", "L-space 정류장 수", 12529, L["n"])
    add("표 4", "L-space 평균 차수", 2.69, L["k_mean"], nd=2)
    add("표 4", "L-space 최대 차수", 13, L["k_max"])
    add("표 4", "L-space 차수 3 이하 비율(%)", 80.5, pct(L["share_deg_le3"]), nd=1)
    add("표 4", "L-space 꼬리 멱함수 지수 γ", 6.1, L["powerlaw"]["alpha"], nd=1)
    add("표 4", "L-space 우도비 검정 p", 0.11, L["powerlaw"]["vuong_p"], nd=2)
    add("표 4", "L-space 군집 계수", 0.027, L["clustering"], nd=3)
    add("표 4", "P-space 평균 차수", 189, round(P["k_mean"]))
    add("표 4", "P-space 군집 계수", 0.729, P["clustering"], nd=3)
    add("표 4", "P-space 꼬리 적합 KS 거리", 0.16, P["powerlaw"]["ks"], nd=2)
    add("표 4", "P-space: 지수 분포가 우세(우도비<0)", True, P["powerlaw"]["R"] < 0)
    add("표 4", "L-space 평균 경로 길이", 30.5, L["apl"], nd=1, tol=0.3)
    add("표 4", "L-space 평균 경로 / 무작위 망", 3.2, round(L["apl"] / L["apl_random"], 1), nd=1, tol=0.1)
    add("표 4", "작은 세상 지수 σ", 38.8, L["sigma"], nd=1, tol=1.0)
    add("표 4", "P-space 평균 거리", 3.02, P["apl"], nd=2, tol=0.03)
    add("표 4", "P-space 평균 환승", 2.02, P["transfers"], nd=2, tol=0.03)
    add("3.1.2", "P-space 연결되는 쌍 비율(%)", 98.8, pct(P["reach"]), nd=1, tol=0.3)
    add("3.1.2", "한 노선으로 직접 닿는 쌍(%)", 1.6, pct(P["frac_direct"]), nd=1, tol=0.2)
    add("3.1.2", "환승 1회 이내(%)", 24.7, pct(P["frac_le1_transfer"]), nd=1, tol=0.5)
    add("3.1.2", "환승 2회 이내(%)", 74.7, pct(P["frac_le2_transfer"]), nd=1, tol=0.5)
    add("표 4", "L-space 모듈성", 0.929, L["modularity"], nd=3, tol=0.005)
    add("표 4", "L-space 커뮤니티 수", 50, L["n_comm"], tol=3)
    add("3.1.2", "L-space 차수 상관", 0.34, L["assort"], nd=2)
    add("3.1.2", "P-space 차수 상관", 0.18, P["assort"], nd=2)
    add("3.1.2", "매개 중심성 1위 정류장(L-space)", "창덕궁.우리소리박물관", L["top_btw"][0][1])
    add("3.1.2", "매개 중심성 상위 5개 정류장의 차수 범위", (2, 6),
        (min(t[3] for t in L["top_btw"]), max(t[3] for t in L["top_btw"])))
    add("3.1.2", "매개 중심성–차수 순위상관", 0.52, L["rho_btw_deg"], nd=2, tol=0.03)
    add("3.1.2", "매개 중심성–경유 노선 수 순위상관", 0.49, L["rho_btw_routes"], nd=2, tol=0.03)

    # ---------------------------------------------------------------- 표 5, 3.2~3.3절
    mc = S["mode_counts"]
    for k, v in (("서울간선버스", 144), ("서울지선버스", 247), ("서울마을버스", 245), ("서울광역버스", 13), ("서울심야버스", 14)):
        add("표 5", f"노선 수 {k}", v, mc[k])
    pm = S["peak_by_mode"]
    for k, v in (("서울간선버스", 0.288), ("서울지선버스", 0.299), ("서울마을버스", 0.306), ("서울광역버스", 0.398)):
        add("표 5", f"피크 집중도 중앙값 {k}", v, pm[k], nd=3)
    add("3.2절", "서울 전체 7·8·17·18시 승차 비중(%)", 29.2, pct(S["peak_share_all"]), nd=1)
    add("3.2절", "승차 1위 노선", "143", S["top_routes_board"][0][0])
    add("3.2절", "그 승차 인원", 1160899, int(S["top_routes_board"][0][1]))
    add("3.2절", "상위 5개 노선 비중(%)", 3.4, pct(S["top5_share"]), nd=1)
    add("3.3절", "서울 전체 7~8시 하차 비중(%)", 13.4, pct(S["base_am_alight"]), nd=1)
    add("3.3절", "서울 전체 15~16시 승차 비중(%)", 13.1, pct(S["base_pm_board_1516"]), nd=1)

    # ---------------------------------------------------------------- 표 6, 7, 3.4.1~3.4.2, 3.4.4
    add("3.4절", "분석 대상 중학교 / 고등학교 수", (15, 11), (S["school_mid"], S["school_high"]))
    add("3.4절", "부지 수", 18, S["school_sites"])
    add("3.4.1", "최근접 정류장 거리 중앙값(m)", 150, S["nearest_med"], nd=0)
    add("3.4.1", "최근접 정류장 거리 평균(m)", 169, S["nearest_mean"], nd=0)
    add("3.4.1", "최근접 정류장 거리 최대(m)", 378, S["nearest_max"], nd=0)
    add("3.4.1", "100m / 200m / 300m 이내 학교 수", (4, 20, 23), (S["le100"], S["le200"], S["le300"]))
    add("3.4.1", "300m 이내 정류장이 없는 학교의 학생 수 합계", 1033, S["students_far"])
    for lv, (nm, near, st300, rt300, am, pmx) in {
            "중학교": ("표 6", 136, 6, 9, 1.21, 1.04), "고등학교": ("표 6", 153, 6, 9, 1.33, 1.22)}.items():
        b = S["by_level"][lv]
        add(nm, f"{lv} 학교 수 / 최근접 거리 / 300m 정류장 / 경유 노선",
            ((15 if lv == "중학교" else 11), near, st300, rt300),
            (b["n"], round(b["nearest"]), round(b["stops300"]), round(b["routes300"])))
        add(nm, f"{lv} 등교 지수 / 하교 지수 중앙값", (am, pmx), (round(b["am"], 2), round(b["pm"], 2)))
    # 대학(비교군) 행: 5곳의 중앙값 (지수는 300m 정류장이 없는 서울시립대 제외)
    U = pd.DataFrame(S["univ"])
    add("표 6", "대학 5곳 최근접 거리 중앙값(m)", 220, round(U["nearest_m"].median()))
    add("표 6", "대학 300m 이내 정류장 수 중앙값", 3, round(U["stops300"].median()))
    add("표 6", "대학 경유 노선 수 중앙값", 2, round(U["routes300"].median()))
    add("표 6", "대학 등교 지수 / 하교 지수 중앙값", (1.25, 1.38),
        (round(U["am300"].dropna().median(), 2), round(U["pm300"].dropna().median(), 2)))
    add("3.4.2", "지수 계산 대상 학교 중 등교 지수 > 1", 18, S["n_am_above"])
    add("3.4.2", "등교 지수 중앙값", 1.23, S["am_ratio_med"], nd=2)
    add("3.4.2", "등교 지수 범위", (0.58, 1.77), (round(S["am_ratio_min"], 2), round(S["am_ratio_max"], 2)))
    add("3.4.2", "하교 지수 중앙값", 1.06, S["pm_ratio_med"], nd=2)
    add("3.4.2", "학교 주변 정류장 / 다른 정류장 수", (78, 466), (S["adj_stops"], S["rest_stops"]))
    add("3.4.2", "7~8시 하차 비중 학교 주변 / 다른 정류장(%)", (16.2, 13.3), (pct(S["adj_am_alight"]), pct(S["rest_am_alight"])))
    add("3.4.2", "15~16시 승차 비중 학교 주변 / 다른 정류장(%)", (14.4, 13.0), (pct(S["adj_pm_board"]), pct(S["rest_pm_board"])))
    add("3.4.2", "학교 주변 정류장의 아침 흐름형 (도착/출발/균형)", (23, 27, 28),
        (S["adj_am_cls"]["도착형"], S["adj_am_cls"]["출발형"], S["adj_am_cls"]["균형형"]))
    ta = S["top_am"]
    for i, (nm, v) in enumerate((("경희여자고등학교", 1.77), ("경희여자중학교", 1.77), ("경희중학교", 1.74),
                                 ("해성국제컨벤션고등학교", 1.73), ("경희고등학교", 1.59))):
        add("표 7", f"등교 지수 상위 {i + 1}위 {nm}", (nm, v), (ta[i][0], round(ta[i][1], 2)))
    for i, (nm, v) in enumerate((("성일중학교", 0.58), ("대광중학교", 0.76), ("동대문중학교", 0.78))):
        add("표 7", f"등교 지수 하위 {i + 1}위 {nm}", (nm, v), (S["low_am"][i][0], round(S["low_am"][i][1], 2)))
    add("3.4.2", "7~8시 하차가 가장 많은 정류장(월 합계)", ("경희대의료원.경희여중고", 19152),
        (S["top_adj_am"][0][1], int(S["top_adj_am"][0][2])))
    add("3.4.4", "학교 200m 이내 신호 지점 중앙값", 8, S["sig200_med"], nd=0)
    add("3.4.4", "그중 차량 신호 지점 중앙값", 4.5, S["vehsig200_med"], nd=1)
    add("3.4.4", "차량 신호 지점이 없는 학교 수", 8, S["vehsig200_zero"])
    add("3.4.4", "정류장 50m 이내 차량 신호가 있는 정류장(학교당 평균)", 3.6, float(sm["stops_with_sig"].mean()), nd=1)

    # ---------------------------------------------------------------- 표 8 (학교 주변 vs 다른 정류장), 3.4.3절
    t = T[0]
    add("표 8", "7~8시 하차: 차이(%p)", 2.8, pct(t["diff"]), nd=1)
    add("표 8", "7~8시 하차: 95% 신뢰구간(%p)", (0.5, 5.0), (pct(t["ci_lo"]), pct(t["ci_hi"])))
    add("표 8", "7~8시 하차: 순열 p", 0.037, t["p_perm"], nd=3, tol=0.005)
    add("표 8", "7~8시 하차: Holm 보정 p", 0.074, t["p_holm"], nd=3, tol=0.01)
    add("3.4.3", "7~8시 하차: 맨-휘트니 p < 0.001", True, t["mw_p"] < 0.001)
    t = T[1]
    add("표 8", "15~16시 승차: 차이(%p)", 1.4, pct(t["diff"]), nd=1)
    add("표 8", "15~16시 승차: 95% 신뢰구간(%p)", (-0.2, 3.1), (pct(t["ci_lo"]), pct(t["ci_hi"])))
    add("표 8", "15~16시 승차: 순열 p", 0.044, t["p_perm"], nd=3, tol=0.005)
    add("표 8", "15~16시 승차: Holm 보정 p", 0.074, t["p_holm"], nd=3, tol=0.01)
    add("3.4.3", "15~16시 승차: 맨-휘트니 p < 0.001", True, t["mw_p"] < 0.001)
    ps = {p["key"]: p for p in S["pseudo"]}
    add("3.4.3", "공간 귀무모형 7~8시 하차 단측 p", 0.008, ps["alight_0708"]["p_one_sided"], nd=3, tol=0.005)
    add("3.4.3", "공간 귀무모형 15~16시 승차 단측 p", 0.062, ps["board_1516"]["p_one_sided"], nd=3, tol=0.012)
    add("3.4.3", "가상 학교 수", 18, S["n_pseudo_sites"])
    sl = S["school_level"]
    add("3.4.3", "학교 단위 등교 지수: 중앙값 / 1 초과 학교 / 대상", (1.23, 18, 23),
        (round(sl["am"]["median"], 2), sl["am"]["n_above1"], sl["am"]["n"]))
    add("3.4.3", "학교 단위 등교 지수 95% 신뢰구간", (1.17, 1.40), (round(sl["am"]["ci_lo"], 2), round(sl["am"]["ci_hi"], 2)))
    add("3.4.3", "학교 단위 등교 지수 윌콕슨 p", 0.003, sl["am"]["wilcoxon_p"], nd=3)
    add("3.4.3", "학교 단위 하교 지수: 중앙값 / 1 초과 학교", (1.06, 17), (round(sl["pm"]["median"], 2), sl["pm"]["n_above1"]))
    add("3.4.3", "학교 단위 하교 지수 95% 신뢰구간", (1.04, 1.22), (round(sl["pm"]["ci_lo"], 2), round(sl["pm"]["ci_hi"], 2)))
    add("3.4.3", "학교 단위 하교 지수 윌콕슨 p", 0.008, sl["pm"]["wilcoxon_p"], nd=3)

    # ---------------------------------------------------------------- 표 9, 10 (대학 비교군), 3.4.5절
    want = {"한국외대": (144, 12, 25, 0.81, 0.86, 1.12, 1.06), "경희대": (259, 1, 10, 1.65, 1.62, 1.64, 1.60),
            "서울시립대": (429, 0, 3, None, 0.92, None, 1.26), "삼육보건대": (220, 8, 17, 0.86, 1.06, 1.00, 1.03),
            "경희사이버대": (111, 3, 17, 1.78, 1.33, 1.64, 1.41)}
    for u in S["univ"]:
        w = want[u["univ"]]
        got = (round(u["nearest_m"]), u["stops300"], u["stops500"],
               None if u["am300"] != u["am300"] else round(u["am300"], 2), round(u["am500"], 2),
               None if u["pm300"] != u["pm300"] else round(u["pm300"], 2), round(u["pm500"], 2))
        add("표 9", f"{u['univ']}: 거리, 300m·500m 정류장, 등교 300m/500m, 하교 300m/500m", w, got)
    add("3.4.5", "대학 300m 이내 정류장(중복 제외)", 23, S["univ_all"])
    add("3.4.5", "그중 학교 주변과 겹치는 정류장", 10, S["univ_overlap_school_stops"])
    add("3.4.5", "학교 전용 / 대학 전용 정류장", (68, 13), (S["school_only_stops"], S["univ_only_stops"]))
    add("3.4.5", "하차 정점: 학교 전용 / 대학 전용 (시)", (8, 18), (S["sonly_peak_alight_hr"], S["uonly_peak_alight_hr"]))
    add("3.4.5", "승차 정점: 학교 전용 / 대학 전용 (시)", (8, 17), (S["sonly_peak_board_hr"], S["uonly_peak_board_hr"]))
    for i, (nm, a_, b_, d_, lo, hi, pp, ph) in enumerate((
            ("7~8시 하차", 15.2, 9.7, 5.5, 1.7, 8.4, 0.036, 0.071),
            ("9~11시 하차", 14.2, 15.2, -0.9, -4.3, 2.6, 0.654, 0.654),
            ("19~21시 승차", 10.2, 14.5, -4.3, -6.7, -1.4, 0.004, 0.012))):
        t = T[2 + i]
        add("표 10", f"{nm}: 학교 전용 / 대학 전용(%)", (a_, b_), (pct(t["share_a"]), pct(t["share_b"])))
        add("표 10", f"{nm}: 차이(%p) / 신뢰구간(%p)", (d_, lo, hi), (pct(t["diff"]), pct(t["ci_lo"]), pct(t["ci_hi"])))
        add("표 10", f"{nm}: 순열 p", pp, t["p_perm"], nd=3, tol=0.005)
        add("표 10", f"{nm}: Holm 보정 p", ph, t["p_holm"], nd=3, tol=0.01)

    # ---------------------------------------------------------------- 표 11, 3.5절 (질의)
    q = S["queries"]
    add("표 11", "질의 1: 노선 수 최다 정류장(그래프 = 표 집계)", ("113000422", 28), tuple(q["q1_graph"]))
    add("표 11", "질의 1: 표 집계와 일치", True, q["q1_graph"] == q["q1_table"])
    add("표 11", "질의 2: 노선 10개 이상 정류장(그래프)", 675, q["q2_graph"])
    add("표 11", "질의 2: 표 집계와 일치", True, q["q2_graph"] == q["q2_table"])
    add("표 11", "한국외대 300m 이내 출발 정류장 수", 12, q["q6_src"])
    add("표 11", "질의 3: 환승 없이 닿는 정류장(그래프)", 521, q["q6_graph_0"])
    add("표 11", "질의 3: 표(행렬 곱)와 일치", True, q["q6_graph_0"] == q["q6_table_0"])
    add("표 11", "질의 4: 환승 1회 이내(그래프)", 7314, q["q6_graph_1"])
    add("표 11", "질의 4: 표(행렬 곱)와 일치", True, q["q6_graph_1"] == q["q6_table_1"])
    add("3.5절", "환승 1회 이내 비율(%)", 58.4, pct(q["q6_graph_1"] / S["stops"]), nd=1)

    # ---------------------------------------------------------------- (선택) 일별 승하차 파일: 표 1, 2.2절 월 합계 검증
    daily = a.daily or os.path.join(a.data_dir, "BUS_STATION_BOARDING_MONTH_202610.csv")
    if os.path.exists(daily):
        d = pd.read_csv(daily, encoding="cp949", usecols=["사용일자", "승차총승객수"], dtype={"사용일자": str})
        per_day = d.groupby("사용일자")["승차총승객수"].sum()
        total = float(per_day.sum())
        add("표 1", "일별 승하차 파일 행 수", 1233359, len(d))
        add("표 1", "일별 파일의 날짜 수 / 10월 27일 누락", (30, True), (len(per_day), "20261027" not in per_day.index))
        add("2.2절", "일별 파일의 월 승차 합계(백만)", 145.0, round(total / 1e6, 1), nd=1)
        tue = [v for k, v in per_day.items() if datetime.date(int(k[:4]), int(k[4:6]), int(k[6:])).weekday() == 1]
        gap = S["board_total"] - total
        add("2.2절", "시간대별 합계와 일별 합계의 차이(백만) ≈ 누락일(화요일) 하루 승차(약 5.4백만)", True,
            abs(gap - sum(tue) / len(tue)) < 0.3e6)
    else:
        print(f"(선택) 일별 승하차 파일이 없어 표 1 의 일별 자료 행 확인은 건너뜀: {daily}")

    # ---------------------------------------------------------------- 결과 출력
    print(f"논문 수치 대조: {R.n}개 항목 중 {R.n - len(R.bad)}개 일치"
          + (f" (그중 {R.approx}개는 난수·표본 근사라 허용 오차 안에서 일치, 표시 'OK~')" if R.approx and a.verbose else ""))
    lines = []
    hash_ok = check_hashes(a.data_dir, lines)
    print("원자료 파일 확인 (SHA-256):")
    print("\n".join(lines))
    if R.bad:
        print(f"\n다른 값 {len(R.bad)}개 — 위의 '[다름]' 줄을 확인하세요.")
        if not hash_ok:
            print("원자료가 논문에 쓴 파일과 다르므로 일부 차이는 자료 때문일 수 있습니다.")
        else:
            print("정수·순위 값이 다르면 코드 또는 자료 문제, 확률적 값만 다르면 라이브러리 버전(난수 스트림) 차이일 가능성이 큽니다.")
        sys.exit(1)
    print("\n결과: 논문에 적힌 수치와 모두 일치합니다." if hash_ok else
          "\n결과: 논문의 수치와 모두 일치하지만, 원자료 파일이 논문에 쓴 파일과 다릅니다(위 안내 참고).")


if __name__ == "__main__":
    main()
