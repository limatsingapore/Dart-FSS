import streamlit as st
import dart_fss as dart
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# 1. 페이지 기본 설정
st.set_page_config(page_title="AI 공시 분석 에이전트", layout="wide")
st.title("🤖 AI Stock Analyst (DART x Gemini)")

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
def get_ai_analysis(stock_name, report_title, text_data, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash') 
    
    prompt = f"""
    당신은 주식 애널리스트입니다.
    종목: '{stock_name}'
    공시 제목: '{report_title}'
    
    [공시 내용 추출]
    {text_data[:20000]} 
    
    [요청사항]
    1. 위 공시의 핵심 내용을 3줄로 요약하세요. (내용이 부족하면 제목을 보고 추론하여 설명하세요)
    2. 호재/악재/중립 여부를 판단하세요.
    3. 실적 수치(매출액, 영업이익 등)가 있다면 반드시 포함하세요.
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
                        st.error("종목을 찾을 수 없습니다.")
                    else:
                        target = found_corps[0]
                        # 기간을 조금 더 늘려서 확실한 문서를 찾아봅시다 (3개월 -> 6개월)
                        start_date = (datetime.now() - pd.DateOffset(months=6)).strftime('%Y%m%d')
                        reports = target.search_filings(bgn_de=start_date, pblntf_detail_ty=['a001', 'a002', 'a003', 'i001', 'i002', 'f001', 'f002'])

                        if reports:
                            latest_report = reports[0]
                            report_url = f"http://dart.fss.or.kr/dsaf001/main.do?rcpNo={latest_report.rcp_no}"
                            
                            st.info(f"📌 최신 공시 발견: [{latest_report.report_nm}]({report_url}) \n(클릭하면 DART 원문으로 이동합니다)")
                            
                            extracted_text = ""
                            
                            # 1단계: 텍스트 페이지 추출 시도
                            try:
                                with st.spinner("문서 내용을 읽어오는 중..."):
                                    for page in latest_report.pages:
                                        extracted_text += page.text + "\n"
                            except Exception as e:
                                pass # 텍스트 실패 시 무시하고 다음 단계로

                            # 2단계: 텍스트가 너무 적으면 '표(Table)' 추출 시도 (실적 공시 대비)
                            if len(extracted_text) < 100:
                                try:
                                    # pages[0]에 있는 html 표라도 긁어오기 시도
                                    if len(latest_report.pages) > 0:
                                        extracted_text += "\n[표 데이터 추출 시도]\n" + latest_report.pages[0].html
                                except:
                                    pass

                            # 결과 처리
                            if len(extracted_text) > 50:
                                with st.spinner("Gemini가 분석 중입니다..."):
                                    analysis_result = get_ai_analysis(target_stock, latest_report.report_nm, extracted_text, gemini_api_key)
                                
                                st.subheader("📊 AI 분석 리포트")
                                st.markdown(analysis_result)
                                with st.expander("추출된 원문 데이터 보기"):
                                    st.text(extracted_text[:3000])
                            else:
                                st.warning("⚠️ 공시 문서가 이미지나 단순 첨부파일로 되어 있어 텍스트를 읽을 수 없습니다.")
                                st.markdown(f"**👉 [여기]({report_url})를 클릭해서 원문을 직접 확인해주세요.**")
                                # 내용이 없어도 제목만으로라도 분석 요청
                                if st.button("제목만으로라도 AI 분석 해보기"):
                                    res = get_ai_analysis(target_stock, latest_report.report_nm, "내용 없음. 제목을 보고 추론할 것.", gemini_api_key)
                                    st.markdown(res)

                        else:
                            st.warning("최근 6개월 내 주요 공시가 없습니다.")
                            
            except Exception as e:
                st.error(f"상세 에러 내용: {e}")
    else:
        st.error("DART API 키를 확인해주세요.")
else:
    st.info("👈 왼쪽 사이드바에 API 키를 먼저 입력해주세요.")
