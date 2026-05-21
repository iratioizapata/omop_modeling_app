# pages/5_cohortes.py
import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
from utils.db import get_patient_features, run_query, CDM
from utils.plots import plot_cohort_comparison, plot_top_concepts
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Comparación de Cohortes",
                   page_icon="👥", layout="wide")
st.title("👥 Caracterización y Comparación de Cohortes")
st.markdown("""
Define dos cohortes mediante concept IDs OMOP y compara sus características
clínicas y demográficas con estadísticos de contraste.
""")

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Definir cohortes")

    st.subheader("Cohorte A (expuesta / target)")
    cohort_a_id  = st.number_input("Concept ID condición A",
                                    min_value=1, value=201826,
                                    key="cid_a",
                                    help="ej. 201826 = Diabetes T2")
    cohort_a_lbl = st.text_input("Etiqueta A", "Diabetes T2")

    st.divider()
    st.subheader("Cohorte B (control / comparadora)")
    cohort_b_id  = st.number_input("Concept ID condición B",
                                    min_value=1, value=320128,
                                    key="cid_b",
                                    help="ej. 320128 = Hipertensión")
    cohort_b_lbl = st.text_input("Etiqueta B", "Hipertensión")

    st.divider()
    lookback = st.slider("Lookback (días)", 90, 730, 365)
    min_cell = st.number_input("Mínimo por celda (privacidad)", 5, 50, 5)

    run_btn = st.button("▶ Comparar cohortes", type="primary",
                         use_container_width=True)

# ── CARGA ──────────────────────────────────────────────────────────────────────
def load_cohort(concept_id: int, label: str, lookback: int) -> pd.DataFrame:
    """Carga features para pacientes con la condición dada."""
    df = get_patient_features(
        condition_concept_ids=[concept_id],
        lookback_days=lookback
    )
    df["group"] = label
    return df


if run_btn:
    with st.spinner(f"Cargando cohorte A ({cohort_a_lbl})..."):
        try:
            df_a = load_cohort(cohort_a_id, cohort_a_lbl, lookback)
        except Exception as e:
            st.error(f"Error cohorte A: {e}"); st.stop()

    with st.spinner(f"Cargando cohorte B ({cohort_b_lbl})..."):
        try:
            df_b = load_cohort(cohort_b_id, cohort_b_lbl, lookback)
        except Exception as e:
            st.error(f"Error cohorte B: {e}"); st.stop()

    df_combined = pd.concat([df_a, df_b], ignore_index=True)
    st.session_state["cohort_a"]    = df_a
    st.session_state["cohort_b"]    = df_b
    st.session_state["cohort_comb"] = df_combined
    st.session_state["cohort_lbls"] = (cohort_a_lbl, cohort_b_lbl)
    st.success(f"✅ {len(df_a):,} en {cohort_a_lbl} | {len(df_b):,} en {cohort_b_lbl}")

