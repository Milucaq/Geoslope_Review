"""Guided workflow, scenario dashboard, independent review and export screens."""

import json

import pandas as pd
import streamlit as st

from gsreview.application.workflow import (
    scenario_frame, data_version, quality_summary, matching_scores, matching_forecast,
    analysis_context, context_id,
)
from gsreview.application.scenario_reports import report_payload, report_html, LIMITATIONS
from gsreview.domain.rules import ReviewInput, STATUSES, RELEVANCE, FOLLOW_UP, ValidationError
from gsreview.presentation.navigation import navigate
from gsreview.application.scenarios import select_scenario


def continue_to(label, page, key):
    st.button(label, key=key, on_click=navigate, args=(page,), type="primary")


def begin_scenario(scenario_id):
    from gsreview.presentation.persistence import new_scenario
    new_scenario(scenario_id)
    select_scenario(st.session_state, scenario_id)
    st.session_state.scenario_selector = scenario_id
    navigate("Calidad de datos")


def render_workflow(c, token, active, page):
    if active.id == "historical":
        st.caption("Caso histórico de referencia · resultados congelados y evidencia científica")
        if page == "Inicio":
            st.markdown("**Comenzar un análisis de monitoreo**")
            left, right = st.columns(2)
            left.button("Nuevo escenario · John Henry", key="flow_new_jh", on_click=begin_scenario, args=("john_henry",))
            right.button("Nuevo escenario · CSV externo", key="flow_new_csv", on_click=begin_scenario, args=("external",))
        return
    frame = scenario_frame(st.session_state, active.id)
    scores = matching_scores(st.session_state, active.id, frame) if frame is not None else {}
    forecast = matching_forecast(st.session_state, active.id, frame) if frame is not None else {}
    seen = st.session_state.get("scenario_visualized") == (active.id, data_version(frame))
    reviews = c.scenario_reviews.listing(token, active.id, frame) if frame is not None else []
    completed = [True, frame is not None, seen, bool(scores), bool(forecast), bool(reviews),
                 st.session_state.get("scenario_report_version") == (active.id, data_version(frame))]
    st.progress(sum(completed)/7, text=f"Avance del análisis · {sum(completed)} de 7 etapas registradas")
    steps = [("Validar datos", "Calidad de datos"), ("Visualizar taludes", "Vista espacial"),
             ("Detectar anomalías", "Prismas"), ("Pronosticar", "Prismas"),
             ("Revisar resultados", "Bandeja de revisión"), ("Generar reporte", "Reportes")]
    columns = st.columns(6)
    for i, (label, destination) in enumerate(steps):
        columns[i].button(label, key=f"flow_{i}", on_click=navigate, args=(destination,),
                          disabled=i > 1 and frame is None, width="stretch")


def dashboard(c, token, active, frame):
    st.title("Panorama del escenario")
    if frame is None:
        st.info("Prepara los datos del escenario para comenzar. No se muestran indicadores históricos.")
        continue_to("Preparar datos", "Calidad de datos", "flow_prepare")
        return
    summary = quality_summary(frame)
    scores = matching_scores(st.session_state, active.id, frame)
    forecast = matching_forecast(st.session_state, active.id, frame)
    reviews = c.scenario_reviews.listing(token, active.id, frame)
    cols = st.columns(4)
    for col, label, value in zip(cols, ["Prismas del escenario", "Mediciones disponibles", "Sectores instrumentados", "Magnitudes conocidas"],
                                 [summary["prisms"], summary["measurements"], summary["sectors"] if summary["sectors"] is not None else "No declarados", summary["known"]]):
        col.metric(label, value)
    cols = st.columns(4)
    marks = int(scores["scores"].isolation_forest_marked_q99.fillna(False).sum()) if scores else "Sin ejecutar"
    cols[0].metric("Marcas atípicas · Isolation Forest", marks)
    cols[1].metric("Episodios candidatos", "No calculados")
    cols[2].metric("Pronósticos disponibles", forecast["report"]["prism_id"] if forecast else "Sin ejecutar")
    latest = {context_id({k: r[k] for k in ("scenario_id", "data_version", "prism_id", "cutoff", "model_version", "analysis_id")}): r for r in reviews}
    cols[3].metric("Revisiones humanas guardadas", len(latest))
    st.caption("Revisión humana: "+" · ".join(
        f"{status}: {sum(r['status'] == status for r in latest.values())}" for status in STATUSES))
    st.caption(f"Calidad: {summary['missing']} magnitudes ausentes. Datos y resultados de tipo {active.kind}. "
               "Las marcas se cuentan por observación, no como episodios ni diagnósticos.")
    if forecast:
        st.caption(f"Pronóstico del prisma {forecast['report']['prism_id']} · corte {forecast['cutoff']} · "
                   f"{forecast['report']['horizon_hours']} horas. No representa otros prismas.")
    continue_to("Continuar con la visualización", "Vista espacial", "flow_visualize")


