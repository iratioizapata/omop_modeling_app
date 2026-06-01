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
    {"FROM " + CDM() + ".condition_occurrence co" if outcome_concept_id else ""}
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


# ── Caracterización de la base de datos OMOP ──────────────────────────────────

def get_records_volume() -> pd.DataFrame:
    """Conteo total de registros y pacientes únicos por dominio principal."""
    parts = []
    domains = [
        ("Person",                "person",              "person_id"),
        ("Visit Occurrence",      "visit_occurrence",    "person_id"),
        ("Condition Occurrence",  "condition_occurrence","person_id"),
        ("Drug Exposure",         "drug_exposure",       "person_id"),
        ("Procedure Occurrence",  "procedure_occurrence","person_id"),
        ("Measurement",           "measurement",         "person_id"),
        ("Observation",           "observation",         "person_id"),
        ("Device Exposure",       "device_exposure",     "person_id"),
        ("Note",                  "note",                "person_id"),
        ("Death",                 "death",               "person_id"),
    ]
    for label, table, pid in domains:
        parts.append(f"""
            SELECT '{label}' AS domain,
                   COUNT(*)                AS n_records,
                   COUNT(DISTINCT {pid})   AS n_patients
            FROM {CDM()}.{table}
        """)
    sql = " UNION ALL ".join(parts) + " ORDER BY n_records DESC"
    try:
        return run_query(sql)
    except Exception:
        # Si alguna tabla no existe en el esquema, ir una a una
        rows = []
        for label, table, pid in domains:
            try:
                df = run_query(f"""
                    SELECT '{label}' AS domain,
                           COUNT(*)              AS n_records,
                           COUNT(DISTINCT {pid}) AS n_patients
                    FROM {CDM()}.{table}
                """)
                rows.append(df)
            except Exception:
                continue
        return pd.concat(rows, ignore_index=True).sort_values(
            "n_records", ascending=False) if rows else pd.DataFrame()


def get_observation_period_stats() -> pd.DataFrame:
    """Distribución del tiempo de observación por paciente (en años)."""
    return run_query(f"""
        SELECT
            person_id,
            observation_period_start_date AS start_date,
            observation_period_end_date   AS end_date,
            (observation_period_end_date - observation_period_start_date) / 365.25
                AS years_observed
        FROM {CDM()}.observation_period
        WHERE observation_period_end_date >= observation_period_start_date
    """)


def get_demographics_extended() -> pd.DataFrame:
    """Demografía con sexo, edad, año de nacimiento, raza y etnicidad."""
    return run_query(f"""
        SELECT
            p.person_id,
            c_gender.concept_name AS gender,
            EXTRACT(YEAR FROM CURRENT_DATE) - p.year_of_birth AS age,
            p.year_of_birth,
            COALESCE(c_race.concept_name,      'Unknown') AS race,
            COALESCE(c_ethnicity.concept_name, 'Unknown') AS ethnicity
        FROM {CDM()}.person p
        LEFT JOIN {CDM()}.concept c_gender    ON p.gender_concept_id    = c_gender.concept_id
        LEFT JOIN {CDM()}.concept c_race      ON p.race_concept_id      = c_race.concept_id
        LEFT JOIN {CDM()}.concept c_ethnicity ON p.ethnicity_concept_id = c_ethnicity.concept_id
        WHERE p.year_of_birth IS NOT NULL
    """)


def get_visit_types(n: int = 20) -> pd.DataFrame:
    """Distribución de tipos de encuentros médicos (urgencias, hospitalización...)."""
    return run_query(f"""
        SELECT
            c.concept_name              AS visit_type,
            COUNT(DISTINCT v.person_id) AS n_patients,
            COUNT(*)                    AS n_visits
        FROM {CDM()}.visit_occurrence v
        LEFT JOIN {CDM()}.concept c ON v.visit_concept_id = c.concept_id
        GROUP BY c.concept_name
        ORDER BY n_visits DESC
        LIMIT :n
    """, {"n": n})


def get_top_procedures(n: int = 20) -> pd.DataFrame:
    """Procedimientos más frecuentes."""
    return run_query(f"""
        SELECT
            c.concept_name,
            c.concept_code,
            c.vocabulary_id,
            COUNT(DISTINCT po.person_id) AS n_patients,
            COUNT(*)                     AS n_records
        FROM {CDM()}.procedure_occurrence po
        JOIN {CDM()}.concept c ON po.procedure_concept_id = c.concept_id
        WHERE c.concept_id != 0
        GROUP BY 1,2,3
        ORDER BY n_patients DESC
        LIMIT :n
    """, {"n": n})


def get_top_measurements(n: int = 20) -> pd.DataFrame:
    """Mediciones / pruebas de laboratorio más frecuentes."""
    return run_query(f"""
        SELECT
            c.concept_name,
            c.concept_code,
            c.vocabulary_id,
            COUNT(DISTINCT m.person_id)                                AS n_patients,
            COUNT(*)                                                   AS n_records,
            AVG(m.value_as_number) FILTER (WHERE m.value_as_number IS NOT NULL)
                                                                       AS mean_value
        FROM {CDM()}.measurement m
        JOIN {CDM()}.concept c ON m.measurement_concept_id = c.concept_id
        WHERE c.concept_id != 0
        GROUP BY 1,2,3
        ORDER BY n_patients DESC
        LIMIT :n
    """, {"n": n})


