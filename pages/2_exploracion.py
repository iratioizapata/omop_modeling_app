# pages/2_exploracion.py
import streamlit as st
import pandas as pd
from utils.db import (get_demographics, get_top_conditions,
                       get_top_drugs, get_top_procedures,
                       get_top_measurements, get_visit_types,
                       search_concepts)
from utils.plots import (plot_age_distribution, plot_gender_pie,
                          plot_top_concepts, plot_visit_types,
                          plot_age_pyramid)

st.set_page_config(page_title="Exploración OMOP", page_icon="🔍", layout="wide")
st.title("🔍 Exploración del CDM OMOP")
st.markdown("Visualiza la población, condiciones, fármacos, procedimientos y "
            "mediciones más prevalentes.")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["👥 Demografía", "🏥 Visitas", "🩺 Condiciones", "💊 Fármacos",
     "🔬 Procedimientos", "🧪 Mediciones", "🔎 Buscar conceptos"])

# ── TAB 1: Demografía ──────────────────────────────────────────────────────────
with tab1:
    if st.button("Cargar datos demográficos", key="load_demo"):
        with st.spinner("Cargando demografía..."):
            try:
                df = get_demographics()
                st.session_state["demographics"] = df
            except Exception as e:
                st.error(f"Error: {e}")

    if "demographics" in st.session_state:
        df = st.session_state["demographics"]
        st.caption(f"{len(df):,} pacientes cargados")

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(plot_age_distribution(df), use_container_width=True)
        with col2:
            st.plotly_chart(plot_gender_pie(df), use_container_width=True)

        st.plotly_chart(plot_age_pyramid(df), use_container_width=True)

        with st.expander("📊 Estadísticas descriptivas"):
            st.dataframe(df[["age"]].describe().round(1), use_container_width=True)

        with st.expander("📋 Muestra de datos (primeras 100 filas)"):
            st.dataframe(df.head(100), use_container_width=True)

# ── TAB 2: Visitas ─────────────────────────────────────────────────────────────
with tab2:
    n_vis = st.slider("Top N tipos de visita", 5, 30, 15, key="n_vis")
    if st.button("Cargar tipos de visita", key="load_vis"):
        with st.spinner("Cargando..."):
            try:
                st.session_state["visit_types"] = get_visit_types(n_vis)
            except Exception as e:
                st.error(f"Error: {e}")

    if "visit_types" in st.session_state:
        df_vis = st.session_state["visit_types"]
        st.plotly_chart(plot_visit_types(df_vis), use_container_width=True)
        st.dataframe(df_vis, use_container_width=True, hide_index=True)

# ── TAB 3: Condiciones ─────────────────────────────────────────────────────────
with tab3:
    n_cond = st.slider("Top N condiciones", 10, 50, 20, key="n_cond")
    if st.button("Cargar condiciones", key="load_cond"):
        with st.spinner("Cargando condiciones..."):
            try:
                df_cond = get_top_conditions(n_cond)
                st.session_state["top_conditions"] = df_cond
            except Exception as e:
                st.error(f"Error: {e}")

    if "top_conditions" in st.session_state:
        df_cond = st.session_state["top_conditions"]
        st.plotly_chart(
            plot_top_concepts(df_cond, title=f"Top {n_cond} condiciones más prevalentes"),
            use_container_width=True)
        st.dataframe(df_cond, use_container_width=True)

# ── TAB 4: Fármacos ────────────────────────────────────────────────────────────
with tab4:
    n_drug = st.slider("Top N fármacos", 10, 50, 20, key="n_drug")
    if st.button("Cargar fármacos", key="load_drug"):
        with st.spinner("Cargando fármacos..."):
            try:
                df_drug = get_top_drugs(n_drug)
                st.session_state["top_drugs"] = df_drug
            except Exception as e:
                st.error(f"Error: {e}")

    if "top_drugs" in st.session_state:
        df_drug = st.session_state["top_drugs"]
        st.plotly_chart(
            plot_top_concepts(df_drug, title=f"Top {n_drug} fármacos más utilizados"),
            use_container_width=True)
        st.dataframe(df_drug, use_container_width=True)

# ── TAB 5: Procedimientos ─────────────────────────────────────────────────────
with tab5:
    n_proc = st.slider("Top N procedimientos", 10, 50, 20, key="n_proc")
    if st.button("Cargar procedimientos", key="load_proc_exp"):
        with st.spinner("Cargando procedimientos..."):
            try:
                st.session_state["top_procedures"] = get_top_procedures(n_proc)
            except Exception as e:
                st.error(f"Error: {e}")

    if "top_procedures" in st.session_state:
        df_proc = st.session_state["top_procedures"]
        st.plotly_chart(
            plot_top_concepts(df_proc, title=f"Top {n_proc} procedimientos"),
            use_container_width=True)
        st.dataframe(df_proc, use_container_width=True)

# ── TAB 6: Mediciones ─────────────────────────────────────────────────────────
with tab6:
    n_meas = st.slider("Top N mediciones", 10, 50, 20, key="n_meas")
    if st.button("Cargar mediciones", key="load_meas_exp"):
        with st.spinner("Cargando mediciones..."):
            try:
                st.session_state["top_measurements"] = get_top_measurements(n_meas)
            except Exception as e:
                st.error(f"Error: {e}")

    if "top_measurements" in st.session_state:
        df_meas = st.session_state["top_measurements"]
        st.plotly_chart(
            plot_top_concepts(df_meas, title=f"Top {n_meas} mediciones"),
            use_container_width=True)
        st.dataframe(df_meas, use_container_width=True)
        st.caption("`mean_value` = media de `value_as_number` cuando está informado.")

# ── TAB 7: Búsqueda de conceptos ──────────────────────────────────────────────
with tab7:
    st.markdown("Busca conceptos OMOP estándar para usar en los modelos.")
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Nombre del concepto", placeholder="diabetes, hypertension...")
    with col2:
        domain = st.selectbox("Dominio", ["(todos)", "Condition", "Drug",
                                           "Measurement", "Observation", "Procedure"])

    if st.button("🔎 Buscar", key="search_concept") and query:
        with st.spinner("Buscando..."):
            try:
                dom_filter = None if domain == "(todos)" else domain
                results    = search_concepts(query, domain=dom_filter)
                if len(results):
                    st.success(f"{len(results)} conceptos encontrados")
                    st.dataframe(results, use_container_width=True,
                                  column_config={
                                      "concept_id":   st.column_config.NumberColumn("ID"),
                                      "concept_name": st.column_config.TextColumn("Nombre"),
                                      "concept_code": st.column_config.TextColumn("Código"),
                                      "domain_id":    st.column_config.TextColumn("Dominio"),
                                      "vocabulary_id":st.column_config.TextColumn("Vocabulario"),
                                  })
                    st.info("💡 Copia el **concept_id** del outcome que quieres modelar "
                            "y úsalo en las páginas de Predicción o Supervivencia.")
                else:
                    st.warning("Sin resultados. Prueba otro término.")
            except Exception as e:
                st.error(f"Error: {e}")
