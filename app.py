# app.py — Home de la OMOP Clinical Modelling Platform
import streamlit as st

st.set_page_config(
    page_title="OMOP Clinical Modelling Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ──────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #003087; }
  [data-testid="stSidebar"] * { color: white !important; }
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stSlider label { color: #cce0ff !important; }
  .metric-card {
    background: #f0f6ff; border-left: 4px solid #003087;
    border-radius: 8px; padding: 1rem 1.4rem; margin: .4rem 0;
  }
  .feature-card {
    background: white; border: 1px solid #dee2e6;
    border-radius: 10px; padding: 1.4rem; margin: .5rem 0;
    box-shadow: 0 2px 6px rgba(0,0,0,.06);
    transition: box-shadow .2s;
  }
  .feature-card:hover { box-shadow: 0 4px 14px rgba(0,48,135,.15); }
  .badge {
    display:inline-block; padding:.25rem .75rem; border-radius:20px;
    font-size:.78rem; font-weight:600; margin:.15rem;
  }
  .badge-blue   { background:#e0ecff; color:#003087; }
  .badge-green  { background:#d4edda; color:#155724; }
  .badge-orange { background:#fde8d1; color:#8b3a00; }
</style>
""", unsafe_allow_html=True)

# ── HERO ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#003087 0%,#0052cc 100%);
            padding:2.5rem 2rem;border-radius:14px;margin-bottom:2rem;color:white">
  <h1 style="margin:0;font-size:2rem">🏥 OMOP Clinical Modelling Platform</h1>
  <p style="margin:.5rem 0 1rem;opacity:.85;font-size:1.05rem">
    Plataforma interactiva para el análisis y modelado de datos OMOP CDM
  </p>
  <span class="badge badge-blue"  style="background:rgba(255,255,255,.2);color:white">Python · Streamlit</span>
  <span class="badge badge-green" style="background:rgba(255,255,255,.2);color:white">PostgreSQL OMOP CDM</span>
  <span class="badge badge-orange"style="background:rgba(255,255,255,.2);color:white">scikit-learn · lifelines</span>
</div>
""", unsafe_allow_html=True)

# ── MÓDULOS ────────────────────────────────────────────────────────────────────
st.subheader("🗂️ Módulos disponibles")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="feature-card">
      <h3>🔌 Conexión</h3>
      <p>Configura y verifica la conexión a tu PostgreSQL OMOP CDM.
      Soporta credenciales locales y Streamlit Cloud secrets.</p>
      <span class="badge badge-blue">PostgreSQL</span>
      <span class="badge badge-blue">SQLAlchemy</span>
    </div>
    <div class="feature-card">
      <h3>🔍 Exploración</h3>
      <p>Visualiza demografía, condiciones y fármacos más prevalentes.
      Busca conceptos OMOP estándar para usar en los modelos.</p>
      <span class="badge badge-green">Plotly</span>
      <span class="badge badge-green">Interactivo</span>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="feature-card">
      <h3>🤖 Predicción Clínica</h3>
      <p>Modelos supervisados para predecir outcomes clínicos.
      Logistic Regression, Random Forest, XGBoost, LightGBM con
      ROC, PR, SHAP y calibración.</p>
      <span class="badge badge-orange">ML</span>
      <span class="badge badge-orange">SHAP</span>
      <span class="badge badge-orange">Calibración</span>
    </div>
    <div class="feature-card">
      <h3>📈 Supervivencia</h3>
      <p>Kaplan-Meier con IC 95%, test log-rank y Cox Proportional
      Hazards con forest plot de hazard ratios.</p>
      <span class="badge badge-blue">lifelines</span>
      <span class="badge badge-blue">Cox PH</span>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="feature-card">
      <h3>👥 Comparación de Cohortes</h3>
      <p>Define dos cohortes por concept ID y genera automáticamente
      la Tabla 1 con SMD, tests Mann-Whitney y Chi² para comparación.</p>
      <span class="badge badge-green">Tabla 1</span>
      <span class="badge badge-green">SMD</span>
      <span class="badge badge-green">Tests</span>
    </div>
    """, unsafe_allow_html=True)

# ── INICIO RÁPIDO ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("🚀 Inicio rápido")

with st.expander("1. Instalar y ejecutar en local", expanded=True):
    st.code("""
# Clonar el proyecto
cd omop_modeling_app

# Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

# Configurar credenciales
cp .env.example .env
# Editar .env con tus credenciales PostgreSQL

# Lanzar la app
streamlit run app.py
""", language="bash")

with st.expander("2. Desplegar en Streamlit Cloud (streamlit.io)"):
    st.markdown("""
    1. Sube el proyecto a un repositorio **GitHub** (privado recomendado)
    2. Ve a [streamlit.io](https://streamlit.io) → **New app**
    3. Conecta el repositorio y selecciona `app.py` como entry point
    4. En **Settings → Secrets** añade:

    ```toml
    [postgres]
    host     = "tu-servidor.com"
    port     = 5432
    dbname   = "omop"
    user     = "omop_user"
    password = "tu_password"
    ```
    5. Deploy — la app estará disponible en `https://tu-app.streamlit.app`

    > **Seguridad**: asegúrate de añadir `.env` y `.streamlit/secrets.toml`
    > a tu `.gitignore` antes de subir el código.
    """)

with st.expander("3. Flujo de análisis recomendado"):
    st.markdown("""
    ```
    🔌 Conexión
        ↓
    🔍 Exploración → Buscar concept_ids de outcomes
        ↓
    👥 Comparar cohortes → Verificar balance (SMD < 0.1)
        ↓
    📈 Supervivencia → Kaplan-Meier + Cox PH
        ↓
    🤖 Predicción → Entrenar modelos → Evaluar AUC + SHAP
    ```
    """)

# ── ESTADO DE SESIÓN ──────────────────────────────────────────────────────────
st.divider()
st.subheader("📋 Estado de la sesión actual")

cols = st.columns(5)
checks = [
    ("features_df",  "Features ML",      "🤖"),
    ("survival_df",  "Datos supervivencia","📈"),
    ("cohort_comb",  "Cohortes cargadas", "👥"),
    ("demographics", "Demografía",        "🔍"),
    ("ml_results",   "Modelos entrenados","✅"),
]
for col, (key, label, icon) in zip(cols, checks):
    has = key in st.session_state
    col.markdown(
        f"<div class='metric-card'>{icon} <b>{label}</b><br>"
        f"{'<span style=\"color:#1a6b3a\">✅ Listo</span>' if has else '<span style=\"color:#888\">⬜ Pendiente</span>'}"
        f"</div>",
        unsafe_allow_html=True)
