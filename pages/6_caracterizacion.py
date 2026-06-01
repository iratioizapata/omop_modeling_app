# pages/6_caracterizacion.py — Caracterización completa de la BBDD OMOP
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.db import (
    get_cohort_summary, get_records_volume, get_observation_period_stats,
    get_demographics_extended, get_visit_types, get_top_conditions,
    get_top_drugs, get_top_procedures, get_top_measurements,
    get_notes_summary, run_dq_full,
    get_prevalence, get_incidence_by_year,
)
from utils.plots import (
    plot_age_distribution, plot_gender_pie, plot_records_volume,
    plot_observation_years, plot_race_distribution,
    plot_ethnicity_distribution, plot_visit_types,
    plot_top_concepts, plot_incidence_by_year, plot_age_pyramid,
)

st.set_page_config(page_title="Caracterización OMOP",
                   page_icon="📋", layout="wide")

st.title("📋 Caracterización de la base de datos OMOP")
st.markdown("""
Análisis descriptivo completo del CDM siguiendo los ejes recomendados por
**OHDSI**: cuantificación, demografía, estructura de tablas, prevalencia,
incidencia y calidad. Equivalente local a *ATLAS* / *CohortDiagnostics*.
""")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Cuantificación", "👥 Demografía", "🗂️ Tablas OMOP",
    "📈 Prevalencia / Incidencia", "🧪 Calidad", "📥 Exportar",
])

# ── TAB 1: CUANTIFICACIÓN ─────────────────────────────────────────────────────
with tab1:
    st.subheader("Volumen global y tiempo de observación")

    if st.button("Cargar cuantificación", key="load_quant", type="primary"):
        with st.spinner("Calculando..."):
            try:
                st.session_state["car_summary"] = get_cohort_summary()
                st.session_state["car_volume"]  = get_records_volume()
            except Exception as e:
                st.error(f"Error: {e}")

        with st.spinner("Tiempo de observación..."):
            try:
                st.session_state["car_obs"] = get_observation_period_stats()
            except Exception as e:
                st.warning(f"Sin observation_period: {e}")

    if "car_summary" in st.session_state:
        s = st.session_state["car_summary"].iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👥 Pacientes únicos", f"{int(s['n_persons']):,}")
        col2.metric("🏥 Visitas totales",  f"{int(s['n_visits']):,}")
        col3.metric("📅 Primera visita",   str(s["first_visit"])[:10])
        col4.metric("📅 Última visita",    str(s["last_visit"])[:10])

    if "car_volume" in st.session_state:
        st.markdown("##### Volumen de registros por dominio")
        vol = st.session_state["car_volume"]
        st.plotly_chart(plot_records_volume(vol), use_container_width=True)
        with st.expander("📋 Tabla detallada"):
            st.dataframe(vol, use_container_width=True, hide_index=True)

    if "car_obs" in st.session_state:
        obs = st.session_state["car_obs"]
        st.markdown("##### Tiempo de observación")
        col1, col2, col3 = st.columns(3)
        col1.metric("Mediana (años)", f"{obs['years_observed'].median():.1f}")
        col2.metric("Media (años)",   f"{obs['years_observed'].mean():.1f}")
        col3.metric("Pacientes",      f"{len(obs):,}")
        st.plotly_chart(plot_observation_years(obs), use_container_width=True)

