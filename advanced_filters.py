from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


PRESET_STORE_KEY = "advanced_filter_presets"
PREFIX = "adv_filter_"


def _state_key(name: str) -> str:
    return f"{PREFIX}{name}"


def _sanitize_multi_state(name: str, options: list[str]) -> None:
    current = st.session_state.get(_state_key(name), [])
    st.session_state[_state_key(name)] = [value for value in current if value in options]


def _format_currency_short(value: float) -> str:
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi"
    if value >= 1_000:
        return f"R$ {value / 1_000:.0f} mil"
    return f"R$ {value:,.0f}".replace(",", ".")


@dataclass
class AdvancedFilters:
    original_df: pd.DataFrame
    filtered_df: pd.DataFrame
    active_filters: dict[str, Any]

    def summary_text(self) -> str:
        if not self.active_filters:
            return "Sem filtros avançados ativos."

        summary_parts: list[str] = []

        if search_text := self.active_filters.get("search_text"):
            summary_parts.append(f"Texto: '{search_text}'")

        if ufs := self.active_filters.get("ufs"):
            summary_parts.append(f"UFs: {len(ufs)}")

        if esferas := self.active_filters.get("esferas"):
            summary_parts.append(f"Esferas: {len(esferas)}")

        if modalidades := self.active_filters.get("modalidades"):
            summary_parts.append(f"Modalidades: {len(modalidades)}")

        if tipos := self.active_filters.get("tipos"):
            summary_parts.append(f"Tipos: {len(tipos)}")

        if valor_range := self.active_filters.get("valor_range"):
            summary_parts.append(
                f"Faixa: {_format_currency_short(valor_range[0])} a {_format_currency_short(valor_range[1])}"
            )

        if ticket_band := self.active_filters.get("ticket_band"):
            summary_parts.append(f"Ticket: {ticket_band}")

        if quick_preset := self.active_filters.get("quick_preset"):
            summary_parts.append(f"Preset rapido: {quick_preset}")

        return " | ".join(summary_parts)

    def save_current_preset(self, name: str) -> None:
        presets = st.session_state.setdefault(PRESET_STORE_KEY, {})
        presets[name] = self.active_filters.copy()


def _reset_filter_state() -> None:
    for key in [
        "search_text",
        "ufs",
        "esferas",
        "modalidades",
        "tipos",
        "ticket_band",
        "quick_preset",
        "preset_name",
        "preset_to_load",
    ]:
        st.session_state[_state_key(key)] = [] if key in {"ufs", "esferas", "modalidades", "tipos"} else ""

    if _state_key("valor_range") in st.session_state:
        del st.session_state[_state_key("valor_range")]


def _apply_saved_preset(name: str, max_value: float) -> None:
    presets = st.session_state.get(PRESET_STORE_KEY, {})
    preset = presets.get(name)
    if not preset:
        return

    st.session_state[_state_key("search_text")] = preset.get("search_text", "")
    st.session_state[_state_key("ufs")] = preset.get("ufs", [])
    st.session_state[_state_key("esferas")] = preset.get("esferas", [])
    st.session_state[_state_key("modalidades")] = preset.get("modalidades", [])
    st.session_state[_state_key("tipos")] = preset.get("tipos", [])
    st.session_state[_state_key("ticket_band")] = preset.get("ticket_band", "Todos")
    st.session_state[_state_key("quick_preset")] = preset.get("quick_preset", "")
    st.session_state[_state_key("valor_range")] = preset.get("valor_range", (0.0, float(max_value)))


