# utils/db.py — Conexión a PostgreSQL OMOP y queries reutilizables
import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# ── Conexión ──────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Conectando a la base de datos...")
def get_engine():
    """Crea el engine SQLAlchemy. Usa secrets de Streamlit Cloud o .env local."""
    try:
        # Streamlit Cloud: secrets.toml
        cfg = st.secrets["postgres"]
        url = (f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
               f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}")
    except Exception:
        # Local: variables de entorno / .env
        url = (f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
               f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}"
               f"/{os.getenv('DB_NAME','omop')}")
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2)


def run_query(sql: str, params: dict = None) -> pd.DataFrame:
    """Ejecuta una query y devuelve un DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def test_connection() -> tuple[bool, str]:
    try:
        df = run_query("SELECT COUNT(*) AS n FROM " + CDM() + ".person")
        return True, f"Conexión OK — {df['n'].iloc[0]:,} personas"
    except Exception as e:
        return False, str(e)


# ── Esquemas ──────────────────────────────────────────────────────────────────

def CDM():   return os.getenv("CDM_SCHEMA",     "omop2")
def RES():   return os.getenv("RESULTS_SCHEMA", "results2")
def VOCAB(): return os.getenv("VOCAB_SCHEMA",   "omop2")

# ── Queries OMOP reutilizables ────────────────────────────────────────────────

def get_cohort_summary() -> pd.DataFrame:
    """Resumen básico de la población: n personas, rango de fechas."""
    return run_query(f"""
        SELECT
            COUNT(DISTINCT p.person_id)          AS n_persons,
            MIN(v.visit_start_date)              AS first_visit,
            MAX(v.visit_start_date)              AS last_visit,
            COUNT(DISTINCT v.visit_occurrence_id) AS n_visits
        FROM {CDM()}.person p
        LEFT JOIN {CDM()}.visit_occurrence v USING (person_id)
    """)


def get_demographics() -> pd.DataFrame:
    """Distribución por sexo, edad y año de nacimiento."""
    return run_query(f"""
        SELECT
            p.person_id,
            c_gender.concept_name                        AS gender,
            EXTRACT(YEAR FROM CURRENT_DATE) - p.year_of_birth AS age,
            p.year_of_birth,
            c_race.concept_name                          AS race
        FROM {CDM()}.person p
        LEFT JOIN {CDM()}.concept c_gender ON p.gender_concept_id  = c_gender.concept_id
        LEFT JOIN {CDM()}.concept c_race   ON p.race_concept_id    = c_race.concept_id
        WHERE p.year_of_birth IS NOT NULL
    """)


def get_top_conditions(n: int = 20) -> pd.DataFrame:
    return run_query(f"""
        SELECT
            c.concept_name,
            c.concept_code,
            c.vocabulary_id,
            COUNT(DISTINCT co.person_id) AS n_patients,
            COUNT(*)                     AS n_records
        FROM {CDM()}.condition_occurrence co
        JOIN {CDM()}.concept c ON co.condition_concept_id = c.concept_id
        WHERE c.concept_id != 0
        GROUP BY 1,2,3
        ORDER BY n_patients DESC
        LIMIT :n
    """, {"n": n})


def get_top_drugs(n: int = 20) -> pd.DataFrame:
    return run_query(f"""
        SELECT
            c.concept_name,
            c.concept_code,
            c.vocabulary_id,
            COUNT(DISTINCT de.person_id) AS n_patients,
            COUNT(*)                     AS n_records
        FROM {CDM()}.drug_exposure de
        JOIN {CDM()}.concept c ON de.drug_concept_id = c.concept_id
        WHERE c.concept_id != 0
        GROUP BY 1,2,3
        ORDER BY n_patients DESC
        LIMIT :n
    """, {"n": n})


def get_patient_features(
    condition_concept_ids: list[int] = None,
    drug_concept_ids:      list[int] = None,
    outcome_concept_id:    int       = None,
    lookback_days:         int       = 365,
    prediction_window:     int       = 365,
) -> pd.DataFrame:
    """
    Construye una tabla de features por paciente para modelado ML.
    - Variables: edad, sexo, n_condiciones, n_farmacos, n_visitas en lookback
    - Target: aparición del outcome_concept_id en el prediction_window
    """
    sql = f"""
    WITH base AS (
        -- Población base: personas con al menos una visita
        SELECT
            p.person_id,
            EXTRACT(YEAR FROM CURRENT_DATE) - p.year_of_birth AS age,
            CASE WHEN c_g.concept_name = 'MALE' THEN 1 ELSE 0 END AS is_male,
            MIN(v.visit_start_date) AS index_date
        FROM {CDM()}.person p
        JOIN {CDM()}.visit_occurrence v USING (person_id)
        LEFT JOIN {CDM()}.concept c_g ON p.gender_concept_id = c_g.concept_id
        GROUP BY p.person_id, p.year_of_birth, c_g.concept_name
    ),
    cond_count AS (
        SELECT co.person_id,
               COUNT(DISTINCT co.condition_concept_id) AS n_distinct_conditions,
               COUNT(*) AS n_condition_records
        FROM {CDM()}.condition_occurrence co
        JOIN base b ON co.person_id = b.person_id
            AND co.condition_start_date BETWEEN
                b.index_date - INTERVAL '{lookback_days} days' AND b.index_date
        GROUP BY co.person_id
    ),
    drug_count AS (
        SELECT de.person_id,
               COUNT(DISTINCT de.drug_concept_id) AS n_distinct_drugs,
               COUNT(*) AS n_drug_records
        FROM {CDM()}.drug_exposure de
        JOIN base b ON de.person_id = b.person_id
            AND de.drug_exposure_start_date BETWEEN
                b.index_date - INTERVAL '{lookback_days} days' AND b.index_date
        GROUP BY de.person_id
    ),
    visit_count AS (
        SELECT v.person_id,
               COUNT(*) AS n_visits
        FROM {CDM()}.visit_occurrence v
        JOIN base b ON v.person_id = b.person_id
            AND v.visit_start_date BETWEEN
                b.index_date - INTERVAL '{lookback_days} days' AND b.index_date
        GROUP BY v.person_id
    ),
    meas_stats AS (
        SELECT m.person_id,
               COUNT(*) AS n_measurements,
               AVG(m.value_as_number) FILTER (WHERE m.value_as_number IS NOT NULL) AS avg_measurement_value
        FROM {CDM()}.measurement m
        JOIN base b ON m.person_id = b.person_id
            AND m.measurement_date BETWEEN
                b.index_date - INTERVAL '{lookback_days} days' AND b.index_date
        GROUP BY m.person_id
    )
    {"," if outcome_concept_id else ""}
    {"outcome AS (" if outcome_concept_id else ""}
    {"SELECT DISTINCT co.person_id, 1 AS has_outcome" if outcome_concept_id else ""}
    {"FROM " + CDM + ".condition_occurrence co" if outcome_concept_id else ""}
    {"JOIN base b ON co.person_id = b.person_id" if outcome_concept_id else ""}
    {"AND co.condition_start_date BETWEEN b.index_date AND b.index_date + INTERVAL '" + str(prediction_window) + " days'" if outcome_concept_id else ""}
    {"WHERE co.condition_concept_id = " + str(outcome_concept_id) if outcome_concept_id else ""}
    {")" if outcome_concept_id else ""}
    SELECT
        b.person_id,
        b.age,
        b.is_male,
        b.index_date,
        COALESCE(cc.n_distinct_conditions, 0) AS n_distinct_conditions,
        COALESCE(cc.n_condition_records,   0) AS n_condition_records,
        COALESCE(dc.n_distinct_drugs,      0) AS n_distinct_drugs,
        COALESCE(dc.n_drug_records,        0) AS n_drug_records,
        COALESCE(vc.n_visits,              0) AS n_visits,
        COALESCE(ms.n_measurements,        0) AS n_measurements,
        COALESCE(ms.avg_measurement_value, 0) AS avg_measurement_value
        {", COALESCE(o.has_outcome, 0) AS outcome" if outcome_concept_id else ""}
    FROM base b
    LEFT JOIN cond_count  cc ON b.person_id = cc.person_id
    LEFT JOIN drug_count  dc ON b.person_id = dc.person_id
    LEFT JOIN visit_count vc ON b.person_id = vc.person_id
    LEFT JOIN meas_stats  ms ON b.person_id = ms.person_id
    {"LEFT JOIN outcome o ON b.person_id = o.person_id" if outcome_concept_id else ""}
    WHERE b.age BETWEEN 18 AND 110
    """
    return run_query(sql)


def get_survival_data(outcome_concept_id: int, max_follow_days: int = 1825) -> pd.DataFrame:
    """
    Datos para análisis de supervivencia:
    - T: días desde primera visita hasta outcome o censura
    - E: 1 si evento ocurrió, 0 si censurado
    """
    return run_query(f"""
    WITH index_dates AS (
        SELECT person_id, MIN(visit_start_date) AS index_date
        FROM {CDM()}.visit_occurrence
        GROUP BY person_id
    ),
    last_obs AS (
        SELECT person_id, MAX(visit_start_date) AS last_date
        FROM {CDM()}.visit_occurrence
        GROUP BY person_id
    ),
    events AS (
        SELECT DISTINCT co.person_id,
               MIN(co.condition_start_date) AS event_date
        FROM {CDM()}.condition_occurrence co
        WHERE co.condition_concept_id = :outcome_id
        GROUP BY co.person_id
    ),
    demographics AS (
        SELECT p.person_id,
               EXTRACT(YEAR FROM CURRENT_DATE) - p.year_of_birth AS age,
               c.concept_name AS gender
        FROM {CDM()}.person p
        LEFT JOIN {CDM()}.concept c ON p.gender_concept_id = c.concept_id
    )
    SELECT
        i.person_id,
        d.age,
        d.gender,
        CASE WHEN e.event_date IS NOT NULL
             THEN LEAST((e.event_date - i.index_date), :max_days)
             ELSE LEAST((l.last_date - i.index_date), :max_days)
        END AS duration_days,
        CASE WHEN e.event_date IS NOT NULL
              AND (e.event_date - i.index_date) <= :max_days
             THEN 1 ELSE 0
        END AS event_observed
    FROM index_dates i
    JOIN last_obs     l ON i.person_id = l.person_id
    JOIN demographics d ON i.person_id = d.person_id
    LEFT JOIN events  e ON i.person_id = e.person_id
    WHERE i.index_date IS NOT NULL
      AND (l.last_date - i.index_date) > 0
    """, {"outcome_id": outcome_concept_id, "max_days": max_follow_days})


def search_concepts(query: str, domain: str = None, limit: int = 50) -> pd.DataFrame:
    """Busca conceptos OMOP por nombre."""
    domain_filter = f"AND domain_id = '{domain}'" if domain else ""
    return run_query(f"""
        SELECT concept_id, concept_name, concept_code,
               domain_id, vocabulary_id, standard_concept
        FROM {VOCAB()}.concept
        WHERE LOWER(concept_name) LIKE LOWER(:q)
          AND standard_concept = 'S'
          AND invalid_reason IS NULL
          {domain_filter}
        ORDER BY concept_name
        LIMIT :lim
    """, {"q": f"%{query}%", "lim": limit})
