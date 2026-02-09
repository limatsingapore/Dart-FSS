import streamlit as st
import dart_fss as dart
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# 1. 페이지 기본 설정
st.set_page_config(page_title="AI 공시 분석 에이전트", layout="wide")
st.title("🤖 AI Stock Analyst (DART x Gemini)")

# 2. 사이드바: API 키 입력 (보안을 위해 입력창으로 받음)
st.sidebar.header("🔑 설정")
dart_api_key = st.sidebar.text_input("OpenDART API Key", type="password")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")

# 3. DART 기업 리스트 초기화 (수정됨: UI 코드 제거)
@st.cache_resource
def init_dart_list(api_key):
    try:
        # 여기서는 오직 데이터만 가져옵니다. 화면 표시는 밖에서!
        dart.set_api_key(api_key=api_key)
        corp_list = dart.get_corp_list()
        return corp_list
    except Exception as e:
        return NoneNone

# 4. Gemini 분석 함수
def get_ai_analysis(stock_name, text_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') # 무료 티어 모델
    
    prompt = f"""
    당신은 20년 경력의 베테랑 펀드매니저입니다.
    아래는 '{stock_name}'의 최근 전자공시 내용입니다.
    
    [요청사항]
    1. 이 공시의 핵심 내용을 3줄로 요약하세요.
    2. 이 뉴스가 주가에 호재인지 악재인지 '호재/악재/중립' 중 하나로 판정하고 이유를 한 문장으로 쓰세요.
    3. 재무적인 숫자가 있다면 별도로 강조해주세요.

    [공시 데이터]
    {text_data[:15000]} 
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- 메인 로직 시작 ---

if dart_api_key and gemini_api_key:
    # DART 리스트 로드 (화면 알림을 밖으로 뺐습니다)
    with st.spinner("기업 리스트를 다운로드 중입니다... (최초 1회 약 1분 소요)"):
        corp_list = init_dart_list(dart_api_key)
    
    if corp_list:
        st.success("시스템 준비 완료!")
        # ... (이후 코드는 동일)
        
        # 입력 폼
        with st.form("analysis_form"):
            target_stock = st.text_input("분석할 종목명을 입력하세요 (예: 삼성전자)", "삼성전자")
            submitted = st.form_submit_button("🚀 분석 시작")

        if submitted:
            try:
                with st.spinner(f"'{target_stock}'의 공시를 뒤지는 중입니다..."):
                    # 종목 찾기
                    target = corp_list.find_by_corp_name(target_stock, exactly=True)
                    
                    if not target:
                        st.error("종목을 찾을 수 없습니다. 정확한 회사명을 입력해주세요.")
                    else:
                        # 최근 3개월 공시 검색
                        start_date = (datetime.now() - pd.DateOffset(months=3)).strftime('%Y%m%d')
                        reports = target.search_filings(bgn_de=start_date, pblntf_detail_ty=['a001', 'a002', 'a003', 'i001', 'i002']) # 사업보고서 및 수시공시 포함

                        if reports:
                            latest_report = reports[0] # 가장 최신 것
                            st.info(f"검색된 최신 공시: **{latest_report.report_nm}** ({latest_report.rcept_dt})")
                            
                            # 본문 추출
                            extracted_text = latest_report.extract_text()
                            
                            # Gemini 호출
                            with st.spinner("Gemini가 보고서를 읽고 있습니다..."):
                                analysis_result = get_ai_analysis(target_stock, extracted_text, gemini_api_key)
                            
                            # 결과 출력
                            st.subheader("📊 AI 분석 리포트")
                            st.markdown(analysis_result)
                            
                            # 원문 보기 (접기/펴기)
                            with st.expander("공시 원문 보기"):
                                st.text(extracted_text[:3000] + "...")
                                
                        else:
                            st.warning("최근 3개월 내 주요 공시가 없습니다.")
                            
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
    else:
        st.error("DART API 키를 확인해주세요.")
else:
    st.info("👈 왼쪽 사이드바에 API 키를 먼저 입력해주세요.")


