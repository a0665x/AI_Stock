from __future__ import annotations

import numpy as np
import pandas as pd

from ai_stock.swing_order_chart import (
    build_swing_order_technical_chart,
    compute_ukf_momentum_state,
    detect_candlestick_patterns,
    detect_fvg_ifvg_zones,
    detect_sfp_events,
    detect_swing_structure_signals,
    summarize_swing_order_technical_context,
)


def _sample_ohlcv(days: int = 90, ticker: str = "TEST") -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    trend = np.linspace(100, 122, days)
    wave = np.sin(np.linspace(0, 8 * np.pi, days)) * 2.5
    close = trend + wave
    open_ = close + np.sin(np.linspace(0, 5 * np.pi, days)) * 0.5
    high = np.maximum(open_, close) + 1.2
    low = np.minimum(open_, close) - 1.1
    volume = 1_000_000 + (np.cos(np.linspace(0, 4 * np.pi, days)) * 120_000).astype(int)
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_ukf_momentum_state_is_bounded_and_has_noise_band() -> None:
    prices = _sample_ohlcv()

    result = compute_ukf_momentum_state(prices)

    assert len(result) == len(prices)
    assert {"raw_momentum", "ukf_momentum", "ukf_velocity", "noise_band_low", "noise_band_high", "state_label"}.issubset(result.columns)
    assert result["ukf_momentum"].between(-100, 100).all()
    assert (result["noise_band_low"] <= result["ukf_momentum"]).all()
    assert (result["noise_band_high"] >= result["ukf_momentum"]).all()
    assert set(result["state_label"]).issubset({"BULLISH_MOMENTUM", "BEARISH_MOMENTUM", "NEUTRAL_MOMENTUM"})


def test_candlestick_patterns_detect_doji_and_engulfing() -> None:
    prices = pd.DataFrame(
        {
            "ticker": ["TEST"] * 4,
            "date": pd.date_range("2025-01-01", periods=4, freq="D"),
            "open": [100.0, 102.0, 100.0, 99.0],
            "high": [103.0, 103.0, 105.0, 104.0],
            "low": [99.0, 100.0, 98.0, 98.0],
            "close": [100.1, 100.5, 104.0, 103.9],
            "volume": [1000, 1100, 1300, 1200],
        }
    )

    patterns = detect_candlestick_patterns(prices)

    assert not patterns.empty
    assert "DOJI" in set(patterns["pattern"])
    assert "BULLISH_ENGULFING" in set(patterns["pattern"])


def test_swing_order_chart_contains_price_indicators_order_zones_and_ukf_panel() -> None:
    prices = _sample_ohlcv()
    order_row = {
        "ticker": "TEST",
        "next_day_buy_low": 116.0,
        "next_day_buy_high": 117.5,
        "next_day_sell_low": 123.0,
        "next_day_sell_high": 125.0,
        "tactical_stop_price": 114.5,
        "hard_stop_price": 111.0,
        "strategy_buy_price": 113.0,
        "strategy_take_profit_price": 128.0,
        "action": "HOLD_WAIT",
    }

    fig = build_swing_order_technical_chart(prices, "TEST", order_row, lookback=80, show_volume=True)
    trace_names = {str(trace.name) for trace in fig.data if getattr(trace, "name", None)}

    assert "K線" in trace_names
    assert "Bollinger Upper" in trace_names
    assert "RSI14" in trace_names
    assert "MACD Hist" in trace_names
    assert "UKF Momentum" in trace_names
    assert "Buy Zone" in trace_names
    assert "Sell Zone" in trace_names
    assert fig.layout.hovermode == "x unified"
    assert fig.layout.height >= 900


def test_swing_order_technical_summary_supports_order_decision_context() -> None:
    prices = _sample_ohlcv()
    summary = summarize_swing_order_technical_context(prices, {"ticker": "TEST"})

    assert summary["ticker"] == "TEST"
    assert "rsi_14" in summary
    assert "macd_hist" in summary
    assert "bb_position_20" in summary
    assert "volume_ratio_20d" in summary
    assert "ukf_momentum_score" in summary
    assert summary["technical_readiness"] in {"BULLISH", "BEARISH", "MIXED"}


