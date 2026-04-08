from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLOR_PRIMARY = "#14526E"
COLOR_PRIMARY_SOFT = "#7BAFC8"
COLOR_ACCENT = "#C68432"
COLOR_TEXT = "#163348"
COLOR_SUBTEXT = "#5D7185"
COLOR_GRID = "rgba(22, 51, 72, 0.10)"
COLOR_AXIS = "rgba(22, 51, 72, 0.18)"
COLOR_SURFACE = "#FFFFFF"


def _empty_chart(message: str, *, height: int = 380) -> go.Figure:
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
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_SURFACE,
        margin=dict(l=16, r=16, t=18, b=16),
    )
    return fig


def _apply_theme(fig: go.Figure, *, height: int, hovermode: str = "closest") -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=COLOR_SURFACE,
        margin=dict(l=18, r=18, t=18, b=16),
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


def _shorten(value: str, limit: int = 30) -> str:
    compact = " ".join(str(value or "Nao informado").split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1]}…"


def build_heatmap_uf_year(df: pd.DataFrame) -> go.Figure:
    if df.empty or df["uf"].dropna().empty or df["ano"].dropna().empty:
        return _empty_chart("Sem base suficiente para o heatmap por UF e ano.", height=420)

    heatmap_df = (
        df.dropna(subset=["uf", "ano"])
        .groupby(["uf", "ano"], dropna=False)
        .agg(valor_total=("valor_global", "sum"))
        .reset_index()
    )
    pivot_df = heatmap_df.pivot(index="uf", columns="ano", values="valor_total").fillna(0.0)

    fig = px.imshow(
        pivot_df,
        color_continuous_scale=["#EAF3F8", COLOR_PRIMARY],
        aspect="auto",
        labels=dict(x="Ano", y="UF", color="Valor total"),
    )
    _apply_theme(fig, height=420)
    fig.update_traces(
        hovertemplate="<b>UF %{y}</b><br>Ano: %{x}<br>Valor total: R$ %{z:,.2f}<extra></extra>"
    )
    fig.update_layout(coloraxis_colorbar=dict(title="Valor"))
    return fig


def build_treemap_hierarchy(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("Sem dados para a hierarquia por esfera, UF e orgao.", height=520)

    treemap_df = df.copy()
    treemap_df["esfera_nome"] = treemap_df["esfera_nome"].fillna("Nao informada")
    treemap_df["uf"] = treemap_df["uf"].fillna("N/A")
    treemap_df["orgao_resumido"] = treemap_df["orgao_nome"].apply(lambda value: _shorten(value, 42))
    treemap_df = (
        treemap_df.groupby(["esfera_nome", "uf", "orgao_resumido"], dropna=False)
        .agg(valor_global=("valor_global", "sum"))
        .reset_index()
    )

    fig = px.treemap(
        treemap_df,
        path=["esfera_nome", "uf", "orgao_resumido"],
        values="valor_global",
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Valor acumulado: R$ %{value:,.2f}<extra></extra>",
        marker_line_width=1,
        marker_line_color="rgba(255,255,255,0.55)",
        marker_colorscale=["#EAF3F8", COLOR_PRIMARY],
    )
    fig.update_layout(
        height=520,
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=18, b=8),
        font=dict(family="Manrope, sans-serif", color=COLOR_TEXT),
    )
    return fig


def build_funnel_status(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby("situacao_nome", dropna=False)
        .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
        .reset_index()
        .sort_values("quantidade", ascending=False)
    )
    if grouped.empty:
        return _empty_chart("Sem status para montar o funil.", height=420)

    fig = go.Figure(
        go.Funnel(
            y=grouped["situacao_nome"].apply(lambda value: _shorten(value, 28)),
            x=grouped["quantidade"],
            texttemplate="%{value}",
            textposition="inside",
            marker=dict(color=[COLOR_PRIMARY, "#2E6C8A", "#4E86A2", "#82ACC0", COLOR_ACCENT][: len(grouped)]),
            customdata=grouped["valor_total"],
            hovertemplate="<b>%{y}</b><br>Qtd. contratos: %{x}<br>Valor total: R$ %{customdata:,.2f}<extra></extra>",
        )
    )
    _apply_theme(fig, height=420)
    fig.update_xaxes(title="Qtd. contratos")
    fig.update_yaxes(title="")
    return fig


