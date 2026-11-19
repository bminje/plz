# seoul-bus-route-graph

졸업논문 **「공공 교통 데이터 기반 노선-정류장 그래프를 활용한 서울시 시내버스 노선망 분석과 동대문구 학교 주변 정류장의 시간대별 이용 사례 연구」**
(박민재, 한국외국어대학교 컴퓨터공학부, 2027.02)의 분석 코드와 자료입니다.
이 저장소만 내려받으면 논문의 표·그림 수치를 처음부터 다시 계산하고, 논문에 적힌 값과 대조할 수 있습니다.

## 빠른 시작 (약 3분)

저장소 맨 위 폴더(이 README 가 있는 곳)에서 실행합니다. Windows 에서 `python` 이 안 되면 `py` 를 쓰세요.

```bash
pip install -r requirements.txt        # 처음 한 번 (Windows: py -m pip install -r requirements.txt)
python src/run_analysis.py             # 분석 전체 (약 1분, 메모리 약 0.5GB) → outputs/ 를 새로 씀
python src/make_pipeline_figure.py outputs/fig_s0_pipeline.png   # 논문 그림 1
python src/check_thesis.py             # 논문에 적힌 수치와 대조
```

마지막 명령이 아래처럼 끝나면 재현에 성공한 것입니다.

```
논문 수치 대조: 189개 항목 중 189개 일치
원자료 파일 확인 (SHA-256):
  [일치] bus_hourly_202610.csv
  [일치] bus_stops.xlsx
  [일치] signals.csv

결과: 논문에 적힌 수치와 모두 일치합니다.
```

저장소에 올려 둔 `outputs/` 를 그대로 두고 비교하려면 결과를 다른 폴더에 저장하세요.

```bash
python src/run_analysis.py --out-dir outputs_rerun
python src/check_thesis.py --out-dir outputs_rerun
```

## 논문의 표·그림은 어디서 나오나

| 논문 | 내용 | 값이 있는 곳 (`outputs/`) |
|---|---|---|
| 표 1 | 사용한 자료의 규모 | `stats.json` (`st_rows`, `h_rows`, `routes`, `stops`, `sg_rows`, `sg_gu`, `sg_dd`). 일별 승하차·교육통계 행은 `data/README.md` 참고 |
| 표 2 | 범주화 기준과 구분 결과 | `stats.json` (`hub_counts`, `len_cls`, `peak_cls`, `am_cls_seoul`), `seoul_stop_table.csv`, `seoul_route_table.csv` |
| 표 3 | 노선-정류장 그래프 지표 | `stats.json` (`routes`, `stops`, `pairs`, `transfer`, `P_edges`, `density`, `avg_deg`, `components`, `largest`) |
| 표 4 | 정류장 연결망 구조 지표 | `stats.json` 의 `L`, `Pspace` (L-space 간선은 `seoul_edges_lspace.csv`) |
| 표 5 | 교통수단별 피크 집중도 | `stats.json` (`mode_counts`, `peak_by_mode`) |
| 표 6, 7 | 동대문구 학교 지표 | `dongdaemun_school_metrics.csv`, `stats.json` (`by_level`, `top_am`, `low_am`) |
| 표 8, 10 | 순열·부트스트랩 검정 | `stat_tests.csv` (`stats.json` 의 `tests`), 공간 귀무모형 `pseudo`, 학교 단위 `school_level` |
| 표 9 | 대학별 지표 | `dongdaemun_university_metrics.csv`, `stats.json` 의 `univ` |
| 표 11 | 질의 예시와 결과 | `stats.json` 의 `queries` (Cypher 판은 `neo4j/queries.cypher`) |
| 그림 1 | 연구 절차 | `fig_s0_pipeline.png` (`src/make_pipeline_figure.py`) |
| 그림 2 | 정류장을 경유하는 노선 수 분포 | `fig_s1_hub.png` |
| 그림 3 | 정류장 연결망 차수 누적 분포 | `fig_s5_degree.png` |
| 그림 4 | 시간대별 하차·승차 비중 | `fig_s2_hourly.png` |
| 그림 5 | 학교 위치와 주변 정류장 | `fig_s3_map.png` |
| 그림 6 | 학교별 등교·하교 지수 | `fig_s4_schools.png` |

## 원자료

논문에 쓴 원자료 3개 파일(서울 열린데이터광장, 공공누리 1유형)이 `data/` 에 들어 있습니다.
내려받은 원본을 파일 이름만 바꾸어 두었으며, 출처·열 구성·SHA-256 은 `data/README.md` 에 적었습니다.
학교 26곳과 대학 5곳의 좌표는 저자가 지도에서 직접 확인해 입력했고 `inputs/` 에 있습니다.

