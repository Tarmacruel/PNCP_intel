from __future__ import annotations

from collections.abc import Sequence
from html import escape

import pandas as pd
import streamlit as st


PLOTLY_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
}


def badge_html(text: str, variant: str = "primary") -> str:
    return f'<span class="ui-badge ui-badge-{escape(variant, quote=True)}">{escape(str(text))}</span>'


def metric_card(
    label: str,
    value: str,
    *,
    icon: str = "■",
    delta: str | None = None,
    delta_type: str | None = None,
) -> None:
    delta_class = f"ui-delta ui-delta-{delta_type}" if delta_type else "ui-delta"
    delta_html = f'<div class="{delta_class}">{escape(delta)}</div>' if delta else ""

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-icon">{escape(icon)}</div>
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value">{escape(value)}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None, *, icon: str | None = None) -> None:
    icon_html = f'<span class="section-icon">{escape(icon)}</span>' if icon else ""
    subtitle_html = f'<p class="section-copy">{escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="section-block">
            <div class="section-title-row">
                {icon_html}
                <h3 class="section-heading">{escape(title)}</h3>
            </div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_wrapper(fig, title: str, description: str | None = None, *, icon: str | None = None) -> None:
    section_header(title, description, icon=icon)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def alert(kind: str, message: str, *, icon: str | None = None) -> None:
    default_icons = {
        "info": "i",
        "warning": "!",
        "success": "+",
        "error": "x",
    }
    icon_value = icon or default_icons.get(kind, "i")
    st.markdown(
        f"""
        <div class="ui-alert ui-alert-{kind}">
            <span class="ui-alert-icon">{escape(icon_value)}</span>
            <span class="ui-alert-text">{escape(message)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(
    *,
    icon: str,
    title: str,
    message: str,
    badges: Sequence[str] | None = None,
) -> None:
    badges_html = ""
    if badges:
        badges_html = '<div class="pill-row">' + "".join(
            badge_html(item, "primary") for item in badges
        ) + "</div>"

    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-state-icon">{escape(icon)}</div>
            <h3>{escape(title)}</h3>
            <p>{escape(message)}</p>
            {badges_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_loading_skeleton(card_count: int = 4) -> None:
    cards = "".join('<div class="ui-skeleton-card"></div>' for _ in range(card_count))
    st.markdown(
        f"""
        <div class="ui-skeleton-grid">{cards}</div>
        <div class="ui-skeleton-chart"></div>
        """,
        unsafe_allow_html=True,
    )


def paginated_table(df: pd.DataFrame, *, key: str, rows_per_page: int = 25) -> pd.DataFrame:
    if df.empty:
        return df

    total_rows = len(df)
    total_pages = max(1, (total_rows + rows_per_page - 1) // rows_per_page)
    toolbar_col_1, toolbar_col_2 = st.columns([1, 3])

    with toolbar_col_1:
        page = st.number_input(
            "Pagina",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key=f"{key}_page",
            label_visibility="collapsed",
        )

    with toolbar_col_2:
        st.markdown(
            f"""
            <div class="table-toolbar">
                <span>{badge_html(f"{total_rows} registros", "primary")}</span>
                <span>{badge_html(f"Pagina {page} de {total_pages}", "success")}</span>
                <span>{badge_html(f"{rows_per_page} por pagina", "warning")}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    start_idx = (page - 1) * rows_per_page
    end_idx = min(start_idx + rows_per_page, total_rows)
    return df.iloc[start_idx:end_idx]


def context_strip(title: str, subtitle: str, items: Sequence[str]) -> None:
    """Render compact, scannable context above a data workspace."""

    items_html = "".join(f'<span class="context-item">{escape(str(item))}</span>' for item in items if item)
    st.markdown(
        f"""
        <section class="context-strip">
            <div>
                <p class="context-kicker">BASE ATIVA</p>
                <h2>{escape(title)}</h2>
                <p>{escape(subtitle)}</p>
            </div>
            <div class="context-items">{items_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def footer_block(*, repo_url: str, timestamp: str) -> None:
    st.markdown(
        f"""
        <div class="footer-shell">
            <p><strong>PNCP Intelligence</strong> • Dados publicos do Portal Nacional de Contratacoes Publicas</p>
            <p>
                Ultima atualizacao: {escape(timestamp)} •
                <a href="https://pncp.gov.br/api/consulta/swagger-ui/index.html" target="_blank">API</a> •
                <a href="{escape(repo_url, quote=True)}" target="_blank">Codigo</a>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