def build_scatter_value_over_time(df: pd.DataFrame) -> go.Figure:
    scatter_df = df.dropna(subset=["data_referencia"]).copy()
    if scatter_df.empty:
        return _empty_chart("Sem datas suficientes para a dispersao temporal.", height=420)

    if len(scatter_df) > 2000:
        scatter_df = scatter_df.sample(2000, random_state=42)

    scatter_df["tipo_resumido"] = scatter_df["tipo_contrato_nome"].apply(lambda value: _shorten(value, 22))
    scatter_df["orgao_resumido"] = scatter_df["orgao_nome"].apply(lambda value: _shorten(value, 26))
    scatter_df["valor_size"] = scatter_df["valor_global"].clip(lower=1).apply(lambda value: math.sqrt(float(value)))

    fig = px.scatter(
        scatter_df,
        x="data_referencia",
        y="valor_global",
        color="tipo_resumido",
        size="valor_size",
        size_max=22,
        opacity=0.72,
        labels={"data_referencia": "Data de referencia", "valor_global": "Valor global"},
        custom_data=["orgao_resumido", "numero_controle_pncp"],
    )
    _apply_theme(fig, height=420)
    fig.update_yaxes(title="Valor global", type="log", tickprefix="R$ ")
    fig.update_xaxes(title="Data de referencia")
    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[1]}</b><br>Orgao: %{customdata[0]}<br>"
            "Valor global: R$ %{y:,.2f}<br>Data: %{x|%d/%m/%Y}<extra></extra>"
        ),
        marker=dict(line=dict(width=0)),
    )
    return fig


def build_boxplot_top_orgaos(df: pd.DataFrame) -> go.Figure:
    top_orgaos = (
        df.groupby("orgao_nome", dropna=False)["valor_global"]
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .index.tolist()
    )
    if not top_orgaos:
        return _empty_chart("Sem orgaos suficientes para o boxplot.", height=430)

    box_df = df[df["orgao_nome"].isin(top_orgaos)].copy()
    box_df["orgao_resumido"] = box_df["orgao_nome"].apply(lambda value: _shorten(value, 20))

    fig = px.box(
        box_df,
        x="orgao_resumido",
        y="valor_global",
        color="orgao_resumido",
        points="outliers",
    )
    _apply_theme(fig, height=430)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title="Orgao", tickangle=-28)
    fig.update_yaxes(title="Valor global", type="log", tickprefix="R$ ")
    return fig


def build_bubble_organs(df: pd.DataFrame) -> go.Figure:
    grouped = (
        df.groupby(["orgao_nome", "uf"], dropna=False)
        .agg(
            quantidade=("numero_controle_pncp", "count"),
            valor_total=("valor_global", "sum"),
            valor_medio=("valor_global", "mean"),
        )
        .reset_index()
        .sort_values("valor_total", ascending=False)
        .head(30)
    )
    if grouped.empty:
        return _empty_chart("Sem base suficiente para o mapa de bolhas.", height=430)

    grouped["orgao_resumido"] = grouped["orgao_nome"].apply(lambda value: _shorten(value, 24))

    fig = px.scatter(
        grouped,
        x="quantidade",
        y="valor_total",
        size="valor_medio",
        color="uf",
        hover_name="orgao_resumido",
        size_max=44,
        custom_data=["orgao_nome", "valor_medio"],
        labels={"quantidade": "Qtd. contratos", "valor_total": "Valor total"},
    )
    _apply_theme(fig, height=430)
    fig.update_yaxes(title="Valor total", tickprefix="R$ ")
    fig.update_xaxes(title="Qtd. contratos")
    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>Qtd. contratos: %{x}<br>"
            "Valor total: R$ %{y:,.2f}<br>Valor medio: R$ %{customdata[1]:,.2f}<extra></extra>"
        ),
        marker=dict(line=dict(width=0.5, color="rgba(15,36,52,0.12)")),
    )
    return fig


def build_sunburst_hierarchy(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("Sem hierarquia suficiente para o sunburst.", height=520)

    sunburst_df = df.copy()
    sunburst_df["esfera_nome"] = sunburst_df["esfera_nome"].fillna("Nao informada")
    sunburst_df["uf"] = sunburst_df["uf"].fillna("N/A")
    sunburst_df["tipo_resumido"] = sunburst_df["tipo_contrato_nome"].apply(lambda value: _shorten(value, 24))
    sunburst_df = (
        sunburst_df.groupby(["esfera_nome", "uf", "tipo_resumido"], dropna=False)
        .agg(valor_global=("valor_global", "sum"))
        .reset_index()
    )

    fig = px.sunburst(
        sunburst_df,
        path=["esfera_nome", "uf", "tipo_resumido"],
        values="valor_global",
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Valor acumulado: R$ %{value:,.2f}<extra></extra>",
        insidetextorientation="radial",
        marker_colorscale=["#EEF5FA", COLOR_ACCENT, COLOR_PRIMARY],
    )
    fig.update_layout(
        height=520,
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=18, b=8),
        font=dict(family="Manrope, sans-serif", color=COLOR_TEXT),
    )
    return fig
