# utils/dq_checks.py
"""Suite de checks de calidad de datos OMOP CDM (estilo Data Quality Dashboard).

Basado en el framework de Kahn que sigue OHDSI:
    - Conformance:  estructura, FK válidas, vocabulary mapping, unicidad de PK.
    - Completeness: campos requeridos no NULL.
    - Plausibility: valores y fechas plausibles.

Cada check devuelve (n_failed, n_total). El SQL admite los placeholders
{CDM} y {VOCAB} que el runner sustituye por el esquema correspondiente.

Severidades y pesos (para el score global):
    - critical (3): viola la especificación o causa fallos en herramientas OHDSI.
    - warning  (2): degradación de calidad importante.
    - info     (1): recomendación / mejora.

Score global  = Σ(peso × (1 − fail_rate)) / Σ(peso) × 100
Estado por check:
    - PASS si fail_rate < 5%
    - WARN si 5% ≤ fail_rate < 20%
    - FAIL si fail_rate ≥ 20%
"""

SEVERITY_WEIGHT = {"critical": 3, "warning": 2, "info": 1}


def status_from_rate(rate: float) -> str:
    if rate is None:
        return "ERROR"
    if rate < 0.05:
        return "PASS"
    if rate < 0.20:
        return "WARN"
    return "FAIL"


