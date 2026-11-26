"""Readable PDF from an immutable report edition; no database or model calls."""

import hashlib
import io
import json
from html import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle

from gsreview.configuration import APP_ROOT


def archive_pdf(report):
    """Summarize saved evidence faithfully; full row-level data remains in JSON."""
    for name, filename in (("GSArchive", "DejaVuSans.ttf"), ("GSArchiveBold", "DejaVuSans-Bold.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(APP_ROOT / "assets/fonts" / filename)))
    pdfmetrics.registerFontFamily("GSArchive", normal="GSArchive", bold="GSArchiveBold",
                                  italic="GSArchive", boldItalic="GSArchiveBold")
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "GSArchiveBold" if style.name in {"Title", "Heading1", "Heading2"} else "GSArchive"
        if style.name == "Heading2":
            style.keepWithNext = True
    styles.add(ParagraphStyle(name="ArchiveCell", fontName="GSArchive", fontSize=7, leading=10,
                             splitLongWords=True, spaceAfter=0))
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 13
    story = []

    def paragraph(value, style="BodyText"):
        if value is None or isinstance(value, float) and pd.isna(value):
            value = "No disponible"
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])

    def section(title):
        story.extend([Spacer(1, 10), paragraph(title, "Heading2")])

    def table(headers, rows, widths=None):
        if not rows:
            story.append(paragraph("Sin resultados archivados en esta sección."))
            return
        cells = [[paragraph(cell, "ArchiveCell") for cell in row] for row in [headers]+rows]
        grid = LongTable(cells, colWidths=widths or [(A4[0]-80)/len(headers)]*len(headers),
                         repeatRows=1, hAlign="LEFT")
        grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1f5")),
            ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#c3d0d8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(grid)

    def text(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value

    payload = report["snapshot"]
    historical = payload.get("historical_export", {})
    story.extend([paragraph("GeoSlope Review", "Title"), paragraph("Reporte archivado", "Heading1")])
    metadata = {"Código": report["id"], "Versión": report["version"], "Versión anterior": report.get("parent") or "Inicial",
                "Fecha UTC": report["created_at"], "Especialista": payload["generated_by"]["display_name"],
                "Escenario": payload.get("saved_scenario_name", payload["scenario"]["id"]),
                "ID de escenario": payload.get("saved_scenario_id", payload["scenario"]["id"]),
                "Versión del escenario": payload.get("saved_scenario_revision", "Congelado" if historical else "No registrada"),
                "Sector": payload.get("sector", "No especificado"),
                "Datos SHA256": payload.get("data_version", historical.get("manifest_hash", "No registrado"))}
    table(["Identificación", "Valor archivado"], [[k, v] for k, v in metadata.items()], [120, A4[0]-200])
    section("Conclusiones del especialista")
    story.append(paragraph(report["conclusions"]))
    section("Observaciones del especialista")
    story.append(paragraph(report["specialist_notes"] or "Sin observaciones adicionales."))
    section("Procedencia y limitaciones")
    story.append(paragraph(text(payload.get("source_details") or payload["scenario"])))
    story.append(paragraph(payload["limitations"]))
    section("Resumen de datos")
    summary = payload.get("quality", historical.get("summary", {}))
    table(["Indicador", "Valor"], [[k, text(v)] for k, v in summary.items()], [180, A4[0]-260])
    section("Isolation Forest - resultados archivados")
    anomalies = pd.DataFrame(payload.get("anomalies", historical.get("records", [])))
    columns = ["Prisma", "Fecha archivada", "Score", "Evaluable", "Marca q99"]
    latest = []
    if not anomalies.empty:
        # Only observed, saved scores; sorting does not infer or fill missing values.
        anomalies = anomalies.sort_values("timestamp", kind="stable")
        for _, row in anomalies.groupby("prism_id", sort=True).tail(1).iterrows():
            latest.append([row.prism_id, row.timestamp, row.get("isolation_forest_score"),
                           row.get("model_eligible"), row.get("isolation_forest_marked_q99")])
    table(columns, latest, [80, 145, 100, 90, A4[0]-495])
    story.append(paragraph("Último registro archivado por prisma; no equivale a una clasificación de riesgo."))
    section("Pronóstico probabilístico archivado (mm)")
    predictions = payload.get("forecast", [])
    table(["Modelo", "Fecha archivada", "q10", "q50", "q90"],
          [[r.get(k) for k in ("model", "timestamp", "q10", "q50", "q90")] for r in predictions],
          [95, 165, 85, 85, A4[0]-510])
    section("Métricas de validación cronológica archivadas")
    table(["Modelo/fold", "Corte", "MAE (mm)", "RMSE (mm)", "Cobertura"],
          [[str(r.get("model"))+" / "+str(r.get("fold")), r.get("cutoff"), r.get("mae_mm"),
            r.get("rmse_mm"), r.get("interval_coverage")] for r in payload.get("forecast_metrics", [])],
          [100, 150, 90, 90, A4[0]-510])
    section("Versiones y trazabilidad de modelos")
    if "model_version" in anomalies:
        story.append(paragraph("Isolation Forest: "+text(sorted(anomalies.model_version.dropna().unique().tolist()))))
    for key in ("model_versions", "anomaly_trace", "forecast_trace"):
        if key in payload:
            story.append(paragraph(key+": "+text(payload[key])))
    if historical:
        story.append(paragraph("Política histórica archivada: "+text(historical["policy"])))
    section("Revisiones humanas archivadas")
    reviews = payload.get("human_reviews", [])
    if not reviews:
        story.append(paragraph("Sin revisiones humanas archivadas."))
    for review in reviews:
        story.append(paragraph(text(review)))
    section("Integridad de esta edición")
    digest = hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
    story.append(paragraph("SHA256 de la edición JSON canónica: "+digest))
    story.append(paragraph("Este PDF resume exclusivamente la edición archivada. Los registros completos, "
                           "valores ausentes y resultados originales están en su descarga JSON. "
                           "Consultar o exportar esta edición no ejecuta modelos de IA."))
    stream = io.BytesIO()

    def footer(canvas, doc):
        canvas.setFont("GSArchive", 8)
        canvas.drawString(40, 22, "GeoSlope Review - edición archivada "+report["id"][:12])
        canvas.drawRightString(A4[0]-40, 22, "Página "+str(doc.page))

    SimpleDocTemplate(stream, pagesize=A4, rightMargin=40, leftMargin=40,
                      topMargin=35, bottomMargin=40, title="GeoSlope Review - reporte archivado",
                      author=payload["generated_by"]["display_name"]).build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
