from __future__ import annotations

from dataclasses import dataclass
from html import escape
from io import BytesIO
from typing import Any, Sequence

import pandas as pd
import plotly.io as pio
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BRAND_NAVY = "#12344D"
BRAND_GOLD = "#C68432"
TEXT = "#163348"
MUTED = "#5D7185"
LINE = "#D7E4EE"
SURFACE = "#F6FAFD"


@dataclass(frozen=True)
class ChartSection:
    """A chart and the factual context that must travel with it in a report."""

    title: str
    caption: str
    figure: Any


def _format_currency(value: float | int | None) -> str:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        numeric = 0.0
    formatted = f"{numeric:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_integer(value: float | int | None) -> str:
    if value is None:
        return "0"
    try:
        if pd.isna(value):
            return "0"
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _plain_text(value: Any, fallback: str = "Não informado") -> str:
    """Normalize values from the public API before using them in a PDF."""

    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(_plain_text(item, "") for item in value if _plain_text(item, ""))
    elif isinstance(value, dict):
        value = ", ".join(f"{key}: {_plain_text(item, '')}" for key, item in value.items())
    text = " ".join(str(value).split())
    return text or fallback


def _pdf_text(value: Any, fallback: str = "Não informado") -> str:
    """Return external content safe for ReportLab's mini-markup parser."""

    return escape(_plain_text(value, fallback), quote=False)


def _numeric_series(df: pd.DataFrame, column_name: str) -> pd.Series:
    if column_name not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column_name], errors="coerce").fillna(0.0)


