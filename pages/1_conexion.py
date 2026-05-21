# pages/1_conexion.py
import streamlit as st
from utils.db import test_connection, get_cohort_summary, get_engine
import os

st.set_page_config(page_title="Conexión OMOP", page_icon="🔌", layout="wide")

st.title("🔌 Conexión a la Base de Datos OMOP")
st.markdown("Configura y verifica la conexión a tu instancia PostgreSQL OMOP CDM.")

# ── Formulario de conexión ─────────────────────────────────────────────────────
with st.expander("⚙️ Configuración de conexión", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        host = st.text_input("Host",     value=os.getenv("DB_HOST","localhost"))
        port = st.text_input("Puerto",   value=os.getenv("DB_PORT","5432"))
        db   = st.text_input("Base de datos", value=os.getenv("DB_NAME","omop"))

    with col2:
        user = st.text_input("Usuario",    value=os.getenv("DB_USER","omop_user"))
        pwd  = st.text_input("Contraseña", type="password",
                              value=os.getenv("DB_PASSWORD",""))

    cdm_schema     = st.text_input("Esquema CDM",       value=os.getenv("CDM_SCHEMA","cdm"))
    results_schema = st.text_input("Esquema resultados", value=os.getenv("RESULTS_SCHEMA","results"))

    # Persistir en session_state
    if st.button("💾 Guardar configuración", type="primary"):
        st.session_state["db_config"] = {
            "host": host, "port": port, "dbname": db,
            "user": user, "password": pwd,
            "cdm_schema": cdm_schema, "results_schema": results_schema,
        }
        # Sobrescribir variables de entorno para que db.py las use
        os.environ["DB_HOST"]        = host
        os.environ["DB_PORT"]        = port
        os.environ["DB_NAME"]        = db
        os.environ["DB_USER"]        = user
        os.environ["DB_PASSWORD"]    = pwd
        os.environ["CDM_SCHEMA"]     = cdm_schema
        os.environ["RESULTS_SCHEMA"] = results_schema
        # Limpiar cache de conexión para que se reconecte
        get_engine.clear()
        st.success("✅ Configuración guardada")

# ── Test de conexión ───────────────────────────────────────────────────────────
st.divider()
st.subheader("🧪 Test de conexión")

if st.button("▶ Probar conexión", type="primary"):
    with st.spinner("Conectando..."):
        ok, msg = test_connection()

    if ok:
        st.success(f"✅ {msg}")
        # Cargar resumen del CDM
        with st.spinner("Cargando resumen del CDM..."):
            try:
                summary = get_cohort_summary()
                st.session_state["cdm_summary"] = summary

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("👥 Personas",    f"{int(summary['n_persons'].iloc[0]):,}")
                col2.metric("🏥 Visitas",     f"{int(summary['n_visits'].iloc[0]):,}")
                col3.metric("📅 Primera visita", str(summary['first_visit'].iloc[0])[:10])
                col4.metric("📅 Última visita",  str(summary['last_visit'].iloc[0])[:10])

            except Exception as e:
                st.warning(f"Conexión OK pero error cargando resumen: {e}")
    else:
        st.error(f"❌ Error de conexión: {msg}")
        st.info("Comprueba que PostgreSQL está activo y las credenciales son correctas.")

# ── Guía de secretos para Streamlit Cloud ─────────────────────────────────────
st.divider()
with st.expander("☁️ Cómo configurar en Streamlit Cloud"):
    st.markdown("""
    Para desplegar en **streamlit.io** sin exponer credenciales,
    crea el fichero `.streamlit/secrets.toml` en tu repositorio:

    ```toml
    [postgres]
    host     = "tu-servidor.com"
    port     = 5432
    dbname   = "omop"
    user     = "omop_user"
    password = "tu_password"
    ```

    En Streamlit Cloud → Settings → Secrets → pega el contenido del `.toml`.

    > ⚠️ **Nunca** subas `.streamlit/secrets.toml` a GitHub.
    > Añádelo a `.gitignore`.
    """)