# ── RESULTADOS ─────────────────────────────────────────────────────────────────
if "cohort_comb" in st.session_state:
    df_a    = st.session_state["cohort_a"]
    df_b    = st.session_state["cohort_b"]
    df_comb = st.session_state["cohort_comb"]
    lbl_a, lbl_b = st.session_state["cohort_lbls"]

    tab1, tab2, tab3 = st.tabs(
        ["📊 Tabla 1 (Características)", "📉 Gráficos", "🔬 Tests estadísticos"])

    # ── TAB 1: TABLA 1 ────────────────────────────────────────────────────────
    with tab1:
        st.subheader("Tabla 1 — Características basales de las cohortes")

        num_features = ["age", "n_distinct_conditions", "n_condition_records",
                         "n_distinct_drugs", "n_drug_records",
                         "n_visits", "n_measurements"]
        num_features = [f for f in num_features if f in df_comb.columns]

        rows = []
        for feat in num_features:
            a_vals = df_a[feat].dropna()
            b_vals = df_b[feat].dropna()
            # Mann-Whitney U
            if len(a_vals) > 5 and len(b_vals) > 5:
                stat, p = stats.mannwhitneyu(a_vals, b_vals, alternative="two-sided")
                p_str = f"{p:.4f}" if p >= 0.001 else "<0.001"
                smd   = abs(a_vals.mean() - b_vals.mean()) / (
                    np.sqrt((a_vals.std()**2 + b_vals.std()**2) / 2) + 1e-9)
            else:
                p_str, smd = "N/A", np.nan

            rows.append({
                "Variable": feat,
                f"{lbl_a} (n={len(df_a):,})":
                    f"{a_vals.mean():.1f} ± {a_vals.std():.1f}",
                f"{lbl_b} (n={len(df_b):,})":
                    f"{b_vals.mean():.1f} ± {b_vals.std():.1f}",
                "p-value":   p_str,
                "SMD":       round(smd, 3) if not np.isnan(smd) else "N/A",
                "Balanceado": "✅" if (not np.isnan(smd) and smd < 0.1) else "⚠️",
            })

        # Sexo
        if "is_male" in df_comb.columns:
            a_male = df_a["is_male"].mean()
            b_male = df_b["is_male"].mean()
            ct = pd.crosstab(df_comb["group"], df_comb["is_male"])
            if ct.shape == (2, 2):
                _, p_sex = stats.chi2_contingency(ct)[:2]
                p_str = f"{p_sex:.4f}" if p_sex >= 0.001 else "<0.001"
            else:
                p_str = "N/A"
            rows.append({
                "Variable": "Sexo masculino (%)",
                f"{lbl_a} (n={len(df_a):,})": f"{a_male:.1%}",
                f"{lbl_b} (n={len(df_b):,})": f"{b_male:.1%}",
                "p-value": p_str, "SMD": "—", "Balanceado": "—",
            })

        tabla1 = pd.DataFrame(rows)
        st.dataframe(tabla1, use_container_width=True, hide_index=True)

        st.caption("SMD < 0.1 se considera balance aceptable entre cohortes.")
        csv = tabla1.to_csv(index=False)
        st.download_button("⬇ Descargar Tabla 1", data=csv,
                            file_name="tabla1.csv", mime="text/csv")

    # ── TAB 2: GRÁFICOS ───────────────────────────────────────────────────────
    with tab2:
        feat_plot = st.selectbox("Variable a comparar",
                                  [f for f in num_features if f in df_comb.columns])
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                plot_cohort_comparison(df_comb, feat_plot, group_col="group"),
                use_container_width=True)
        with col2:
            # Distribución de edades superpuesta
            fig = px.histogram(df_comb, x=feat_plot, color="group",
                                barmode="overlay", opacity=0.65,
                                color_discrete_sequence=["#003087","#e05a00"],
                                labels={"group": "Cohorte"})
            fig.update_layout(title=f"Distribución de {feat_plot}",
                               plot_bgcolor="white", height=400)
            st.plotly_chart(fig, use_container_width=True)

        # Pirámide de edades
        if "age" in df_comb.columns and "is_male" in df_comb.columns:
            st.subheader("Pirámide de edad por cohorte y sexo")
            bins = [0,30,40,50,60,70,80,200]
            lbls = ["<30","30-39","40-49","50-59","60-69","70-79","80+"]
            df_comb["age_grp"] = pd.cut(df_comb["age"], bins=bins, labels=lbls)

            pyramid_data = []
            for grp_lbl, grp_df in [(lbl_a, df_a), (lbl_b, df_b)]:
                for sex, sex_lbl in [(1, "M"), (0, "F")]:
                    sub = grp_df[grp_df["is_male"] == sex]
                    sub = sub.copy()
                    sub["age_grp"] = pd.cut(sub["age"], bins=bins, labels=lbls)
                    counts = sub["age_grp"].value_counts().reset_index()
                    counts.columns = ["age_grp", "count"]
                    counts["group"] = grp_lbl
                    counts["sex"]   = sex_lbl
                    pyramid_data.append(counts)

            pyr_df = pd.concat(pyramid_data)
            fig_pyr = px.bar(pyr_df, x="count", y="age_grp",
                              color="group", facet_col="sex",
                              orientation="h", barmode="group",
                              color_discrete_sequence=["#003087","#e05a00"])
            fig_pyr.update_layout(height=400, plot_bgcolor="white")
            st.plotly_chart(fig_pyr, use_container_width=True)

    # ── TAB 3: TESTS ESTADÍSTICOS ─────────────────────────────────────────────
    with tab3:
        st.subheader("Tests de hipótesis — Variables continuas (Mann-Whitney U)")
        test_rows = []
        for feat in num_features:
            a_v = df_a[feat].dropna()
            b_v = df_b[feat].dropna()
            if len(a_v) > 5 and len(b_v) > 5:
                stat, p = stats.mannwhitneyu(a_v, b_v, alternative="two-sided")
                test_rows.append({
                    "Variable":    feat,
                    f"Mediana {lbl_a}": round(a_v.median(), 2),
                    f"Mediana {lbl_b}": round(b_v.median(), 2),
                    "U estadístico": round(stat, 1),
                    "p-value": round(p, 6),
                    "Significativo": "✅ Sí" if p < 0.05 else "No",
                })
        if test_rows:
            st.dataframe(pd.DataFrame(test_rows), use_container_width=True,
                          hide_index=True)

        st.subheader("Tests de hipótesis — Variables categóricas (Chi²)")
        cat_features = ["is_male"]
        chi_rows = []
        for feat in cat_features:
            if feat in df_comb.columns:
                ct = pd.crosstab(df_comb["group"], df_comb[feat])
                if ct.shape[0] >= 2 and ct.shape[1] >= 2:
                    chi2, p, _, _ = stats.chi2_contingency(ct)
                    chi_rows.append({
                        "Variable": feat,
                        "Chi²": round(chi2, 4),
                        "p-value": round(p, 6),
                        "Significativo": "✅ Sí" if p < 0.05 else "No",
                    })
        if chi_rows:
            st.dataframe(pd.DataFrame(chi_rows), use_container_width=True,
                          hide_index=True)
        else:
            st.info("Sin variables categóricas para comparar.")
