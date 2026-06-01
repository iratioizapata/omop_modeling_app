# utils/dq_checks.py
"""Suite exhaustiva de checks de calidad de datos OMOP CDM v5.x.

Cobertura completa de las tablas estandarizadas:

  Clínicas:        person, observation_period, visit_occurrence, visit_detail,
                   condition_occurrence, drug_exposure, procedure_occurrence,
                   device_exposure, measurement, observation, death, note,
                   specimen
  Sistema salud:   location, care_site, provider
  Economía salud:  payer_plan_period, cost
  Derivadas:       drug_era, dose_era, condition_era

Framework de Kahn (mismo que OHDSI Data Quality Dashboard):
    - Conformance:  estructura, PK únicas, FK válidas, vocabulary mapping.
    - Completeness: campos requeridos no NULL.
    - Plausibility: rangos y fechas plausibles.

Severidades y pesos:
    - critical (3): viola la especificación o causa fallos en herramientas OHDSI.
    - warning  (2): degradación de calidad importante.
    - info     (1): recomendación / mejora.

Score por check  = 1 − n_failed / n_total
Score global     = Σ(peso × score) / Σ(peso) × 100
Estado:
    - PASS  fail_rate < 5 %
    - WARN  5 % ≤ fail_rate < 20 %
    - FAIL  fail_rate ≥ 20 %

Las tablas que no existan en el esquema CDM del usuario producirán un check
con estado ERROR (no rompen la suite — el runner captura la excepción).
"""

SEVERITY_WEIGHT = {"critical": 3, "warning": 2, "info": 1}


def status_from_rate(rate):
    if rate is None:
        return "ERROR"
    if rate < 0.05:
        return "PASS"
    if rate < 0.20:
        return "WARN"
    return "FAIL"


# Helpers para no repetir SQL mil veces
def _unique(table, pk, heavy=False):
    return dict(
        name=f"{table}.{pk} único",
        category="Conformance", severity="critical", heavy=heavy,
        sql=f"SELECT COUNT(*)-COUNT(DISTINCT {pk}) AS n_failed, "
            f"COUNT(*) AS n_total FROM {{CDM}}.{table}")


def _notnull(table, col, severity="critical", heavy=False):
    return dict(
        name=f"{table}.{col} NOT NULL",
        category="Completeness", severity=severity, heavy=heavy,
        sql=f"SELECT COUNT(*) FILTER (WHERE {col} IS NULL) AS n_failed, "
            f"COUNT(*) AS n_total FROM {{CDM}}.{table}")


def _mapped(table, col, severity="warning", heavy=False):
    return dict(
        name=f"{table}.{col} mapeado (≠ 0)",
        category="Conformance", severity=severity, heavy=heavy,
        sql=f"SELECT COUNT(*) FILTER (WHERE {col} = 0) AS n_failed, "
            f"COUNT(*) AS n_total FROM {{CDM}}.{table}")


def _fk_person(table, alias, heavy=False):
    return dict(
        name=f"{table}.person_id existe en person",
        category="Conformance", severity="critical", heavy=heavy,
        sql=f"SELECT COUNT(*) FILTER (WHERE p.person_id IS NULL) AS n_failed, "
            f"COUNT(*) AS n_total "
            f"FROM {{CDM}}.{table} {alias} "
            f"LEFT JOIN {{CDM}}.person p ON {alias}.person_id = p.person_id")


def _end_ge_start(table, start, end, severity="warning", heavy=False):
    return dict(
        name=f"{table}: {end} ≥ {start}",
        category="Plausibility", severity=severity, heavy=heavy,
        sql=f"SELECT COUNT(*) FILTER (WHERE {end} < {start}) AS n_failed, "
            f"COUNT(*) FILTER (WHERE {end} IS NOT NULL "
            f"             AND {start} IS NOT NULL) AS n_total "
            f"FROM {{CDM}}.{table}")


def _not_future(table, date_col, severity="critical", heavy=False):
    return dict(
        name=f"{table}: {date_col} no en el futuro",
        category="Plausibility", severity=severity, heavy=heavy,
        sql=f"SELECT COUNT(*) FILTER (WHERE {date_col} > CURRENT_DATE) AS n_failed, "
            f"COUNT(*) FILTER (WHERE {date_col} IS NOT NULL) AS n_total "
            f"FROM {{CDM}}.{table}")


