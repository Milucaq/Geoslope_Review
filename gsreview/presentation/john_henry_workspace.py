"""Independent terrain-backed experimental workspace inside GeoSlope Review."""

import base64
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from gsreview.analytics.john_henry import anchor_synthetic, frame_at
from gsreview.analytics.slope_geometry import slope_degrees, slope_sectors, annotate_anchors

ROOT = Path(__file__).resolve().parents[2]


def _b64(data):
    return base64.b64encode(data).decode("ascii")


@st.cache_data(show_spinner=False)
def _load(root, revision):
    del revision
    root = Path(root)
    meta = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    raw = {}
    for name in ("mesh.npz", "texture.jpg"):
        raw[name] = (root / name).read_bytes()
        if hashlib.sha256(raw[name]).hexdigest() != meta["asset_hashes"][name]:
            raise ValueError("Activos topográficos incompatibles")
    import io

    with np.load(io.BytesIO(raw["mesh.npz"]), allow_pickle=False) as m:
        positions, origin = m["positions"], m["origin"]
        triangles = m["indices"]
        slopes = slope_degrees(positions, triangles)
        payload = {
            "positions": _b64(positions.astype("<f4").tobytes()),
            "uv": _b64(m["uv"].astype("<f4").tobytes()),
            "indices": _b64(m["indices"].astype("<u4").tobytes()),
            "texture": _b64(raw["texture.jpg"]),
            "vertices": len(positions),
            "slopes": _b64(slopes.astype("<f4").tobytes()),
            "triangles": len(m["indices"]),
        }
    return meta, payload, positions, origin, triangles, slopes


@st.cache_data(show_spinner=False, max_entries=6)
def _sectors(slopes, triangles, threshold):
    return slope_sectors(slopes, triangles, threshold)


