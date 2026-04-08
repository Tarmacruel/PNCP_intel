from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import plotly.io as pio
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _format_currency(value: float | int | None) -> str:
    numeric = float(value or 0)
    formatted = f"{numeric:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _format_integer(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "0"
    return f"{int(value):,}".replace(",", ".")


def _safe_text(value: Any, fallback: str = "Nao informado") -> str:
    if value is None:
        return fallback
    text = " ".join(str(value).split())
    return text or fallback


class PDFReportGenerator:
    def __init__(self) -> None:
        styles = getSampleStyleSheet()
        self.styles = {
            "title": ParagraphStyle(
                "ReportTitle",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=28,
                leading=32,
                textColor=colors.white,
                alignment=TA_CENTER,
                spaceAfter=18,
            ),
            "subtitle": ParagraphStyle(
                "ReportSubtitle",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=11,
                leading=16,
                textColor=colors.white,
                alignment=TA_CENTER,
            ),
            "section": ParagraphStyle(
                "SectionTitle",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=16,
                leading=20,
                textColor=colors.HexColor("#163348"),
                spaceAfter=10,
            ),
            "body": ParagraphStyle(
                "Body",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=10,
                leading=15,
                textColor=colors.HexColor("#233A4D"),
            ),
            "caption": ParagraphStyle(
                "Caption",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#5D7185"),
                alignment=TA_CENTER,
            ),
            "cover_label": ParagraphStyle(
                "CoverLabel",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=14,
                textColor=colors.white,
                alignment=TA_CENTER,
            ),
        }

    def generate_pdf(
        self,
        df: pd.DataFrame,
        *,
        meta: dict[str, Any],
        filter_summary: str,
        charts: dict[str, Any] | None = None,
        report_mode: str = "executive",
    ) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
            title="Dossie PNCP",
            author="PNCP Intelligence",
        )

        story: list[Any] = []
        story.extend(self._build_cover(df, meta))
        story.extend(self._build_summary(df, meta, filter_summary))
        story.extend(self._build_metric_cards(df))

        if charts:
            story.extend(self._build_chart_sections(charts))

        story.extend(self._build_top_organs_table(df))
        story.extend(self._build_yearly_table(df))
        story.extend(self._build_value_bands_table(df))

        if report_mode == "full":
            story.extend(self._build_contract_table(df))

        doc.build(
            story,
            onFirstPage=self._draw_cover_chrome,
            onLaterPages=self._draw_page_chrome,
        )
        buffer.seek(0)
        return buffer.read()

    def _build_cover(self, df: pd.DataFrame, meta: dict[str, Any]) -> list[Any]:
        supplier_name = _safe_text(meta.get("supplier_name", "Fornecedor consultado"))
        start_date = meta.get("requested_start_date")
        end_date = meta.get("requested_end_date")
        if start_date and end_date:
            period_label = f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        elif start_date:
            period_label = f"A partir de {start_date.strftime('%d/%m/%Y')}"
        elif end_date:
            period_label = f"Ate {end_date.strftime('%d/%m/%Y')}"
        else:
            period_label = "Todo o historico indexado"

        cover_box = Table(
            [
                [Paragraph("PNCP Intelligence", self.styles["title"])],
                [Paragraph("Dossie executivo de contratos publicos", self.styles["subtitle"])],
                [Spacer(1, 0.35 * cm)],
                [Paragraph(supplier_name, self.styles["cover_label"])],
                [Paragraph(_safe_text(meta.get("cnpj", "-")), self.styles["cover_label"])],
                [Paragraph(period_label, self.styles["subtitle"])],
                [Paragraph(_safe_text(meta.get("fetched_at", "-")), self.styles["subtitle"])],
            ],
            colWidths=[17.5 * cm],
        )
        cover_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#163348")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#163348")),
                    ("ROUNDEDCORNERS", [18, 18, 18, 18]),
                    ("TOPPADDING", (0, 0), (-1, -1), 18),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                    ("LEFTPADDING", (0, 0), (-1, -1), 24),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 24),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        return [Spacer(1, 5.5 * cm), cover_box, PageBreak()]

    def _build_summary(self, df: pd.DataFrame, meta: dict[str, Any], filter_summary: str) -> list[Any]:
        total_records = meta.get("total_records", len(df))
        retrieved_records = meta.get("retrieved_records", len(df))
        strategy = meta.get("search_strategy", "janela_unica")
        strategy_label = "Cobertura bidirecional do indice" if strategy == "janela_dupla" else "Janela unica do indice"
        partial_note = ""
        if meta.get("is_partial", False):
            partial_note = (
                f"A recuperacao da base foi parcial: {retrieved_records} de {total_records} contratos retornaram "
                "na janela publica disponivel."
            )

        summary_text = (
            f"<b>Fornecedor:</b> {_safe_text(meta.get('supplier_name'))}<br/>"
            f"<b>CNPJ:</b> {_safe_text(meta.get('cnpj'))}<br/>"
            f"<b>Contratos indexados:</b> {_format_integer(total_records)}<br/>"
            f"<b>Contratos recuperados:</b> {_format_integer(retrieved_records)}<br/>"
            f"<b>Estrategia:</b> {strategy_label}<br/>"
            f"<b>Filtros aplicados:</b> {_safe_text(filter_summary)}"
        )
        if partial_note:
            summary_text += f"<br/><b>Observacao:</b> {partial_note}"

        return [
            Paragraph("Resumo executivo", self.styles["section"]),
            Paragraph(summary_text, self.styles["body"]),
            Spacer(1, 0.35 * cm),
        ]

    def _build_metric_cards(self, df: pd.DataFrame) -> list[Any]:
        total_contracts = len(df)
        total_value = float(df["valor_global"].sum())
        average_value = float(df["valor_global"].mean()) if total_contracts else 0.0
        total_organs = int(df["orgao_nome"].nunique())

        metrics = [
            ("Contratos", _format_integer(total_contracts)),
            ("Valor total", _format_currency(total_value)),
            ("Valor medio", _format_currency(average_value)),
            ("Orgaos", _format_integer(total_organs)),
        ]

        metric_cells = []
        for label, value in metrics:
            metric_table = Table(
                [
                    [Paragraph(label, self.styles["caption"])],
                    [Paragraph(f"<b>{value}</b>", self.styles["body"])],
                ],
                colWidths=[4.15 * cm],
            )
            metric_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6FAFD")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D7E4EE")),
                        ("ROUNDEDCORNERS", [12, 12, 12, 12]),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            metric_cells.append(metric_table)

        metrics_table = Table([metric_cells], colWidths=[4.15 * cm] * 4)
        metrics_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return [metrics_table, Spacer(1, 0.45 * cm)]

    def _figure_to_image(self, fig: Any, *, width: float = 17.2 * cm, height: float = 8.8 * cm) -> Image | None:
        try:
            image_bytes = pio.to_image(fig, format="png", width=1200, height=650, scale=2)
        except Exception:
            return None

        buffer = BytesIO(image_bytes)
        image = Image(buffer, width=width, height=height)
        return image

    def _build_chart_sections(self, charts: dict[str, Any]) -> list[Any]:
        story: list[Any] = []
        sections = [
            ("Painel grafico", charts.get("top_orgs"), "Concentracao financeira por orgao contratante."),
            ("Linha temporal", charts.get("timeline"), "Volume e valor contratual ao longo do tempo."),
            ("Distribuicao de valor", charts.get("value_band"), "Concentracao da carteira por faixa de ticket."),
        ]

        for title, figure, caption in sections:
            if figure is None:
                continue
            image = self._figure_to_image(figure)
            if image is None:
                continue
            story.append(Paragraph(title, self.styles["section"]))
            story.append(image)
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph(caption, self.styles["caption"]))
            story.append(Spacer(1, 0.45 * cm))

        return story

    def _build_top_organs_table(self, df: pd.DataFrame) -> list[Any]:
        grouped = (
            df.groupby("orgao_nome", dropna=False)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
            .sort_values("valor_total", ascending=False)
            .head(12)
        )
        if grouped.empty:
            return []

        total_value = float(df["valor_global"].sum()) or 1.0
        rows = [["Orgao", "Qtd.", "Valor total", "% carteira"]]
        for _, row in grouped.iterrows():
            rows.append(
                [
                    _safe_text(row["orgao_nome"], "Nao informado")[:54],
                    _format_integer(row["quantidade"]),
                    _format_currency(row["valor_total"]),
                    f"{row['valor_total'] / total_value * 100:.1f}%",
                ]
            )

        return [
            Paragraph("Principais orgaos contratantes", self.styles["section"]),
            self._build_table(rows, [8.7 * cm, 2 * cm, 3.3 * cm, 2.2 * cm]),
            Spacer(1, 0.4 * cm),
        ]

    def _build_yearly_table(self, df: pd.DataFrame) -> list[Any]:
        grouped = (
            df.dropna(subset=["ano"])
            .groupby("ano")
            .agg(
                quantidade=("numero_controle_pncp", "count"),
                valor_total=("valor_global", "sum"),
                valor_medio=("valor_global", "mean"),
            )
            .reset_index()
            .sort_values("ano")
        )
        if grouped.empty:
            return []

        rows = [["Ano", "Qtd.", "Valor total", "Valor medio"]]
        for _, row in grouped.iterrows():
            rows.append(
                [
                    _format_integer(row["ano"]),
                    _format_integer(row["quantidade"]),
                    _format_currency(row["valor_total"]),
                    _format_currency(row["valor_medio"]),
                ]
            )

        return [
            Paragraph("Evolucao anual", self.styles["section"]),
            self._build_table(rows, [2.2 * cm, 2.2 * cm, 5.5 * cm, 5.5 * cm]),
            Spacer(1, 0.4 * cm),
        ]

    def _build_value_bands_table(self, df: pd.DataFrame) -> list[Any]:
        bands = pd.cut(
            df["valor_global"],
            bins=[0, 50_000, 500_000, 1_000_000, 5_000_000, float("inf")],
            labels=[
                "Ate R$ 50 mil",
                "R$ 50 mil a 500 mil",
                "R$ 500 mil a 1 mi",
                "R$ 1 mi a 5 mi",
                "Acima de R$ 5 mi",
            ],
            include_lowest=True,
        )
        grouped = (
            df.assign(faixa=bands)
            .groupby("faixa", observed=True)
            .agg(quantidade=("numero_controle_pncp", "count"), valor_total=("valor_global", "sum"))
            .reset_index()
        )
        if grouped.empty:
            return []

        total_contracts = len(df) or 1
        total_value = float(df["valor_global"].sum()) or 1.0
        rows = [["Faixa", "Qtd.", "% qtd.", "Valor total", "% valor"]]
        for _, row in grouped.iterrows():
            rows.append(
                [
                    _safe_text(row["faixa"]),
                    _format_integer(row["quantidade"]),
                    f"{row['quantidade'] / total_contracts * 100:.1f}%",
                    _format_currency(row["valor_total"]),
                    f"{row['valor_total'] / total_value * 100:.1f}%",
                ]
            )

        return [
            Paragraph("Bandas de valor", self.styles["section"]),
            self._build_table(rows, [5.2 * cm, 2 * cm, 2.2 * cm, 4.8 * cm, 2.2 * cm]),
            Spacer(1, 0.4 * cm),
        ]

    def _build_contract_table(self, df: pd.DataFrame) -> list[Any]:
        sample_df = (
            df.sort_values("data_referencia", ascending=False)
            .head(40)
            .copy()
        )
        if sample_df.empty:
            return []

        rows = [["Numero PNCP", "Orgao", "Valor", "Data", "Situacao"]]
        for _, row in sample_df.iterrows():
            date_label = row["data_assinatura"].strftime("%d/%m/%Y") if pd.notna(row["data_assinatura"]) else "N/A"
            rows.append(
                [
                    _safe_text(row["numero_controle_pncp"])[:22],
                    _safe_text(row["orgao_nome"])[:40],
                    _format_currency(row["valor_global"]),
                    date_label,
                    _safe_text(row["situacao_nome"])[:18],
                ]
            )

        return [
            PageBreak(),
            Paragraph("Amostra detalhada de contratos", self.styles["section"]),
            Paragraph(
                "O relatorio completo inclui uma amostra operacional dos 40 contratos mais recentes apos os filtros ativos.",
                self.styles["body"],
            ),
            Spacer(1, 0.2 * cm),
            self._build_table(rows, [4.1 * cm, 6.7 * cm, 3.0 * cm, 2.0 * cm, 2.0 * cm], font_size=7.4),
        ]

    def _build_table(self, rows: list[list[str]], column_widths: list[float], *, font_size: float = 8.8) -> Table:
        table = Table(rows, colWidths=column_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163348")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), font_size),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFD")]),
                    ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#D9E4EC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _draw_cover_chrome(self, canvas, doc) -> None:  # noqa: ANN001
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#163348"))
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    def _draw_page_chrome(self, canvas, doc) -> None:  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5D7185"))
        canvas.drawString(1.6 * cm, A4[1] - 1.0 * cm, "PNCP Intelligence")
        canvas.drawRightString(A4[0] - 1.6 * cm, 1.0 * cm, f"Pagina {doc.page}")
        canvas.restoreState()


pdf_generator = PDFReportGenerator()
