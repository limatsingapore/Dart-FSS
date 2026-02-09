import streamlit as st
import dart_fss as dart
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# 1. 페이지 기본 설정
st.set_page_config(page_title="AI 공시 분석 에이전트", layout="wide")
st.title("Stock Analyst (DART x Gemini)")

# 2. 사이드바 설정
st.sidebar.header("🔑 설정")
dart_api_key = st.sidebar.text_input("OpenDART API Key", type="password")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")

# 3. DART 기업 리스트 초기화
@st.cache_resource
def init_dart_list(api_key):
    try:
        dart.set_api_key(api_key=api_key)
        corp_list = dart.get_corp_list()
        return corp_list
    except Exception as e:
        return None

# 4. Gemini 분석 함수
def get_ai_analysis(stock_name, text_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') 
    
    prompt = f"""
    당신은 20년 경력의 베테랑 펀드매니저입니다.
    아래는 '{stock_name}'의 최근 전자공시 내용입니다.
    
    [요청사항]
    1. 이 공시의 핵심 내용을 3줄로 요약하세요.
    2. 이 뉴스가 주가에 호재인지 악재인지 '호재/악재/중립' 중 하나로 판정하고 이유를 한 문장으로 쓰세요.
    3. 재무적인 숫자가 있다면 별도로 강조해주세요.

    [공시 데이터]
    {text_data[:20000]} 
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- 메인 로직 ---

if dart_api_key and gemini_api_key:
    if 'corp_list_loaded' not in st.session_state:
        with st.spinner("기업 리스트를 다운로드 중입니다... (1분 정도 소요)"):
            corp_list = init_dart_list(dart_api_key)
            st.session_state['corp_list_loaded'] = True
    else:
        corp_list = init_dart_list(dart_api_key)
    
    if corp_list:
        st.success("시스템 준비 완료!")
        
        with st.form("analysis_form"):
            target_stock = st.text_input("분석할 종목명을 입력하세요 (예: 삼성전자)", "대우건설")
            submitted = st.form_submit_button("🚀 분석 시작")

        if submitted:
            try:
                with st.spinner(f"'{target_stock}'의 공시를 뒤지는 중입니다..."):
                    found_corps = corp_list.find_by_corp_name(target_stock, exactly=True)
                    
                    if not found_corps:
                        st.error("종목을 찾을 수 없습니다. 정확한 회사명을 입력해주세요.")
                    else:
                        target = found_corps[0]
                        start_date = (datetime.now() - pd.DateOffset(months=3)).strftime('%Y%m%d')
                        reports = target.search_filings(bgn_de=start_date, pblntf_detail_ty=['a001', 'a002', 'a003', 'i001', 'i002'])

                        if reports:
                            latest_report = reports[0]
                            st.info(f"검색된 최신 공시: **{latest_report.report_nm}** ({latest_report.rcept_dt})")
                            
                            # [수정된 부분] 페이지별로 텍스트 추출
                            extracted_text = ""
                            try:
                                with st.spinner("공시 문서 본문을 가져오는 중입니다... (시간이 조금 걸릴 수 있습니다)"):
                                    # pages 속성에 접근하면 자동으로 로딩됩니다.
                                    for page in latest_report.pages:
                                        extracted_text += page.text + "\n"
                            except Exception as text_error:
                                extracted_text = "텍스트 추출 실패 (이미지 문서일 가능성 있음)"
                            
                            # Gemini 호출
                            if len(extracted_text) > 50: # 내용이 있을 때만
                                with st.spinner("Gemini가 보고서를 읽고 있습니다..."):
                                    analysis_result = get_ai_analysis(target_stock, extracted_text, gemini_api_key)
                                
                                st.subheader("📊 AI 분석 리포트")
                                st.markdown(analysis_result)
                                
                                with st.expander("공시 원문 보기"):
                                    st.text(extracted_text[:3000] + "...")
                            else:
                                st.warning("공시 문서에서 텍스트를 읽어오지 못했습니다.")

                        else:
                            st.warning("최근 3개월 내 주요 공시가 없습니다.")
                            
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
    else:
        st.error("DART API 키를 확인해주세요.")
else:
    st.info("👈 왼쪽 사이드바에 API 키를 먼저 입력해주세요.")
