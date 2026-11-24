from gsreview.configuration import COLORS
from gsreview.presentation import theme

"""Gráficos instrumentales locales; ninguna superficie se infiere de los prismas."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PALETTE = {
    "no_evaluable": COLORS["gray"],
    "sin_marca": COLORS["blue"],
    "marca_aislada": COLORS["navy"],
    "episodio_en_observacion": COLORS["teal"],
    "candidato_revision": COLORS["purple"],
}


def series(rows, episode=None):
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
        subplot_titles=(
            "Movimiento reportado (mm)",
            "Puntaje base y q99",
            "Isolation Forest y q99",
        ),
    )
    fig.add_trace(
        go.Scatter(
            x=rows.timestamp,
            y=rows.reported_3d_movement_mm,
            name="Medición real",
            line_color=theme.PALETTE["teal"],
        ),
        row=1,
        col=1,
    )
    for flag, label, color, symbol in [
        ("baseline_mark_q99", "Marca base", theme.PALETTE["cyan"], "circle-open"),
        ("iforest_mark_q99", "Marca IF", theme.PALETTE["sky"], "diamond-open"),
        ("agreement_same_row", "Coincidencia", COLORS["purple"], "diamond"),
        ("quality_interruption_flag", "Calidad", COLORS["gray"], "x"),
    ]:
        points = rows.loc[rows[flag].fillna(False)]
        fig.add_trace(
            go.Scatter(
                x=points.timestamp,
                y=points.reported_3d_movement_mm,
                mode="markers",
                name=label,
                marker={"color": color, "symbol": symbol, "size": 8},
            ),
            row=1,
            col=1,
        )
    for row, score, threshold in [
        (2, "baseline_score", 4.439772224885318),
        (3, "isolation_forest_score", 0.5872931971929567),
    ]:
        fig.add_trace(
            go.Scatter(
                x=rows.timestamp,
                y=rows[score],
                mode="lines+markers",
                name=score,
                line_color=theme.PALETTE["teal_2"],
            ),
            row=row,
            col=1,
        )
        fig.add_hline(y=threshold, line_dash="dash", line_color="#F59E0B", row=row, col=1)
    if episode is not None:
        for row in (1, 2, 3):
            fig.add_vrect(
                x0=episode.start_timestamp,
                x1=episode.last_observed_timestamp,
                fillcolor=COLORS["purple"],
                opacity=0.08,
                line_width=0,
                row=row,
                col=1,
            )
    theme.style_fig(fig, 650)
    fig.update_layout(
        title="Mediciones reales · anomalías estadísticas experimentales",
        legend={"orientation": "h", "y": -0.15},
        margin={"t": 80, "b": 100},
    )
    return fig


STATE_LABELS = {
    "no_evaluable": "No evaluable",
    "sin_marca": "Sin marca",
    "marca_aislada": "Marca aislada",
    "episodio_en_observacion": "Episodio en observación",
    "candidato_revision": "Candidato para revisión",
}
STATE_SYMBOLS = {
    "no_evaluable": "cross",
    "sin_marca": "circle",
    "marca_aislada": "square",
    "episodio_en_observacion": "diamond-open",
    "candidato_revision": "diamond",
}


def spatial(points, dimension="3D", colors=None, selected=None, focus=False, labels=True):
    """Only original points; focusing changes the camera, never the coordinates."""
    colors = colors or {
        **PALETTE,
        "sin_marca": COLORS["spatial_series"],
        "marca_aislada": COLORS["spatial_selected"],
        "candidato_revision": COLORS["spatial_agreement"],
    }

    fig = go.Figure()

    mark_count = int(points.causal_state.isin(["marca_aislada", "episodio_en_observacion"]).sum())

    for state, group in points.groupby("causal_state"):
        custom = (
            group[["prism_id", "timestamp", "model_eligible", "episode_id"]].astype(str).to_numpy()
        )
        common = dict(
            mode="markers+text" if labels else "markers",
            text=group.prism_id,
            textposition="top center",
            textfont={"size": 11, "color": COLORS["spatial_text"]},
            customdata=custom,
            name=(
                f"Marca estadística ({mark_count})"
                if state in ("marca_aislada", "episodio_en_observacion")
                else f"{STATE_LABELS[state]} ({len(group)})"
            ),
            legendgroup=(
                "mark" if state in ("marca_aislada", "episodio_en_observacion") else state
            ),
            showlegend=not (
                state == "marca_aislada" and "episodio_en_observacion" in set(points.causal_state)
            ),
            marker={
                "size": 6 if dimension == "3D" else 11,
                "color": colors[state],
                "symbol": "circle-open"
                if state in ("marca_aislada", "episodio_en_observacion")
                else STATE_SYMBOLS[state],
                "opacity": 0.9,
            },
            hovertemplate="Prisma %{customdata[0]}<br>Medición %{customdata[1]}<br>Evaluable %{customdata[2]}<br>Episodio %{customdata[3]}<extra></extra>",
        )
        if dimension == "3D":
            fig.add_trace(go.Scatter3d(x=group.easting, y=group.northing, z=group.rl, **common))
        else:
            fig.add_trace(go.Scatter(x=group.easting, y=group.northing, **common))
    target = points.loc[points.prism_id.eq(selected)] if selected is not None else points.iloc[:0]
    if not target.empty:
        row = target.iloc[0]
        highlight = dict(
            mode="markers+text",
            text=[str(selected)],
            textposition="top center",
            textfont={"size": 12, "color": COLORS["spatial_text"]},
            customdata=target[["prism_id", "timestamp", "model_eligible", "episode_id"]]
            .astype(str)
            .to_numpy(),
            name="Prisma seleccionado",
            showlegend=False,
            marker={
                "size": 13 if dimension == "3D" else 23,
                "color": COLORS["spatial_selected"],
                "symbol": "circle-open",
                "line": {"width": 3},
            },
            hovertemplate="Prisma " + str(selected) + "<extra></extra>",
        )
        if dimension == "3D":
            fig.add_trace(go.Scatter3d(x=[row.easting], y=[row.northing], z=[row.rl], **highlight))
        else:
            fig.add_trace(go.Scatter(x=[row.easting], y=[row.northing], **highlight))
        if focus:
            ranges = {
                column: max(float(points[column].max() - points[column].min()), 1.0)
                for column in ("easting", "northing", "rl")
            }
            if dimension == "3D":
                half = max(ranges.values()) * 0.12
                fig.update_layout(
                    scene_camera={
                        "center": {"x": 0, "y": 0, "z": 0},
                        "eye": {"x": 1.4, "y": 1.4, "z": 1.1},
                    }
                )
                for axis, column in (("xaxis", "easting"), ("yaxis", "northing"), ("zaxis", "rl")):
                    fig.update_layout(
                        scene={
                            axis: {"range": [float(row[column]) - half, float(row[column]) + half]}
                        }
                    )
            else:
                half = max(ranges["easting"], ranges["northing"]) * 0.12
                fig.update_xaxes(range=[float(row.easting) - half, float(row.easting) + half])
                fig.update_yaxes(range=[float(row.northing) - half, float(row.northing) + half])
    fig.update_layout(
        title="Ubicaciones instrumentales · datos originales",
        height=650,
        template="plotly_white",
        paper_bgcolor=COLORS["spatial_panel"],
        plot_bgcolor=COLORS["spatial_panel"],
        font={"color": COLORS["spatial_text"]},
        legend={"orientation": "h", "y": -0.1, "font": {"size": 10}},
        margin={"l": 10, "r": 10, "t": 55, "b": 90},
        scene={
            "bgcolor": COLORS["spatial_panel"],
            "aspectmode": "data",
            "xaxis": {
                "title": "Easting",
                "nticks": 5,
                "backgroundcolor": COLORS["spatial_panel"],
                "gridcolor": COLORS["spatial_grid"],
            },
            "yaxis": {
                "title": "Northing",
                "nticks": 5,
                "backgroundcolor": COLORS["spatial_panel"],
                "gridcolor": COLORS["spatial_grid"],
            },
            "zaxis": {
                "title": "RL",
                "nticks": 5,
                "backgroundcolor": COLORS["spatial_panel"],
                "gridcolor": COLORS["spatial_grid"],
            },
        },
        uirevision=f"{dimension}:{selected if focus else 'all'}:{focus}",
    )
    fig.update_xaxes(
        title="Easting (unidad original)", scaleanchor="y", gridcolor=COLORS["spatial_grid"]
    )
    fig.update_yaxes(title="Northing (unidad original)", gridcolor=COLORS["spatial_grid"])
    return fig


def movement_preview(rows):
    """Compact linked series from unchanged measurements and frozen marks."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rows.timestamp,
            y=rows.reported_3d_movement_mm,
            connectgaps=False,
            mode="lines",
            name="Medición real",
            line_color=COLORS["spatial_series"],
        )
    )
    for flag, label, color, symbol in [
        ("union_mark", "Marca estadística", COLORS["spatial_selected"], "circle"),
        ("agreement_same_row", "Coincidencia", COLORS["spatial_agreement"], "diamond"),
        ("quality_interruption_flag", "Interrupción de calidad", "#8995a2", "x"),
    ]:
        subset = rows.loc[rows[flag].fillna(False)]
        fig.add_trace(
            go.Scatter(
                x=subset.timestamp,
                y=subset.reported_3d_movement_mm,
                mode="markers",
                name=label,
                marker={"color": color, "symbol": symbol, "size": 7},
            )
        )
    fig.update_layout(
        height=265,
        title="Movimiento reportado (mm)",
        template="plotly_white",
        paper_bgcolor=COLORS["spatial_panel"],
        plot_bgcolor=COLORS["spatial_panel"],
        margin={"l": 20, "r": 5, "t": 45, "b": 55},
        legend={"orientation": "h", "font": {"size": 9}},
        font={"size": 10, "color": COLORS["spatial_text"]},
    )
    return fig


