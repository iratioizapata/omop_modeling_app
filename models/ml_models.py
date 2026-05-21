# models/ml_models.py — Pipeline ML supervisado para datos OMOP
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score, roc_curve, precision_recall_curve,
    average_precision_score, confusion_matrix,
    classification_report, brier_score_loss, f1_score
)
from sklearn.calibration import calibration_curve
from imblearn.over_sampling import SMOTE
import shap
import xgboost as xgb
import lightgbm as lgb


MODELS = {
    "Logistic Regression (LASSO)": lambda: LogisticRegression(
        C=0.1, penalty="l1", solver="saga", max_iter=1000, random_state=42),
    "Logistic Regression (Ridge)": lambda: LogisticRegression(
        C=1.0, penalty="l2", solver="lbfgs", max_iter=1000, random_state=42),
    "Random Forest": lambda: RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=10,
        class_weight="balanced", random_state=42, n_jobs=-1),
    "Gradient Boosting": lambda: GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=4, random_state=42),
    "XGBoost": lambda: xgb.XGBClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=5,
        scale_pos_weight=1, eval_metric="auc",
        random_state=42, verbosity=0),
    "LightGBM": lambda: lgb.LGBMClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=5,
        class_weight="balanced", random_state=42, verbose=-1),
}

FEATURE_COLS = [
    "age", "is_male",
    "n_distinct_conditions", "n_condition_records",
    "n_distinct_drugs", "n_drug_records",
    "n_visits", "n_measurements", "avg_measurement_value",
]


def prepare_data(df: pd.DataFrame, target_col: str = "outcome",
                 test_size: float = 0.2, balance: bool = False):
    """
    Prepara X, y y hace el split train/test.
    Opcionalmente aplica SMOTE para clases desbalanceadas.
    """
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].fillna(0).astype(float)
    y = df[target_col].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=42)

    scaler = StandardScaler()
    X_train_sc = pd.DataFrame(
        scaler.fit_transform(X_train), columns=available, index=X_train.index)
    X_test_sc  = pd.DataFrame(
        scaler.transform(X_test),  columns=available, index=X_test.index)

    if balance and y_train.mean() < 0.3:
        try:
            sm = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum()-1))
            X_train_sc_arr, y_train = sm.fit_resample(X_train_sc, y_train)
            X_train_sc = pd.DataFrame(X_train_sc_arr, columns=available)
        except Exception:
            pass  # Si hay muy pocos positivos, continuar sin SMOTE

    return X_train_sc, X_test_sc, y_train, y_test, scaler, available


def train_evaluate(model_name: str, X_train, X_test, y_train, y_test,
                   feature_names: list) -> dict:
    """Entrena un modelo y devuelve todas las métricas y objetos para plots."""
    model = MODELS[model_name]()

    # Cross-validation (3-fold para rapidez)
    cv_auc = cross_val_score(
        MODELS[model_name](), X_train, y_train,
        cv=StratifiedKFold(3, shuffle=True, random_state=42),
        scoring="roc_auc", n_jobs=-1
    )

    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred       = (y_pred_proba >= 0.5).astype(int)

    fpr, tpr, _  = roc_curve(y_test, y_pred_proba)
    prec, rec, _ = precision_recall_curve(y_test, y_pred_proba)
    frac_pos, mean_pred = calibration_curve(y_test, y_pred_proba, n_bins=10)

    metrics = {
        "AUC-ROC":          round(roc_auc_score(y_test, y_pred_proba), 4),
        "AUC-PR":           round(average_precision_score(y_test, y_pred_proba), 4),
        "Brier Score":      round(brier_score_loss(y_test, y_pred_proba), 4),
        "F1 Score":         round(f1_score(y_test, y_pred), 4),
        "CV AUC (mean±sd)": f"{cv_auc.mean():.3f} ± {cv_auc.std():.3f}",
        "N train":          len(y_train),
        "N test":           len(y_test),
        "Prevalencia test": f"{y_test.mean():.2%}",
    }

    # Feature importances
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_[0])
    else:
        importances = np.zeros(len(feature_names))

    # SHAP (solo para tree-based, con sample para rapidez)
    shap_values = None
    try:
        sample = X_test.sample(min(200, len(X_test)), random_state=42)
        if model_name in ("Random Forest", "Gradient Boosting", "XGBoost", "LightGBM"):
            explainer  = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(sample)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # clase positiva
        else:
            explainer  = shap.LinearExplainer(model, X_train)
            shap_values = explainer.shap_values(sample)
    except Exception:
        pass

    return {
        "model":        model,
        "metrics":      metrics,
        "fpr": fpr, "tpr": tpr,
        "precision": prec, "recall": rec,
        "avg_precision": average_precision_score(y_test, y_pred_proba),
        "cm":           confusion_matrix(y_test, y_pred),
        "importances":  importances,
        "feature_names": feature_names,
        "shap_values":  shap_values,
        "shap_sample":  sample if shap_values is not None else None,
        "frac_pos":     frac_pos,
        "mean_pred":    mean_pred,
        "report":       classification_report(y_test, y_pred, output_dict=True),
    }


def compare_models(X_train, X_test, y_train, y_test,
                   selected_models: list, feature_names: list) -> dict:
    """Entrena y evalúa múltiples modelos para comparación."""
    results = {}
    for name in selected_models:
        with st.spinner(f"Entrenando {name}..."):
            results[name] = train_evaluate(name, X_train, X_test,
                                            y_train, y_test, feature_names)
    return results


def get_comparison_df(results: dict) -> pd.DataFrame:
    rows = []
    for name, res in results.items():
        row = {"Modelo": name}
        row.update(res["metrics"])
        rows.append(row)
    return pd.DataFrame(rows).set_index("Modelo")
