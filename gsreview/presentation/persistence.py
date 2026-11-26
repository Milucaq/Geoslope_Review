"""Explicit save/open actions and a durable report inbox."""

import json
import os
import uuid

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from gsreview.application.persistence import restore_state, STATE_KEYS
from gsreview.application.scenario_reports import report_payload, report_html, LIMITATIONS
from gsreview.infrastructure.archive_pdf import archive_pdf
from gsreview.domain.rules import ValidationError


def new_scenario(kind):
    for key in list(st.session_state):
        if key in STATE_KEYS or key.startswith(("scenario_", "science_", "jh_", "hu110_", "report_")):
            if key != "scenario_owner":
                del st.session_state[key]
    st.session_state.active_scenario = kind
    st.session_state.scenario_selector = kind


def open_scenario(c, token, object_id):
    restore_state(st.session_state, c.persistence.scenario(token, object_id))


def scenario_controls(c, token, active):
    with st.expander("Escenarios guardados · Nuevo / Guardar / Abrir"):
        if os.environ.get("RENDER"):
            st.warning("Render: la configuración actual usa almacenamiento temporal. Guardar en SQLite no garantiza "
                       "recuperación tras reinicios o despliegues. Conserva los backups fuera de esta instancia.")
        else:
            st.caption("Los guardados permanecen en el almacenamiento local de esta instalación.")
        items = c.persistence.listing(token, "scenario")
        latest = {item["id"]: item for item in items}
        if latest:
            chosen = st.selectbox("Abrir escenario existente", list(latest), format_func=lambda key: latest[key]["name"], key="saved_case_choice")
            st.button("Abrir escenario", on_click=open_scenario, args=(c, token, chosen), key="saved_case_open")
        if active.id != "historical":
            st.button("Nuevo escenario", on_click=new_scenario, args=(active.id,), key="saved_case_new")
            name = st.text_input("Nombre del escenario", key="scenario_name")
            if st.button("Guardar escenario", key="saved_case_save"):
                try:
                    snapshot = c.persistence.save_scenario(token, name, st.session_state)
                except (ValidationError, SQLAlchemyError, OSError, ValueError) as exc:
                    st.error(str(exc) if isinstance(exc, ValidationError) else "No se pudo guardar el escenario. Conserva el borrador e inténtalo nuevamente.")
                else:
                    st.session_state.scenario_saved_id = snapshot["id"]
                    st.session_state.scenario_saved_revision = snapshot["revision"]
                    st.success("Escenario guardado persistentemente · versión "+str(snapshot["revision"]))


def clear_report_form():
    for key in ("report_conclusions", "report_notes", "report_parent"):
        st.session_state.pop(key, None)
    st.session_state.report_request = uuid.uuid4().hex


def new_report_version(parent):
    clear_report_form()
    st.session_state.report_parent = parent
    st.session_state.report_tab = "Nuevo reporte"


def historical_snapshot(c, token):
    """Archive the existing verified export without running scientific models."""
    exported = json.loads(c.reports.generate(token, "general", "", "JSON"))
    actor = c.auth.authorize(token, "export")
    return {"scenario": {"id": "historical"}, "generated_by": {
        "actor_id": actor["id"], "display_name": actor["display_name"]},
        "human_reviews": exported["reviews"], "limitations": exported["notice"],
        "model_versions": {path: digest for path, digest in exported["artifacts"].items() if path.startswith("models/")},
        "historical_export": exported}