def get_notes_summary() -> pd.DataFrame:
    """Volumen de notas clínicas por tipo (texto libre)."""
    return run_query(f"""
        SELECT
            COALESCE(c.concept_name, 'Unknown') AS note_type,
            COUNT(DISTINCT n.person_id)         AS n_patients,
            COUNT(*)                            AS n_notes,
            AVG(LENGTH(n.note_text))            AS avg_text_length
        FROM {CDM()}.note n
        LEFT JOIN {CDM()}.concept c ON n.note_type_concept_id = c.concept_id
        GROUP BY c.concept_name
        ORDER BY n_notes DESC
    """)


def get_cohort_size(concept_id: int) -> int:
    """Número de pacientes con al menos un registro de la condición."""
    df = run_query(f"""
        SELECT COUNT(DISTINCT person_id) AS n
        FROM {CDM()}.condition_occurrence
        WHERE condition_concept_id = :cid
    """, {"cid": concept_id})
    return int(df["n"].iloc[0])


def get_prevalence(concept_id: int) -> dict:
    """Prevalencia: pacientes con la condición / pacientes totales."""
    df = run_query(f"""
        WITH total AS (SELECT COUNT(DISTINCT person_id) AS n FROM {CDM()}.person),
        cases AS (
            SELECT COUNT(DISTINCT person_id) AS n
            FROM {CDM()}.condition_occurrence
            WHERE condition_concept_id = :cid
        )
        SELECT t.n AS n_total, c.n AS n_cases,
               CASE WHEN t.n > 0 THEN c.n::float / t.n ELSE 0 END AS prevalence
        FROM total t, cases c
    """, {"cid": concept_id})
    r = df.iloc[0]
    return {"n_total": int(r["n_total"]),
            "n_cases": int(r["n_cases"]),
            "prevalence": float(r["prevalence"])}


def get_incidence_by_year(concept_id: int) -> pd.DataFrame:
    """Incidencia anual: nuevos casos por año (primera aparición de la condición)."""
    return run_query(f"""
        WITH first_dx AS (
            SELECT person_id,
                   MIN(condition_start_date) AS first_date
            FROM {CDM()}.condition_occurrence
            WHERE condition_concept_id = :cid
            GROUP BY person_id
        )
        SELECT
            EXTRACT(YEAR FROM first_date)::int AS year,
            COUNT(*)                           AS n_new_cases
        FROM first_dx
        GROUP BY 1
        ORDER BY 1
    """, {"cid": concept_id})


def get_cohort_comorbidities(concept_id: int, n: int = 20) -> pd.DataFrame:
    """Top condiciones concomitantes en pacientes de la cohorte (excluida la propia)."""
    return run_query(f"""
        WITH cohort AS (
            SELECT DISTINCT person_id
            FROM {CDM()}.condition_occurrence
            WHERE condition_concept_id = :cid
        )
        SELECT
            c.concept_name,
            c.concept_code,
            COUNT(DISTINCT co.person_id)              AS n_patients,
            COUNT(DISTINCT co.person_id)::float
              / NULLIF((SELECT COUNT(*) FROM cohort), 0) AS prop_cohort
        FROM {CDM()}.condition_occurrence co
        JOIN cohort                            USING (person_id)
        JOIN {CDM()}.concept c ON co.condition_concept_id = c.concept_id
        WHERE co.condition_concept_id <> :cid
          AND c.concept_id != 0
        GROUP BY 1,2
        ORDER BY n_patients DESC
        LIMIT :n
    """, {"cid": concept_id, "n": n})


def get_cohort_treatments(concept_id: int, when: str = "before",
                          window_days: int = 365, n: int = 20) -> pd.DataFrame:
    """Top fármacos en la ventana previa o posterior a la inclusión en la cohorte.

    when = 'before' | 'after'
    """
    if when == "before":
        date_filter = ("de.drug_exposure_start_date BETWEEN "
                       "idx.index_date - INTERVAL ':w days' AND idx.index_date")
    else:
        date_filter = ("de.drug_exposure_start_date BETWEEN "
                       "idx.index_date AND idx.index_date + INTERVAL ':w days'")
    date_filter = date_filter.replace(":w", str(int(window_days)))

    return run_query(f"""
        WITH idx AS (
            SELECT person_id, MIN(condition_start_date) AS index_date
            FROM {CDM()}.condition_occurrence
            WHERE condition_concept_id = :cid
            GROUP BY person_id
        )
        SELECT
            c.concept_name,
            c.concept_code,
            COUNT(DISTINCT de.person_id) AS n_patients,
            COUNT(*)                     AS n_records,
            COUNT(DISTINCT de.person_id)::float
              / NULLIF((SELECT COUNT(*) FROM idx), 0) AS prop_cohort
        FROM {CDM()}.drug_exposure de
        JOIN idx                          USING (person_id)
        JOIN {CDM()}.concept c ON de.drug_concept_id = c.concept_id
        WHERE {date_filter}
          AND c.concept_id != 0
        GROUP BY 1,2
        ORDER BY n_patients DESC
        LIMIT :n
    """, {"cid": concept_id, "n": n})