def _build_active_filters(df: pd.DataFrame) -> dict[str, Any]:
    max_value = float(df["valor_global"].max()) if not df.empty else 0.0
    default_range = (0.0, max_value)

    value_range = st.session_state.get(_state_key("valor_range"), default_range)
    active_filters: dict[str, Any] = {}

    if search_text := st.session_state.get(_state_key("search_text"), "").strip():
        active_filters["search_text"] = search_text

    if ufs := st.session_state.get(_state_key("ufs"), []):
        active_filters["ufs"] = ufs

    if esferas := st.session_state.get(_state_key("esferas"), []):
        active_filters["esferas"] = esferas

    if modalidades := st.session_state.get(_state_key("modalidades"), []):
        active_filters["modalidades"] = modalidades

    if tipos := st.session_state.get(_state_key("tipos"), []):
        active_filters["tipos"] = tipos

    if (
        value_range
        and max_value > 0
        and (float(value_range[0]) > default_range[0] or float(value_range[1]) < default_range[1])
    ):
        active_filters["valor_range"] = (float(value_range[0]), float(value_range[1]))

    ticket_band = st.session_state.get(_state_key("ticket_band"), "Todos")
    if ticket_band and ticket_band != "Todos":
        active_filters["ticket_band"] = ticket_band

    quick_preset = st.session_state.get(_state_key("quick_preset"), "")
    if quick_preset:
        active_filters["quick_preset"] = quick_preset

    return active_filters


def _apply_filters(df: pd.DataFrame, active_filters: dict[str, Any]) -> pd.DataFrame:
    filtered = df.copy()

    if search_text := active_filters.get("search_text"):
        search = str(search_text).lower()
        filtered = filtered[
            filtered["objeto"].fillna("").str.lower().str.contains(search)
            | filtered["titulo"].fillna("").str.lower().str.contains(search)
            | filtered["numero_controle_pncp"].fillna("").str.lower().str.contains(search)
        ]

    if ufs := active_filters.get("ufs"):
        filtered = filtered[filtered["uf"].isin(ufs)]

    if esferas := active_filters.get("esferas"):
        filtered = filtered[filtered["esfera_nome"].isin(esferas)]

    if modalidades := active_filters.get("modalidades"):
        filtered = filtered[filtered["modalidade_licitacao_nome"].isin(modalidades)]

    if tipos := active_filters.get("tipos"):
        filtered = filtered[filtered["tipo_contrato_nome"].isin(tipos)]

    if value_range := active_filters.get("valor_range"):
        filtered = filtered[
            (filtered["valor_global"] >= float(value_range[0])) & (filtered["valor_global"] <= float(value_range[1]))
        ]

    if ticket_band := active_filters.get("ticket_band"):
        ticket_rules = {
            "Ate R$ 10 mil": (0, 10_000),
            "R$ 10 mil a 100 mil": (10_000, 100_000),
            "R$ 100 mil a 1 mi": (100_000, 1_000_000),
            "Acima de R$ 1 mi": (1_000_000, float("inf")),
        }
        lower, upper = ticket_rules.get(ticket_band, (0, float("inf")))
        filtered = filtered[(filtered["valor_global"] >= lower) & (filtered["valor_global"] < upper)]

    if quick_preset := active_filters.get("quick_preset"):
        if quick_preset == "Maiores contratos":
            filtered = filtered.nlargest(min(50, len(filtered)), "valor_global")
        elif quick_preset == "Mais recentes":
            filtered = filtered.sort_values("data_referencia", ascending=False).head(min(50, len(filtered)))
        elif quick_preset == "Ultimos 12 meses":
            recent_cutoff = pd.Timestamp(datetime.now()) - pd.DateOffset(months=12)
            filtered = filtered[filtered["data_referencia"] >= recent_cutoff]

    return filtered


