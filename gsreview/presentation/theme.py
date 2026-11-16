"""Tema visual del panel: carga de CSS (solo styles.css; navigation.css lo inyecta navigation.py), helpers HTML y estilo común de Plotly."""

from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parents[2] / "assets"

PALETTE = {
    "ink": "#071A24",
    "teal": "#134E5E",
    "teal_2": "#1A6B7C",
    "cyan": "#26C6DA",
    "sky": "#38BDF8",
    "grid": "#E2E8F0",
    "text": "#0F2A36",
    "gray": "#94A3B8",
}
COLORWAY = [PALETTE["teal"], PALETTE["cyan"], PALETTE["sky"], PALETTE["teal_2"], PALETTE["gray"]]


@lru_cache(maxsize=1)
def _css():
    parts = []
    for name in ("styles.css",):
        path = ASSETS / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def inject_css():
    """Inyecta los estilos del panel; es idempotente entre ejecuciones."""
    st.markdown(f"<style>{_css()}</style>", unsafe_allow_html=True)


def html(markup, target=st):
    """Renderiza HTML sin líneas en blanco ni sangrías (Markdown las rompe)."""
    clean = "\n".join(line.strip() for line in markup.splitlines() if line.strip())
    target.markdown(clean, unsafe_allow_html=True)


def badge(text, tone="info"):
    return f'<span class="gx-badge gx-{tone}">{escape(str(text))}</span>'


def page_head(label, status="Datos verificados"):
    return (
        '<div class="gx-page"></div>'
        '<div class="gx-crumbs">'
        f"<span>Monitoreo Geotécnico / <b>{escape(label)}</b></span>"
        f"{badge(status, 'ok')}</div>"
    )


def style_fig(fig, height=340):
    """Aplica el estilo común a una figura de Plotly."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Segoe UI, sans-serif", "color": PALETTE["text"], "size": 12},
        colorway=COLORWAY,
        margin={"l": 8, "r": 8, "t": 40, "b": 8},
        height=height,
        title={"font": {"size": 15, "color": PALETTE["ink"]}},
        hoverlabel={"bgcolor": PALETTE["ink"], "font": {"color": "#FFFFFF"}},
        legend={"bgcolor": "rgba(0,0,0,0)"},
    )
    fig.update_xaxes(gridcolor=PALETTE["grid"], zeroline=False, linecolor=PALETTE["grid"])
    fig.update_yaxes(gridcolor=PALETTE["grid"], zeroline=False, linecolor=PALETTE["grid"])
    return fig


# --- Piezas para navigation.py (sidebar) ---------------------------------------------------


def sidebar_brand(name):
    return f'<div class="gx-brand"><i>G</i><b>{escape(name)}</b></div>'


def sidebar_group(title):
    return f'<div class="gx-nav-title">{escape(title)}</div>'


def sidebar_context(site="West Wall", policy="Política híbrida provisional"):
    return (
        '<div class="gx-context"><small>Sitio</small>'
        f"<b>{escape(site)}</b><span>{escape(policy)}</span></div>"
    )


def sidebar_profile(display_name, role):
    initials = "".join(p[0] for p in str(display_name).split()[:2]).upper() or "U"
    return (
        f'<div class="gx-profile"><div class="gx-avatar">{escape(initials)}</div>'
        f"<div><b>{escape(str(display_name))}</b><span>{escape(str(role))}</span></div></div>"
    )