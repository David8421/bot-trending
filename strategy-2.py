# -*- coding: utf-8 -*-
"""
Modulo C - Scalping (Cripto y/o Forex) - ESQUELETO BASE
==========================================================
ADVERTENCIA IMPORTANTE:
Este modulo es el de mayor exigencia tecnica del proyecto. El scalping
real requiere:
  - Ejecucion en timeframes de 1-5 minutos (a veces segundos)
  - Baja latencia entre la señal y la orden (idealmente un VPS cerca del
    servidor del exchange/broker, no un equipo domestico con conexion
    variable)
  - Comisiones y slippage tienen un impacto proporcionalmente mucho mayor
    que en trend-following o grid, porque las ganancias por operacion
    son pequeñas

Este archivo es un PUNTO DE PARTIDA con una logica simple y conocida
(reversion a la media con Bandas de Bollinger + RSI en extremos), NO una
estrategia lista para producción. Antes de usarla en real:
  1. Backtesting exhaustivo incluyendo comisiones y slippage realistas
  2. Validar en un VPS con baja latencia al exchange elegido
  3. Asignar capital separado y acotado (ver docs/ARQUITECTURA.md, 15%
     sugerido del capital total)

Logica base (reversion a la media, timeframe 5m):
  Entrada long: precio toca banda inferior de Bollinger + RSI < 25
  Salida: precio vuelve a la banda media, o stop-loss ajustado (~1%)
"""

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter


class ModuloCScalping(IStrategy):
    timeframe = "5m"
    can_short = False

    # Stop-loss ajustado: en scalping las perdidas deben limitarse rapido
    stoploss = -0.01

    trailing_stop = False
    minimal_roi = {
        "0": 0.015,   # objetivo de ganancia rapido: 1.5%
        "15": 0.008,  # si pasan 15 min, conformarse con menos
        "30": 0,      # si pasan 30 min, salir en breakeven
    }

    max_open_trades = 2

    bb_std = DecimalParameter(1.5, 2.5, default=2.0, space="buy")
    rsi_oversold = DecimalParameter(15, 30, default=25, space="buy")

    startup_candle_count: int = 30

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=self.bb_std.value, nbdevdn=self.bb_std.value)
        dataframe["bb_lower"] = bollinger["lowerband"]
        dataframe["bb_mid"] = bollinger["middleband"]
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=7)  # RSI corto para scalping
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] <= dataframe["bb_lower"])
            & (dataframe["rsi"] < self.rsi_oversold.value)
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] >= dataframe["bb_mid"]),
            "exit_long",
        ] = 1
        return dataframe