def apply_advanced_filters(df: pd.DataFrame) -> AdvancedFilters:
    if df.empty:
        return AdvancedFilters(original_df=df, filtered_df=df, active_filters={})

    max_value = float(df["valor_global"].max())
    current_range = st.session_state.get(_state_key("valor_range"), (0.0, max_value))
    safe_min = max(0.0, min(float(current_range[0]), max_value))
    safe_max = max(safe_min, min(float(current_range[1]), max_value))

    st.session_state.setdefault(_state_key("ticket_band"), "Todos")
    st.session_state.setdefault(_state_key("quick_preset"), "")
    st.session_state.setdefault(_state_key("preset_name"), "")
    st.session_state.setdefault(_state_key("preset_to_load"), "")
    st.session_state[_state_key("valor_range")] = (safe_min, safe_max)

    uf_options = sorted([value for value in df["uf"].dropna().unique().tolist() if value and value != "N/A"])
    esfera_options = sorted([value for value in df["esfera_nome"].dropna().unique().tolist() if value])
    modalidade_options = sorted([value for value in df["modalidade_licitacao_nome"].dropna().unique().tolist() if value])
    tipo_options = sorted([value for value in df["tipo_contrato_nome"].dropna().unique().tolist() if value])

    _sanitize_multi_state("ufs", uf_options)
    _sanitize_multi_state("esferas", esfera_options)
    _sanitize_multi_state("modalidades", modalidade_options)
    _sanitize_multi_state("tipos", tipo_options)

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Filtros Avancados")
        st.caption("Refinos laterais para texto, faixa de valor, geografia, modalidade e presets operacionais.")

        action_col_1, action_col_2 = st.columns(2)
        with action_col_1:
            if st.button("Limpar filtros", use_container_width=True, key=_state_key("reset_button")):
                _reset_filter_state()
                st.rerun()
        with action_col_2:
            if st.button("Top 50", use_container_width=True, key=_state_key("top50_button")):
                st.session_state[_state_key("quick_preset")] = "Maiores contratos"
                st.rerun()

        st.text_input(
            "Busca textual",
            key=_state_key("search_text"),
            placeholder="Objeto, titulo ou numero PNCP",
            help="Busca direta em objeto, titulo e numero de controle.",
        )

        if uf_options:
            st.multiselect("UF", uf_options, key=_state_key("ufs"))

        if esfera_options:
            st.multiselect("Esfera", esfera_options, key=_state_key("esferas"))

        if modalidade_options:
            st.multiselect("Modalidade", modalidade_options, key=_state_key("modalidades"))

        if tipo_options:
            st.multiselect("Tipo contratual", tipo_options, key=_state_key("tipos"))

        st.slider(
            "Faixa de valor (R$)",
            min_value=0.0,
            max_value=float(max_value),
            key=_state_key("valor_range"),
        )

        st.selectbox(
            "Faixa de ticket",
            ["Todos", "Ate R$ 10 mil", "R$ 10 mil a 100 mil", "R$ 100 mil a 1 mi", "Acima de R$ 1 mi"],
            key=_state_key("ticket_band"),
        )

        quick_col_1, quick_col_2 = st.columns(2)
        with quick_col_1:
            if st.button("Recentes", use_container_width=True, key=_state_key("recent_button")):
                st.session_state[_state_key("quick_preset")] = "Mais recentes"
                st.rerun()
        with quick_col_2:
            if st.button("12 meses", use_container_width=True, key=_state_key("12m_button")):
                st.session_state[_state_key("quick_preset")] = "Ultimos 12 meses"
                st.rerun()

        if st.button("Sem preset", use_container_width=True, key=_state_key("clear_preset_button")):
            st.session_state[_state_key("quick_preset")] = ""
            st.rerun()

        st.markdown("#### Presets salvos")
        st.text_input("Nome do preset", key=_state_key("preset_name"), placeholder="Ex.: auditoria hospitais")
        if st.button("Salvar preset atual", use_container_width=True, key=_state_key("save_preset_button")):
            preset_name = st.session_state.get(_state_key("preset_name"), "").strip()
            if preset_name:
                active_filters_to_save = _build_active_filters(df)
                st.session_state.setdefault(PRESET_STORE_KEY, {})[preset_name] = active_filters_to_save
                st.success(f"Preset '{preset_name}' salvo.")
            else:
                st.warning("Informe um nome antes de salvar o preset.")

        preset_names = sorted(st.session_state.get(PRESET_STORE_KEY, {}).keys())
        if preset_names:
            st.selectbox("Carregar preset", [""] + preset_names, key=_state_key("preset_to_load"))
            if st.button("Aplicar preset salvo", use_container_width=True, key=_state_key("load_preset_button")):
                selected_preset = st.session_state.get(_state_key("preset_to_load"), "")
                if selected_preset:
                    _apply_saved_preset(selected_preset, max_value=max_value)
                    st.rerun()

    active_filters = _build_active_filters(df)
    filtered_df = _apply_filters(df, active_filters)
    return AdvancedFilters(original_df=df, filtered_df=filtered_df, active_filters=active_filters)
