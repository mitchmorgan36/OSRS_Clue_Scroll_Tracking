from typing import Any, Dict

import pandas as pd
import plotly.graph_objects as go

from .config import (
    CHART_TOP_MARGIN,
    END_TO_END_RECENT_ACQ_EWMA_SPAN,
    END_TO_END_RECENT_COMP_EWMA_SPAN,
    END_TO_END_X_TITLE_STANDOFF,
    HISTOGRAM_BOTTOM_MARGIN,
    LINE_CHART_BOTTOM_MARGIN,
    PRIMARY_LEGEND_Y,
    PRIMARY_PACE_CHART_HEIGHT,
    SECONDARY_DETAIL_CHART_HEIGHT,
    SECONDARY_HISTOGRAM_HEIGHT,
    SECONDARY_LEGEND_Y,
)
from .metrics import ewma_mean, weighted_ratio

def make_chart_legend_below(y: float | None = None, chart_height: int | None = None) -> dict:
    if y is None:
        y = PRIMARY_LEGEND_Y
    return dict(
        orientation="h",
        yanchor="top",
        y=y,
        xanchor="center",
        x=0.5,
        groupclick="togglegroup",
    )


def make_line_layout(
    title: str,
    x_title: str,
    y_title: str,
    y2_title: str | None = None,
    height: int = 380,
    legend_y: float | None = None,
) -> dict:
    layout = dict(
        title=title,
        height=height,
        margin=dict(l=40, r=40, t=CHART_TOP_MARGIN, b=LINE_CHART_BOTTOM_MARGIN),
        legend=make_chart_legend_below(y=legend_y, chart_height=height),
        xaxis=dict(
            title=dict(text=x_title, standoff=24),
            automargin=True,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        yaxis=dict(
            title=y_title,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
    )
    if y2_title is not None:
        layout["yaxis2"] = dict(title=y2_title, overlaying="y", side="right")
    return layout


def scale_marker_sizes(
    weights: pd.Series,
    min_size: float = 6.0,
    max_size: float = 28.0,
    max_weight: float | None = None,
) -> list[float]:
    vals = pd.to_numeric(weights, errors="coerce").fillna(0.0).clip(lower=0.0)
    positive = vals[vals > 0]
    if positive.empty:
        return [min_size] * len(vals)

    size_max = float(max_weight) if max_weight and max_weight > 0 else float(positive.max())
    size_max = max(size_max, float(positive.max()))
    scale = positive.div(size_max)

    sizes = pd.Series(min_size, index=vals.index, dtype=float)
    sizes.loc[positive.index] = min_size + scale * (max_size - min_size)
    return sizes.tolist()


def build_range_histogram(
    series: pd.Series,
    title: str,
    x_title: str,
    y_title: str,
    height: int = SECONDARY_HISTOGRAM_HEIGHT,
) -> go.Figure:
    values = pd.to_numeric(series, errors="coerce").dropna()
    fig = go.Figure()
    if values.empty:
        fig.update_layout(title=title, height=height)
        return fig

    count = len(values)
    if count <= 5:
        bin_count = max(3, count)
    elif count <= 12:
        bin_count = 5
    elif count <= 25:
        bin_count = 7
    else:
        bin_count = 10

    bins = pd.cut(values, bins=bin_count, include_lowest=True)
    hist = bins.value_counts().sort_index()

    labels = []
    counts = []
    for interval, c in hist.items():
        if int(c) <= 0 or not isinstance(interval, pd.Interval):
            continue
        labels.append(f"{float(interval.left):.2f}–{float(interval.right):.2f}")
        counts.append(int(c))

    fig.add_trace(
        go.Bar(
            x=labels,
            y=counts,
            name="Count",
            marker_color="#4f46e5",
            text=counts,
            textposition="outside",
            texttemplate="%{text}",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=40, r=20, t=CHART_TOP_MARGIN, b=HISTOGRAM_BOTTOM_MARGIN),
        xaxis=dict(
            title=x_title,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        yaxis=dict(
            title=y_title,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        showlegend=False,
    )
    return fig


def build_acq_clues_per_hour_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["trip_id", "clues_per_hour"]).sort_values("trip_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout("Clues per hour by trip", "Trip #", "Clues per hour", height=PRIMARY_PACE_CHART_HEIGHT)
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["clues_per_hour"],
            mode="lines+markers",
            name="Clues per hour",
            line=dict(color="#1d4ed8", width=3),
            marker=dict(color="#1d4ed8", size=7),
            customdata=pd.DataFrame({"clues": d["clues"], "log_date": d["log_date"].astype(str)}),
            hovertemplate=(
                "Trip %{x}<br>Date: %{customdata[1]}"
                "<br>Clues/hr: %{y:.2f}"
                "<br>Clues obtained: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["recent_ewma_clues_per_hour"],
            mode="lines",
            name=f"Recent EWMA (span {END_TO_END_RECENT_ACQ_EWMA_SPAN} trips)",
            line=dict(color="#60a5fa", width=2.5, dash="dash"),
            hovertemplate=(
                f"Trip %{{x}}<br>Recent EWMA "
                f"(span {END_TO_END_RECENT_ACQ_EWMA_SPAN} trips): %{{y:.2f}} clues/hr<extra></extra>"
            ),
        )
    )

    overall_avg = weighted_ratio(d["clues"], d["duration_seconds"] / 3600.0)
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#93c5fd", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} clues/hr<extra></extra>",
        )
    )
    return fig


def build_acq_profitability_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["trip_id"]).sort_values("trip_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "GP cost per clue by trip",
            "Trip #",
            "GP per clue",
            height=SECONDARY_DETAIL_CHART_HEIGHT,
            legend_y=SECONDARY_LEGEND_Y,
        )
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["gp_cost_per_clue"],
            mode="lines+markers",
            name="GP cost per clue",
            line=dict(color="#b45309", width=2.5),
            marker=dict(color="#b45309", size=6),
            customdata=pd.DataFrame({"clues": d["clues"], "log_date": d["log_date"].astype(str)}),
            hovertemplate=(
                "Trip %{x}<br>Date: %{customdata[1]}"
                "<br>GP cost/clue: %{y:,.0f}"
                "<br>Clues obtained: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["recent_ewma_gp_cost_per_clue"],
            mode="lines",
            name=f"Recent EWMA (span {END_TO_END_RECENT_ACQ_EWMA_SPAN} trips)",
            line=dict(color="#f59e0b", width=2.5, dash="dash"),
            hovertemplate=(
                f"Trip %{{x}}<br>Recent EWMA "
                f"(span {END_TO_END_RECENT_ACQ_EWMA_SPAN} trips): %{{y:,.0f}} GP/clue<extra></extra>"
            ),
        )
    )

    overall_avg = weighted_ratio(d["gp_cost"], d["clues"])
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#fde68a", width=2, dash="dot"),
            hovertemplate="Trip %{x}<br>Overall GP cost/clue: %{y:,.0f}<extra></extra>",
        )
    )
    return fig


