# -*- coding: utf-8 -*-
"""
Modulo D - Forex con Interactive Brokers (Semi-automatico)
=============================================================
A diferencia de los modulos de cripto (que usan Freqtrade), este modulo
se conecta directamente a Interactive Brokers via su API oficial
(TWS API / ib_insync), porque Freqtrade no soporta IB de forma nativa.

Flujo semi-automatico:
  1. El motor calcula la señal (misma logica que el Modulo A: cruce de
     EMAs + RSI + MACD, adaptada a un par de forex).
  2. En vez de ejecutar la orden directamente, ENVIA UNA NOTIFICACION
     (ej. Telegram) con el detalle de la señal.
  3. El usuario confirma manualmente (ej. respondiendo al bot) antes de
     que se envie la orden real a Interactive Brokers.
  4. Una vez validado el sistema por un tiempo, este mismo motor puede
     pasar a modo automatico quitando el paso de confirmacion manual.

Requisitos antes de ejecutar esto de verdad:
  - Tener TWS (Trader Workstation) o IB Gateway corriendo y con la API
    habilitada (Configuracion > API > Habilitar clientes ActiveX y de
    Socket), apuntando a localhost, puerto 7497 (paper trading) o 7496
    (cuenta real) - SIEMPRE EMPEZAR CON PAPER TRADING (7497).
  - pip install ib_insync
  - Una cuenta de Interactive Brokers habilitada para forex.

Este archivo es un ESQUELETO funcional de referencia: la logica de
señal esta completa, pero la integracion de notificacion/confirmacion
(Telegram u otro canal) debe conectarse a tus credenciales propias antes
de usarse.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd

try:
    from ib_insync import IB, Forex, util
except ImportError:
    IB = None  # Permite importar este archivo sin ib_insync instalado (solo lectura/revision)


# --- Configuracion de conexion ---
IB_HOST = "127.0.0.1"
IB_PORT = 7497  # 7497 = paper trading. Cambiar a 7496 solo tras validar en paper.
IB_CLIENT_ID = 1

# --- Reglas de señal (equivalentes al Modulo A, adaptadas a forex) ---
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
RSI_BUY_MIN = 40
RSI_BUY_MAX = 70


@dataclass
class TradeSignal:
    pair: str
    direction: str  # "long" o "short"
    price: float
    reason: str


def connect_ib() -> "IB":
    if IB is None:
        raise RuntimeError("ib_insync no esta instalado. Ejecuta: pip install ib_insync")
    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
    return ib


def fetch_forex_history(ib: "IB", pair: str = "EURUSD", duration: str = "30 D", bar_size: str = "4 hours") -> pd.DataFrame:
    contract = Forex(pair)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting=bar_size,
        whatToShow="MIDPOINT",
        useRTH=True,
    )
    return util.df(bars)


def compute_signal(df: pd.DataFrame, pair: str) -> Optional[TradeSignal]:
    """
    Aplica la misma logica de entrada del Modulo A (trend-following)
    sobre datos de forex: cruce alcista de EMAs + RSI en rango + MACD
    con histograma positivo y creciente.
    """
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macdhist"] = macd_line - signal_line

    last = df.iloc[-1]
    prev = df.iloc[-2]

    cruce_alcista = (last["ema_fast"] > last["ema_slow"]) and (prev["ema_fast"] <= prev["ema_slow"])
    rsi_ok = RSI_BUY_MIN < last["rsi"] < RSI_BUY_MAX
    macd_ok = last["macdhist"] > 0 and last["macdhist"] > prev["macdhist"]

    if cruce_alcista and rsi_ok and macd_ok:
        return TradeSignal(
            pair=pair,
            direction="long",
            price=float(last["close"]),
            reason="Cruce alcista EMA20/50 + RSI en rango + MACD histograma creciente",
        )
    return None


def notify_for_confirmation(signal: TradeSignal) -> None:
    """
    PLACEHOLDER: conectar aqui con Telegram (o el canal que prefieras).
    Ejemplo de mensaje a enviar:

        "Señal detectada en {signal.pair}: {signal.direction} a {signal.price}.
         Razon: {signal.reason}.
         Responde 'confirmar' para ejecutar, o ignora para descartar."

    Hasta que se conecte un canal real de confirmacion, esta funcion solo
    imprime la señal en consola (modo de prueba).
    """
    print(f"[SEÑAL PENDIENTE DE CONFIRMACION] {signal}")


def run_once(pair: str = "EURUSD") -> None:
    ib = connect_ib()
    try:
        df = fetch_forex_history(ib, pair=pair)
        signal = compute_signal(df, pair)
        if signal:
            notify_for_confirmation(signal)
        else:
            print(f"Sin señal para {pair} en este ciclo.")
    finally:
        ib.disconnect()


if __name__ == "__main__":
    run_once()
