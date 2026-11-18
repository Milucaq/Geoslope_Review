"""Vista temporal de prismas importados desde CSV."""

import plotly.graph_objects as go
import streamlit as st

from gsreview.application.csv_import import MAX_FILE_SIZE, validate_csv
from gsreview.application.external_spatial import prepare_external_points
from gsreview.domain.rules import ValidationError


def render_external_workspace():
    st.info(
        "Datos externos temporales. No se modifican las mediciones "
        "históricas ni los resultados de los modelos."
    )

    uploaded = st.file_uploader(
        "Seleccionar CSV validable",
        type=["csv"],
        key="hu110_csv",
    )

    if uploaded is None:
        st.caption(
            "Columnas requeridas: source_record_id, prism_id, timestamp, "
            "easting, northing, rl, movement_rate_mm_per_day, elapsed_hours."
        )
        return

    try:
        content = uploaded.getvalue()
        if len(content) > MAX_FILE_SIZE:
            raise ValidationError("El archivo supera el límite de 10 MB.")

        validated = validate_csv(content)
        points, invalid_count = prepare_external_points(validated)
    except ValidationError as error:
        st.error(f"CSV rechazado: {error}")
        return

    st.success("Archivo validado correctamente.")

    if invalid_count:
        st.warning(
            f"Se omitieron {invalid_count} mediciones con coordenadas inválidas."
        )

    first, second = st.columns(2)
    first.metric("Mediciones validadas", len(validated))
    second.metric("Prismas visualizados", len(points))

    dimension = st.segmented_control(
        "Dimensión",
        ["2D", "3D"],
        default="3D",
        key="hu110_dimension",
    ) or "3D"

    prism_ids = sorted(points["prism_id"].astype(str).unique().tolist())
    chosen = st.selectbox(
        "Consultar prisma",
        ["Todos"] + prism_ids,
        key="hu110_prism",
    )

    visible = (
        points
        if chosen == "Todos"
        else points.loc[points["prism_id"].astype(str).eq(chosen)]
    )

    custom = visible[
        ["prism_id", "timestamp", "movement_rate_mm_per_day"]
    ].astype(str).to_numpy()

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