def test_swing_structure_fvg_ifvg_and_sfp_signals_are_detected() -> None:
    prices = pd.DataFrame(
        {
            "ticker": ["TEST"] * 13,
            "date": pd.date_range("2025-01-01", periods=13, freq="D"),
            "open": [100, 101, 102, 108, 109, 107, 106, 104, 103, 101, 105, 108, 99],
            "high": [102, 103, 104, 111, 112, 109, 108, 106, 105, 110, 109, 112, 103],
            "low": [99, 100, 101, 107, 108, 105, 104, 102, 100, 99, 98, 107, 97],
            "close": [101, 102, 103, 110, 108.5, 106, 105, 103, 101, 105, 108, 111, 101],
            "volume": [1000, 1100, 1200, 1800, 1500, 1400, 1300, 1250, 1600, 2100, 1900, 2200, 2300],
        }
    )

    structure = detect_swing_structure_signals(prices, swing_window=1, min_break_pct=0.001)
    fvg = detect_fvg_ifvg_zones(prices, min_gap_pct=0.004)
    sfp = detect_sfp_events(prices, swing_window=1, tolerance_pct=0.001)

    assert {"swings", "structure_events", "support_resistance"}.issubset(structure)
    assert {"swing_high", "swing_low"}.intersection(set(structure["swings"]["type"]))
    assert set(fvg["zone_type"]).intersection({"FVG_BULLISH", "FVG_BEARISH"})
    assert "IFVG" in set(fvg["status"])
    assert set(sfp["event_type"]).intersection({"SFP_BEARISH", "SFP_BULLISH"})


def test_swing_chart_displays_smc_signal_overlays() -> None:
    prices = _sample_ohlcv(140)
    order_row = {
        "ticker": "TEST",
        "next_day_buy_low": 116.0,
        "next_day_buy_high": 117.5,
        "next_day_sell_low": 123.0,
        "next_day_sell_high": 125.0,
        "tactical_stop_price": 114.5,
        "hard_stop_price": 111.0,
        "strategy_buy_price": 113.0,
        "strategy_take_profit_price": 128.0,
        "action": "HOLD_WAIT",
    }

    fig = build_swing_order_technical_chart(prices, "TEST", order_row, lookback=120, show_volume=True)
    trace_names = {str(trace.name) for trace in fig.data if getattr(trace, "name", None)}

    assert "Swing High" in trace_names
    assert "Swing Low" in trace_names
    assert "BOS / ChoCH" in trace_names
    assert "SFP" in trace_names
    assert "FVG / IFVG" in trace_names


def test_swing_chart_can_render_external_smc_order_blocks_and_liquidity(monkeypatch) -> None:
    prices = _sample_ohlcv(80)
    dates = prices["date"]

    def fake_context(one, **kwargs):
        return {
            "engine": "smartmoneyconcepts",
            "fvg_zones": pd.DataFrame(
                [
                    {
                        "zone_id": "fvg1",
                        "date": dates.iloc[-20],
                        "end_date": dates.iloc[-1],
                        "zone_type": "FVG_BULLISH",
                        "status": "FVG",
                        "y0": 108.0,
                        "y1": 110.0,
                        "direction": "bullish",
                        "strength": 0.2,
                        "label": "SMC FVG Bullish",
                        "source": "smartmoneyconcepts",
                    }
                ]
            ),
            "order_blocks": pd.DataFrame(
                [
                    {
                        "zone_id": "ob1",
                        "date": dates.iloc[-18],
                        "end_date": dates.iloc[-1],
                        "zone_type": "OB_BULLISH",
                        "y0": 106.0,
                        "y1": 109.0,
                        "direction": "bullish",
                        "strength": 0.7,
                        "label": "SMC OB Bullish",
                        "source": "smartmoneyconcepts",
                    }
                ]
            ),
            "liquidity": pd.DataFrame(
                [
                    {
                        "date": dates.iloc[-15],
                        "level": 121.0,
                        "direction": "buy_side",
                        "status": "resting",
                        "strength": 1.0,
                        "label": "SMC Liquidity Buy Side",
                        "source": "smartmoneyconcepts",
                    }
                ]
            ),
            "swings": pd.DataFrame(columns=["date", "price", "type", "strength", "source"]),
            "structure_events": pd.DataFrame(columns=["date", "price", "event_type", "reference_price", "description", "source"]),
        }

    monkeypatch.setattr("ai_stock.swing_order_chart.build_smc_context", fake_context)

    fig = build_swing_order_technical_chart(prices, "TEST", {"ticker": "TEST"}, lookback=80, show_volume=True)
    trace_names = {str(trace.name) for trace in fig.data if getattr(trace, "name", None)}

    assert "SMC Order Block" in trace_names
    assert "SMC Liquidity" in trace_names
    assert "FVG / IFVG" in trace_names
    assert any("SMC OB" in str(getattr(shape, "name", "")) for shape in fig.layout.shapes)
