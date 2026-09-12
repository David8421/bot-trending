Sistema de Bot de Trading Modular
Proyecto de bot de trading con múltiples módulos, construido a partir de la planeación conversacional documentada en Plan_Bot_Trading_Recapitulacion.docx. Este README es el punto de entrada técnico del repositorio.
Antes que nada: todo el código aquí presente es una base de desarrollo, no un sistema listo para operar con capital real. Cada módulo requiere validación con backtesting propio, y los módulos marcados como "semi-automático" o "esqueleto" requieren trabajo adicional antes de producción.
Estructura del repositorio
trading-bot-system/
├── module_a_trend_following/   # Cripto, Freqtrade, automático (LISTO PARA BACKTEST)
│   ├── strategy.py
│   └── config.json
├── module_b_grid_dca/          # Cripto, Freqtrade, automático (LISTO PARA BACKTEST)
│   └── strategy.py
├── module_c_scalping/          # Cripto/Forex, automático (ESQUELETO — requiere infra de baja latencia)
│   └── strategy.py
├── module_d_forex_ib/          # Forex, Interactive Brokers, semi-automático (ESQUELETO FUNCIONAL)
│   └── signal_engine.py
├── module_e_prediction/        # Capa de predicción ML, transversal (ESQUELETO FUNCIONAL)
│   └── predictor.py
├── risk_engine/
│   └── risk_config.yaml        # Límites de riesgo y asignación de capital por módulo
└── docs/
Asignación de capital y arquitectura (resumen)
Módulo
Mercado
Ejecución
% capital
Automatización
A. Trend-following
Cripto (Binance/Bybit)
Freqtrade
30%
Automático
B. Grid/DCA
Cripto (Binance/Bybit)
Freqtrade
25%
Automático
C. Scalping
Cripto y/o Forex
Freqtrade / IB
15%
Automático (requiere baja latencia)
D. Forex
Interactive Brokers
Script propio (ib_insync)
30%
Semi-automático → automático tras validar
E. Predicción
—
XGBoost
— (no ejecuta)
Filtro opcional transversal
Detalle completo de reglas de entrada/salida y gestión de riesgo por estrategia: ver el documento de recapitulación (secciones 7 a 9).
Requisitos generales
# Entorno virtual recomendado
python -m venv venv
source venv/bin/activate   # En Windows: venv\Scripts\activate

# Módulos A, B, C (Freqtrade)
pip install freqtrade ta-lib

# Módulo D (Interactive Brokers)
pip install ib_insync

# Módulo E (predicción)
pip install xgboost scikit-learn pandas numpy
Nota sobre TA-Lib: la librería ta-lib (usada por talib.abstract en los módulos A, B y C) requiere instalar primero la librería nativa en el sistema operativo antes de pip install ta-lib — revisar la documentación oficial de Freqtrade para el paso específico según tu sistema operativo.
Cómo correr el backtesting (Módulos A y B)
cd module_a_trend_following
freqtrade download-data --config config.json --timerange 20240101-20260101
freqtrade backtesting --config config.json --strategy ModuloATrendFollowing --timerange 20240101-20260101
Repetir de forma equivalente para module_b_grid_dca con su propio config.json (crear uno análogo al de Módulo A, ajustando stake_currency, pair_whitelist y el nombre de la estrategia a ModuloBGridDCA).
Métricas a revisar en el reporte de backtesting: retorno total, drawdown máximo, win rate, y sharpe ratio — no solo el retorno total (ver sección 7 del documento de recapitulación sobre por qué esto importa).
Cómo probar el Módulo D (forex, Interactive Brokers)
Instalar y abrir TWS (Trader Workstation) o IB Gateway.
En la configuración de la API, habilitar "Enable ActiveX and Socket Clients" y confirmar el puerto 7497 (cuenta de paper trading).
Con TWS/Gateway corriendo, ejecutar:
python module_d_forex_ib/signal_engine.py
Por ahora, la función notify_for_confirmation solo imprime la señal en consola. Antes de usarlo en la práctica, hay que conectarla a un canal real (ej. un bot de Telegram) para poder confirmar o rechazar cada señal manualmente, como corresponde al modo semi-automático.
Nunca usar el puerto 7496 (cuenta real) hasta validar extensamente en paper trading (7497).
Cómo evaluar el Módulo E (predicción) antes de usarlo
import pandas as pd
from module_e_prediction.predictor import walk_forward_validation

df = pd.read_csv("tu_historico_ohlcv.csv")  # columnas: open, high, low, close, volume
resultado = walk_forward_validation(df)
print(resultado)
Si accuracy_mean no supera claramente el porcentaje base de velas alcistas del periodo evaluado, el modelo no está aportando señal real y no debe integrarse como filtro en los demás módulos.
Sobre el Módulo C (scalping)
Este módulo se entrega como base de referencia, no como algo listo para correr en producción. Antes de considerarlo:
Validar backtesting incluyendo comisiones y slippage realistas (freqtrade permite configurar esto en el backtesting).
Conseguir infraestructura de baja latencia (VPS cercano al exchange).
Asignar capital separado y acotado, según risk_engine/risk_config.yaml.
Roadmap sugerido
Backtesting del Módulo A (trend-following) con al menos 1-2 años de datos, incluyendo mercado alcista, bajista y lateral.
Backtesting del Módulo B (grid/DCA) bajo las mismas condiciones.
Comparar A vs. B vs. combinación de ambos según drawdown y sharpe ratio, no solo retorno total.
Validar el Módulo D en paper trading de Interactive Brokers durante varias semanas, con confirmación manual de cada señal.
Evaluar el Módulo E con walk_forward_validation sobre los mismos pares/periodos usados en A y B; solo integrarlo si mejora resultados de forma consistente.
Añadir el Módulo C (scalping) al final, una vez A, B y D estén validados y exista infraestructura de baja latencia disponible.
Confirmar con un contador el tratamiento fiscal aplicable en Costa Rica antes de operar con capital real.
Verificar que el exchange elegido cumpla con el registro VASP ante la SUGEF (Ley 10961).
Pasar a capital real pequeño, con monitorización activa y escalado gradual según resultados sostenidos.
Advertencia
Este proyecto tiene fines de desarrollo técnico y educativo. Ningún componente aquí garantiza rentabilidad. El rendimiento pasado de cualquier estrategia no garantiza resultados futuros. Antes de operar con capital real, valida cada módulo con tu propio backtesting y considera asesoría profesional en materia fiscal y legal en tu jurisdicción.