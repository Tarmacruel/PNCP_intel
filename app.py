from __future__ import annotations

import math
import re
import time
from datetime import date, datetime
from io import BytesIO
from typing import Any

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from advanced_charts import (
    build_boxplot_top_orgaos,
    build_bubble_organs,
    build_funnel_status,
    build_heatmap_uf_year,
    build_scatter_value_over_time,
    build_sunburst_hierarchy,
    build_treemap_hierarchy,
)
from advanced_filters import apply_advanced_filters
from pdf_generator import pdf_generator

from components import (
    alert as ui_alert,
    chart_wrapper,
    empty_state as ui_empty_state,
    footer_block,
    metric_card as ui_metric_card,
    paginated_table,
    render_loading_skeleton,
    section_header,
)


st.set_page_config(
    page_title="PNCP Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_TITLE = "PNCP Intelligence"
SEARCH_API_URL = "https://pncp.gov.br/api/search/"
DETAIL_API_BASE = "https://pncp.gov.br/api/pncp/v1/orgaos"
CONSULTA_CONTRATOS_API_URL = "https://pncp.gov.br/api/consulta/v1/contratos"
APP_BASE_URL = "https://pncp.gov.br/app"
REPO_URL = "https://github.com/Tarmacruel/PNCP_intel"
CACHE_TTL_SECONDS = 3600
SEARCH_WINDOW_LIMIT = 10000
DEFAULT_PAGE_SIZE = SEARCH_WINDOW_LIMIT
CONSULTA_PAGE_SIZE = 500
MAX_RETRIES = 4
DEFAULT_SORT = "-data"
ASCENDING_SORT = "data"
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
YEAR_RANGE_LIMIT = 5
COLOR_PRIMARY = "#14526E"
COLOR_PRIMARY_SOFT = "#72A8C4"
COLOR_ACCENT = "#C68432"
COLOR_ACCENT_SOFT = "#E8BE86"
COLOR_SUCCESS = "#2F8F66"
COLOR_TEXT = "#163348"
COLOR_SUBTEXT = "#5D7185"
COLOR_GRID = "rgba(22, 51, 72, 0.10)"
COLOR_AXIS = "rgba(22, 51, 72, 0.18)"
COLOR_SURFACE = "#FFFFFF"
EXCEL_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]")


class PncpApiError(RuntimeError):
    """Raised when the PNCP public endpoints cannot satisfy the request."""