def _ge_birthyear(table, alias, date_col, severity="warning", heavy=False):
    return dict(
        name=f"{table}: {date_col} ≥ year_of_birth del paciente",
        category="Plausibility", severity=severity, heavy=heavy,
        sql=f"SELECT COUNT(*) FILTER ("
            f"  WHERE EXTRACT(YEAR FROM {alias}.{date_col}) < p.year_of_birth"
            f") AS n_failed, "
            f"COUNT(*) FILTER (WHERE p.year_of_birth IS NOT NULL "
            f"             AND {alias}.{date_col} IS NOT NULL) AS n_total "
            f"FROM {{CDM}}.{table} {alias} "
            f"JOIN {{CDM}}.person p ON {alias}.person_id = p.person_id")


def _standard(table, concept_col, heavy=False):
    return dict(
        name=f"{table}: concept es standard ('S')",
        category="Conformance", severity="info", heavy=heavy,
        sql=f"SELECT "
            f"  COALESCE(SUM(CASE WHEN c.standard_concept IS DISTINCT FROM 'S' "
            f"                    THEN t.cnt END), 0) AS n_failed, "
            f"  COALESCE(SUM(t.cnt), 0)              AS n_total "
            f"FROM ( "
            f"  SELECT {concept_col}, COUNT(*) AS cnt "
            f"  FROM {{CDM}}.{table} GROUP BY {concept_col} "
            f") t LEFT JOIN {{VOCAB}}.concept c "
            f"  ON t.{concept_col} = c.concept_id")


# ── DEFINICIÓN DE TODOS LOS CHECKS ────────────────────────────────────────────
CHECKS = []

# ─── PERSON ──────────────────────────────────────────────────────────────────
CHECKS += [
    _unique("person", "person_id"),
    _notnull("person", "year_of_birth"),
    _notnull("person", "gender_concept_id"),
    _mapped("person", "gender_concept_id"),
    dict(name="person.gender_concept_id en (8507, 8532, 0)",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE gender_concept_id NOT IN (8507, 8532, 0)) "
             "AS n_failed, COUNT(*) AS n_total FROM {CDM}.person"),
    dict(name="person.year_of_birth en rango [1850, año actual]",
         category="Plausibility", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER ("
             "  WHERE year_of_birth < 1850 "
             "     OR year_of_birth > EXTRACT(YEAR FROM CURRENT_DATE)"
             ") AS n_failed, "
             "COUNT(*) FILTER (WHERE year_of_birth IS NOT NULL) AS n_total "
             "FROM {CDM}.person"),
    dict(name="person.month_of_birth en [1, 12]",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE month_of_birth NOT BETWEEN 1 AND 12) "
             "AS n_failed, "
             "COUNT(*) FILTER (WHERE month_of_birth IS NOT NULL) AS n_total "
             "FROM {CDM}.person"),
    dict(name="person.day_of_birth en [1, 31]",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE day_of_birth NOT BETWEEN 1 AND 31) "
             "AS n_failed, "
             "COUNT(*) FILTER (WHERE day_of_birth IS NOT NULL) AS n_total "
             "FROM {CDM}.person"),
]

# ─── OBSERVATION_PERIOD ──────────────────────────────────────────────────────
CHECKS += [
    _unique("observation_period", "observation_period_id"),
    _notnull("observation_period", "person_id"),
    _notnull("observation_period", "observation_period_start_date"),
    _notnull("observation_period", "observation_period_end_date"),
    _mapped("observation_period", "period_type_concept_id", severity="info"),
    _end_ge_start("observation_period",
                   "observation_period_start_date",
                   "observation_period_end_date",
                   severity="critical"),
    _not_future("observation_period", "observation_period_start_date"),
    _fk_person("observation_period", "op"),
]

# ─── VISIT_OCCURRENCE ────────────────────────────────────────────────────────
CHECKS += [
    _unique("visit_occurrence", "visit_occurrence_id"),
    _notnull("visit_occurrence", "person_id"),
    _notnull("visit_occurrence", "visit_start_date"),
    _notnull("visit_occurrence", "visit_end_date", severity="warning"),
    _mapped("visit_occurrence", "visit_concept_id"),
    _end_ge_start("visit_occurrence", "visit_start_date", "visit_end_date",
                   severity="critical"),
    _not_future("visit_occurrence", "visit_start_date"),
    _ge_birthyear("visit_occurrence", "v", "visit_start_date"),
    _fk_person("visit_occurrence", "v"),
    _standard("visit_occurrence", "visit_concept_id"),
]

