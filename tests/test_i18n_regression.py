from __future__ import annotations

import pandas as pd

from ai_stock.i18n import localize_dataframe_for_display


def test_localize_dataframe_selects_columns_before_translating() -> None:
    raw = pd.DataFrame(
        {
            "代號": ["AAPL"],
            "預測天數": [1],
            "因子": ["RSI_lag_1"],
            "重要度": [0.12],
            "方向貢獻": [0.03],
            "方向": ["正向"],
            "方法": ["shap_explainer"],
            "額外欄位": ["ignore me"],
        }
    )

    out = localize_dataframe_for_display(
        raw,
        ["代號", "預測天數", "因子", "重要度", "方向貢獻", "方向", "方法"],
        "en",
    )

    assert list(out.columns) == ["Ticker", "Prediction horizon", "Factor", "Importance", "Signed contribution", "Direction", "Method"]
    assert out.iloc[0]["Ticker"] == "AAPL"
    assert "額外欄位" not in out.columns


def test_localize_dataframe_ignores_missing_optional_columns() -> None:
    raw = pd.DataFrame({"代號": ["AAPL"], "因子": ["RSI_lag_1"]})

    out = localize_dataframe_for_display(raw, ["代號", "預測天數", "因子"], "en")

    assert list(out.columns) == ["Ticker", "Factor"]