def load_css() -> None:
    st.markdown(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap");

        :root {
            --primary: #12344d;
            --primary-dark: #0b2437;
            --secondary: #2f5f7e;
            --accent: #c17b2d;
            --accent-2: #d89443;
            --success: #1f8f63;
            --warning: #cb7a19;
            --danger: #b94848;
            --bg-app: #f4f7fb;
            --bg-card: rgba(255, 255, 255, 0.94);
            --bg-soft: #ecf2f7;
            --text-primary: #11283b;
            --text-secondary: #66788a;
            --border: rgba(18, 52, 77, 0.11);
            --shadow-sm: 0 10px 24px rgba(17, 40, 59, 0.05);
            --shadow-md: 0 20px 50px rgba(17, 40, 59, 0.08);
            --shadow-lg: 0 30px 70px rgba(17, 40, 59, 0.14);
            --radius: 18px;
            --radius-lg: 26px;
            --transition: all .22s ease;
        }

        html, body, [class*="css"] { font-family: "Manrope", sans-serif; }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(193, 123, 45, 0.12), transparent 22%),
                radial-gradient(circle at 15% 10%, rgba(18, 52, 77, 0.08), transparent 28%),
                linear-gradient(180deg, #fbfdff 0%, var(--bg-app) 100%);
        }

        #MainMenu, header, footer { visibility: hidden; }
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(11,36,55,.985) 0%, rgba(18,52,77,.985) 65%, rgba(34,69,95,.98) 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stSidebar"] * { color: #f8fbff; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div { color: inherit; }
        [data-testid="stSidebar"] [data-baseweb="input"] input,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            color: var(--text-primary) !important;
            background: rgba(255,255,255,.95) !important;
        }

        .masthead {
            position: relative;
            overflow: hidden;
            padding: 1.8rem 1.8rem;
            border-radius: var(--radius-lg);
            background:
                linear-gradient(132deg, rgba(11,36,55,.99) 0%, rgba(18,52,77,.97) 52%, rgba(47,95,126,.95) 78%, rgba(193,123,45,.86) 100%);
            box-shadow: var(--shadow-lg);
            color: white;
            margin-bottom: 1.1rem;
            border: 1px solid rgba(255,255,255,.08);
            animation: rise .34s ease-out;
        }

        .masthead::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(120deg, rgba(255,255,255,.04), transparent 34%),
                radial-gradient(circle at 84% 18%, rgba(255,255,255,.18), transparent 22%);
            pointer-events: none;
        }

        .masthead-grid {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: minmax(0, 1.55fr) minmax(260px, .9fr);
            gap: 1.2rem;
            align-items: end;
        }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            padding: .38rem .74rem;
            border-radius: 999px;
            background: rgba(255,255,255,.12);
            font-size: .74rem;
            font-weight: 800;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: rgba(255,255,255,.96);
        }

        .masthead h1 {
            margin: .85rem 0 .5rem;
            font-size: clamp(2rem, 3vw, 2.8rem);
            line-height: 1.02;
            letter-spacing: -.03em;
            font-weight: 800;
            color: #ffffff !important;
        }

        .masthead p {
            margin: 0;
            max-width: 62ch;
            font-size: 1rem;
            line-height: 1.62;
            color: rgba(255,255,255,.88) !important;
        }

        .masthead-note {
            padding: 1rem 1.05rem;
            border-radius: 20px;
            background: rgba(255,255,255,.11);
            border: 1px solid rgba(255,255,255,.12);
            backdrop-filter: blur(10px);
        }

        .masthead-note strong {
            display: block;
            margin-bottom: .45rem;
            font-size: .76rem;
            letter-spacing: .08em;
            text-transform: uppercase;
            opacity: .82;
            color: #ffffff;
        }

        .masthead-note span {
            display: block;
            line-height: 1.55;
            font-size: .98rem;
            color: #ffffff;
        }

        .info-card,
        .filter-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: var(--shadow-sm);
            padding: 1rem 1.1rem;
            animation: rise .34s ease-out;
        }

        .section-title {
            margin: 0;
            color: var(--text-primary);
            font-size: 1rem;
            font-weight: 800;
            letter-spacing: -.02em;
        }

        .section-copy {
            margin: .25rem 0 0;
            color: var(--text-secondary);
            font-size: .92rem;
            line-height: 1.56;
        }

        .section-block {
            margin: 0 0 .8rem;
            padding-bottom: .4rem;
        }

        .section-title-row {
            display: flex;
            align-items: center;
            gap: .55rem;
        }

        .section-icon {
            display: inline-flex;
            width: 1.85rem;
            height: 1.85rem;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            background: rgba(18,52,77,.08);
            color: var(--primary);
            font-weight: 700;
        }

        .section-heading {
            margin: 0;
            color: var(--text-primary);
            font-size: 1.08rem;
            font-weight: 800;
            letter-spacing: -.02em;
        }

        .metric-card {
            background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(248,251,255,.92));
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1rem 1.05rem;
            min-height: 152px;
            box-shadow: var(--shadow-sm);
            transition: var(--transition);
            display: flex;
            flex-direction: column;
            gap: .26rem;
            animation: rise .36s ease-out;
        }

        .metric-card:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow-md);
            border-color: rgba(47,95,126,.25);
        }

        .metric-icon {
            width: 2.2rem;
            height: 2.2rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 14px;
            background: linear-gradient(135deg, rgba(18,52,77,.08), rgba(193,123,45,.12));
            color: var(--primary);
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: .15rem;
        }

        .metric-label {
            color: var(--text-secondary);
            font-size: .73rem;
            font-weight: 800;
            letter-spacing: .08em;
            text-transform: uppercase;
        }

        .metric-value {
            color: var(--text-primary);
            font-size: clamp(1.28rem, 2vw, 1.9rem);
            font-weight: 800;
            letter-spacing: -.03em;
            line-height: 1.08;
        }

        .ui-delta {
            margin-top: auto;
            padding-top: .35rem;
            color: var(--text-secondary);
            font-size: .84rem;
            font-weight: 600;
        }

        .ui-delta-positive { color: var(--success); }
        .ui-delta-warning { color: var(--warning); }
        .ui-delta-negative { color: var(--danger); }

        .pill-row,
        .table-toolbar {
            display: flex;
            flex-wrap: wrap;
            gap: .5rem;
            margin-top: .8rem;
        }

        .pill,
        .ui-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: .4rem .72rem;
            border-radius: 999px;
            font-size: .76rem;
            font-weight: 700;
            line-height: 1;
            white-space: nowrap;
        }

        .pill,
        .ui-badge-primary {
            background: rgba(18,52,77,.08);
            color: var(--primary);
        }

        .ui-badge-success {
            background: rgba(31,143,99,.12);
            color: var(--success);
        }

        .ui-badge-warning {
            background: rgba(203,122,25,.14);
            color: var(--warning);
        }

        .ui-badge-danger {
            background: rgba(185,72,72,.12);
            color: var(--danger);
        }

        .ui-alert {
            display: flex;
            gap: .7rem;
            align-items: flex-start;
            padding: .95rem 1rem;
            margin: .8rem 0 1rem;
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
        }

        .ui-alert-icon {
            width: 1.75rem;
            height: 1.75rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            font-weight: 800;
            font-size: .86rem;
            flex-shrink: 0;
        }

        .ui-alert-text {
            line-height: 1.58;
            font-size: .92rem;
            color: var(--text-primary);
        }

        .ui-alert-info {
            background: rgba(18,52,77,.05);
        }

        .ui-alert-info .ui-alert-icon {
            background: rgba(18,52,77,.12);
            color: var(--primary);
        }

        .ui-alert-warning {
            background: rgba(203,122,25,.08);
            border-color: rgba(203,122,25,.16);
        }

        .ui-alert-warning .ui-alert-icon {
            background: rgba(203,122,25,.14);
            color: var(--warning);
        }

        .ui-alert-success {
            background: rgba(31,143,99,.08);
            border-color: rgba(31,143,99,.16);
        }

        .ui-alert-success .ui-alert-icon {
            background: rgba(31,143,99,.14);
            color: var(--success);
        }

        .ui-alert-error {
            background: rgba(185,72,72,.08);
            border-color: rgba(185,72,72,.18);
        }

        .ui-alert-error .ui-alert-icon {
            background: rgba(185,72,72,.14);
            color: var(--danger);
        }

        .empty-state {
            text-align: center;
            padding: 2.3rem 1.5rem;
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(255,255,255,.96), rgba(239,244,250,.9));
            border: 1px dashed rgba(18,52,77,.18);
            box-shadow: var(--shadow-sm);
        }

        .empty-state-icon {
            font-size: 2.8rem;
            line-height: 1;
            margin-bottom: .85rem;
        }

        .empty-state h3 {
            margin: 0 0 .42rem;
            color: var(--text-primary);
            font-size: 1.08rem;
            font-weight: 800;
        }

        .empty-state p {
            margin: 0 auto;
            max-width: 52ch;
            color: var(--text-secondary);
            line-height: 1.66;
        }

        .ui-skeleton-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin: 1rem 0 1.2rem;
        }

        .ui-skeleton-card,
        .ui-skeleton-chart {
            border-radius: 18px;
            background: linear-gradient(90deg, #eef3f7 25%, #e2eaf1 50%, #eef3f7 75%);
            background-size: 200% 100%;
            animation: shimmer 1.6s infinite linear;
        }

        .ui-skeleton-card { height: 146px; }
        .ui-skeleton-chart { height: 360px; }

        .stTabs [data-baseweb="tab-list"] {
            gap: .5rem;
            padding-bottom: .3rem;
            margin-bottom: .35rem;
            overflow-x: auto;
            scrollbar-width: none;
        }

        .stTabs [data-baseweb="tab"] {
            height: auto;
            padding: .72rem 1rem;
            border-radius: 999px;
            background: rgba(255,255,255,.84);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            font-weight: 700;
            transition: var(--transition);
            white-space: nowrap;
        }

        .stTabs [data-baseweb="tab"]:hover {
            border-color: rgba(18,52,77,.18);
            color: var(--text-primary);
            transform: translateY(-1px);
        }

        .stTabs [aria-selected="true"] {
            color: var(--primary) !important;
            border-color: rgba(18,52,77,.22);
            box-shadow: 0 12px 26px rgba(17,40,59,.08);
            background: rgba(255,255,255,.98);
        }

        .stButton > button,
        .stDownloadButton > button,
        .stFormSubmitButton > button {
            width: 100%;
            border: 0;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
            color: white;
            font-weight: 800;
            padding: .74rem 1rem;
            box-shadow: 0 14px 30px rgba(193,123,45,.24);
            transition: var(--transition);
        }

        .stButton > button p,
        .stDownloadButton > button p,
        .stFormSubmitButton > button p {
            color: #ffffff !important;
            margin: 0;
        }

        .stButton > button:focus,
        .stDownloadButton > button:focus,
        .stFormSubmitButton > button:focus {
            outline: none !important;
            box-shadow: 0 0 0 4px rgba(193,123,45,.16), 0 14px 30px rgba(193,123,45,.24) !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        .stFormSubmitButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 18px 36px rgba(193,123,45,.3);
            background: linear-gradient(135deg, #b76e20 0%, var(--accent) 100%);
            color: white;
            border: 0;
        }

        .stTextInput input,
        .stDateInput input,
        [data-baseweb="select"] > div,
        .stNumberInput input {
            border-radius: 14px !important;
            border: 1px solid rgba(18,52,77,.14) !important;
            background: rgba(255,255,255,.95) !important;
            color: var(--text-primary) !important;
            min-height: 46px;
        }

        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] label,
        .stMultiSelect label,
        .stSelectbox label {
            color: var(--text-primary) !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }

        [data-baseweb="select"] > div {
            box-shadow: 0 1px 2px rgba(17, 40, 59, 0.04);
        }

        [data-baseweb="select"] span,
        [data-baseweb="select"] input,
        [data-baseweb="tag"] span {
            color: var(--text-primary) !important;
            opacity: 1 !important;
        }

        [data-baseweb="select"] [aria-hidden="true"] {
            color: var(--text-secondary) !important;
            opacity: 1 !important;
        }

        [data-baseweb="tag"] {
            background: rgba(20, 82, 110, 0.08) !important;
            border-radius: 999px !important;
            border: 1px solid rgba(20, 82, 110, 0.12) !important;
        }

        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
        [data-testid="stSidebar"] .stMultiSelect label,
        [data-testid="stSidebar"] .stSelectbox label {
            color: #f8fbff !important;
        }

        .stTextInput input:focus,
        .stDateInput input:focus,
        .stNumberInput input:focus {
            border-color: rgba(47,95,126,.4) !important;
            box-shadow: 0 0 0 4px rgba(47,95,126,.08) !important;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 22px;
            overflow: hidden;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            background: rgba(255,255,255,.95);
        }

        .stPlotlyChart {
            border-radius: 22px;
            border: 1px solid var(--border);
            background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(250,252,255,.96));
            box-shadow: var(--shadow-sm);
            padding: .35rem .45rem;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }

        .stPlotlyChart:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
            border-color: rgba(18,52,77,.16);
        }

        .footer-shell {
            margin-top: 2rem;
            padding: 1.5rem 1rem 2.3rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: .88rem;
            border-top: 1px solid rgba(18,52,77,.1);
        }

        .footer-shell p {
            margin: .15rem 0;
        }

        .footer-shell a {
            color: var(--secondary);
            text-decoration: none;
            font-weight: 700;
        }

        @keyframes rise {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        @media (max-width: 1080px) {
            .ui-skeleton-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }

        @media (max-width: 980px) {
            .masthead-grid { grid-template-columns: 1fr; }
        }

        @media (max-width: 768px) {
            .block-container { padding-top: 1rem; }
            .masthead { padding: 1.35rem 1.2rem; }
            .masthead h1 { font-size: 1.7rem; }
            .masthead p { font-size: .94rem; }
            .masthead-note { padding: .9rem .95rem; border-radius: 16px; }
            .metric-card { min-height: 138px; }
            .metric-value { font-size: 1.45rem; }
            .info-card, .filter-card { padding: .9rem .95rem; }
            .section-copy { font-size: .88rem; }
            .section-heading { font-size: 1rem; }
            .stTabs [data-baseweb="tab"] { padding: .62rem .92rem; font-size: .86rem; }
            .stPlotlyChart { border-radius: 18px; padding: .2rem .2rem; }
            div[data-testid="stDataFrame"] { border-radius: 18px; }
            .table-toolbar { gap: .35rem; }
            .ui-skeleton-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_cnpj(raw_value: str) -> str:
    return "".join(filter(str.isdigit, raw_value or ""))


def format_cnpj_display(raw_value: str) -> str:
    cnpj = format_cnpj(raw_value)
    if len(cnpj) != 14:
        return raw_value
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def validate_cnpj(raw_value: str) -> bool:
    cnpj = format_cnpj(raw_value)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    weights_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    total_1 = sum(int(cnpj[index]) * weights_1[index] for index in range(12))
    digit_1 = 0 if total_1 % 11 < 2 else 11 - (total_1 % 11)
    if digit_1 != int(cnpj[12]):
        return False

    total_2 = sum(int(cnpj[index]) * weights_2[index] for index in range(13))
    digit_2 = 0 if total_2 % 11 < 2 else 11 - (total_2 % 11)
    return digit_2 == int(cnpj[13])


def format_currency(value: float | int | None) -> str:
    numeric = float(value or 0)
    formatted = f"{numeric:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def format_integer(value: int | float | None) -> str:
    if value is None or pd.isna(value):
        return "0"
    return f"{int(value):,}".replace(",", ".")


def extract_error_message(response: httpx.Response) -> str:
    raw_text = response.text.strip().strip('"')
    return raw_text[:180] if raw_text else "Resposta vazia"


def request_json(client: httpx.Client, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.get(url, params=params)

            if response.status_code == 204:
                return {}

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "2")
                delay = max(1, int(retry_after)) if retry_after.isdigit() else min(2**attempt, 8)
                time.sleep(delay)
                continue

            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            is_http_error = isinstance(exc, httpx.HTTPStatusError)
            status_code = exc.response.status_code if is_http_error and exc.response is not None else None

            if status_code and status_code < 500 and status_code not in {408, 429}:
                response_message = extract_error_message(exc.response) if exc.response is not None else "Sem detalhe"
                raise PncpApiError(
                    f"Erro definitivo do PNCP ({status_code}) ao consultar {url}: {response_message}."
                ) from exc

            if attempt == MAX_RETRIES:
                break

            time.sleep(min(2**attempt, 8))

    raise PncpApiError("Nao foi possivel consultar o PNCP no momento.") from last_error


def extract_detail_parts(item_url: str) -> tuple[str, str, str] | None:
    if not item_url:
        return None

    parts = item_url.strip("/").split("/")
    if len(parts) != 4 or parts[0] != "contratos":
        return None

    return parts[1], parts[2], parts[3]


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_contract_detail(item_url: str) -> dict[str, Any]:
    detail_parts = extract_detail_parts(item_url)
    if not detail_parts:
        return {}

    orgao_cnpj, ano, sequencial = detail_parts
    url = f"{DETAIL_API_BASE}/{orgao_cnpj}/contratos/{ano}/{sequencial}"

    with httpx.Client(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": f"{APP_TITLE}/1.0"},
    ) as client:
        return request_json(client, url)


def build_search_params(query: str, *, sort: str, document_types: str) -> dict[str, Any]:
    return {
        "q": query,
        "tipos_documento": document_types,
        "ordenacao": sort,
        "pagina": 1,
        "tam_pagina": DEFAULT_PAGE_SIZE,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_search_index(query: str, *, document_types: str) -> dict[str, Any]:
    all_items: list[dict[str, Any]] = []

    with httpx.Client(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": f"{APP_TITLE}/1.0"},
    ) as client:
        recent_payload = request_json(
            client,
            SEARCH_API_URL,
            params=build_search_params(query, sort=DEFAULT_SORT, document_types=document_types),
        )
        recent_items = recent_payload.get("items", []) or []
        total_records = int(recent_payload.get("total") or len(recent_items))
        total_pages = max(1, math.ceil(total_records / DEFAULT_PAGE_SIZE)) if total_records else 1
        all_items.extend(recent_items)

        search_strategy = "janela_unica"
        retrieved_windows = 1

        # O endpoint de busca do PNCP permite no maximo uma janela de 10 mil resultados por ordenacao.
        # Para carteiras entre 10.001 e 20.000 itens, abrimos a janela espelhada em ordem crescente
        # e unimos as duas pontas do indice.
        if total_records > SEARCH_WINDOW_LIMIT:
            oldest_payload = request_json(
                client,
                SEARCH_API_URL,
                params=build_search_params(query, sort=ASCENDING_SORT, document_types=document_types),
            )
            all_items.extend(oldest_payload.get("items", []) or [])
            search_strategy = "janela_dupla"
            retrieved_windows = 2

    deduplicated_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in all_items:
        unique_key = item.get("numero_controle_pncp") or item.get("id") or item.get("item_url")
        if not unique_key or unique_key in seen_ids:
            continue
        seen_ids.add(unique_key)
        deduplicated_items.append(item)

    retrieved_records = len(deduplicated_items)
    is_partial = total_records > (SEARCH_WINDOW_LIMIT * retrieved_windows) and retrieved_records < total_records

    return {
        "items": deduplicated_items,
        "total_records": total_records,
        "total_pages": total_pages,
        "retrieved_records": retrieved_records,
        "search_strategy": search_strategy,
        "retrieved_windows": retrieved_windows,
        "is_partial": is_partial,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_contract_search(cnpj: str) -> dict[str, Any]:
    search_payload = fetch_search_index(cnpj, document_types="contrato")
    deduplicated_items = search_payload.get("items", []) or []

    supplier_name = None
    sample_checked = 0
    sample_exact_match = True
    sample_indexes = {0, 1, 2, max(len(deduplicated_items) - 3, 0), max(len(deduplicated_items) - 1, 0)}
    for sample_item in [deduplicated_items[index] for index in sorted(sample_indexes) if index < len(deduplicated_items)]:
        detail = fetch_contract_detail(sample_item.get("item_url", ""))
        if not detail:
            continue
        sample_checked += 1
        supplier_name = supplier_name or detail.get("nomeRazaoSocialFornecedor")
        if detail.get("niFornecedor") != cnpj:
            sample_exact_match = False

    return {
        "items": deduplicated_items,
        "total_records": search_payload.get("total_records", len(deduplicated_items)),
        "total_pages": search_payload.get("total_pages", 1),
        "retrieved_records": search_payload.get("retrieved_records", len(deduplicated_items)),
        "search_strategy": search_payload.get("search_strategy", "janela_unica"),
        "retrieved_windows": search_payload.get("retrieved_windows", 1),
        "is_partial": search_payload.get("is_partial", False),
        "supplier_name": supplier_name,
        "sample_checked": sample_checked,
        "sample_exact_match": sample_exact_match,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_organ_contract_enrichment(cnpj: str, start_year: int, end_year: int) -> pd.DataFrame:
    all_records: list[dict[str, Any]] = []

    with httpx.Client(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": f"{APP_TITLE}/1.0"},
    ) as client:
        for year in range(start_year, end_year + 1):
            params = {
                "dataInicial": f"{year}0101",
                "dataFinal": f"{year}1231",
                "cnpjOrgao": cnpj,
                "pagina": 1,
                "tamanhoPagina": CONSULTA_PAGE_SIZE,
            }

            while True:
                payload = request_json(client, CONSULTA_CONTRATOS_API_URL, params=params)
                records = payload.get("data", []) or []
                all_records.extend(records)

                total_pages = int(payload.get("totalPaginas") or 1)
                current_page = int(payload.get("numeroPagina") or params["pagina"])
                if current_page >= total_pages or not records:
                    break

                params["pagina"] += 1

    if not all_records:
        return pd.DataFrame()

    enrichment_df = pd.DataFrame(all_records).copy()
    enrichment_df["numero_controle_pncp"] = enrichment_df.get("numeroControlePNCP", "").fillna("")
    enrichment_df["fornecedor_cnpj"] = enrichment_df.get("niFornecedor", "").fillna("")
    enrichment_df["fornecedor_nome"] = enrichment_df.get("nomeRazaoSocialFornecedor", "").fillna("")
    enrichment_df["valor_global_api"] = pd.to_numeric(enrichment_df.get("valorGlobal"), errors="coerce")
    enrichment_df["data_assinatura_api"] = pd.to_datetime(enrichment_df.get("dataAssinatura"), errors="coerce")
    enrichment_df["ano_api"] = pd.to_numeric(enrichment_df.get("anoContrato"), errors="coerce").astype("Int64")

    return enrichment_df[
        [
            "numero_controle_pncp",
            "fornecedor_cnpj",
            "fornecedor_nome",
            "valor_global_api",
            "data_assinatura_api",
            "ano_api",
        ]
    ].drop_duplicates(subset=["numero_controle_pncp"], keep="last")


def normalize_contracts(payload: dict[str, Any], cnpj: str) -> pd.DataFrame:
    items = payload.get("items", []) or []
    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items).copy()

    defaults = {
        "description": "",
        "item_url": "",
        "title": "Contrato",
        "numero_controle_pncp": "",
        "unidade_nome": "Nao informada",
        "municipio_nome": "Nao informado",
        "numero_sequencial": "",
        "orgao_cnpj": "",
        "situacao_nome": "Nao informado",
        "orgao_nome": "Nao informado",
        "modalidade_licitacao_nome": "Nao informada",
        "tipo_contrato_nome": "Nao informado",
        "uf": "N/A",
        "esfera_nome": "Nao informada",
        "poder_nome": "Nao informado",
    }
    for column_name, default_value in defaults.items():
        if column_name not in df.columns:
            df[column_name] = default_value

    df["valor_global"] = pd.to_numeric(df.get("valor_global"), errors="coerce").fillna(0.0)
    df["ano"] = pd.to_numeric(df.get("ano"), errors="coerce").astype("Int64")
    df["data_assinatura"] = pd.to_datetime(df.get("data_assinatura"), errors="coerce")
    df["data_publicacao_pncp"] = pd.to_datetime(df.get("data_publicacao_pncp"), errors="coerce")
    df["data_atualizacao_pncp"] = pd.to_datetime(df.get("data_atualizacao_pncp"), errors="coerce")
    df["data_referencia"] = df["data_assinatura"].fillna(df["data_publicacao_pncp"])
    df["mes_ano"] = df["data_referencia"].dt.to_period("M").dt.to_timestamp()
    df["link_pncp"] = df["item_url"].fillna("").apply(
        lambda value: f"{APP_BASE_URL}{value}" if value else APP_BASE_URL
    )
    df["objeto"] = df["description"].fillna("Sem descricao publicada")
    df["titulo"] = df["title"].fillna("Contrato")
    df["fornecedor_cnpj"] = cnpj
    df["fornecedor_nome"] = payload.get("supplier_name") or "Fornecedor consultado"

    display_order = [
        "numero_controle_pncp",
        "titulo",
        "objeto",
        "orgao_nome",
        "unidade_nome",
        "municipio_nome",
        "uf",
        "situacao_nome",
        "modalidade_licitacao_nome",
        "tipo_contrato_nome",
        "esfera_nome",
        "poder_nome",
        "valor_global",
        "data_assinatura",
        "data_publicacao_pncp",
        "data_atualizacao_pncp",
        "ano",
        "link_pncp",
        "numero_sequencial",
        "orgao_cnpj",
        "fornecedor_cnpj",
        "fornecedor_nome",
    ]

    available_order = [column for column in display_order if column in df.columns]
    remainder = [column for column in df.columns if column not in available_order]
    return df[available_order + remainder].sort_values(
        by=["data_referencia", "valor_global"],
        ascending=[False, False],
        na_position="last",
    )


def normalize_organ_documents(
    payload: dict[str, Any],
    cnpj: str,
    *,
    start_year: int,
    end_year: int,
    contract_enrichment: pd.DataFrame | None = None,
) -> pd.DataFrame:
    items = payload.get("items", []) or []
    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items).copy()

    defaults = {
        "description": "",
        "item_url": "",
        "title": "Documento PNCP",
        "numero_controle_pncp": "",
        "unidade_nome": "Nao informada",
        "unidade_codigo": "",
        "municipio_nome": "Nao informado",
        "numero_sequencial": "",
        "orgao_cnpj": "",
        "situacao_nome": "Nao informado",
        "orgao_nome": "Nao informado",
        "modalidade_licitacao_nome": "Nao informada",
        "tipo_nome": "Nao informado",
        "tipo_contrato_nome": "Nao informado",
        "document_type": "contrato",
        "uf": "N/A",
        "esfera_nome": "Nao informada",
        "poder_nome": "Nao informado",
    }
    for column_name, default_value in defaults.items():
        if column_name not in df.columns:
            df[column_name] = default_value

    df["orgao_cnpj"] = df["orgao_cnpj"].fillna("").astype(str)
    df = df[df["orgao_cnpj"] == cnpj].copy()
    if df.empty:
        return pd.DataFrame()

    df["valor_global"] = pd.to_numeric(df.get("valor_global"), errors="coerce").fillna(0.0)
    df["ano"] = pd.to_numeric(df.get("ano"), errors="coerce").astype("Int64")
    df = df[df["ano"].between(start_year, end_year, inclusive="both")].copy()
    if df.empty:
        return pd.DataFrame()

    df["data_assinatura"] = pd.to_datetime(df.get("data_assinatura"), errors="coerce")
    df["data_publicacao_pncp"] = pd.to_datetime(df.get("data_publicacao_pncp"), errors="coerce")
    df["data_atualizacao_pncp"] = pd.to_datetime(df.get("data_atualizacao_pncp"), errors="coerce")
    df["data_referencia"] = (
        df["data_assinatura"]
        .fillna(df["data_publicacao_pncp"])
        .fillna(df["data_atualizacao_pncp"])
    )
    df["mes_ano"] = df["data_referencia"].dt.to_period("M").dt.to_timestamp()
    df["link_pncp"] = df["item_url"].fillna("").apply(
        lambda value: f"{APP_BASE_URL}{value}" if value else APP_BASE_URL
    )
    df["objeto"] = df["description"].fillna("Sem descricao publicada")
    df["titulo"] = df["title"].fillna("Documento PNCP")
    df["document_type"] = df["document_type"].fillna("contrato")
    df["document_type_label"] = df["document_type"].map(
        {
            "contrato": "Contratos e empenhos",
            "edital": "Compras/Licitacoes",
            "ata": "Atas",
        }
    ).fillna("Outros documentos")
    df["fornecedor_cnpj"] = ""
    df["fornecedor_nome"] = df["document_type"].map(
        {
            "edital": "Nao se aplica",
            "ata": "Nao informado",
        }
    ).fillna("Nao informado")

    if contract_enrichment is not None and not contract_enrichment.empty:
        df = df.merge(
            contract_enrichment,
            how="left",
            on="numero_controle_pncp",
        )
        df["fornecedor_cnpj"] = df.get("fornecedor_cnpj_x", "").fillna("")
        df["fornecedor_nome"] = df.get("fornecedor_nome_x", "Nao informado").fillna("Nao informado")
        contract_mask = df["document_type"].eq("contrato")
        df.loc[contract_mask, "fornecedor_cnpj"] = (
            df.loc[contract_mask, "fornecedor_cnpj_y"].fillna(df.loc[contract_mask, "fornecedor_cnpj"]).fillna("")
        )
        df.loc[contract_mask, "fornecedor_nome"] = (
            df.loc[contract_mask, "fornecedor_nome_y"].fillna(df.loc[contract_mask, "fornecedor_nome"]).fillna("Nao informado")
        )
        df.loc[contract_mask, "valor_global"] = (
            df.loc[contract_mask, "valor_global_api"].fillna(df.loc[contract_mask, "valor_global"])
        )
        df.loc[contract_mask, "data_assinatura"] = (
            df.loc[contract_mask, "data_assinatura_api"].fillna(df.loc[contract_mask, "data_assinatura"])
        )
        df.loc[contract_mask, "ano"] = df.loc[contract_mask, "ano_api"].fillna(df.loc[contract_mask, "ano"])
        drop_columns = [
            "fornecedor_cnpj_x",
            "fornecedor_cnpj_y",
            "fornecedor_nome_x",
            "fornecedor_nome_y",
            "valor_global_api",
            "data_assinatura_api",
            "ano_api",
        ]
        df = df.drop(columns=[column for column in drop_columns if column in df.columns])

    display_order = [
        "document_type",
        "document_type_label",
        "numero_controle_pncp",
        "titulo",
        "objeto",
        "orgao_nome",
        "orgao_cnpj",
        "unidade_codigo",
        "unidade_nome",
        "municipio_nome",
        "uf",
        "situacao_nome",
        "modalidade_licitacao_nome",
        "tipo_nome",
        "tipo_contrato_nome",
        "valor_global",
        "data_assinatura",
        "data_publicacao_pncp",
        "data_atualizacao_pncp",
        "data_referencia",
        "ano",
        "fornecedor_cnpj",
        "fornecedor_nome",
        "link_pncp",
        "numero_sequencial",
        "esfera_nome",
        "poder_nome",
    ]

    available_order = [column for column in display_order if column in df.columns]
    remainder = [column for column in df.columns if column not in available_order]
    return df[available_order + remainder].sort_values(
        by=["data_referencia", "valor_global"],
        ascending=[False, False],
        na_position="last",
    )


def apply_dashboard_filters(
    df: pd.DataFrame,
    *,
    start_date: date | None,
    end_date: date | None,
    orgaos: list[str],
    anos: list[int],
    situacoes: list[str],
) -> pd.DataFrame:
    filtered = df.copy()

    if start_date:
        filtered = filtered[filtered["data_referencia"] >= pd.Timestamp(start_date)]
    if end_date:
        filtered = filtered[filtered["data_referencia"] < pd.Timestamp(end_date) + pd.Timedelta(days=1)]
    if orgaos:
        filtered = filtered[filtered["orgao_nome"].isin(orgaos)]
    if anos:
        filtered = filtered[filtered["ano"].isin(anos)]
    if situacoes:
        filtered = filtered[filtered["situacao_nome"].isin(situacoes)]

    return filtered


def apply_organ_dashboard_filters(
    df: pd.DataFrame,
    *,
    search_text: str,
    document_types: list[str],
    years: list[int],
    units: list[str],
    suppliers: list[str],
    modalities: list[str],
    situations: list[str],
) -> pd.DataFrame:
    filtered = df.copy()

    if search_text.strip():
        normalized_text = search_text.strip().lower()
        filtered = filtered[
            filtered["objeto"].fillna("").str.lower().str.contains(normalized_text)
            | filtered["titulo"].fillna("").str.lower().str.contains(normalized_text)
            | filtered["numero_controle_pncp"].fillna("").str.lower().str.contains(normalized_text)
        ]

    if document_types:
        filtered = filtered[filtered["document_type"].isin(document_types)]
    if years:
        filtered = filtered[filtered["ano"].isin(years)]
    if units:
        filtered = filtered[filtered["unidade_nome"].isin(units)]
    if suppliers:
        filtered = filtered[filtered["fornecedor_nome"].isin(suppliers)]
    if modalities:
        filtered = filtered[filtered["modalidade_licitacao_nome"].isin(modalities)]
    if situations:
        filtered = filtered[filtered["situacao_nome"].isin(situations)]

    return filtered


def render_masthead(query_scope: str) -> None:
    if query_scope == "organ":
        title = "Panorama anual de orgaos publicos no PNCP"
        description = (
            "Consulte contratos, compras/licitações e atas a partir do CNPJ do orgao, "
            "aplique faixa obrigatoria de anos e explore a base consolidada por objeto, unidade e fornecedor."
        )
        note = (
            "Busca publica do portal PNCP com recorte operacional por faixa de anos e apoio do endpoint "
            "oficial de contratos para enriquecimento de fornecedor."
        )
    else:
        title = "Dossie de contratos publicos por fornecedor"
        description = (
            "Consulte contratos e empenhos publicados no PNCP a partir do CNPJ da empresa, "
            "aplique recortes operacionais e exporte a base tratada para Excel ou CSV."
        )
        note = (
            "Busca publica do portal PNCP com paginacao automatica e enriquecimento por endpoint "
            "de detalhe para verificacao do fornecedor."
        )

    st.markdown(
        f"""
        <section class="masthead">
            <div class="masthead-grid">
                <div>
                    <span class="eyebrow">Painel analitico do PNCP</span>
                    <h1>{title}</h1>
                    <p>{description}</p>
                </div>
                <div class="masthead-note">
                    <strong>Fonte operacional</strong>
                    <span>{note}</span>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

def render_filter_summary(
    cnpj: str,
    supplier_name: str,
    total_records: int,
    retrieved_records: int,
    start_date: date | None,
    end_date: date | None,
    sample_checked: int,
    sample_exact_match: bool,
    search_strategy: str,
    is_partial: bool,
) -> None:
    if start_date and end_date:
        period_label = f"{start_date.strftime('%d/%m/%Y')} ate {end_date.strftime('%d/%m/%Y')}"
    elif start_date:
        period_label = f"A partir de {start_date.strftime('%d/%m/%Y')}"
    elif end_date:
        period_label = f"Ate {end_date.strftime('%d/%m/%Y')}"
    else:
        period_label = "Todo o historico indexado"

    if sample_checked == 0:
        quality_label = "Sem validacao amostral"
    else:
        quality_label = "Verificacao amostral ok" if sample_exact_match else "Indice exige revisao manual"

    if search_strategy == "janela_dupla":
        strategy_label = "Cobertura bidirecional do indice"
    else:
        strategy_label = "Janela unica do indice"

    coverage_label = (
        f"Base recuperada: {format_integer(retrieved_records)} de {format_integer(total_records)}"
        if is_partial
        else f"Base recuperada: {format_integer(retrieved_records)} contratos"
    )

    st.markdown(
        f"""
        <div class="info-card">
            <p class="section-title">{supplier_name or "Fornecedor consultado"}</p>
            <p class="section-copy">
                CNPJ {format_cnpj_display(cnpj)} | {format_integer(total_records)} contratos indexados no portal
            </p>
            <div class="pill-row">
                <span class="pill">Periodo: {period_label}</span>
                <span class="pill">{strategy_label}</span>
                <span class="pill">{coverage_label}</span>
                <span class="pill">Recorte amostral: {sample_checked} contrato(s)</span>
                <span class="pill">{quality_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_organ_filter_summary(
    *,
    cnpj: str,
    organ_name: str,
    total_records: int,
    retrieved_records: int,
    exact_records: int,
    start_year: int,
    end_year: int,
    search_strategy: str,
    is_partial: bool,
    enrichment_status: str,
) -> None:
    if start_year == end_year:
        period_label = f"Ano analisado: {start_year}"
    else:
        period_label = f"Faixa anual: {start_year} a {end_year}"

    strategy_label = "Cobertura bidirecional do indice" if search_strategy == "janela_dupla" else "Janela unica do indice"
    coverage_label = (
        f"Base exata no recorte: {format_integer(exact_records)} registros"
        if not is_partial
        else f"Base exata no recorte: {format_integer(exact_records)} de {format_integer(total_records)}"
    )

    st.markdown(
        f"""
        <div class="info-card">
            <p class="section-title">{organ_name or "Orgao publico consultado"}</p>
            <p class="section-copy">
                CNPJ {format_cnpj_display(cnpj)} | {format_integer(retrieved_records)} registros recuperados do indice
            </p>
            <div class="pill-row">
                <span class="pill">{period_label}</span>
                <span class="pill">{strategy_label}</span>
                <span class="pill">{coverage_label}</span>
                <span class="pill">{enrichment_status}</span>
                <span class="pill">{format_integer(total_records)} registros brutos na busca</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def shorten_label(value: str, *, limit: int = 44) -> str:
    if not value:
        return "Nao informado"
    compact = " ".join(str(value).split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1]}…"


def build_empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        font=dict(family="Manrope, sans-serif", size=14, color=COLOR_SUBTEXT),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_SURFACE,
        margin=dict(l=16, r=16, t=16, b=16),
    )
    return fig


def apply_chart_theme(fig: go.Figure, *, height: int, hovermode: str = "closest") -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_SURFACE,
        margin=dict(l=18, r=18, t=20, b=12),
        font=dict(family="Manrope, sans-serif", size=13, color=COLOR_TEXT),
        hovermode=hovermode,
        hoverlabel=dict(
            bgcolor="#0F2434",
            bordercolor="rgba(255,255,255,0.16)",
            font=dict(family="Manrope, sans-serif", size=12, color="white"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title_text="",
            font=dict(size=12, color=COLOR_SUBTEXT),
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=COLOR_GRID,
        linecolor=COLOR_AXIS,
        tickfont=dict(color=COLOR_SUBTEXT, size=11),
        title_font=dict(color=COLOR_SUBTEXT, size=12),
        zeroline=False,
        automargin=True,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=COLOR_GRID,
        linecolor=COLOR_AXIS,
        tickfont=dict(color=COLOR_SUBTEXT, size=11),
        title_font=dict(color=COLOR_SUBTEXT, size=12),
        zeroline=False,
        automargin=True,
    )
    return fig


def build_top_orgs_chart(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby("orgao_nome", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("valor_total", ascending=False)
        .head(10)
        .sort_values("valor_total", ascending=True)
    )
    if grouped.empty:
        return build_empty_chart("Sem dados suficientes para montar o ranking de orgaos.")

    grouped["orgao_curto"] = grouped["orgao_nome"].apply(shorten_label)
    grouped["valor_label"] = grouped["valor_total"].apply(format_currency)
    grouped["qtd_label"] = grouped["quantidade"].apply(format_integer)

    fig = go.Figure()
    fig.add_bar(
        x=grouped["valor_total"],
        y=grouped["orgao_curto"],
        orientation="h",
        marker=dict(color=COLOR_PRIMARY, line=dict(color="#0F3044", width=0)),
        customdata=grouped[["orgao_nome", "qtd_label", "valor_label"]],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Valor total: %{customdata[2]}<br>"
            "Qtd. contratos: %{customdata[1]}<extra></extra>"
        ),
    )
    apply_chart_theme(fig, height=480)
    fig.update_layout(showlegend=False, bargap=0.24)
    fig.update_xaxes(title="Valor total contratado", tickprefix="R$ ")
    fig.update_yaxes(title="", showgrid=False)
    return fig


def build_status_chart(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby("situacao_nome", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("quantidade", ascending=True)
    )
    if grouped.empty:
        return build_empty_chart("Sem status publicados para exibir.")

    grouped["situacao_curta"] = grouped["situacao_nome"].apply(lambda value: shorten_label(value, limit=28))
    grouped["qtd_label"] = grouped["quantidade"].apply(format_integer)
    grouped["valor_label"] = grouped["valor_total"].apply(format_currency)

    fig = go.Figure()
    fig.add_bar(
        x=grouped["quantidade"],
        y=grouped["situacao_curta"],
        orientation="h",
        marker=dict(
            color=[COLOR_PRIMARY if index == len(grouped) - 1 else COLOR_PRIMARY_SOFT for index in range(len(grouped))]
        ),
        customdata=grouped[["situacao_nome", "qtd_label", "valor_label"]],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Qtd. contratos: %{customdata[1]}<br>"
            "Valor total: %{customdata[2]}<extra></extra>"
        ),
    )
    apply_chart_theme(fig, height=480)
    fig.update_layout(showlegend=False, bargap=0.3)
    fig.update_xaxes(title="Quantidade de contratos")
    fig.update_yaxes(title="", showgrid=False)
    return fig


def build_timeline_chart(df: pd.DataFrame) -> go.Figure:
    monthly = (
        df.dropna(subset=["mes_ano"])
        .groupby("mes_ano")
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("mes_ano")
    )
    if monthly.empty:
        return build_empty_chart("Nao ha serie temporal suficiente para este recorte.")

    monthly["valor_label"] = monthly["valor_total"].apply(format_currency)
    monthly["qtd_label"] = monthly["quantidade"].apply(format_integer)

    fig = go.Figure()
    fig.add_scatter(
        x=monthly["mes_ano"],
        y=monthly["valor_total"],
        name="Valor total",
        mode="lines+markers",
        line=dict(color=COLOR_PRIMARY, width=3),
        marker=dict(size=7, color=COLOR_PRIMARY),
        fill="tozeroy",
        fillcolor="rgba(20, 82, 110, 0.10)",
        customdata=monthly[["valor_label", "qtd_label"]],
        hovertemplate="%{x|%m/%Y}<br>Valor total: %{customdata[0]}<br>Qtd. contratos: %{customdata[1]}<extra></extra>",
    )
    fig.add_bar(
        x=monthly["mes_ano"],
        y=monthly["quantidade"],
        name="Qtd. contratos",
        marker_color="rgba(198, 132, 50, 0.70)",
        yaxis="y2",
        hovertemplate="%{x|%m/%Y}<br>Qtd. contratos: %{y}<extra></extra>",
    )
    apply_chart_theme(fig, height=430, hovermode="x unified")
    fig.update_layout(bargap=0.5)
    fig.update_xaxes(title="Mes de referencia", tickformat="%b/%y")
    fig.update_yaxes(title="Valor total contratado", tickprefix="R$ ", rangemode="tozero")
    fig.update_layout(
        yaxis2=dict(
            title="Qtd. contratos",
            overlaying="y",
            side="right",
            rangemode="tozero",
            showgrid=False,
            tickfont=dict(color=COLOR_SUBTEXT, size=11),
            title_font=dict(color=COLOR_SUBTEXT, size=12),
        )
    )
    return fig


def build_yearly_chart(df: pd.DataFrame) -> go.Figure:
    yearly = (
        df.dropna(subset=["ano"])
        .groupby("ano")
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("ano")
    )
    if yearly.empty:
        return build_empty_chart("Nao ha consolidacao anual para este recorte.")

    yearly["ano_label"] = yearly["ano"].astype("Int64").astype(str)
    yearly["valor_label"] = yearly["valor_total"].apply(format_currency)
    yearly["qtd_label"] = yearly["quantidade"].apply(format_integer)

    fig = go.Figure()
    fig.add_bar(
        x=yearly["ano_label"],
        y=yearly["quantidade"],
        name="Qtd. contratos",
        marker_color=COLOR_ACCENT,
        customdata=yearly[["valor_label", "qtd_label"]],
        hovertemplate="%{x}<br>Qtd. contratos: %{customdata[1]}<br>Valor total: %{customdata[0]}<extra></extra>",
    )
    fig.add_scatter(
        x=yearly["ano_label"],
        y=yearly["valor_total"],
        name="Valor total",
        mode="lines+markers",
        line=dict(color=COLOR_PRIMARY, width=3),
        marker=dict(size=7, color=COLOR_PRIMARY),
        yaxis="y2",
        customdata=yearly[["valor_label", "qtd_label"]],
        hovertemplate="%{x}<br>Valor total: %{customdata[0]}<br>Qtd. contratos: %{customdata[1]}<extra></extra>",
    )
    apply_chart_theme(fig, height=430, hovermode="x unified")
    fig.update_xaxes(title="Ano")
    fig.update_yaxes(title="Qtd. contratos", rangemode="tozero")
    fig.update_layout(
        yaxis2=dict(
            title="Valor total",
            overlaying="y",
            side="right",
            rangemode="tozero",
            showgrid=False,
            tickprefix="R$ ",
            tickfont=dict(color=COLOR_SUBTEXT, size=11),
            title_font=dict(color=COLOR_SUBTEXT, size=12),
        )
    )
    return fig


def build_value_histogram(df: pd.DataFrame) -> go.Figure:
    positive_values = df["valor_global"].fillna(0).clip(lower=1)
    if positive_values.empty:
        return build_empty_chart("Nao ha valores para distribuir.")

    histogram_df = pd.DataFrame(
        {
            "valor_log10": positive_values.apply(lambda value: math.log10(max(float(value), 1.0))),
        }
    )

    fig = px.histogram(
        histogram_df,
        x="valor_log10",
        nbins=min(24, max(10, int(math.sqrt(len(histogram_df))))),
        color_discrete_sequence=[COLOR_PRIMARY],
    )
    apply_chart_theme(fig, height=410)
    fig.update_layout(bargap=0.08, showlegend=False)
    fig.update_xaxes(
        title="Faixas de valor em escala logaritmica",
        tickvals=[3, 4, 5, 6, 7, 8],
        ticktext=["R$ 1 mil", "R$ 10 mil", "R$ 100 mil", "R$ 1 mi", "R$ 10 mi", "R$ 100 mi"],
    )
    fig.update_yaxes(title="Qtd. contratos")
    fig.update_traces(
        hovertemplate="Faixa log10: %{x:.2f}<br>Qtd. contratos: %{y}<extra></extra>",
        marker_line_width=0,
    )

    median_value = positive_values.median()
    fig.add_vline(
        x=math.log10(max(float(median_value), 1.0)),
        line_width=2,
        line_dash="dash",
        line_color=COLOR_ACCENT,
        annotation_text=f"Mediana: {format_currency(median_value)}",
        annotation_position="top left",
        annotation_font=dict(color=COLOR_ACCENT, size=11),
    )
    return fig


def build_value_band_chart(df: pd.DataFrame) -> go.Figure:
    bands_df = build_value_bands(df)
    if bands_df.empty:
        return build_empty_chart("Nao ha faixas suficientes para este recorte.")

    bands_df["faixa_label"] = bands_df["faixa_valor"].astype(str)
    bands_df["valor_label"] = bands_df["valor_total"].apply(format_currency)
    bands_df["share_label"] = bands_df["participacao"].map(lambda value: f"{value:.1f}% da carteira")

    fig = go.Figure()
    fig.add_bar(
        x=bands_df["valor_total"],
        y=bands_df["faixa_label"],
        orientation="h",
        marker=dict(
            color=[COLOR_PRIMARY, "#2E6C8A", "#5A87A2", COLOR_ACCENT_SOFT, COLOR_ACCENT][: len(bands_df)]
        ),
        text=bands_df["share_label"],
        textposition="outside",
        cliponaxis=False,
        customdata=bands_df[["valor_label", "quantidade"]],
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Valor total: %{customdata[0]}<br>"
            "Qtd. contratos: %{customdata[1]}<extra></extra>"
        ),
    )
    apply_chart_theme(fig, height=410)
    fig.update_layout(showlegend=False, bargap=0.28)
    fig.update_xaxes(title="Valor total por faixa", tickprefix="R$ ")
    fig.update_yaxes(title="", showgrid=False)
    return fig


def build_value_bands(df: pd.DataFrame) -> pd.DataFrame:
    bands = pd.cut(
        df["valor_global"],
        bins=[0, 50000, 500000, 1000000, 5000000, float("inf")],
        labels=[
            "Ate R$ 50 mil",
            "R$ 50 mil a 500 mil",
            "R$ 500 mil a 1 mi",
            "R$ 1 mi a 5 mi",
            "Acima de R$ 5 mi",
        ],
        include_lowest=True,
    )

    summary = (
        df.assign(faixa_valor=bands)
        .groupby("faixa_valor", observed=True)
        .agg(
            quantidade=("numero_controle_pncp", "count"),
            valor_total=("valor_global", "sum"),
            valor_medio=("valor_global", "mean"),
        )
        .reset_index()
    )
    summary["participacao"] = summary["quantidade"].div(max(len(df), 1)).mul(100)
    return summary


def build_document_mix_chart(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby("document_type_label", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"))
        .reset_index()
        .sort_values("quantidade", ascending=False)
    )
    if grouped.empty:
        return build_empty_chart("Nao ha documentos suficientes para compor o panorama.")

    fig = go.Figure(
        go.Pie(
            labels=grouped["document_type_label"],
            values=grouped["quantidade"],
            hole=0.58,
            marker=dict(colors=[COLOR_PRIMARY, COLOR_ACCENT, COLOR_PRIMARY_SOFT][: len(grouped)]),
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Qtd. registros: %{value}<extra></extra>",
        )
    )
    apply_chart_theme(fig, height=430)
    fig.update_layout(showlegend=False)
    return fig


def build_top_suppliers_chart(df: pd.DataFrame) -> go.Figure:
    contracts_df = df[
        df["document_type"].eq("contrato")
        & df["fornecedor_nome"].fillna("").ne("")
        & ~df["fornecedor_nome"].isin(["Nao informado", "Nao se aplica"])
    ].copy()
    grouped = (
        contracts_df.groupby("fornecedor_nome", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("valor_total", ascending=False)
        .head(10)
        .sort_values("valor_total", ascending=True)
    )
    if grouped.empty:
        return build_empty_chart("Os contratos deste recorte nao trouxeram fornecedores suficientes para ranking.")

    grouped["fornecedor_curto"] = grouped["fornecedor_nome"].apply(lambda value: shorten_label(value, limit=34))
    grouped["valor_label"] = grouped["valor_total"].apply(format_currency)
    grouped["qtd_label"] = grouped["quantidade"].apply(format_integer)

    fig = go.Figure()
    fig.add_bar(
        x=grouped["valor_total"],
        y=grouped["fornecedor_curto"],
        orientation="h",
        marker=dict(color=COLOR_PRIMARY, line=dict(width=0)),
        customdata=grouped[["fornecedor_nome", "qtd_label", "valor_label"]],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Valor total: %{customdata[2]}<br>"
            "Qtd. contratos: %{customdata[1]}<extra></extra>"
        ),
    )
    apply_chart_theme(fig, height=460)
    fig.update_layout(showlegend=False, bargap=0.24)
    fig.update_xaxes(title="Valor total contratado", tickprefix="R$ ")
    fig.update_yaxes(title="", showgrid=False)
    return fig


def build_top_units_chart(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby(["unidade_nome", "uf"], dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("valor_total", ascending=False)
        .head(10)
        .sort_values("valor_total", ascending=True)
    )
    if grouped.empty:
        return build_empty_chart("Nao ha unidades suficientes para o ranking.")

    grouped["unidade_label"] = grouped.apply(
        lambda row: shorten_label(f"{row['unidade_nome']} ({row['uf']})", limit=34),
        axis=1,
    )
    grouped["valor_label"] = grouped["valor_total"].apply(format_currency)
    grouped["qtd_label"] = grouped["quantidade"].apply(format_integer)

    fig = go.Figure()
    fig.add_bar(
        x=grouped["valor_total"],
        y=grouped["unidade_label"],
        orientation="h",
        marker=dict(color=COLOR_ACCENT, line=dict(width=0)),
        customdata=grouped[["unidade_nome", "uf", "qtd_label", "valor_label"]],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "UF: %{customdata[1]}<br>"
            "Qtd. registros: %{customdata[2]}<br>"
            "Valor total: %{customdata[3]}<extra></extra>"
        ),
    )
    apply_chart_theme(fig, height=460)
    fig.update_layout(showlegend=False, bargap=0.24)
    fig.update_xaxes(title="Valor total", tickprefix="R$ ")
    fig.update_yaxes(title="", showgrid=False)
    return fig


def build_modality_chart(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby("modalidade_licitacao_nome", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"))
        .reset_index()
        .sort_values("quantidade", ascending=False)
        .head(10)
        .sort_values("quantidade", ascending=True)
    )
    if grouped.empty:
        return build_empty_chart("Nao ha modalidades suficientes para este recorte.")

    grouped["modalidade_curta"] = grouped["modalidade_licitacao_nome"].apply(lambda value: shorten_label(value, limit=28))

    fig = go.Figure()
    fig.add_bar(
        x=grouped["quantidade"],
        y=grouped["modalidade_curta"],
        orientation="h",
        marker=dict(color=COLOR_PRIMARY_SOFT, line=dict(width=0)),
        customdata=grouped["modalidade_licitacao_nome"],
        hovertemplate="<b>%{customdata}</b><br>Qtd. registros: %{x}<extra></extra>",
    )
    apply_chart_theme(fig, height=430)
    fig.update_layout(showlegend=False, bargap=0.28)
    fig.update_xaxes(title="Quantidade")
    fig.update_yaxes(title="", showgrid=False)
    return fig


def build_top_objects_summary(df: pd.DataFrame, *, limit: int = 15) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    objects_df = df.copy()
    objects_df["objeto_grupo"] = objects_df["objeto"].fillna("Sem descricao publicada").apply(lambda value: shorten_label(value, limit=100))

    return (
        objects_df.groupby("objeto_grupo", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values(["quantidade", "valor_total"], ascending=[False, False])
        .head(limit)
    )


def prepare_export_payload(
    df: pd.DataFrame,
    meta: dict[str, Any],
    *,
    export_format: str,
    include_charts: bool,
    filter_summary: str,
) -> tuple[bytes, str, str, str]:
    query_scope = meta.get("query_scope", "supplier")
    if query_scope == "organ":
        file_stem = f"pncp_orgao_{meta.get('cnpj', '')}_{meta.get('start_year', '-')}_{meta.get('end_year', '-')}"
    else:
        file_stem = f"pncp_contratos_{meta.get('cnpj', '')}"

    if export_format == "CSV":
        payload = dataframe_to_csv_bytes(df)
        return payload, f"{file_stem}.csv", "text/csv", "Download CSV"

    if export_format == "Excel":
        payload = build_excel_report_bytes(df, meta, filter_summary)
        return (
            payload,
            f"{file_stem}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Download Excel",
        )

    chart_payload = None
    if include_charts:
        if query_scope == "organ":
            contracts_df = df[df["document_type"].eq("contrato")].copy()
            timeline_source = contracts_df if not contracts_df.empty else df
            chart_payload = {
                "top_orgs": build_top_suppliers_chart(df),
                "timeline": build_yearly_chart(timeline_source),
                "value_band": build_document_mix_chart(df),
            }
        else:
            chart_payload = {
                "top_orgs": build_top_orgs_chart(df),
                "timeline": build_timeline_chart(df),
                "value_band": build_value_band_chart(df),
            }

    report_mode = "full" if export_format == "PDF Completo" else "executive"
    payload = pdf_generator.generate_pdf(
        df,
        meta=meta,
        filter_summary=filter_summary,
        charts=chart_payload,
        report_mode=report_mode,
    )
    return payload, f"{file_stem}.pdf", "application/pdf", "Download PDF"


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sanitize_dataframe_for_excel(df).to_excel(writer, index=False, sheet_name="Contratos")
    return output.getvalue()


def sanitize_excel_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return EXCEL_ILLEGAL_CHARS_RE.sub("", value)


def sanitize_dataframe_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    sanitized_df = df.copy()
    object_columns = sanitized_df.select_dtypes(include=["object", "string"]).columns
    for column_name in object_columns:
        sanitized_df[column_name] = sanitized_df[column_name].map(sanitize_excel_text)
    return sanitized_df


def build_excel_report_bytes(df: pd.DataFrame, meta: dict[str, Any], filter_summary: str) -> bytes:
    export_df = df.copy()
    for column_name in ["data_assinatura", "data_publicacao_pncp", "data_atualizacao_pncp", "data_referencia", "mes_ano"]:
        if column_name in export_df.columns:
            export_df[column_name] = pd.to_datetime(export_df[column_name], errors="coerce").dt.strftime("%Y-%m-%d")

    query_scope = meta.get("query_scope", "supplier")
    if query_scope == "organ":
        summary_rows = [
            ["Escopo", "Consulta por orgao publico"],
            ["Orgao", meta.get("organ_name", "Orgao publico consultado")],
            ["CNPJ do orgao", meta.get("cnpj", "-")],
            ["Faixa de anos", f"{meta.get('start_year', '-')} a {meta.get('end_year', '-')}"],
            ["Registros brutos no indice", meta.get("total_records", len(df))],
            ["Registros recuperados", meta.get("retrieved_records", len(df))],
            ["Base exata no recorte", meta.get("exact_records", len(df))],
            ["Valor total", format_currency(df["valor_global"].sum())],
            ["Fornecedores distintos", format_integer(df["fornecedor_nome"].replace(["Nao informado", "Nao se aplica"], pd.NA).dropna().nunique())],
            ["Unidades distintas", format_integer(df["unidade_nome"].nunique())],
            ["Filtros ativos", filter_summary],
            ["Atualizado em", meta.get("fetched_at", "-")],
        ]
        ranking_df = (
            df[df["document_type"].eq("contrato")]
            .groupby("fornecedor_nome", dropna=False)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
            .sort_values("valor_total", ascending=False)
            .head(20)
            .rename(columns={"fornecedor_nome": "fornecedor"})
        )
        ranking_sheet_name = "Top_fornecedores"
        export_sheet_name = "Base_consolidada"
    else:
        summary_rows = [
            ["Escopo", "Consulta por fornecedor"],
            ["Fornecedor", meta.get("supplier_name", "Fornecedor consultado")],
            ["CNPJ", meta.get("cnpj", "-")],
            ["Contratos indexados", meta.get("total_records", len(df))],
            ["Contratos recuperados", meta.get("retrieved_records", len(df))],
            ["Valor total", format_currency(df["valor_global"].sum())],
            ["Valor medio", format_currency(df["valor_global"].mean())],
            ["Orgaos distintos", format_integer(df["orgao_nome"].nunique())],
            ["Filtros ativos", filter_summary],
            ["Atualizado em", meta.get("fetched_at", "-")],
        ]
        ranking_df = (
            df.groupby("orgao_nome", dropna=False)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
            .sort_values("valor_total", ascending=False)
            .head(20)
        )
        ranking_sheet_name = "Top_orgaos"
        export_sheet_name = "Contratos"

    summary_df = pd.DataFrame(summary_rows, columns=["Metrica", "Valor"])
    summary_df = sanitize_dataframe_for_excel(summary_df)
    ranking_df = sanitize_dataframe_for_excel(ranking_df)
    export_df = sanitize_dataframe_for_excel(export_df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Resumo")
        ranking_df.to_excel(writer, index=False, sheet_name=ranking_sheet_name)
        export_df.to_excel(writer, index=False, sheet_name=export_sheet_name)

    return output.getvalue()


def render_sidebar() -> dict[str, Any]:
    with st.sidebar:
        st.markdown("## Jornada de consulta")
        st.caption("Alterne entre fornecedor e orgao publico sem misturar estado, filtros ou exportacoes.")

        st.session_state.setdefault("query_scope", "supplier")
        scope_label = st.radio(
            "Escopo",
            options=["Fornecedor", "Orgao publico"],
            index=0 if st.session_state.get("query_scope", "supplier") == "supplier" else 1,
            horizontal=True,
            key="query_scope_selector",
            label_visibility="collapsed",
        )
        query_scope = "supplier" if scope_label == "Fornecedor" else "organ"
        st.session_state["query_scope"] = query_scope

        submitted = False
        cnpj_input = ""
        start_date: date | None = None
        end_date: date | None = None
        start_year = date.today().year
        end_year = date.today().year

        if query_scope == "supplier":
            st.markdown("## Consulta do fornecedor")
            st.caption("Informe o CNPJ e, se quiser, aplique um recorte temporal para leitura operacional.")

            st.session_state.setdefault("supplier_search_cnpj", "")
            st.session_state.setdefault("supplier_search_use_period", False)
            st.session_state.setdefault("supplier_search_start_date", date(date.today().year - 1, 1, 1))
            st.session_state.setdefault("supplier_search_end_date", date.today())

            with st.form("supplier_search_form", clear_on_submit=False):
                st.markdown("**CNPJ do fornecedor**")
                cnpj_input = st.text_input(
                    "CNPJ do fornecedor",
                    placeholder="00.000.000/0000-00",
                    help="Aceita entrada com ou sem pontuacao.",
                    label_visibility="collapsed",
                    key="supplier_search_cnpj",
                )

                use_period_filter = st.toggle(
                    "Aplicar recorte por data de assinatura",
                    help="Desligado: considera todo o historico indexado na busca do portal.",
                    key="supplier_search_use_period",
                )

                if use_period_filter:
                    period_col_1, period_col_2 = st.columns(2)
                    with period_col_1:
                        st.caption("Inicial")
                        start_date = st.date_input(
                            "Inicial",
                            format="DD/MM/YYYY",
                            label_visibility="collapsed",
                            key="supplier_search_start_date",
                        )
                    with period_col_2:
                        st.caption("Final")
                        end_date = st.date_input(
                            "Final",
                            format="DD/MM/YYYY",
                            label_visibility="collapsed",
                            key="supplier_search_end_date",
                        )

                submitted = st.form_submit_button("Buscar contratos", use_container_width=True)
        else:
            st.markdown("## Consulta do orgao publico")
            st.caption("Informe o CNPJ do orgao e uma faixa obrigatoria de anos para consolidar contratos, compras e atas.")

            current_year = date.today().year
            available_years = list(range(current_year, 2015, -1))
            st.session_state.setdefault("organ_search_cnpj", "")
            st.session_state.setdefault("organ_search_start_year", current_year)
            st.session_state.setdefault("organ_search_end_year", current_year)

            with st.form("organ_search_form", clear_on_submit=False):
                st.markdown("**CNPJ do orgao**")
                cnpj_input = st.text_input(
                    "CNPJ do orgao",
                    placeholder="00.000.000/0000-00",
                    help="O v1 localiza o orgao por CNPJ exato.",
                    label_visibility="collapsed",
                    key="organ_search_cnpj",
                )

                year_col_1, year_col_2 = st.columns(2)
                with year_col_1:
                    start_year = st.selectbox(
                        "Ano inicial",
                        options=available_years,
                        key="organ_search_start_year",
                    )
                with year_col_2:
                    end_year = st.selectbox(
                        "Ano final",
                        options=available_years,
                        key="organ_search_end_year",
                    )

                submitted = st.form_submit_button("Buscar orgao", use_container_width=True)

        st.markdown("---")
        st.markdown("### Fonte")
        if query_scope == "supplier":
            st.caption("Busca publica do portal PNCP com enriquecimento no endpoint oficial de detalhe.")
            st.markdown(
                """
                - Portal: `pncp.gov.br`
                - Atualizacao: tempo real
                - Janela robusta: ate 20 mil contratos
                - Exportacao: Excel e CSV
                """
            )
        else:
            st.caption("Panorama por orgao com indice publico do PNCP e apoio do endpoint oficial de contratos.")
            st.markdown(
                f"""
                - Portal: `pncp.gov.br`
                - Atualizacao: tempo real
                - Faixa anual obrigatoria
                - Limite inicial: ate {YEAR_RANGE_LIMIT} anos por consulta
                """
            )

        st.markdown("### Notas operacionais")
        if query_scope == "supplier":
            st.caption(
                "Consultas volumosas podem levar alguns segundos. Acima de 20 mil itens no indice, aplique um recorte temporal para auditoria completa."
            )
        else:
            st.caption(
                "O modulo por orgao exige faixa de anos e valida o CNPJ exato do orgao na base. Se o indice ultrapassar a janela robusta, reduza o intervalo anual."
            )

    return {
        "query_scope": query_scope,
        "submitted": submitted,
        "cnpj_input": cnpj_input,
        "start_date": start_date,
        "end_date": end_date,
        "start_year": start_year,
        "end_year": end_year,
    }


def initialize_state() -> None:
    st.session_state.setdefault("query_scope", "supplier")
    st.session_state.setdefault("supplier_contracts_df", None)
    st.session_state.setdefault("supplier_query_meta", {})
    st.session_state.setdefault("organ_documents_df", None)
    st.session_state.setdefault("organ_query_meta", {})


def run_supplier_search(cnpj_input: str, start_date: date | None, end_date: date | None) -> None:
    cnpj = format_cnpj(cnpj_input)
    if not cnpj:
        ui_alert("error", "Informe um CNPJ para iniciar a consulta.")
        st.stop()

    if not validate_cnpj(cnpj):
        ui_alert("error", "O CNPJ informado e invalido. Revise os digitos e tente novamente.")
        st.stop()

    if start_date and end_date and start_date > end_date:
        ui_alert("error", "A data inicial nao pode ser posterior a data final.")
        st.stop()

    with st.spinner(f"Consultando contratos do fornecedor {format_cnpj_display(cnpj)}..."):
        payload = fetch_contract_search(cnpj)
        contracts_df = normalize_contracts(payload, cnpj)

    st.session_state["supplier_contracts_df"] = contracts_df
    st.session_state["supplier_query_meta"] = {
        "query_scope": "supplier",
        "cnpj": cnpj,
        "supplier_name": payload.get("supplier_name") or "Fornecedor consultado",
        "total_records": payload.get("total_records", len(contracts_df)),
        "total_pages": payload.get("total_pages", 1),
        "retrieved_records": payload.get("retrieved_records", len(contracts_df)),
        "search_strategy": payload.get("search_strategy", "janela_unica"),
        "retrieved_windows": payload.get("retrieved_windows", 1),
        "is_partial": payload.get("is_partial", False),
        "sample_checked": payload.get("sample_checked", 0),
        "sample_exact_match": payload.get("sample_exact_match", True),
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "fetched_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    st.session_state["prepared_export_supplier"] = None


def run_organ_search(cnpj_input: str, start_year: int, end_year: int) -> None:
    cnpj = format_cnpj(cnpj_input)
    if not cnpj:
        ui_alert("error", "Informe o CNPJ do orgao para iniciar a consulta.")
        st.stop()

    if not validate_cnpj(cnpj):
        ui_alert("error", "O CNPJ do orgao informado e invalido. Revise os digitos e tente novamente.")
        st.stop()

    if start_year > end_year:
        ui_alert("error", "O ano inicial nao pode ser maior que o ano final.")
        st.stop()

    if (end_year - start_year + 1) > YEAR_RANGE_LIMIT:
        ui_alert(
            "error",
            f"A faixa inicial esta limitada a ate {YEAR_RANGE_LIMIT} anos por consulta. Reduza o intervalo e tente novamente.",
        )
        st.stop()

    with st.spinner(f"Consultando panorama do orgao {format_cnpj_display(cnpj)}..."):
        search_payload = fetch_search_index(cnpj, document_types="edital|ata|contrato")
        enrichment_status = "Contratos enriquecidos pela API oficial"
        try:
            contract_enrichment = fetch_organ_contract_enrichment(cnpj, start_year, end_year)
        except PncpApiError:
            contract_enrichment = pd.DataFrame()
            enrichment_status = "Enriquecimento de fornecedor indisponivel"

        organ_df = normalize_organ_documents(
            search_payload,
            cnpj,
            start_year=start_year,
            end_year=end_year,
            contract_enrichment=contract_enrichment,
        )

    organ_name = organ_df["orgao_nome"].dropna().iloc[0] if not organ_df.empty else "Orgao publico consultado"
    st.session_state["organ_documents_df"] = organ_df
    st.session_state["organ_query_meta"] = {
        "query_scope": "organ",
        "cnpj": cnpj,
        "organ_name": organ_name,
        "total_records": search_payload.get("total_records", len(organ_df)),
        "total_pages": search_payload.get("total_pages", 1),
        "retrieved_records": search_payload.get("retrieved_records", len(organ_df)),
        "search_strategy": search_payload.get("search_strategy", "janela_unica"),
        "retrieved_windows": search_payload.get("retrieved_windows", 1),
        "is_partial": search_payload.get("is_partial", False),
        "exact_records": len(organ_df),
        "start_year": start_year,
        "end_year": end_year,
        "enrichment_status": enrichment_status,
        "fetched_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    st.session_state["prepared_export_organ"] = None


def render_dashboard(df: pd.DataFrame, meta: dict[str, Any]) -> None:
    requested_start = meta.get("requested_start_date")
    requested_end = meta.get("requested_end_date")

    render_filter_summary(
        cnpj=meta.get("cnpj", ""),
        supplier_name=meta.get("supplier_name", "Fornecedor consultado"),
        total_records=meta.get("total_records", len(df)),
        retrieved_records=meta.get("retrieved_records", len(df)),
        start_date=requested_start,
        end_date=requested_end,
        sample_checked=meta.get("sample_checked", 0),
        sample_exact_match=meta.get("sample_exact_match", True),
        search_strategy=meta.get("search_strategy", "janela_unica"),
        is_partial=meta.get("is_partial", False),
    )

    if meta.get("sample_checked", 0) > 0 and not meta.get("sample_exact_match", True):
        ui_alert(
            "warning",
            "A amostra verificada nao confirmou todos os contratos no CNPJ informado. Revise manualmente antes de usar a base para decisao.",
        )

    if meta.get("is_partial", False):
        ui_alert(
            "warning",
            (
                f"O PNCP indexa {format_integer(meta.get('total_records', len(df)))} contratos para este CNPJ, "
                f"mas o endpoint publico limita a recuperacao a {format_integer(meta.get('retrieved_records', len(df)))} "
                "itens nesta estrategia. Para auditoria completa, aplique um recorte temporal menor."
            ),
        )

    if df.empty:
        ui_empty_state(
            icon="📭",
            title="Nenhum contrato encontrado",
            message="Nao localizamos contratos para este CNPJ no indice publico do PNCP.",
            badges=["Revise o CNPJ", "Tente novamente mais tarde", "Verifique a indexacao no portal"],
        )
        return

    advanced_filter_state = apply_advanced_filters(df)
    analysis_df = advanced_filter_state.filtered_df
    advanced_summary = advanced_filter_state.summary_text()

    if advanced_filter_state.active_filters:
        ui_alert("info", f"Filtros avancados ativos: {advanced_summary}")

    if analysis_df.empty:
        ui_empty_state(
            icon="🧭",
            title="Sem resultados apos os filtros avancados",
            message="Os filtros laterais removeram todos os contratos da analise. Ajuste texto, faixa de valor ou presets para continuar.",
            badges=["Limpe filtros", "Amplie a faixa de valor", "Revise UFs e modalidades"],
        )
        return

    orgao_options = sorted(analysis_df["orgao_nome"].dropna().unique().tolist())
    year_options = sorted([int(year) for year in analysis_df["ano"].dropna().unique().tolist()], reverse=True)
    situation_options = sorted(analysis_df["situacao_nome"].dropna().unique().tolist())

    section_header(
        "Filtros dinamicos da analise",
        "Todos os graficos, metricas, exportacoes e a tabela respondem aos recortes abaixo.",
        icon="🎛️",
    )
    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    with filter_col_1:
        selected_orgaos = st.multiselect("Orgao", options=orgao_options, default=[], key="main_filter_orgaos")
    with filter_col_2:
        selected_years = st.multiselect("Ano", options=year_options, default=[], key="main_filter_anos")
    with filter_col_3:
        selected_situations = st.multiselect(
            "Situacao",
            options=situation_options,
            default=[],
            key="main_filter_situacoes",
        )

    filtered_df = apply_dashboard_filters(
        analysis_df,
        start_date=requested_start,
        end_date=requested_end,
        orgaos=selected_orgaos,
        anos=selected_years,
        situacoes=selected_situations,
    )

    if filtered_df.empty:
        ui_empty_state(
            icon="🧭",
            title="Sem resultados neste recorte",
            message="Os filtros atuais removeram todos os contratos da visualizacao. Ajuste os recortes para continuar.",
            badges=["Amplie o periodo", "Remova um filtro", "Troque o orgao"],
        )
        return

    total_contracts = len(filtered_df)
    total_value = filtered_df["valor_global"].sum()
    average_value = filtered_df["valor_global"].mean()
    unique_organs = filtered_df["orgao_nome"].nunique()
    years_covered = filtered_df["ano"].dropna().nunique()

    metric_col_1, metric_col_2, metric_col_3, metric_col_4, metric_col_5 = st.columns(5)
    with metric_col_1:
        ui_metric_card("Contratos", format_integer(total_contracts), icon="📄", delta="Base filtrada")
    with metric_col_2:
        ui_metric_card("Valor total", format_currency(total_value), icon="💰", delta="Soma da carteira")
    with metric_col_3:
        ui_metric_card("Valor medio", format_currency(average_value), icon="📈", delta="Ticket medio")
    with metric_col_4:
        ui_metric_card("Orgaos", format_integer(unique_organs), icon="🏛️", delta="Relacionamentos distintos")
    with metric_col_5:
        ui_metric_card("Anos cobertos", format_integer(years_covered), icon="🗓️", delta="Historico visivel")

    tab_1, tab_2, tab_3, tab_4, tab_5, tab_6 = st.tabs(
        [
            "Visao executiva",
            "Orgaos e temporalidade",
            "Base completa",
            "Distribuicao de valor",
            "Graficos avancados",
            "Exportacao",
        ]
    )

    with tab_1:
        exec_col_1, exec_col_2 = st.columns([1.5, 1])
        with exec_col_1:
            chart_wrapper(
                build_top_orgs_chart(filtered_df),
                "Top orgaos por valor contratado",
                "Mapa de concentracao financeira por contratante.",
                icon="🏛️",
            )
        with exec_col_2:
            chart_wrapper(
                build_status_chart(filtered_df),
                "Situacao das contratacoes",
                "Leitura objetiva do volume publicado por status no portal.",
                icon="📌",
            )

        summary = (
            filtered_df.groupby("tipo_contrato_nome", dropna=False)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
            .sort_values(["quantidade", "valor_total"], ascending=[False, False])
        )
        summary["valor_total"] = summary["valor_total"].apply(format_currency)
        section_header(
            "Resumo por tipo contratual",
            "Visao consolidada do mix entre contratos, cartas e empenhos.",
            icon="📦",
        )
        st.dataframe(
            summary.rename(
                columns={
                    "tipo_contrato_nome": "Tipo contratual",
                    "quantidade": "Qtd. contratos",
                    "valor_total": "Valor total",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tab_2:
        timeline_col_1, timeline_col_2 = st.columns([1.5, 1])
        with timeline_col_1:
            chart_wrapper(
                build_timeline_chart(filtered_df),
                "Evolucao mensal",
                "Valor total e volume contratual por mes de referencia.",
                icon="📆",
            )
        with timeline_col_2:
            chart_wrapper(
                build_yearly_chart(filtered_df),
                "Volume anual",
                "Leitura compacta da intensidade de contratacao por ano.",
                icon="📊",
            )

        organ_summary = (
            filtered_df.groupby(["orgao_nome", "uf"], dropna=False)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
            .sort_values("valor_total", ascending=False)
            .head(15)
        )
        organ_summary["valor_total"] = organ_summary["valor_total"].apply(format_currency)
        section_header(
            "Ranking consolidado de orgaos",
            "Tabela operacional para identificar os principais compradores.",
            icon="📋",
        )
        st.dataframe(
            organ_summary.rename(
                columns={
                    "orgao_nome": "Orgao",
                    "uf": "UF",
                    "quantidade": "Qtd. contratos",
                    "valor_total": "Valor total",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tab_3:
        section_header(
            "Relacao completa de contratos filtrados",
            "Tabela paginada para revisao detalhada e abertura direta no portal.",
            icon="🔎",
        )

        table_df = filtered_df[
            [
                "numero_controle_pncp",
                "titulo",
                "objeto",
                "orgao_nome",
                "unidade_nome",
                "situacao_nome",
                "modalidade_licitacao_nome",
                "tipo_contrato_nome",
                "valor_global",
                "data_assinatura",
                "link_pncp",
            ]
        ].copy()

        table_df["valor_global"] = table_df["valor_global"].apply(format_currency)
        table_df["data_assinatura"] = table_df["data_assinatura"].dt.strftime("%d/%m/%Y").fillna("N/A")

        paged_table_df = paginated_table(table_df, key="contracts_table", rows_per_page=25)

        st.dataframe(
            paged_table_df.rename(
                columns={
                    "numero_controle_pncp": "Numero PNCP",
                    "titulo": "Titulo",
                    "objeto": "Objeto",
                    "orgao_nome": "Orgao",
                    "unidade_nome": "Unidade",
                    "situacao_nome": "Situacao",
                    "modalidade_licitacao_nome": "Modalidade",
                    "tipo_contrato_nome": "Tipo contratual",
                    "valor_global": "Valor global",
                    "data_assinatura": "Data de assinatura",
                    "link_pncp": "Link PNCP",
                }
            ),
            column_config={
                "Link PNCP": st.column_config.LinkColumn(
                    "Link PNCP",
                    help="Abre o detalhe do contrato no portal",
                    display_text="abrir no portal",
                )
            },
            use_container_width=True,
            hide_index=True,
            height=620,
        )

    with tab_4:
        dist_col_1, dist_col_2 = st.columns(2)
        with dist_col_1:
            chart_wrapper(
                build_value_histogram(filtered_df),
                "Histograma de valores",
                "Distribuicao dos tickets em escala logaritmica para evitar distorcao por outliers.",
                icon="📶",
            )
        with dist_col_2:
            chart_wrapper(
                build_value_band_chart(filtered_df),
                "Valor por faixa",
                "Concentracao financeira por bandas de ticket contratual.",
                icon="📉",
            )

        bands_df = build_value_bands(filtered_df)
        bands_df["valor_total"] = bands_df["valor_total"].apply(format_currency)
        bands_df["valor_medio"] = bands_df["valor_medio"].apply(format_currency)
        bands_df["participacao"] = bands_df["participacao"].map(lambda value: f"{value:.1f}%")
        section_header(
            "Faixas de valor",
            "Leitura direta da composicao da carteira por bandas financeiras.",
            icon="💹",
        )
        st.dataframe(
            bands_df.rename(
                columns={
                    "faixa_valor": "Faixa",
                    "quantidade": "Qtd. contratos",
                    "valor_total": "Valor total",
                    "valor_medio": "Valor medio",
                    "participacao": "Participacao",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tab_5:
        advanced_col_1, advanced_col_2 = st.columns(2)
        with advanced_col_1:
            chart_wrapper(
                build_heatmap_uf_year(filtered_df),
                "Heatmap de UF por ano",
                "Mapa de calor do valor contratado por unidade federativa e ano de referencia.",
                icon="🗺️",
            )
        with advanced_col_2:
            chart_wrapper(
                build_funnel_status(filtered_df),
                "Funil de situacoes",
                "Leitura de afunilamento por status publicado no portal.",
                icon="🎯",
            )

        chart_wrapper(
            build_treemap_hierarchy(filtered_df),
            "Treemap hierarquico",
            "Distribuicao da carteira por esfera, UF e orgao contratante.",
            icon="📦",
        )

        advanced_col_3, advanced_col_4 = st.columns(2)
        with advanced_col_3:
            chart_wrapper(
                build_scatter_value_over_time(filtered_df),
                "Dispersao temporal de valores",
                "Amostra visual da carteira ao longo do tempo com escala logaritmica.",
                icon="✨",
            )
        with advanced_col_4:
            chart_wrapper(
                build_boxplot_top_orgaos(filtered_df),
                "Boxplot dos principais orgaos",
                "Amplitude dos tickets por orgao entre os maiores compradores.",
                icon="📈",
            )

        advanced_col_5, advanced_col_6 = st.columns(2)
        with advanced_col_5:
            chart_wrapper(
                build_bubble_organs(filtered_df),
                "Bolhas de densidade por orgao",
                "Cruza quantidade de contratos, valor total e ticket medio.",
                icon="🔵",
            )
        with advanced_col_6:
            chart_wrapper(
                build_sunburst_hierarchy(filtered_df),
                "Sunburst da carteira",
                "Hierarquia da base por esfera, UF e tipo contratual.",
                icon="☀️",
            )

    with tab_6:
        section_header(
            "Exportar base filtrada",
            "Gere PDF executivo ou completo, alem dos pacotes Excel e CSV da base filtrada.",
            icon="⬇️",
        )
        export_summary = advanced_summary if advanced_filter_state.active_filters else "Sem filtros avancados ativos."
        export_meta = {
            **meta,
            "fetched_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

        export_col_1, export_col_2 = st.columns([1.2, 1])
        with export_col_1:
            export_format = st.selectbox(
                "Formato do relatorio",
                ["PDF Executivo", "PDF Completo", "Excel", "CSV"],
                key="supplier_export_format",
            )
        with export_col_2:
            include_charts = st.checkbox(
                "Incluir graficos no PDF",
                value=True,
                key="supplier_export_include_charts",
                help="Quando desmarcado, o PDF fica mais leve e rapido para gerar.",
            )

        if st.button("Preparar pacote de exportacao", use_container_width=True, key="supplier_prepare_export_button"):
            with st.spinner("Gerando arquivo..."):
                try:
                    payload, filename, mime_type, label = prepare_export_payload(
                        filtered_df,
                        export_meta,
                        export_format=export_format,
                        include_charts=include_charts,
                        filter_summary=export_summary,
                    )
                except Exception as exc:
                    ui_alert("error", f"Nao foi possivel gerar o arquivo agora: {exc}")
                else:
                    st.session_state["prepared_export_supplier"] = {
                        "payload": payload,
                        "filename": filename,
                        "mime_type": mime_type,
                        "label": label,
                    }
                    ui_alert("success", f"Arquivo preparado com sucesso: {filename}")

        prepared_export = st.session_state.get("prepared_export_supplier")
        if prepared_export:
            st.download_button(
                prepared_export["label"],
                data=prepared_export["payload"],
                file_name=prepared_export["filename"],
                mime=prepared_export["mime_type"],
                use_container_width=True,
            )

        quick_export_col_1, quick_export_col_2 = st.columns(2)
        with quick_export_col_1:
            st.download_button(
                "Baixar CSV rapido",
                data=dataframe_to_csv_bytes(filtered_df),
                file_name=f"pncp_contratos_{meta.get('cnpj', '')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with quick_export_col_2:
            st.download_button(
                "Baixar Excel rapido",
                data=build_excel_report_bytes(filtered_df, export_meta, export_summary),
                file_name=f"pncp_contratos_{meta.get('cnpj', '')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        section_header("Links uteis", "Atalhos para conferencia no portal e documentacao publica.", icon="🔗")
        st.markdown(
            f"""
            - [Abrir consulta do fornecedor no portal]({APP_BASE_URL}/buscar/todos?q={meta.get('cnpj', '')}&pagina=1)
            - [Listagem publica de contratos]({APP_BASE_URL}/contratos?pagina=1)
            - [Swagger da API de consulta do PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
            """
        )

    footer_block(
        repo_url=REPO_URL,
        timestamp=meta.get("fetched_at", "-"),
    )


def render_organ_dashboard(df: pd.DataFrame, meta: dict[str, Any]) -> None:
    render_organ_filter_summary(
        cnpj=meta.get("cnpj", ""),
        organ_name=meta.get("organ_name", "Orgao publico consultado"),
        total_records=meta.get("total_records", len(df)),
        retrieved_records=meta.get("retrieved_records", len(df)),
        exact_records=meta.get("exact_records", len(df)),
        start_year=meta.get("start_year", date.today().year),
        end_year=meta.get("end_year", date.today().year),
        search_strategy=meta.get("search_strategy", "janela_unica"),
        is_partial=meta.get("is_partial", False),
        enrichment_status=meta.get("enrichment_status", "Consulta consolidada"),
    )

    if meta.get("is_partial", False):
        ui_alert(
            "warning",
            (
                f"A busca por este orgao extrapolou a janela robusta do indice publico. "
                f"A base exata no recorte anual mostra {format_integer(meta.get('exact_records', len(df)))} registros, "
                "mas para auditoria total vale reduzir ainda mais a faixa de anos."
            ),
        )

    if meta.get("enrichment_status") != "Contratos enriquecidos pela API oficial":
        ui_alert(
            "warning",
            "O enriquecimento oficial de fornecedores ficou indisponivel nesta execucao. O panorama segue valido, mas alguns contratos podem aparecer sem fornecedor preenchido.",
        )

    if df.empty:
        ui_empty_state(
            icon="🏛️",
            title="Nenhum registro encontrado para o orgao",
            message="Nao localizamos contratos, compras/licitações ou atas para o CNPJ e a faixa anual informados.",
            badges=["Revise o CNPJ", "Ajuste a faixa de anos", "Confira a indexacao no portal"],
        )
        return

    section_header(
        "Filtros dinamicos da analise",
        "O panorama completo do orgao responde aos recortes por objeto, documento, unidade, fornecedor, modalidade e situacao.",
        icon="🎛️",
    )

    search_text = st.text_input(
        "Busca textual por objeto, titulo ou numero PNCP",
        placeholder="Ex.: medicamento, limpeza, 0039446...",
        key="organ_filter_text",
    )

    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    with filter_col_1:
        selected_document_types = st.multiselect(
            "Tipo de documento",
            options=["contrato", "edital", "ata"],
            default=[],
            format_func=lambda value: {
                "contrato": "Contratos e empenhos",
                "edital": "Compras/Licitacoes",
                "ata": "Atas",
            }.get(value, value),
            key="organ_filter_document_types",
        )
    with filter_col_2:
        selected_years = st.multiselect(
            "Ano",
            options=sorted([int(year) for year in df["ano"].dropna().unique().tolist()], reverse=True),
            default=[],
            key="organ_filter_years",
        )
    with filter_col_3:
        selected_units = st.multiselect(
            "Unidade administrativa",
            options=sorted(df["unidade_nome"].dropna().unique().tolist()),
            default=[],
            key="organ_filter_units",
        )

    filter_col_4, filter_col_5, filter_col_6 = st.columns(3)
    with filter_col_4:
        supplier_options = sorted(
            [
                value
                for value in df["fornecedor_nome"].dropna().unique().tolist()
                if value and value not in {"Nao informado", "Nao se aplica"}
            ]
        )
        selected_suppliers = st.multiselect(
            "Fornecedor",
            options=supplier_options,
            default=[],
            key="organ_filter_suppliers",
        )
    with filter_col_5:
        selected_modalities = st.multiselect(
            "Modalidade",
            options=sorted(df["modalidade_licitacao_nome"].dropna().unique().tolist()),
            default=[],
            key="organ_filter_modalities",
        )
    with filter_col_6:
        selected_situations = st.multiselect(
            "Situacao",
            options=sorted(df["situacao_nome"].dropna().unique().tolist()),
            default=[],
            key="organ_filter_situations",
        )

    filtered_df = apply_organ_dashboard_filters(
        df,
        search_text=search_text,
        document_types=selected_document_types,
        years=selected_years,
        units=selected_units,
        suppliers=selected_suppliers,
        modalities=selected_modalities,
        situations=selected_situations,
    )

    if filtered_df.empty:
        ui_empty_state(
            icon="🧭",
            title="Sem resultados neste recorte",
            message="Os filtros atuais removeram todos os registros do orgao. Ajuste os recortes para continuar.",
            badges=["Limpe os filtros", "Revise a busca textual", "Amplie o conjunto de documentos"],
        )
        return

    filter_summary_parts: list[str] = []
    if search_text.strip():
        filter_summary_parts.append(f"Texto: {search_text.strip()}")
    if selected_document_types:
        filter_summary_parts.append(f"Tipos: {len(selected_document_types)}")
    if selected_years:
        filter_summary_parts.append(f"Anos: {len(selected_years)}")
    if selected_units:
        filter_summary_parts.append(f"Unidades: {len(selected_units)}")
    if selected_suppliers:
        filter_summary_parts.append(f"Fornecedores: {len(selected_suppliers)}")
    if selected_modalities:
        filter_summary_parts.append(f"Modalidades: {len(selected_modalities)}")
    if selected_situations:
        filter_summary_parts.append(f"Situacoes: {len(selected_situations)}")
    filter_summary = " | ".join(filter_summary_parts) if filter_summary_parts else "Sem filtros ativos no modulo de orgao."

    total_records = len(filtered_df)
    total_value = filtered_df["valor_global"].sum()
    supplier_count = (
        filtered_df["fornecedor_nome"]
        .replace(["Nao informado", "Nao se aplica"], pd.NA)
        .dropna()
        .nunique()
    )
    unit_count = filtered_df["unidade_nome"].nunique()
    years_covered = filtered_df["ano"].dropna().nunique()

    metric_col_1, metric_col_2, metric_col_3, metric_col_4, metric_col_5 = st.columns(5)
    with metric_col_1:
        ui_metric_card("Registros", format_integer(total_records), icon="📄", delta="Base consolidada")
    with metric_col_2:
        ui_metric_card("Valor total", format_currency(total_value), icon="💰", delta="Soma do recorte")
    with metric_col_3:
        ui_metric_card("Fornecedores", format_integer(supplier_count), icon="🏢", delta="Contratos com fornecedor")
    with metric_col_4:
        ui_metric_card("Unidades", format_integer(unit_count), icon="🏛️", delta="Estrutura ativa")
    with metric_col_5:
        ui_metric_card("Anos cobertos", format_integer(years_covered), icon="🗓️", delta="Faixa visivel")

    contracts_df = filtered_df[filtered_df["document_type"].eq("contrato")].copy()
    edital_df = filtered_df[filtered_df["document_type"].eq("edital")].copy()
    ata_df = filtered_df[filtered_df["document_type"].eq("ata")].copy()

    tab_1, tab_2, tab_3, tab_4, tab_5, tab_6 = st.tabs(
        [
            "Visao geral",
            "Contratos anuais",
            "Compras/Licitacoes",
            "Atas",
            "Base consolidada",
            "Exportacao",
        ]
    )

    with tab_1:
        overview_col_1, overview_col_2 = st.columns([1, 1.2])
        with overview_col_1:
            chart_wrapper(
                build_document_mix_chart(filtered_df),
                "Composicao por tipo de documento",
                "Leitura imediata do mix entre contratos/empenhos, compras/licitações e atas.",
                icon="🧩",
            )
        with overview_col_2:
            chart_wrapper(
                build_yearly_chart(filtered_df),
                "Leitura anual consolidada",
                "Volume e valor total do panorama do orgao ao longo da faixa anual consultada.",
                icon="📆",
            )

        overview_col_3, overview_col_4 = st.columns(2)
        with overview_col_3:
            chart_wrapper(
                build_top_suppliers_chart(filtered_df),
                "Top fornecedores contratados",
                "Ranking financeiro dos fornecedores com contratos vinculados ao orgao.",
                icon="🏢",
            )
        with overview_col_4:
            chart_wrapper(
                build_top_units_chart(filtered_df),
                "Top unidades e UFs",
                "Leitura operacional das unidades administrativas mais ativas no recorte.",
                icon="📍",
            )

    with tab_2:
        if contracts_df.empty:
            ui_empty_state(
                icon="📑",
                title="Sem contratos ou empenhos neste recorte",
                message="A faixa anual e os filtros atuais nao retornaram contratos/empenhos do orgao.",
                badges=["Ajuste os anos", "Limpe filtros", "Revise o CNPJ do orgao"],
            )
        else:
            contracts_col_1, contracts_col_2 = st.columns([1.2, 1])
            with contracts_col_1:
                chart_wrapper(
                    build_yearly_chart(contracts_df),
                    "Contratos por ano",
                    "Quantidade e valor anual de contratos/empenhos associados ao orgao.",
                    icon="📈",
                )
            with contracts_col_2:
                chart_wrapper(
                    build_top_suppliers_chart(contracts_df),
                    "Fornecedores mais relevantes",
                    "Leitura concentrada dos maiores fornecedores do orgao no recorte.",
                    icon="🤝",
                )

            top_objects_df = build_top_objects_summary(contracts_df, limit=20)
            if not top_objects_df.empty:
                top_objects_df["valor_total"] = top_objects_df["valor_total"].apply(format_currency)
                section_header(
                    "Objetos mais recorrentes",
                    "Agrupamento operacional dos principais objetos publicados pelo orgao nos contratos/empenhos.",
                    icon="🧾",
                )
                st.dataframe(
                    top_objects_df.rename(
                        columns={
                            "objeto_grupo": "Objeto",
                            "quantidade": "Qtd. registros",
                            "valor_total": "Valor total",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab_3:
        if edital_df.empty:
            ui_empty_state(
                icon="🛒",
                title="Sem compras/licitações neste recorte",
                message="Nao ha registros de edital para a faixa anual e filtros selecionados.",
                badges=["Revise os anos", "Troque a modalidade", "Amplie a busca textual"],
            )
        else:
            procurement_col_1, procurement_col_2 = st.columns(2)
            with procurement_col_1:
                chart_wrapper(
                    build_modality_chart(edital_df),
                    "Distribuicao por modalidade",
                    "Como as compras/licitações do orgao se distribuem por modalidade publicada.",
                    icon="📦",
                )
            with procurement_col_2:
                chart_wrapper(
                    build_status_chart(edital_df),
                    "Situacoes das compras/licitações",
                    "Status publicados no portal para editais e compras do recorte.",
                    icon="📌",
                )

            procurement_table = edital_df[
                [
                    "numero_controle_pncp",
                    "titulo",
                    "objeto",
                    "unidade_nome",
                    "modalidade_licitacao_nome",
                    "situacao_nome",
                    "valor_global",
                    "link_pncp",
                ]
            ].copy()
            procurement_table["valor_global"] = procurement_table["valor_global"].apply(format_currency)

            section_header(
                "Base de compras/licitações",
                "Tabela detalhada para leitura do objeto, unidade administrativa e modalidade.",
                icon="🔎",
            )
            st.dataframe(
                procurement_table.rename(
                    columns={
                        "numero_controle_pncp": "Numero PNCP",
                        "titulo": "Titulo",
                        "objeto": "Objeto",
                        "unidade_nome": "Unidade",
                        "modalidade_licitacao_nome": "Modalidade",
                        "situacao_nome": "Situacao",
                        "valor_global": "Valor global",
                        "link_pncp": "Link PNCP",
                    }
                ),
                column_config={
                    "Link PNCP": st.column_config.LinkColumn(
                        "Link PNCP",
                        help="Abre o detalhe da compra/licitação no portal",
                        display_text="abrir no portal",
                    )
                },
                use_container_width=True,
                hide_index=True,
                height=560,
            )

    with tab_4:
        if ata_df.empty:
            ui_empty_state(
                icon="🗂️",
                title="Sem atas neste recorte",
                message="Nao ha atas publicadas para o orgao dentro da faixa anual informada.",
                badges=["Revise o intervalo", "Verifique o portal", "Mantenha o recorte"],
            )
        else:
            ata_col_1, ata_col_2 = st.columns([1.2, 1])
            with ata_col_1:
                chart_wrapper(
                    build_yearly_chart(ata_df),
                    "Atas por ano",
                    "Leitura anual das atas vinculadas ao orgao no recorte consultado.",
                    icon="📅",
                )
            with ata_col_2:
                chart_wrapper(
                    build_top_units_chart(ata_df),
                    "Unidades com atas",
                    "Unidades administrativas e UFs com maior concentracao de atas.",
                    icon="📍",
                )

            ata_table = ata_df[
                [
                    "numero_controle_pncp",
                    "titulo",
                    "objeto",
                    "unidade_nome",
                    "situacao_nome",
                    "valor_global",
                    "link_pncp",
                ]
            ].copy()
            ata_table["valor_global"] = ata_table["valor_global"].apply(format_currency)
            section_header(
                "Tabela de atas",
                "Leitura operacional das atas para conferencia rapida no portal.",
                icon="📋",
            )
            st.dataframe(
                ata_table.rename(
                    columns={
                        "numero_controle_pncp": "Numero PNCP",
                        "titulo": "Titulo",
                        "objeto": "Objeto",
                        "unidade_nome": "Unidade",
                        "situacao_nome": "Situacao",
                        "valor_global": "Valor global",
                        "link_pncp": "Link PNCP",
                    }
                ),
                column_config={
                    "Link PNCP": st.column_config.LinkColumn(
                        "Link PNCP",
                        help="Abre o detalhe da ata no portal",
                        display_text="abrir no portal",
                    )
                },
                use_container_width=True,
                hide_index=True,
                height=560,
            )

    with tab_5:
        section_header(
            "Base consolidada do orgao",
            "Tabela paginada com tipo de documento, fornecedor, unidade, ano e abertura direta no portal.",
            icon="🗃️",
        )

        consolidated_df = filtered_df[
            [
                "document_type_label",
                "numero_controle_pncp",
                "titulo",
                "objeto",
                "fornecedor_nome",
                "orgao_nome",
                "unidade_nome",
                "modalidade_licitacao_nome",
                "situacao_nome",
                "ano",
                "valor_global",
                "link_pncp",
            ]
        ].copy()
        consolidated_df["ano"] = consolidated_df["ano"].astype("Int64").astype(str)
        consolidated_df["valor_global"] = consolidated_df["valor_global"].apply(format_currency)
        paged_consolidated_df = paginated_table(consolidated_df, key="organ_documents_table", rows_per_page=25)
        st.dataframe(
            paged_consolidated_df.rename(
                columns={
                    "document_type_label": "Tipo de documento",
                    "numero_controle_pncp": "Numero PNCP",
                    "titulo": "Titulo",
                    "objeto": "Objeto",
                    "fornecedor_nome": "Fornecedor",
                    "orgao_nome": "Orgao",
                    "unidade_nome": "Unidade",
                    "modalidade_licitacao_nome": "Modalidade",
                    "situacao_nome": "Situacao",
                    "ano": "Ano",
                    "valor_global": "Valor global",
                    "link_pncp": "Link PNCP",
                }
            ),
            column_config={
                "Link PNCP": st.column_config.LinkColumn(
                    "Link PNCP",
                    help="Abre o detalhe do documento no portal",
                    display_text="abrir no portal",
                )
            },
            use_container_width=True,
            hide_index=True,
            height=620,
        )

    with tab_6:
        section_header(
            "Exportar base consolidada",
            "Baixe CSV, Excel e PDF do panorama do orgao com faixa anual, tipo de documento, unidade e fornecedor.",
            icon="⬇️",
        )

        export_meta = {
            **meta,
            "fetched_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        export_col_1, export_col_2 = st.columns([1.2, 1])
        with export_col_1:
            export_format = st.selectbox(
                "Formato do relatorio",
                ["PDF Executivo", "PDF Completo", "Excel", "CSV"],
                key="organ_export_format",
            )
        with export_col_2:
            include_charts = st.checkbox(
                "Incluir graficos no PDF",
                value=True,
                key="organ_export_include_charts",
                help="Quando desmarcado, o PDF fica mais leve e rapido para gerar.",
            )

        if st.button("Preparar pacote de exportacao", use_container_width=True, key="organ_prepare_export_button"):
            with st.spinner("Gerando arquivo..."):
                try:
                    payload, filename, mime_type, label = prepare_export_payload(
                        filtered_df,
                        export_meta,
                        export_format=export_format,
                        include_charts=include_charts,
                        filter_summary=filter_summary,
                    )
                except Exception as exc:
                    ui_alert("error", f"Nao foi possivel gerar o arquivo agora: {exc}")
                else:
                    st.session_state["prepared_export_organ"] = {
                        "payload": payload,
                        "filename": filename,
                        "mime_type": mime_type,
                        "label": label,
                    }
                    ui_alert("success", f"Arquivo preparado com sucesso: {filename}")

        prepared_export = st.session_state.get("prepared_export_organ")
        if prepared_export:
            st.download_button(
                prepared_export["label"],
                data=prepared_export["payload"],
                file_name=prepared_export["filename"],
                mime=prepared_export["mime_type"],
                use_container_width=True,
            )

        quick_export_col_1, quick_export_col_2 = st.columns(2)
        with quick_export_col_1:
            st.download_button(
                "Baixar CSV rapido",
                data=dataframe_to_csv_bytes(filtered_df),
                file_name=f"pncp_orgao_{meta.get('cnpj', '')}_{meta.get('start_year', '-')}_{meta.get('end_year', '-')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with quick_export_col_2:
            st.download_button(
                "Baixar Excel rapido",
                data=build_excel_report_bytes(filtered_df, export_meta, filter_summary),
                file_name=f"pncp_orgao_{meta.get('cnpj', '')}_{meta.get('start_year', '-')}_{meta.get('end_year', '-')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        section_header("Links uteis", "Atalhos para conferencia direta do orgao no portal e documentacao publica.", icon="🔗")
        st.markdown(
            f"""
            - [Abrir busca publica do orgao no portal]({APP_BASE_URL}/buscar/todos?q={meta.get('cnpj', '')}&pagina=1)
            - [Listagem publica do orgao no indice]({APP_BASE_URL}/buscar/todos?q={meta.get('cnpj', '')}&pagina=1)
            - [Swagger da API de consulta do PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
            """
        )

    footer_block(
        repo_url=REPO_URL,
        timestamp=meta.get("fetched_at", "-"),
    )


def render_initial_screen(query_scope: str) -> None:
    if query_scope == "organ":
        ui_empty_state(
            icon="🏛️",
            title="Pronto para consultar o orgao publico",
            message="Informe o CNPJ do orgao, escolha a faixa de anos e navegue pelo panorama de contratos, compras/licitações e atas.",
            badges=["CNPJ do orgao", "Faixa anual obrigatoria", "Panorama consolidado"],
        )
    else:
        ui_empty_state(
            icon="🔎",
            title="Pronto para consultar o fornecedor",
            message="Informe o CNPJ no menu lateral, execute a busca e navegue por metricas, series temporais, base completa e exportacoes.",
            badges=["Busca por CNPJ", "Graficos interativos", "Exportacao imediata"],
        )

    info_col_1, info_col_2 = st.columns(2)
    with info_col_1:
        if query_scope == "organ":
            section_header(
                "O que este modulo entrega",
                "Uma leitura anual do orgao com separacao entre contratos, compras/licitações e atas.",
                icon="🧩",
            )
            st.markdown(
                """
                <div class="info-card">
                    <p class="section-copy">
                        Consulta por CNPJ exato do orgao, faixa anual obrigatoria, panorama consolidado por tipo
                        de documento, filtros por objeto/unidade/fornecedor e exportacao pronta para compartilhamento.
                    </p>
                    <div class="pill-row">
                        <span class="pill">Contratos anuais</span>
                        <span class="pill">Compras e atas</span>
                        <span class="pill">Base consolidada</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            section_header(
                "O que este painel entrega",
                "Uma superficie de trabalho orientada a leitura operacional, nao so uma vitrine de dados.",
                icon="🧩",
            )
            st.markdown(
                """
                <div class="info-card">
                    <p class="section-copy">
                        Busca por CNPJ, paginacao automatica, validacao do documento, visao executiva,
                        recortes por orgao/ano/situacao, base clicavel e exportacao.
                    </p>
                    <div class="pill-row">
                        <span class="pill">Busca profissional</span>
                        <span class="pill">Graficos interativos</span>
                        <span class="pill">Exportacao imediata</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with info_col_2:
        if query_scope == "organ":
            section_header(
                "Fluxo recomendado",
                "Passos curtos para sair do CNPJ do orgao e chegar a uma leitura anual filtravel.",
                icon="🧭",
            )
            st.markdown(
                """
                <div class="info-card">
                    <p class="section-copy">
                        1. Informe o CNPJ do orgao. 2. Escolha ano inicial e final.
                        3. Execute a busca. 4. Filtre por objeto, documento, unidade ou fornecedor.
                        5. Exporte a base consolidada.
                    </p>
                    <div class="pill-row">
                        <span class="pill">Faixa de ate 5 anos</span>
                        <span class="pill">Filtro por objeto</span>
                        <span class="pill">Exportacao executiva</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            section_header(
                "Fluxo recomendado",
                "Passos curtos para chegar da consulta bruta a uma base pronta para compartilhar.",
                icon="🧭",
            )
            st.markdown(
                """
                <div class="info-card">
                    <p class="section-copy">
                        1. Informe o CNPJ do fornecedor. 2. Defina periodo, se quiser um recorte.
                        3. Execute a busca. 4. Refine os filtros dinamicos. 5. Exporte a base final.
                    </p>
                    <div class="pill-row">
                        <span class="pill">CNPJ com ou sem mascara</span>
                        <span class="pill">Periodo opcional</span>
                        <span class="pill">Base clicavel no portal</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def main() -> None:
    load_css()
    initialize_state()
    sidebar_state = render_sidebar()
    query_scope = sidebar_state["query_scope"]
    render_masthead(query_scope)

    if sidebar_state["submitted"]:
        loading_placeholder = st.empty()
        with loading_placeholder.container():
            render_loading_skeleton()
        try:
            if query_scope == "organ":
                run_organ_search(
                    sidebar_state["cnpj_input"],
                    int(sidebar_state["start_year"]),
                    int(sidebar_state["end_year"]),
                )
            else:
                run_supplier_search(
                    sidebar_state["cnpj_input"],
                    sidebar_state["start_date"],
                    sidebar_state["end_date"],
                )
        except PncpApiError as exc:
            loading_placeholder.empty()
            ui_alert("error", str(exc))
            st.stop()
        loading_placeholder.empty()

    if query_scope == "organ":
        records_df = st.session_state.get("organ_documents_df")
        query_meta = st.session_state.get("organ_query_meta", {})
    else:
        records_df = st.session_state.get("supplier_contracts_df")
        query_meta = st.session_state.get("supplier_query_meta", {})

    if records_df is None:
        render_initial_screen(query_scope)
        footer_block(repo_url=REPO_URL, timestamp=datetime.now().strftime("%d/%m/%Y %H:%M"))
        return

    if records_df.empty:
        if query_scope == "organ":
            ui_alert("warning", "Nenhum documento foi encontrado para o orgao e a faixa anual informados.")
        else:
            ui_alert("warning", "Nenhum contrato foi encontrado para o CNPJ informado.")
        footer_block(repo_url=REPO_URL, timestamp=datetime.now().strftime("%d/%m/%Y %H:%M"))
        return

    if query_scope == "organ":
        render_organ_dashboard(records_df, query_meta)
    else:
        render_dashboard(records_df, query_meta)


if __name__ == "__main__":
    main()