def review_context(frame, active):
    ids = sorted(frame.prism_id.unique())
    saved = st.session_state.get("scenario_selected_prism")
    prism = st.selectbox("Prisma a revisar", ids, index=ids.index(saved) if saved in ids else 0,
                        key="scenario_review_prism")
    times = sorted(pd.to_datetime(frame.loc[frame.prism_id.eq(prism), "timestamp"], utc=True).unique())
    saved_cutoff = pd.to_datetime(st.session_state.get("scenario_analysis_cutoff"), utc=True)
    cutoff = st.select_slider("Fecha de corte de revisión", times, value=saved_cutoff if saved_cutoff in times else times[-1], key="scenario_review_cutoff")
    scores = matching_scores(st.session_state, active.id, frame)
    model = str(scores["scores"].model_version.iloc[0]) if scores else "not_run"
    forecast = matching_forecast(st.session_state, active.id, frame, prism, cutoff)
    if forecast:
        model += " | forecast="+json.dumps(forecast["report"].get("model_versions", {}), sort_keys=True)
    analysis = context_id({"anomalies": scores.get("executed_at", "not_run"),
                           "forecast": forecast.get("report", {}), "cutoff": str(cutoff)})
    return analysis_context(frame, active.id, prism, cutoff, model, analysis)


def review_page(c, token, active, frame):
    st.title("Revisión del escenario")
    st.caption("Decisión humana, sin diagnóstico automático de inestabilidad. Historial propio del usuario y la versión de datos.")
    context = review_context(frame, active)
    records = c.scenario_reviews.listing(token, active.id, frame)
    same = [r for r in records if all(r.get(k) == v for k, v in context.items())]
    latest = same[-1] if same else {}
    identity = context_id(context)
    expected_key = "scenario_review_expected_"+identity
    draft = "scenario_review_draft_"+identity+"_"
    if expected_key not in st.session_state:
        st.session_state[expected_key] = latest.get("version", 0)
    st.write(f"Versión de revisión: {latest.get('version', 0)} · datos {context['data_version'][:12]} · modelo {context['model_version']}")
    if st.session_state[expected_key] != latest.get("version", 0):
        st.warning("Hay una versión más reciente. Recarga la revisión antes de guardar este borrador.")
        st.button("Recargar revisión", key="scenario_review_reload", on_click=reload_review,
                  args=(expected_key, latest.get("version", 0), draft))
    with st.form("scenario_review_form_"+identity):
        status = st.selectbox("Estado de revisión humana", STATUSES, index=STATUSES.index(latest.get("status", "Pendiente")), key=draft+"status")
        relevance = st.selectbox("Relevancia para seguimiento", RELEVANCE, index=RELEVANCE.index(latest.get("relevance", "Indeterminado")), key=draft+"relevance")
        comment = st.text_area("Observaciones del especialista", value=latest.get("comment", ""), max_chars=6000, key=draft+"comment")
        quality = st.text_area("Información adicional o validaciones pendientes", value=latest.get("quality_comment", ""), max_chars=6000, key=draft+"quality")
        follow = st.selectbox("Acción de seguimiento", FOLLOW_UP, index=FOLLOW_UP.index(latest.get("follow_up", "Verificar datos")), key=draft+"follow")
        if st.form_submit_button("Guardar decisión", type="primary"):
            try:
                saved = c.scenario_reviews.save(token, active.id, frame, context["prism_id"], context["cutoff"],
                    context["model_version"], context["analysis_id"], ReviewInput(status=status, relevance=relevance,
                    comment=comment, quality_comment=quality, follow_up=follow, expected_version=st.session_state[expected_key]))
            except ValidationError as exc:
                st.error(str(exc))
            else:
                st.session_state[expected_key] = saved["version"]
                st.success("Decisión guardada con trazabilidad e historial de versiones.")
    records = c.scenario_reviews.listing(token, active.id, frame)
    if records:
        st.dataframe(pd.DataFrame(records), hide_index=True)
    continue_to("Continuar al reporte", "Reportes", "flow_report")


def reload_review(expected_key, version, draft):
    st.session_state[expected_key] = version
    for key in list(st.session_state):
        if key.startswith(draft):
            del st.session_state[key]


def reports_page(c, token, active, frame, show_title=True):
    if show_title:
        st.title("Reporte del escenario")
    st.info(LIMITATIONS)
    payload = report_payload(c.auth, c.scenario_reviews, token, active.id, frame, st.session_state)
    st.write(f"Versión de datos: {payload['data_version']} · {len(payload['human_reviews'])} decisiones propias guardadas")
    st.download_button("Descargar reporte HTML" if show_title else "Vista previa HTML (sin archivar)", report_html(payload).encode("utf-8"),
                       "geoslope_escenario.html", "text/html", key="scenario_download_html")
    st.download_button("Descargar trazabilidad JSON" if show_title else "Vista previa JSON (sin archivar)", json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"),
                       "geoslope_escenario.json", "application/json", key="scenario_download_json")
    st.session_state.scenario_report_version = (active.id, data_version(frame))
    if not payload["human_reviews"]:
        st.warning("Reporte sin decisión humana guardada; no constituye revisión completada.")
    scientific_reference(c)


def scientific_reference(c):
    with st.expander("Experimentos científicos existentes · referencia sintética independiente"):
        from gsreview.analytics.experiment_summary import summarize_experiments

        st.caption("SYN-W01 · semilla 42 · 45 días · cadencia 6 h. No son métricas del prisma activo ni validación de campo.")
        summary, comparisons = summarize_experiments(c.app_root / "reports/science/synthetic_backtest.csv")
        st.dataframe(summary, hide_index=True)
        st.dataframe(comparisons, hide_index=True)
        st.caption("True indica menor error o cobertura más próxima a 0.80 que la referencia; False indica que no la supera en ese criterio.")