def build_completion_minutes_per_casket_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "minutes_per_casket"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "Minutes per casket by session",
            "Session #",
            "Minutes per casket",
            height=SECONDARY_DETAIL_CHART_HEIGHT,
            legend_y=SECONDARY_LEGEND_Y,
        )
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["minutes_per_casket"],
            mode="lines+markers",
            name="Minutes per casket",
            line=dict(color="#0f766e", width=3),
            marker=dict(color="#0f766e", size=7),
            hovertemplate="Session %{x}<br>Minutes/casket: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["recent_ewma_minutes_per_casket"],
            mode="lines",
            name=f"Recent EWMA (span {END_TO_END_RECENT_COMP_EWMA_SPAN} sessions)",
            line=dict(color="#5eead4", width=2.5, dash="dash"),
            hovertemplate=(
                f"Session %{{x}}<br>Recent EWMA "
                f"(span {END_TO_END_RECENT_COMP_EWMA_SPAN} sessions): %{{y:.2f}} min/casket<extra></extra>"
            ),
        )
    )

    overall_avg = weighted_ratio(d["duration_seconds"] / 60.0, d["clues_completed"])
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#99f6e4", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} min/casket<extra></extra>",
        )
    )
    return fig


def build_completion_caskets_per_hour_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "caskets_per_hour"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "Caskets per hour by session",
            "Session #",
            "Caskets per hour",
            height=PRIMARY_PACE_CHART_HEIGHT,
        )
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["caskets_per_hour"],
            mode="lines+markers",
            name="Caskets per hour",
            line=dict(color="#047857", width=3),
            marker=dict(color="#047857", size=7),
            customdata=pd.DataFrame(
                {
                    "clues_completed": d["clues_completed"],
                    "log_date": d["log_date"].astype(str),
                }
            ),
            hovertemplate=(
                "Session %{x}<br>Date: %{customdata[1]}"
                "<br>Caskets/hr: %{y:.2f}"
                "<br>Caskets completed: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["recent_ewma_caskets_per_hour"],
            mode="lines",
            name=f"Recent EWMA (span {END_TO_END_RECENT_COMP_EWMA_SPAN} sessions)",
            line=dict(color="#6ee7b7", width=2.5, dash="dash"),
            hovertemplate=(
                f"Session %{{x}}<br>Recent EWMA "
                f"(span {END_TO_END_RECENT_COMP_EWMA_SPAN} sessions): %{{y:.2f}} caskets/hr<extra></extra>"
            ),
        )
    )

    overall_avg = weighted_ratio(d["clues_completed"], d["duration_seconds"] / 3600.0)
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#a7f3d0", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} caskets/hr<extra></extra>",
        )
    )
    return fig