def run_dq_full(skip_heavy: bool = False, progress_cb=None) -> tuple:
    """Ejecuta la suite completa de checks DQ y devuelve (detalle_df, summary_dict).

    Parámetros:
        skip_heavy:  si True salta los checks sobre tablas muy grandes
                     (measurement principalmente).
        progress_cb: callable(i, n, check_name) opcional para actualizar UI.

    Score global ponderado por severidad:
        score = Σ(peso × (1 − fail_rate)) / Σ(peso) × 100
    """
    from utils.dq_checks import CHECKS, SEVERITY_WEIGHT, status_from_rate

    selected = [c for c in CHECKS if not (skip_heavy and c.get("heavy"))]
    results  = []

    for i, check in enumerate(selected):
        if progress_cb:
            try:
                progress_cb(i, len(selected), check["name"])
            except Exception:
                pass
        try:
            sql = check["sql"].format(CDM=CDM(), VOCAB=VOCAB())
            df  = run_query(sql)
            n_failed = int(df["n_failed"].iloc[0] or 0)
            n_total  = int(df["n_total"].iloc[0] or 0)
            if n_total == 0:
                status, pct = "N/A", None
            else:
                pct    = n_failed / n_total * 100
                status = status_from_rate(n_failed / n_total)
            results.append({
                "name":       check["name"],
                "category":   check["category"],
                "severity":   check["severity"],
                "n_failed":   n_failed,
                "n_total":    n_total,
                "pct_failed": pct,
                "status":     status,
                "error":      None,
            })
        except Exception as e:
            msg = str(e).split("\n")[0][:250]
            results.append({
                "name":       check["name"],
                "category":   check["category"],
                "severity":   check["severity"],
                "n_failed":   None,
                "n_total":    None,
                "pct_failed": None,
                "status":     "ERROR",
                "error":      msg,
            })

    df_det = pd.DataFrame(results)

    # Score global ponderado por severidad sobre checks válidos
    valid = df_det[df_det["status"].isin(["PASS", "WARN", "FAIL"])].copy()
    if len(valid):
        valid["weight"] = valid["severity"].map(SEVERITY_WEIGHT)
        valid["score"]  = 1 - valid["pct_failed"] / 100
        global_score = float(
            (valid["weight"] * valid["score"]).sum() / valid["weight"].sum() * 100
        )
    else:
        global_score = 0.0

    # Score por categoría
    cat_scores = {}
    for cat in valid["category"].unique():
        sub = valid[valid["category"] == cat]
        cat_scores[cat] = float(
            (sub["weight"] * sub["score"]).sum() / sub["weight"].sum() * 100
        )

    counts = df_det["status"].value_counts().to_dict()
    summary = {
        "global_score":    round(global_score, 2),
        "category_scores": {k: round(v, 2) for k, v in cat_scores.items()},
        "n_checks":        len(df_det),
        "n_pass":          int(counts.get("PASS",  0)),
        "n_warn":          int(counts.get("WARN",  0)),
        "n_fail":          int(counts.get("FAIL",  0)),
        "n_error":         int(counts.get("ERROR", 0)),
        "n_na":            int(counts.get("N/A",   0)),
    }
    return df_det, summary


def get_data_quality_summary() -> pd.DataFrame:
    """Métricas de calidad rápida: % de valores faltantes / no mapeados en campos clave."""
    return run_query(f"""
        SELECT
            'person.year_of_birth NULL' AS check_name,
            COUNT(*) FILTER (WHERE year_of_birth IS NULL) AS n_failed,
            COUNT(*)                                       AS n_total
        FROM {CDM()}.person
        UNION ALL
        SELECT
            'person.gender_concept_id = 0',
            COUNT(*) FILTER (WHERE gender_concept_id = 0 OR gender_concept_id IS NULL),
            COUNT(*)
        FROM {CDM()}.person
        UNION ALL
        SELECT
            'condition_occurrence.condition_concept_id = 0',
            COUNT(*) FILTER (WHERE condition_concept_id = 0),
            COUNT(*)
        FROM {CDM()}.condition_occurrence
        UNION ALL
        SELECT
            'drug_exposure.drug_concept_id = 0',
            COUNT(*) FILTER (WHERE drug_concept_id = 0),
            COUNT(*)
        FROM {CDM()}.drug_exposure
        UNION ALL
        SELECT
            'measurement.measurement_concept_id = 0',
            COUNT(*) FILTER (WHERE measurement_concept_id = 0),
            COUNT(*)
        FROM {CDM()}.measurement
    """)
