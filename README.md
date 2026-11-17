# seoul-bus-route-graph

서울시 시내버스 노선-정류장 그래프 분석과 동대문구 학교 주변 정류장의 시간대별 이용 분석 코드 (졸업논문 재현용).

## 실행
```bash
pip install -r requirements.txt
# data/README.md 의 안내대로 원자료를 내려받아 data/ 에 둔다 (원자료는 재배포하지 않음)
python3 -I src/run_analysis.py --data-dir data --inputs-dir inputs --out-dir outputs   # 약 1분
python3 src/make_pipeline_figure.py
```
난수 시드는 2026으로 고정되어 있다. 결과는 `outputs/stats.json`, CSV, `fig_s*.png`에 저장된다.

## 확인용 기대값 (논문과 같은 입력일 때)
- 노선 666개, 정류장 12,529개
- 경유 노선이 가장 많은 정류장: 홍대입구역 (28개 노선)
- 대형 허브(노선 10개 이상) 675개
- 한국외대 300m 정류장 12개에서 환승 없이 521개, 환승 1회 이내 7,314개 정류장에 도달

## 구성
- `src/` 분석 코드 (matching: 좌표 연결, network: L/P/C-space 지표, stat_tests: 순열·부트스트랩 검정)
- `inputs/` 저자가 지도에서 직접 확인해 입력한 학교·대학 좌표
- `neo4j/` Neo4j용 CSV와 Cypher (`import.cypher`, `queries.cypher`). **논문 작성 환경에서는 Neo4j를 실행하지 못해 이 파일들은 실행·검증되지 않았다.**

## 주의
신호등 좌표는 서울 열린데이터광장 OA-15546의 설명(EPSG:5186)에 따라 변환한다. 정류장의 약 15%는 좌표를 연결하지 못했으며(서울 밖·가상 정류장 위주) 분석 결과에 영향은 논문 2.2절에 적었다.

라이선스: MIT (코드). 원자료는 각 제공 기관의 이용 조건을 따른다.
