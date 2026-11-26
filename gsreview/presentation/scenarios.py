"""One scenario selector and explicit boundaries for historical-only modules."""

import streamlit as st

from gsreview.application.scenarios import SCENARIOS, bind_session, select_scenario, supports_page


def render_scenario_selector(token, placement=None):
    active = bind_session(st.session_state, token)
    with placement if placement is not None else st.sidebar:
        selected = st.selectbox(
            "Escenario de monitoreo", list(SCENARIOS),
            index=None if "scenario_selector" in st.session_state else list(SCENARIOS).index(active.id),
            format_func=lambda key: SCENARIOS[key].label,
            key="scenario_selector",
        )
    active = select_scenario(st.session_state, selected)
    st.caption(f"{active.label} · {active.provenance} · {active.spatial_reference}")
    return active


def render_scenario_page(active, page, c=None, token=None):
    """Return True when the scenario owns this page; never fall through to history."""
    if not supports_page(active.id, page):
        st.warning("Este módulo solo admite el histórico congelado. Cambia el escenario para consultarlo.")
        return True
    if page == "Reportes":
        from gsreview.presentation.persistence import reports
        from gsreview.application.workflow import scenario_frame
        reports(c, token, active, scenario_frame(st.session_state, active.id))
        return True
    if active.id == "historical" or page not in {"Inicio", "Calidad de datos", "Prismas", "Bandeja de revisión", "Reportes"}:
        return False
    from gsreview.application.workflow import scenario_frame
    from gsreview.presentation.workflow import dashboard, continue_to, review_page, reports_page

    frame = scenario_frame(st.session_state, active.id)
    if page == "Inicio":
        dashboard(c, token, active, frame)
    elif page == "Calidad de datos" and active.id == "external":
        st.title("Calidad del escenario")
        from gsreview.presentation.external_spatial_workspace import render_external_workspace

        render_external_workspace(c, token, mode="data")
    elif frame is None:
        st.title("Preparar escenario")
        st.info("Aún no hay datos válidos de este escenario. Carga el CSV o genera instrumentación en el visor.")
        continue_to("Ir a preparación del terreno", "Vista espacial", "flow_terrain_prepare")
    elif page == "Calidad de datos":
        st.title("Calidad del escenario")
        from gsreview.application.workflow import quality_summary
        quality = quality_summary(frame)
        cols = st.columns(4)
        for col, label, value in zip(cols, ["Prismas", "Mediciones", "Magnitudes conocidas", "Magnitudes ausentes"],
                                     [quality["prisms"], quality["measurements"], quality["known"], quality["missing"]]):
            col.metric(label, value)
        st.dataframe(frame.head(100), hide_index=True)
        st.caption(active.provenance+" · "+active.spatial_reference)
        continue_to("Visualizar taludes", "Vista espacial", "flow_quality_view")
    elif page == "Prismas":
        st.title("Análisis del escenario")
        from gsreview.presentation.science import render_anomalies
        render_anomalies(c, token, active.id, frame)
    elif page == "Bandeja de revisión":
        review_page(c, token, active, frame)
    else:
        reports_page(c, token, active, frame)
    return True
