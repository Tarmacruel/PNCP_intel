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
            --bg: #f4f7fb;
            --surface: #ffffff;
            --text: #102a43;
            --muted: #627d98;
            --primary: #0b4f6c;
            --border: rgba(11, 79, 108, 0.12);
            --shadow: 0 20px 60px rgba(16, 42, 67, 0.08);
        }

        html, body, [class*="css"] { font-family: "Manrope", sans-serif; }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(11, 79, 108, 0.08), transparent 28%),
                linear-gradient(180deg, #f8fbfe 0%, var(--bg) 100%);
        }
        #MainMenu, header, footer { visibility: hidden; }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(11,79,108,.98) 0%, rgba(10,61,83,.98) 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        [data-testid="stSidebar"] * { color: #f8fbfe; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span { color: #f8fbfe !important; }
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea { color: #102a43 !important; }
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        .masthead {
            position: relative;
            overflow: hidden;
            padding: 1.6rem 1.7rem;
            border: 1px solid var(--border);
            border-radius: 24px;
            background: linear-gradient(135deg, rgba(10,61,83,.98) 0%, rgba(11,79,108,.94) 56%, rgba(192,122,44,.88) 100%);
            box-shadow: var(--shadow);
            color: #ffffff;
            margin-bottom: 1.2rem;
            animation: rise 320ms ease-out;
        }
        .masthead::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(120deg, rgba(255,255,255,.04) 0%, transparent 35%),
                radial-gradient(circle at 85% 15%, rgba(255,255,255,.14), transparent 26%);
            pointer-events: none;
        }
        .masthead-grid {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: minmax(0, 1.6fr) minmax(240px, .8fr);
            gap: 1rem;
            align-items: end;
        }
        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            padding: .36rem .7rem;
            border-radius: 999px;
            background: rgba(255,255,255,.12);
            font-size: .78rem;
            font-weight: 700;
            letter-spacing: .08em;
            text-transform: uppercase;
        }
        .masthead h1 {
            margin: .9rem 0 .45rem 0;
            font-size: clamp(1.9rem, 3vw, 2.7rem);
            line-height: 1.05;
            font-weight: 800;
        }
        .masthead p { margin: 0; max-width: 64ch; line-height: 1.6; color: rgba(255,255,255,.88); }
        .masthead-note {
            padding: .95rem 1rem;
            border-radius: 18px;
            background: rgba(255,255,255,.12);
            backdrop-filter: blur(6px);
            border: 1px solid rgba(255,255,255,.16);
        }
        .masthead-note strong {
            display: block;
            font-size: .82rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            opacity: .86;
            margin-bottom: .45rem;
        }
        .masthead-note span { display: block; font-size: 1rem; line-height: 1.55; }
        .metric-card {
            padding: 1rem 1.1rem;
            border-radius: 20px;
            border: 1px solid var(--border);
            background: rgba(255,255,255,.92);
            box-shadow: 0 10px 32px rgba(16,42,67,.05);
            animation: rise 360ms ease-out;
        }
        .metric-label {
            color: var(--muted);
            font-size: .77rem;
            font-weight: 700;
            letter-spacing: .06em;
            text-transform: uppercase;
        }
        .metric-value {
            margin-top: .4rem;
            color: var(--text);
            font-size: clamp(1.2rem, 2vw, 1.85rem);
            font-weight: 800;
            line-height: 1.1;
        }
        .metric-subtitle { margin-top: .35rem; color: var(--muted); font-size: .85rem; }
        .filter-card, .info-card {
            padding: 1rem 1.1rem;
            border-radius: 18px;
            background: rgba(255,255,255,.88);
            border: 1px solid var(--border);
            box-shadow: 0 12px 34px rgba(16,42,67,.05);
        }
        .section-title { margin: 0; color: var(--text); font-size: 1.05rem; font-weight: 800; letter-spacing: -.01em; }
        .section-copy { margin: .28rem 0 0 0; color: var(--muted); font-size: .92rem; line-height: 1.55; }
        .pill-row { display: flex; flex-wrap: wrap; gap: .55rem; margin-top: .8rem; }
        .pill {
            display: inline-flex;
            align-items: center;
            gap: .4rem;
            padding: .45rem .72rem;
            border-radius: 999px;
            background: rgba(11,79,108,.08);
            color: var(--primary);
            font-size: .8rem;
            font-weight: 700;
        }
        .empty-state {
            padding: 1.2rem 1.3rem;
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(238,243,248,.9));
            border: 1px dashed rgba(11,79,108,.22);
            color: var(--text);
        }
        .empty-state h3 { margin: 0 0 .4rem 0; font-size: 1.05rem; }
        .empty-state p { margin: 0; color: var(--muted); line-height: 1.65; }
        .stTabs [data-baseweb="tab-list"] { gap: .5rem; padding-bottom: .2rem; }
        .stTabs [data-baseweb="tab"] {
            height: auto;
            padding: .7rem 1rem;
            border-radius: 999px;
            background: rgba(255,255,255,.84);
            border: 1px solid var(--border);
            color: var(--muted);
            font-weight: 700;
        }
        .stTabs [aria-selected="true"] {
            color: var(--primary) !important;
            border-color: rgba(11,79,108,.24);
            box-shadow: 0 10px 24px rgba(16,42,67,.06);
        }
        .stButton > button,
        .stDownloadButton > button,
        .stFormSubmitButton > button {
            width: 100%;
            border: 0;
            border-radius: 14px;
            background: linear-gradient(135deg, #0b4f6c 0%, #13627f 100%);
            color: white;
            font-weight: 800;
            padding: .72rem 1rem;
            box-shadow: 0 14px 30px rgba(11,79,108,.18);
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover,
        .stFormSubmitButton > button:hover {
            border: 0;
            color: white;
            background: linear-gradient(135deg, #0a465f 0%, #115873 100%);
        }
        div[data-testid="stDataFrame"] {
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid var(--border);
            box-shadow: 0 14px 40px rgba(16,42,67,.05);
            background: rgba(255,255,255,.92);
        }
        .stPlotlyChart { padding: .2rem 0; }
        @keyframes rise {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @media (max-width: 980px) { .masthead-grid { grid-template-columns: 1fr; } }
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


def render_metric_card(label: str, value: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-state">
            <h3>Pronto para consultar o fornecedor</h3>
            <p>
                Informe o CNPJ no menu lateral, opcionalmente aplique um recorte temporal e execute a busca.
                O painel consolida metricas, distribuicoes, evolucao temporal, base completa e exportacoes.
            </p>
        </div>
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
        st.caption("Use o CNPJ da empresa para localizar contratos e empenhos indexados no portal.")

        with st.form("search_form", clear_on_submit=False):
            cnpj_input = st.text_input(
                "CNPJ",
                placeholder="00.000.000/0000-00",
                help="Aceita entrada com ou sem pontuacao.",
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
                    start_date = st.date_input("Inicial", value=default_start, format="DD/MM/YYYY")
                with period_col_2:
                    end_date = st.date_input("Final", value=today, format="DD/MM/YYYY")

            submitted = st.form_submit_button("Buscar contratos", use_container_width=True)

        st.markdown("---")
        st.markdown("### Fonte")
        st.caption(
            "Painel baseado na busca publica do PNCP e no endpoint oficial de detalhe de contratos."
        )

        st.markdown("### Notas operacionais")
        st.caption(
            "A primeira consulta pode levar alguns segundos, dependendo do volume paginado e da resposta do portal."
        )

    return submitted, cnpj_input, start_date, end_date


def initialize_state() -> None:
    st.session_state.setdefault("contracts_df", None)
    st.session_state.setdefault("query_meta", {})


def run_search(cnpj_input: str, start_date: date | None, end_date: date | None) -> None:
    cnpj = format_cnpj(cnpj_input)
    if not cnpj:
        st.error("Informe um CNPJ para iniciar a consulta.")
        st.stop()

    if not validate_cnpj(cnpj):
        st.error("O CNPJ informado e invalido. Revise os digitos e tente novamente.")
        st.stop()

    if start_date and end_date and start_date > end_date:
        st.error("A data inicial nao pode ser posterior a data final.")
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
        st.warning(
            "A amostra verificada nao confirmou todos os contratos no CNPJ informado. Revise manualmente antes de usar a base para decisao."
        )

    if df.empty:
        st.warning("Nenhum contrato foi localizado para o CNPJ informado.")
        return

    orgao_options = sorted(df["orgao_nome"].dropna().unique().tolist())
    year_options = sorted([int(year) for year in df["ano"].dropna().unique().tolist()], reverse=True)
    situation_options = sorted(df["situacao_nome"].dropna().unique().tolist())

    st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
    st.markdown(
        """
        <p class="section-title">Filtros dinamicos da superficie analitica</p>
        <p class="section-copy">Os filtros abaixo refinam todos os graficos, metricas, tabela e exportacoes.</p>
        """,
        unsafe_allow_html=True,
    )

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
        st.warning("Os filtros aplicados nao retornaram contratos. Ajuste os recortes para continuar.")
        return

    total_contracts = len(filtered_df)
    total_value = filtered_df["valor_global"].sum()
    average_value = filtered_df["valor_global"].mean()
    unique_organs = filtered_df["orgao_nome"].nunique()
    years_covered = filtered_df["ano"].dropna().nunique()

    metric_col_1, metric_col_2, metric_col_3, metric_col_4, metric_col_5 = st.columns(5)
    with metric_col_1:
        render_metric_card("Contratos", format_integer(total_contracts), "Base filtrada")
    with metric_col_2:
        render_metric_card("Valor total", format_currency(total_value), "Soma da carteira")
    with metric_col_3:
        render_metric_card("Valor medio", format_currency(average_value), "Ticket medio")
    with metric_col_4:
        render_metric_card("Orgaos", format_integer(unique_organs), "Relacionamentos distintos")
    with metric_col_5:
        render_metric_card("Anos cobertos", format_integer(years_covered), "Historico visivel")

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
            st.markdown("#### Top orgaos por valor contratado")
            st.plotly_chart(build_top_orgs_chart(filtered_df), use_container_width=True)
        with exec_col_2:
            st.markdown("#### Situacao das contratacoes")
            st.plotly_chart(build_status_donut(filtered_df), use_container_width=True)

        summary = (
            filtered_df.groupby("tipo_contrato_nome", dropna=False)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
            .sort_values(["quantidade", "valor_total"], ascending=[False, False])
        )
        summary["valor_total"] = summary["valor_total"].apply(format_currency)
        st.markdown("#### Resumo por tipo contratual")
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
            st.markdown("#### Evolucao mensal")
            st.plotly_chart(build_timeline_chart(filtered_df), use_container_width=True)
        with timeline_col_2:
            st.markdown("#### Volume anual")
            st.plotly_chart(build_yearly_chart(filtered_df), use_container_width=True)

        organ_summary = (
            filtered_df.groupby(["orgao_nome", "uf"], dropna=False)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
            .sort_values("valor_total", ascending=False)
            .head(15)
        )
        organ_summary["valor_total"] = organ_summary["valor_total"].apply(format_currency)
        st.markdown("#### Ranking consolidado de orgaos")
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
        st.markdown("#### Relacao completa de contratos filtrados")

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

        st.dataframe(
            table_df.rename(
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
            st.markdown("#### Histograma de valores")
            st.plotly_chart(build_value_histogram(filtered_df), use_container_width=True)
        with dist_col_2:
            st.markdown("#### Boxplot dos valores")
            st.plotly_chart(build_value_boxplot(filtered_df), use_container_width=True)

        bands_df = build_value_bands(filtered_df)
        bands_df["valor_total"] = bands_df["valor_total"].apply(format_currency)
        bands_df["valor_medio"] = bands_df["valor_medio"].apply(format_currency)
        bands_df["participacao"] = bands_df["participacao"].map(lambda value: f"{value:.1f}%")
        st.markdown("#### Faixas de valor")
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
        st.markdown("#### Exportar base filtrada")
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

        st.markdown("#### Links uteis")
        st.markdown(
            f"""
            - [Abrir consulta do fornecedor no portal]({APP_BASE_URL}/buscar/todos?q={meta.get('cnpj', '')}&pagina=1)
            - [Listagem publica de contratos]({APP_BASE_URL}/contratos?pagina=1)
            - [Swagger da API de consulta do PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
            """
        )

    st.caption(
        f"Ultima atualizacao local: {meta.get('fetched_at', '-')}. Filtros aplicados sobre a base retornada pelo portal do PNCP."
    )


def render_initial_screen() -> None:
    render_empty_state()

    info_col_1, info_col_2 = st.columns(2)
    with info_col_1:
        st.markdown(
            """
            <div class="info-card">
                <p class="section-title">O que este painel entrega</p>
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
        st.markdown(
            """
            <div class="info-card">
                <p class="section-title">Fluxo recomendado</p>
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
        try:
            run_search(cnpj_input, start_date, end_date)
        except PncpApiError as exc:
            st.error(str(exc))
            st.stop()

    contracts_df = st.session_state.get("contracts_df")
    query_meta = st.session_state.get("query_meta", {})

    if contracts_df is None:
        render_initial_screen()
        return

    if contracts_df.empty:
        st.warning("Nenhum contrato foi encontrado para o CNPJ informado.")
        return

    render_dashboard(contracts_df, query_meta)


if __name__ == "__main__":
    main()
