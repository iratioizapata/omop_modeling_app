# utils/plots.py — Visualizaciones Plotly reutilizables
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

BLUE   = "#003087"
LBLUE  = "#4A90D9"
GREEN  = "#1a6b3a"
ORANGE = "#e05a00"
RED    = "#c0392b"
GREY   = "#6c757d"

PALETTE = [BLUE, LBLUE, GREEN, ORANGE, RED, "#8e44ad", "#16a085", "#d35400"]


def fig_layout(fig, title="", height=420):
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=BLUE)),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Segoe UI, Arial", size=11, color="#333"),
        margin=dict(l=40, r=20, t=50, b=40),
        height=height,
        legend=dict(bgcolor="rgba(255,255,255,0.8)", bordercolor="#ddd", borderwidth=1),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0", linecolor="#ddd")
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0", linecolor="#ddd")
    return fig


def plot_age_distribution(df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(df, x="age", nbins=30, color_discrete_sequence=[BLUE],
                       labels={"age": "Edad (años)", "count": "Pacientes"})
    fig.update_traces(marker_line_color="white", marker_line_width=0.5)
    return fig_layout(fig, "Distribución por edad")


def plot_gender_pie(df: pd.DataFrame) -> go.Figure:
    counts = df["gender"].value_counts().reset_index()
    counts.columns = ["gender", "n"]
    fig = px.pie(counts, names="gender", values="n",
                 color_discrete_sequence=PALETTE, hole=0.4)
    fig.update_traces(textposition="outside", textinfo="percent+label")
    return fig_layout(fig, "Distribución por sexo", height=360)


def plot_top_concepts(df: pd.DataFrame, col_name="concept_name",
                      col_value="n_patients", title="Top conceptos") -> go.Figure:
    df2 = df.head(15).sort_values(col_value)
    fig = px.bar(df2, x=col_value, y=col_name, orientation="h",
                 color_discrete_sequence=[BLUE],
                 labels={col_value: "N pacientes", col_name: ""})
    fig.update_traces(marker_line_color="white", marker_line_width=0.3)
    return fig_layout(fig, title, height=460)


def plot_roc_curve(fpr, tpr, auc_score: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines",
                              line=dict(color=BLUE, width=2.5),
                              name=f"ROC (AUC={auc_score:.3f})"))
    fig.add_trace(go.Scatter(x=[0,1], y=[0,1], mode="lines",
                              line=dict(color=GREY, width=1.5, dash="dash"),
                              name="Azar", showlegend=True))
    fig.update_layout(
        xaxis_title="Tasa de Falsos Positivos",
        yaxis_title="Tasa de Verdaderos Positivos",
        xaxis=dict(range=[0,1]), yaxis=dict(range=[0,1.02])
    )
    return fig_layout(fig, "Curva ROC", height=420)


def plot_precision_recall(precision, recall, avg_precision: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=recall, y=precision, mode="lines",
                              line=dict(color=GREEN, width=2.5),
                              name=f"PR (AP={avg_precision:.3f})"))
    fig.update_layout(xaxis_title="Recall", yaxis_title="Precision",
                      xaxis=dict(range=[0,1]), yaxis=dict(range=[0,1.02]))
    return fig_layout(fig, "Curva Precision-Recall", height=420)


def plot_confusion_matrix(cm: np.ndarray, labels=("No evento","Evento")) -> go.Figure:
    fig = px.imshow(cm, text_auto=True, color_continuous_scale="Blues",
                    x=list(labels), y=list(labels),
                    labels=dict(x="Predicho", y="Real", color="N"))
    fig.update_traces(textfont_size=14)
    return fig_layout(fig, "Matriz de Confusión", height=380)


def plot_feature_importance(features: list, importances: np.ndarray,
                             model_name: str = "") -> go.Figure:
    idx   = np.argsort(importances)[-20:]
    df    = pd.DataFrame({"feature": np.array(features)[idx],
                           "importance": importances[idx]})
    fig   = px.bar(df, x="importance", y="feature", orientation="h",
                   color="importance", color_continuous_scale=["#d6e4f7", BLUE],
                   labels={"importance": "Importancia", "feature": ""})
    return fig_layout(fig, f"Importancia de variables — {model_name}", height=500)


