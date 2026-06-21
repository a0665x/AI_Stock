from __future__ import annotations

import pandas as pd

from ai_stock.i18n import LANGUAGES, t, translate_dataframe_columns, translate_dataframe_values, translate_options


def test_i18n_language_registry_has_required_languages() -> None:
    assert set(LANGUAGES) == {"zh", "en", "ja", "ko"}
    assert t("決策報表", "en") == "Decision report"
    assert t("決策報表", "ja") == "判断レポート"
    assert t("決策報表", "ko") == "결정 보고서"


def test_i18n_dataframe_column_translation_keeps_values() -> None:
    df = pd.DataFrame({"代號": ["AAPL"], "決策": ["等待確認"], "Kelly 建議倉位": [0.0]})
    out = translate_dataframe_columns(df, "en")
    assert list(out.columns) == ["Ticker", "Decision", "Kelly suggested position"]
    assert out.iloc[0]["Ticker"] == "AAPL"


def test_i18n_translates_decision_and_kelly_reason_values() -> None:
    df = pd.DataFrame(
        {
            "決策": ["等待確認"],
            "決策原因": ["等待確認：預估報酬 +0.23% 仍在 ±6.14% 門檻內；代表模型優勢尚未明顯大過近期波動與回撤風險。"],
            "Kelly 原因": ["Kelly 為 0：預估報酬 +0.23%，風險單位 3.31%，在保守勝率假設 52% 下，約需大於 3.05% 的優勢才值得配置。"],
        }
    )

    out = translate_dataframe_values(df, "en")

    assert out.iloc[0]["決策"] == "Wait for confirmation"
    assert "Wait for confirmation:" in out.iloc[0]["決策原因"]
    assert "expected return +0.23%" in out.iloc[0]["決策原因"]
    assert "recent volatility and drawdown risk" in out.iloc[0]["決策原因"]
    assert "Kelly is 0:" in out.iloc[0]["Kelly 原因"]
    assert "conservative win-rate assumption 52%" in out.iloc[0]["Kelly 原因"]
    assert not any("等待確認" in str(value) or "預估報酬" in str(value) or "風險單位" in str(value) for value in out.iloc[0])


def test_i18n_translates_sidebar_choice_labels() -> None:
    assert translate_options(["時間出場", "停損優先", "移動停損"], "en") == ["Time exit", "Stop-loss first", "Trailing stop"]
    assert translate_options(["時間出場", "停損優先", "移動停損"], "ja") == ["時間で終了", "損切り優先", "トレーリングストップ"]
    assert translate_options(["時間出場", "停損優先", "移動停損"], "ko") == ["시간 청산", "손절 우선", "트레일링 스톱"]


def test_streamlit_app_exposes_language_selector_and_i18n_helpers() -> None:
    source = open("src/ai_stock/app.py", encoding="utf-8").read()
    assert "_language_selector" in source
    assert "LANGUAGES" in source
    assert "_install_streamlit_i18n" in source
    assert "translate_dataframe_columns" in source
    assert "translate_dataframe_values" in source
    assert "translate_options" in source
    assert '"toggle"' in source
    assert '"write"' in source
    assert t("##### 因子研究", "en") == "##### Factor research"


def test_i18n_translates_dynamic_ui_templates() -> None:
    assert t("決策：{action}", "en", action="🟡 Wait for confirmation") == "Decision: 🟡 Wait for confirmation"
    assert t("參考買進：{price}", "en", price="287.38") == "Buy reference: 287.38"
    assert t("SHAP / 歸因分析", "en") == "SHAP / Attribution"
    assert t("最佳累積報酬", "en") == "Best cumulative return"
    assert "Every horizon days" in t(
        "每隔 horizon 天，只使用當下以前的資料重新產生決策報表，再用下一段行情驗證。這不是實盤成交模擬，先用來檢查策略方向、停損與回撤是否合理。",
        "en",
    )
    assert "Current setting: past 7-day factors" in t(
        "目前設定：過去 {window} 天因子 → 比較未來 {horizons} 天漲跌；上漲門檻 {threshold:.1f}%；模型 {model}。",
        "en",
        window=7,
        horizons="1, 3, 5, 10",
        threshold=0.0,
        model="Gradient Boosting",
    )
