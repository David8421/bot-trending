# -*- coding: utf-8 -*-
"""
Modulo E - Capa de Prediccion (opcional, transversal) - ESQUELETO BASE
=========================================================================
Este modulo NO ejecuta operaciones por si mismo. Genera una señal
adicional (probabilidad de que el precio suba en las proximas N velas)
que los demas modulos pueden usar como filtro de confirmacion opcional
-- nunca como autoridad final (esa la mantiene el motor de riesgo de
cada modulo).

Enfoque elegido: XGBoost sobre una señal BINARIA simple (sube/baja en
las proximas N velas), no un modelo de prediccion de precio exacto.
Razones (ver investigacion en la conversacion):
  - Los modelos de prediccion de precio (LSTM, hibridos) son propensos a
    sobreajuste (overfitting), especialmente en mercados volatiles.
  - XGBoost es mas interpretable, mas rapido de entrenar/validar, y en
    varios estudios comparativos rinde igual o mejor que LSTM con menor
    complejidad para este tipo de tarea.

ADVERTENCIA: un modelo de prediccion, sin importar su accuracy en
backtesting, puede fallar en produccion si el regimen de mercado
cambia. Este modulo SOLO debe usarse como filtro adicional, evaluado
con el mismo rigor (o mayor) que las estrategias basadas en reglas,
comparando resultados CON y SIN esta capa antes de confiar en ella con
capital real.

Requiere: pip install xgboost scikit-learn pandas ta
"""

from dataclasses import dataclass
import pandas as pd
import numpy as np

try:
    import xgboost as xgb
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import accuracy_score, precision_score, recall_score
except ImportError:
    xgb = None  # Permite importar/revisar este archivo sin las dependencias instaladas


N_FORWARD_CANDLES = 3  # horizonte de prediccion: sube/baja en las proximas 3 velas
FEATURE_WINDOW = 14


@dataclass
class PredictionResult:
    probability_up: float
    label_predicted: int  # 1 = sube, 0 = no sube
    confidence_note: str


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera features tecnicos simples a partir de OHLCV. Se mantienen
    deliberadamente simples (complejidad "media") en vez de un feature
    engineering extenso, para reducir el riesgo de sobreajuste.
    """
    out = df.copy()

    out["return_1"] = out["close"].pct_change(1)
    out["return_3"] = out["close"].pct_change(3)
    out["volatility"] = out["close"].pct_change().rolling(FEATURE_WINDOW).std()

    ema_fast = out["close"].ewm(span=12, adjust=False).mean()
    ema_slow = out["close"].ewm(span=26, adjust=False).mean()
    out["ema_diff"] = (ema_fast - ema_slow) / out["close"]

    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(FEATURE_WINDOW).mean()
    loss = (-delta.clip(upper=0)).rolling(FEATURE_WINDOW).mean()
    rs = gain / loss
    out["rsi"] = 100 - (100 / (1 + rs))

    out["volume_change"] = out["volume"].pct_change(1)

    # Etiqueta (target): sube en las proximas N velas
    out["future_return"] = out["close"].shift(-N_FORWARD_CANDLES) / out["close"] - 1
    out["target"] = (out["future_return"] > 0).astype(int)

    return out.dropna()


FEATURE_COLUMNS = ["return_1", "return_3", "volatility", "ema_diff", "rsi", "volume_change"]


def walk_forward_validation(df: pd.DataFrame, n_splits: int = 5) -> dict:
    """
    Validacion walk-forward (no un simple train/test aleatorio, que
    filtraria informacion futura en series de tiempo). Devuelve metricas
    promedio para juzgar honestamente si el modelo aporta algo real.
    """
    if xgb is None:
        raise RuntimeError("Faltan dependencias: pip install xgboost scikit-learn")

    data = build_features(df)
    X = data[FEATURE_COLUMNS]
    y = data["target"]

    tscv = TimeSeriesSplit(n_splits=n_splits)
    accuracies, precisions, recalls = [], [], []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
        )
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        accuracies.append(accuracy_score(y_test, preds))
        precisions.append(precision_score(y_test, preds, zero_division=0))
        recalls.append(recall_score(y_test, preds, zero_division=0))

    return {
        "accuracy_mean": float(np.mean(accuracies)),
        "precision_mean": float(np.mean(precisions)),
        "recall_mean": float(np.mean(recalls)),
        "n_splits": n_splits,
        "note": (
            "Comparar accuracy_mean contra el 50% base (o el ratio real de "
            "velas alcistas del periodo). Si no supera claramente ese "
            "punto de referencia, la capa de prediccion no aporta valor "
            "real y no deberia usarse como filtro."
        ),
    }


def predict_latest(df: pd.DataFrame) -> PredictionResult:
    """
    Entrena con todo el historico disponible (excepto las ultimas
    N_FORWARD_CANDLES, que no tienen target valido) y predice la
    probabilidad para la vela mas reciente. Usar SOLO despues de validar
    con walk_forward_validation que el modelo aporta señal real.
    """
    if xgb is None:
        raise RuntimeError("Faltan dependencias: pip install xgboost scikit-learn")

    data = build_features(df)
    X = data[FEATURE_COLUMNS]
    y = data["target"]

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
    )
    model.fit(X, y)

    latest_features = X.iloc[[-1]]
    probability_up = float(model.predict_proba(latest_features)[0][1])
    label = int(probability_up > 0.5)

    return PredictionResult(
        probability_up=probability_up,
        label_predicted=label,
        confidence_note=(
            "Usar solo como filtro adicional. No ejecutar ninguna orden "
            "basandose unicamente en esta prediccion."
        ),
    )