def build_completion_caskets_completed_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "clues_completed"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "Caskets completed by session",
            "Session #",
            "Caskets completed",
            height=SECONDARY_DETAIL_CHART_HEIGHT,
            legend_y=SECONDARY_LEGEND_Y,
        )
    )
    if d.empty:
        return fig

    d["recent_ewma_caskets_completed"] = ewma_mean(
        pd.to_numeric(d["clues_completed"], errors="coerce"),
        END_TO_END_RECENT_COMP_EWMA_SPAN,
    )

    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["clues_completed"],
            mode="lines+markers",
            name="Caskets completed",
            line=dict(color="#059669", width=3),
            marker=dict(color="#059669", size=7),
            customdata=pd.DataFrame({"log_date": d["log_date"].astype(str)}),
            hovertemplate=(
                "Session %{x}<br>Date: %{customdata[0]}"
                "<br>Caskets completed: %{y:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["recent_ewma_caskets_completed"],
            mode="lines",
            name=f"Recent EWMA (span {END_TO_END_RECENT_COMP_EWMA_SPAN} sessions)",
            line=dict(color="#6ee7b7", width=2.5, dash="dash"),
            hovertemplate=(
                f"Session %{{x}}<br>Recent EWMA "
                f"(span {END_TO_END_RECENT_COMP_EWMA_SPAN} sessions): %{{y:.2f}} caskets/session<extra></extra>"
            ),
        )
    )

    overall_avg = float(pd.to_numeric(d["clues_completed"], errors="coerce").dropna().mean())
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#a7f3d0", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} caskets/session<extra></extra>",
        )
    )
    return fig


