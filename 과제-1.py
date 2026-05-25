from datetime import date, datetime, timedelta
import html
from io import BytesIO, StringIO
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from pykrx import stock


st.set_page_config(
    page_title="메자닌 데이터 플랫폼",
    layout="wide",
)

st.title("메자닌 데이터 플랫폼")
st.caption("전환사채/리픽싱/희석위험 분석")

st.markdown(
    """
    <style>
    :root {
        --brand-red: #ff4b4b;
        --brand-red-dark: #b91c1c;
        --brand-red-soft: #fff1f2;
        --brand-border: #fecdd3;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #fff1f2 0%, #ffffff 42%);
        border-right: 1px solid #fecdd3;
    }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] label {
        color: #991b1b;
    }
    .stButton > button {
        background: #ff4b4b;
        color: #ffffff;
        border: 1px solid #ff4b4b;
        border-radius: 6px;
        font-weight: 700;
    }
    .stButton > button:hover {
        background: #e03131;
        border-color: #e03131;
        color: #ffffff;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #fecdd3;
        border-top: 3px solid #ff4b4b;
        border-radius: 6px;
        padding: 12px 14px;
        box-shadow: none;
    }
    div[data-testid="stMetricLabel"] p {
        color: #b91c1c;
        font-weight: 700;
    }
    div[data-testid="stMetricValue"] {
        color: #0f172a;
    }
    div[data-testid="stTabs"] div[role="tablist"] {
        gap: 0;
        border-bottom: 1px solid #fecdd3;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        background: transparent;
        color: #b91c1c;
        border-radius: 0;
        border: 0;
        border-bottom: 3px solid transparent;
        margin-right: 2px;
        font-weight: 700;
        padding: 0.6rem 0.9rem;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: #fff1f2;
        color: #991b1b;
        border-bottom-color: #ff4b4b;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover {
        background: #fff7f7;
        color: #991b1b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


DEFAULT_OPEN_DART_API_KEY = "99008eb607f55b24c9fe337dcf874bbc2684193f"
OPENDART_DATA_START_DATE = date(2015, 1, 1)

MEZZANINE_DISCLOSURE_APIS = [
    {
        "type": "CB",
        "name": "전환사채",
        "endpoint": "cvbdIsDecsn",
    },
    {
        "type": "BW",
        "name": "신주인수권부사채",
        "endpoint": "bdwtIsDecsn",
    },
    {
        "type": "EB",
        "name": "교환사채",
        "endpoint": "exbdIsDecsn",
    },
]

KOREAN_COLUMN_NAMES = {
    "rcept_no": "접수번호",
    "corp_cls": "법인구분",
    "corp_code": "고유번호",
    "corp_name": "회사명",
    "bd_tm": "회차",
    "bd_knd": "사채종류",
    "stock_code": "종목코드",
    "market": "시장",
    "bd_fta": "발행금액",
    "atcsc_rmislmt": "정관상 잔여 발행한도",
    "ovis_fta": "해외발행 권면총액",
    "ovis_fta_crn": "해외발행 통화단위",
    "ovis_ster": "해외발행 기준환율",
    "ovis_isar": "해외발행지역",
    "ovis_mktnm": "해외상장 시장명",
    "fdpp_fclt": "시설자금",
    "fdpp_bsninh": "영업양수자금",
    "fdpp_op": "운영자금",
    "fdpp_dtrp": "채무상환자금",
    "fdpp_ocsa": "타법인 증권 취득자금",
    "fdpp_etc": "기타자금",
    "bd_intr_ex": "표면이자율",
    "bd_intr_sf": "만기이자율",
    "bd_mtd": "사채만기일",
    "bdis_mthn": "사채발행방법",
    "cv_rt": "전환비율",
    "cv_prc": "전환가액",
    "ex_prc": "행사가액/교환가액",
    "cvisstk_knd": "전환발행 주식 종류",
    "cvisstk_cnt": "전환가능주식수",
    "cvisstk_tisstk_vs": "희석률",
    "nstk_isstk_cnt": "신주인수권 행사 가능 주식수",
    "nstk_isstk_tisstk_vs": "행사 주식총수 대비 비율",
    "extg_stkcnt": "교환대상 주식수",
    "extg_tisstk_vs": "교환대상 주식총수 대비 비율",
    "cvrqpd_bgd": "전환청구시작일",
    "cvrqpd_edd": "전환청구종료일",
    "expd_bgd": "신주인수권 행사시작일",
    "expd_edd": "신주인수권 행사종료일",
    "exrqpd_bgd": "교환청구시작일",
    "exrqpd_edd": "교환청구종료일",
    "act_mktprcfl_cvprc_lwtrsprc": "최저조정가액",
    "act_mktprcfl_cvprc_lwtrsprc_bs": "최저조정가액 근거",
    "rmislmt_lt70p": "70% 미만 조정 가능 잔여한도",
    "sbd": "청약일",
    "pymd": "납입일",
    "rpmcmp": "대표주관회사",
    "grint": "보증기관",
    "bddd": "이사회결의일",
    "rs_sm_atn": "증권신고서 제출대상 여부",
    "ex_sm_r": "제출 면제 사유",
    "disclosure_type": "공시구분",
    "disclosure_name": "공시유형",
    "event_date": "발행결정일",
    "payment_date": "납입일",
    "conversion_start_date": "전환청구 시작일",
    "conversion_end_date": "전환청구 종료일",
    "maturity_date": "사채만기일",
    "potential_share_count": "전환/행사/교환 가능 주식수",
    "calendar_size": "표시 물량",
    "ISIN": "종목코드(ISIN)",
    "KOR_SECN_NM": "종목명",
    "SECN_KACD_NM": "채권분류",
    "OPTION_TPCD_NM": "옵션",
    "PARTICUL_BOND_KIND": "주식관련사채 종류",
    "PARTICUL_BOND_KIND_TPCD_NM": "주식관련사채 구분",
    "ISSU_CUR_CD": "발행통화",
    "REP_SECN_NM": "발행자",
    "ISSU_DT": "발행일",
    "XPIR_DT": "만기일",
    "FIRST_ISSU_AMT": "발행금액",
    "ISSU_REMA": "발행잔액",
    "COUPON_RATE": "표면금리",
    "XPIR_GUAR_PRATE": "만기보장수익률",
    "INT_KIND": "이자유형",
    "PRIN_RCV_FNCECO": "원리금지급기관/지점",
    "RECU_WHCD_NM": "공모/사모",
    "RANK_TPCD_NM": "선후순위 구분",
    "SEIBro_ISIN": "SEIBro 종목코드(ISIN)",
    "SEIBro_종목명": "SEIBro 종목명",
    "SEIBro_발행잔액": "SEIBro 발행잔액",
    "SEIBro_발행잔액_원문": "SEIBro 발행잔액(원문)",
    "SEIBro_발행금액": "SEIBro 발행금액",
    "SEIBro_발행금액_원문": "SEIBro 발행금액(원문)",
    "SEIBro_매핑회차": "SEIBro 매핑회차",
    "SEIBro_매핑상태": "SEIBro 매핑상태",
    "SEIBro_매핑점수": "SEIBro 매핑점수",
    "SEIBro_잔액존재": "SEIBro 잔액존재",
    "event_date_source": "발행결정일 출처",
    "payment_date_source": "납입일 출처",
    "conversion_start_date_source": "권리행사 시작일 출처",
    "conversion_end_date_source": "권리행사 종료일 출처",
    "conversion_period": "전환청구기간",
    "conversion_status": "전환청구 상태",
    "days_to_conversion_start": "전환청구 시작 D-Day",
    "funding_purpose_total": "자금사용 합계",
    "잔여권면총액_추정": "잔여 권면총액(추정)",
    "잔여가능주식수_추정": "잔여 가능주식수(추정)",
    "잔여시총대비비율_추정": "잔여 시총대비 비율(추정)",
    "잔여주식가치_추정": "잔여 주식가치(추정)",
    "추적차감권면총액": "추적 차감 권면총액",
    "추적차감주식수": "추적 차감 주식수",
    "잔여물량추적상태": "잔여물량 추적상태",
}


def get_open_dart_api_key():
    env_key = os.getenv("OPEN_DART_API_KEY")

    if env_key:
        return env_key

    secrets_paths = [
        Path.home() / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
    ]

    if any(path.exists() for path in secrets_paths):
        return st.secrets.get("OPEN_DART_API_KEY", DEFAULT_OPEN_DART_API_KEY)

    return DEFAULT_OPEN_DART_API_KEY


def normalize_date(value):
    if isinstance(value, tuple):
        value = value[0] if value else date.today()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.today()


def clean_number(value):
    if pd.isna(value):
        return np.nan

    text = str(value).replace(",", "").replace("%", "").strip()

    if text in {"", "-", "None", "null"}:
        return np.nan

    return pd.to_numeric(text, errors="coerce")


def first_available_number(row, candidates):
    for column in candidates:
        if column not in row.index:
            continue

        value = clean_number(row.get(column))

        if pd.notna(value):
            return value

    return np.nan


def parse_date(value):
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value.normalize()

    if isinstance(value, datetime):
        return pd.Timestamp(value.date())

    if isinstance(value, date):
        return pd.Timestamp(value)

    text = str(value).strip()

    if text in {"", "-", "None", "null", "nan", "NaT"}:
        return pd.NaT

    digit_text = "".join(re.findall(r"\d", text))

    if len(digit_text) >= 8:
        digit_text = digit_text[:8]
    else:
        return pd.NaT

    if len(digit_text) != 8:
        return pd.NaT

    return pd.to_datetime(digit_text, format="%Y%m%d", errors="coerce")


def extract_date_with_source(row, candidates, fallback_from_rcept_no=False):
    for column in candidates:
        if column not in row.index:
            continue

        parsed = parse_date(row.get(column))

        if pd.notna(parsed):
            return parsed, column

    if fallback_from_rcept_no:
        rcept_no = clean_display_text(row.get("rcept_no"))
        parsed = parse_date(rcept_no[:8])

        if pd.notna(parsed):
            return parsed, "rcept_no"

    return pd.NaT, ""


def fill_date_column_from_candidates(df, target_column, candidates, fallback_from_rcept_no=False):
    extracted = df.apply(
        lambda row: extract_date_with_source(row, candidates, fallback_from_rcept_no=fallback_from_rcept_no),
        axis=1,
    )
    df[target_column] = extracted.apply(lambda value: value[0])
    df[f"{target_column}_source"] = extracted.apply(lambda value: value[1])
    return df


def to_korean_columns(df):
    renamed = df.rename(columns={col: KOREAN_COLUMN_NAMES.get(col, col) for col in df.columns}).copy()
    counts = {}
    unique_columns = []

    for column in renamed.columns:
        counts[column] = counts.get(column, 0) + 1
        unique_columns.append(column if counts[column] == 1 else f"{column}_{counts[column]}")

    renamed.columns = unique_columns
    return renamed


def korean_labels(columns):
    return {column: KOREAN_COLUMN_NAMES.get(column, column) for column in columns}


def clean_display_text(value):
    if pd.isna(value):
        return ""

    return " ".join(str(value).replace("\xa0", " ").split())


def flatten_table_columns(df):
    flattened = df.copy()

    if isinstance(flattened.columns, pd.MultiIndex):
        flattened.columns = [
            " ".join(
                clean_display_text(part)
                for part in column
                if clean_display_text(part) and not clean_display_text(part).startswith("Unnamed")
            )
            or f"컬럼{index + 1}"
            for index, column in enumerate(flattened.columns)
        ]
    else:
        flattened.columns = [
            clean_display_text(column) if clean_display_text(column) and not clean_display_text(column).startswith("Unnamed")
            else f"컬럼{index + 1}"
            for index, column in enumerate(flattened.columns)
        ]

    flattened = flattened.applymap(clean_display_text)
    flattened = flattened.replace("", np.nan).dropna(how="all").dropna(axis=1, how="all").fillna("")
    return flattened


def table_contains_keywords(df, keywords):
    text = " ".join(clean_display_text(value) for value in df.to_numpy().ravel())
    text += " " + " ".join(clean_display_text(column) for column in df.columns)
    return any(keyword in text for keyword in keywords)


def filter_document_tables(tables, keywords):
    return [
        (index, table)
        for index, table in enumerate(tables, start=1)
        if table_contains_keywords(table, keywords)
    ]


def extract_round_number(value):
    text = clean_display_text(value)
    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def extract_amount_from_text(text):
    text = clean_display_text(text)
    number_matches = re.findall(r"\d[\d,]*", text)

    if not number_matches:
        return np.nan

    value = clean_number(number_matches[0])

    if pd.isna(value):
        return np.nan

    if "억원" in text:
        return value * 100000000

    if "백만원" in text:
        return value * 1000000

    if "천원" in text:
        return value * 1000

    return value


def extract_tracking_event_from_tables(report_name, tables):
    text = clean_display_text(report_name) + " "
    text += " ".join(
        clean_display_text(value)
        for table in tables
        for value in table.to_numpy().ravel()
    )

    event_type = "기타"
    if any(keyword in text for keyword in ["전환청구", "전환권행사", "전환권 행사"]):
        event_type = "전환행사"
    elif any(keyword in text for keyword in ["신주인수권행사", "신주인수권 행사"]):
        event_type = "신주인수권행사"
    elif any(keyword in text for keyword in ["교환청구", "교환권행사", "교환권 행사"]):
        event_type = "교환청구"
    elif any(keyword in text for keyword in ["만기전 취득", "만기전사채취득", "사채 취득", "소각"]):
        event_type = "만기전취득/소각"
    elif any(keyword in text for keyword in ["조기상환"]):
        event_type = "조기상환"

    round_number = extract_round_number(text)
    amount = np.nan
    shares = np.nan

    for table in tables:
        for _, row in table.iterrows():
            row_text = " ".join(clean_display_text(value) for value in row.tolist())

            if pd.isna(amount) and any(keyword in row_text for keyword in ["권면", "사채", "금액", "취득", "상환"]):
                amount = extract_amount_from_text(row_text)

            if pd.isna(shares) and any(keyword in row_text for keyword in ["주식수", "행사주식", "전환주식", "교환주식"]):
                shares = extract_amount_from_text(row_text)

            if not round_number and any(keyword in row_text for keyword in ["회차", "회"]):
                round_number = extract_round_number(row_text)

    return {
        "추적공시유형": event_type,
        "추적회차": round_number,
        "차감권면총액": amount,
        "차감주식수": shares,
    }


@st.cache_data(ttl=60 * 60)
def get_disclosure_list(api_key, corp_code, start_date, end_date, page_count=100):
    all_rows = []
    page_no = 1

    while True:
        response = requests.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": start_date.strftime("%Y%m%d"),
                "end_de": end_date.strftime("%Y%m%d"),
                "last_reprt_at": "Y",
                "sort": "date",
                "sort_mth": "desc",
                "page_no": page_no,
                "page_count": page_count,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "013":
            break

        if data.get("status") != "000":
            raise ValueError(data.get("message", "공시 목록 조회 실패"))

        all_rows.extend(data.get("list", []))

        total_page = int(data.get("total_page", page_no))
        if page_no >= total_page:
            break

        page_no += 1

    return pd.DataFrame(all_rows)


@st.cache_data(ttl=60 * 60)
def build_remaining_tracking_events(api_key, corp_code, start_date, end_date, max_documents=30):
    disclosure_list = get_disclosure_list(api_key, corp_code, start_date, end_date)

    if disclosure_list.empty or "report_nm" not in disclosure_list.columns:
        return pd.DataFrame()

    keywords = [
        "전환청구",
        "전환권행사",
        "신주인수권행사",
        "교환청구",
        "교환권행사",
        "만기전",
        "사채취득",
        "조기상환",
        "소각",
    ]
    matched = disclosure_list[
        disclosure_list["report_nm"].apply(lambda value: any(keyword in clean_display_text(value) for keyword in keywords))
    ].head(max_documents)

    events = []

    for _, row in matched.iterrows():
        rcept_no = row.get("rcept_no")

        if not rcept_no:
            continue

        try:
            tables = get_disclosure_document_tables(api_key, rcept_no)
        except (requests.RequestException, ValueError):
            tables = []

        event = extract_tracking_event_from_tables(row.get("report_nm", ""), tables)
        event.update(
            {
                "추적공시명": row.get("report_nm"),
                "추적접수번호": rcept_no,
                "추적접수일": parse_date(rcept_no[:8]),
            }
        )
        events.append(event)

    return pd.DataFrame(events)


def build_funding_purpose_df(mezz_df):
    purpose_columns = ["fdpp_fclt", "fdpp_bsninh", "fdpp_op", "fdpp_dtrp", "fdpp_ocsa", "fdpp_etc"]
    base_columns = [col for col in ["disclosure_name", "corp_name", "bd_tm", "event_date", "bd_fta"] if col in mezz_df.columns]
    available_purpose_columns = [col for col in purpose_columns if col in mezz_df.columns]

    if not available_purpose_columns:
        return pd.DataFrame()

    funding_df = mezz_df[base_columns + available_purpose_columns].copy()

    for column in available_purpose_columns:
        funding_df[column] = funding_df[column].apply(clean_number)

    funding_df["funding_purpose_total"] = funding_df[available_purpose_columns].sum(axis=1, min_count=1)
    return funding_df


@st.cache_data(ttl=60 * 60)
def get_disclosure_document_tables(api_key, rcept_no):
    url = "https://opendart.fss.or.kr/api/document.xml"
    response = requests.get(url, params={"crtfc_key": api_key, "rcept_no": rcept_no}, timeout=20)
    response.raise_for_status()

    if not response.content.startswith(b"PK"):
        try:
            root = ET.fromstring(response.content)
            message = root.findtext("message") or "공시 원문을 내려받을 수 없습니다."
        except ET.ParseError:
            message = "공시 원문 응답을 해석할 수 없습니다."

        raise ValueError(message)

    tables = []

    with ZipFile(BytesIO(response.content)) as zip_file:
        for name in zip_file.namelist():
            raw_document = zip_file.read(name)
            document_text = None

            for encoding in ("utf-8", "euc-kr", "cp949"):
                try:
                    document_text = raw_document.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if not document_text:
                continue

            try:
                html_tables = pd.read_html(StringIO(document_text))
            except (ImportError, ValueError):
                continue

            tables.extend(flatten_table_columns(table) for table in html_tables if not table.empty)

    return tables


# --- Seibro integration helpers ---
def _seibro_post(session, req_param_xml: str, action: str = "", task: str = "", extra: dict = None):
    """Post a WebSquare-style request to Seibro's callServletService.jsp and return response text.

    This helper mirrors the observed WebSquare POST pattern. Failures raise
    requests.RequestException so callers can handle network errors without
    breaking the main app.
    """
    url = "https://seibro.or.kr/websquare/engine/proworks/callServletService.jsp"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "python-requests/SeibroClient",
    }
    # Seibro expects action/task as attributes on the <reqParam> element in many endpoints.
    req = req_param_xml or "<reqParam/>"
    if action or task:
        # If <reqParam already has attributes, skip naive injection
        if req.lstrip().startswith("<reqParam") and "action=" not in req and "task=" not in req:
            insert_attrs = []
            if action:
                insert_attrs.append(f'action="{action}"')
            if task:
                insert_attrs.append(f'task="{task}"')
            req = req.replace("<reqParam", "<reqParam " + " ".join(insert_attrs), 1)

    data = {"reqParam": req}
    if extra:
        data.update(extra)

    resp = session.post(url, headers=headers, data=data, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_seibro_xml_to_df(xml_text: str, record_tag: str):
    """Parse a Seibro XML response into a DataFrame by extracting repeated `record_tag` nodes."""
    try:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_text)
    except Exception:
        return pd.DataFrame()

    records = []
    for rec in root.findall(f".//{record_tag}"):
        entry = {}
        for child in rec:
            # Seibro typically encodes values as attributes on child tags
            val = child.get("value") if child.get("value") is not None else (child.text.strip() if child.text else None)
            entry[child.tag] = val
        records.append(entry)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def fetch_seibro_issuance_list(isin: str = None, corp_name: str = None, issue_start_date=None, issue_end_date=None):
    """Fetch issuance/list data from Seibro. Pass `isin` or `corp_name`.

    Returns a DataFrame (empty if no data). May raise requests.RequestException
    on network errors.
    """
    import requests

    session = requests.Session()
    post_url = "https://seibro.or.kr/websquare/engine/proworks/callServletService.jsp"

    # Choose control page and default action
    issue_start_date = normalize_date(issue_start_date or OPENDART_DATA_START_DATE)
    issue_end_date = normalize_date(issue_end_date or date.today())
    start_text = issue_start_date.strftime("%Y%m%d")
    end_text = issue_end_date.strftime("%Y%m%d")
    safe_corp_name = html.escape(corp_name or "")
    safe_isin = html.escape(isin or "")

    if isin:
        control_url = f"https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/bond/BIP_CNTS03004V.xml&ISIN={isin}&menuNo=415"
        req_root = (
            f'<reqParam action="issuInfoViewEL1" task="ksd.safe.bip.cnts.bone.process.BondSecnDetailPTask">'
            f'<ISIN value="{safe_isin}"/>'
            "</reqParam>"
        )
        action = "issuInfoViewEL1"
    else:
        control_url = "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/bond/BIP_CNTS03018V.xml&menuNo=104"
        req_root = (
            '<reqParam action="issuSecnPListEL1" task="ksd.safe.bip.cnts.bone.process.StkRlCbondIssuSecnPTask">'
            f'<ISSU_DT_START value="{start_text}"/>'
            f'<ISSU_DT_END value="{end_text}"/>'
            '<XPIR_DT_START value=""/>'
            '<XPIR_DT_END value=""/>'
            '<ISSUCO_CUSTNO value=""/>'
            '<ISIN value=""/>'
            '<INDTP_CLSF_NO value=""/>'
            '<SELECT_XPIR_DT_START value=""/>'
            '<SELECT_XPIR_DT_END value=""/>'
            '<PARTICUL_BOND_KIND_TPCD value=""/>'
            '<CREDIT_GRD_CD value=""/>'
            '<XPIR_GUAR_PRATE1 value=""/>'
            '<XPIR_GUAR_PRATE2 value=""/>'
            '<LIST_TPCD value=""/>'
            '<PAGE_ON_CNT value="10000"/>'
            '<PAGE_NUM value="1"/>'
            "</reqParam>"
        )
        action = "issuSecnPListEL1"

    # try to establish session cookies
    try:
        session.get(control_url, timeout=15)
    except requests.RequestException:
        pass

    headers = {
        "Content-Type": 'application/xml; charset="UTF-8"',
        "Accept": "application/xml",
        "Referer": control_url,
        "submissionid": f"submission_{action}",
        "User-Agent": "python-requests/SeibroClient",
    }

    resp = session.post(post_url, data=req_root, headers=headers, timeout=20)
    resp.raise_for_status()
    text = resp.text

    for tag in ("result", "row", "issuSecnPListEL1", "item"):
        df = parse_seibro_xml_to_df(text, tag)
        if not df.empty:
            if corp_name and not isin:
                query = clean_display_text(corp_name)
                search_cols = [col for col in ["REP_SECN_NM", "KOR_SECN_NM"] if col in df.columns]

                if search_cols:
                    mask = pd.Series(False, index=df.index)
                    for col in search_cols:
                        mask = mask | df[col].fillna("").astype(str).str.contains(query, case=False, na=False, regex=False)
                    df = df[mask].copy()

            return df

    return pd.DataFrame()


@st.cache_data(ttl=60 * 10)
def find_seibro_isins(company_name: str):
    """Return a list of ISIN codes for a given company name by querying SEIBro."""
    if not company_name:
        return []

    try:
        df = fetch_seibro_issuance_list(corp_name=company_name)
    except Exception:
        return []

    if df.empty:
        return []

    # find a column that looks like ISIN
    isin_col = None
    for col in df.columns:
        if col.lower() == "isin" or "isin" in col.lower():
            isin_col = col
            break

    if isin_col is None:
        # try values fallback: search for 12-character tokens starting with 'KR'
        vals = []
        for _, row in df.iterrows():
            for v in row.values:
                if isinstance(v, str) and v.upper().startswith("KR") and len(v.strip()) >= 12:
                    vals.append(v.strip())
        return list(dict.fromkeys(vals))

    isins = df[isin_col].dropna().astype(str).str.strip().unique().tolist()
    return [i for i in isins if i]


def find_column_by_keywords(df, keywords):
    for column in df.columns:
        lowered = str(column).lower()
        if any(keyword.lower() in lowered for keyword in keywords):
            return column
    return None


def extract_seibro_isin_options(df):
    if df.empty:
        return []

    isin_col = find_column_by_keywords(df, ["isin", "종목코드", "표준코드"])
    name_col = find_column_by_keywords(df, ["종목명", "채권명", "한글종목명", "secn", "bond"])
    issue_date_col = find_column_by_keywords(df, ["발행일", "issu_dt", "issue"])
    maturity_col = find_column_by_keywords(df, ["만기", "matu"])

    options = []
    seen = set()

    for _, row in df.iterrows():
        raw_isin = clean_display_text(row.get(isin_col)) if isin_col else ""

        if not raw_isin:
            for value in row.values:
                value_text = clean_display_text(value)
                match = re.search(r"KR[A-Z0-9]{10}", value_text.upper())
                if match:
                    raw_isin = match.group(0)
                    break

        if not raw_isin or raw_isin in seen:
            continue

        seen.add(raw_isin)
        bond_name = clean_display_text(row.get(name_col)) if name_col else ""
        issue_date = clean_display_text(row.get(issue_date_col)) if issue_date_col else ""
        maturity_date = clean_display_text(row.get(maturity_col)) if maturity_col else ""
        label_parts = [raw_isin]

        if bond_name:
            label_parts.append(bond_name)

        if issue_date:
            label_parts.append(f"발행일 {issue_date}")

        if maturity_date:
            label_parts.append(f"만기 {maturity_date}")

        options.append(
            {
                "isin": raw_isin,
                "label": " / ".join(label_parts),
            }
        )

    return options


def normalize_match_text(value):
    return re.sub(r"\s+", "", clean_display_text(value)).lower()


def seibro_bond_type(disclosure_type):
    return {
        "CB": "전환",
        "BW": "신주",
        "EB": "교환",
    }.get(disclosure_type, "")


def date_distance_days(left, right):
    left = parse_date(left)
    right = parse_date(right)

    if pd.isna(left) or pd.isna(right):
        return np.nan

    return abs((left - right).days)


@st.cache_data(ttl=60 * 60)
def fetch_seibro_remaining_bonds(company_name, issue_start_date, issue_end_date):
    seibro_df = fetch_seibro_issuance_list(
        corp_name=company_name,
        issue_start_date=issue_start_date,
        issue_end_date=issue_end_date,
    )

    if seibro_df.empty:
        return seibro_df

    if "ISSU_REMA" in seibro_df.columns:
        seibro_df["SEIBro_발행잔액_원문"] = seibro_df["ISSU_REMA"]
        seibro_df["SEIBro_발행잔액"] = seibro_df["ISSU_REMA"].apply(clean_number)
    else:
        seibro_df["SEIBro_발행잔액_원문"] = ""
        seibro_df["SEIBro_발행잔액"] = np.nan

    if "FIRST_ISSU_AMT" in seibro_df.columns:
        seibro_df["SEIBro_발행금액_원문"] = seibro_df["FIRST_ISSU_AMT"]
        seibro_df["SEIBro_발행금액"] = seibro_df["FIRST_ISSU_AMT"].apply(clean_number)
    else:
        seibro_df["SEIBro_발행금액_원문"] = ""
        seibro_df["SEIBro_발행금액"] = np.nan

    seibro_df["SEIBro_매핑회차"] = seibro_df.apply(
        lambda row: extract_round_number(row.get("KOR_SECN_NM")) or extract_round_number(row.get("NUM")),
        axis=1,
    )
    return seibro_df.copy()


def score_seibro_match(dart_row, seibro_row):
    score = 0
    dart_round = extract_round_number(dart_row.get("bd_tm"))
    bond_name = normalize_match_text(seibro_row.get("KOR_SECN_NM"))
    issuer_name = normalize_match_text(seibro_row.get("REP_SECN_NM"))
    dart_company = normalize_match_text(dart_row.get("corp_name"))
    dart_type = seibro_bond_type(dart_row.get("disclosure_type"))

    if dart_company and (dart_company in issuer_name or issuer_name in dart_company):
        score += 25

    if dart_round and dart_round in bond_name:
        score += 30

    if dart_type and dart_type in clean_display_text(seibro_row.get("SECN_KACD", "")) + clean_display_text(seibro_row.get("KOR_SECN_NM", "")):
        score += 15

    issue_gap = date_distance_days(dart_row.get("event_date"), seibro_row.get("ISSU_DT"))
    if pd.notna(issue_gap):
        if issue_gap <= 7:
            score += 20
        elif issue_gap <= 45:
            score += 10

    maturity_gap = date_distance_days(dart_row.get("maturity_date"), seibro_row.get("XPIR_DT"))
    if pd.notna(maturity_gap):
        if maturity_gap <= 3:
            score += 20
        elif maturity_gap <= 30:
            score += 10

    dart_amount = dart_row.get("발행금액")
    seibro_amount = seibro_row.get("SEIBro_발행금액")
    if pd.notna(dart_amount) and pd.notna(seibro_amount) and max(dart_amount, seibro_amount) > 0:
        amount_gap = abs(dart_amount - seibro_amount) / max(dart_amount, seibro_amount)
        if amount_gap <= 0.01:
            score += 25
        elif amount_gap <= 0.10:
            score += 12

    return score


def attach_seibro_remaining_to_dart(mezz_df, seibro_remaining_df):
    mapped = mezz_df.copy()
    mapped["SEIBro_ISIN"] = ""
    mapped["SEIBro_종목명"] = ""
    mapped["SEIBro_발행잔액"] = np.nan
    mapped["SEIBro_발행잔액_원문"] = ""
    mapped["SEIBro_발행금액"] = np.nan
    mapped["SEIBro_발행금액_원문"] = ""
    mapped["SEIBro_매핑회차"] = ""
    mapped["SEIBro_매핑상태"] = "동일 회차 후보 없음"
    mapped["SEIBro_매핑점수"] = 0
    mapped["SEIBro_잔액존재"] = False

    if seibro_remaining_df.empty:
        return mapped

    for index, dart_row in mapped.iterrows():
        dart_round = extract_round_number(dart_row.get("bd_tm"))

        if not dart_round:
            mapped.at[index, "SEIBro_매핑상태"] = "OpenDART 회차 없음"
            continue

        round_candidates = seibro_remaining_df[
            seibro_remaining_df.get("SEIBro_매핑회차", pd.Series("", index=seibro_remaining_df.index)).astype(str)
            == dart_round
        ].copy()

        if round_candidates.empty:
            mapped.at[index, "SEIBro_매핑상태"] = "동일 회차 후보 없음"
            continue

        scored_rows = []

        for _, seibro_row in round_candidates.iterrows():
            score = score_seibro_match(dart_row, seibro_row)
            scored_rows.append((score, seibro_row))

        if not scored_rows:
            continue

        best_score, best_row = max(scored_rows, key=lambda item: item[0])

        mapped.at[index, "SEIBro_ISIN"] = clean_display_text(best_row.get("ISIN"))
        mapped.at[index, "SEIBro_종목명"] = clean_display_text(best_row.get("KOR_SECN_NM"))
        mapped.at[index, "SEIBro_발행잔액"] = best_row.get("SEIBro_발행잔액")
        mapped.at[index, "SEIBro_발행잔액_원문"] = best_row.get("SEIBro_발행잔액_원문")
        mapped.at[index, "SEIBro_발행금액"] = best_row.get("SEIBro_발행금액")
        mapped.at[index, "SEIBro_발행금액_원문"] = best_row.get("SEIBro_발행금액_원문")
        mapped.at[index, "SEIBro_매핑회차"] = best_row.get("SEIBro_매핑회차")
        mapped.at[index, "SEIBro_매핑상태"] = "동일 회차 매핑"
        mapped.at[index, "SEIBro_매핑점수"] = best_score
        mapped.at[index, "SEIBro_잔액존재"] = pd.notna(best_row.get("SEIBro_발행잔액")) and best_row.get("SEIBro_발행잔액") > 0

    return mapped


def seibro_section_df(row, keywords):
    matched = {}

    for column, value in row.items():
        column_text = clean_display_text(column)
        value_text = clean_display_text(value)

        if not value_text:
            continue

        if any(keyword.lower() in column_text.lower() for keyword in keywords):
            matched[column] = value

    if not matched:
        return pd.DataFrame()

    return pd.DataFrame(
        [{"항목": KOREAN_COLUMN_NAMES.get(column, column), "값": value} for column, value in matched.items()]
    )


@st.cache_data(ttl=60 * 10)
def fetch_seibro_mobile_bond_tables(isin, bond_name=""):
    if not isin:
        return []

    response = requests.get(
        "https://m.seibro.or.kr/cnts/bond/selectDetailSearch.do",
        params={"InOrdSel": "all", "txt_code": isin, "txt_sch": bond_name or isin},
        timeout=20,
    )
    response.raise_for_status()

    try:
        tables = pd.read_html(StringIO(response.text))
    except ValueError:
        return []

    cleaned_tables = []
    for table in tables:
        cleaned = flatten_table_columns(table)
        if not cleaned.empty:
            cleaned_tables.append(cleaned)

    return cleaned_tables


def classify_seibro_mobile_tables(tables):
    sections = {
        "채권원리금": [],
        "수익률": [],
        "조기행사옵션": [],
        "주식관련옵션": [],
        "기타": [],
    }

    for table in tables:
        table_text = " ".join(clean_display_text(value) for value in table.to_numpy().ravel())
        table_text += " " + " ".join(clean_display_text(column) for column in table.columns)

        if any(keyword in table_text for keyword in ["지급일", "지급액", "원리금", "이자", "원금상환", "표면금리"]):
            sections["채권원리금"].append(table)
        elif any(keyword in table_text for keyword in ["수익률", "보장", "금리", "PRATE", "RATE"]):
            sections["수익률"].append(table)
        elif any(keyword in table_text for keyword in ["조기상환", "행사시작일", "행사종료일", "CALL", "PUT"]):
            sections["조기행사옵션"].append(table)
        elif any(keyword in table_text for keyword in ["주식관련", "대상 주식", "행사 가격", "행사 비율", "Warrant", "전환", "교환"]):
            sections["주식관련옵션"].append(table)
        else:
            sections["기타"].append(table)

    return sections


def first_trading_row_on_or_after(df, date_value):
    date_value = pd.to_datetime(date_value)
    matched = df[df["날짜"] >= date_value]
    return None if matched.empty else matched.iloc[0]


def last_trading_row_on_or_before(df, date_value):
    date_value = pd.to_datetime(date_value)
    matched = df[df["날짜"] <= date_value]
    return None if matched.empty else matched.iloc[-1]


def trading_day_after(df, start_value, trading_days):
    start_value = pd.to_datetime(start_value)
    matched = df[df["날짜"] >= start_value]

    if matched.empty:
        return pd.NaT

    index = min(max(trading_days, 0), len(matched) - 1)
    return matched.iloc[index]["날짜"]


@st.cache_data(ttl=60 * 60 * 24)
def download_corp_codes(api_key):
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    response = requests.get(url, params={"crtfc_key": api_key}, timeout=20)
    response.raise_for_status()

    with ZipFile(BytesIO(response.content)) as zip_file:
        xml_name = zip_file.namelist()[0]
        xml_data = zip_file.read(xml_name)

    root = ET.fromstring(xml_data)
    corp_list = []

    for child in root.findall("list"):
        stock_code = child.findtext("stock_code")

        if stock_code and stock_code.strip():
            corp_list.append(
                {
                    "corp_code": child.findtext("corp_code"),
                    "corp_name": child.findtext("corp_name"),
                    "stock_code": stock_code.strip(),
                }
            )

    return pd.DataFrame(corp_list, columns=["corp_code", "corp_name", "stock_code"])


@st.cache_data(ttl=60 * 10)
def get_mezzanine_disclosure_data(api_key, corp_code, start_date, end_date, disclosure_api):
    url = f"https://opendart.fss.or.kr/api/{disclosure_api['endpoint']}.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": start_date.strftime("%Y%m%d"),
        "end_de": end_date.strftime("%Y%m%d"),
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    if data.get("status") not in {"000", "013"}:
        st.error(f"{disclosure_api['name']} DART API 오류: {data.get('message', '알 수 없는 오류')}")
        return pd.DataFrame()

    df = pd.DataFrame(data.get("list", []))

    if df.empty:
        return df

    df["disclosure_type"] = disclosure_api["type"]
    df["disclosure_name"] = disclosure_api["name"]
    return df


@st.cache_data(ttl=60 * 10)
def get_all_mezzanine_data(api_key, corp_code, start_date, end_date, selected_types):
    dataframes = []

    for disclosure_api in MEZZANINE_DISCLOSURE_APIS:
        if disclosure_api["type"] not in selected_types:
            continue

        try:
            df = get_mezzanine_disclosure_data(api_key, corp_code, start_date, end_date, disclosure_api)
        except requests.RequestException as error:
            st.warning(f"{disclosure_api['name']} 공시 조회 실패: {error}")
            continue

        if not df.empty:
            dataframes.append(df)

    if not dataframes:
        return pd.DataFrame()

    return pd.concat(dataframes, ignore_index=True, sort=False)


@st.cache_data(ttl=60 * 10)
def get_price(stock_code, start_yyyymmdd, end_yyyymmdd):
    try:
        df = stock.get_market_ohlcv(start_yyyymmdd, end_yyyymmdd, stock_code)
    except (KeyError, ValueError, IndexError):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    df.rename(columns={df.columns[0]: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"])
    return df


@st.cache_data(ttl=60 * 10)
def get_benchmark_price(index_code, start_yyyymmdd, end_yyyymmdd):
    try:
        df = stock.get_index_ohlcv_by_date(start_yyyymmdd, end_yyyymmdd, index_code)
    except (KeyError, ValueError, IndexError):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    df.rename(columns={df.columns[0]: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"])
    return df


@st.cache_data(ttl=60 * 10)
def get_market_cap(stock_code, date_text):
    try:
        cap_df = stock.get_market_cap_by_date(date_text, date_text, stock_code)
        if not cap_df.empty and "시가총액" in cap_df.columns:
            return cap_df.iloc[-1]["시가총액"]
    except Exception:
        pass

    try:
        cap_df = stock.get_market_cap_by_ticker(date_text)
        if not cap_df.empty and stock_code in cap_df.index and "시가총액" in cap_df.columns:
            return cap_df.loc[stock_code, "시가총액"]
    except Exception:
        pass

    return np.nan


def get_recent_market_cap(stock_code, base_date, lookback_days=14):
    base_date = normalize_date(base_date)

    for days_back in range(lookback_days + 1):
        date_value = base_date - timedelta(days=days_back)
        market_cap = get_market_cap(stock_code, date_value.strftime("%Y%m%d"))

        if pd.notna(market_cap) and market_cap > 0:
            return market_cap, date_value

    return np.nan, pd.NaT


DEFAULT_RISK_WEIGHTS = {
    "dilution": 30,
    "gap": 30,
    "cb_ratio": 25,
    "refixing": 15,
    "zero_coupon": 5,
    "high_yield": 10,
}


def calculate_risk_components(row, weights=None):
    weights = weights or DEFAULT_RISK_WEIGHTS
    components = {
        "희석률 점수": 0.0,
        "전환가괴리율 점수": 0.0,
        "시총대비CB비율 점수": 0.0,
        "리픽싱 점수": 0.0,
        "무이자 점수": 0.0,
        "고금리 점수": 0.0,
    }
    dilution = row.get("희석률")
    gap_ratio = row.get("전환가괴리율")
    cb_ratio = row.get("시총대비CB비율")
    floor_price = row.get("최저조정가액")
    surface_rate = row.get("표면이자율")
    maturity_rate = row.get("만기이자율")

    if pd.notna(dilution):
        if dilution >= 30:
            components["희석률 점수"] = weights["dilution"]
        elif dilution >= 20:
            components["희석률 점수"] = weights["dilution"] * 2 / 3
        elif dilution >= 10:
            components["희석률 점수"] = weights["dilution"] / 3

    if pd.notna(gap_ratio):
        if gap_ratio < 0.8:
            components["전환가괴리율 점수"] = weights["gap"]
        elif gap_ratio < 1.0:
            components["전환가괴리율 점수"] = weights["gap"] * 2 / 3
        elif gap_ratio < 1.2:
            components["전환가괴리율 점수"] = weights["gap"] / 3

    if pd.notna(cb_ratio):
        if cb_ratio >= 50:
            components["시총대비CB비율 점수"] = weights["cb_ratio"]
        elif cb_ratio >= 30:
            components["시총대비CB비율 점수"] = weights["cb_ratio"] * 0.6
        elif cb_ratio >= 10:
            components["시총대비CB비율 점수"] = weights["cb_ratio"] * 0.32

    if pd.notna(floor_price):
        components["리픽싱 점수"] = weights["refixing"]

    if pd.notna(surface_rate) and surface_rate <= 0:
        components["무이자 점수"] = weights["zero_coupon"]

    if pd.notna(maturity_rate) and maturity_rate >= 8:
        components["고금리 점수"] = weights["high_yield"]

    return components


def calculate_risk_score(row, weights=None):
    return min(sum(calculate_risk_components(row, weights).values()), 100)


def risk_label(score):
    if score >= 80:
        return "매우위험"
    if score >= 60:
        return "위험"
    if score >= 40:
        return "주의"
    return "낮음"


def risk_color(score):
    if score >= 70:
        return "#dc2626"
    if score >= 40:
        return "#f59e0b"
    return "#16a34a"


def nearest_trading_date(price_df, event_date):
    event_price_row = first_trading_row_on_or_after(price_df, event_date)

    if event_price_row is None:
        return pd.NaT

    return event_price_row["날짜"]


def chart_event_date(price_df, event_date):
    if pd.isna(event_date):
        return pd.NaT

    event_date = pd.to_datetime(event_date)

    if price_df.empty:
        return event_date

    if event_date > price_df["날짜"].max() or event_date < price_df["날짜"].min():
        return event_date

    nearest_date = nearest_trading_date(price_df, event_date)
    return event_date if pd.isna(nearest_date) else nearest_date


def add_vertical_event(fig, x_value, label, color, dash="dash"):
    fig.add_shape(
        type="line",
        x0=x_value,
        x1=x_value,
        y0=0,
        y1=1,
        xref="x",
        yref="paper",
        line={"color": color, "width": 2.5, "dash": dash},
        opacity=0.8,
        layer="above",
    )
    fig.add_annotation(
        x=x_value,
        y=1,
        yref="paper",
        text=label,
        showarrow=False,
        yanchor="bottom",
        font={"color": color, "size": 11},
    )


def add_event_lines(fig, event_rows, price_df, event_specs=None, highlight_period=None):
    event_specs = event_specs or [
        ("event_date", "발행", "#e11d48", "dash"),
        ("payment_date", "납입", "#f59e0b", "dot"),
        ("conversion_start_date", "전환시작", "#2563eb", "dash"),
        ("conversion_end_date", "전환종료", "#16a34a", "dot"),
    ]

    for _, row in event_rows.iterrows():
        issue_date = row.get("event_date")
        conversion_start_date = row.get("conversion_start_date")

        highlight_start = row.get(highlight_period[0]) if highlight_period else issue_date
        highlight_end = row.get(highlight_period[1]) if highlight_period else conversion_start_date

        if pd.notna(highlight_start) and pd.notna(highlight_end) and highlight_end >= highlight_start:
            x0 = chart_event_date(price_df, highlight_start)
            x1 = chart_event_date(price_df, highlight_end)

            if pd.notna(x0) and pd.notna(x1) and x1 >= x0:
                fig.add_shape(
                    type="rect",
                    x0=x0,
                    x1=x1,
                    y0=0,
                    y1=1,
                    xref="x",
                    yref="paper",
                    fillcolor="rgba(107, 114, 128, 0.18)",
                    line={"color": "rgba(107, 114, 128, 0.28)", "width": 1},
                    layer="above",
                )

        for column, label, color, dash in event_specs:
            event_date = row.get(column)

            if pd.isna(event_date):
                continue

            x_value = chart_event_date(price_df, event_date)

            if pd.isna(x_value):
                continue

            add_vertical_event(fig, x_value, label, color, dash)


def make_warning_messages(mezz_df):
    warning_messages = []

    for _, row in mezz_df.iterrows():
        dilution = row.get("희석률")
        surface_rate = row.get("표면이자율")
        maturity_rate = row.get("만기이자율")
        lowest_price = row.get("최저조정가액")
        conversion_price = row.get("전환가액")
        label = f"{row.get('corp_name', '')} {row.get('bd_tm', '')}".strip()

        if pd.notna(dilution) and dilution >= 20:
            warning_messages.append(f"{label}: 희석률 {dilution:.2f}%")

        if pd.notna(surface_rate) and surface_rate <= 0:
            warning_messages.append(f"{label}: 표면이자율 0%")

        if pd.notna(lowest_price) and pd.notna(conversion_price) and conversion_price > 0:
            refixing_ratio = lowest_price / conversion_price

            if refixing_ratio <= 0.7:
                warning_messages.append(f"{label}: 70% 이하 리픽싱 가능 구조")

        if pd.notna(maturity_rate) and maturity_rate >= 8:
            warning_messages.append(f"{label}: 고금리 메자닌 구조")

    return warning_messages


def get_conversion_status(start_value, end_value):
    today = pd.Timestamp(date.today())

    if pd.isna(start_value) and pd.isna(end_value):
        return "기간 미공시"

    if pd.notna(start_value) and today < start_value:
        return "전환청구 전"

    if pd.notna(end_value) and today > end_value:
        return "전환청구 종료"

    return "전환청구 가능"


def build_conversion_period_df(mezz_df):
    period_cols = [
        "disclosure_name",
        "corp_name",
        "bd_tm",
        "event_date",
        "payment_date",
        "conversion_start_date",
        "conversion_end_date",
        "cvisstk_cnt",
        "cv_prc",
        "전환가액",
        "희석률",
        "위험등급",
    ]
    period_cols = [col for col in period_cols if col in mezz_df.columns]
    period_df = mezz_df[period_cols].copy()

    if period_df.empty:
        return period_df

    period_df["conversion_period"] = period_df.apply(
        lambda row: (
            f"{row['conversion_start_date'].strftime('%Y-%m-%d') if pd.notna(row.get('conversion_start_date')) else '-'}"
            " ~ "
            f"{row['conversion_end_date'].strftime('%Y-%m-%d') if pd.notna(row.get('conversion_end_date')) else '-'}"
        ),
        axis=1,
    )
    period_df["conversion_status"] = period_df.apply(
        lambda row: get_conversion_status(row.get("conversion_start_date"), row.get("conversion_end_date")),
        axis=1,
    )
    period_df["days_to_conversion_start"] = period_df["conversion_start_date"].apply(
        lambda value: (value.date() - date.today()).days if pd.notna(value) else np.nan
    )

    return period_df.sort_values(["conversion_start_date", "event_date"], na_position="last")


def add_remaining_overhang_estimates(mezz_df, current_price, market_cap, tracking_events=None):
    estimated = mezz_df.copy()
    today = pd.Timestamp(date.today())

    estimated["잔여권면총액_추정"] = estimated["발행금액"]
    estimated["잔여가능주식수_추정"] = estimated["potential_share_count"]
    estimated["추적차감권면총액"] = 0.0
    estimated["추적차감주식수"] = 0.0
    estimated["잔여물량추적상태"] = "추적 공시 미반영"

    if tracking_events is not None and not tracking_events.empty:
        for index, row in estimated.iterrows():
            round_number = extract_round_number(row.get("bd_tm"))
            matched_events = tracking_events[tracking_events["추적회차"] == round_number] if round_number else pd.DataFrame()

            if matched_events.empty:
                continue

            deducted_amount = matched_events["차감권면총액"].dropna().sum()
            deducted_shares = matched_events["차감주식수"].dropna().sum()

            estimated.at[index, "추적차감권면총액"] = deducted_amount
            estimated.at[index, "추적차감주식수"] = deducted_shares

            if pd.notna(estimated.at[index, "잔여권면총액_추정"]):
                estimated.at[index, "잔여권면총액_추정"] = max(
                    estimated.at[index, "잔여권면총액_추정"] - deducted_amount,
                    0,
                )

            if pd.notna(estimated.at[index, "잔여가능주식수_추정"]):
                estimated.at[index, "잔여가능주식수_추정"] = max(
                    estimated.at[index, "잔여가능주식수_추정"] - deducted_shares,
                    0,
                )

            estimated.at[index, "잔여물량추적상태"] = "추적 공시 반영"

    if "conversion_end_date" in estimated.columns:
        ended_mask = estimated["conversion_end_date"].notna() & (estimated["conversion_end_date"] < today)
        estimated.loc[ended_mask, ["잔여권면총액_추정", "잔여가능주식수_추정"]] = 0
        estimated.loc[ended_mask, "잔여물량추적상태"] = "권리행사기간 종료"

    missing_share_mask = estimated["잔여가능주식수_추정"].isna() & (estimated["전환가액"] > 0)
    estimated.loc[missing_share_mask, "잔여가능주식수_추정"] = (
        estimated.loc[missing_share_mask, "잔여권면총액_추정"] / estimated.loc[missing_share_mask, "전환가액"]
    )

    estimated["잔여시총대비비율_추정"] = np.where(
        market_cap > 0,
        estimated["잔여권면총액_추정"] / market_cap * 100,
        np.nan,
    )
    estimated["잔여주식가치_추정"] = estimated["잔여가능주식수_추정"] * current_price

    return estimated


def prepare_mezzanine_dataframe(mezz_df):
    prepared = mezz_df.copy()

    prepared = fill_date_column_from_candidates(
        prepared,
        "event_date",
        ["bddd", "이사회결의일", "발행결정일"],
        fallback_from_rcept_no=True,
    )
    prepared = fill_date_column_from_candidates(prepared, "payment_date", ["pymd", "납입일"])
    prepared = fill_date_column_from_candidates(
        prepared,
        "conversion_start_date",
        ["cvrqpd_bgd", "expd_bgd", "exrqpd_bgd", "전환청구시작일", "신주인수권 행사시작일", "교환청구시작일", "전환청구 시작일"],
    )
    prepared = fill_date_column_from_candidates(
        prepared,
        "conversion_end_date",
        ["cvrqpd_edd", "expd_edd", "exrqpd_edd", "전환청구종료일", "신주인수권 행사종료일", "교환청구종료일", "전환청구 종료일"],
    )
    prepared = fill_date_column_from_candidates(prepared, "maturity_date", ["bd_mtd", "사채만기일"])

    prepared["희석률"] = prepared.apply(
        lambda row: first_available_number(row, ["cvisstk_tisstk_vs", "nstk_isstk_tisstk_vs", "extg_tisstk_vs", "희석률"]),
        axis=1,
    )
    prepared["potential_share_count"] = prepared.apply(
        lambda row: first_available_number(row, ["cvisstk_cnt", "nstk_isstk_cnt", "extg_stkcnt", "전환가능주식수"]),
        axis=1,
    )
    if "cv_prc" in prepared:
        prepared["전환가액"] = prepared["cv_prc"].apply(clean_number)
    elif "ex_prc" in prepared:
        prepared["전환가액"] = prepared["ex_prc"].apply(clean_number)
    else:
        prepared["전환가액"] = np.nan
    prepared["최저조정가액"] = (
        prepared["act_mktprcfl_cvprc_lwtrsprc"].apply(clean_number)
        if "act_mktprcfl_cvprc_lwtrsprc" in prepared
        else np.nan
    )
    prepared["발행금액"] = prepared["bd_fta"].apply(clean_number) if "bd_fta" in prepared else np.nan
    prepared["표면이자율"] = prepared["bd_intr_ex"].apply(clean_number) if "bd_intr_ex" in prepared else np.nan
    prepared["만기이자율"] = prepared["bd_intr_sf"].apply(clean_number) if "bd_intr_sf" in prepared else np.nan
    prepared["리픽싱 조항"] = prepared["최저조정가액"].notna().astype(int)
    return prepared


def calculate_period_return(stock_code, start_value, end_value):
    if pd.isna(start_value) or pd.isna(end_value) or end_value < start_value:
        return np.nan

    price_df = get_price(
        stock_code,
        pd.to_datetime(start_value).strftime("%Y%m%d"),
        pd.to_datetime(end_value).strftime("%Y%m%d"),
    )

    if price_df.empty:
        return np.nan

    start_row = first_trading_row_on_or_after(price_df, start_value)
    end_row = last_trading_row_on_or_before(price_df, end_value)

    if start_row is None or end_row is None or start_row["종가"] <= 0:
        return np.nan

    return (end_row["종가"] / start_row["종가"] - 1) * 100


def build_event_return_df(mezz_df, start_column, end_column):
    results = []

    for _, row in mezz_df.iterrows():
        stock_code = row.get("stock_code")

        if not stock_code:
            continue

        period_return = calculate_period_return(stock_code, row.get(start_column), row.get(end_column))
        results.append(
            {
                "회사명": row.get("corp_name"),
                "종목코드": stock_code,
                "회차": row.get("bd_tm"),
                "공시유형": row.get("disclosure_name"),
                "시작 기준일": row.get(start_column),
                "종료 기준일": row.get(end_column),
                "기간수익률(%)": period_return,
                "리픽싱 조항": row.get("리픽싱 조항", 0),
                "조기상환 옵션": row.get("조기상환 옵션", 0),
                "콜옵션": row.get("콜옵션", 0),
                "풋옵션": row.get("풋옵션", 0),
            }
        )

    return pd.DataFrame(results)


def round_option_label(row):
    parts = [
        str(row.get("bd_tm", "회차 미상")),
        str(row.get("disclosure_name", "공시")),
    ]

    if pd.notna(row.get("event_date")):
        parts.append(row["event_date"].strftime("%Y-%m-%d"))

    return " / ".join(parts)


API_KEY = get_open_dart_api_key()

st.sidebar.header("검색 설정")

try:
    with st.spinner("기업 목록 다운로드 중입니다."):
        corp_df = download_corp_codes(API_KEY)
except requests.RequestException as error:
    st.error(f"기업 목록 다운로드 실패: {error}")
    st.stop()

try:
    kospi_tickers = set(stock.get_market_ticker_list(market="KOSPI"))
    kosdaq_tickers = set(stock.get_market_ticker_list(market="KOSDAQ"))
    market_by_ticker = {ticker: "KOSPI" for ticker in kospi_tickers}
    market_by_ticker.update({ticker: "KOSDAQ" for ticker in kosdaq_tickers})
    corp_df = corp_df[corp_df["stock_code"].isin(market_by_ticker)].copy()
    corp_df["market"] = corp_df["stock_code"].map(market_by_ticker)
except (IndexError, KeyError, ValueError, requests.RequestException):
    corp_df = corp_df.copy()
    corp_df["market"] = "상장"

if corp_df.empty:
    st.error("조회 가능한 상장사 목록이 없습니다.")
    st.stop()

default_company_query = st.session_state.get("company_query", "에코프로")
company_query = st.sidebar.text_input("기업 검색", value=default_company_query, placeholder="회사명 또는 종목코드")
st.session_state["company_query"] = company_query

if company_query.strip():
    query = company_query.strip()
    company_candidates = corp_df[
        corp_df["corp_name"].str.contains(query, case=False, na=False)
        | corp_df["stock_code"].str.contains(query, case=False, na=False)
    ].copy()
else:
    company_candidates = corp_df.copy()

company_candidates = company_candidates.sort_values(["corp_name", "stock_code"]).head(100).copy()
company_candidates["display_name"] = company_candidates.apply(
    lambda row: f"{row['corp_name']} ({row['stock_code']}, {row.get('market', '상장')})",
    axis=1,
)

if company_candidates.empty:
    selected_company_option = None
    st.sidebar.warning("검색 결과가 없습니다.")
else:
    previous_company = st.session_state.get("selected_company_option")
    candidate_options = company_candidates["display_name"].tolist()
    default_company_index = candidate_options.index(previous_company) if previous_company in candidate_options else 0
    selected_company_option = st.sidebar.selectbox(
        "기업 선택",
        candidate_options,
        index=default_company_index,
    )
    st.session_state["selected_company_option"] = selected_company_option

search_all_period = st.sidebar.checkbox("전체 기간 조회(2015년 이후)", value=True)
selected_disclosure_types = st.sidebar.multiselect(
    "공시 종류",
    options=[api["type"] for api in MEZZANINE_DISCLOSURE_APIS],
    default=[api["type"] for api in MEZZANINE_DISCLOSURE_APIS],
    format_func=lambda value: next(api["name"] for api in MEZZANINE_DISCLOSURE_APIS if api["type"] == value),
)
track_remaining_volume = st.sidebar.checkbox("잔여물량 공시 자동 추적", value=True)
tracking_document_limit = st.sidebar.number_input("잔여물량 추적 공시 수", min_value=5, max_value=100, value=30, step=5)
input_start_date = normalize_date(st.sidebar.date_input("시작일", value=date(2024, 1, 1)))
input_end_date = normalize_date(st.sidebar.date_input("종료일", value=date.today()))
start_date = OPENDART_DATA_START_DATE if search_all_period else input_start_date
end_date = date.today() if search_all_period else input_end_date
benchmark_name = st.sidebar.selectbox("벤치마크", ["KOSDAQ", "KOSPI"])
benchmark_code = "2001" if benchmark_name == "KOSDAQ" else "1001"

with st.sidebar.expander("희석위험지수 가중치", expanded=False):
    risk_weights = {
        "dilution": st.slider("희석률", 0, 50, DEFAULT_RISK_WEIGHTS["dilution"]),
        "gap": st.slider("전환가괴리율", 0, 50, DEFAULT_RISK_WEIGHTS["gap"]),
        "cb_ratio": st.slider("시총대비 CB비율", 0, 50, DEFAULT_RISK_WEIGHTS["cb_ratio"]),
        "refixing": st.slider("리픽싱 조항", 0, 30, DEFAULT_RISK_WEIGHTS["refixing"]),
        "zero_coupon": st.slider("표면이자율 0%", 0, 20, DEFAULT_RISK_WEIGHTS["zero_coupon"]),
        "high_yield": st.slider("고금리 만기이자", 0, 20, DEFAULT_RISK_WEIGHTS["high_yield"]),
    }

search_button = st.sidebar.button("조회", type="primary")

if search_button:
    st.session_state["search_requested"] = True

if not st.session_state.get("search_requested", False):
    st.info("왼쪽 사이드바에서 기업을 검색해 선택한 뒤 조회를 눌러주세요.")
    st.stop()

if selected_company_option is None:
    st.error("조회할 기업을 선택해 주세요.")
    st.stop()

if not selected_disclosure_types:
    st.error("조회할 공시 종류를 하나 이상 선택해 주세요.")
    st.stop()

if start_date > end_date:
    st.error("시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()

corp_info = company_candidates[company_candidates["display_name"] == selected_company_option].iloc[0]
corp_code = corp_info["corp_code"]
stock_code = corp_info["stock_code"]
company_name = corp_info["corp_name"]

st.success(f"{company_name} / {stock_code}")

try:
    mezz_df = get_all_mezzanine_data(
        API_KEY,
        corp_code,
        start_date,
        end_date,
        selected_disclosure_types,
    )
except requests.RequestException as error:
    st.error(f"메자닌 공시 조회 실패: {error}")
    st.stop()

if mezz_df.empty:
    st.warning("선택한 종류의 메자닌 공시가 없습니다.")
    st.stop()

mezz_df = prepare_mezzanine_dataframe(mezz_df)
mezz_df["stock_code"] = stock_code
mezz_df["market"] = corp_info.get("market", "")

tracking_events_df = pd.DataFrame()
if track_remaining_volume:
    try:
        tracking_events_df = build_remaining_tracking_events(
            API_KEY,
            corp_code,
            start_date,
            date.today(),
            int(tracking_document_limit),
        )
    except (requests.RequestException, ValueError) as error:
        st.warning(f"잔여물량 추적 공시 조회 실패: {error}")

seibro_remaining_df = pd.DataFrame()
try:
    seibro_remaining_df = fetch_seibro_remaining_bonds(
        company_name,
        OPENDART_DATA_START_DATE,
        date.today(),
    )
    mezz_df = attach_seibro_remaining_to_dart(mezz_df, seibro_remaining_df)
except Exception as error:
    st.warning(f"SEIBro 발행잔액 매핑 실패: {error}")

event_date_columns = ["event_date", "payment_date", "conversion_start_date", "conversion_end_date", "maturity_date"]
available_event_dates = pd.concat(
    [mezz_df[column] for column in event_date_columns if column in mezz_df.columns],
    ignore_index=True,
).dropna()
chart_start = min(start_date, available_event_dates.min().date() if not available_event_dates.empty else start_date)
chart_display_end = max(
    end_date,
    date.today(),
    min(
        available_event_dates.max().date(),
        date.today() + timedelta(days=365),
    )
    if not available_event_dates.empty
    else end_date,
)
price_end_date = min(chart_display_end, date.today())

price_df = get_price(
    stock_code,
    chart_start.strftime("%Y%m%d"),
    price_end_date.strftime("%Y%m%d"),
)

if price_df.empty:
    st.error("주가 데이터가 없습니다.")
    st.stop()

current_price = price_df.iloc[-1]["종가"]
market_cap, market_cap_date = get_recent_market_cap(stock_code, price_df.iloc[-1]["날짜"])
market_cap_source = "pykrx"

mezz_df["현재주가"] = current_price
mezz_df["시가총액"] = market_cap
mezz_df["전환가괴리율"] = np.where(mezz_df["전환가액"] > 0, mezz_df["현재주가"] / mezz_df["전환가액"], np.nan)
mezz_df["시총대비CB비율"] = np.where(market_cap > 0, mezz_df["발행금액"] / market_cap * 100, np.nan)
mezz_df = add_remaining_overhang_estimates(mezz_df, current_price, market_cap, tracking_events_df)
mezz_df["위험점수"] = mezz_df.apply(lambda row: calculate_risk_score(row, risk_weights), axis=1)
mezz_df["위험등급"] = mezz_df["위험점수"].apply(risk_label)

remaining_summary_df = (
    mezz_df[mezz_df["SEIBro_잔액존재"]].copy()
    if "SEIBro_잔액존재" in mezz_df.columns and mezz_df["SEIBro_잔액존재"].any()
    else mezz_df.copy()
)

latest_risk = remaining_summary_df["위험점수"].max()
latest_dilution = remaining_summary_df["희석률"].max()
latest_cb_ratio = remaining_summary_df["시총대비CB비율"].max()
latest_gap = remaining_summary_df["전환가괴리율"].min()
event_rows = mezz_df[
    mezz_df[event_date_columns].notna().any(axis=1)
].copy()

latest_row = remaining_summary_df.sort_values("event_date", ascending=False).iloc[0]
gauge_score = latest_row.get("위험점수", np.nan)
gauge_score = 0 if pd.isna(gauge_score) else float(gauge_score)

st.subheader("실시간 희석위험지수")
gauge_col, metric_col = st.columns([1.15, 1])

with gauge_col:
    gauge_fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=gauge_score,
            title={"text": "희석위험지수"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": risk_color(gauge_score)},
                "steps": [
                    {"range": [0, 40], "color": "#dcfce7"},
                    {"range": [40, 70], "color": "#fef3c7"},
                    {"range": [70, 100], "color": "#fee2e2"},
                ],
            },
        )
    )
    gauge_fig.update_layout(height=290, margin={"l": 20, "r": 20, "t": 45, "b": 10})
    st.plotly_chart(gauge_fig, use_container_width=True)

with metric_col:
    metric_row1_col1, metric_row1_col2 = st.columns(2)
    metric_row2_col1, metric_row2_col2 = st.columns(2)
    metric_row1_col1.metric("최대 희석률", f"{latest_dilution:.2f}%" if pd.notna(latest_dilution) else "-")
    metric_row1_col2.metric("시총대비 CB비율", f"{latest_cb_ratio:.2f}%" if pd.notna(latest_cb_ratio) else "-")
    metric_row2_col1.metric("전환가괴리율", f"{latest_gap:.2f}" if pd.notna(latest_gap) else "-")
    metric_row2_col2.metric("위험등급", latest_row.get("위험등급", "-"))
    st.caption(
        f"시가총액 기준일: {pd.to_datetime(market_cap_date).strftime('%Y-%m-%d')} / 출처: {market_cap_source}"
        if pd.notna(market_cap_date)
        else "시가총액 기준일: 조회 실패"
    )
    if pd.notna(market_cap):
        st.caption(f"시가총액: {market_cap / 100000000:.1f}억")

tabs = st.tabs(
    [
        "요약",
        "주가 이벤트",
        "CAR 분석",
        "리픽싱/오버행",
        "악성 CB 탐지",
        "상환/자금/옵션",
        "원본 데이터",
        "SEIBro 데이터",
    ]
)

with tabs[0]:
    st.subheader("실시간 희석위험 분석")
    if "SEIBro_잔액존재" in mezz_df.columns and mezz_df["SEIBro_잔액존재"].any():
        st.caption("SEIBro 발행잔액이 남아있는 ISIN에 매핑된 회차만 표시합니다.")
    else:
        st.caption("SEIBro 발행잔액 매핑 결과가 없어 OpenDART 조회 회차 전체를 표시합니다.")

    show_columns = [
        "disclosure_name",
        "corp_name",
        "bd_tm",
        "SEIBro_ISIN",
        "SEIBro_종목명",
        "SEIBro_매핑회차",
        "SEIBro_매핑상태",
        "SEIBro_발행잔액_원문",
        "SEIBro_발행금액_원문",
        "SEIBro_매핑점수",
        "발행금액",
        "전환가액",
        "최저조정가액",
        "희석률",
        "전환가괴리율",
        "시총대비CB비율",
        "위험점수",
        "위험등급",
    ]
    available_cols = [col for col in show_columns if col in remaining_summary_df.columns]
    st.dataframe(to_korean_columns(remaining_summary_df[available_cols]), use_container_width=True)

    with st.expander("OpenDART-SEIBro 회차 매핑 확인", expanded=False):
        mapping_cols = [
            col
            for col in [
                "disclosure_name",
                "corp_name",
                "bd_tm",
                "event_date",
                "maturity_date",
                "발행금액",
                "SEIBro_매핑회차",
                "SEIBro_매핑상태",
                "SEIBro_ISIN",
                "SEIBro_종목명",
                "SEIBro_발행금액_원문",
                "SEIBro_발행잔액_원문",
                "SEIBro_매핑점수",
                "SEIBro_잔액존재",
            ]
            if col in mezz_df.columns
        ]
        st.dataframe(to_korean_columns(mezz_df[mapping_cols]), use_container_width=True, hide_index=True)
        if not seibro_remaining_df.empty:
            st.caption("아래는 발행인명으로 조회한 SEIBro 원본 후보입니다. 발행잔액은 계산하지 않고 SEIBro 원문 값을 그대로 표시합니다.")
            seibro_candidate_cols = [
                col
                for col in [
                    "SEIBro_매핑회차",
                    "ISIN",
                    "KOR_SECN_NM",
                    "REP_SECN_NM",
                    "ISSU_DT",
                    "XPIR_DT",
                    "SEIBro_발행금액_원문",
                    "SEIBro_발행잔액_원문",
                    "SECN_KACD",
                    "OPTION_TPCD_NM",
                ]
                if col in seibro_remaining_df.columns
            ]
            st.dataframe(to_korean_columns(seibro_remaining_df[seibro_candidate_cols]), use_container_width=True, hide_index=True)

    risk_x = "bd_tm" if "bd_tm" in remaining_summary_df.columns else remaining_summary_df.index
    risk_fig = px.bar(
        remaining_summary_df,
        x=risk_x,
        y="위험점수",
        color="위험등급",
        text="위험점수",
        hover_data=[
            col
            for col in ["disclosure_name", "SEIBro_ISIN", "SEIBro_발행잔액_원문", "SEIBro_매핑상태", "bd_fta", "희석률", "전환가괴리율"]
            if col in remaining_summary_df.columns
        ],
        title="메자닌 위험점수",
        labels=korean_labels(remaining_summary_df.columns),
    )
    risk_fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    risk_fig.update_layout(
        height=360 if len(remaining_summary_df) <= 3 else 420,
        bargap=0.65 if len(remaining_summary_df) <= 3 else 0.25,
        margin={"l": 20, "r": 20, "t": 60, "b": 40},
    )

    if len(remaining_summary_df) <= 3:
        risk_chart_col, risk_note_col = st.columns([1, 1])

        with risk_chart_col:
            risk_fig.update_traces(width=0.35)
            st.plotly_chart(risk_fig, use_container_width=True)

        with risk_note_col:
            st.markdown("#### 위험점수 구성")
            score_cols = [
                "disclosure_name",
                "bd_tm",
                "SEIBro_ISIN",
                "SEIBro_발행잔액_원문",
                "SEIBro_매핑상태",
                "희석률",
                "전환가괴리율",
                "시총대비CB비율",
                "위험점수",
                "위험등급",
            ]
            score_cols = [col for col in score_cols if col in remaining_summary_df.columns]
            st.dataframe(to_korean_columns(remaining_summary_df[score_cols]), use_container_width=True, hide_index=True)
    else:
        st.plotly_chart(risk_fig, use_container_width=True)

    st.markdown("#### 위험점수 산식 확인")
    st.caption("사이드바의 가중치를 조정하면 아래 항목별 점수와 최종 위험점수가 함께 바뀝니다.")
    component_df = pd.DataFrame([calculate_risk_components(row, risk_weights) for _, row in remaining_summary_df.iterrows()])
    score_detail_base_cols = [
        col
        for col in ["disclosure_name", "bd_tm", "SEIBro_ISIN", "SEIBro_발행잔액_원문", "SEIBro_매핑상태", "희석률", "전환가괴리율", "시총대비CB비율", "위험점수", "위험등급"]
        if col in remaining_summary_df.columns
    ]
    score_detail_df = pd.concat([remaining_summary_df[score_detail_base_cols].reset_index(drop=True), component_df], axis=1)
    st.dataframe(to_korean_columns(score_detail_df), use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("주가 및 CB 이벤트")

    event_label_map = {
        "event_date": "발행결정일",
        "payment_date": "납입일",
        "conversion_start_date": "전환청구 시작일",
        "conversion_end_date": "전환청구 종료일",
        "maturity_date": "사채만기일",
    }
    event_color_map = {
        "event_date": "#e11d48",
        "payment_date": "#f59e0b",
        "conversion_start_date": "#2563eb",
        "conversion_end_date": "#16a34a",
        "maturity_date": "#7c3aed",
    }
    round_filter_rows = mezz_df.copy().reset_index(drop=True)
    round_filter_rows["_round_option"] = round_filter_rows.apply(round_option_label, axis=1)
    selected_chart_round = st.selectbox(
        "그래프 표시 회차",
        round_filter_rows["_round_option"].tolist(),
        index=0,
    )
    chart_event_rows = round_filter_rows[round_filter_rows["_round_option"] == selected_chart_round].copy()
    close_date_col1, close_date_col2 = st.columns(2)
    with close_date_col1:
        selected_close_start_date = normalize_date(
            st.date_input(
                "종가 표시 시작일",
                value=chart_start,
                min_value=chart_start,
                max_value=price_end_date,
            )
        )
    with close_date_col2:
        selected_close_end_date = normalize_date(
            st.date_input(
                "종가 표시 종료일",
                value=price_df.iloc[-1]["날짜"].date(),
                min_value=chart_start,
                max_value=price_end_date,
            )
        )

    if selected_close_start_date > selected_close_end_date:
        st.warning("종가 표시 시작일이 종료일보다 늦어 종료일과 동일하게 맞췄습니다.")
        selected_close_start_date = selected_close_end_date

    display_price_df = price_df[
        (price_df["날짜"] >= pd.Timestamp(selected_close_start_date))
        & (price_df["날짜"] <= pd.Timestamp(selected_close_end_date))
    ].copy()

    if display_price_df.empty:
        st.warning("선택한 종가 표시일까지 조회 가능한 주가 데이터가 없습니다.")
        display_price_df = price_df.copy()

    future_event_cutoff = pd.Timestamp(date.today() + timedelta(days=365))
    selected_event_date_cols = list(event_label_map)
    event_has_near_date = chart_event_rows[selected_event_date_cols].apply(
        lambda row: row.dropna().le(future_event_cutoff).any(),
        axis=1,
    )
    chart_future_event_rows = chart_event_rows[~event_has_near_date].copy()
    chart_event_rows = chart_event_rows[event_has_near_date].copy()
    selected_line_events = st.multiselect(
        "세로선 표시 기준일",
        list(event_label_map),
        default=["event_date", "payment_date", "conversion_start_date", "conversion_end_date"],
        format_func=lambda value: event_label_map[value],
    )
    highlight_col1, highlight_col2 = st.columns(2)
    with highlight_col1:
        highlight_start_column = st.selectbox(
            "배경 하이라이트 시작",
            list(event_label_map),
            index=0,
            format_func=lambda value: event_label_map[value],
        )
    with highlight_col2:
        highlight_end_column = st.selectbox(
            "배경 하이라이트 종료",
            list(event_label_map),
            index=2,
            format_func=lambda value: event_label_map[value],
        )
    selected_event_specs = [
        (column, event_label_map[column], event_color_map[column], "dash" if column.endswith("date") else "dot")
        for column in selected_line_events
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=display_price_df["날짜"],
            open=display_price_df["시가"],
            high=display_price_df["고가"],
            low=display_price_df["저가"],
            close=display_price_df["종가"],
            name="주가",
        )
    )
    add_event_lines(
        fig,
        chart_event_rows,
        display_price_df,
        event_specs=selected_event_specs,
        highlight_period=(highlight_start_column, highlight_end_column),
    )
    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        legend_orientation="h",
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )
    chart_view_end = selected_close_end_date
    near_event_dates = pd.concat(
        [chart_event_rows[column] for column in selected_event_date_cols if column in chart_event_rows.columns],
        ignore_index=True,
    ).dropna()

    if not near_event_dates.empty:
        chart_view_end = max(
            chart_view_end,
            min(near_event_dates.max().date(), date.today() + timedelta(days=365)),
        )

    fig.update_xaxes(range=[selected_close_start_date, chart_view_end])
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"표시 기간: {selected_close_start_date.strftime('%Y-%m-%d')} ~ {display_price_df.iloc[-1]['날짜'].strftime('%Y-%m-%d')} "
        f"/ 종료 종가: {display_price_df.iloc[-1]['종가']:,.0f}원"
    )

    if not chart_future_event_rows.empty:
        future_info_cols = [
            col
            for col in [
                "disclosure_name",
                "bd_tm",
                "payment_date",
                "conversion_start_date",
                "conversion_end_date",
                "maturity_date",
                "SEIBro_ISIN",
                "SEIBro_종목명",
            ]
            if col in chart_future_event_rows.columns
        ]
        st.markdown("#### 1년 이후 도래 이벤트")
        st.caption("그래프 스케일 보호를 위해 오늘부터 1년 이후 이벤트는 차트에 그리지 않고 정보성 표로만 표시합니다.")
        st.dataframe(to_korean_columns(chart_future_event_rows[future_info_cols]), use_container_width=True, hide_index=True)

    date_check_cols = [
        col
        for col in [
            "disclosure_name",
            "bd_tm",
            "event_date",
            "payment_date",
            "conversion_start_date",
            "conversion_end_date",
            "maturity_date",
            "potential_share_count",
        ]
        if col in mezz_df.columns
    ]
    st.markdown("#### 기준일 추출 현황")
    st.dataframe(to_korean_columns(mezz_df[date_check_cols]), use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("CAR 이벤트 스터디")

    car_round_rows = mezz_df.copy().reset_index(drop=True)
    car_round_rows["_round_option"] = car_round_rows.apply(round_option_label, axis=1)
    selected_car_round = st.selectbox(
        "CAR 표시 회차",
        ["전체 회차"] + car_round_rows["_round_option"].tolist(),
        index=0,
        key="car_round_filter",
    )
    car_base_df = (
        mezz_df
        if selected_car_round == "전체 회차"
        else car_round_rows[car_round_rows["_round_option"] == selected_car_round].copy()
    )
    car_event_column = st.selectbox(
        "CAR 기준일",
        ["event_date", "payment_date", "conversion_start_date", "conversion_end_date", "maturity_date"],
        format_func=lambda value: KOREAN_COLUMN_NAMES.get(value, value),
    )
    car_windows = st.multiselect(
        "이벤트 이후 분석 기간",
        [1, 3, 5, 10, 20],
        default=[1, 3, 5, 10],
        format_func=lambda value: f"{value}거래일",
    )
    benchmark_df = get_benchmark_price(
        benchmark_code,
        chart_start.strftime("%Y%m%d"),
        price_end_date.strftime("%Y%m%d"),
    )

    if benchmark_df.empty:
        st.warning("벤치마크 데이터를 찾을 수 없어 벤치마크 수익률을 0으로 두고 계산합니다.")
        benchmark_returns = price_df[["날짜"]].copy()
        benchmark_returns["benchmark_return"] = 0.0
    else:
        benchmark_returns = benchmark_df[["날짜", "종가"]].copy()
        benchmark_returns["benchmark_return"] = benchmark_returns["종가"].pct_change()

    price_returns = price_df[["날짜", "종가"]].copy()
    price_returns["stock_return"] = price_returns["종가"].pct_change()

    merged = pd.merge(
        price_returns[["날짜", "stock_return"]],
        benchmark_returns[["날짜", "benchmark_return"]],
        on="날짜",
        how="left",
    )
    merged["benchmark_return"] = merged["benchmark_return"].fillna(0)
    merged["abnormal_return"] = merged["stock_return"].fillna(0) - merged["benchmark_return"]
    merged["CAR"] = merged["abnormal_return"].cumsum()

    car_fig = px.line(
        merged,
        x="날짜",
        y="CAR",
        title="전체 기간 누적초과수익률(CAR)",
        labels={"날짜": "날짜", "CAR": "누적초과수익률(CAR)"},
    )
    car_fig.update_layout(height=420)
    st.plotly_chart(car_fig, use_container_width=True)

    issue_event_rows = car_base_df.dropna(subset=[car_event_column])

    if issue_event_rows.empty:
        st.info(f"{KOREAN_COLUMN_NAMES.get(car_event_column, car_event_column)} 데이터가 없어 이벤트별 CAR을 계산할 수 없습니다.")
    else:
        car_results = []

        for _, row in issue_event_rows.iterrows():
            event_date = row[car_event_column]
            before_date = trading_day_after(price_df, event_date, 0)

            if pd.isna(before_date):
                continue

            stock_before = first_trading_row_on_or_after(price_df, before_date)
            bm_before = first_trading_row_on_or_after(benchmark_df, before_date) if not benchmark_df.empty else None

            if stock_before is None:
                continue

            result = {
                "회차": row.get("bd_tm", "회차 미상"),
                "기준일 종류": KOREAN_COLUMN_NAMES.get(car_event_column, car_event_column),
                "이벤트일": event_date.strftime("%Y-%m-%d"),
                "기준 거래일": stock_before["날짜"].strftime("%Y-%m-%d"),
            }

            for window in car_windows:
                after_date = trading_day_after(price_df, event_date, int(window))

                if pd.isna(after_date):
                    result[f"{window}거래일 CAR(%)"] = np.nan
                    continue

                stock_after = last_trading_row_on_or_before(price_df, after_date)
                bm_after = (
                    last_trading_row_on_or_before(benchmark_df, after_date)
                    if not benchmark_df.empty
                    else None
                )

                if stock_after is None:
                    result[f"{window}거래일 CAR(%)"] = np.nan
                    continue

                stock_ret = (stock_after["종가"] / stock_before["종가"] - 1) * 100

                if bm_before is not None and bm_after is not None:
                    bm_ret = (bm_after["종가"] / bm_before["종가"] - 1) * 100
                else:
                    bm_ret = 0

                result[f"{window}거래일 CAR(%)"] = stock_ret - bm_ret

            car_results.append(result)

        if car_results:
            car_result_df = pd.DataFrame(car_results)
            st.dataframe(car_result_df, use_container_width=True)

            y_columns = [col for col in car_result_df.columns if col.endswith("CAR(%)")]

            if y_columns:
                car_event_fig = px.bar(
                    car_result_df,
                    x="이벤트일",
                    y=y_columns,
                    barmode="group",
                    title="이벤트별 CAR",
                    labels={"이벤트일": "이벤트일", "value": "CAR(%)", "variable": "분석 기간"},
                )
                car_event_fig.update_layout(height=420)
                st.plotly_chart(car_event_fig, use_container_width=True)
        else:
            st.info("주가 거래일과 이벤트일이 맞지 않아 계산 가능한 CAR 결과가 없습니다.")

    st.subheader("기준일 간 수익률")
    period_col1, period_col2 = st.columns(2)
    with period_col1:
        single_period_start = st.selectbox(
            "시작 기준일",
            ["event_date", "payment_date", "conversion_start_date"],
            format_func=lambda value: KOREAN_COLUMN_NAMES.get(value, value),
            key="single_period_start",
        )
    with period_col2:
        single_period_end = st.selectbox(
            "종료 기준일",
            ["payment_date", "conversion_start_date", "conversion_end_date", "maturity_date"],
            index=1,
            format_func=lambda value: KOREAN_COLUMN_NAMES.get(value, value),
            key="single_period_end",
        )

    single_return_df = build_event_return_df(car_base_df, single_period_start, single_period_end)
    st.dataframe(single_return_df, use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("리픽싱 추적")

    refixing_df = mezz_df.dropna(subset=["최저조정가액"])

    if refixing_df.empty:
        st.info("리픽싱 데이터가 없습니다.")
    else:
        refixing_fig = px.line(
            refixing_df,
            x="event_date",
            y="전환가액",
            color="bd_tm" if "bd_tm" in refixing_df.columns else None,
            markers=True,
            title="전환가액 추이",
            labels=korean_labels(refixing_df.columns),
        )
        st.plotly_chart(refixing_fig, use_container_width=True)

    st.subheader("회차별 전환청구기간")

    conversion_period_df = build_conversion_period_df(mezz_df)

    if conversion_period_df.empty:
        st.info("전환청구기간 데이터를 찾을 수 없습니다.")
    else:
        st.dataframe(to_korean_columns(conversion_period_df), use_container_width=True, hide_index=True)

    st.subheader("전환청구 오버행 캘린더")
    st.caption("각 회차의 전환·행사·교환 청구 시작일에 잠재 물량이 언제부터 오버행으로 열리는지 보여줍니다.")

    st.markdown("#### 회차별 잔여 오버행 추정")
    remaining_cols = [
        col
        for col in [
            "disclosure_name",
            "corp_name",
            "bd_tm",
            "conversion_start_date",
            "conversion_end_date",
            "발행금액",
            "potential_share_count",
            "잔여권면총액_추정",
            "잔여가능주식수_추정",
            "잔여시총대비비율_추정",
            "위험등급",
        ]
        if col in mezz_df.columns
    ]
    st.dataframe(to_korean_columns(mezz_df[remaining_cols]), use_container_width=True, hide_index=True)
    st.caption("현재 추정치는 전환/행사/교환 종료일이 지난 회차만 0으로 보고, 행사·상환·소각 공시 차감은 아직 반영하지 않습니다.")

    calendar_cols = [
        col
        for col in [
            "disclosure_name",
            "corp_name",
            "bd_tm",
            "conversion_start_date",
            "conversion_end_date",
            "potential_share_count",
            "전환가액",
            "발행금액",
            "희석률",
            "위험등급",
        ]
        if col in mezz_df.columns
    ]
    calendar_df = mezz_df.dropna(subset=["conversion_start_date"])[calendar_cols].copy()

    if calendar_df.empty:
        st.info("전환/행사/교환 청구 시작일 데이터가 없습니다. 기준일 추출 현황에서 원본 날짜 필드가 채워졌는지 확인해 주세요.")
    else:
        calendar_df["calendar_size"] = calendar_df["potential_share_count"].fillna(calendar_df["발행금액"] / 1000)
        calendar_df["calendar_size"] = calendar_df["calendar_size"].replace(0, np.nan)
        st.dataframe(to_korean_columns(calendar_df.sort_values("conversion_start_date")), use_container_width=True)

        timeline_fig = px.scatter(
            calendar_df,
            x="conversion_start_date",
            y="발행금액",
            size="calendar_size",
            color="위험등급",
            hover_data=[
                col
                for col in ["disclosure_name", "corp_name", "bd_tm", "potential_share_count", "희석률"]
                if col in calendar_df.columns
            ],
            title="전환청구 가능 물량",
            labels={
                **korean_labels(calendar_df.columns),
                "calendar_size": "표시 물량",
            },
        )
        timeline_fig.update_layout(height=420)
        st.plotly_chart(timeline_fig, use_container_width=True)

with tabs[4]:
    st.subheader("악성 CB 구조 탐지")

    warning_messages = make_warning_messages(mezz_df)

    if warning_messages:
        for message in warning_messages:
            st.warning(message)
    else:
        st.success("탐지된 고위험 메자닌 구조가 없습니다.")

    toxic_df = mezz_df[mezz_df["위험점수"] >= 60]

    if toxic_df.empty:
        st.success("고위험 CB 없음")
    else:
        st.error("고위험 메자닌 탐지")
        toxic_cols = [col for col in ["corp_name", "bd_tm", "위험점수", "위험등급"] if col in toxic_df.columns]
        st.dataframe(to_korean_columns(toxic_df[toxic_cols]), use_container_width=True)

    st.subheader("AI 자동 해석")
    avg_dilution = mezz_df["희석률"].mean()

    if pd.isna(avg_dilution):
        st.info("희석률 데이터가 없어 자동 해석을 생성할 수 없습니다.")
    else:
        if avg_dilution >= 15:
            dilution_comment = "희석 위험이 높은 편입니다."
        elif avg_dilution >= 5:
            dilution_comment = "중간 수준 희석 위험입니다."
        else:
            dilution_comment = "희석 위험은 낮은 수준입니다."

        if latest_risk >= 70:
            risk_comment = "리픽싱 및 전환가능 물량으로 인해 잠재 오버행 부담이 큽니다."
        elif latest_risk >= 40:
            risk_comment = "일부 전환물량 부담이 존재합니다."
        else:
            risk_comment = "메자닌 구조 리스크는 제한적입니다."

        st.info(
            f"""
            평균 희석률: {avg_dilution:.2f}%

            종합 의견: {dilution_comment}

            리스크 평가: {risk_comment}

            투자 해석: 전환청구 시작일 전후 수급 변동성과 오버행 여부를 모니터링할 필요가 있습니다.
            """
        )

with tabs[5]:
    st.subheader("회차별 조기상환 스케줄")
    st.caption("상단에서 회차를 선택하면 해당 공시의 조기상환·옵션·자금 사용 표만 모아 보여줍니다.")

    repayment_keywords = ["조기상환", "조기 상환", "Put Option", "풋옵션", "매도청구"]
    option_keywords = ["콜옵션", "Call Option", "매수청구권", "풋옵션", "Put Option", "매도청구권"]
    funding_detail_keywords = ["자금의 사용", "자금사용", "사용목적", "자금조달의 목적", "사용내역"]

    round_rows = mezz_df[mezz_df["rcept_no"].notna()].copy() if "rcept_no" in mezz_df.columns else pd.DataFrame()

    if round_rows.empty:
        st.info("접수번호가 없어 공시 원문 상세를 조회할 수 없습니다.")
    else:
        round_rows = round_rows.sort_values(["event_date", "bd_tm"], ascending=[False, True], na_position="last")
        round_rows = round_rows.reset_index(drop=True)
        round_rows["_round_option"] = round_rows.apply(
            lambda row: " / ".join(
                [
                    str(row.get("bd_tm", "회차 미상")),
                    str(row.get("disclosure_name", "공시")),
                    row["event_date"].strftime("%Y-%m-%d") if pd.notna(row.get("event_date")) else "일자 미상",
                    str(row.get("rcept_no", "")),
                ]
            ),
            axis=1,
        )

        overview_cols = [
            col
            for col in [
                "disclosure_name",
                "bd_tm",
                "event_date",
                "payment_date",
                "bd_fta",
                "전환가액",
                "희석률",
                "위험등급",
                "rcept_no",
            ]
            if col in round_rows.columns
        ]
        st.dataframe(to_korean_columns(round_rows[overview_cols]), use_container_width=True, hide_index=True)

        selected_round_option = st.selectbox(
            "상세 조회 회차",
            round_rows["_round_option"].tolist(),
            index=0,
        )
        selected_row = round_rows.loc[round_rows["_round_option"] == selected_round_option].iloc[0]
        selected_rcept_no = selected_row.get("rcept_no")
        dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={selected_rcept_no}"

        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
        summary_col1.metric("회차", selected_row.get("bd_tm", "-"))
        summary_col2.metric("공시유형", selected_row.get("disclosure_name", "-"))
        summary_col3.metric(
            "발행결정일",
            selected_row["event_date"].strftime("%Y-%m-%d") if pd.notna(selected_row.get("event_date")) else "-",
        )
        summary_col4.metric(
            "발행금액",
            f"{selected_row.get('발행금액') / 100000000:.1f}억" if pd.notna(selected_row.get("발행금액")) else "-",
        )
        st.markdown(f"[DART 원문 열기]({dart_url})")

        try:
            document_tables = get_disclosure_document_tables(API_KEY, selected_rcept_no)
        except (requests.RequestException, ValueError) as error:
            st.warning(f"공시 원문 표를 불러오지 못했습니다: {error}")
            document_tables = []

        repayment_tables = filter_document_tables(document_tables, repayment_keywords)
        option_tables = filter_document_tables(document_tables, option_keywords)
        funding_detail_tables = filter_document_tables(document_tables, funding_detail_keywords)

        detail_tabs = st.tabs(["조기상환", "콜/풋옵션", "자금 사용"])

        with detail_tabs[0]:
            if repayment_tables:
                for table_index, table in repayment_tables:
                    st.caption(f"원문 표 #{table_index}")
                    st.dataframe(table, use_container_width=True, hide_index=True)
            else:
                st.info("선택한 회차에서 조기상환 스케줄 표를 찾지 못했습니다.")

        with detail_tabs[1]:
            if option_tables:
                for table_index, table in option_tables:
                    st.caption(f"원문 표 #{table_index}")
                    st.dataframe(table, use_container_width=True, hide_index=True)
            else:
                st.info("선택한 회차에서 콜옵션/풋옵션 상세 표를 찾지 못했습니다.")

        with detail_tabs[2]:
            if funding_detail_tables:
                for table_index, table in funding_detail_tables:
                    st.caption(f"원문 표 #{table_index}")
                    st.dataframe(table, use_container_width=True, hide_index=True)
            else:
                st.info("선택한 회차에서 자금 사용 상세 표를 찾지 못했습니다.")

    st.subheader("자금 사용 목적 요약")
    funding_df = build_funding_purpose_df(mezz_df)

    if funding_df.empty:
        st.info("OpenDART 기본 응답에서 자금 사용 목적 데이터를 찾지 못했습니다.")
    else:
        st.dataframe(to_korean_columns(funding_df), use_container_width=True, hide_index=True)

        purpose_value_cols = [
            col
            for col in ["fdpp_fclt", "fdpp_bsninh", "fdpp_op", "fdpp_dtrp", "fdpp_ocsa", "fdpp_etc"]
            if col in funding_df.columns
        ]
        chart_df = funding_df.melt(
            id_vars=[col for col in ["bd_tm", "disclosure_name"] if col in funding_df.columns],
            value_vars=purpose_value_cols,
            var_name="자금용도",
            value_name="금액",
        ).dropna(subset=["금액"])
        chart_df = chart_df[chart_df["금액"] != 0]
        chart_df["자금용도"] = chart_df["자금용도"].map(KOREAN_COLUMN_NAMES).fillna(chart_df["자금용도"])

        if not chart_df.empty:
            funding_fig = px.bar(
                chart_df,
                x="자금용도",
                y="금액",
                color="bd_tm" if "bd_tm" in chart_df.columns else None,
                barmode="group",
                title="회차별 자금 사용 목적",
                labels={"자금용도": "자금용도", "금액": "금액", "bd_tm": "회차"},
            )
            funding_fig.update_layout(height=420)
            st.plotly_chart(funding_fig, use_container_width=True)


with tabs[6]:
    st.subheader("전체 원본 데이터")
    display_df = to_korean_columns(mezz_df)
    st.dataframe(display_df, use_container_width=True)

    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="CSV 다운로드",
        data=csv,
        file_name=f"{company_name}_CB분석.csv",
        mime="text/csv",
    )


with tabs[7]:
    st.subheader("SEIBro 데이터")
    st.caption("발행인명으로 SEIBro 채권 발행 목록을 먼저 조회한 뒤, 취합된 종목코드(ISIN)를 선택합니다.")

    seibro_url = "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/bond/BIP_CNTS03018V.xml&menuNo=104"
    st.markdown(f"[SEIBro 원문 화면 열기]({seibro_url})")

    seibro_col1, seibro_col2, seibro_col3 = st.columns([1.5, 1, 0.8])

    with seibro_col1:
        seibro_issuer_name = st.text_input("발행인", value=company_name, key="seibro_issuer_name")
    with seibro_col2:
        seibro_issue_start_date = normalize_date(
            st.date_input("발행일 시작", value=OPENDART_DATA_START_DATE, key="seibro_issue_start_date")
        )
    with seibro_col3:
        st.write("")
        st.write("")
        seibro_search_btn = st.button("발행인 조회", key="seibro_issuer_search")

    if seibro_search_btn:
        with st.spinner("SEIBro에서 발행인 기준 채권 목록을 조회 중입니다."):
            try:
                seibro_list_df = fetch_seibro_issuance_list(
                    corp_name=seibro_issuer_name,
                    issue_start_date=seibro_issue_start_date,
                    issue_end_date=date.today(),
                )
            except Exception as error:
                st.warning(f"SEIBro 발행인 조회 실패: {error}")
                seibro_list_df = pd.DataFrame()

        st.session_state["seibro_list_df"] = seibro_list_df
        st.session_state["seibro_isin_options"] = extract_seibro_isin_options(seibro_list_df)

    seibro_list_df = st.session_state.get("seibro_list_df", pd.DataFrame())
    seibro_isin_options = st.session_state.get("seibro_isin_options", [])

    if seibro_list_df.empty:
        st.info("발행인 조회를 먼저 눌러 주세요. 조회기간 발행일 시작 기본값은 2015-01-01입니다.")
    else:
        st.markdown("#### 발행인 조회 결과")
        st.dataframe(seibro_list_df, use_container_width=True, hide_index=True)

        if not seibro_isin_options:
            st.warning("조회 결과에서 종목코드(ISIN)를 자동 추출하지 못했습니다. 원문 결과의 컬럼명을 확인해 주세요.")
        else:
            option_labels = [option["label"] for option in seibro_isin_options]
            selected_isin_label = st.selectbox("종목코드(ISIN) 선택", option_labels, key="seibro_selected_isin_label")
            selected_isin = next(
                option["isin"]
                for option in seibro_isin_options
                if option["label"] == selected_isin_label
            )
            st.success(f"선택한 ISIN: {selected_isin}")

            if st.button("선택 ISIN 상세 조회", key="seibro_isin_detail_fetch"):
                with st.spinner("SEIBro에서 선택 ISIN 상세 데이터를 조회 중입니다."):
                    try:
                        seibro_detail_df = fetch_seibro_issuance_list(isin=selected_isin)
                    except Exception as error:
                        st.warning(f"SEIBro ISIN 상세 조회 실패: {error}")
                        seibro_detail_df = pd.DataFrame()

                    selected_bond_name = ""
                    if not seibro_list_df.empty and "ISIN" in seibro_list_df.columns:
                        matched_bond = seibro_list_df[seibro_list_df["ISIN"] == selected_isin]
                        if not matched_bond.empty:
                            selected_bond_name = clean_display_text(matched_bond.iloc[0].get("KOR_SECN_NM", ""))

                    try:
                        seibro_mobile_tables = fetch_seibro_mobile_bond_tables(selected_isin, selected_bond_name)
                    except Exception as error:
                        st.warning(f"SEIBro 모바일 상세 표 조회 실패: {error}")
                        seibro_mobile_tables = []

                if seibro_detail_df.empty:
                    st.info("선택한 ISIN의 상세 데이터를 찾지 못했습니다.")
                else:
                    st.markdown("#### 선택 ISIN 상세")
                    st.dataframe(to_korean_columns(seibro_detail_df), use_container_width=True, hide_index=True)

                    detail_row = seibro_detail_df.iloc[0]
                    mobile_sections = classify_seibro_mobile_tables(seibro_mobile_tables)
                    seibro_detail_tabs = st.tabs(["채권원리금", "수익률", "조기행사옵션", "주식관련 옵션", "전체 상세"])

                    with seibro_detail_tabs[0]:
                        principal_df = seibro_section_df(
                            detail_row,
                            ["FIRST_ISSU_AMT", "ISSU_REMA", "COUPON_RATE", "INT_KIND", "PRIN_RCV_FNCECO", "XPIR_DT", "RECU_WHCD", "RANK"],
                        )
                        if principal_df.empty and not mobile_sections["채권원리금"]:
                            st.info("채권원리금 관련 데이터를 찾지 못했습니다.")
                        else:
                            if not principal_df.empty:
                                st.dataframe(principal_df, use_container_width=True, hide_index=True)
                            for index, table in enumerate(mobile_sections["채권원리금"], start=1):
                                st.caption(f"SEIBro 표 #{index}")
                                st.dataframe(table, use_container_width=True, hide_index=True)

                    with seibro_detail_tabs[1]:
                        yield_df = seibro_section_df(
                            detail_row,
                            ["COUPON_RATE", "XPIR_GUAR_PRATE", "PRATE", "RATE", "YIELD", "INT_KIND"],
                        )
                        if yield_df.empty and not mobile_sections["수익률"]:
                            st.info("수익률 관련 데이터를 찾지 못했습니다.")
                        else:
                            if not yield_df.empty:
                                st.dataframe(yield_df, use_container_width=True, hide_index=True)
                            for index, table in enumerate(mobile_sections["수익률"], start=1):
                                st.caption(f"SEIBro 표 #{index}")
                                st.dataframe(table, use_container_width=True, hide_index=True)

                    with seibro_detail_tabs[2]:
                        option_df = seibro_section_df(
                            detail_row,
                            ["OPTION", "CALL", "PUT"],
                        )
                        if option_df.empty and not mobile_sections["조기행사옵션"]:
                            st.info("조기행사옵션 데이터를 찾지 못했습니다.")
                        else:
                            if not option_df.empty:
                                st.dataframe(option_df, use_container_width=True, hide_index=True)
                            for index, table in enumerate(mobile_sections["조기행사옵션"], start=1):
                                st.caption(f"SEIBro 표 #{index}")
                                st.dataframe(table, use_container_width=True, hide_index=True)

                    with seibro_detail_tabs[3]:
                        stock_option_df = seibro_section_df(
                            detail_row,
                            ["PARTICUL_BOND", "STOCK", "WARRANT", "CV", "EXER", "행사", "전환", "교환"],
                        )
                        if stock_option_df.empty and not mobile_sections["주식관련옵션"]:
                            st.info("주식관련 옵션 데이터를 찾지 못했습니다.")
                        else:
                            if not stock_option_df.empty:
                                st.dataframe(stock_option_df, use_container_width=True, hide_index=True)
                            for index, table in enumerate(mobile_sections["주식관련옵션"], start=1):
                                st.caption(f"SEIBro 표 #{index}")
                                st.dataframe(table, use_container_width=True, hide_index=True)

                    with seibro_detail_tabs[4]:
                        st.dataframe(to_korean_columns(seibro_detail_df), use_container_width=True, hide_index=True)
                        for index, table in enumerate(seibro_mobile_tables, start=1):
                            st.caption(f"모바일 상세 표 #{index}")
                            st.dataframe(table, use_container_width=True, hide_index=True)