# ─── VISIT_DETAIL ────────────────────────────────────────────────────────────
CHECKS += [
    _unique("visit_detail", "visit_detail_id", heavy=True),
    _notnull("visit_detail", "person_id", heavy=True),
    _notnull("visit_detail", "visit_detail_start_date", heavy=True),
    _notnull("visit_detail", "visit_occurrence_id", heavy=True),
    _mapped("visit_detail", "visit_detail_concept_id", heavy=True),
    _end_ge_start("visit_detail", "visit_detail_start_date",
                   "visit_detail_end_date", severity="critical", heavy=True),
    _not_future("visit_detail", "visit_detail_start_date", heavy=True),
    _fk_person("visit_detail", "vd", heavy=True),
    dict(name="visit_detail.visit_occurrence_id existe en visit_occurrence",
         category="Conformance", severity="critical", heavy=True,
         sql="SELECT COUNT(*) FILTER (WHERE v.visit_occurrence_id IS NULL) "
             "AS n_failed, COUNT(*) AS n_total "
             "FROM {CDM}.visit_detail vd "
             "LEFT JOIN {CDM}.visit_occurrence v "
             "  ON vd.visit_occurrence_id = v.visit_occurrence_id"),
]

# ─── CONDITION_OCCURRENCE ────────────────────────────────────────────────────
CHECKS += [
    _unique("condition_occurrence", "condition_occurrence_id"),
    _notnull("condition_occurrence", "person_id"),
    _notnull("condition_occurrence", "condition_start_date"),
    _mapped("condition_occurrence", "condition_concept_id"),
    _end_ge_start("condition_occurrence", "condition_start_date",
                   "condition_end_date"),
    _not_future("condition_occurrence", "condition_start_date"),
    _ge_birthyear("condition_occurrence", "co", "condition_start_date"),
    _fk_person("condition_occurrence", "co"),
    _standard("condition_occurrence", "condition_concept_id"),
]

# ─── DRUG_EXPOSURE ───────────────────────────────────────────────────────────
CHECKS += [
    _unique("drug_exposure", "drug_exposure_id"),
    _notnull("drug_exposure", "person_id"),
    _notnull("drug_exposure", "drug_exposure_start_date"),
    _mapped("drug_exposure", "drug_concept_id"),
    _end_ge_start("drug_exposure", "drug_exposure_start_date",
                   "drug_exposure_end_date"),
    _not_future("drug_exposure", "drug_exposure_start_date"),
    _ge_birthyear("drug_exposure", "de", "drug_exposure_start_date"),
    _fk_person("drug_exposure", "de"),
    _standard("drug_exposure", "drug_concept_id"),
]

# ─── PROCEDURE_OCCURRENCE ────────────────────────────────────────────────────
CHECKS += [
    _unique("procedure_occurrence", "procedure_occurrence_id"),
    _notnull("procedure_occurrence", "person_id"),
    _notnull("procedure_occurrence", "procedure_date"),
    _mapped("procedure_occurrence", "procedure_concept_id"),
    _not_future("procedure_occurrence", "procedure_date"),
    _ge_birthyear("procedure_occurrence", "po", "procedure_date"),
    _fk_person("procedure_occurrence", "po"),
    _standard("procedure_occurrence", "procedure_concept_id"),
]

# ─── DEVICE_EXPOSURE ─────────────────────────────────────────────────────────
CHECKS += [
    _unique("device_exposure", "device_exposure_id"),
    _notnull("device_exposure", "person_id"),
    _notnull("device_exposure", "device_exposure_start_date"),
    _mapped("device_exposure", "device_concept_id"),
    _end_ge_start("device_exposure", "device_exposure_start_date",
                   "device_exposure_end_date"),
    _not_future("device_exposure", "device_exposure_start_date"),
    _fk_person("device_exposure", "dvc"),
    _standard("device_exposure", "device_concept_id"),
]

# ─── MEASUREMENT (heavy) ─────────────────────────────────────────────────────
CHECKS += [
    _unique("measurement", "measurement_id", heavy=True),
    _notnull("measurement", "person_id", heavy=True),
    _notnull("measurement", "measurement_date", heavy=True),
    _mapped("measurement", "measurement_concept_id", heavy=True),
    _not_future("measurement", "measurement_date", heavy=True),
    _fk_person("measurement", "m", heavy=True),
    _standard("measurement", "measurement_concept_id", heavy=True),
]

# ─── OBSERVATION ─────────────────────────────────────────────────────────────
CHECKS += [
    _unique("observation", "observation_id", heavy=True),
    _notnull("observation", "person_id", heavy=True),
    _notnull("observation", "observation_date", heavy=True),
    _mapped("observation", "observation_concept_id", heavy=True),
    _not_future("observation", "observation_date", heavy=True),
    _fk_person("observation", "o", heavy=True),
    _standard("observation", "observation_concept_id", heavy=True),
]

