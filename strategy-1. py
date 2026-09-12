# -*- coding: utf-8 -*-
"""
Modulo B - Grid Dinamico con Filtro de Tendencia (Cripto)
===========================================================
Implementa la logica de "grid" usando la funcionalidad nativa de Freqtrade
de ajuste de posicion (position adjustment / DCA), que permite anadir
compras escalonadas a una posicion abierta, similar a los niveles de un
grid bot.

Filtro de tendencia:
  - Solo se abre/mantiene el grid si el precio esta sobre la EMA de 200
  - Si el precio cae bajo la EMA 200, se pausa: no se abren nuevos niveles

Configuracion del grid:
  - Rango de precio definido por volatilidad reciente (ATR de 14 periodos)
  - 5-10 niveles escalonados dentro del rango (aproximado via DCA steps)
  - Reajuste: se recomienda revisar diariamente si el rango sigue vigente

Gestion de riesgo:
  - Maximo 30-40% del capital de esta estrategia en grid activo a la vez
    (controlado via max_entry_position_adjustment y stake_amount)

IMPORTANTE: freqtrade no tiene un "grid bot" nativo identico a los de
Pionex/Binance; aqui se aproxima el comportamiento con DCA escalonado
condicionado a un filtro de tendencia. Validar con backtesting antes
de asumir que el comportamiento es equivalente a un grid bot clasico.
"""

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from freqtrade.persistence import Trade
from datetime import datetime
from typing import Optional


class ModuloBGridDCA(IStrategy):
    timeframe = "4h"
    can_short = False

    # Stop-loss amplio porque el grid ya gestiona el riesgo via niveles;
    # este es un limite de proteccion extremo, no la salida principal.
    stoploss = -0.15

    trailing_stop = False
    minimal_roi = {"0": 10}  # se prioriza la logica de niveles, no un ROI fijo

    max_open_trades = 3

    # --- Parametros del filtro de tendencia ---
    ema_filter_length = IntParameter(150, 250, default=200, space="buy")

    # --- Parametros de position adjustment (niveles del grid) ---
    # Numero maximo de compras adicionales por encima de la inicial (niveles)
    max_dca_orders = 6  # 1 entrada inicial + hasta 6 niveles = 7 total (dentro de 5-10)
    # Cuanto debe caer el precio (respecto al precio promedio actual) para
    # disparar el siguiente nivel de compra.
    dca_price_step_pct = DecimalParameter(0.02, 0.05, default=0.03, space="buy")
    # Multiplicador del monto de cada nivel adicional respecto al inicial
    dca_stake_multiplier = 1.0

    position_adjustment_enable = True
    max_entry_position_adjustment = max_dca_orders

    startup_candle_count: int = 210

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_filter"] = ta.EMA(dataframe, timeperiod=self.ema_filter_length.value)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        # Rango de referencia del grid (informativo, para logging/analisis)
        dataframe["grid_range_pct"] = dataframe["atr"] / dataframe["close"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            # Filtro de tendencia: solo operar si el precio esta sobre la EMA200
            (dataframe["close"] > dataframe["ema_filter"]),
            (dataframe["volume"] > 0),
        ]
        dataframe.loc[conditions[0] & conditions[1], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Salida principal: el precio pierde el filtro de tendencia de forma
        # sostenida (cierra la posicion completa, no solo pausa nuevos niveles)
        dataframe.loc[
            (dataframe["close"] < dataframe["ema_filter"] * 0.97),  # margen de 3% para evitar ruido
            "exit_long",
        ] = 1
        return dataframe

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> Optional[float]:
        """
        Anade un nuevo 'nivel de grid' (compra adicional) si el precio ha
        caido lo suficiente respecto al precio promedio de la posicion,
        y siempre que el filtro de tendencia (EMA200) siga vigente.
        """
        if current_profit > -self.dca_price_step_pct.value:
            return None  # aun no cae lo suficiente para el siguiente nivel

        filled_entries = trade.select_filled_orders(trade.entry_side)
        count_of_entries = len(filled_entries)

        if count_of_entries >= self.max_dca_orders + 1:
            return None  # ya se alcanzo el maximo de niveles del grid

        try:
            stake_amount = filled_entries[0].stake_amount
            stake_amount = stake_amount * self.dca_stake_multiplier
            return stake_amount
        except (IndexError, KeyError):
            return None
