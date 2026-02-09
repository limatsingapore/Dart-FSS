import streamlit as st
import dart_fss as dart
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import re

# 1. 페이지 설정
st.set_page_config(page_title="AI 공시 분석기 Pro", layout="wide")
st.title("🤖 AI Stock Analyst (HTML Only Version)")

# 2. 사이드바 (API 키)
st.sidebar.header("🔑 설정")
dart_api_key = st.sidebar.text_input("OpenDART API Key", type="password")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")

# 3. DART 초기화
@st.cache_resource
def init_dart_list(api_key):
    try:
        dart.set_api_key(api_key=api_key)
        corp_list = dart.get_corp_list()
        return corp_list
    except Exception as e:
        return None

# HTML 태그 정리 함수 (너무 긴 스타일/스크립트 제거)
def clean_html_structure(html_content):
    if not html_content: return ""
    # 불필요한 스타일, 스크립트 제거
    clean = re.sub(r'<style.*?>.*?</style>', '', html_content, flags=re.DOTALL)
    clean = re.sub(r'<script.*?>.*?</script>', '', clean, flags=re.DOTALL)
    clean = re.sub(r'', '', clean, flags=re.DOTALL)
    return clean

# 4. Gemini 분석 함수
def get_ai_analysis(stock_name, report_title, raw_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') 
    
    prompt = f"""
    당신은 20년차 펀드매니저이자 데이터 분석가입니다.
    
    [분석 대상]
    기업명: {stock_name}
    보고서: {report_title}
    
    [데이터 소스 (HTML Code)]
    아래 데이터는 DART 공시 문서의 Raw HTML입니다. 
    HTML Table 구조(tr, td)를 해석하여 정확한 재무 수치를 추출하세요.
    --------------------------
    {raw_data[:30000]} 
    --------------------------
    
    [지시사항]
    1. **핵심 요약 (3줄)**: 보고서의 가장 중요한 실적 및 변화.
    2. **주요 재무 실적 (Markdown 표)**: 매출액, 영업이익, 당기순이익 (단위 포함). 전년 동기 대비 증감율이 있다면 계산하거나 명시.
    3. **상세 분석**: 긍정적/부정적 요인 서술.
    4. **특이사항**: 자본금 변동, 소송 등 리스크 요인.
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- 메인 로직 ---

if dart_api_key and gemini_api_key:
    if 'corp_list_loaded' not in st.session_state:
        with st.spinner("시스템 초기화 중... (약 1분)"):
            corp_list = init_dart_list(dart_api_key)
            st.session_state['corp_list_loaded'] = True
    else:
        corp_list = init_dart_list(dart_api_key)
    
    if corp_list:
        st.success("준비 완료")
        
        # 1. 종목 및 검색 옵션
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                target_stock = st.text_input("종목명", "기업은행")
            with col2:
                report_filter = st.radio(
                    "보고서 필터", 
                    ["정기보고서만(사업/반기/분기)", "모든 공시(최근순)"],
                    horizontal=True
                )
            with col3:
                st.write("") 
                st.write("") 
                search_btn = st.button("🔍 공시 조회", use_container_width=True)

        if 'search_results' not in st.session_state:
            st.session_state['search_results'] = None

        if search_btn:
            try:
                with st.spinner(f"'{target_stock}' 공시 데이터를 가져옵니다..."):
                    found_corps = corp_list.find_by_corp_name(target_stock, exactly=True)
                    if found_corps:
                        target = found_corps[0]
                        start_date = (datetime.now() - pd.DateOffset(years=2)).strftime('%Y%m%d')
                        
                        if "정기보고서" in report_filter:
                            reports = target.search_filings(bgn_de=start_date, pblntf_detail_ty=['a001', 'a002', 'a003'])
                        else:
                            reports = target.search_filings(bgn_de=start_date)
                        
                        if reports:
                            st.session_state['search_results'] = reports
                            st.rerun()
                        else:
                            st.warning("해당 조건의 공시가 없습니다.")
                    else:
                        st.error("종목을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"검색 오류: {e}")

        # 2. 결과 리스트 및 분석
        if st.session_state['search_results']:
            reports = st.session_state['search_results']
            
            report_map = {f"[{r.rcept_dt}] {r.report_nm}": r for r in reports}
            
            st.divider()
            selected_option = st.selectbox("📋 분석할 문서를 선택하세요:", list(report_map.keys()))
            target_report = report_map[selected_option]
            
            if st.button("🚀 HTML 모드로 강력 분석 시작"):
                report_url = f"http://dart.fss.or.kr/dsaf001/main.do?rcpNo={target_report.rcp_no}"
                st.info(f"선택: **{target_report.report_nm}**")
                st.markdown(f"👉 [DART 원문 보기]({report_url})")

                raw_content = ""
                progress_bar = st.progress(0)
                
                try:
                    # 페이지 스캔 (앞부분 5페이지만 - 보통 여기에 재무정보 집중됨)
                    # 필요시 pages[:10] 등으로 늘리세요
                    pages_to_scan = target_report.pages[:5] 
                    total_pages = len(pages_to_scan)
                    
                    with st.spinner("문서 원본(HTML)을 다운로드 중입니다..."):
                        for i, page in enumerate(pages_to_scan):
                            try:
                                # [핵심 수정] .text 접근을 아예 삭제하고 .html만 가져옵니다.
                                html_data = page.html
                                if html_data:
                                    raw_content += clean_html_structure(html_data) + "\n"
                            except Exception as page_error:
                                # 특정 페이지 로드 실패시 건너뛰기
                                pass
                            
                            progress_bar.progress((i + 1) / total_pages)
                            
                except Exception as e:
                    st.error(f"데이터 로드 중 문제 발생: {e}")
                
                # 분석 시작
                if len(raw_content) > 100:
                    with st.spinner("Gemini가 HTML 테이블을 해석하고 있습니다..."):
                        analysis_result = get_ai_analysis(target_stock, target_report.report_nm, raw_content, gemini_api_key)
                    
                    st.divider()
                    st.subheader("📊 AI 심층 분석 결과")
                    st.markdown(analysis_result)
                    
                    with st.expander("AI에게 전달된 HTML 데이터 확인"):
                        st.code(raw_content[:1000], language='html')
                else:
                    st.error("HTML 데이터를 가져올 수 없습니다. (보안 문서 또는 이미지 PDF)")

else:
    st.info("왼쪽에 API 키를 입력해주세요.")