def build_end_to_end_time_breakdown_pie(end_to_end_sum: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    acquire_minutes = float(end_to_end_sum.get("acquire_minutes_per_casket") or 0.0)
    complete_minutes = float(end_to_end_sum.get("complete_minutes_per_casket") or 0.0)

    labels = ["Acquisition time", "Completion time"]
    values = [max(0.0, acquire_minutes), max(0.0, complete_minutes)]
    if sum(values) <= 0:
        fig.update_layout(title="Time per casket split", height=360)
        return fig

    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.35,
            sort=False,
            marker=dict(colors=["#1d4ed8", "#0f766e"]),
            textinfo="percent",
            texttemplate="%{percent:.1%}",
            hovertemplate="%{label}<br>%{value:.2f} min (%{percent:.1%})<extra></extra>",
        )
    )
    fig.update_layout(
        title="Time per casket split",
        height=430,
        margin=dict(l=20, r=20, t=90, b=95),
        legend=make_chart_legend_below(y=-0.08),
    )
    return fig


def build_end_to_end_cph_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "End-to-end caskets per hour",
            "Date",
            "Caskets per hour",
            height=PRIMARY_PACE_CHART_HEIGHT,
        )
    )
    if trend_df.empty:
        return fig

    max_raw_weight = float(
        max(
            pd.to_numeric(trend_df["raw_total_same_day_weight"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["acq_caskets"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["comp_caskets"], errors="coerce").fillna(0.0).max(),
        )
    )
    raw_total_sizes = scale_marker_sizes(
        trend_df["raw_total_same_day_weight"],
        min_size=9.0,
        max_size=32.0,
        max_weight=max_raw_weight,
    )
    raw_acq_sizes = scale_marker_sizes(
        trend_df["acq_caskets"],
        min_size=7.0,
        max_size=28.0,
        max_weight=max_raw_weight,
    )
    raw_comp_sizes = scale_marker_sizes(
        trend_df["comp_caskets"],
        min_size=7.0,
        max_size=28.0,
        max_weight=max_raw_weight,
    )
    hover_raw_total_data = trend_df[
        [
            "adjusted_acquire_minutes_per_casket",
            "adjusted_complete_minutes_per_casket",
            "adjusted_acquire_same_day_share",
            "adjusted_complete_same_day_share",
            "acq_caskets",
            "comp_caskets",
            "raw_total_same_day_weight",
        ]
    ]
    hover_span_data = trend_df[["recent_acq_ewma_span", "recent_comp_ewma_span"]]
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name="Adjusted daily total",
            legendgroup="raw_points",
            hoverinfo="skip",
            marker=dict(
                size=11,
                color="rgba(220, 38, 38, 0)",
                line=dict(color="rgba(220, 38, 38, 0.40)", width=1.5),
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["adjusted_end_to_end_caskets_per_hour"],
            mode="markers",
            name="Adjusted daily total",
            showlegend=False,
            legendgroup="raw_points",
            marker=dict(
                size=raw_total_sizes,
                color="rgba(220, 38, 38, 0)",
                line=dict(color="rgba(220, 38, 38, 0.40)", width=1.5),
            ),
            customdata=hover_raw_total_data,
            hovertemplate=(
                "%{x}<br>Adjusted daily pace: %{y:.4f} caskets/hr"
                "<br>Adjusted acquisition: %{customdata[0]:.4f} min/clue"
                "<br>Adjusted completion: %{customdata[1]:.4f} min/casket"
                "<br>Acquisition same-day weight: %{customdata[2]:.0%} from %{customdata[4]:.0f} clues"
                "<br>Completion same-day weight: %{customdata[3]:.0%} from %{customdata[5]:.0f} caskets"
                "<br>Date's total marker weight: %{customdata[6]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_end_to_end_caskets_per_hour"],
            mode="lines+markers",
            name="Recent overall",
            line=dict(color="#dc2626", width=3),
            marker=dict(color="#dc2626", size=7),
            customdata=hover_span_data,
            hovertemplate=(
                "%{x}<br>Recent overall: %{y:.2f} caskets/hr"
                "<br>Acquisition EWMA span: %{customdata[0]:.0f}"
                "<br>Completion EWMA span: %{customdata[1]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_acquire_caskets_per_hour"],
            mode="markers",
            name="Raw acquisition point",
            showlegend=False,
            legendgroup="raw_points",
            marker=dict(
                size=raw_acq_sizes,
                color="rgba(29, 78, 216, 0)",
                line=dict(color="rgba(29, 78, 216, 0.38)", width=1.5),
            ),
            customdata=trend_df[["acq_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw acquisition pace: %{y:.4f} clues/hr"
                "<br>Clues logged on this date: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_acquire_caskets_per_hour"],
            mode="lines+markers",
            name="Recent acquisition",
            line=dict(color="#1d4ed8", width=2.5),
            marker=dict(color="#1d4ed8", size=6),
            hovertemplate="%{x}<br>Recent acquisition pace: %{y:.2f} clues/hr<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_complete_caskets_per_hour"],
            mode="markers",
            name="Raw completion point",
            showlegend=False,
            legendgroup="raw_points",
            marker=dict(
                size=raw_comp_sizes,
                color="rgba(15, 118, 110, 0)",
                line=dict(color="rgba(15, 118, 110, 0.38)", width=1.5),
            ),
            customdata=trend_df[["comp_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw completion pace: %{y:.4f} caskets/hr"
                "<br>Caskets logged on this date: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_complete_caskets_per_hour"],
            mode="lines+markers",
            name="Recent completion",
            line=dict(color="#0f766e", width=2.5),
            marker=dict(color="#0f766e", size=6),
            hovertemplate="%{x}<br>Recent completion pace: %{y:.2f} caskets/hr<extra></extra>",
        )
    )
    yaxis_config = dict(
        title="Caskets per hour",
        automargin=True,
        showline=True,
        linecolor="rgba(148, 163, 184, 0.42)",
        ticks="outside",
        ticklen=5,
        tickcolor="rgba(148, 163, 184, 0.42)",
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["all_time_end_to_end_caskets_per_hour"],
            mode="lines",
            name="Overall average",
            line=dict(color="#64748b", width=2.5, dash="dot"),
            hovertemplate="%{x}<br>Overall average: %{y:.4f} caskets/hr<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=64, b=165),
        legend=make_chart_legend_below(chart_height=PRIMARY_PACE_CHART_HEIGHT),
        xaxis=dict(
            title=dict(text="Date", standoff=END_TO_END_X_TITLE_STANDOFF),
            type="category",
            tickangle=-35,
            automargin=True,
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist(),
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        yaxis=yaxis_config,
    )
    return fig


def build_end_to_end_deviation_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    chart_height = SECONDARY_DETAIL_CHART_HEIGHT
    fig.update_layout(
        title="End-to-end daily deviation",
        height=chart_height,
        margin=dict(l=40, r=40, t=CHART_TOP_MARGIN, b=LINE_CHART_BOTTOM_MARGIN),
        legend=make_chart_legend_below(y=SECONDARY_LEGEND_Y, chart_height=chart_height),
        barmode="overlay",
        bargap=0.28,
        xaxis=dict(
            title=dict(text="Date", standoff=44),
            type="category",
            tickangle=-35,
            automargin=True,
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist() if "date_label" in trend_df else [],
            showline=False,
            ticks="",
        ),
        yaxis=dict(
            title="Deviation from recent EWMA",
            ticksuffix="%",
            zeroline=False,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
    )
    if trend_df.empty:
        return fig

    d = trend_df.copy()
    adjusted_cph = pd.to_numeric(d["adjusted_end_to_end_caskets_per_hour"], errors="coerce")
    recent_cph = pd.to_numeric(d["recent_end_to_end_caskets_per_hour"], errors="coerce")
    overall_cph = pd.to_numeric(d["all_time_end_to_end_caskets_per_hour"], errors="coerce")
    d["recent_deviation_pct"] = (adjusted_cph.div(recent_cph.where(recent_cph > 0)) - 1.0) * 100.0
    d["overall_deviation_pct"] = (adjusted_cph.div(overall_cph.where(overall_cph > 0)) - 1.0) * 100.0
    d["adjusted_cph"] = adjusted_cph
    d["recent_cph"] = recent_cph
    d["overall_cph"] = overall_cph
    d["acq_caskets"] = pd.to_numeric(d["acq_caskets"], errors="coerce").fillna(0.0)
    d["comp_caskets"] = pd.to_numeric(d["comp_caskets"], errors="coerce").fillna(0.0)
    d["acq_same_day_share"] = (
        pd.to_numeric(d["adjusted_acquire_same_day_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    )
    d["comp_same_day_share"] = (
        pd.to_numeric(d["adjusted_complete_same_day_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    )

    recent_acq_minutes = pd.to_numeric(d["recent_acquire_minutes_per_casket"], errors="coerce")
    recent_comp_minutes = pd.to_numeric(d["recent_complete_minutes_per_casket"], errors="coerce")
    recent_component_total = recent_acq_minutes + recent_comp_minutes
    d["acq_time_share"] = recent_acq_minutes.div(recent_component_total.where(recent_component_total > 0))
    d["comp_time_share"] = recent_comp_minutes.div(recent_component_total.where(recent_component_total > 0))

    adjusted_acq_minutes = pd.to_numeric(d["adjusted_acquire_minutes_per_casket"], errors="coerce")
    adjusted_comp_minutes = pd.to_numeric(d["adjusted_complete_minutes_per_casket"], errors="coerce")
    adjusted_component_total = adjusted_acq_minutes + adjusted_comp_minutes
    d["acq_time_share"] = d["acq_time_share"].where(
        d["acq_time_share"].notna(),
        adjusted_acq_minutes.div(adjusted_component_total.where(adjusted_component_total > 0)),
    )
    d["comp_time_share"] = d["comp_time_share"].where(
        d["comp_time_share"].notna(),
        adjusted_comp_minutes.div(adjusted_component_total.where(adjusted_component_total > 0)),
    )
    d["acq_time_share"] = d["acq_time_share"].fillna(0.0).clip(0.0, 1.0)
    d["comp_time_share"] = d["comp_time_share"].fillna(0.0).clip(0.0, 1.0)
    d["same_day_confidence"] = (
        (d["acq_same_day_share"] * d["acq_time_share"])
        + (d["comp_same_day_share"] * d["comp_time_share"])
    ).fillna(0.0).clip(0.0, 1.0)
    visible_confidence = d["same_day_confidence"].where(d["recent_deviation_pct"].notna()).dropna()
    min_alpha = 0.18
    if visible_confidence.empty:
        weight_alpha = pd.Series(min_alpha, index=d.index, dtype=float)
    else:
        min_confidence = float(visible_confidence.min())
        max_confidence = float(visible_confidence.max())
        if max_confidence > min_confidence:
            confidence_ratio = d["same_day_confidence"].sub(min_confidence).div(max_confidence - min_confidence)
            confidence_ratio = confidence_ratio.clip(0.0, 1.0).fillna(0.0)
            weight_alpha = (min_alpha + (1.0 - min_alpha) * confidence_ratio.pow(0.85)).clip(min_alpha, 1.0)
        else:
            weight_alpha = pd.Series(1.0, index=d.index, dtype=float)
    positive_colors = [f"rgba(22, 163, 74, {alpha:.3f})" for alpha in weight_alpha]
    negative_colors = [f"rgba(225, 29, 72, {alpha:.3f})" for alpha in weight_alpha]

    positive = d["recent_deviation_pct"].where(d["recent_deviation_pct"] >= 0)
    negative = d["recent_deviation_pct"].where(d["recent_deviation_pct"] < 0)
    d["recent_deviation_label"] = d["recent_deviation_pct"].apply(
        lambda value: "" if pd.isna(value) else f"{float(value):+.1f}%"
    )
    positive_labels = d["recent_deviation_label"].where(d["recent_deviation_pct"] >= 0, "")
    negative_labels = d["recent_deviation_label"].where(d["recent_deviation_pct"] < 0, "")
    hover_data = d[
        [
            "adjusted_cph",
            "recent_cph",
            "overall_cph",
            "overall_deviation_pct",
            "same_day_confidence",
            "acq_caskets",
            "comp_caskets",
        ]
    ]
    hover_template = (
        "%{x}<br>Vs recent pace: %{y:.2f}%"
        "<br>Adjusted pace: %{customdata[0]:.4f} caskets/hr"
        "<br>Recent pace: %{customdata[1]:.4f} caskets/hr"
        "<br>Vs overall average: %{customdata[3]:.2f}%"
        "<br>Overall average: %{customdata[2]:.4f} caskets/hr"
        "<br>Daily confidence: %{customdata[4]:.0%}"
        "<br>Logged: %{customdata[5]:.0f} acquired, %{customdata[6]:.0f} completed"
        "<extra></extra>"
    )

    fig.add_trace(
        go.Bar(
            x=[None],
            y=[None],
            name="Better than recent",
            legendgroup="better_than_recent",
            marker=dict(color="#16a34a"),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Bar(
            x=[None],
            y=[None],
            name="Slower than recent",
            legendgroup="slower_than_recent",
            marker=dict(color="#e11d48"),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Bar(
            x=d["date_label"],
            y=positive,
            name="Better than recent",
            showlegend=False,
            legendgroup="better_than_recent",
            marker=dict(color=positive_colors),
            text=positive_labels,
            textposition="outside",
            texttemplate="%{text}",
            textfont=dict(color="#e5e7eb", size=11),
            cliponaxis=False,
            customdata=hover_data,
            hovertemplate=hover_template,
        )
    )
    fig.add_trace(
        go.Bar(
            x=d["date_label"],
            y=negative,
            name="Slower than recent",
            showlegend=False,
            legendgroup="slower_than_recent",
            marker=dict(color=negative_colors),
            text=negative_labels,
            textposition="outside",
            texttemplate="%{text}",
            textfont=dict(color="#e5e7eb", size=11),
            cliponaxis=False,
            customdata=hover_data,
            hovertemplate=hover_template,
        )
    )
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y",
        y0=0,
        y1=0,
        layer="above",
        line=dict(color="#ffffff", width=0.75),
    )

    return fig


def build_end_to_end_minutes_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout("End-to-end minutes per casket", "Date", "Minutes per casket", height=420)
    )
    if trend_df.empty:
        return fig

    max_raw_weight = float(
        max(
            pd.to_numeric(trend_df["raw_total_same_day_weight"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["acq_caskets"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["comp_caskets"], errors="coerce").fillna(0.0).max(),
        )
    )
    raw_total_sizes = scale_marker_sizes(
        trend_df["raw_total_same_day_weight"],
        min_size=8.0,
        max_size=20.0,
        max_weight=max_raw_weight,
    )
    raw_acq_sizes = scale_marker_sizes(
        trend_df["acq_caskets"],
        min_size=7.0,
        max_size=18.0,
        max_weight=max_raw_weight,
    )
    raw_comp_sizes = scale_marker_sizes(
        trend_df["comp_caskets"],
        min_size=7.0,
        max_size=18.0,
        max_weight=max_raw_weight,
    )
    hover_span_data = trend_df[["recent_acq_ewma_span", "recent_comp_ewma_span"]]
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["adjusted_total_minutes_per_casket"],
            mode="markers",
            name="Adjusted daily total",
            marker=dict(
                size=raw_total_sizes,
                color="rgba(220, 38, 38, 0)",
                line=dict(color="rgba(220, 38, 38, 0.40)", width=1.5),
            ),
            customdata=trend_df[
                [
                    "adjusted_acquire_minutes_per_casket",
                    "adjusted_complete_minutes_per_casket",
                    "adjusted_acquire_same_day_share",
                    "adjusted_complete_same_day_share",
                    "acq_caskets",
                    "comp_caskets",
                    "raw_total_same_day_weight",
                ]
            ],
            hovertemplate=(
                "%{x}<br>Adjusted daily total: %{y:.4f} min/casket"
                "<br>Adjusted acquisition: %{customdata[0]:.4f} min/clue"
                "<br>Adjusted completion: %{customdata[1]:.4f} min/casket"
                "<br>Acquisition same-day weight: %{customdata[2]:.0%} from %{customdata[4]:.0f} clues"
                "<br>Completion same-day weight: %{customdata[3]:.0%} from %{customdata[5]:.0f} caskets"
                "<br>Total marker weight: %{customdata[6]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_total_minutes_per_casket"],
            mode="lines+markers",
            name="Recent total (EWMA)",
            line=dict(color="#dc2626", width=3),
            marker=dict(color="#dc2626", size=7),
            customdata=hover_span_data,
            hovertemplate=(
                "%{x}<br>Recent total: %{y:.2f} min/casket"
                "<br>Acquisition EWMA span: %{customdata[0]:.0f}"
                "<br>Completion EWMA span: %{customdata[1]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_acquire_minutes_per_casket"],
            mode="markers",
            name="Raw acquisition point",
            marker=dict(
                size=raw_acq_sizes,
                color="rgba(29, 78, 216, 0)",
                line=dict(color="rgba(29, 78, 216, 0.38)", width=1.5),
            ),
            customdata=trend_df[["acq_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw acquisition: %{y:.4f} min/clue"
                "<br>Acquired clues: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_acquire_minutes_per_casket"],
            mode="lines",
            name="Recent acquisition (EWMA)",
            line=dict(color="#1d4ed8", width=2.5),
            hovertemplate="%{x}<br>Recent acquisition: %{y:.2f} min/clue<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_complete_minutes_per_casket"],
            mode="markers",
            name="Raw completion point",
            marker=dict(
                size=raw_comp_sizes,
                color="rgba(15, 118, 110, 0)",
                line=dict(color="rgba(15, 118, 110, 0.38)", width=1.5),
            ),
            customdata=trend_df[["comp_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw completion: %{y:.4f} min/casket"
                "<br>Completed caskets: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_complete_minutes_per_casket"],
            mode="lines",
            name="Recent completion (EWMA)",
            line=dict(color="#0f766e", width=2.5),
            hovertemplate="%{x}<br>Recent completion: %{y:.2f} min/casket<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["all_time_total_minutes_per_casket"],
            mode="lines",
            name="Overall average",
            line=dict(color="#64748b", width=2.5, dash="dot"),
            hovertemplate="%{x}<br>Overall average: %{y:.4f} min/casket<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=64, b=120),
        legend=make_chart_legend_below(),
        xaxis=dict(
            title="Date",
            type="category",
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist(),
        )
    )
    return fig


def build_end_to_end_income_source_pie(end_to_end_sum: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    rune_gp = float(end_to_end_sum.get("rune_armor_gp_per_clue") or 0.0)
    chaos_gp = float(end_to_end_sum.get("chaos_rune_gp_per_clue") or 0.0)
    death_gp = float(end_to_end_sum.get("death_rune_gp_per_clue") or 0.0)
    alch_gp = float(end_to_end_sum.get("expected_income_per_casket_alch") or 0.0)

    labels = [
        "Rune armor drops",
        "Chaos runes",
        "Death runes",
        "Casket alch rewards",
    ]
    values = [max(0.0, rune_gp), max(0.0, chaos_gp), max(0.0, death_gp), max(0.0, alch_gp)]
    if sum(values) <= 0:
        fig.update_layout(title="Estimated GP sources per casket", height=360)
        return fig

    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.35,
            sort=False,
            textinfo="percent",
            texttemplate="%{percent:.1%}",
            hovertemplate="%{label}<br>%{percent:.1%}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Estimated GP sources per casket",
        height=430,
        margin=dict(l=20, r=20, t=90, b=95),
        legend=make_chart_legend_below(y=-0.08),
    )
    return fig
