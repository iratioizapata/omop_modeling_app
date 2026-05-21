# pages/3_prediccion.py
import streamlit as st
import pandas as pd
import numpy as np
from utils.db import get_patient_features
from utils.plots import (plot_roc_curve, plot_precision_recall,
                          plot_confusion_matrix, plot_feature_importance,
                          plot_shap_beeswarm, plot_calibration_curve)
from models.ml_models import (MODELS, prepare_data, train_evaluate,
                                compare_models, get_comparison_df)

st.set_page_config(page_title="Predicción Clínica", page_icon="🤖", layout="wide")
st.title("🤖 Predicción Clínica — ML Supervisado")
st.markdown("""
Construye modelos predictivos sobre tu población OMOP.
Define el **outcome** (lo que quieres predecir), ajusta los parámetros y
evalúa los modelos con métricas clínicas estándar.
""")

# ── SIDEBAR: Configuración ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración del análisis")

    st.subheader("Outcome (variable a predecir)")
    outcome_concept_id = st.number_input(
        "Concept ID del outcome",
        min_value=0, value=201826,
        help="Concept ID OMOP del diagnóstico/evento a predecir (ej. 201826 = Diabetes T2)")
    st.caption("🔎 Usa la página Exploración para buscar el concept_id")

    st.subheader("Ventanas temporales")
    lookback  = st.slider("Lookback (días de historial previo)", 90, 730, 365)
    pred_win  = st.slider("Prediction window (días de seguimiento)", 90, 730, 365)

    st.subheader("Modelos a entrenar")
    selected_models = st.multiselect(
        "Selecciona modelos",
        list(MODELS.keys()),
        default=["Logistic Regression (LASSO)", "Random Forest", "XGBoost"])

    st.subheader("Opciones")
    test_size = st.slider("% test",        10, 40, 20) / 100
    balance   = st.checkbox("Balancear clases (SMOTE)", value=True,
                              help="Recomendado si el outcome es raro (<10%)")

    run_btn = st.button("🚀 Ejecutar modelos", type="primary",
                         use_container_width=True)

# ── CARGA DE DATOS ─────────────────────────────────────────────────────────────
if run_btn:
    if not selected_models:
        st.error("Selecciona al menos un modelo.")
        st.stop()

    with st.spinner("Extrayendo features de la BBDD OMOP..."):
        try:
            df = get_patient_features(
                outcome_concept_id = outcome_concept_id if outcome_concept_id > 0 else None,
                lookback_days      = lookback,
                prediction_window  = pred_win,
            )
            st.session_state["features_df"]    = df
            st.session_state["outcome_id"]     = outcome_concept_id
        except Exception as e:
            st.error(f"Error extrayendo datos: {e}")
            st.stop()

    df = st.session_state["features_df"]
    n_pos = int(df["outcome"].sum()) if "outcome" in df.columns else 0
    st.success(f"✅ {len(df):,} pacientes | {n_pos:,} con outcome ({n_pos/len(df):.1%})")

    if n_pos < 20:
        st.error("Muy pocos casos positivos para modelar (< 20). "
                 "Prueba otro outcome o amplía la ventana de predicción.")
        st.stop()

    # Preparar datos
    with st.spinner("Preparando train/test split..."):
        X_tr, X_te, y_tr, y_te, scaler, features = prepare_data(
            df, target_col="outcome", test_size=test_size, balance=balance)

    st.info(f"Train: {len(y_tr):,} | Test: {len(y_te):,} | "
            f"Prevalencia test: {y_te.mean():.1%}")

    # Entrenar modelos
    with st.spinner(f"Entrenando {len(selected_models)} modelos..."):
        results = compare_models(X_tr, X_te, y_tr, y_te,
                                  selected_models, features)
    st.session_state["ml_results"]  = results
    st.session_state["ml_features"] = features
    st.success("✅ Modelos entrenados")

# ── RESULTADOS ─────────────────────────────────────────────────────────────────
if "ml_results" in st.session_state:
    results  = st.session_state["ml_results"]
    features = st.session_state["ml_features"]

    # Tabla comparativa
    st.subheader("📊 Comparación de modelos")
    comp_df = get_comparison_df(results)
    st.dataframe(
        comp_df.style.highlight_max(
            subset=["AUC-ROC","AUC-PR","F1 Score"],
            color="#d4edda", axis=0
        ).highlight_min(
            subset=["Brier Score"],
            color="#d4edda", axis=0
        ),
        use_container_width=True
    )

    # Seleccionar modelo para detalle
    st.divider()
    selected = st.selectbox("🔍 Ver detalle del modelo",
                             list(results.keys()), key="detail_model")
    res = results[selected]

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["ROC / PR", "Matriz confusión", "Importancia variables",
         "SHAP", "Calibración"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                plot_roc_curve(res["fpr"], res["tpr"], res["metrics"]["AUC-ROC"]),
                use_container_width=True)
        with col2:
            st.plotly_chart(
                plot_precision_recall(res["precision"], res["recall"],
                                      res["avg_precision"]),
                use_container_width=True)

    with tab2:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(
                plot_confusion_matrix(res["cm"]),
                use_container_width=True)
        with col2:
            st.subheader("Métricas detalladas")
            for k, v in res["metrics"].items():
                st.metric(k, v)

    with tab3:
        if res["importances"] is not None and len(res["importances"]) > 0:
            st.plotly_chart(
                plot_feature_importance(res["feature_names"],
                                         res["importances"], selected),
                use_container_width=True)
        else:
            st.info("Importancia de variables no disponible para este modelo.")

    with tab4:
        if res["shap_values"] is not None:
            st.plotly_chart(
                plot_shap_beeswarm(res["shap_values"], res["feature_names"]),
                use_container_width=True)
            st.caption(
                "Cada punto es un paciente. Valores SHAP positivos → mayor riesgo de outcome.")
        else:
            st.info("SHAP no disponible para este modelo.")

    with tab5:
        st.plotly_chart(
            plot_calibration_curve(res["frac_pos"], res["mean_pred"]),
            use_container_width=True)
        st.caption(
            "Una curva cercana a la diagonal indica buena calibración: "
            "si el modelo dice 30% de probabilidad, ~30% de esos pacientes tienen el outcome.")

    # Descargar predicciones
    st.divider()
    st.subheader("💾 Exportar predicciones")
    if "features_df" in st.session_state:
        df_export = st.session_state["features_df"].copy()
        model_obj = res["model"]
        # Regenerar features para todo el dataset
        feat_cols = [c for c in features if c in df_export.columns]
        X_all = df_export[feat_cols].fillna(0).astype(float)
        df_export["predicted_proba"] = model_obj.predict_proba(X_all)[:, 1]
        df_export["predicted_label"] = (df_export["predicted_proba"] >= 0.5).astype(int)

        csv = df_export[["person_id","predicted_proba","predicted_label",
                          "outcome"] + feat_cols].to_csv(index=False)
        st.download_button(
            "⬇ Descargar predicciones CSV",
            data=csv, file_name="omop_predictions.csv",
            mime="text/csv", type="primary")