def plot_shap_beeswarm(shap_values, feature_names: list) -> go.Figure:
    """Approximación de beeswarm SHAP con scatter."""
    means = np.abs(shap_values).mean(axis=0)
    idx   = np.argsort(means)[-15:]
    rows  = []
    for i in idx:
        for sv in shap_values[:, i]:
            rows.append({"feature": feature_names[i], "shap": sv})
    df = pd.DataFrame(rows)
    fig = px.strip(df, x="shap", y="feature", color="shap",
                   color_continuous_scale=["#e74c3c", "#bdc3c7", BLUE],
                   labels={"shap": "SHAP value", "feature": ""})
    fig.add_vline(x=0, line_dash="dash", line_color=GREY)
    return fig_layout(fig, "SHAP Values — Impacto por variable", height=520)


def plot_calibration_curve(fraction_pos, mean_pred) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=mean_pred, y=fraction_pos, mode="lines+markers",
                              line=dict(color=BLUE, width=2),
                              marker=dict(size=7),
                              name="Modelo"))
    fig.add_trace(go.Scatter(x=[0,1], y=[0,1], mode="lines",
                              line=dict(color=GREY, dash="dash"),
                              name="Perfectamente calibrado"))
    fig.update_layout(xaxis_title="Probabilidad predicha",
                      yaxis_title="Fracción de positivos")
    return fig_layout(fig, "Curva de calibración", height=400)


def plot_km_curve(kmf_dict: dict) -> go.Figure:
    """kmf_dict = {label: KaplanMeierFitter object}"""
    fig = go.Figure()
    colors = PALETTE
    for i, (label, kmf) in enumerate(kmf_dict.items()):
        t  = kmf.survival_function_.index.values
        sf = kmf.survival_function_["KM_estimate"].values
        ci_lo = kmf.confidence_interval_["KM_estimate_lower_0.95"].values
        ci_hi = kmf.confidence_interval_["KM_estimate_upper_0.95"].values
        c = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=np.concatenate([t, t[::-1]]),
            y=np.concatenate([ci_hi, ci_lo[::-1]]),
            fill="toself", fillcolor=c, opacity=0.12,
            line=dict(color="rgba(0,0,0,0)"), showlegend=False))
        fig.add_trace(go.Scatter(x=t, y=sf, mode="lines",
                                  line=dict(color=c, width=2.5),
                                  name=label))
    fig.update_layout(
        xaxis_title="Tiempo (días)",
        yaxis_title="Probabilidad de supervivencia",
        yaxis=dict(range=[0, 1.05])
    )
    return fig_layout(fig, "Curvas de Kaplan-Meier", height=460)


def plot_cox_forest(summary_df: pd.DataFrame) -> go.Figure:
    """Forest plot para coeficientes Cox."""
    df = summary_df.copy()
    df["exp_coef"] = np.exp(df["coef"])
    df["exp_lo"]   = np.exp(df["coef lower 95%"])
    df["exp_hi"]   = np.exp(df["coef upper 95%"])
    df = df.sort_values("exp_coef")

    fig = go.Figure()
    for _, row in df.iterrows():
        color = RED if row["exp_coef"] > 1 else GREEN
        fig.add_trace(go.Scatter(
            x=[row["exp_lo"], row["exp_hi"]],
            y=[row.name, row.name],
            mode="lines", line=dict(color=color, width=2),
            showlegend=False))
        fig.add_trace(go.Scatter(
            x=[row["exp_coef"]], y=[row.name],
            mode="markers", marker=dict(color=color, size=10),
            showlegend=False))

    fig.add_vline(x=1, line_dash="dash", line_color=GREY)
    fig.update_layout(xaxis_title="Hazard Ratio (HR)", yaxis_title="")
    return fig_layout(fig, "Forest Plot — Hazard Ratios (Cox)", height=max(350, len(df)*40))


def plot_cohort_comparison(df: pd.DataFrame, feature: str,
                            group_col: str = "group") -> go.Figure:
    fig = px.box(df, x=group_col, y=feature, color=group_col,
                  color_discrete_sequence=PALETTE,
                  labels={group_col: "Cohorte", feature: feature})
    return fig_layout(fig, f"Comparación: {feature}", height=400)
