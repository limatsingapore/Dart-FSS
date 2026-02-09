import streamlit as st
import dart_fss as dart
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="AI 공시 분석 에이전트", layout="wide")
st.title("🤖 AI Stock Analyst (Periodic Reports First)")

# 2. 사이드바 설정
st.sidebar.header("🔑 설정")
dart_api_key = st.sidebar.text_input("OpenDART API Key", type="password")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")

# 3. DART 리스트 초기화
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
    당신은 전문 펀드매니저입니다.
    종목: '{stock_name}'
    보고서: '{report_title}'
    
    [공시 텍스트 추출]
    {text_data[:25000]} 
    
    [요청사항]
    1. 핵심 요약 (3줄)
    2. 재무 상태 및 실적 분석 (수치 포함 필수)
    3. 리스크 및 특이사항
    4. 종합 투자의견 (긍정/부정/중립)
    """
    response = model.generate_content(prompt)
    return response.text

# --- 메인 로직 ---

if dart_api_key and gemini_api_key:
    if 'corp_list_loaded' not in st.session_state:
        with st.spinner("기업 리스트 로딩 중..."):
            corp_list = init_dart_list(dart_api_key)
            st.session_state['corp_list_loaded'] = True
    else:
        corp_list = init_dart_list(dart_api_key)
    
    if corp_list:
        st.success("시스템 준비 완료!")
        
        with st.form("analysis_form"):
            col1, col2 = st.columns([3, 1])
            with col1:
                target_stock = st.text_input("종목명 (예: 대우건설)", "대우건설")
            with col2:
                # 사용자가 보고서 유형을 강제할 수도 있게 옵션 추가
                report_type = st.selectbox("보고서 우선순위", ["정기보고서(사업/반기/분기)", "모든 최신공시"])
            
            submitted = st.form_submit_button("🚀 심층 분석 시작")

        if submitted:
            try:
                with st.spinner(f"'{target_stock}'의 보고서를 선별 중입니다..."):
                    found_corps = corp_list.find_by_corp_name(target_stock, exactly=True)
                    
                    if not found_corps:
                        st.error("종목을 찾을 수 없습니다.")
                    else:
                        target = found_corps[0]
                        # 검색 기간 1년으로 확장 (분기/반기 보고서는 드문드문 나오므로)
                        start_date = (datetime.now() - pd.DateOffset(years=1)).strftime('%Y%m%d')
                        
                        # 모든 유형 검색
                        all_reports = target.search_filings(bgn_de=start_date, pblntf_detail_ty=['a001', 'a002', 'a003', 'f001', 'f002', 'i001', 'i002'])

                        target_report = None
                        
                        if all_reports:
                            # [핵심 로직] 정기보고서 우선 필터링
                            if report_type == "정기보고서(사업/반기/분기)":
                                for r in all_reports:
                                    # 보고서 명에 '보고서'가 들어가고 '기재정정'이 아닌 것을 우선 찾음
                                    if "보고서" in r.report_nm and "기재정정" not in r.report_nm:
                                        target_report = r
                                        break
                                # 정기보고서가 없으면 어쩔 수 없이 최신 공시 선택
                                if target_report is None:
                                    st.warning("지정된 기간 내 정기보고서가 없어 가장 최신 공시를 가져옵니다.")
                                    target_report = all_reports[0]
                            else:
                                target_report = all_reports[0]

                            # 찾은 보고서 처리
                            report_url = f"http://dart.fss.or.kr/dsaf001/main.do?rcpNo={target_report.rcp_no}"
                            st.info(f"📌 분석 대상: **[{target_report.report_nm}]** ({target_report.rcept_dt})")
                            st.markdown(f"👉 [DART 원문 보러가기]({report_url})")

                            extracted_text = ""
                            with st.spinner("문서 전체 페이지를 스캔 중입니다... (데이터 양에 따라 10~20초 소요)"):
                                for page in target_report.pages:
                                    extracted_text += page.text + "\n"
                            
                            if len(extracted_text) > 100:
                                with st.spinner("Gemini가 재무제표를 분석하고 있습니다..."):
                                    analysis_result = get_ai_analysis(target_stock, target_report.report_nm, extracted_text, gemini_api_key)
                                
                                st.divider()
                                st.subheader("📊 AI 심층 리포트")
                                st.markdown(analysis_result)
                                
                                with st.expander("AI가 읽은 원문 데이터 일부 확인"):
                                    st.text(extracted_text[:3000])
                            else:
                                st.error("텍스트 추출 실패: 이미지 위주의 문서이거나 내용이 비어있습니다.")
                        else:
                            st.warning("검색 기간 내 공시가 없습니다.")
                            
            except Exception as e:
                st.error(f"에러 발생: {e}")
    else:
        st.error("API 키를 확인해주세요.")
else:
    st.info("API 키 입력 대기 중...")
