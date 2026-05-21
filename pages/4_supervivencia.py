# pages/4_supervivencia.py
import streamlit as st
import pandas as pd
from utils.db import get_survival_data
from utils.plots import plot_km_curve, plot_cox_forest
from models.survival import (fit_kaplan_meier, logrank_pvalue,
                               fit_cox, survival_summary_table)

st.set_page_config(page_title="Análisis de Supervivencia",
                   page_icon="📈", layout="wide")
st.title("📈 Análisis de Supervivencia")
st.markdown("""
Estima curvas de supervivencia (**Kaplan-Meier**) y factores pronósticos
(**Cox Proportional Hazards**) sobre tu población OMOP.
""")

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")

    outcome_id = st.number_input(
        "Concept ID del evento",
        min_value=1, value=4306655,
        help="Evento de interés (ej. 4306655 = Death, 201826 = Diabetes T2)")
    st.caption("🔎 Usa la página Exploración para buscar el concept_id")

    max_follow = st.slider("Seguimiento máximo (días)", 180, 3650, 1825,
                            help="1825 días = 5 años")

    st.divider()
    group_col = st.selectbox("Estratificar KM por",
                               ["(sin estratificación)", "gender",
                                "age_group", "n_visits_group"])

    st.divider()
    cox_covariates = st.multiselect(
        "Covariables para Cox",
        ["age", "is_male", "n_distinct_conditions", "n_distinct_drugs",
         "n_visits", "n_measurements", "avg_measurement_value"],
        default=["age", "is_male", "n_distinct_conditions", "n_distinct_drugs"]
    )
    cox_penalizer = st.slider("Penalización Cox (L2)", 0.0, 1.0, 0.1, 0.05)

    run_btn = st.button("▶ Ejecutar análisis", type="primary",
                         use_container_width=True)

# ── CARGA DE DATOS ─────────────────────────────────────────────────────────────
if run_btn:
    with st.spinner("Extrayendo datos de supervivencia de la BBDD..."):
        try:
            df = get_survival_data(outcome_id, max_follow)
            st.session_state["survival_df"] = df
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    n_events = int(df["event_observed"].sum())
    st.success(f"✅ {len(df):,} pacientes | {n_events:,} eventos ({n_events/len(df):.1%})")

    if n_events < 10:
        st.error("Muy pocos eventos para el análisis (< 10). "
                 "Prueba otro outcome o amplía el seguimiento.")
        st.stop()

# ── ANÁLISIS ───────────────────────────────────────────────────────────────────
if "survival_df" in st.session_state:
    df = st.session_state["survival_df"].copy()

    # Crear grupos auxiliares si se pide estratificación
    if group_col == "age_group" and "age" in df.columns:
        df["age_group"] = pd.cut(
            df["age"], bins=[0,40,60,75,200],
            labels=["<40","40-59","60-74","75+"])
        grp = "age_group"
    elif group_col == "n_visits_group" and "n_visits" in df.columns:
        df["n_visits_group"] = pd.cut(
            df["n_visits"], bins=[0,2,5,10,9999],
            labels=["1-2","3-5","6-10","10+"])
        grp = "n_visits_group"
    elif group_col == "(sin estratificación)":
        grp = None
    else:
        grp = group_col if group_col in df.columns else None

    tab1, tab2, tab3 = st.tabs(
        ["📉 Kaplan-Meier", "🌲 Cox PH", "📋 Tabla resumen"])

    # ── TAB 1: KAPLAN-MEIER ───────────────────────────────────────────────────
    with tab1:
        with st.spinner("Ajustando curvas Kaplan-Meier..."):
            kmf_dict = fit_kaplan_meier(df, group_col=grp)

        st.plotly_chart(plot_km_curve(kmf_dict), use_container_width=True)

        # Log-rank test si hay estratificación
        if grp and grp in df.columns:
            lr = logrank_pvalue(df, group_col=grp)
            if lr["p_value"] is not None:
                p = lr["p_value"]
                col1, col2 = st.columns(2)
                col1.metric("Test log-rank p-value", f"{p:.4f}")
                col2.metric("Interpretación",
                            "✅ Diferencia significativa (p<0.05)" if p < 0.05
                            else "⚠️ Sin diferencia significativa")

        # Tabla resumen
        summary_tbl = survival_summary_table(kmf_dict)
        st.dataframe(summary_tbl, use_container_width=True)

        # Predicción individual
        st.divider()
        st.subheader("🎯 Probabilidad de supervivencia a un tiempo dado")
        col1, col2 = st.columns(2)
        with col1:
            pred_time = st.number_input("Tiempo (días)", 30, max_follow, 365)
        with col2:
            grp_sel = st.selectbox("Grupo", list(kmf_dict.keys()), key="km_grp_sel")
        if st.button("Calcular"):
            kmf_sel = kmf_dict[grp_sel]
            prob    = kmf_sel.predict(pred_time)
            st.metric(f"P(supervivencia > {pred_time} días) — {grp_sel}",
                      f"{prob*100:.1f}%")

    # ── TAB 2: COX PH ─────────────────────────────────────────────────────────
    with tab2:
        if not cox_covariates:
            st.warning("Selecciona al menos una covariable en el sidebar.")
        else:
            with st.spinner("Ajustando modelo Cox PH..."):
                try:
                    cox_res = fit_cox(df, covariates=cox_covariates,
                                      penalizer=cox_penalizer)
                    st.session_state["cox_result"] = cox_res
                except Exception as e:
                    st.error(f"Error en Cox PH: {e}")
                    st.stop()

            col1, col2, col3 = st.columns(3)
            col1.metric("C-index (concordancia)", cox_res["c_index"])
            col2.metric("N pacientes",            f"{cox_res['n']:,}")
            col3.metric("N eventos",              f"{cox_res['events']:,}")

            st.caption("C-index > 0.7 indica buena discriminación")

            # Forest plot
            st.plotly_chart(
                plot_cox_forest(cox_res["summary"]),
                use_container_width=True)

            # Tabla de coeficientes
            with st.expander("📋 Tabla completa de coeficientes"):
                display_cols = ["coef","exp(coef)","se(coef)",
                                "coef lower 95%","coef upper 95%","p"]
                avail = [c for c in display_cols if c in cox_res["summary"].columns]
                st.dataframe(
                    cox_res["summary"][avail].round(4)
                    .style.apply(
                        lambda col: ["background-color: #d4edda"
                                     if v < 0.05 else "" for v in col],
                        subset=["p"]),
                    use_container_width=True)
                st.caption("Verde = p < 0.05 (estadísticamente significativo)")

            # Descargar summary Cox
            csv_cox = cox_res["summary"].round(4).to_csv()
            st.download_button("⬇ Descargar tabla Cox CSV",
                                data=csv_cox, file_name="cox_summary.csv",
                                mime="text/csv")

    # ── TAB 3: TABLA RESUMEN ──────────────────────────────────────────────────
    with tab3:
        st.subheader("Datos de supervivencia completos")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Mediana seguimiento (días)",
                      round(df["duration_days"].median(), 0))
        with col2:
            st.metric("Tasa de eventos global",
                      f"{df['event_observed'].mean():.1%}")

        st.dataframe(
            df[["person_id","age","gender","duration_days","event_observed"]]
            .head(500),
            use_container_width=True)

        csv_surv = df.to_csv(index=False)
        st.download_button("⬇ Descargar datos supervivencia CSV",
                            data=csv_surv, file_name="survival_data.csv",
                            mime="text/csv")
