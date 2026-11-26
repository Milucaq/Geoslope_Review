"""Componente Three.js compilado localmente con Vite."""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from gsreview.analytics.terrain_mesh import terrain_payload


_BUNDLE = Path(__file__).resolve().parents[2] / "assets/three_component/bundle"


def render_three_terrain(arrays, exaggeration, revision):
    if not (_BUNDLE / "index.html").is_file():
        st.warning("Three.js aún no está compilado. Usa Plotly o ejecuta npm run build.")
        return False
    component = components.declare_component("geoslope_three_terrain", path=str(_BUNDLE))
    component(payload=terrain_payload(arrays, exaggeration), revision=revision,
              key="geoslope_three_terrain", default=None)
    return True


def render_three_instrumental(points, visible, selected, labels, focus, surface, revision):
    from gsreview.analytics.instrumental_mesh import instrumental_payload

    if not (_BUNDLE / "index.html").is_file():
        st.warning("Three.js no está compilado; selecciona Plotly.")
        return None
    component = components.declare_component("geoslope_three_instrumental", path=str(_BUNDLE))
    return component(mode="instrumental", payload=instrumental_payload(
        points, visible, selected, labels, focus, surface), revision=revision,
        key="geoslope_three_instrumental", default=None)
