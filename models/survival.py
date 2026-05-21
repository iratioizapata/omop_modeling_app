# models/survival.py — Kaplan-Meier y Cox PH con lifelines
import pandas as pd
import numpy as np
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import logrank_test, multivariate_logrank_test
from lifelines.utils import concordance_index


def fit_kaplan_meier(df: pd.DataFrame,
                     duration_col: str = "duration_days",
                     event_col:    str = "event_observed",
                     group_col:    str = None) -> dict:
    """
    Ajusta una o varias curvas KM.
    Si group_col es None, ajusta una curva global.
    Devuelve {label: KaplanMeierFitter}.
    """
    kmf_dict = {}

    if group_col and group_col in df.columns:
        groups = df[group_col].dropna().unique()
        for grp in sorted(groups):
            mask = df[group_col] == grp
            kmf  = KaplanMeierFitter()
            kmf.fit(
                durations  = df.loc[mask, duration_col],
                event_observed = df.loc[mask, event_col],
                label      = str(grp)
            )
            kmf_dict[str(grp)] = kmf
    else:
        kmf = KaplanMeierFitter()
        kmf.fit(durations=df[duration_col], event_observed=df[event_col],
                label="Global")
        kmf_dict["Global"] = kmf

    return kmf_dict


def logrank_pvalue(df: pd.DataFrame,
                   duration_col: str = "duration_days",
                   event_col:    str = "event_observed",
                   group_col:    str = "gender") -> dict:
    """Test log-rank entre dos grupos."""
    groups = df[group_col].dropna().unique()
    if len(groups) < 2:
        return {"p_value": None, "test_statistic": None}

    if len(groups) == 2:
        g1, g2 = groups
        m1, m2 = df[group_col]==g1, df[group_col]==g2
        res = logrank_test(
            df.loc[m1, duration_col], df.loc[m2, duration_col],
            df.loc[m1, event_col],    df.loc[m2, event_col]
        )
        return {"p_value": round(res.p_value, 6),
                "test_statistic": round(res.test_statistic, 4),
                "groups": list(groups)}
    else:
        res = multivariate_logrank_test(
            df[duration_col], df[group_col], df[event_col])
        return {"p_value": round(res.p_value, 6),
                "test_statistic": round(res.test_statistic, 4),
                "groups": list(groups)}


def fit_cox(df: pd.DataFrame,
            duration_col:  str   = "duration_days",
            event_col:     str   = "event_observed",
            covariates:    list  = None,
            penalizer:     float = 0.1) -> dict:
    """
    Ajusta un modelo Cox PH.
    Devuelve el modelo, su resumen y el C-index.
    """
    if covariates is None:
        covariates = ["age", "is_male",
                      "n_distinct_conditions", "n_distinct_drugs",
                      "n_visits", "n_measurements"]

    available = [c for c in covariates if c in df.columns]
    cols = available + [duration_col, event_col]
    df_cox = df[cols].dropna().copy()

    # Eliminar columnas de varianza cero
    var_ok = df_cox[available].std() > 0
    available = [c for c in available if var_ok.get(c, False)]
    cols = available + [duration_col, event_col]
    df_cox = df_cox[cols]

    cph = CoxPHFitter(penalizer=penalizer)
    cph.fit(df_cox, duration_col=duration_col, event_col=event_col, show_progress=False)

    c_index = concordance_index(
        df_cox[duration_col], -cph.predict_partial_hazard(df_cox), df_cox[event_col])

    summary = cph.summary.copy()
    summary["significant"] = summary["p"] < 0.05
    summary["HR"]          = np.exp(summary["coef"])
    summary["HR_lo95"]     = np.exp(summary["coef lower 95%"])
    summary["HR_hi95"]     = np.exp(summary["coef upper 95%"])

    return {
        "model":    cph,
        "summary":  summary,
        "c_index":  round(c_index, 4),
        "n":        len(df_cox),
        "events":   int(df_cox[event_col].sum()),
        "covariates": available,
    }


def survival_summary_table(kmf_dict: dict) -> pd.DataFrame:
    """Tabla resumen: mediana de supervivencia y cuartiles por grupo."""
    rows = []
    for label, kmf in kmf_dict.items():
        med = kmf.median_survival_time_
        rows.append({
            "Grupo":     label,
            "N":         int(kmf.event_table["at_risk"].iloc[0]),
            "Eventos":   int(kmf.event_table["observed"].sum()),
            "Mediana supervivencia (días)": round(med, 1) if not np.isinf(med) else "No alcanzada",
            "Supervivencia a 1 año (%)":
                round(kmf.predict(365) * 100, 1) if 365 <= kmf.timeline.max() else "N/A",
            "Supervivencia a 3 años (%)":
                round(kmf.predict(1095) * 100, 1) if 1095 <= kmf.timeline.max() else "N/A",
        })
    return pd.DataFrame(rows)
