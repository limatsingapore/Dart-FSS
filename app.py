import streamlit as st
import dart_fss as dart
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="AI 공시 분석기", layout="wide")
st.title("🤖 AI Stock Analyst (Select & Analyze)")

# 2. 사이드바 (API 키)
st.sidebar.header("🔑 설정")
dart_api_key = st.sidebar.text_input("OpenDART API Key", type="password")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")

# 3. DART 초기화 (캐싱)
@st.cache_resource
def init_dart_list(api_key):
    try:
        dart.set_api_key(api_key=api_key)
        corp_list = dart.get_corp_list()
        return corp_list
    except Exception as e:
        return None

# 4. Gemini 분석 함수
def get_ai_analysis(stock_name, report_title, text_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') 
    
    prompt = f"""
    당신은 20년차 펀드매니저입니다.
    
    [분석 대상]
    기업명: {stock_name}
    보고서: {report_title}
    
    [보고서 내용]
    {text_data[:25000]}
    
    [지시사항]
    1. 이 보고서의 핵심 요약 (3줄)
    2. 주요 재무 수치 추출 (매출, 영업이익, 당기순이익 등 숫자가 있다면 표 형식으로 정리)
    3. 투자자 입장에서의 긍정/부정 요인 분석
    4. 결론 (한 문장)
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- 메인 로직 ---

if dart_api_key and gemini_api_key:
    if 'corp_list_loaded' not in st.session_state:
        with st.spinner("최초 실행: 기업 리스트 다운로드 중... (약 1분)"):
            corp_list = init_dart_list(dart_api_key)
            st.session_state['corp_list_loaded'] = True
    else:
        corp_list = init_dart_list(dart_api_key)
    
    if corp_list:
        st.success("시스템 준비 완료")
        
        # 1. 종목 검색
        col1, col2 = st.columns([3, 1])
        with col1:
            target_stock = st.text_input("종목명 입력", "대우건설")
        with col2:
            search_btn = st.button("🔍 공시 조회")

        # 세션 상태에 검색 결과 저장 (화면 리프레시 되어도 유지)
        if 'search_results' not in st.session_state:
            st.session_state['search_results'] = None

        if search_btn:
            try:
                with st.spinner(f"'{target_stock}'의 최근 1년치 공시를 가져옵니다..."):
                    found_corps = corp_list.find_by_corp_name(target_stock, exactly=True)
                    if found_corps:
                        target = found_corps[0]
                        # 1년치 넉넉하게 검색
                        start_date = (datetime.now() - pd.DateOffset(years=1)).strftime('%Y%m%d')
                        reports = target.search_filings(bgn_de=start_date, pblntf_detail_ty=['a001', 'a002', 'a003', 'f001', 'f002', 'i001', 'i002'])
                        
                        if reports:
                            st.session_state['search_results'] = reports
                            st.rerun() # 화면 갱신해서 아래 선택창 표시
                        else:
                            st.warning("기간 내 공시가 없습니다.")
                    else:
                        st.error("종목을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"검색 중 오류: {e}")

        # 2. 공시 선택 및 분석
        if st.session_state['search_results']:
            reports = st.session_state['search_results']
            
            # 선택상자(Selectbox) 만들기
            report_options = {f"[{r.rcept_dt}] {r.report_nm}": r for r in reports}
            selected_option = st.selectbox("📋 분석할 보고서를 선택하세요:", list(report_options.keys()))
            
            # 선택된 보고서 객체
            target_report = report_options[selected_option]
            
            # 3. 분석 버튼
            if st.button("🚀 선택한 보고서 AI 분석 시작"):
                report_url = f"http://dart.fss.or.kr/dsaf001/main.do?rcpNo={target_report.rcp_no}"
                st.info(f"선택된 보고서: **[{target_report.report_nm}]**")
                st.markdown(f"👉 [DART 원문 새창으로 열기]({report_url})")

                extracted_text = ""
                with st.spinner("문서 내용을 추출하고 있습니다..."):
                    try:
                        for page in target_report.pages:
                            extracted_text += page.text + "\n"
                    except:
                        pass
                
                # 텍스트가 너무 적으면(이미지/표) 경고
                if len(extracted_text) < 100:
                    st.warning("⚠️ 텍스트 추출 결과가 너무 적습니다. 표나 이미지로 된 공시일 수 있습니다.")
                    st.text("추출된 텍스트 일부:\n" + extracted_text[:500])
                    
                    if st.button("그래도 강제로 분석해보기"):
                        with st.spinner("Gemini에게 억지로 분석시키는 중..."):
                             res = get_ai_analysis(target_stock, target_report.report_nm, extracted_text, gemini_api_key)
                             st.markdown(res)
                else:
                    # 정상 분석 수행
                    with st.spinner("Gemini가 열심히 보고서를 읽고 있습니다..."):
                        analysis_result = get_ai_analysis(target_stock, target_report.report_nm, extracted_text, gemini_api_key)
                    
                    st.divider()
                    st.subheader("📊 AI 분석 결과")
                    st.markdown(analysis_result)
                    
                    with st.expander("AI가 읽은 원문(앞부분) 확인"):
                        st.text(extracted_text[:2000])

else:
    st.info("왼쪽에 API 키를 입력해주세요.")
