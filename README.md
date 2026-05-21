# OMOP Clinical Modelling Platform

Aplicación Streamlit para el análisis y modelado de datos OMOP CDM desde PostgreSQL.

## Módulos

| Página | Descripción |
|--------|-------------|
| 🔌 Conexión | Configura y verifica la conexión a PostgreSQL OMOP |
| 🔍 Exploración | Demografía, top condiciones/fármacos, búsqueda de conceptos |
| 🤖 Predicción | ML supervisado: LR, RF, XGBoost, LightGBM + ROC/PR/SHAP |
| 📈 Supervivencia | Kaplan-Meier, log-rank test, Cox PH + forest plot |
| 👥 Cohortes | Tabla 1 automática, SMD, Mann-Whitney, Chi² |

## Instalación local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # Editar con tus credenciales
streamlit run app.py
```

## Deploy en Streamlit Cloud

1. Sube a GitHub (repositorio privado)
2. [streamlit.io](https://streamlit.io) → New app → selecciona `app.py`
3. Settings → Secrets:

```toml
[postgres]
host     = "tu-servidor.com"
port     = 5432
dbname   = "omop"
user     = "omop_user"
password = "tu_password"
```

## Estructura

```
omop_modeling_app/
├── app.py                    # Home / entrada principal
├── requirements.txt
├── .env.example
├── pages/
│   ├── 1_conexion.py         # Configuración de conexión
│   ├── 2_exploracion.py      # Exploración del CDM
│   ├── 3_prediccion.py       # ML supervisado
│   ├── 4_supervivencia.py    # Kaplan-Meier + Cox PH
│   └── 5_cohortes.py         # Comparación de cohortes
├── models/
│   ├── ml_models.py          # Pipeline ML completo
│   └── survival.py           # Análisis de supervivencia
└── utils/
    ├── db.py                 # Conexión y queries OMOP
    └── plots.py              # Visualizaciones Plotly
```
