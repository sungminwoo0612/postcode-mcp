# postcode-mcp 📮

**한국 도로명주소 + 5자리 우편번호 + 상세주소 + 영문주소**를  
카카오/행안부(Juso) API를 조합해서 찾아주는 **주소 전용 MCP 서버**입니다.

- 입력: 장소명, 주소 문자열, 또는 카카오맵 place JSON
- 출력: `best` + `candidates` + `detail`(상세주소) + `english`(영문주소)를 포함한 JSON
- 사용처: PlayMCP, MCP Planner(예: ToolBartender)와 연계

> Planner MCP 예시는 [`toolbartender-mcp`](https://github.com/sungminwoo0612/toolbartender-mcp) 를 참고하세요.

---

## Keywords

`postcode`, `juso`, `kakao`, `korean address`, `PlayMCP`, `fastmcp`

---

## What it does

### 1) 기본 주소/우편번호 검색
- `resolve_postcode_auto` 도구를 통해:
  - **도로명주소 + 지번주소 + 5자리 우편번호(postcode5)** 반환
  - 후보(`candidates`)는 최대 N개 (`max_candidates`)까지 제공

### 2) 상세주소(detail) 조회 (행안부 addrDetailApi)
- best 후보에 포함된 코드 필드:
  - `admCd`, `rnMgtSn`, `udrtYn`, `buldMnnm`, `buldSlno`, `bdMgtSn`
- 이 값을 이용해 **상세주소(동/호 등)** 조회
- 응답: `detail = { common, items[] }`

### 3) 영문주소(english) 조회
- 별도의 행안부 **영문주소 API** 호출
- 응답을 내부 표준 스키마로 변환:
  - `road_addr`, `jibun_addr`, `postcode5`, `building_name`, detail keys 등
- 응답: `english = { common, best, candidates[] }`

### 4) Kakao place 연동
- Kakao place JSON (`road_address_name`, `address_name`, `place_name` 등)을 그대로 입력 가능
- 흐름:
  1. Kakao place가 있으면 `road_address_name` → 주소 검색 (전략 A)
  2. 없으면 `query` 문자열만으로 검색 (전략 B)
- `meta.strategy`:
  - `"A_kakao_then_juso"` 또는 `"B_juso_fallback"`

---

## Exposed MCP tools

### `resolve_postcode_auto`
- **설명**:  
  장소명/주소 또는 카카오맵 place JSON을 입력받아,
  - `best`: 가장 적합한 주소 후보
  - `candidates`: 추가 후보
  - `detail`: 상세주소 API 결과(옵션)
  - `english`: 영문주소 API 결과(옵션)
  를 반환합니다.

- **입력 필드 (요약)**:
  - `query: string | null` — 장소명/주소 문자열
  - `kakao_place: object | null` — 카카오 place 단일 객체
  - `kakao_places: object[] | null` — 카카오 place 리스트
  - `hint_city: string | null` — 스코어링 힌트 (예: “수원”)
  - `max_candidates: int` (기본 5, 1~20)
  - `include_detail: bool` (기본 `true`)
  - `detail_search_type: "dong"` (기본)
  - `dong_nm: string | null`
  - `include_english: bool` (기본 `true`)
  - `english_count_per_page: int` (기본 5, 1~20)

- **출력 필드 (요약)**:
  - `best: { road_addr, jibun_addr, postcode5, building_name, admCd, rnMgtSn, ... } | null`
  - `candidates: same[]`
  - `detail: { common, items[] } | null`
  - `english: { common, best, candidates[] } | null`
  - `message: string | null`
  - `meta: { strategy, input_used, include_detail, include_english, ... }`

---

## Quickstart (Local, uv)

```bash
uv venv -p 3.11.8
uv sync --all-extras
cp .env.example .env  # 키 입력
```

### 환경변수 (.env)
필수:
```bash
JUSO_ROAD_KEY="..."      # 또는 레거시 JUSO_CONFM_KEY
```

선택:
```bash
JUSO_DETAIL_KEY="..."    # 상세주소 API
JUSO_ENG_KEY="..."       # 영문주소 API
JUSO_ENG_API_URL="https://business.juso.go.kr/addrlink/addrEngApi.do"
LOG_LEVEL="INFO"
```

### Run
STDIO (로컬/Inspector):
```bash
fastmcp run
```

HTTP (PlayMCP/외부 연동 권장):
```bash
fastmcp run --transport http --host 0.0.0.0 --port 3334
# MCP endpoint: http://localhost:8000/mcp
```

---

## PlayMCP 연동
- PlayMCP: https://playmcp.kakao.com
- 기존 MCP 예시: https://playmcp.kakao.com/mcp/3, /61, /243

### 등록 팁
- MCP 이름: `postcode-mcp`
- Endpoint: `https://your-domain.com/mcp`
- Tool: `resolve_postcode_auto` (ASCII)
- Tool 설명: README의 한글 설명 사용
- 영문/상세 주소를 기본으로 포함하려면 `include_detail=true`, `include_english=true` 유지

### LLM 사용 예시
- “카카오 본사 주소와 5자리 우편번호, 영문주소 알려줘”  
  → Kakao Maps MCP로 place 검색 → `road_address_name`을 본 MCP에 전달
- “경기도 수원시 팔달구 효원로 241의 우편번호와 상세주소를 알려줘”  
  → `query`로 직접 호출

---

## Examples

### 예시 1: 단순 주소 문자열
```json
{
  "tool": "resolve_postcode_auto",
  "arguments": {
    "query": "경기도 수원시 팔달구 효원로 241",
    "hint_city": "수원",
    "max_candidates": 5
  }
}
```

### 예시 2: 카카오 place + 장소명
```json
{
  "tool": "resolve_postcode_auto",
  "arguments": {
    "query": "카카오 본사",
    "kakao_place": {
      "place_name": "카카오",
      "road_address_name": "경기 성남시 분당구 대왕판교로 645번길 14"
    },
    "hint_city": "성남",
    "include_detail": true,
    "include_english": true
  }
}
```

---

## Test
```bash
pytest -q
```
- `tests/test_postcode_tool.py`는 Juso 키가 없으면 자동 스킵합니다.

---

## License
MIT