## 결과가 논문과 다르게 나올 때

- `check_thesis.py` 는 개수·순위처럼 정해지는 값은 논문과 정확히 같아야 일치로 보고, 순열·부트스트랩·표본 근사처럼
  난수를 쓰는 값은 허용 오차 안이면 일치로 봅니다. 난수 시드는 2026 으로 고정되어 있습니다.
- 정수나 순위가 다르면 먼저 원자료 SHA-256 이 `[일치]` 인지 보세요. `[다름]` 이면 논문에 쓴 파일과 내용이 다른 자료입니다.
- 원자료가 같은데 확률적 값만 조금 다르면 라이브러리 버전 차이(난수 스트림, Louvain 커뮤니티 탐색 등)일 수 있습니다.
  아래의 테스트한 버전으로 맞추면 같은 값이 나옵니다.

## 테스트한 환경

- Linux, Python 3.13.18, numpy 2.5.3, pandas 3.0.5, scipy 1.18.1, networkx 3.7, openpyxl 3.1.5, matplotlib 3.11.2, pillow 12.3.0
  (같은 버전: `pip install -r requirements-tested.txt`)
- 이 환경에서 저장소를 새로 받아 처음부터 실행한 결과, `outputs/` 의 16개 파일이 저장소에 올린 파일과 바이트 단위로
  같았고 `check_thesis.py` 가 모두 일치로 끝났습니다. 소요 시간은 약 1분, 최대 메모리는 약 0.5GB 였습니다.
- Windows 와 macOS, 다른 버전의 파이썬·라이브러리에서는 직접 실행해 보지 못했습니다. 파이썬 문법은 3.11, 3.12 에서
  컴파일만 확인했습니다. 코드가 쓰는 CSV·JSON 은 모두 UTF-8 로 저장하고, 원자료 중 CSV 두 개는 CP949 로 읽습니다.

## 문제 해결

| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError` | `pip install -r requirements.txt` (Windows 는 `py -m pip install ...`) |
| `[입력 파일 없음] data/...` | `data/README.md` 를 보고 해당 이름으로 `data/` 에 두기 (다른 폴더면 `--data-dir`) |
| 그림의 한글이 네모(□)로 보임 | 한글 글꼴이 없는 경우입니다. 수치에는 영향이 없습니다. Windows(맑은 고딕)·macOS(AppleGothic)는 자동으로 쓰고, Linux 는 `fonts-nanum` 등을 설치한 뒤 다시 실행 |
| 메모리 부족 | 정류장 연결망(P-space) 계산에 약 0.5GB 가 필요합니다. 다른 프로그램을 닫고 다시 실행 |
| `check_thesis.py` 가 `stats.json` 이 없다고 함 | `run_analysis.py` 를 먼저 실행하고, 결과를 다른 폴더에 저장했다면 `--out-dir` 로 지정 |

## 폴더 구성

```
data/      원자료 3개 파일과 안내(README.md)
inputs/    저자가 직접 입력한 학교(26곳, 18개 부지)·대학(5곳) 좌표와 학생 수
src/       분석 코드. run_analysis.py 가 전체를 실행하고 check_thesis.py 가 논문 수치와 대조
outputs/   run_analysis.py 의 결과 (논문 표·그림의 수치, CSV, 그림 PNG)
neo4j/     (선택) Neo4j 용 CSV 와 Cypher. 실행·검증하지 못했음
```

## Neo4j (선택)

논문의 그래프 질의는 NetworkX 와 pandas 로 수행했고 그래프 데이터베이스는 쓰지 않았습니다(논문 2.3절).
`neo4j/` 의 CSV 와 Cypher 는 같은 그래프를 Neo4j 에 적재해 볼 수 있게 만든 선택 자료이며,
**논문 작성 환경에서는 Neo4j 를 실행하지 못해 이 파일들은 실행·검증되지 않았습니다.** 사용법과 기대값은 `neo4j/README.md` 에 있습니다.

## 라이선스와 출처

- 코드: MIT (`LICENSE`)
- 원자료: 서울특별시, 서울 열린데이터광장 (공공누리 1유형: 출처표시, 상업적 이용 및 변경 가능). 데이터셋 이름과 주소는 `data/README.md`
- 학교 이름과 학생 수: 한국교육개발원 교육통계서비스(https://kess.kedi.re.kr) 「2026년 유·초·중등 교육통계 학교별 주요 현황」 (조사기준일 2026.4.1)
