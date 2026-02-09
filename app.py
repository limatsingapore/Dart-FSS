import streamlit as st
import dart_fss as dart
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import re

# 1. 페이지 설정
st.set_page_config(page_title="AI 공시 분석기 Pro", layout="wide")
st.title("🤖 AI Stock Analyst (HTML Parser Version)")

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

# HTML 태그를 좀 줄여서 토큰을 아끼는 헬퍼 함수
def clean_html(html_content):
    if not html_content: return ""
    # 스타일 태그 제거 (내용과 무관하므로)
    clean = re.sub(r'<style.*?>.*?</style>', '', html_content, flags=re.DOTALL)
    # 주석 제거
    clean = re.sub(r'', '', clean, flags=re.DOTALL)
    return clean

# 4. Gemini 분석 함수
def get_ai_analysis(stock_name, report_title, raw_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') 
    
    # HTML이 들어갈 수 있으므로 프롬프트 조정
    prompt = f"""
    당신은 20년차 펀드매니저이자 데이터 분석가입니다.
    
    [분석 대상]
    기업명: {stock_name}
    보고서: {report_title}
    
    [데이터 소스 (HTML 또는 텍스트)]
    아래 데이터는 DART 공시 문서의 원문(HTML 포함)입니다. 
    HTML 태그(table, tr, td) 구조를 해석하여 재무 수치와 텍스트 내용을 파악하세요.
    --------------------------
    {raw_data[:30000]} 
    --------------------------
    
    [지시사항]
    1. **핵심 요약 (3줄)**: 보고서의 가장 중요한 변화나 실적 요약.
    2. **주요 재무 실적 (표)**: 매출액, 영업이익, 당기순이익 등 핵심 숫자를 찾아 표(Markdown Table)로 정리하세요. (단위 필수 표기)
    3. **상세 분석**: 전분기/전년동기 대비 어떤 변화가 있는지 서술하세요.
    4. **특이사항**: 소송, 자본금 변동 등 리스크 요인이 있다면 언급하세요.
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
                # 필터링 옵션 강화
                report_filter = st.radio(
                    "보고서 필터", 
                    ["정기보고서만(사업/반기/분기)", "모든 공시(최근순)"],
                    horizontal=True
                )
            with col3:
                st.write("") # 여백
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
                        start_date = (datetime.now() - pd.DateOffset(years=2)).strftime('%Y%m%d') # 2년치 넉넉하게
                        
                        # 필터링 로직
                        if "정기보고서" in report_filter:
                            # a001:사업, a002:반기, a003:분기
                            reports = target.search_filings(bgn_de=start_date, pblntf_detail_ty=['a001', 'a002', 'a003'])
                        else:
                            reports = target.search_filings(bgn_de=start_date) # 전체 검색
                        
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
            
            # 리스트박스에 표시할 이름 포맷팅
            report_map = {f"[{r.rcept_dt}] {r.report_nm}": r for r in reports}
            
            st.divider()
            selected_option = st.selectbox("📋 분석할 문서를 선택하세요:", list(report_map.keys()))
            target_report = report_map[selected_option]
            
            if st.button("🚀 HTML 모드로 강력 분석 시작"):
                report_url = f"http://dart.fss.or.kr/dsaf001/main.do?rcpNo={target_report.rcp_no}"
                st.info(f"선택: **{target_report.report_nm}**")
                st.markdown(f"👉 [DART 원문 보기]({report_url})")

                raw_content = ""
                # 진행률 표시바
                progress_bar = st.progress(0)
                
                try:
                    # 페이지가 많을 수 있으니 최대 5페이지만 (보통 앞부분에 재무정보가 있음)
                    # 필요한 경우 limit 숫자를 늘리세요.
                    pages_to_scan = target_report.pages[:10] 
                    total_pages = len(pages_to_scan)
                    
                    with st.spinner("문서 구조(HTML)를 파싱하고 있습니다..."):
                        for i, page in enumerate(pages_to_scan):
                            # 1차 시도: 텍스트
                            text = page.text
                            # 2차 시도: 텍스트가 부실하면 HTML 가져오기
                            if len(text) < 50: 
                                html = page.html
                                raw_content += clean_html(html) + "\n"
                            else:
                                raw_content += text + "\n"
                            
                            progress_bar.progress((i + 1) / total_pages)
                            
                except Exception as e:
                    st.error(f"데이터 추출 중 일부 오류: {e}")
                
                # 분석 시작
                if len(raw_content) > 100:
                    with st.spinner("Gemini가 복잡한 재무제표 표를 해석하고 있습니다..."):
                        analysis_result = get_ai_analysis(target_stock, target_report.report_nm, raw_content, gemini_api_key)
                    
                    st.divider()
                    st.subheader("📊 AI 심층 분석 결과")
                    st.markdown(analysis_result)
                    
                    with st.expander("AI에게 전달된 원본 데이터(HTML 일부) 확인"):
                        st.code(raw_content[:1000], language='html')
                else:
                    st.error("데이터를 추출할 수 없습니다. 보안 문서이거나 이미지가 깨진 파일일 수 있습니다.")

else:
    st.info("왼쪽에 API 키를 입력해주세요.")
