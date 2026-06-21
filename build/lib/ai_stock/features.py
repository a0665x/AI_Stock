from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _stochastic_kd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9) -> tuple[pd.Series, pd.Series]:
    lowest_low = low.rolling(period).min()
    highest_high = high.rolling(period).max()
    k = (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan) * 100
    d = k.rolling(3).mean()
    return k, d


def generate_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """參考 Part1 的 char_generator，但拿掉 TA-Lib 依賴。

    Required columns:
    - 開盤
    - 最高
    - 最低
    - 收盤
    - 成交股數
    """
    data = df.copy()

    for period in [5, 7, 10, 14, 20, 35, 60, 90, 120]:
        data[f'SMA{period}'] = data['收盤'].rolling(period).mean() / data['收盤']
        data[f'EMA{period}'] = data['收盤'].ewm(span=period, adjust=False).mean() / data['收盤']

    for period in [5, 10, 20, 60, 120]:
        data[f'VMA{period}'] = data['成交股數'].rolling(period).mean() / data['成交股數']

    data['MA10_diff5'] = data['SMA10'] - data['SMA5']
    data['MA20_diff10'] = data['SMA20'] - data['SMA10']
    data['MA60_diff20'] = data['SMA60'] - data['SMA20']
    data['VMA10_diff5'] = data['VMA10'] - data['VMA5']
    data['VMA20_diff10'] = data['VMA20'] - data['VMA10']
    data['VMA60_diff20'] = data['VMA60'] - data['VMA20']

    ema_fast_12 = data['收盤'].ewm(span=6, adjust=False).mean()
    ema_slow_12 = data['收盤'].ewm(span=12, adjust=False).mean()
    data['MACD12'] = ema_fast_12 - ema_slow_12
    data['MACD12_S'] = data['MACD12'].ewm(span=9, adjust=False).mean()
    data['MACD12_H'] = data['MACD12'] - data['MACD12_S']

    ema_fast_26 = data['收盤'].ewm(span=13, adjust=False).mean()
    ema_slow_26 = data['收盤'].ewm(span=26, adjust=False).mean()
    data['MACD26'] = ema_fast_26 - ema_slow_26
    data['MACD26_S'] = data['MACD26'].ewm(span=19, adjust=False).mean()
    data['MACD26_H'] = data['MACD26'] - data['MACD26_S']

    for period in [6, 9, 12, 16, 21]:
        data[f'RSI{period}'] = _rsi(data['收盤'], period)
        data[f'MOM{period}'] = data['收盤'].diff(period)

    data['KD_K'], data['KD_D'] = _stochastic_kd(data['最高'], data['最低'], data['收盤'])
    data['KD_diff'] = data['KD_K'] - data['KD_D']

    data['成交股數'] = data['成交股數'] / data['成交股數'].shift(1)
    for col in ['開盤', '最高', '最低']:
        data[col] = data[col] / data['收盤']

    for period in [3, 5, 8, 13, 21, 34, 55, 89]:
        data[f'std_{period}'] = data['收盤'].rolling(period).std() / data['收盤']

    data['close_1'] = (data['收盤'].shift(-1) / data['收盤'] - 1) * 100.0
    data['close_60'] = (data['收盤'].shift(-60) / data['收盤'] - 1) * 100.0
    return data
