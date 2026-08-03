# 시흥 청년 주거 지도

시흥시의 소형 민간 임대주택(오피스텔·연립다세대, 전용 20~39㎡) 가격과 청년 공공임대 공급을 같은 기준으로 비교하는 데이터 시각화 웹 프로젝트입니다.

> 현재 배포 화면은 **시연 데이터**입니다. 실제 결과라고 발표하거나 제출하지 말고, 아래 데이터 수집 단계를 완료한 뒤 `data/processed/dashboard.json`을 실제 정제본으로 교체해야 합니다.

## 화면과 해석 기준

- 민간 가격: 전월세 실거래가의 환산월세
- 공공 공급: 청년·대학생·청년계층 모집공고에 명시된 공급 호수
- 환산월세: `월세 + (보증금 × 연 전환율 ÷ 12)`
- 전환율: 화면에서 연 4%, 5%, 6% 선택 가능
- 분석 단위: 시흥시 및 동 단위
- 해석: 가격과 공급의 **동시점 패턴** 비교이며 인과관계나 수요를 단정하지 않음

## 폴더 구조

```text
app/                    FastAPI 서버
static/                 HTML, CSS, 동적 JavaScript 대시보드
data/raw/               원본 데이터 보관 (Git 제외)
data/templates/         공공임대 수기 정리 양식
data/processed/         배포에 포함할 정제 결과
scripts/                수집·정제 스크립트
.cloudtype/             Cloudtype 설정 예시
```

## 로컬 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다. 상태 확인 주소는 `http://127.0.0.1:8000/health`입니다.

### 네이버 지도 연결

Naver Cloud Maps에서 `Dynamic Map` Application을 만들고, Application key의 **Client ID**를 `.env`의 `NAVER_MAPS_KEY_ID`에 넣습니다. Cloudtype에서는 같은 이름의 환경변수에 Client ID를 넣습니다. Client Secret은 사용하거나 저장하지 않습니다. Application의 Web 서비스 URL에는 `http://localhost:8000`과 Cloudtype 배포 주소(경로·`#` 제외)를 등록합니다.

## 실제 데이터 수집 순서

1. 공공데이터포털에서 국토교통부 전월세 실거래가 API 활용신청 후 일반 인증키를 발급받습니다.
2. 터미널에서 키를 환경변수로 설정합니다. 키를 Git에 저장하지 않습니다.

```bash
export DATA_GO_KR_SERVICE_KEY='발급받은_일반_인증키'
python scripts/collect_private_rent.py --from 202508 --to 202607
```

3. 마이홈·LH·GH·시흥시의 청년 공공임대 공고를 확인하고 `data/templates/public_housing_template.csv` 양식으로 `data/raw/public_housing/public_housing.csv`를 만듭니다. 공고별 공급 호수를 중복 기입하지 않습니다.
4. 첫 API 수집본의 필드명과 동명·면적·계약일·보증금·월세를 검증합니다. API 응답의 필드가 바뀌었으면 `scripts/build_dashboard_data.py`의 필드 후보를 보정합니다.
5. `scripts/build_dashboard_data.py`를 실행해 `data/processed/dashboard_actual.json`을 만듭니다. 숫자·공고 수·동명을 검토한 뒤에만 이 파일을 `dashboard.json`으로 교체합니다.

## Cloudtype 배포

1. 이 폴더를 GitHub 저장소로 올립니다. `.env`, `data/raw/`는 올리지 않습니다.
2. Cloudtype에서 **Dockerfile** 템플릿을 선택하고 저장소를 연결합니다.
3. Dockerfile 경로는 `Dockerfile`, 서비스 포트는 `8000`으로 입력합니다.
4. 배포 후 `/health`가 `{ "status": "ok" }`를 반환하는지 확인합니다.

Cloudtype 무료 티어는 카드 등록이 필요하고, 하루 1회 중지 및 임시 디스크 초기화가 있습니다. 따라서 수집·저장은 로컬에서 하고, 배포 서버는 `data/processed/`의 읽기 전용 결과만 제공하도록 설계했습니다.

## 배포 전 확인 목록

- [ ] 화면의 `시연 모드` 배너가 실제 자료 교체 후 제거되었는가
- [ ] 모든 거래·공고 수치에 출처 URL이 있는가
- [ ] 환산월세 전환율과 단위(만원)가 표시되는가
- [ ] 공고 수·공급 호수와 경쟁률·신청자 수를 혼동하지 않았는가
- [ ] 원본 API 키·개인정보·원본 대용량 파일이 저장소에 없는가
- [ ] 모바일 화면과 외부 Cloudtype URL에서 필터·표·링크가 동작하는가
