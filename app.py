"""Único punto de navegación; ninguna vista puede evitar el guard de sesión."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st
from gsreview.application.container import Container, APP_ROOT
from gsreview.domain.rules import AccessDenied, ValidationError
from gsreview.presentation.views import login, VIEWS
from gsreview.presentation.navigation import render_navigation
from gsreview.configuration import BRAND
from gsreview.presentation.scenarios import render_scenario_selector, render_scenario_page


@st.cache_resource
def application(runtime, source, key):
    return Container(runtime=runtime, source=source)


def main():
    st.set_page_config(page_title=BRAND["name"], page_icon="⛰", layout="wide", initial_sidebar_state="expanded")
    try:
        c = application(
            os.environ.get("GEOSLOPE_RUNTIME"),
            os.environ.get("GEOSLOPE_SOURCE"),
            os.environ.get("GEOSLOPE_KEY_FILE"),
        )
        css = (APP_ROOT / "assets/styles.css").read_text()
        for key, value in c.brand["colors"].items():
            css = css.replace("{{" + key + "}}", value)
        st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)
        if "token" not in st.session_state:
            login(c)
            return
        token = st.session_state.token
        try:
            actor = c.auth.authorize(token, "profile")
            c.reader.assert_current()
        except AccessDenied:
            st.session_state.clear()
            st.warning("La sesión terminó. Inicia sesión nuevamente.")
            login(c)
            return
        codes = st.session_state.get("recovery_once", [])
        if codes:
            st.title("Guarda tus códigos de recuperación")
            st.info(
                "Se muestran una sola vez. Guárdalos en un lugar privado fuera de esta aplicación."
            )
            st.code("\n".join(codes))
            if st.button("Ya guardé mis códigos", type="primary"):
                st.session_state.pop("recovery_once", None)
                st.rerun()
            return
        from gsreview.application.scenarios import bind_session
        bind_session(st.session_state, token)
        scenario_slot = st.sidebar.container()
        page = render_navigation(c, token, actor)
        # Keep forced password-change/profile flows under their existing permissions.
        if page in {"Inicio", "Vista espacial", "Calidad de datos", "Prismas",
                    "Bandeja de revisión", "Reportes"}:
            c.auth.authorize(token, "read")
            active = render_scenario_selector(token, scenario_slot)
            from gsreview.presentation.persistence import scenario_controls
            scenario_controls(c, token, active)
            from gsreview.presentation.workflow import render_workflow
            render_workflow(c, token, active, page)
            if render_scenario_page(active, page, c, token):
                return
        if page != "Vista espacial":
            st.session_state.pop("spatial_access_logged", None)
        VIEWS[page](c, token)
    except (AccessDenied, ValidationError) as e:
        st.error(str(e))
        if "challenge" in st.session_state and "expir" in str(e):
            st.session_state.pop("challenge", None)
    except Exception:
        st.error(
            "No se pudo completar la operación. Verifica la instalación y la integridad de los datos; el administrador puede consultar la documentación local."
        )


if __name__ == "__main__":
    main()