class _NumberedCanvas(canvas.Canvas):
    """Render page x of y after the document has been fully built."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:  # noqa: N802
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.saveState()
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor(MUTED))
                self.drawRightString(A4[0] - 1.6 * cm, 0.8 * cm, f"Página {self._pageNumber} de {page_count}")
                self.restoreState()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


class PDFReportGenerator:
    """Generate a concise, auditable PNCP report without trusting source markup."""

    def __init__(self) -> None:
        styles = getSampleStyleSheet()
        self.styles = {
            "title": ParagraphStyle(
                "ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=28,
                leading=32, textColor=colors.white, alignment=TA_CENTER, spaceAfter=14,
            ),
            "subtitle": ParagraphStyle(
                "ReportSubtitle", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5,
                leading=15, textColor=colors.white, alignment=TA_CENTER,
            ),
            "section": ParagraphStyle(
                "SectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15,
                leading=20, textColor=colors.HexColor(TEXT), spaceBefore=4, spaceAfter=9,
            ),
            "body": ParagraphStyle(
                "Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5,
                leading=14, textColor=colors.HexColor("#233A4D"),
            ),
            "caption": ParagraphStyle(
                "Caption", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.2,
                leading=11, textColor=colors.HexColor(MUTED), alignment=TA_CENTER,
            ),
            "cover_label": ParagraphStyle(
                "CoverLabel", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.5,
                leading=14, textColor=colors.white, alignment=TA_CENTER,
            ),
            "table_header": ParagraphStyle(
                "TableHeader", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.5,
                leading=9.5, textColor=colors.white, alignment=TA_LEFT,
            ),
            "table_cell": ParagraphStyle(
                "TableCell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.5,
                leading=9.5, textColor=colors.HexColor(TEXT), alignment=TA_LEFT,
            ),
            "finding": ParagraphStyle(
                "Finding", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2,
                leading=13.4, textColor=colors.HexColor(TEXT), leftIndent=8,
            ),
        }

    def generate_pdf(
        self,
        df: pd.DataFrame,
        *,
        meta: dict[str, Any],
        filter_summary: str,
        charts: Sequence[ChartSection] | None = None,
        report_mode: str = "executive",
    ) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
            topMargin=1.7 * cm, bottomMargin=1.45 * cm, title="Dossiê PNCP", author="PNCP Intelligence",
        )
        story: list[Any] = []
        story.extend(self._build_cover(meta, report_mode))
        story.extend(self._build_summary(df, meta, filter_summary))
        story.extend(self._build_metric_cards(df, meta))
        story.extend(self._build_findings(df, meta))
        if charts:
            story.extend(self._build_chart_sections(charts))
        story.extend(self._build_primary_ranking_table(df, meta))
        story.extend(self._build_yearly_table(df))
        story.extend(self._build_value_bands_table(df))
        story.extend(self._build_methodology(meta))
        if report_mode == "detail":
            story.extend(self._build_detail_table(df, meta))
        doc.build(
            story, onFirstPage=self._draw_cover_chrome, onLaterPages=self._draw_page_chrome,
            canvasmaker=_NumberedCanvas,
        )
        buffer.seek(0)
        return buffer.read()

    def _build_cover(self, meta: dict[str, Any], report_mode: str) -> list[Any]:
        query_scope = meta.get("query_scope", "supplier")
        entity_name = _plain_text(
            meta.get("organ_name", "Órgão público consultado")
            if query_scope == "organ"
            else meta.get("supplier_name", "Fornecedor consultado")
        )
        report_label = "Relatório executivo" if report_mode == "executive" else "Relatório detalhado — amostra"
        if query_scope == "organ":
            period_label = f"Faixa anual: {meta.get('start_year', '-')} a {meta.get('end_year', '-')}"
            subtitle = "Panorama de órgão público"
        else:
            start_date = meta.get("requested_start_date")
            end_date = meta.get("requested_end_date")
            if start_date and end_date:
                period_label = f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
            elif start_date:
                period_label = f"A partir de {start_date.strftime('%d/%m/%Y')}"
            elif end_date:
                period_label = f"Até {end_date.strftime('%d/%m/%Y')}"
            else:
                period_label = "Todo o histórico indexado"
            subtitle = "Dossiê de contratos públicos"
        cover_box = Table(
            [
                [Paragraph("PNCP Intelligence", self.styles["title"])],
                [Paragraph(report_label, self.styles["subtitle"])],
                [Spacer(1, 0.35 * cm)],
                [Paragraph(_pdf_text(subtitle), self.styles["cover_label"])],
                [Paragraph(_pdf_text(entity_name), self.styles["cover_label"])],
                [Paragraph(_pdf_text(meta.get("cnpj", "-")), self.styles["cover_label"])],
                [Paragraph(_pdf_text(period_label), self.styles["subtitle"])],
                [Paragraph(_pdf_text(meta.get("report_generated_at", meta.get("fetched_at", "-"))), self.styles["subtitle"])],
            ],
            colWidths=[17.5 * cm],
        )
        cover_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BRAND_NAVY)),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(BRAND_NAVY)),
            ("ROUNDEDCORNERS", [18, 18, 18, 18]),
            ("TOPPADDING", (0, 0), (-1, -1), 18), ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
            ("LEFTPADDING", (0, 0), (-1, -1), 24), ("RIGHTPADDING", (0, 0), (-1, -1), 24),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        return [Spacer(1, 5.1 * cm), cover_box, PageBreak()]

    def _build_summary(self, df: pd.DataFrame, meta: dict[str, Any], filter_summary: str) -> list[Any]:
        query_scope = meta.get("query_scope", "supplier")
        total_records = meta.get("total_records", len(df))
        retrieved_records = meta.get("retrieved_records", len(df))
        strategy_label = (
            "Cobertura bidirecional do índice" if meta.get("search_strategy") == "janela_dupla"
            else "Janela única do índice"
        )
        if query_scope == "organ":
            summary_text = (
                f"<b>Órgão:</b> {_pdf_text(meta.get('organ_name'))}<br/>"
                f"<b>CNPJ:</b> {_pdf_text(meta.get('cnpj', '-'))}<br/>"
                f"<b>Faixa anual:</b> {_pdf_text(meta.get('start_year', '-'))} a {_pdf_text(meta.get('end_year', '-'))}<br/>"
                f"<b>Registros recuperados:</b> {_format_integer(retrieved_records)} de {_format_integer(total_records)}<br/>"
                f"<b>Base exata no recorte:</b> {_format_integer(meta.get('exact_records', len(df)))}<br/>"
                f"<b>Estratégia:</b> {strategy_label}<br/>"
                f"<b>Enriquecimento:</b> {_pdf_text(meta.get('enrichment_status', 'Consulta consolidada'))}<br/>"
                f"<b>Filtros efetivos:</b> {_pdf_text(filter_summary, 'Sem filtros ativos')}"
            )
        else:
            summary_text = (
                f"<b>Fornecedor:</b> {_pdf_text(meta.get('supplier_name'))}<br/>"
                f"<b>CNPJ:</b> {_pdf_text(meta.get('cnpj', '-'))}<br/>"
                f"<b>Contratos recuperados:</b> {_format_integer(retrieved_records)} de {_format_integer(total_records)}<br/>"
                f"<b>Estratégia:</b> {strategy_label}<br/>"
                f"<b>Filtros efetivos:</b> {_pdf_text(filter_summary, 'Sem filtros ativos')}"
            )
        if meta.get("is_partial", False):
            summary_text += (
                "<br/><b>Atenção de cobertura:</b> a busca excede a janela pública disponível. "
                "Reduza o recorte antes de usar a base como auditoria integral."
            )
        return [
            Paragraph("Resumo executivo", self.styles["section"]),
            Paragraph(summary_text, self.styles["body"]),
            Spacer(1, 0.35 * cm),
        ]

    def _build_metric_cards(self, df: pd.DataFrame, meta: dict[str, Any]) -> list[Any]:
        query_scope = meta.get("query_scope", "supplier")
        values = _numeric_series(df, "valor_global")
        total_records = len(df)
        if query_scope == "organ":
            suppliers = df.get("fornecedor_nome", pd.Series(dtype="object"))
            units = df.get("unidade_nome", pd.Series(dtype="object"))
            metrics = [
                ("Registros", _format_integer(total_records)),
                ("Valor total", _format_currency(values.sum())),
                ("Fornecedores", _format_integer(suppliers.replace(["Não informado", "Não se aplica"], pd.NA).dropna().nunique())),
                ("Unidades", _format_integer(units.dropna().nunique())),
            ]
        else:
            organs = df.get("orgao_nome", pd.Series(dtype="object"))
            metrics = [
                ("Contratos", _format_integer(total_records)),
                ("Valor total", _format_currency(values.sum())),
                ("Ticket médio", _format_currency(values.mean() if total_records else 0)),
                ("Órgãos", _format_integer(organs.dropna().nunique())),
            ]
        metric_cells: list[Any] = []
        for label, value in metrics:
            metric_table = Table(
                [[Paragraph(label.upper(), self.styles["caption"])], [Paragraph(f"<b>{_pdf_text(value, '0')}</b>", self.styles["body"])]],
                colWidths=[4.15 * cm],
            )
            metric_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SURFACE)),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(LINE)),
                ("ROUNDEDCORNERS", [10, 10, 10, 10]),
                ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            metric_cells.append(metric_table)
        metrics_table = Table([metric_cells], colWidths=[4.15 * cm] * 4)
        metrics_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return [metrics_table, Spacer(1, 0.5 * cm)]

    def _build_findings(self, df: pd.DataFrame, meta: dict[str, Any]) -> list[Any]:
        if df.empty:
            return []
        query_scope = meta.get("query_scope", "supplier")
        entity_column = "fornecedor_nome" if query_scope == "organ" else "orgao_nome"
        entity_label = "fornecedor" if query_scope == "organ" else "órgão contratante"
        working = df.copy()
        working["_valor_relatorio"] = _numeric_series(df, "valor_global")
        values = working["_valor_relatorio"]
        findings: list[str] = []
        if entity_column in working.columns and float(values.sum()) != 0:
            ranking = working.groupby(entity_column, dropna=False)["_valor_relatorio"].sum().sort_values(ascending=False)
            if not ranking.empty:
                findings.append(
                    f"<b>Concentração:</b> {_pdf_text(ranking.index[0])} representa "
                    f"{float(ranking.iloc[0]) / float(values.sum()) * 100:.1f}% do valor do recorte como {entity_label} líder."
                )
        largest = working.loc[values.idxmax()]
        findings.append(
            f"<b>Maior registro:</b> {_format_currency(largest.get('_valor_relatorio'))} vinculado a "
            f"{_pdf_text(largest.get(entity_column, 'Não informado'))}."
        )
        years = _numeric_series(working, "ano").replace(0, pd.NA).dropna().nunique()
        findings.append(
            f"<b>Série histórica:</b> o recorte reúne dados de {_format_integer(years)} ano(s) de referência."
            if years else "<b>Série histórica:</b> há registros sem ano de referência consolidado no recorte."
        )
        rendered: list[Any] = [Paragraph("Achados para leitura", self.styles["section"])]
        for finding in findings[:3]:
            rendered.append(Paragraph(finding, self.styles["finding"]))
            rendered.append(Spacer(1, 0.12 * cm))
        rendered.append(Spacer(1, 0.18 * cm))
        return rendered

    def _figure_to_image(self, fig: Any, *, width: float = 17.2 * cm, height: float = 8.8 * cm) -> Image | None:
        try:
            image_bytes = pio.to_image(fig, format="png", width=1200, height=650, scale=2)
        except Exception:
            return None
        return Image(BytesIO(image_bytes), width=width, height=height)

    def _build_chart_sections(self, charts: Sequence[ChartSection]) -> list[Any]:
        story: list[Any] = []
        for section in charts:
            image = self._figure_to_image(section.figure)
            story.append(Paragraph(_pdf_text(section.title), self.styles["section"]))
            if image is None:
                story.append(Paragraph(
                    "O gráfico não pôde ser renderizado neste ambiente. Os indicadores e tabelas deste relatório permanecem válidos.",
                    self.styles["body"],
                ))
            else:
                story.append(image)
                story.append(Spacer(1, 0.15 * cm))
                story.append(Paragraph(_pdf_text(section.caption), self.styles["caption"]))
            story.append(Spacer(1, 0.42 * cm))
        return story

    def _build_primary_ranking_table(self, df: pd.DataFrame, meta: dict[str, Any]) -> list[Any]:
        if df.empty:
            return []
        query_scope = meta.get("query_scope", "supplier")
        working = df.copy()
        working["_valor_relatorio"] = _numeric_series(df, "valor_global")
        if query_scope == "organ":
            if "document_type" in working.columns:
                working = working[working["document_type"].eq("contrato")]
            name_column, title, first_column = "fornecedor_nome", "Principais fornecedores", "Fornecedor"
        else:
            name_column, title, first_column = "orgao_nome", "Principais órgãos contratantes", "Órgão"
        if working.empty or name_column not in working.columns:
            return []
        count_column = "numero_controle_pncp" if "numero_controle_pncp" in working.columns else name_column
        grouped = (
            working.groupby(name_column, dropna=False)
            .agg(quantidade=(count_column, "count"), valor_total=("_valor_relatorio", "sum"))
            .reset_index().sort_values("valor_total", ascending=False).head(12)
        )
        total_value = float(working["_valor_relatorio"].sum())
        rows = [[first_column, "Qtd.", "Valor total", "% do recorte"]]
        for _, row in grouped.iterrows():
            rows.append([
                _plain_text(row[name_column], "Não informado")[:70], _format_integer(row["quantidade"]),
                _format_currency(row["valor_total"]),
                "N/A" if total_value == 0 else f"{row['valor_total'] / total_value * 100:.1f}%",
            ])
        return [
            Paragraph(title, self.styles["section"]),
            self._build_table(rows, [8.4 * cm, 2 * cm, 3.5 * cm, 2.3 * cm]),
            Spacer(1, 0.42 * cm),
        ]

    def _build_yearly_table(self, df: pd.DataFrame) -> list[Any]:
        if df.empty or "ano" not in df.columns:
            return []
        working = df.copy()
        working["_valor_relatorio"] = _numeric_series(df, "valor_global")
        working["_ano_relatorio"] = pd.to_numeric(working["ano"], errors="coerce")
        count_column = "numero_controle_pncp" if "numero_controle_pncp" in working.columns else "_ano_relatorio"
        grouped = (
            working.dropna(subset=["_ano_relatorio"])
            .groupby("_ano_relatorio")
            .agg(quantidade=(count_column, "count"), valor_total=("_valor_relatorio", "sum"), valor_medio=("_valor_relatorio", "mean"))
            .reset_index().sort_values("_ano_relatorio")
        )
        if grouped.empty:
            return []
        rows = [["Ano", "Qtd.", "Valor total", "Ticket médio"]]
        for _, row in grouped.iterrows():
            rows.append([
                _format_integer(row["_ano_relatorio"]), _format_integer(row["quantidade"]),
                _format_currency(row["valor_total"]), _format_currency(row["valor_medio"]),
            ])
        return [
            Paragraph("Evolução anual", self.styles["section"]),
            self._build_table(rows, [2.2 * cm, 2.2 * cm, 5.5 * cm, 5.5 * cm]),
            Spacer(1, 0.42 * cm),
        ]

    def _build_value_bands_table(self, df: pd.DataFrame) -> list[Any]:
        if df.empty:
            return []
        values = _numeric_series(df, "valor_global")
        labels = pd.cut(
            values.clip(lower=0), bins=[0, 50_000, 500_000, 1_000_000, 5_000_000, float("inf")],
            labels=["Até R$ 50 mil", "R$ 50 mil a 500 mil", "R$ 500 mil a 1 mi", "R$ 1 mi a 5 mi", "Acima de R$ 5 mi"],
            include_lowest=True,
        ).astype("object")
        labels.loc[values < 0] = "Ajustes / negativos"
        count_column = "numero_controle_pncp" if "numero_controle_pncp" in df.columns else "_valor_relatorio"
        count_values = df[count_column] if count_column in df.columns else values
        grouped = (
            pd.DataFrame({"faixa": labels, "_valor_relatorio": values, "_contador": count_values})
            .groupby("faixa", dropna=False)
            .agg(quantidade=("_contador", "count"), valor_total=("_valor_relatorio", "sum"))
            .reset_index()
        )
        if grouped.empty:
            return []
        total_records, total_value = len(df), float(values.sum())
        rows = [["Faixa", "Qtd.", "% qtd.", "Valor total", "% valor"]]
        for _, row in grouped.iterrows():
            rows.append([
                _plain_text(row["faixa"], "Sem faixa"), _format_integer(row["quantidade"]),
                f"{row['quantidade'] / total_records * 100:.1f}%" if total_records else "N/A",
                _format_currency(row["valor_total"]),
                "N/A" if total_value == 0 else f"{row['valor_total'] / total_value * 100:.1f}%",
            ])
        return [
            Paragraph("Bandas de valor", self.styles["section"]),
            self._build_table(rows, [5.2 * cm, 2 * cm, 2.2 * cm, 4.8 * cm, 2.2 * cm]),
            Spacer(1, 0.42 * cm),
        ]

    def _build_methodology(self, meta: dict[str, Any]) -> list[Any]:
        body = (
            "<b>Fonte e método.</b> Dados públicos consultados no Portal Nacional de Contratações Públicas (PNCP). "
            "Os indicadores refletem apenas os registros recuperados e os filtros efetivos deste arquivo. "
            f"Fonte: {_pdf_text(meta.get('source_url', 'https://pncp.gov.br'))}. "
            f"Gerado em: {_pdf_text(meta.get('report_generated_at', meta.get('fetched_at', '-')))}. "
            f"Identificador do relatório: {_pdf_text(meta.get('report_id', '-'))}."
        )
        if meta.get("is_partial", False):
            body += " <b>Atenção:</b> a cobertura é parcial devido ao limite público de recuperação do índice."
        return [
            Paragraph("Proveniência e limites", self.styles["section"]),
            Paragraph(body, self.styles["body"]),
            Spacer(1, 0.42 * cm),
        ]

    def _build_detail_table(self, df: pd.DataFrame, meta: dict[str, Any]) -> list[Any]:
        if df.empty:
            return []
        query_scope = meta.get("query_scope", "supplier")
        try:
            sample_limit = max(1, min(int(meta.get("detail_sample_limit", 50)), 100))
        except (TypeError, ValueError):
            sample_limit = 50
        sample_df = df.copy()
        if "data_referencia" in sample_df.columns:
            sample_df = sample_df.sort_values("data_referencia", ascending=False, na_position="last")
        sample_df = sample_df.head(sample_limit)
        if query_scope == "organ":
            rows = [["Tipo", "Número PNCP", "Fornecedor", "Unidade", "Ano"]]
            for _, row in sample_df.iterrows():
                rows.append([
                    _plain_text(row.get("document_type_label"))[:22], _plain_text(row.get("numero_controle_pncp"))[:28],
                    _plain_text(row.get("fornecedor_nome"))[:50], _plain_text(row.get("unidade_nome"))[:44],
                    _format_integer(row.get("ano")),
                ])
            widths, title = [3.0 * cm, 4.1 * cm, 4.7 * cm, 4.3 * cm, 1.6 * cm], "Amostra detalhada de documentos"
        else:
            rows = [["Número PNCP", "Órgão", "Valor", "Data", "Situação"]]
            for _, row in sample_df.iterrows():
                date_value = pd.to_datetime(row.get("data_assinatura"), errors="coerce")
                rows.append([
                    _plain_text(row.get("numero_controle_pncp"))[:28], _plain_text(row.get("orgao_nome"))[:62],
                    _format_currency(row.get("valor_global")),
                    date_value.strftime("%d/%m/%Y") if pd.notna(date_value) else "N/A",
                    _plain_text(row.get("situacao_nome"))[:25],
                ])
            widths, title = [4.1 * cm, 6.7 * cm, 3.0 * cm, 2.0 * cm, 2.0 * cm], "Amostra detalhada de contratos"
        description = (
            f"Este anexo apresenta os {len(sample_df)} registros mais recentes dentre {len(df)} registros no recorte. "
            "Para a base integral, utilize a exportação Excel ou CSV."
        )
        return [
            PageBreak(), Paragraph(title, self.styles["section"]),
            Paragraph(_pdf_text(description), self.styles["body"]), Spacer(1, 0.2 * cm),
            self._build_table(rows, widths, font_size=7.2),
        ]

    def _build_table(self, rows: list[list[Any]], column_widths: list[float], *, font_size: float = 7.5) -> Table:
        cell_style = ParagraphStyle(
            f"TableCell{font_size}", parent=self.styles["table_cell"], fontSize=font_size, leading=font_size + 2.2,
        )
        header_style = ParagraphStyle(
            f"TableHeader{font_size}", parent=self.styles["table_header"], fontSize=font_size, leading=font_size + 2.2,
        )
        rendered_rows = [
            [Paragraph(_pdf_text(cell, ""), header_style if row_index == 0 else cell_style) for cell in row]
            for row_index, row in enumerate(rows)
        ]
        table = Table(rendered_rows, colWidths=column_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_NAVY)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFD")]),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor(LINE)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def _draw_cover_chrome(self, canvas_obj, doc) -> None:  # noqa: ANN001
        canvas_obj.saveState()
        canvas_obj.setFillColor(colors.HexColor(BRAND_NAVY))
        canvas_obj.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas_obj.setFillColor(colors.HexColor(BRAND_GOLD))
        canvas_obj.rect(0, 0, A4[0], 0.55 * cm, fill=1, stroke=0)
        canvas_obj.restoreState()

    def _draw_page_chrome(self, canvas_obj, doc) -> None:  # noqa: ANN001
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(colors.HexColor(LINE))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(1.5 * cm, A4[1] - 1.1 * cm, A4[0] - 1.5 * cm, A4[1] - 1.1 * cm)
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(colors.HexColor(BRAND_NAVY))
        canvas_obj.drawString(1.6 * cm, A4[1] - 0.8 * cm, "PNCP Intelligence")
        canvas_obj.restoreState()


pdf_generator = PDFReportGenerator()