# ─── DEATH ───────────────────────────────────────────────────────────────────
CHECKS += [
    _notnull("death", "person_id"),
    _notnull("death", "death_date"),
    _not_future("death", "death_date"),
    _fk_person("death", "dt"),
    _ge_birthyear("death", "dt", "death_date", severity="critical"),
    dict(name="death.person_id único (1 muerte por persona)",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*)-COUNT(DISTINCT person_id) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.death"),
]

# ─── NOTE ────────────────────────────────────────────────────────────────────
CHECKS += [
    _unique("note", "note_id", heavy=True),
    _notnull("note", "person_id", heavy=True),
    _notnull("note", "note_date", heavy=True),
    _not_future("note", "note_date", heavy=True),
    _fk_person("note", "nt", heavy=True),
]

# ─── SPECIMEN ────────────────────────────────────────────────────────────────
CHECKS += [
    _unique("specimen", "specimen_id"),
    _notnull("specimen", "person_id"),
    _notnull("specimen", "specimen_date"),
    _mapped("specimen", "specimen_concept_id", severity="info"),
    _not_future("specimen", "specimen_date"),
    _fk_person("specimen", "sp"),
]

# ─── LOCATION / CARE_SITE / PROVIDER ─────────────────────────────────────────
CHECKS += [
    _unique("location",  "location_id"),
    _unique("care_site", "care_site_id"),
    _unique("provider",  "provider_id"),
    dict(name="care_site.location_id existe en location (si informado)",
         category="Conformance", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER ("
             "  WHERE cs.location_id IS NOT NULL AND l.location_id IS NULL"
             ") AS n_failed, "
             "COUNT(*) FILTER (WHERE cs.location_id IS NOT NULL) AS n_total "
             "FROM {CDM}.care_site cs "
             "LEFT JOIN {CDM}.location l ON cs.location_id = l.location_id"),
    dict(name="provider.care_site_id existe en care_site (si informado)",
         category="Conformance", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER ("
             "  WHERE pr.care_site_id IS NOT NULL AND cs.care_site_id IS NULL"
             ") AS n_failed, "
             "COUNT(*) FILTER (WHERE pr.care_site_id IS NOT NULL) AS n_total "
             "FROM {CDM}.provider pr "
             "LEFT JOIN {CDM}.care_site cs ON pr.care_site_id = cs.care_site_id"),
]

# ─── PAYER_PLAN_PERIOD ───────────────────────────────────────────────────────
CHECKS += [
    _unique("payer_plan_period", "payer_plan_period_id"),
    _notnull("payer_plan_period", "person_id"),
    _notnull("payer_plan_period", "payer_plan_period_start_date"),
    _notnull("payer_plan_period", "payer_plan_period_end_date"),
    _end_ge_start("payer_plan_period",
                   "payer_plan_period_start_date",
                   "payer_plan_period_end_date",
                   severity="critical"),
    _fk_person("payer_plan_period", "ppp"),
]

# ─── COST ────────────────────────────────────────────────────────────────────
CHECKS += [
    _unique("cost", "cost_id", heavy=True),
    _notnull("cost", "cost_event_id", heavy=True),
]

# ─── ERAS (derived) ──────────────────────────────────────────────────────────
CHECKS += [
    _unique("drug_era", "drug_era_id"),
    _notnull("drug_era", "person_id"),
    _notnull("drug_era", "drug_era_start_date"),
    _notnull("drug_era", "drug_era_end_date"),
    _mapped("drug_era", "drug_concept_id"),
    _end_ge_start("drug_era", "drug_era_start_date", "drug_era_end_date",
                   severity="critical"),
    _fk_person("drug_era", "dre"),

    _unique("dose_era", "dose_era_id"),
    _notnull("dose_era", "person_id"),
    _end_ge_start("dose_era", "dose_era_start_date", "dose_era_end_date",
                   severity="critical"),
    _fk_person("dose_era", "doe"),

    _unique("condition_era", "condition_era_id"),
    _notnull("condition_era", "person_id"),
    _notnull("condition_era", "condition_era_start_date"),
    _notnull("condition_era", "condition_era_end_date"),
    _mapped("condition_era", "condition_concept_id"),
    _end_ge_start("condition_era",
                   "condition_era_start_date",
                   "condition_era_end_date",
                   severity="critical"),
    _fk_person("condition_era", "cer"),
]