# Marcamos como heavy=True los checks contra tablas potencialmente muy grandes
# (measurement suele tener 100M+ filas en CDMs reales). El usuario puede
# saltarlos desde la UI con "Suite rápida".
CHECKS = [
    # ── A. UNIQUENESS (PK únicas) ─────────────────────────────────────────────
    dict(name="person.person_id único",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*)-COUNT(DISTINCT person_id) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.person"),
    dict(name="visit_occurrence.visit_occurrence_id único",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*)-COUNT(DISTINCT visit_occurrence_id) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.visit_occurrence"),
    dict(name="condition_occurrence.condition_occurrence_id único",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*)-COUNT(DISTINCT condition_occurrence_id) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.condition_occurrence"),
    dict(name="drug_exposure.drug_exposure_id único",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*)-COUNT(DISTINCT drug_exposure_id) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.drug_exposure"),
    dict(name="measurement.measurement_id único",
         category="Conformance", severity="critical", heavy=True,
         sql="SELECT COUNT(*)-COUNT(DISTINCT measurement_id) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.measurement"),

    # ── B. COMPLETENESS (campos requeridos NOT NULL) ──────────────────────────
    dict(name="person.year_of_birth NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE year_of_birth IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.person"),
    dict(name="person.gender_concept_id NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE gender_concept_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.person"),
    dict(name="visit_occurrence.person_id NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.visit_occurrence"),
    dict(name="visit_occurrence.visit_start_date NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE visit_start_date IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.visit_occurrence"),
    dict(name="visit_occurrence.visit_end_date NOT NULL",
         category="Completeness", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE visit_end_date IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.visit_occurrence"),
    dict(name="condition_occurrence.person_id NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.condition_occurrence"),
    dict(name="condition_occurrence.condition_start_date NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE condition_start_date IS NULL) "
             "AS n_failed, COUNT(*) AS n_total FROM {CDM}.condition_occurrence"),
    dict(name="drug_exposure.person_id NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.drug_exposure"),
    dict(name="drug_exposure.drug_exposure_start_date NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE drug_exposure_start_date IS NULL) "
             "AS n_failed, COUNT(*) AS n_total FROM {CDM}.drug_exposure"),
    dict(name="measurement.measurement_date NOT NULL",
         category="Completeness", severity="critical", heavy=True,
         sql="SELECT COUNT(*) FILTER (WHERE measurement_date IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.measurement"),
    dict(name="procedure_occurrence.procedure_date NOT NULL",
         category="Completeness", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE procedure_date IS NULL) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.procedure_occurrence"),

    # ── C. CONFORMANCE - Vocabulary (concept_id != 0) ─────────────────────────
    dict(name="person.gender_concept_id mapeado",
         category="Conformance", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE gender_concept_id = 0) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.person"),
    dict(name="condition_occurrence.condition_concept_id mapeado",
         category="Conformance", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE condition_concept_id = 0) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.condition_occurrence"),
    dict(name="drug_exposure.drug_concept_id mapeado",
         category="Conformance", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE drug_concept_id = 0) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.drug_exposure"),
    dict(name="procedure_occurrence.procedure_concept_id mapeado",
         category="Conformance", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE procedure_concept_id = 0) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.procedure_occurrence"),
    dict(name="measurement.measurement_concept_id mapeado",
         category="Conformance", severity="warning", heavy=True,
         sql="SELECT COUNT(*) FILTER (WHERE measurement_concept_id = 0) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.measurement"),
    dict(name="visit_occurrence.visit_concept_id mapeado",
         category="Conformance", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE visit_concept_id = 0) AS n_failed, "
             "COUNT(*) AS n_total FROM {CDM}.visit_occurrence"),

    # ── D. CONFORMANCE - FK (sin huérfanos) ───────────────────────────────────
    dict(name="condition_occurrence.person_id existe en person",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE p.person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total "
             "FROM {CDM}.condition_occurrence co "
             "LEFT JOIN {CDM}.person p ON co.person_id = p.person_id"),
    dict(name="drug_exposure.person_id existe en person",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE p.person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total "
             "FROM {CDM}.drug_exposure de "
             "LEFT JOIN {CDM}.person p ON de.person_id = p.person_id"),
    dict(name="visit_occurrence.person_id existe en person",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE p.person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total "
             "FROM {CDM}.visit_occurrence v "
             "LEFT JOIN {CDM}.person p ON v.person_id = p.person_id"),
    dict(name="measurement.person_id existe en person",
         category="Conformance", severity="critical", heavy=True,
         sql="SELECT COUNT(*) FILTER (WHERE p.person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total "
             "FROM {CDM}.measurement m "
             "LEFT JOIN {CDM}.person p ON m.person_id = p.person_id"),
    dict(name="procedure_occurrence.person_id existe en person",
         category="Conformance", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE p.person_id IS NULL) AS n_failed, "
             "COUNT(*) AS n_total "
             "FROM {CDM}.procedure_occurrence po "
             "LEFT JOIN {CDM}.person p ON po.person_id = p.person_id"),

    # ── E. PLAUSIBILITY - VALUE (rangos válidos) ──────────────────────────────
    dict(name="person.year_of_birth en rango plausible [1850, año actual]",
         category="Plausibility", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER ("
             "  WHERE year_of_birth < 1850 "
             "     OR year_of_birth > EXTRACT(YEAR FROM CURRENT_DATE)"
             ") AS n_failed, "
             "COUNT(*) FILTER (WHERE year_of_birth IS NOT NULL) AS n_total "
             "FROM {CDM}.person"),
    dict(name="person.gender_concept_id en (8507, 8532, 0)",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE gender_concept_id NOT IN (8507, 8532, 0)) "
             "AS n_failed, COUNT(*) AS n_total FROM {CDM}.person"),
    dict(name="person.month_of_birth en [1, 12] (cuando informado)",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE month_of_birth NOT BETWEEN 1 AND 12) "
             "AS n_failed, "
             "COUNT(*) FILTER (WHERE month_of_birth IS NOT NULL) AS n_total "
             "FROM {CDM}.person"),

    # ── F. PLAUSIBILITY - TEMPORAL (coherencia de fechas) ─────────────────────
    dict(name="visit_occurrence: visit_end_date >= visit_start_date",
         category="Plausibility", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE visit_end_date < visit_start_date) "
             "AS n_failed, "
             "COUNT(*) FILTER (WHERE visit_end_date IS NOT NULL "
             "             AND visit_start_date IS NOT NULL) AS n_total "
             "FROM {CDM}.visit_occurrence"),
    dict(name="condition_occurrence: end_date >= start_date",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE condition_end_date < condition_start_date) "
             "AS n_failed, "
             "COUNT(*) FILTER (WHERE condition_end_date IS NOT NULL "
             "             AND condition_start_date IS NOT NULL) AS n_total "
             "FROM {CDM}.condition_occurrence"),
    dict(name="drug_exposure: end_date >= start_date",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER ("
             "  WHERE drug_exposure_end_date < drug_exposure_start_date"
             ") AS n_failed, "
             "COUNT(*) FILTER (WHERE drug_exposure_end_date IS NOT NULL "
             "             AND drug_exposure_start_date IS NOT NULL) AS n_total "
             "FROM {CDM}.drug_exposure"),
    dict(name="visit_occurrence: start_date no en el futuro",
         category="Plausibility", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE visit_start_date > CURRENT_DATE) "
             "AS n_failed, COUNT(*) FILTER (WHERE visit_start_date IS NOT NULL) "
             "AS n_total FROM {CDM}.visit_occurrence"),
    dict(name="condition_occurrence: start_date no en el futuro",
         category="Plausibility", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE condition_start_date > CURRENT_DATE) "
             "AS n_failed, COUNT(*) FILTER (WHERE condition_start_date IS NOT NULL) "
             "AS n_total FROM {CDM}.condition_occurrence"),
    dict(name="drug_exposure: start_date no en el futuro",
         category="Plausibility", severity="critical", heavy=False,
         sql="SELECT COUNT(*) FILTER (WHERE drug_exposure_start_date > CURRENT_DATE) "
             "AS n_failed, "
             "COUNT(*) FILTER (WHERE drug_exposure_start_date IS NOT NULL) "
             "AS n_total FROM {CDM}.drug_exposure"),
    dict(name="condition_occurrence: start_date >= year_of_birth del paciente",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER ("
             "  WHERE EXTRACT(YEAR FROM co.condition_start_date) < p.year_of_birth"
             ") AS n_failed, "
             "COUNT(*) FILTER (WHERE p.year_of_birth IS NOT NULL "
             "             AND co.condition_start_date IS NOT NULL) AS n_total "
             "FROM {CDM}.condition_occurrence co "
             "JOIN {CDM}.person p ON co.person_id = p.person_id"),
    dict(name="drug_exposure: start_date >= year_of_birth del paciente",
         category="Plausibility", severity="warning", heavy=False,
         sql="SELECT COUNT(*) FILTER ("
             "  WHERE EXTRACT(YEAR FROM de.drug_exposure_start_date) < p.year_of_birth"
             ") AS n_failed, "
             "COUNT(*) FILTER (WHERE p.year_of_birth IS NOT NULL "
             "             AND de.drug_exposure_start_date IS NOT NULL) AS n_total "
             "FROM {CDM}.drug_exposure de "
             "JOIN {CDM}.person p ON de.person_id = p.person_id"),

    # ── G. STANDARDIZATION (concept_id es standard) ───────────────────────────
    # Patrón: agregar por concept_id primero (reduce el JOIN con concept)
    dict(name="condition_occurrence: concept es standard ('S')",
         category="Conformance", severity="info", heavy=False,
         sql="SELECT "
             "  COALESCE(SUM(CASE WHEN c.standard_concept IS DISTINCT FROM 'S' "
             "                    THEN t.cnt END), 0) AS n_failed, "
             "  COALESCE(SUM(t.cnt), 0)              AS n_total "
             "FROM ( "
             "  SELECT condition_concept_id, COUNT(*) AS cnt "
             "  FROM {CDM}.condition_occurrence GROUP BY condition_concept_id "
             ") t LEFT JOIN {VOCAB}.concept c "
             "  ON t.condition_concept_id = c.concept_id"),
    dict(name="drug_exposure: concept es standard ('S')",
         category="Conformance", severity="info", heavy=False,
         sql="SELECT "
             "  COALESCE(SUM(CASE WHEN c.standard_concept IS DISTINCT FROM 'S' "
             "                    THEN t.cnt END), 0) AS n_failed, "
             "  COALESCE(SUM(t.cnt), 0)              AS n_total "
             "FROM ( "
             "  SELECT drug_concept_id, COUNT(*) AS cnt "
             "  FROM {CDM}.drug_exposure GROUP BY drug_concept_id "
             ") t LEFT JOIN {VOCAB}.concept c "
             "  ON t.drug_concept_id = c.concept_id"),
    dict(name="measurement: concept es standard ('S')",
         category="Conformance", severity="info", heavy=True,
         sql="SELECT "
             "  COALESCE(SUM(CASE WHEN c.standard_concept IS DISTINCT FROM 'S' "
             "                    THEN t.cnt END), 0) AS n_failed, "
             "  COALESCE(SUM(t.cnt), 0)              AS n_total "
             "FROM ( "
             "  SELECT measurement_concept_id, COUNT(*) AS cnt "
             "  FROM {CDM}.measurement GROUP BY measurement_concept_id "
             ") t LEFT JOIN {VOCAB}.concept c "
             "  ON t.measurement_concept_id = c.concept_id"),
    dict(name="procedure_occurrence: concept es standard ('S')",
         category="Conformance", severity="info", heavy=False,
         sql="SELECT "
             "  COALESCE(SUM(CASE WHEN c.standard_concept IS DISTINCT FROM 'S' "
             "                    THEN t.cnt END), 0) AS n_failed, "
             "  COALESCE(SUM(t.cnt), 0)              AS n_total "
             "FROM ( "
             "  SELECT procedure_concept_id, COUNT(*) AS cnt "
             "  FROM {CDM}.procedure_occurrence GROUP BY procedure_concept_id "
             ") t LEFT JOIN {VOCAB}.concept c "
             "  ON t.procedure_concept_id = c.concept_id"),
]