# ── TAB 2: DEMOGRAFÍA ─────────────────────────────────────────────────────────
with tab2:
    st.subheader("Distribución demográfica")

    if st.button("Cargar demografía", key="load_demo_full", type="primary"):
        with st.spinner("Cargando..."):
            try:
                st.session_state["car_demo"] = get_demographics_extended()
            except Exception as e:
                st.error(f"Error: {e}")

    if "car_demo" in st.session_state:
        df = st.session_state["car_demo"]
        st.caption(f"{len(df):,} pacientes")

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(plot_age_distribution(df), use_container_width=True)
        with col2:
            st.plotly_chart(plot_gender_pie(df), use_container_width=True)

        # Pirámide poblacional
        st.plotly_chart(plot_age_pyramid(df), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(plot_race_distribution(df),
                            use_container_width=True)
        with col2:
            st.plotly_chart(plot_ethnicity_distribution(df),
                            use_container_width=True)

        with st.expander("📊 Estadísticas descriptivas (edad)"):
            st.dataframe(df[["age"]].describe().round(1),
                          use_container_width=True)

        with st.expander("📋 Tabla de frecuencias raza × etnicidad"):
            ct = pd.crosstab(df["race"], df["ethnicity"])
            st.dataframe(ct, use_container_width=True)

# ── TAB 3: ESTRUCTURA DE TABLAS ───────────────────────────────────────────────
with tab3:
    st.subheader("Estructura y volumen por tabla clínica")
    n = st.slider("Top N por tabla", 10, 50, 20, key="car_n")

    sub1, sub2, sub3, sub4, sub5 = st.tabs(
        ["🏥 Visitas", "🩺 Condiciones", "💊 Fármacos",
         "🔬 Procedimientos", "🧪 Mediciones"])

    with sub1:
        if st.button("Cargar visitas", key="load_visits"):
            try:
                st.session_state["car_visits"] = get_visit_types(n)
            except Exception as e:
                st.error(f"Error: {e}")
        if "car_visits" in st.session_state:
            v = st.session_state["car_visits"]
            st.plotly_chart(plot_visit_types(v), use_container_width=True)
            st.dataframe(v, use_container_width=True, hide_index=True)

    with sub2:
        if st.button("Cargar condiciones", key="load_cond_car"):
            try:
                st.session_state["car_cond"] = get_top_conditions(n)
            except Exception as e:
                st.error(f"Error: {e}")
        if "car_cond" in st.session_state:
            d = st.session_state["car_cond"]
            st.plotly_chart(
                plot_top_concepts(d, title=f"Top {n} condiciones"),
                use_container_width=True)
            st.dataframe(d, use_container_width=True, hide_index=True)

    with sub3:
        if st.button("Cargar fármacos", key="load_drug_car"):
            try:
                st.session_state["car_drug"] = get_top_drugs(n)
            except Exception as e:
                st.error(f"Error: {e}")
        if "car_drug" in st.session_state:
            d = st.session_state["car_drug"]
            st.plotly_chart(
                plot_top_concepts(d, title=f"Top {n} fármacos"),
                use_container_width=True)
            st.dataframe(d, use_container_width=True, hide_index=True)

    with sub4:
        if st.button("Cargar procedimientos", key="load_proc"):
            try:
                st.session_state["car_proc"] = get_top_procedures(n)
            except Exception as e:
                st.error(f"Error: {e}")
        if "car_proc" in st.session_state:
            d = st.session_state["car_proc"]
            st.plotly_chart(
                plot_top_concepts(d, title=f"Top {n} procedimientos"),
                use_container_width=True)
            st.dataframe(d, use_container_width=True, hide_index=True)

    with sub5:
        if st.button("Cargar mediciones", key="load_meas"):
            try:
                st.session_state["car_meas"] = get_top_measurements(n)
            except Exception as e:
                st.error(f"Error: {e}")
        if "car_meas" in st.session_state:
            d = st.session_state["car_meas"]
            st.plotly_chart(
                plot_top_concepts(d, title=f"Top {n} mediciones"),
                use_container_width=True)
            st.dataframe(d, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("##### 📝 Notas clínicas")
    if st.button("Cargar resumen de notas", key="load_notes"):
        try:
            st.session_state["car_notes"] = get_notes_summary()
        except Exception as e:
            st.warning(f"Sin tabla note o vacía: {e}")
    if "car_notes" in st.session_state:
        notes = st.session_state["car_notes"]
        if len(notes):
            col1, col2 = st.columns(2)
            col1.metric("Notas totales",  f"{int(notes['n_notes'].sum()):,}")
            col2.metric("Pacientes con notas",
                        f"{int(notes['n_patients'].sum()):,}")
            st.dataframe(notes, use_container_width=True, hide_index=True)
        else:
            st.info("Sin notas clínicas registradas.")

# ── TAB 4: PREVALENCIA / INCIDENCIA ───────────────────────────────────────────
with tab4:
    st.subheader("Prevalencia e incidencia de una condición")
    st.markdown("Introduce el `concept_id` de la condición de interés "
                "(usa la página de Exploración para buscarlo).")

    col1, col2 = st.columns([2, 1])
    with col1:
        cid = st.number_input("Concept ID de la condición",
                               min_value=1, value=201826, key="prev_cid")
    with col2:
        st.write("")
        st.write("")
        run = st.button("▶ Calcular", type="primary", key="prev_btn")

    if run:
        try:
            prev = get_prevalence(int(cid))
            inc  = get_incidence_by_year(int(cid))
            st.session_state["car_prev"] = prev
            st.session_state["car_inc"]  = inc
        except Exception as e:
            st.error(f"Error: {e}")

    if "car_prev" in st.session_state:
        p = st.session_state["car_prev"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Pacientes totales", f"{p['n_total']:,}")
        col2.metric("Casos",             f"{p['n_cases']:,}")
        col3.metric("Prevalencia",       f"{p['prevalence']*100:.2f}%")

    if "car_inc" in st.session_state:
        inc = st.session_state["car_inc"]
        if len(inc):
            st.plotly_chart(plot_incidence_by_year(inc),
                            use_container_width=True)
            st.dataframe(inc, use_container_width=True, hide_index=True)
        else:
            st.info("Sin casos registrados para esta condición.")

# ── TAB 5: CALIDAD DE DATOS ───────────────────────────────────────────────────
with tab5:
    st.subheader("Auditoría completa de calidad del CDM")
    st.markdown("""
    Suite exhaustiva de checks sobre tu OMOP, basada en el **framework de Kahn**
    que sigue **OHDSI Data Quality Dashboard**. Cubre las tres dimensiones de
    calidad de datos:

    - **Conformance** — la estructura cumple la especificación (PK únicas, FK
      válidas, vocabulary mapping correcto).
    - **Completeness** — campos obligatorios no nulos.
    - **Plausibility** — valores y fechas plausibles (rangos válidos, eventos
      posteriores al nacimiento, fechas no en el futuro…).

    Cada check se pondera por **severidad**:
    🔴 critical (×3)   🟡 warning (×2)   ⚪ info (×1)

    **Score global = Σ(peso × (1 − fail_rate)) / Σ(peso) × 100**
    """)

    col1, col2 = st.columns([2, 1])
    with col1:
        skip_heavy = st.checkbox(
            "Saltar tablas pesadas (recomendado para CDMs grandes)",
            value=True,
            help="Salta checks sobre `measurement` cuando la tabla es muy grande "
                 "(suele añadir varios minutos de ejecución).")
    with col2:
        st.write("")
        run_dq = st.button("▶ Ejecutar auditoría completa",
                            type="primary", key="run_dq_full_btn")

    if run_dq:
        progress = st.progress(0.0, text="Iniciando...")
        def _cb(i, n, name):
            progress.progress((i + 1) / n,
                              text=f"{i + 1}/{n} — {name[:80]}")
        with st.spinner("Ejecutando suite de calidad..."):
            try:
                df_det, summary = run_dq_full(skip_heavy=skip_heavy,
                                                progress_cb=_cb)
                st.session_state["dq_full"] = (df_det, summary)
            except Exception as e:
                st.error(f"Error global: {e}")
        progress.empty()

    if "dq_full" in st.session_state:
        df_det, summary = st.session_state["dq_full"]
        score = summary["global_score"]

        # ── SCORE GLOBAL + INTERPRETACIÓN ─────────────────────────────────────
        st.markdown("##### 🎯 Score global de calidad")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Score",        f"{score:.1f}%")
        col2.metric("Checks",       summary["n_checks"])
        col3.metric("✅ PASS",       summary["n_pass"])
        col4.metric("⚠️ WARN",       summary["n_warn"])
        col5.metric("❌ FAIL",       summary["n_fail"])
        col6.metric("💥 Error/NA",   summary["n_error"] + summary["n_na"])

        if score >= 90:
            st.success(f"🏆 **Excelente** ({score:.1f}%) — el CDM cumple la "
                       "especificación OMOP con un nivel de incidencias muy bajo.")
        elif score >= 75:
            st.info(f"👍 **Buena calidad** ({score:.1f}%) — hay incidencias "
                    "menores; revisa los WARN para mejorarlo.")
        elif score >= 60:
            st.warning(f"⚠️ **Mejorable** ({score:.1f}%) — varios checks fallan; "
                       "los FAIL pueden invalidar análisis específicos.")
        else:
            st.error(f"❌ **Insuficiente** ({score:.1f}%) — problemas graves "
                     "que comprometen la fiabilidad de los análisis.")

        # ── SCORE POR CATEGORÍA ──────────────────────────────────────────────
        st.markdown("##### Score por categoría (Kahn framework)")
        cat_df = pd.DataFrame([
            {"Categoría": k, "Score": v}
            for k, v in summary["category_scores"].items()
        ]).sort_values("Score", ascending=False)
        fig = px.bar(cat_df, x="Categoría", y="Score", text="Score",
                      color="Score", color_continuous_scale="RdYlGn",
                      range_color=[0, 100])
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(yaxis_range=[0, 110], height=340,
                           plot_bgcolor="white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # ── FILTROS Y TABLA DE DETALLE ───────────────────────────────────────
        st.markdown("##### Detalle por check")
        col1, col2 = st.columns(2)
        with col1:
            sev_filter = st.multiselect(
                "Severidad",
                ["critical", "warning", "info"],
                default=["critical", "warning", "info"])
        with col2:
            cat_options = list(df_det["category"].unique())
            cat_filter = st.multiselect("Categoría", cat_options,
                                          default=cat_options)

        view = df_det[df_det["severity"].isin(sev_filter)
                       & df_det["category"].isin(cat_filter)].copy()

        emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌",
                 "ERROR": "💥", "N/A": "➖"}
        view["status"] = view["status"].map(lambda s: f"{emoji.get(s, '')} {s}")
        view = view.sort_values(
            ["category", "severity", "pct_failed"],
            ascending=[True, True, False], na_position="last")

        st.dataframe(
            view[["category", "severity", "name", "n_failed", "n_total",
                  "pct_failed", "status", "error"]],
            use_container_width=True, hide_index=True,
            column_config={
                "category":   "Categoría",
                "severity":   "Severidad",
                "name":       "Check",
                "n_failed":   st.column_config.NumberColumn("Fallos",
                                                              format="%d"),
                "n_total":    st.column_config.NumberColumn("Total",
                                                              format="%d"),
                "pct_failed": st.column_config.NumberColumn("% fallos",
                                                              format="%.2f"),
                "status":     "Estado",
                "error":      "Error (si aplica)",
            })

        st.caption("Estado: ✅ PASS <5%  ·  ⚠️ WARN 5-20%  ·  ❌ FAIL ≥20%  "
                   "·  💥 ERROR (query falló)  ·  ➖ N/A (tabla vacía)")

        # ── DESCARGAS ────────────────────────────────────────────────────────
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇ Descargar informe detallado (CSV)",
                                data=df_det.to_csv(index=False),
                                file_name="dq_full_report.csv",
                                mime="text/csv")
        with col2:
            import json
            st.download_button("⬇ Descargar resumen (JSON)",
                                data=json.dumps(summary, indent=2,
                                                 ensure_ascii=False),
                                file_name="dq_summary.json",
                                mime="application/json")

# ── TAB 6: EXPORTAR ───────────────────────────────────────────────────────────
with tab6:
    st.subheader("Descargar resultados")
    st.markdown("Exporta los datos calculados en esta página como CSV.")

    exportables = {
        "car_volume":  ("volumen_dominios.csv",  "Volumen por dominio"),
        "car_demo":    ("demografia.csv",        "Demografía"),
        "car_visits":  ("visit_types.csv",       "Tipos de visita"),
        "car_cond":    ("top_conditions.csv",    "Top condiciones"),
        "car_drug":    ("top_drugs.csv",         "Top fármacos"),
        "car_proc":    ("top_procedures.csv",    "Top procedimientos"),
        "car_meas":    ("top_measurements.csv",  "Top mediciones"),
        "car_notes":   ("notes_summary.csv",     "Resumen notas"),
        "car_inc":     ("incidence_by_year.csv", "Incidencia anual"),
        "car_dq":      ("data_quality.csv",      "Calidad de datos"),
    }
    available = [(k, v) for k, v in exportables.items() if k in st.session_state]
    if not available:
        st.info("Aún no has cargado nada en las otras pestañas.")
    else:
        for key, (fname, label) in available:
            df = st.session_state[key]
            if isinstance(df, pd.DataFrame):
                st.download_button(f"⬇ {label}",
                                    data=df.to_csv(index=False),
                                    file_name=fname, mime="text/csv",
                                    key=f"dl_{key}")