def reports(c, token, active, frame):
    st.title("Reporte del escenario" if active.id != "historical" else "Reportes y trazabilidad")
    destination = st.session_state.pop("report_next_tab", None)
    if destination:
        st.session_state.report_tab = destination
    new, history = st.tabs(["Nuevo reporte", "Historial de reportes"],
                           default="Nuevo reporte", key="report_tab", on_change="rerun")
    with new:
        if active.id != "historical" and frame is None:
            st.info("Abre un escenario guardado o prepara datos para un nuevo reporte.")
        else:
            st.caption("Resumen del análisis activo · "+active.label)
            if frame is not None:
                st.write("Prismas:", frame.prism_id.nunique(), "· Mediciones:", len(frame))
            else:
                st.caption("El archivo histórico conserva la referencia general congelada y sus revisiones actuales.")
            st.session_state.setdefault("report_request", uuid.uuid4().hex)
            if st.session_state.pop("report_clear", False):
                clear_report_form()
            with st.form("persistent_report_form"):
                conclusions = st.text_area("Conclusiones", key="report_conclusions", max_chars=6000)
                notes = st.text_area("Observaciones del especialista para el reporte", key="report_notes", max_chars=6000)
                if st.form_submit_button("Guardar reporte", type="primary"):
                    try:
                        if not conclusions.strip():
                            raise ValidationError("Las conclusiones son obligatorias.")
                        if active.id == "historical":
                            payload = historical_snapshot(c, token)
                        else:
                            working = dict(st.session_state)
                            working["active_scenario"] = active.id
                            working["jh_records" if active.id == "john_henry" else "scenario_external_frame"] = frame
                            scenario = c.persistence.save_scenario(token, working.get("scenario_name") or active.label, working)
                            st.session_state.scenario_saved_id = scenario["id"]
                            st.session_state.scenario_saved_revision = scenario["revision"]
                            payload = report_payload(c.auth, c.scenario_reviews, token, active.id, frame, st.session_state)
                            payload["saved_scenario_id"] = scenario["id"]
                            payload["saved_scenario_revision"] = scenario["revision"]
                            payload["saved_scenario_name"] = scenario["name"]
                            payload["sector"] = st.session_state.get("scenario_jh_settings", {}).get("sector")
                        saved = c.persistence.save_report(token, payload, conclusions, notes,
                            st.session_state.report_request, st.session_state.get("report_parent"))
                    except (ValidationError, SQLAlchemyError, OSError, ValueError) as exc:
                        st.error(str(exc) if isinstance(exc, ValidationError) else "No se pudo guardar el reporte. El borrador se conserva; inténtalo nuevamente.")
                    else:
                        st.session_state.report_selected = saved["id"]
                        st.session_state.report_clear = True
                        st.session_state.report_saved_notice = True
                        st.session_state.report_history_reset = True
                        st.session_state.report_next_tab = "Historial de reportes"
                        st.rerun()
            if active.id != "historical":
                st.info(LIMITATIONS)
                from gsreview.presentation.workflow import scientific_reference
                scientific_reference(c)
    with history:
        if st.session_state.pop("report_history_reset", False):
            for key in ("report_search", "report_after", "report_before", "report_history_selection",
                        "report_filter_Escenario", "report_filter_Prisma", "report_filter_Estado", "report_detail_id"):
                st.session_state.pop(key, None)
            st.session_state.report_history_selection = st.session_state.report_selected
        if st.session_state.pop("report_saved_notice", False):
            st.success("Transacción confirmada. Reporte guardado; formulario limpio.")
        items = c.persistence.listing(token, "report")
        query = st.text_input("Buscar escenario, prisma o estado", key="report_search").casefold()
        after = st.date_input("Desde fecha", value=None, key="report_after")
        before = st.date_input("Hasta fecha", value=None, key="report_before")
        rows = []
        for item in items:
            snapshot = item["snapshot"]
            review = snapshot["human_reviews"][-1] if snapshot["human_reviews"] else {}
            row = {"Código": item["id"], "Fecha": item["created_at"], "Escenario": snapshot.get("saved_scenario_name") or snapshot["scenario"]["id"],
                   "Sector": snapshot.get("sector"), "Prisma": snapshot.get("forecast_trace", {}).get("report", {}).get("prism_id", review.get("prism_id", "Todos")),
                   "Especialista": snapshot["generated_by"]["display_name"], "Estado": review.get("status", "Sin revisión"),
                   "Modelos": str(snapshot.get("model_versions", snapshot.get("forecast_trace", {}).get("report", {}).get("model_versions", {})))+
                        " "+str(sorted({r.get("model_version", "") for r in snapshot.get("anomalies", [])})), "Versión": item["version"]}
            date = pd.Timestamp(item["created_at"]).date()
            if (query and query not in str(row).casefold()) or (after and date < after) or (before and date > before):
                continue
            rows.append(row)
        a, b, d = st.columns(3)
        filters = {}
        for column, label, widget in (("Escenario", "Escenario del reporte", a), ("Prisma", "Prisma del reporte", b),
                                      ("Estado", "Estado del reporte", d)):
            choices = sorted({str(row[column]) for row in rows} - {"Todos"})
            filters[column] = widget.selectbox(label, ["Todos"]+choices, key="report_filter_"+column)
        rows = [row for row in rows if all(value == "Todos" or str(row[column]) == value for column, value in filters.items())]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        if rows:
            ids = [row["Código"] for row in rows]
            chosen = st.selectbox("Consultar reporte guardado", ids, key="report_history_selection")
            item = next(item for item in items if item["id"] == chosen)
            if st.button("Ver detalle", key="report_view_detail"):
                st.session_state.report_detail_id = chosen
            if st.session_state.get("report_detail_id") == chosen:
                st.json(item)
            content = item["snapshot"] | {"report_archive": {k: v for k, v in item.items() if k != "snapshot"}}
            st.download_button("Descargar HTML guardado", report_html(content), "geoslope_reporte.html", "text/html")
            st.download_button("Descargar JSON guardado", json.dumps(item, ensure_ascii=False, indent=2), "geoslope_reporte.json", "application/json")
            st.download_button("Descargar PDF guardado", archive_pdf(item), "geoslope_reporte.pdf", "application/pdf")
            st.button("Crear nueva versión del reporte", key="report_new_version", on_click=new_report_version, args=(chosen,))
        if active.id == "historical":
            with st.expander("Exportaciones históricas PDF / CSV / JSON"):
                from gsreview.presentation.views import report_view
                report_view(c, token)
