"""Vista temporal de prismas importados desde CSV."""

import plotly.graph_objects as go
import streamlit as st
import hashlib

from gsreview.application.csv_import import MAX_FILE_SIZE, validate_csv
from gsreview.application.external_spatial import prepare_external_points
from gsreview.domain.rules import ValidationError


def render_external_workspace(c=None, token=None, mode="full"):
    st.info(
        "Datos externos temporales. No se modifican las mediciones "
        "históricas ni los resultados de los modelos."
    )
    st.caption("Columna opcional para análisis científico: reported_3d_movement_mm, "
               "magnitud escalar reportada en milímetros. Vacío significa desconocido.")

    uploaded = st.file_uploader(
        "Seleccionar CSV validable",
        type=["csv"],
        key="hu110_csv",
    )

    cached = st.session_state.get("scenario_external_frame")
    if uploaded is None and cached is None:
        st.caption(
            "Columnas requeridas: source_record_id, prism_id, timestamp, "
            "easting, northing, rl, movement_rate_mm_per_day, elapsed_hours."
        )
        return

    try:
        if uploaded is not None:
            content = uploaded.getvalue()
            if len(content) > MAX_FILE_SIZE:
                raise ValidationError("El archivo supera el límite de 10 MB.")
            validated = validate_csv(
                content,
                filename=getattr(uploaded, "name", None),
                content_type=getattr(uploaded, "type", None),
            )
        else:
            validated = cached.copy(deep=True)
        points, invalid_count = prepare_external_points(validated)
    except ValidationError as error:
        st.session_state.pop("scenario_external_frame", None)
        st.error(f"CSV rechazado: {error}")
        return

    st.session_state.scenario_external_frame = validated.copy(deep=True)
    if uploaded is not None:
        st.session_state.scenario_external_source = {
            "filename": getattr(uploaded, "name", "CSV externo"),
            "source_sha256": hashlib.sha256(content).hexdigest(), "validation": "CSV structure only",
        }
    st.success("Archivo validado correctamente.")
    st.caption("Estructura CSV validada; CRS y datum pendientes. La carga no ejecuta inferencia.")

    if invalid_count:
        st.warning(f"Se omitieron {invalid_count} mediciones con coordenadas inválidas.")

    first, second = st.columns(2)
    first.metric("Mediciones validadas", len(validated))
    second.metric("Prismas visualizados", len(points))
    if mode == "data":
        st.dataframe(validated.head(100), hide_index=True)
        from gsreview.presentation.workflow import continue_to
        continue_to("Continuar al visor", "Vista espacial", "flow_external_view")
        return

    dimension = (
        st.segmented_control(
            "Dimensión",
            ["2D", "3D"],
            default="3D",
            key="hu110_dimension",
        )
        or "3D"
    )

    prism_ids = sorted(points["prism_id"].astype(str).unique().tolist())
    chosen = st.selectbox(
        "Consultar prisma",
        ["Todos"] + prism_ids,
        key="hu110_prism",
    )

    visible = points if chosen == "Todos" else points.loc[points["prism_id"].astype(str).eq(chosen)]

    custom = visible[["prism_id", "timestamp", "movement_rate_mm_per_day"]].astype(str).to_numpy()

    common = {
        "mode": "markers+text",
        "text": visible["prism_id"],
        "textposition": "top center",
        "customdata": custom,
        "marker": {"size": 7 if dimension == "3D" else 12},
        "hovertemplate": (
            "Prisma: %{customdata[0]}<br>"
            "Fecha: %{customdata[1]}<br>"
            "Tasa de movimiento: %{customdata[2]} mm/día"
            "<extra></extra>"
        ),
    }

    figure = go.Figure()

    if dimension == "3D":
        figure.add_trace(
            go.Scatter3d(
                x=visible["easting"],
                y=visible["northing"],
                z=visible["rl"],
                **common,
            )
        )
        figure.update_layout(
            scene={
                "xaxis_title": "Este (Easting)",
                "yaxis_title": "Norte (Northing)",
                "zaxis_title": "Elevación (RL)",
                "aspectmode": "data",
            }
        )
    else:
        figure.add_trace(
            go.Scatter(
                x=visible["easting"],
                y=visible["northing"],
                **common,
            )
        )
        figure.update_xaxes(title="Este (Easting)", scaleanchor="y")
        figure.update_yaxes(title="Norte (Northing)")

    figure.update_layout(
        title="Ubicaciones instrumentales · datos externos",
        height=550,
        template="plotly_white",
        margin={"l": 20, "r": 20, "t": 60, "b": 40},
    )

    st.plotly_chart(figure, width="stretch")

    st.caption(
        "Se muestra la última medición por prisma. "
        "Las coordenadas conservan las unidades y el sistema "
        "de referencia declarados por el archivo de origen."
    )

    st.dataframe(
        visible[
            [
                "prism_id",
                "timestamp",
                "easting",
                "northing",
                "rl",
                "movement_rate_mm_per_day",
            ]
        ],
        hide_index=True,
        width="stretch",
    )
    if c is not None:
        from gsreview.application.workflow import data_version
        from gsreview.presentation.science import render_prism_detail
        st.session_state.scenario_visualized = ("external", data_version(validated))
        if chosen != "Todos":
            render_prism_detail(c, token, "external", validated, chosen, validated.timestamp.max())
        else:
            from gsreview.presentation.workflow import continue_to
            continue_to("Continuar al análisis", "Prismas", "flow_external_analyze")
