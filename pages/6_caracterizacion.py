# pages/6_caracterizacion.py — Caracterización completa de la BBDD OMOP
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.db import (
    get_cohort_summary, get_records_volume, get_observation_period_stats,
    get_demographics_extended, get_visit_types, get_top_conditions,
    get_top_drugs, get_top_procedures, get_top_measurements,
    get_notes_summary, get_data_quality_summary,
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
    st.subheader("Métricas de calidad rápidas")
    st.markdown("Porcentaje de registros con campos clave nulos o no mapeados "
                "(`concept_id = 0`). Equivalente reducido a *Data Quality Dashboard*.")

    if st.button("Ejecutar checks de calidad", key="load_dq", type="primary"):
        try:
            st.session_state["car_dq"] = get_data_quality_summary()
        except Exception as e:
            st.error(f"Error: {e}")

    if "car_dq" in st.session_state:
        dq = st.session_state["car_dq"].copy()
        dq["pct_failed"] = (dq["n_failed"] / dq["n_total"].replace(0, 1)) * 100
        dq["estado"] = dq["pct_failed"].apply(
            lambda x: "✅" if x < 5 else ("⚠️" if x < 20 else "❌"))
        st.dataframe(
            dq[["check_name", "n_failed", "n_total",
                "pct_failed", "estado"]].round(2),
            use_container_width=True, hide_index=True,
            column_config={
                "check_name": "Check",
                "n_failed":   st.column_config.NumberColumn("Fallos"),
                "n_total":    st.column_config.NumberColumn("Total"),
                "pct_failed": st.column_config.NumberColumn("% fallos",
                                                              format="%.2f%%"),
                "estado":     "Estado",
            })
        st.caption("✅ <5% · ⚠️ 5-20% · ❌ >20%")

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
