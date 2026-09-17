"""One-pass production Agent integration regression; read-only Tool handlers."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))
from app.config import get_openai_api_key, get_spring_server_base_url
from app.prompts import REAL_ESTATE_AGENT_INSTRUCTIONS
from app.providers.openai_provider import OpenAIProvider
from app.retrievers.openai_vector_store_law_retriever import OpenAIVectorStoreLawRetriever
from app.tools.legal_dong_adjacency import LegalDongAdjacencyTool
from app.tools.property_search import PropertySearchTool
from app.tools.real_estate_law import RealEstateLawSearchTool
from app.tools.transit_station import TransitStationTool
from evaluate_production_law_v2_real_user24 import ResponsesProxy, VectorStoresProxy, ClientProxy

MODEL = "gpt-5.6-luna"
STORE = "vs_6aa764aaf2008191af233d99e6fd6cd2"
OUTPUT = PROJECT / "docs/evaluation/production_agent_integrated_regression_30_live.csv"
QUESTIONS = [
    ("A", "", "안녕하세요. 집찾GO에서 무엇을 도와줄 수 있나요?", None),
    ("A", "", "집을 보러 갈 때 채광을 확인하는 간단한 팁 알려줘.", None),
    ("A", "", "아파트와 오피스텔의 생활상 차이를 쉽게 설명해줘.", None),
    ("B", "property", "분당구에서 6억 이하 아파트 찾아줘.", None),
    ("B", "property", "정자동에서 5억 이하 오피스텔 매물 찾아줘.", None),
    ("B", "property", "판교동 빌라 매물 검색해줘.", None),
    ("B", "property", "이 주변에 현재 등록된 아파트 매물이 있나요?", {"current_page":"map","map_center":{"lat":37.394,"lng":127.111},"zoom":6,"map_bounds":{"south":37.38,"west":127.09,"north":37.41,"east":127.13}}),
    ("B", "property", "선택한 정자동에서 7억 이하 아파트 보여줘.", {"current_page":"map","selected_region":{"type":"legal_dong","code":"41135103","name":"정자동","full_name":"성남시 분당구 정자동","center":{"lat":37.366,"lng":127.107},"bounds":{"south":37.35,"west":127.09,"north":37.38,"east":127.13}},"zoom":6}),
    ("C", "station,map", "정자역 근처로 지도 이동해줘.", {"current_page":"map","zoom":3}),
    ("C", "map", "지도를 조금 확대해줘.", {"current_page":"map","map_center":{"lat":37.394,"lng":127.111},"zoom":5}),
    ("C", "map", "정자동 경계를 지도에서 선택해줘.", {"current_page":"map","zoom":5}),
    ("D", "station", "판교역 위치를 찾아서 지도에 보여줘.", {"current_page":"map","zoom":4}),
    ("D", "adjacency", "정자동과 경계가 맞닿은 동은 어디야?", {"current_page":"map"}),
    ("D", "adjacency", "선택한 이 동의 옆 동을 알려줘.", {"current_page":"map","selected_region":"정자동"}),
    ("D", "station", "서현역을 지도에서 찾을 수 있나요?", {"current_page":"map","zoom":4}),
    ("E", "law", "묵시적으로 갱신된 전세 계약을 임차인이 해지하면 언제 효력이 생기나요?", None),
    ("E", "law", "전입신고와 집 인도를 마치면 대항력은 정확히 언제 생기나요?", None),
    ("E", "law", "매매 계약을 체결하면 거래신고는 누가 언제까지 해야 하나요?", None),
    ("E", "law", "중개사가 계약 전에 확인하고 설명해야 할 법적 사항은 무엇인가요?", None),
    ("F", "property,map", "분당구 6억 이하 아파트를 찾아 지도에 보여줘.", {"current_page":"map","zoom":4}),
    ("F", "property,map", "판교동 빌라 매물을 찾아 마커를 강조해줘.", {"current_page":"map","zoom":4}),
    ("F", "property,map", "여기 화면 안의 5억 이하 오피스텔을 검색해서 지도에 표시해줘.", {"current_page":"map","map_bounds":{"south":37.38,"west":127.09,"north":37.41,"east":127.13},"zoom":5}),
    ("G", "property,station", "정자역 근처 6억 이하 아파트를 찾아주고 역 위치도 지도에 보여줘.", {"current_page":"map","zoom":4}),
    ("G", "property,adjacency", "정자동 아파트 매물을 찾고 정자동과 맞닿은 동도 알려줘.", {"current_page":"map","zoom":5}),
    ("G", "property,station", "판교역 주변 오피스텔 매물을 찾아주고 역 위치도 알려줘.", {"current_page":"map","zoom":4}),
    ("H", "property,law", "정자동 전세 매물을 찾아주고 보증금 보호를 위해 계약 전에 확인할 법적 요건도 알려줘.", {"current_page":"map","zoom":5}),
    ("H", "property,law", "분당구 아파트 매물을 찾아주고 중개사가 설명해야 할 법적 내용도 알려줘.", {"current_page":"map","zoom":5}),
    ("H", "property,law", "판교동 빌라 매물을 찾아주고 매매 계약 후 거래신고 기한도 알려줘.", {"current_page":"map","zoom":5}),
    ("I", "property,station,law", "정자역 근처 아파트를 찾고 역 위치도 보여줘. 전세 계약 시 대항력 발생 시점도 알려줘.", {"current_page":"map","zoom":4}),
    ("I", "property,adjacency,law", "정자동 매물을 찾고 옆 동도 알려줘. 계약 전 중개사가 확인·설명할 법적 내용도 알려줘.", {"current_page":"map","zoom":5}),
]

def j(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

def save(rows):
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def main():
    if len(QUESTIONS) != 30 or OUTPUT.exists():
        raise RuntimeError("Question set changed or output already exists")
    key = get_openai_api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY unavailable")
    run = "production-agent-integrated-30-" + uuid.uuid4().hex[:12]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip()
    timestamp = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    spring = get_spring_server_base_url()
    property_tool = PropertySearchTool(spring)
    station_tool = TransitStationTool(spring)
    adjacency_tool = LegalDongAdjacencyTool()
    rows = []
    for index, (category, expected, question, state) in enumerate(QUESTIONS, 1):
        print(f"Evaluating {index}/30: {category}", flush=True)
        response_client = OpenAI(api_key=key, max_retries=0)
        vector_client = OpenAI(api_key=key, max_retries=0)
        responses = ResponsesProxy(response_client.responses)
        vector = VectorStoresProxy(vector_client.vector_stores)
        provider = OpenAIProvider(key, MODEL, REAL_ESTATE_AGENT_INSTRUCTIONS)
        provider._client = ClientProxy(response_client, responses=responses)
        retriever = OpenAIVectorStoreLawRetriever(key, STORE, client=ClientProxy(vector_client, vector_stores=vector))
        law_tool = RealEstateLawSearchTool(retriever)
        results = []
        def observe(name, handler):
            def wrapped(arguments):
                result = handler(arguments)
                results.append({"name":name,"arguments":arguments,"result":result})
                return result
            return wrapped
        start = time.perf_counter()
        final = ""
        actions = []
        error = ""
        try:
            reply = provider.generate(message=question, app_state=state,
                search_properties=observe("search_properties", property_tool.search),
                find_transit_station=observe("find_transit_station", station_tool.search),
                get_adjacent_legal_dongs=observe("get_adjacent_legal_dongs", adjacency_tool.lookup),
                search_real_estate_law=observe("search_real_estate_law", law_tool.search))
            final = reply.message
            actions = [item.model_dump() for item in reply.actions]
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        rows.append({"RunID":run,"Timestamp":timestamp,"GitCommit":commit,"AgentModel":MODEL,
            "LawCorpus":"law_store_v2","VectorStoreID":STORE,"ResponsesStore":"false","SDKRetry":"0","ManualRetry":"0",
            "ID":index,"Category":category,"UserQuestion":question,"AppState":j(state),"ExpectedToolTypes":expected,
            "ActualTools":j(responses.calls),"ToolResults":j(results),"ToolCallCount":len(responses.calls),
            "ResponseRounds":responses.rounds,"Actions":j(actions),"FinalResponse":final,"LatencyMs":round((time.perf_counter()-start)*1000),
            "InputTokens":responses.input_tokens,"OutputTokens":responses.output_tokens,
            "TotalTokens":responses.input_tokens+responses.output_tokens,"TokenUsageAvailable":"Y" if responses.usage_available else "N",
            "Error":error,"Classification":"PENDING_REVIEW","Notes":""})
        save(rows)
    print(f"Saved {len(rows)} rows; Run ID: {run}")

if __name__ == "__main__":
    main()