def render_john_henry_workspace(c, token):
    c.auth.authorize(token, "read")
    c.reader.assert_current()
    st.session_state.scenario_jh_valid = False
    settings = st.session_state.get("scenario_jh_settings", {}).copy()
    st.subheader("John Henry Mine · escenario experimental")
    st.info(
        "Topografía real de John Henry Mine; instrumentación y mediciones simuladas. "
        "No son mediciones reales de la mina ni predicciones de falla."
    )
    root = ROOT / "assets/terrain/john_henry"
    bundle = ROOT / "assets/three_component/bundle"
    files = [root / "metadata.json", root / "mesh.npz", root / "texture.jpg", bundle / "index.html"]
    if not all(p.is_file() for p in files):
        st.warning("Faltan activos preparados o el componente Three.js compilado.")
        return
    try:
        meta, geometry, positions, origin, triangles, slopes = _load(
            str(root), tuple(p.stat().st_mtime_ns for p in files[:3])
        )
    except (OSError, ValueError, KeyError):
        st.error("No se pudieron verificar los activos topográficos.")
        return
    a, b, d = st.columns(3)
    a.metric("Vértices", meta["vertices"])
    b.metric("Triángulos", meta["triangles"])
    d.metric("Paso de malla (m)", f"{meta['mesh_spacing_m'][0]:.1f}")
    st.caption(
        "Fuente: OpenTopography · EPSG:6339 · elevaciones NAVD88. Huecos NoData sin reconstruir."
    )
    st.subheader("Análisis geométrico de taludes")
    st.caption(
        "Pendientes locales estimadas en la malla sin exageración vertical. "
        "No son una clasificación de estabilidad ni delimitaciones mineras oficiales."
    )
    a, b = st.columns(2)
    threshold = a.selectbox(
        "Umbral geométrico (°)", [25, 30, 35, 40, 45, 50],
        index=[25, 30, 35, 40, 45, 50].index(settings.get("threshold", 35)), key="jh_slope_threshold"
    )
    layer = b.radio(
        "Capa del terreno",
        ["Ortofotografía", "Pendientes", "Ortofotografía + pendientes"],
        index=["Ortofotografía", "Pendientes", "Ortofotografía + pendientes"].index(settings.get("layer", "Ortofotografía + pendientes")),
        horizontal=False,
        key="jh_slope_layer_v2",
    )
    sectors = _sectors(slopes, triangles, threshold)
    choices = sorted(int(x) for x in np.unique(sectors) if x > 0)
    st.caption(
        "Amarillo: desde el umbral · naranja: +10° · rojo: +20°. "
        "La capa colorea cada triángulo según la media de sus tres pendientes de vértice, "
        "sin exageración vertical. Gris o textura: triángulos no resaltados. "
        "No representa riesgo. Sectores candidatos: componentes conectados de al menos 20 vértices."
    )
    chosen_sector = st.selectbox(
        "Sector geométrico para instrumentar",
        [0] + choices,
        index=([0]+choices).index(settings.get("sector", 0)) if settings.get("sector", 0) in [0]+choices else 0,
        format_func=lambda x: "Todos los sectores candidatos" if x == 0 else f"Sector {x}",
        key="jh_slope_sector",
    )
    eligible = sectors > 0 if chosen_sector == 0 else sectors == chosen_sector
    st.write(f"Sectores candidatos: {len(choices)} · Vértices elegibles: {int(eligible.sum()):,}")
    with st.form("jh_config"):
        p, q, r = st.columns(3)
        count = p.number_input("Prismas simulados", 4, 40, settings.get("count", 12))
        days = q.number_input("Días simulados", 3, 90, settings.get("days", 15))
        fraction = r.slider("Fracción con deformación simulada", 0.0, 1.0, settings.get("fraction", .25), 0.05)
        seed = st.number_input("Semilla", 0, 2147483647, settings.get("seed", 42))
        generate = st.form_submit_button("Generar escenario sobre terreno real")
    config_key = (meta["asset_hashes"]["mesh.npz"], threshold, chosen_sector)
    settings.update(threshold=threshold, layer=layer, sector=chosen_sector, count=count, days=days, fraction=fraction, seed=seed)
    if generate:
        if int(eligible.sum()) < count:
            st.warning(
                "No hay suficientes vértices elegibles. Reduce el número de prismas o cambia el umbral/sector."
            )
        else:
            generated = c.synthetic.generate(
                token, n_prisms=count, days=days, deformed_fraction=fraction, seed=seed
            )
            anchored = anchor_synthetic(generated["records"], positions[eligible], origin, seed)
            st.session_state["jh_records"] = annotate_anchors(
                anchored, positions, origin, slopes, sectors
            )
            st.session_state["jh_asset"] = meta["asset_hashes"]["mesh.npz"]
            st.session_state["jh_slope_config"] = config_key
            st.session_state.pop("jh_cutoff", None)
    records = st.session_state.get("jh_records")
    st.session_state.scenario_jh_valid = records is not None and st.session_state.get("jh_slope_config") == config_key
    markers = []
    amplify = 1
    if records is not None and st.session_state.get("jh_slope_config") == config_key:
        times = sorted(pd.Timestamp(x).to_pydatetime() for x in records.timestamp.unique())
        saved_cutoff = pd.to_datetime(st.session_state.get("scenario_analysis_cutoff"), utc=True)
        saved_cutoff = saved_cutoff.tz_localize(None).to_pydatetime() if saved_cutoff is not None else None
        cutoff = st.select_slider(
            "Fecha de simulación", options=times, value=saved_cutoff if saved_cutoff in times else times[-1], key="jh_cutoff"
        )
        amplify = st.selectbox(
            "Amplificación visual de flechas (no de prismas)",
            [1, 10, 50, 100],
            index=[1, 10, 50, 100].index(settings.get("amplify", 1)),
            format_func=lambda x: f"{x}×",
            key="jh_vector_scale_v2",
        )
        markers = frame_at(records, cutoff, origin, amplify)
        anchors = records.groupby("prism_id").first()
        for marker in markers:
            row = anchors.loc[marker["id"]]
            marker["pendiente_base_deg"] = float(row["pendiente_base_deg"])
            marker["sector_topografico"] = int(row["sector_topografico"])
        st.caption(
            "Los prismas conservan sus posiciones simuladas sin amplificar. Solo las flechas "
            "se amplifican; no representan trayectorias futuras. El relieve puede tener otra escala vertical. "
            "Si falta una medición, se conserva la última posición válida o la posición inicial."
        )
    vertical = st.selectbox(
        "Exageración vertical del terreno",
        [1, 2, 3, 5],
        index=[1, 2, 3, 5].index(settings.get("vertical", 3)),
        format_func=lambda x: f"{x}×",
        key="jh_vertical_exaggeration",
    )
    st.caption(
        "1× conserva la escala real. Los demás factores exageran visualmente la elevación "
        "del terreno y los instrumentos juntos; no modifican las mediciones exportadas."
    )
    revision = meta["asset_hashes"]["mesh.npz"]
    component = components.declare_component("geoslope_three_john_henry", path=str(bundle))
    event = component(
        mode="john_henry",
        payload=geometry,
        markers=markers,
        amplify=amplify,
        revision=revision,
        vertical=vertical,
        slope_layer=layer != "Ortofotografía",
        slope_mode=layer,
        slope_threshold=threshold,
        key="geoslope_three_john_henry",
        default=None,
    )
    if markers:
        st.caption(
            "Colores: estados simulados por HU-103, no inferencia del Isolation Forest ni niveles de riesgo."
        )
        if isinstance(event, dict):
            chosen = next((m for m in markers if m["id"] == event.get("prism_id")), None)
            if chosen:
                st.write("Prisma simulado:", chosen["id"], "·", chosen["state"])
                st.write("Posición de referencia temporal:", chosen["position_timestamp"])
                st.write(
                    f"Sector geométrico {chosen['sector_topografico']} · Pendiente base {chosen['pendiente_base_deg']:.1f}°"
                )
                st.write(
                    f"Este {chosen['easting']:.4f} · Norte {chosen['northing']:.4f} · Elevación {chosen['rl']:.4f}"
                )
                st.metric(
                    "Desplazamiento vectorial simulado desde el inicio (mm)",
                    f"{chosen['coordinate_displacement_mm']:.3f}",
                )
                reported = chosen["movement"]
                st.write(
                    "Movimiento escalar reportado por el generador (mm):",
                    f"{reported:.3f}" if reported is not None else "Sin dato",
                )
                st.caption(
                    "Magnitudes distintas: la norma del cambio de coordenadas no es necesariamente "
                    "igual al movimiento escalar reportado por HU-103."
                )
        st.dataframe(
            pd.DataFrame(markers).drop(columns=["position", "base", "vector_endpoint"]),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Descargar mediciones simuladas georreferenciadas",
            records.to_csv(index=False).encode("utf-8"),
            "john_henry_prismas_simulados.csv",
            "text/csv",
        )
        from gsreview.application.workflow import data_version
        from gsreview.presentation.science import render_prism_detail

        st.session_state.scenario_visualized = ("john_henry", data_version(records))
        ids = [m["id"] for m in markers]
        if isinstance(event, dict) and event.get("prism_id") in ids:
            event_key = (event.get("prism_id"), event.get("nonce"))
            if st.session_state.get("scenario_last_prism_event") != event_key:
                st.session_state.jh_detail_prism = event["prism_id"]
                st.session_state.scenario_last_prism_event = event_key
        saved_prism = st.session_state.get("scenario_selected_prism")
        prism = st.selectbox("Consultar prisma del escenario", ids, key="jh_detail_prism",
                            index=None if "jh_detail_prism" in st.session_state else ids.index(saved_prism) if saved_prism in ids else 0)
        render_prism_detail(c, token, "john_henry", records, prism, cutoff)
    settings.update(amplify=amplify, vertical=vertical)
    st.session_state.scenario_jh_settings = settings
    with st.expander("Fuente, licencia y metodología"):
        st.json(meta)
