from __future__ import annotations

import math
import time
from datetime import date, datetime
from io import BytesIO
from typing import Any

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
APP_BASE_URL = "https://pncp.gov.br/app"
REPO_URL = "https://github.com/Tarmacruel/PNCP_intel"
CACHE_TTL_SECONDS = 3600
DEFAULT_PAGE_SIZE = 100
MAX_RETRIES = 4
DEFAULT_SORT = "-data"
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
COLOR_PRIMARY = "#0B4F6C"
COLOR_ACCENT = "#C07A2C"


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
        }

        .masthead h1 {
            margin: .85rem 0 .5rem;
            font-size: clamp(2rem, 3vw, 2.8rem);
            line-height: 1.02;
            letter-spacing: -.03em;
            font-weight: 800;
        }

        .masthead p {
            margin: 0;
            max-width: 62ch;
            font-size: 1rem;
            line-height: 1.62;
            color: rgba(255,255,255,.86);
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
        }

        .masthead-note span {
            display: block;
            line-height: 1.55;
            font-size: .98rem;
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
        }

        .stTabs [data-baseweb="tab"] {
            height: auto;
            padding: .72rem 1rem;
            border-radius: 999px;
            background: rgba(255,255,255,.84);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            font-weight: 700;
        }

        .stTabs [aria-selected="true"] {
            color: var(--primary) !important;
            border-color: rgba(18,52,77,.22);
            box-shadow: 0 12px 26px rgba(17,40,59,.08);
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
            background: rgba(255,255,255,.96);
            box-shadow: var(--shadow-sm);
            padding: .2rem .25rem;
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
            .metric-card { min-height: 138px; }
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
                raise PncpApiError(f"Erro definitivo do PNCP ({status_code}) ao consultar {url}.") from exc

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


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_contract_search(cnpj: str) -> dict[str, Any]:
    params = {
        "q": cnpj,
        "tipos_documento": "contrato",
        "ordenacao": DEFAULT_SORT,
        "pagina": 1,
        "tam_pagina": DEFAULT_PAGE_SIZE,
    }

    all_items: list[dict[str, Any]] = []

    with httpx.Client(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": f"{APP_TITLE}/1.0"},
    ) as client:
        first_payload = request_json(client, SEARCH_API_URL, params=params)
        first_items = first_payload.get("items", []) or []
        total_records = int(first_payload.get("total") or len(first_items))
        total_pages = max(1, math.ceil(total_records / DEFAULT_PAGE_SIZE)) if total_records else 1
        all_items.extend(first_items)

        for page in range(2, total_pages + 1):
            params["pagina"] = page
            payload = request_json(client, SEARCH_API_URL, params=params)
            all_items.extend(payload.get("items", []) or [])

    deduplicated_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in all_items:
        unique_key = item.get("numero_controle_pncp") or item.get("id") or item.get("item_url")
        if not unique_key or unique_key in seen_ids:
            continue
        seen_ids.add(unique_key)
        deduplicated_items.append(item)

    supplier_name = None
    sample_checked = 0
    sample_exact_match = True
    for sample_item in deduplicated_items[:5]:
        detail = fetch_contract_detail(sample_item.get("item_url", ""))
        if not detail:
            continue
        sample_checked += 1
        supplier_name = supplier_name or detail.get("nomeRazaoSocialFornecedor")
        if detail.get("niFornecedor") != cnpj:
            sample_exact_match = False

    return {
        "items": deduplicated_items,
        "total_records": total_records,
        "total_pages": total_pages,
        "supplier_name": supplier_name,
        "sample_checked": sample_checked,
        "sample_exact_match": sample_exact_match,
    }


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


def render_masthead() -> None:
    st.markdown(
        """
        <section class="masthead">
            <div class="masthead-grid">
                <div>
                    <span class="eyebrow">Painel analitico do PNCP</span>
                    <h1>Dossie de contratos publicos por fornecedor</h1>
                    <p>
                        Consulte contratos e empenhos publicados no PNCP a partir do CNPJ da empresa,
                        aplique recortes operacionais e exporte a base tratada para Excel ou CSV.
                    </p>
                </div>
                <div class="masthead-note">
                    <strong>Fonte operacional</strong>
                    <span>
                        Busca publica do portal PNCP com paginacao automatica e enriquecimento por endpoint
                        de detalhe para verificacao do fornecedor.
                    </span>
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
    start_date: date | None,
    end_date: date | None,
    sample_checked: int,
    sample_exact_match: bool,
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

    st.markdown(
        f"""
        <div class="info-card">
            <p class="section-title">{supplier_name or "Fornecedor consultado"}</p>
            <p class="section-copy">
                CNPJ {format_cnpj_display(cnpj)} | {format_integer(total_records)} contratos indexados no portal
            </p>
            <div class="pill-row">
                <span class="pill">Periodo: {period_label}</span>
                <span class="pill">Recorte amostral: {sample_checked} contrato(s)</span>
                <span class="pill">{quality_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_top_orgs_chart(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby("orgao_nome", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("valor_total", ascending=False)
        .head(12)
        .sort_values("valor_total", ascending=True)
    )

    fig = px.bar(
        grouped,
        x="valor_total",
        y="orgao_nome",
        orientation="h",
        text="quantidade",
        color="valor_total",
        color_continuous_scale=["#D9EAF3", COLOR_PRIMARY],
        labels={"valor_total": "Valor total", "orgao_nome": "Orgao"},
    )
    fig.update_traces(
        texttemplate="%{text} itens",
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Valor total: %{x:$,.2f}<br>Quantidade: %{text}<extra></extra>",
    )
    fig.update_layout(
        height=520,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis_title="Valor total (R$)",
        yaxis_title="",
    )
    return fig


def build_status_donut(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby("situacao_nome", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("quantidade", ascending=False)
    )

    fig = px.pie(
        grouped,
        names="situacao_nome",
        values="quantidade",
        hole=0.62,
        color_discrete_sequence=[COLOR_PRIMARY, COLOR_ACCENT, "#5D7A8C", "#8FB8D8", "#D6A96A"],
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>Contratos: %{value}<br>Participacao: %{percent}<extra></extra>",
    )
    fig.update_layout(
        height=440,
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=20, b=0),
        showlegend=True,
        legend_title_text="Situacao",
    )
    return fig


def build_timeline_chart(df: pd.DataFrame) -> go.Figure:
    monthly = (
        df.dropna(subset=["mes_ano"])
        .groupby("mes_ano")
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("mes_ano")
    )

    fig = go.Figure()
    fig.add_bar(
        x=monthly["mes_ano"],
        y=monthly["valor_total"],
        name="Valor total",
        marker_color=COLOR_PRIMARY,
        opacity=0.9,
        hovertemplate="%{x|%m/%Y}<br>Valor total: %{y:$,.2f}<extra></extra>",
    )
    fig.add_scatter(
        x=monthly["mes_ano"],
        y=monthly["quantidade"],
        name="Quantidade",
        mode="lines+markers",
        line=dict(color=COLOR_ACCENT, width=3),
        marker=dict(size=7),
        yaxis="y2",
        hovertemplate="%{x|%m/%Y}<br>Contratos: %{y}<extra></extra>",
    )
    fig.update_layout(
        height=460,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis=dict(title="Valor total (R$)", rangemode="tozero"),
        yaxis2=dict(title="Quantidade", overlaying="y", side="right", rangemode="tozero"),
        xaxis=dict(title="Mes de referencia"),
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

    fig = px.bar(
        yearly,
        x="ano",
        y="quantidade",
        color="valor_total",
        color_continuous_scale=["#E6EEF5", COLOR_ACCENT],
        labels={"ano": "Ano", "quantidade": "Quantidade"},
    )
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Contratos: %{y}<br>Valor total: %{marker.color:$,.2f}<extra></extra>"
    )
    fig.update_layout(
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=20, b=0),
    )
    return fig


def build_value_histogram(df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(
        df,
        x="valor_global",
        nbins=30,
        color_discrete_sequence=[COLOR_PRIMARY],
        labels={"valor_global": "Valor global"},
    )
    fig.update_traces(hovertemplate="Faixa: %{x}<br>Contratos: %{y}<extra></extra>")
    fig.update_layout(
        height=420,
        bargap=0.08,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis_title="Valor global (R$)",
        yaxis_title="Quantidade",
    )
    return fig


def build_value_boxplot(df: pd.DataFrame) -> go.Figure:
    fig = px.box(
        df,
        y="valor_global",
        color_discrete_sequence=[COLOR_ACCENT],
        points="outliers",
        labels={"valor_global": "Valor global"},
    )
    fig.update_layout(
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=20, b=0),
        yaxis_title="Valor global (R$)",
        xaxis_title="",
        showlegend=False,
    )
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


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Contratos")
    return output.getvalue()


def render_sidebar() -> tuple[bool, str, date | None, date | None]:
    with st.sidebar:
        st.markdown("## Consulta do fornecedor")
        st.caption("Informe o CNPJ e, se quiser, aplique um recorte temporal para leitura operacional.")

        with st.form("search_form", clear_on_submit=False):
            st.markdown("**CNPJ do fornecedor**")
            cnpj_input = st.text_input(
                "CNPJ",
                placeholder="00.000.000/0000-00",
                help="Aceita entrada com ou sem pontuacao.",
                label_visibility="collapsed",
            )

            use_period_filter = st.toggle(
                "Aplicar recorte por data de assinatura",
                value=False,
                help="Desligado: considera todo o historico indexado na busca do portal.",
            )

            start_date: date | None = None
            end_date: date | None = None

            if use_period_filter:
                today = date.today()
                default_start = date(today.year - 1, 1, 1)
                period_col_1, period_col_2 = st.columns(2)
                with period_col_1:
                    st.caption("Inicial")
                    start_date = st.date_input(
                        "Inicial",
                        value=default_start,
                        format="DD/MM/YYYY",
                        label_visibility="collapsed",
                    )
                with period_col_2:
                    st.caption("Final")
                    end_date = st.date_input(
                        "Final",
                        value=today,
                        format="DD/MM/YYYY",
                        label_visibility="collapsed",
                    )

            submitted = st.form_submit_button("Buscar contratos", use_container_width=True)

        st.markdown("---")
        st.markdown("### Fonte")
        st.caption("Busca publica do portal PNCP com enriquecimento no endpoint oficial de detalhe.")
        st.markdown(
            """
            - Portal: `pncp.gov.br`
            - Atualizacao: tempo real
            - Exportacao: Excel e CSV
            """
        )

        st.markdown("### Notas operacionais")
        st.caption("A primeira busca pode levar alguns segundos por causa da paginacao e do cache inicial.")

    return submitted, cnpj_input, start_date, end_date


def initialize_state() -> None:
    st.session_state.setdefault("contracts_df", None)
    st.session_state.setdefault("query_meta", {})


def run_search(cnpj_input: str, start_date: date | None, end_date: date | None) -> None:
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

    st.session_state["contracts_df"] = contracts_df
    st.session_state["query_meta"] = {
        "cnpj": cnpj,
        "supplier_name": payload.get("supplier_name") or "Fornecedor consultado",
        "total_records": payload.get("total_records", len(contracts_df)),
        "total_pages": payload.get("total_pages", 1),
        "sample_checked": payload.get("sample_checked", 0),
        "sample_exact_match": payload.get("sample_exact_match", True),
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "fetched_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def render_dashboard(df: pd.DataFrame, meta: dict[str, Any]) -> None:
    requested_start = meta.get("requested_start_date")
    requested_end = meta.get("requested_end_date")

    render_filter_summary(
        cnpj=meta.get("cnpj", ""),
        supplier_name=meta.get("supplier_name", "Fornecedor consultado"),
        total_records=meta.get("total_records", len(df)),
        start_date=requested_start,
        end_date=requested_end,
        sample_checked=meta.get("sample_checked", 0),
        sample_exact_match=meta.get("sample_exact_match", True),
    )

    if meta.get("sample_checked", 0) > 0 and not meta.get("sample_exact_match", True):
        ui_alert(
            "warning",
            "A amostra verificada nao confirmou todos os contratos no CNPJ informado. Revise manualmente antes de usar a base para decisao.",
        )

    if df.empty:
        ui_empty_state(
            icon="📭",
            title="Nenhum contrato encontrado",
            message="Nao localizamos contratos para este CNPJ no indice publico do PNCP.",
            badges=["Revise o CNPJ", "Tente novamente mais tarde", "Verifique a indexacao no portal"],
        )
        return

    orgao_options = sorted(df["orgao_nome"].dropna().unique().tolist())
    year_options = sorted([int(year) for year in df["ano"].dropna().unique().tolist()], reverse=True)
    situation_options = sorted(df["situacao_nome"].dropna().unique().tolist())

    section_header(
        "Filtros dinamicos da analise",
        "Todos os graficos, metricas, exportacoes e a tabela respondem aos recortes abaixo.",
        icon="🎛️",
    )
    st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    with filter_col_1:
        selected_orgaos = st.multiselect("Orgao", options=orgao_options, default=[])
    with filter_col_2:
        selected_years = st.multiselect("Ano", options=year_options, default=[])
    with filter_col_3:
        selected_situations = st.multiselect("Situacao", options=situation_options, default=[])
    st.markdown("</div>", unsafe_allow_html=True)

    filtered_df = apply_dashboard_filters(
        df,
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

    tab_1, tab_2, tab_3, tab_4, tab_5 = st.tabs(
        [
            "Visao executiva",
            "Orgaos e temporalidade",
            "Base completa",
            "Distribuicao de valor",
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
                build_status_donut(filtered_df),
                "Situacao das contratacoes",
                "Distribuicao das publicacoes por status do portal.",
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
                "Distribuicao dos tickets contratuais em faixas continuas.",
                icon="📶",
            )
        with dist_col_2:
            chart_wrapper(
                build_value_boxplot(filtered_df),
                "Boxplot dos valores",
                "Amplitude, mediana e outliers da carteira filtrada.",
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
        section_header(
            "Exportar base filtrada",
            "Leve a base tratada para analise externa ou consolidacao interna.",
            icon="⬇️",
        )
        export_df = filtered_df.copy()
        export_df["data_assinatura"] = export_df["data_assinatura"].dt.strftime("%Y-%m-%d")
        export_df["data_publicacao_pncp"] = export_df["data_publicacao_pncp"].dt.strftime("%Y-%m-%d")
        export_df["data_atualizacao_pncp"] = export_df["data_atualizacao_pncp"].dt.strftime("%Y-%m-%d")
        export_df["data_referencia"] = export_df["data_referencia"].dt.strftime("%Y-%m-%d")
        export_df["mes_ano"] = export_df["mes_ano"].dt.strftime("%Y-%m-%d")

        export_col_1, export_col_2 = st.columns(2)
        file_stem = f"pncp_contratos_{meta.get('cnpj', '')}"
        with export_col_1:
            st.download_button(
                "Baixar Excel",
                data=dataframe_to_excel_bytes(export_df),
                file_name=f"{file_stem}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.caption("Planilha com a base filtrada, pronta para analise complementar.")
        with export_col_2:
            st.download_button(
                "Baixar CSV",
                data=dataframe_to_csv_bytes(export_df),
                file_name=f"{file_stem}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.caption("Arquivo UTF-8 com separador ponto e virgula.")

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


def render_initial_screen() -> None:
    ui_empty_state(
        icon="🔎",
        title="Pronto para consultar o fornecedor",
        message="Informe o CNPJ no menu lateral, execute a busca e navegue por metricas, series temporais, base completa e exportacoes.",
        badges=["Busca por CNPJ", "Graficos interativos", "Exportacao imediata"],
    )

    info_col_1, info_col_2 = st.columns(2)
    with info_col_1:
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
    render_masthead()

    submitted, cnpj_input, start_date, end_date = render_sidebar()

    if submitted:
        loading_placeholder = st.empty()
        with loading_placeholder.container():
            render_loading_skeleton()
        try:
            run_search(cnpj_input, start_date, end_date)
        except PncpApiError as exc:
            loading_placeholder.empty()
            ui_alert("error", str(exc))
            st.stop()
        loading_placeholder.empty()

    contracts_df = st.session_state.get("contracts_df")
    query_meta = st.session_state.get("query_meta", {})

    if contracts_df is None:
        render_initial_screen()
        footer_block(repo_url=REPO_URL, timestamp=datetime.now().strftime("%d/%m/%Y %H:%M"))
        return

    if contracts_df.empty:
        ui_alert("warning", "Nenhum contrato foi encontrado para o CNPJ informado.")
        footer_block(repo_url=REPO_URL, timestamp=datetime.now().strftime("%d/%m/%Y %H:%M"))
        return

    render_dashboard(contracts_df, query_meta)


if __name__ == "__main__":
    main()