SYNTHETIC_RISK_COLORS = {
    "estable": "#10B981",
    "observacion": "#F59E0B",
    "alerta_falla": "#EF4444",
}

SYNTHETIC_RISK_SYMBOLS = {
    "estable": "circle",
    "observacion": "diamond-open",
    "alerta_falla": "diamond",
}

SYNTHETIC_RISK_ORDER = ("alerta_falla", "observacion", "estable")


def synthetic_spatial_map(points, dimension="3D", selected=None):
    """Renderiza el mapa espacial 2D/3D de prismas sintéticos coloreados por riesgo de falla (HU-117)."""
    fig = go.Figure()

    if dimension == "3D" and not points.empty and len(points) >= 3:
        e_min, e_max = float(points["easting"].min()) - 8.0, float(points["easting"].max()) + 8.0
        n_min, n_max = float(points["northing"].min()) - 8.0, float(points["northing"].max()) + 8.0
        rl_max, rl_min = float(points["rl"].max()) + 2.0, float(points["rl"].min()) - 2.0
        fig.add_trace(
            go.Surface(
                x=[[e_min, e_max], [e_min, e_max]],
                y=[[n_min, n_min], [n_max, n_max]],
                z=[[rl_max, rl_min], [rl_max, rl_min]],
                colorscale=[[0, "#102837"], [0.5, "#17384C"], [1, "#1F4961"]],
                opacity=0.32,
                showscale=False,
                name="Superficie del talud simulado",
                hoverinfo="skip",
            )
        )

    for level in SYNTHETIC_RISK_ORDER:
        group = points.loc[points["risk_level"].eq(level)]
        if group.empty:
            continue
        label = group["risk_label"].iloc[0]
        color = SYNTHETIC_RISK_COLORS.get(level, COLORS["spatial_series"])
        symbol = SYNTHETIC_RISK_SYMBOLS.get(level, "circle")
        custom = (
            group[
                [
                    "prism_id",
                    "sector",
                    "bench",
                    "displacement_mm",
                    "latest_rate_mm_day",
                    "risk_label",
                    "risk_score",
                    "diagnosis",
                ]
            ]
            .astype(str)
            .to_numpy()
        )
        common = {
            "mode": "markers+text",
            "text": group["prism_id"],
            "textposition": "top center",
            "textfont": {"size": 11, "color": COLORS["spatial_text"]},
            "customdata": custom,
            "name": f"{label} ({len(group)})",
            "marker": {
                "size": 8 if dimension == "3D" else 13,
                "color": color,
                "symbol": symbol,
                "opacity": 0.95,
                "line": {"width": 1.5, "color": "#FFFFFF"},
            },
            "hovertemplate": (
                "<b>Prisma %{customdata[0]}</b> · %{customdata[1]} (%{customdata[2]})<br>"
                "Estado IA: <b>%{customdata[5]}</b> (Índice %{customdata[6]}/100)<br>"
                "Desplazamiento 3D: %{customdata[3]} mm · Tasa: %{customdata[4]} mm/día<br>"
                "Diagnóstico: %{customdata[7]}<extra></extra>"
            ),
        }
        if dimension == "3D":
            fig.add_trace(
                go.Scatter3d(
                    x=group["easting"],
                    y=group["northing"],
                    z=group["rl"],
                    **common,
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=group["easting"],
                    y=group["northing"],
                    **common,
                )
            )

    if selected is not None and not points.empty:
        target = points.loc[points["prism_id"].eq(selected)]
        if not target.empty:
            row = target.iloc[0]
            highlight = {
                "mode": "markers",
                "name": f"Seleccionado ({selected})",
                "showlegend": False,
                "marker": {
                    "size": 15 if dimension == "3D" else 22,
                    "color": COLORS["spatial_selected"],
                    "symbol": "circle-open",
                    "line": {"width": 3, "color": COLORS["spatial_selected"]},
                },
                "hoverinfo": "skip",
            }
            if dimension == "3D":
                fig.add_trace(
                    go.Scatter3d(
                        x=[row["easting"]],
                        y=[row["northing"]],
                        z=[row["rl"]],
                        **highlight,
                    )
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=[row["easting"]],
                        y=[row["northing"]],
                        **highlight,
                    )
                )

    fig.update_layout(
        title=f"Mapa espacial del talud simulado ({dimension}) · Detección de fallas por IA",
        height=520,
        template="plotly_white",
        paper_bgcolor=COLORS["spatial_panel"],
        plot_bgcolor=COLORS["spatial_panel"],
        font={"color": COLORS["spatial_text"]},
        legend={"orientation": "h", "y": -0.12, "font": {"size": 11}},
        margin={"l": 12, "r": 12, "t": 55, "b": 75},
        scene={
            "bgcolor": COLORS["spatial_panel"],
            "aspectmode": "data",
            "xaxis": {
                "title": "Este (Easting, m)",
                "nticks": 5,
                "backgroundcolor": COLORS["spatial_panel"],
                "gridcolor": COLORS["spatial_grid"],
            },
            "yaxis": {
                "title": "Norte (Northing, m)",
                "nticks": 5,
                "backgroundcolor": COLORS["spatial_panel"],
                "gridcolor": COLORS["spatial_grid"],
            },
            "zaxis": {
                "title": "Cota (RL, m)",
                "nticks": 5,
                "backgroundcolor": COLORS["spatial_panel"],
                "gridcolor": COLORS["spatial_grid"],
            },
        },
    )
    fig.update_xaxes(
        title="Este (Easting, m)",
        scaleanchor="y",
        gridcolor=COLORS["spatial_grid"],
    )
    fig.update_yaxes(
        title="Norte (Northing, m)",
        gridcolor=COLORS["spatial_grid"],
    )
    return fig
