from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from ai_stock.analytics import add_indicators, compute_correlation_table, compute_latest_technical_snapshot
from ai_stock.attribution import build_attribution_report
from ai_stock.backtesting import compare_backtest_scenarios, run_backtest
from ai_stock.data_sources import DataRequest, clear_yfinance_disk_cache, load_history, normalize_ohlcv
from ai_stock.forecasting import build_decision_report
from ai_stock.portfolio import build_portfolio_order_plan, load_local_portfolio, portfolio_tickers, summarize_portfolio
from ai_stock.order_planner import augment_order_plan_with_smc, build_next_day_order_plan, build_smc_timeframe_signals, integrate_strategy_recommendations_into_order_plan
from ai_stock.order_strategy_workbench import ORDER_STRATEGIES, build_order_strategy_workbench, build_strategy_visualization_payload
from ai_stock.swing_order_chart import build_swing_order_technical_chart, summarize_swing_order_technical_context
from ai_stock.visual_insights import (
    build_decision_price_chart,
    build_market_heatmap_table,
    build_opportunity_radar,
    build_smart_tuning_lite,
    build_strategy_health_cards,
    build_watchlist_sparklines,
)
from ai_stock.trade_vision import (
    build_mtf_matrix,
    build_trade_narrative,
    build_trade_plan_from_decision,
    build_trade_vision_chart,
    build_trade_zones,
    compute_trade_signal_score,
    detect_market_structure,
)
from ai_stock.training_data import build_training_dataset, compute_top_training_features
from ai_stock.i18n import (
    LANGUAGES,
    localize_dataframe_for_display,
    t,
    translate_dataframe_columns,
    translate_dataframe_values,
    translate_mapping,
    translate_options,
)
from ai_stock.factor_research import (
    build_factor_horizon_comparison,
    build_factor_research_report,
    build_horizon_metric_trends,
    build_ticker_horizon_metric_matrix,
)


st.set_page_config(page_title="AI Stock 決策儀表板", page_icon="📈", layout="wide")


def _language_selector() -> str:
    """Render a compact top-right language selector and return the active language code."""
    labels = list(LANGUAGES.values())
    codes = list(LANGUAGES.keys())
    default_code = st.session_state.get("ui_language", "zh")
    default_index = codes.index(default_code) if default_code in codes else 0
    _, language_col = st.columns([0.78, 0.22])
    with language_col:
        selected = st.selectbox(
            "🌐 語言 / Language",
            labels,
            index=default_index,
            key="ui_language_label",
            label_visibility="collapsed",
        )
    code = codes[labels.index(selected)]
    st.session_state["ui_language"] = code
    return code


UI_LANG = _language_selector()
_ = lambda text, **kwargs: t(text, UI_LANG, **kwargs)


def _install_streamlit_i18n() -> None:
    """Translate common Streamlit display strings without changing data/model values."""
    if getattr(st, "_ai_stock_i18n_wrapped", False):
        return

    def current_lang() -> str:
        return str(st.session_state.get("ui_language", "zh"))

    def wrap_first_arg(func_name: str) -> None:
        original = getattr(st, func_name)

        def wrapped(*args, **kwargs):
            if args and isinstance(args[0], str):
                args = (t(args[0], current_lang()), *args[1:])
            if "label" in kwargs and isinstance(kwargs["label"], str):
                kwargs["label"] = t(kwargs["label"], current_lang())
            if "help" in kwargs and isinstance(kwargs["help"], str):
                kwargs["help"] = t(kwargs["help"], current_lang())
            return original(*args, **kwargs)

        setattr(st, func_name, wrapped)

    for name in [
        "write",
        "spinner",
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "info",
        "warning",
        "error",
        "success",
        "button",
        "download_button",
        "file_uploader",
        "checkbox",
        "slider",
        "number_input",
        "metric",
        "text_area",
        "segmented_control",
        "toggle",
        "radio",
        "selectbox",
        "multiselect",
    ]:
        if hasattr(st, name):
            wrap_first_arg(name)

    def wrap_delta_method(func_name: str) -> None:
        original = getattr(DeltaGenerator, func_name)

        def wrapped(self, *args, **kwargs):
            if args and isinstance(args[0], str):
                args = (t(args[0], current_lang()), *args[1:])
            if "label" in kwargs and isinstance(kwargs["label"], str):
                kwargs["label"] = t(kwargs["label"], current_lang())
            if "help" in kwargs and isinstance(kwargs["help"], str):
                kwargs["help"] = t(kwargs["help"], current_lang())
            return original(self, *args, **kwargs)

        setattr(DeltaGenerator, func_name, wrapped)

    for name in [
        "write",
        "spinner",
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "info",
        "warning",
        "error",
        "success",
        "button",
        "download_button",
        "file_uploader",
        "checkbox",
        "slider",
        "number_input",
        "metric",
        "text_area",
        "segmented_control",
        "toggle",
        "radio",
        "selectbox",
        "multiselect",
    ]:
        if hasattr(DeltaGenerator, name):
            wrap_delta_method(name)

    original_tabs = st.tabs

    def tabs_wrapped(labels):
        return original_tabs([t(str(label), current_lang()) for label in labels])

    st.tabs = tabs_wrapped

    original_expander = st.expander

    def expander_wrapped(label, *args, **kwargs):
        if isinstance(label, str):
            label = t(label, current_lang())
        return original_expander(label, *args, **kwargs)

    st.expander = expander_wrapped
    st._ai_stock_i18n_wrapped = True


_install_streamlit_i18n()


ACTION_LABELS_ZH = {
    "BUY_WATCH": "偏多觀察",
    "HOLD_WAIT": "等待確認",
    "SELL_OR_AVOID": "減碼/避開",
}
ACTION_LABELS = translate_mapping(ACTION_LABELS_ZH, UI_LANG)
ACTION_HELP_ZH = {
    "BUY_WATCH": "模型預估報酬大於近期波動門檻，但仍需等待價格接近買進參考或量價確認。",
    "HOLD_WAIT": "預估優勢不夠明顯，先觀察，不急著追價。",
    "SELL_OR_AVOID": "預估報酬偏弱或風險不對稱，偏向減碼、避開或等更低價。",
}
ACTION_HELP = translate_mapping(ACTION_HELP_ZH, UI_LANG)
ACTION_BADGE_ZH = {
    "BUY_WATCH": "🟢 偏多觀察",
    "HOLD_WAIT": "🟡 等待確認",
    "SELL_OR_AVOID": "🔴 減碼/避開",
}
ACTION_BADGE = translate_mapping(ACTION_BADGE_ZH, UI_LANG)
STRATEGY_SIDE_LABELS_ZH = {
    "BUY": "買進 / 加碼",
    "SELL": "賣出 / 減碼 / 保護",
    "WAIT": "等待確認",
    "HOLD": "等待確認",
    "HOLD_WAIT": "等待確認",
    "BUY_WATCH": "偏多觀察",
    "SELL_OR_AVOID": "減碼 / 避開",
}
STRATEGY_SIDE_LABELS = translate_mapping(STRATEGY_SIDE_LABELS_ZH, UI_LANG)


def _display_strategy_side(value: object) -> object:
    if pd.isna(value):
        return value
    return STRATEGY_SIDE_LABELS.get(str(value), value)


ORDER_ACTION_LABELS_ZH = {
    "REDUCE_OR_EXIT": "減碼 / 出清檢查",
    "STOP_LOSS_ALERT": "停損警示",
    "TAKE_PROFIT_ALERT": "停利警示",
    "ADD_OR_HOLD": "可加碼 / 持有",
    "WAIT_FOR_BUY_PRICE": "等待買價",
    "HOLD_WITH_TIGHT_STOP": "持有並收緊停損",
    "HOLD_WITH_STOP": "持有並掛停損",
    "REVIEW_MANUALLY": "人工檢查",
}
ORDER_ACTION_LABELS = translate_mapping(ORDER_ACTION_LABELS_ZH, UI_LANG)
YFINANCE_CACHE_TTL_SECONDS = 60 * 60


def _split_tickers(text: str) -> tuple[str, ...]:
    return tuple(t.strip().upper() for t in text.replace("\n", ",").split(",") if t.strip())


@st.cache_data(ttl=YFINANCE_CACHE_TTL_SECONDS, show_spinner=False)
def _load_yf(tickers: tuple[str, ...], period: str, interval: str) -> pd.DataFrame:
    return load_history(DataRequest(tickers, period=period, interval=interval, provider="yfinance"))


def _clear_cached_market_data() -> None:
    """Force the next rerun to fetch fresh market data and recompute dependent tables."""
    _load_yf.clear()
    clear_yfinance_disk_cache()
    _cached_snapshot.clear()
    _cached_correlations.clear()
    _cached_decision_report.clear()
    _cached_attribution.clear()
    _cached_backtest.clear()
    _cached_scenario_comparison.clear()
    _cached_smart_tuning_lite.clear()
    _cached_next_day_order_plan.clear()
    _cached_factor_research.clear()
    _cached_training_dataset.clear()


@st.cache_data(ttl=600, show_spinner=False)
def _cached_snapshot(prices: pd.DataFrame) -> pd.DataFrame:
    return compute_latest_technical_snapshot(prices)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_correlations(prices: pd.DataFrame) -> pd.DataFrame:
    return compute_correlation_table(prices)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_decision_report(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    return build_decision_report(prices, horizon=horizon)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_attribution(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    return build_attribution_report(prices, horizon=horizon)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_backtest(
    prices: pd.DataFrame,
    horizon: int,
    lookback: int,
    only_buy_watch: bool,
    trailing_stop_pct: float,
):
    return run_backtest(
        prices,
        horizon=horizon,
        lookback=lookback,
        step=horizon,
        only_buy_watch=only_buy_watch,
        exit_rule="stop_loss",
        trailing_stop_pct=trailing_stop_pct,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_scenario_comparison(
    prices: pd.DataFrame,
    horizons: tuple[int, ...],
    exit_rules: tuple[str, ...],
    lookback: int,
    only_buy_watch: bool,
    trailing_stop_pct: float,
) -> pd.DataFrame:
    return compare_backtest_scenarios(
        prices,
        horizons=list(horizons),
        exit_rules=list(exit_rules),
        lookback=lookback,
        only_buy_watch=only_buy_watch,
        trailing_stop_pct=trailing_stop_pct,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_smart_tuning_lite(
    prices: pd.DataFrame,
    horizons: tuple[int, ...],
    exit_rules: tuple[str, ...],
    stop_loss_pcts: tuple[float, ...],
    lookback: int,
    only_buy_watch: bool,
    trailing_stop_pct: float,
) -> pd.DataFrame:
    return build_smart_tuning_lite(
        prices,
        horizons=horizons,
        exit_rules=exit_rules,
        stop_loss_pcts=stop_loss_pcts,
        lookback=lookback,
        only_buy_watch=only_buy_watch,
        trailing_stop_pct=trailing_stop_pct,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_next_day_order_plan(prices: pd.DataFrame, decision_report: pd.DataFrame, holdings: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return build_next_day_order_plan(prices, decision_report, holdings, lookback=lookback)


@st.cache_data(ttl=900, show_spinner=False)
def _cached_smc_multitimeframe_signals(tickers: tuple[str, ...], daily_prices: pd.DataFrame, enable_intraday: bool = True) -> pd.DataFrame:
    frames: dict[str, pd.DataFrame] = {"1d": daily_prices[daily_prices["ticker"].astype(str).str.upper().isin(tickers)].copy() if not daily_prices.empty else pd.DataFrame()}
    if enable_intraday and tickers:
        try:
            frames["15m"] = load_history(DataRequest(tickers=tickers, period="5d", interval="15m", provider="yfinance"))
        except Exception:
            frames["15m"] = pd.DataFrame()
        try:
            frames["1h"] = load_history(DataRequest(tickers=tickers, period="60d", interval="1h", provider="yfinance"))
        except Exception:
            frames["1h"] = pd.DataFrame()
    return build_smc_timeframe_signals(frames)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_order_technical_context(one: pd.DataFrame, order_row: pd.Series | None) -> dict:
    return summarize_swing_order_technical_context(one, order_row)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_trade_structure(one: pd.DataFrame, swing_window: int, min_break_pct: float) -> dict[str, pd.DataFrame]:
    return detect_market_structure(one, swing_window=swing_window, min_break_pct=min_break_pct)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_trade_zones(one: pd.DataFrame, structure_result: dict[str, pd.DataFrame], lookback: int) -> pd.DataFrame:
    return build_trade_zones(one, structure_result, lookback=lookback)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_mtf_matrix(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    return build_mtf_matrix(prices, ticker)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_factor_research(
    prices: pd.DataFrame,
    window: int,
    horizon: int,
    target_threshold_pct: float,
    model_type: str,
):
    return build_factor_research_report(
        prices,
        window=window,
        horizon=horizon,
        target_threshold=target_threshold_pct / 100,
        model_type=model_type,
        top_n=20,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_factor_horizon_comparison(
    prices: pd.DataFrame,
    window: int,
    horizons: tuple[int, ...],
    target_threshold_pct: float,
    model_type: str,
) -> dict[str, pd.DataFrame]:
    return build_factor_horizon_comparison(
        prices,
        window=window,
        horizons=horizons,
        target_threshold=target_threshold_pct / 100,
        model_type=model_type,
        top_n=20,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_training_dataset(prices: pd.DataFrame, forward_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    dataset = build_training_dataset(prices, forward_days=forward_days, include_smc=True, include_patterns=True)
    ranked = compute_top_training_features(dataset, target_col=f"forward_return_{forward_days}d", top_n=30)
    return dataset, ranked


def _fmt_price(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.2f}"


def _fmt_pct(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):+.{digits}f}%"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if pd.notna(out) else default


def _humanize_report(report: pd.DataFrame) -> pd.DataFrame:
    if report.empty:
        return report
    out = report.copy()
    out["決策"] = out["action"].map(ACTION_LABELS).fillna(out["action"])
    out["Kelly 建議倉位"] = (out["kelly_fraction"] * 100).round(1)
    out = translate_dataframe_values(out, UI_LANG)
    rename = {
        "ticker": "代號",
        "last_close": "最新收盤",
        "predicted_price": "預估價",
        "expected_return_pct": "模型預估報酬%",
        "relationship_adjusted_return_pct": "關係調整後報酬%",
        "suggested_buy_price": "參考買進價",
        "suggested_sell_price": "參考賣出價",
        "stop_loss_price": "參考停損價",
        "risk_unit_pct": "風險單位%",
        "drawdown_from_60d_high_pct": "距60日高點%",
        "max_drawdown_60d_pct": "60日最大回撤%",
        "relationship_pressure_5d": "同/反向關係壓力%",
        "positive_corr_pressure_5d": "正相關壓力%",
        "negative_corr_pressure_5d": "反相關壓力%",
        "kelly_reason": "Kelly 原因",
        "action_reason": "決策原因",
        "rsi_14": "RSI14",
        "bb_position_20": "布林位置",
        "mfi_14": "MFI14",
        "model": "模型",
    }
    columns = [
        "ticker",
        "決策",
        "last_close",
        "expected_return_pct",
        "relationship_adjusted_return_pct",
        "suggested_buy_price",
        "suggested_sell_price",
        "stop_loss_price",
        "Kelly 建議倉位",
        "action_reason",
        "kelly_reason",
        "risk_unit_pct",
        "drawdown_from_60d_high_pct",
        "max_drawdown_60d_pct",
        "relationship_pressure_5d",
        "rsi_14",
        "bb_position_20",
        "mfi_14",
        "predicted_price",
        "model",
    ]
    return translate_dataframe_columns(out[[c for c in columns if c in out.columns]].rename(columns=rename), UI_LANG)


def _render_opportunity_radar(radar: pd.DataFrame) -> None:
    if radar.empty:
        return
    st.subheader("今日機會雷達")
    st.caption("把決策、Kelly、回測勝率與買賣價位濃縮成卡片；先看顏色與原因，再進表格細查。")
    color_by_tone = {
        "bullish": "#dcfce7",
        "neutral": "#fef9c3",
        "bearish": "#fee2e2",
    }
    border_by_tone = {
        "bullish": "#16a34a",
        "neutral": "#eab308",
        "bearish": "#dc2626",
    }
    cols = st.columns(min(3, len(radar)))
    for idx, row in radar.head(6).iterrows():
        with cols[idx % len(cols)]:
            tone = str(row.get("tone", "neutral"))
            action = ACTION_BADGE.get(str(row.get("action", "")), str(row.get("action", "")))
            reason = _(str(row.get("reason", "")))
            if len(reason) > 115:
                reason = reason[:112] + "…"
            st.markdown(
                f"""
<div style=\"border:1px solid {border_by_tone.get(tone, '#94a3b8')}; background:{color_by_tone.get(tone, '#f8fafc')}; border-radius:14px; padding:14px; min-height:230px; margin-bottom:12px;\">
  <div style=\"font-size:1.25rem; font-weight:800; color:#0f172a;\">{row.get('ticker', '')}</div>
  <div style=\"font-size:0.95rem; margin:4px 0 10px 0; color:#334155;\">{action}</div>
  <div style=\"display:grid; grid-template-columns:1fr 1fr; gap:6px; font-size:0.9rem; color:#0f172a;\">
    <div><b>{_('調整報酬')}</b><br>{_fmt_pct(row.get('adjusted_return_pct'))}</div>
    <div><b>{_('Kelly')}</b><br>{float(row.get('kelly_pct', 0) or 0):.1f}%</div>
    <div><b>{_('回測勝率')}</b><br>{_fmt_pct(row.get('win_rate_pct'))}</div>
    <div><b>{_('回測報酬')}</b><br>{_fmt_pct(row.get('backtest_return_pct'))}</div>
    <div><b>{_('買進')}</b><br>{_fmt_price(row.get('suggested_buy_price'))}</div>
    <div><b>{_('停損')}</b><br>{_fmt_price(row.get('stop_loss_price'))}</div>
  </div>
  <div style=\"margin-top:10px; font-size:0.82rem; color:#475569; line-height:1.35;\">{reason}</div>
</div>
""",
                unsafe_allow_html=True,
            )


def _render_strategy_health(cards: pd.DataFrame) -> None:
    if cards.empty:
        return
    st.subheader("策略健檢卡")
    st.caption("把回測勝率、最大回撤、Profit Factor、樣本數與 Kelly 狀態轉成可讀警訊。")
    icon = {"danger": "🔴", "warning": "🟠", "info": "🔵", "ok": "🟢"}
    color = {"danger": "#fee2e2", "warning": "#ffedd5", "info": "#dbeafe", "ok": "#dcfce7"}
    border = {"danger": "#dc2626", "warning": "#f97316", "info": "#2563eb", "ok": "#16a34a"}
    templates = {
        "low_sample": "樣本數不足：{ticker} 目前只有 {trades} 筆回測交易，勝率與報酬只能當方向參考。",
        "high_drawdown": "最大回撤偏高：{ticker} 最大回撤 {max_drawdown_pct:.1f}%，需要降低倉位、提高停損或改用更保守出場規則。",
        "low_profit_factor": "Profit Factor 低於 1：{ticker} 獲利交易不足以覆蓋虧損交易，暫不適合只靠此策略進場。",
        "low_win_rate": "勝率偏低：{ticker} 回測勝率 {win_rate_pct:.1f}%，需搭配更強確認訊號。",
        "negative_return": "累積報酬為負：{ticker} 在目前參數下累積報酬為 {cumulative_return_pct:.1f}%，代表策略方向暫時不佳。",
        "hold_zero_kelly": "等待確認：{ticker} Kelly 為 0 且決策為等待確認，代表模型優勢尚未大過近期風險。",
        "health_ok": "策略健檢通過：目前回測沒有明顯樣本不足、回撤過高或 Profit Factor 過低警訊。",
    }
    for row_idx, row in cards.head(8).iterrows():
        sev = str(row.get("severity", "info"))
        code = str(row.get("code", ""))
        template = templates.get(code)
        message = _(template, **row.to_dict()) if template else _(str(row.get("message", "")))
        title = _(str(row.get("title", "")))
        st.markdown(
            f"""
<div style=\"border-left:5px solid {border.get(sev, '#64748b')}; background:{color.get(sev, '#f8fafc')}; border-radius:10px; padding:10px 12px; margin-bottom:8px;\">
  <div style=\"font-weight:800; color:#0f172a;\">{icon.get(sev, 'ℹ️')} {row.get('ticker', '')} · {title}</div>
  <div style=\"color:#475569; font-size:0.92rem; line-height:1.35;\">{message}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _sparkline_svg(values: list[float], width: int = 120, height: int = 32) -> str:
    if not values:
        return ""
    clean = [float(v) for v in values if pd.notna(v)]
    if len(clean) < 2:
        return ""
    lo, hi = min(clean), max(clean)
    span = hi - lo if hi != lo else 1.0
    points = []
    for idx, value in enumerate(clean):
        x = idx / max(len(clean) - 1, 1) * width
        y = height - ((value - lo) / span * (height - 4) + 2)
        points.append(f"{x:.1f},{y:.1f}")
    color = "#16a34a" if clean[-1] >= clean[0] else "#dc2626"
    return f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}'><polyline fill='none' stroke='{color}' stroke-width='2.2' points='{' '.join(points)}'/></svg>"


def _render_watchlist(watchlist: pd.DataFrame) -> None:
    if watchlist.empty:
        return
    with st.sidebar:
        st.markdown("##### Watchlist")
        for _, row in watchlist.head(10).iterrows():
            badge = ACTION_BADGE.get(str(row.get("action", "")), "—")
            st.markdown(
                f"""
<div style=\"border:1px solid #e2e8f0; border-radius:10px; padding:8px; margin-bottom:8px; background:#ffffff;\">
  <div style=\"display:flex; justify-content:space-between; align-items:center; gap:8px;\">
    <div><b>{row.get('ticker', '')}</b><br><span style=\"font-size:0.78rem;color:#64748b;\">{badge}</span></div>
    <div style=\"text-align:right;\"><b>{_fmt_price(row.get('last_close'))}</b><br><span style=\"font-size:0.78rem;color:{'#16a34a' if float(row.get('change_1d_pct', 0) or 0) >= 0 else '#dc2626'};\">{_fmt_pct(row.get('change_1d_pct'))}</span></div>
  </div>
  <div style=\"margin-top:4px;\">{_sparkline_svg(row.get('sparkline', []))}</div>
</div>
""",
                unsafe_allow_html=True,
            )


def _build_market_heatmap_chart(heatmap: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if heatmap.empty:
        return fig
    fig.add_trace(
        go.Treemap(
            labels=heatmap["ticker"],
            parents=[""] * len(heatmap),
            values=heatmap["size"],
            text=heatmap["label"],
            textinfo="text",
            marker={
                "colors": heatmap["color_value"],
                "colorscale": "RdYlGn",
                "cmid": 0,
                "colorbar": {"title": _("5日報酬%")},
            },
            customdata=heatmap[["return_1d_pct", "return_5d_pct", "signal_score", "action"]],
            hovertemplate="%{label}<br>1D=%{customdata[0]:+.2f}%<br>5D=%{customdata[1]:+.2f}%<br>Signal=%{customdata[2]:+.2f}<br>%{customdata[3]}<extra></extra>",
        )
    )
    fig.update_layout(height=420, margin={"l": 10, "r": 10, "t": 25, "b": 10})
    return fig


def _humanize_next_day_order_plan(plan: pd.DataFrame) -> pd.DataFrame:
    if plan.empty:
        return plan
    out = plan.copy()
    if "action" in out.columns:
        out["action"] = out["action"].map(ACTION_LABELS).fillna(out["action"])
    probability_labels = {
        "HIGH": "高",
        "MEDIUM": "中",
        "LOW_MEDIUM": "低到中",
        "LOW_STRATEGY_LEVEL": "低，偏策略價",
    }
    order_labels = {
        "BUY_LIMIT": "買進限價單",
        "ADD_LIMIT": "加碼限價單",
        "TAKE_PROFIT_LIMIT": "分批停利限價單",
        "REBOUND_REDUCE_LIMIT": "反彈減碼限價單",
        "PROTECTIVE_STOP": "保護性停損單",
        "PROTECT_PROFIT_STOP": "獲利保護停損單",
        "REDUCE_OR_AVOID": "減碼 / 避開",
        "NO_ORDER_WAIT": "不掛單，等待確認",
        "BRACKET_PLAN": "停利 + 停損 OCO 計畫",
    }
    for col in ["buy_touch_probability", "sell_touch_probability", "tactical_stop_touch_probability"]:
        if col in out.columns:
            out[col] = out[col].map(probability_labels).fillna(out[col])
    if "suggested_order_type" in out.columns:
        out["suggested_order_type"] = out["suggested_order_type"].map(order_labels).fillna(out["suggested_order_type"])
    if "final_side" in out.columns:
        out["final_side"] = out["final_side"].map(_display_strategy_side)
    out["隔日買進區"] = out.apply(lambda row: f"{_fmt_price(row.get('next_day_buy_low'))} - {_fmt_price(row.get('next_day_buy_high'))}", axis=1)
    out["隔日賣出區"] = out.apply(lambda row: f"{_fmt_price(row.get('next_day_sell_low'))} - {_fmt_price(row.get('next_day_sell_high'))}", axis=1)
    if "final_buy_low" in out.columns:
        out["最終買進區"] = out.apply(lambda row: f"{_fmt_price(row.get('final_buy_low'))} - {_fmt_price(row.get('final_buy_high'))}", axis=1)
        out["最終賣出區"] = out.apply(lambda row: f"{_fmt_price(row.get('final_sell_low'))} - {_fmt_price(row.get('final_sell_high'))}", axis=1)
    out = translate_dataframe_values(out, UI_LANG)
    columns = [
        "ticker",
        "quantity",
        "current_price",
        "action",
        "suggested_order_type",
        "final_recommendation_source",
        "final_side",
        "final_strategy",
        "final_strategy_edge_score",
        "最終買進區",
        "最終賣出區",
        "final_stop_loss",
        "final_take_profit",
        "priority_score",
        "buy_urgency_score",
        "sell_urgency_score",
        "smc_confidence_score",
        "smc_bias",
        "smc_timeframe_summary",
        "隔日買進區",
        "隔日賣出區",
        "tactical_stop_price",
        "hard_stop_price",
        "strategy_buy_price",
        "strategy_take_profit_price",
        "buy_touch_probability",
        "sell_touch_probability",
        "tactical_stop_touch_probability",
        "median_intraday_range_pct",
        "p80_intraday_range_pct",
        "reason",
    ]
    rename = {
        "ticker": "代號",
        "quantity": "持有數量",
        "current_price": "目前價格",
        "action": "模型決策",
        "suggested_order_type": "建議單型",
        "final_recommendation_source": "最終推薦來源",
        "final_side": "最終方向",
        "final_strategy": "最終策略",
        "final_strategy_edge_score": "最終策略適配分數",
        "final_stop_loss": "最終停損",
        "final_take_profit": "最終停利",
        "priority_score": "優先處理分數",
        "buy_urgency_score": "買進急迫度",
        "sell_urgency_score": "賣出急迫度",
        "smc_confidence_score": "SMC信心分數",
        "smc_bias": "SMC方向",
        "smc_timeframe_summary": "SMC多週期摘要",
        "tactical_stop_price": "戰術停損",
        "hard_stop_price": "硬停損",
        "strategy_buy_price": "策略買進價",
        "strategy_take_profit_price": "策略停利價",
        "buy_touch_probability": "買進成交機率",
        "sell_touch_probability": "賣出成交機率",
        "tactical_stop_touch_probability": "戰術停損觸及機率",
        "median_intraday_range_pct": "20日中位日內波動%",
        "p80_intraday_range_pct": "20日80分位日內波動%",
        "reason": "原因",
    }
    return translate_dataframe_columns(out[[c for c in columns if c in out.columns]].rename(columns=rename), UI_LANG)


def _render_tradingview_action_board(order_plan: pd.DataFrame) -> None:
    """Render a compact TradingView-like action board for today's dashboard."""
    st.subheader("TradingView 式行動清單")
    st.caption("把交易計畫濃縮成 watchlist：先看最終方向、優先分數、買賣區與下一步。等待確認不是沒有模型或沒有回測，而是目前優勢還不足以追價。")
    if order_plan.empty:
        st.info("尚無可用的隔日掛單資料；請確認持倉檔或先到交易計畫頁產生掛單清單。")
        return
    top = order_plan.sort_values("priority_score", ascending=False).head(8).copy()
    board = pd.DataFrame(
        {
            "代號": top.get("ticker", pd.Series(dtype=str)).astype(str),
            "最終方向": top.get("final_side", top.get("action", pd.Series(dtype=str))).fillna("").map(_display_strategy_side).astype(str),
            "優先分數": top.get("priority_score", pd.Series(dtype=float)).map(lambda v: int(round(_safe_float(v)))),
            "買進區": top.apply(lambda row: f"{_fmt_price(row.get('final_buy_low', row.get('next_day_buy_low')))} - {_fmt_price(row.get('final_buy_high', row.get('next_day_buy_high')))}", axis=1),
            "賣出區": top.apply(lambda row: f"{_fmt_price(row.get('final_sell_low', row.get('next_day_sell_low')))} - {_fmt_price(row.get('final_sell_high', row.get('next_day_sell_high')))}", axis=1),
            "最終策略": top.get("final_strategy", pd.Series(dtype=str)).fillna("基礎掛單計畫").astype(str),
            "下一步": top.get("final_side", top.get("action", pd.Series(dtype=str))).fillna("").map(
                lambda side: "下一步：打開交易計畫或圖表分析" if str(side) in {"BUY", "SELL", "BUY_WATCH", "SELL_OR_AVOID"} else "下一步：等待價格接近區間再確認"
            ),
        }
    )
    st.dataframe(
        board,
        hide_index=True,
        use_container_width=True,
        column_config={
            "優先分數": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
            "下一步": st.column_config.TextColumn(width="large"),
        },
    )


def _urgency_alpha(score: float) -> float:
    try:
        value = float(score)
    except (TypeError, ValueError):
        value = 0.0
    return max(0.08, min(0.92, value / 100.0))


def _render_next_day_order_heatmap(plan: pd.DataFrame) -> None:
    """Render a styled priority table without raw HTML rows leaking to Markdown.

    Earlier versions used a hand-written HTML table string. Some Streamlit
    frontends / Markdown render paths can show raw table-row fragments as source
    text, which is confusing in a decision dashboard.  A pandas Styler keeps the
    heat-map semantics while letting Streamlit own the table renderer.
    """
    if plan.empty:
        return
    top = plan.sort_values("priority_score", ascending=False).head(10).copy()
    display = pd.DataFrame(
        {
            "標的": top.get("ticker", pd.Series(dtype=str)).astype(str),
            "建議單型": top.get("suggested_order_type", pd.Series(dtype=str)).astype(str),
            "最終策略": top.get("final_strategy", pd.Series(dtype=str)).fillna("").astype(str),
            "最終方向": top.get("final_side", pd.Series(dtype=str)).fillna("").map(_display_strategy_side).astype(str),
            "買進急迫度": top.get("buy_urgency_score", pd.Series(dtype=float)).map(lambda v: int(round(_safe_float(v)))),
            "買進區": top.apply(lambda row: f"{_fmt_price(row.get('final_buy_low', row.get('next_day_buy_low')))} - {_fmt_price(row.get('final_buy_high', row.get('next_day_buy_high')))}", axis=1),
            "賣出急迫度": top.get("sell_urgency_score", pd.Series(dtype=float)).map(lambda v: int(round(_safe_float(v)))),
            "賣出區": top.apply(lambda row: f"{_fmt_price(row.get('final_sell_low', row.get('next_day_sell_low')))} - {_fmt_price(row.get('final_sell_high', row.get('next_day_sell_high')))}", axis=1),
            "優先分數": top.get("priority_score", pd.Series(dtype=float)).map(lambda v: int(round(_safe_float(v)))),
            "SMC方向": top.get("smc_bias", pd.Series(dtype=str)).astype(str),
        }
    )
    display["處理方向"] = display.apply(
        lambda row: "買進 / 加碼" if int(row["買進急迫度"]) >= int(row["賣出急迫度"]) else "賣出 / 減碼 / 保護",
        axis=1,
    )

    def urgency_style(value: object, color: str) -> str:
        score = _safe_float(value, 0.0)
        alpha = _urgency_alpha(score)
        if color == "green":
            return f"background-color: rgba(22, 163, 74, {alpha:.2f}); color: #052e16; font-weight: 800;"
        return f"background-color: rgba(220, 38, 38, {alpha:.2f}); color: #450a0a; font-weight: 800;"

    def priority_style(value: object) -> str:
        score = _safe_float(value, 0.0)
        alpha = max(0.08, min(0.75, score / 100.0))
        return f"background-color: rgba(37, 99, 235, {alpha:.2f}); color: #0f172a; font-weight: 800;"

    styled = (
        display.style
        .map(lambda value: urgency_style(value, "green"), subset=["買進急迫度"])
        .map(lambda value: urgency_style(value, "red"), subset=["賣出急迫度"])
        .map(priority_style, subset=["優先分數"])
        .set_properties(subset=["標的", "建議單型", "最終策略", "最終方向", "買進區", "賣出區", "SMC方向", "處理方向"], **{"font-weight": "600"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


_INDICATOR_GLOSSARY = [
    ("🕯️", "K線", "每根 K 棒顯示開高低收；搭配十字游標看隔日掛單區是否靠近轉折棒。"),
    ("━━", "SMA20 / SMA60", "短中期均線；SMA20 在 SMA60 上且價格回踩不破，偏波段多頭。"),
    ("〰️", "Bollinger", "布林通道；買進區靠近下緣且動能止跌通常比追上緣更適合限價買。"),
    ("⚡", "RSI14", "動能強弱；30 附近偏超賣，70 附近偏過熱，40-55 回升常用於 swing 回踩確認。"),
    ("▮▮", "MACD / MACD Hist", "趨勢動能；柱體由負轉正或負值收斂代表賣壓可能減弱。"),
    ("▥", "成交量 / Volume Ratio", "量能確認；突破或吞噬 K 搭配放量，訊號可信度較高。"),
    ("◇", "UKF Momentum", "多指標去噪動能；高於 20 偏多，低於 -20 偏弱，中間代表雜訊較多。"),
    ("▧", "FVG / IFVG", "公平價值缺口與失效後反轉缺口；買進區靠近 bullish FVG 較有回補依據，IFVG 常作反壓/支撐角色反轉。"),
    ("▣", "SMC Order Block", "smartmoneyconcepts 推導的訂單塊；隔日買/賣區與 OB 重疊可提高技術理由。"),
    ("●", "SMC Liquidity", "流動性高低點；掃過前高/前低後收回，常對應假突破或反向機會。"),
    ("▲▼", "Swing High / Low", "擺動高低點；用來判斷結構與掛單區是否靠近關鍵支撐壓力。"),
    ("✚", "BOS / ChoCH", "結構突破 / 結構轉換；BOS 看延續，ChoCH 看可能轉向。"),
    ("◆", "SFP", "Swing Failure Pattern，掃停損假突破後收回，常用於避免追高殺低。"),
]


def _render_indicator_glossary() -> None:
    with st.expander("圖例名詞說明 / Legend glossary", expanded=False):
        st.caption("前方符號用來快速對應圖中的線條、區塊或 marker；Plotly legend 文字本身不支援自訂 hover tooltip，因此以此說明表補足。")
        for icon, name, desc in _INDICATOR_GLOSSARY:
            st.markdown(
                f"<span style='display:inline-block;min-width:2.1rem;text-align:center;font-weight:800'>{html.escape(icon)}</span> "
                f"<b>{html.escape(name)}</b>：{html.escape(desc)}",
                unsafe_allow_html=True,
            )


def _humanize_portfolio_order_plan(plan: pd.DataFrame) -> pd.DataFrame:
    if plan.empty:
        return plan
    out = plan.copy()
    if "action" in out.columns:
        out["action"] = out["action"].map(ACTION_LABELS).fillna(out["action"])
    if "suggested_order_action" in out.columns:
        out["suggested_order_action"] = out["suggested_order_action"].map(ORDER_ACTION_LABELS).fillna(out["suggested_order_action"])
    out = translate_dataframe_values(out, UI_LANG)
    return translate_dataframe_columns(
        out.rename(
            columns={
                "ticker": "代號",
                "name_zh": "名稱",
                "quantity": "持有數量",
                "market_value": "持倉市值",
                "portfolio_weight_pct": "持倉權重%",
                "broker_current_price": "帳戶現價",
                "last_close": "行情收盤",
                "price_gap_pct": "帳戶/行情差異%",
                "cost_price": "成本價",
                "unrealized_pnl": "未實現損益",
                "unrealized_pnl_pct": "未實現損益%",
                "today_pnl": "今日損益",
                "today_pnl_pct_of_value": "今日損益/市值%",
                "action": "模型決策",
                "suggested_order_action": "操作建議",
                "kelly_pct": "Kelly%",
                "add_buy_limit_price": "加碼限價參考",
                "stop_loss_order_price": "停損單參考",
                "take_profit_order_price": "停利單參考",
                "relationship_adjusted_return_pct": "關係調整後報酬%",
                "risk_unit_pct": "風險單位%",
                "max_drawdown_60d_pct": "60日最大回撤%",
                "order_note": "操作說明",
                "action_reason": "決策原因",
                "kelly_reason": "Kelly 原因",
            }
        ),
        UI_LANG,
    )


def _render_portfolio_summary(summary: dict) -> None:
    if not summary or int(summary.get("positions", 0) or 0) <= 0:
        return
    st.subheader("我的持倉狀態")
    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("持倉檔數", f"{int(summary.get('positions', 0) or 0)}")
    p2.metric("總市值", _fmt_price(summary.get("total_market_value")))
    p3.metric("今日損益", _fmt_price(summary.get("total_today_pnl")))
    p4.metric("最大持倉", str(summary.get("largest_ticker") or "—"), _fmt_pct(summary.get("largest_weight_pct"), 1))
    alerts = int(summary.get("stop_alerts", 0) or 0) + int(summary.get("take_profit_alerts", 0) or 0) + int(summary.get("reduce_alerts", 0) or 0)
    p5.metric("風險/停利提醒", f"{alerts}")


def _humanize_smart_tuning(tuning: pd.DataFrame) -> pd.DataFrame:
    if tuning.empty:
        return tuning
    out = tuning.copy()
    for col in ["win_rate", "stop_loss_hit_rate", "cumulative_return", "max_drawdown", "avg_trade_return", "stop_loss_pct"]:
        if col in out.columns:
            out[col] = out[col] * 100
    out = translate_dataframe_values(out, UI_LANG)
    return translate_dataframe_columns(
        out.rename(
            columns={
                "rank": "排名",
                "ticker": "代號",
                "scenario": "情境",
                "holding_days": "持有天數",
                "exit_rule": "出場規則",
                "stop_loss_pct": "風險寬度%",
                "score": "綜合分數",
                "trades": "交易次數",
                "win_rate": "勝率%",
                "stop_loss_hit_rate": "停損命中率%",
                "cumulative_return": "累積報酬%",
                "max_drawdown": "最大回撤%",
                "avg_trade_return": "平均單筆報酬%",
                "profit_factor": "Profit Factor",
            }
        ),
        UI_LANG,
    )


def _humanize_strategy_workbench_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    out = summary.copy()
    for col in ["win_rate", "stop_hit_rate"]:
        if col in out.columns:
            out[col] = out[col] * 100
    out = translate_dataframe_values(out, UI_LANG)
    return translate_dataframe_columns(
        out.rename(
            columns={
                "ticker": "代號",
                "strategy_label": "策略欄位",
                "holding_days": "持有天數",
                "risk_tolerance_pct": "風險耐受度%",
                "backtest_range": "回測期間",
                "trade_count": "交易次數",
                "win_rate": "勝率%",
                "avg_return_pct": "平均報酬%",
                "cumulative_return_pct": "累積報酬%",
                "max_drawdown_pct": "最大回撤%",
                "stop_hit_rate": "停損命中率%",
                "profit_factor": "Profit Factor",
                "strategy_edge_score": "策略適配分數",
                "latest_signal": "最新策略訊號",
            }
        ),
        UI_LANG,
    )


def _humanize_strategy_order_recommendations(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return orders
    out = orders.copy()
    if "side" in out.columns:
        out["side"] = out["side"].map(_display_strategy_side)
    out = translate_dataframe_values(out, UI_LANG)
    return translate_dataframe_columns(
        out.rename(
            columns={
                "ticker": "代號",
                "best_strategy_label": "最佳策略",
                "holding_days": "持有天數",
                "risk_tolerance_pct": "風險耐受度%",
                "side": "處理方向",
                "urgency_score": "買賣迫切度",
                "strategy_edge_score": "策略適配分數",
                "buy_low": "買進區低",
                "buy_high": "買進區高",
                "sell_low": "賣出區低",
                "sell_high": "賣出區高",
                "stop_loss": "停損價",
                "take_profit": "停利參考",
                "reason": "理由",
            }
        ),
        UI_LANG,
    )


def _build_strategy_score_chart(summary: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if summary.empty:
        return fig
    work = summary.copy()
    work["label"] = work["ticker"].astype(str) + " / " + work["strategy_label"].astype(str)
    work = work.sort_values("strategy_edge_score", ascending=True).tail(25)
    fig.add_trace(
        go.Bar(
            x=work["strategy_edge_score"],
            y=work["label"],
            orientation="h",
            marker_color=["#16a34a" if float(v) >= 65 else "#eab308" if float(v) >= 45 else "#dc2626" for v in work["strategy_edge_score"]],
            customdata=work[["win_rate", "trade_count", "avg_return_pct", "profit_factor"]],
            hovertemplate="%{y}<br>適配分數=%{x:.0f}<br>勝率=%{customdata[0]:.1%}<br>交易=%{customdata[1]}<br>平均報酬=%{customdata[2]:.2f}%<br>PF=%{customdata[3]:.2f}<extra></extra>",
        )
    )
    fig.update_layout(height=520, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis={"range": [0, 100], "title": "策略適配分數"})
    return fig


def _build_smart_tuning_chart(tuning: pd.DataFrame) -> go.Figure:
    work = tuning.sort_values("score", ascending=True).tail(20).copy()
    fig = go.Figure()
    if work.empty:
        return fig
    fig.add_trace(
        go.Bar(
            x=work["score"],
            y=work["scenario"],
            orientation="h",
            marker_color=["#16a34a" if v >= 0 else "#dc2626" for v in work["score"]],
            customdata=work[["win_rate", "cumulative_return", "max_drawdown", "profit_factor"]],
            hovertemplate="%{y}<br>score=%{x:.2f}<br>win=%{customdata[0]:.1%}<br>return=%{customdata[1]:.2%}<br>drawdown=%{customdata[2]:.2%}<br>PF=%{customdata[3]:.2f}<extra></extra>",
        )
    )
    fig.update_layout(height=520, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis_title=_("綜合分數"))
    return fig


def _humanize_mtf_matrix(mtf: pd.DataFrame) -> pd.DataFrame:
    if mtf.empty:
        return mtf
    return translate_dataframe_columns(
        mtf.rename(
            columns={
                "timeframe": "時間框架",
                "trend_state": "趨勢狀態",
                "momentum_score": "動能分數",
                "volume_score": "量能分數",
                "volatility_score": "波動分數",
                "signal_strength": "訊號強度",
                "description": "說明",
            }
        ),
        UI_LANG,
    )


def _score_breakdown_frame(score: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"項目": "Trend", "分數": score.get("trend_score")},
            {"項目": "Momentum", "分數": score.get("momentum_score")},
            {"項目": "Volume", "分數": score.get("volume_score")},
            {"項目": "Structure", "分數": score.get("structure_score")},
            {"項目": "Risk", "分數": score.get("risk_score")},
            {"項目": "Portfolio", "分數": score.get("portfolio_score")},
            {"項目": "Composite", "分數": score.get("composite_score")},
        ]
    )


def _build_score_breakdown_chart(score: dict) -> go.Figure:
    frame = _score_breakdown_frame(score)
    fig = go.Figure(
        go.Bar(
            x=frame["分數"],
            y=frame["項目"],
            orientation="h",
            marker_color=["#16a34a" if float(v or 0) >= 60 else "#eab308" if float(v or 0) >= 40 else "#dc2626" for v in frame["分數"]],
            hovertemplate="%{y}: %{x:.1f}<extra></extra>",
        )
    )
    fig.update_layout(height=280, xaxis={"range": [0, 100], "title": _("分數")}, margin={"l": 10, "r": 10, "t": 15, "b": 10})
    return fig


def _render_trade_plan_card(plan: dict, score: dict) -> None:
    status = str(score.get("status", plan.get("plan_status", "HOLD_WAIT")))
    st.metric("Current Price", _fmt_price(plan.get("current_price")))
    st.metric("Composite Score", f"{float(score.get('composite_score', 0) or 0):.0f}/100", status)
    st.metric("Action Badge", ACTION_BADGE.get(str(plan.get("action", "")), str(plan.get("action", ""))))
    p1, p2 = st.columns(2)
    p1.metric("Entry", _fmt_price(plan.get("entry_price")))
    p2.metric("SL", _fmt_price(plan.get("stop_loss_price")))
    t1, t2, t3 = st.columns(3)
    t1.metric("TP1", _fmt_price(plan.get("take_profit_1")))
    t2.metric("TP2", _fmt_price(plan.get("take_profit_2")))
    t3.metric("TP3", _fmt_price(plan.get("take_profit_3")))
    r1, r2 = st.columns(2)
    r1.metric("RR Ratio", f"{float(plan.get('rr_ratio', 0) or 0):.2f}")
    r2.metric("Kelly Fraction", f"{float(plan.get('kelly_fraction', 0) or 0) * 100:.1f}%")
    st.metric("Plan Status", str(plan.get("plan_status", "—")))
    st.warning("研究輔助，不自動下單。實際下單前請自行確認券商報價、流動性、稅費與個人風險承受度。")


def _humanize_snapshot(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty:
        return snapshot
    out = snapshot.copy()
    rename = {
        "ticker": "代號",
        "date": "日期",
        "last_close": "最新收盤",
        "return_1d": "1日報酬",
        "return_5d": "5日報酬",
        "return_20d": "20日報酬",
        "sma_20": "SMA20",
        "sma_60": "SMA60",
        "ema_20": "EMA20",
        "ema_60": "EMA60",
        "rsi_14": "RSI14",
        "macd_hist": "MACD 柱",
        "bb_position_20": "布林位置",
        "atr_pct_14": "ATR%",
        "stoch_k_14": "KD-K",
        "stoch_d_3": "KD-D",
        "mfi_14": "MFI14",
        "volatility_20d": "20日年化波動",
        "volume_ratio_20d": "量能比",
        "drawdown_from_60d_high": "距60日高點",
        "max_drawdown_60d": "60日最大回撤",
        "support_20": "20日支撐",
        "resistance_20": "20日壓力",
    }
    percent_cols = ["return_1d", "return_5d", "return_20d", "volatility_20d", "atr_pct_14", "drawdown_from_60d_high", "max_drawdown_60d"]
    for col in percent_cols:
        if col in out.columns:
            out[col] = out[col] * 100
    return translate_dataframe_columns(out.rename(columns=rename), UI_LANG)


def _build_price_chart(one: pd.DataFrame, ticker: str, show_volume: bool) -> go.Figure:
    ind = add_indicators(one)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=one["date"],
            open=one["open"],
            high=one["high"],
            low=one["low"],
            close=one["close"],
            name=ticker,
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
        )
    )
    fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_20"], name="SMA20", line={"color": "#2563eb"}))
    fig.add_trace(go.Scatter(x=ind["date"], y=ind["sma_60"], name="SMA60", line={"color": "#f97316"}))
    if show_volume:
        fig.add_trace(
            go.Bar(
                x=one["date"],
                y=one["volume"],
                name="成交量",
                marker_color="rgba(100,116,139,0.25)",
                yaxis="y2",
            )
        )
        fig.update_layout(yaxis2={"overlaying": "y", "side": "right", "showgrid": False, "title": "Volume"})
    fig.update_layout(
        height=560,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig


def _build_corr_heatmap(correlations: pd.DataFrame, tickers: list[str]) -> go.Figure:
    matrix = pd.DataFrame(1.0, index=tickers, columns=tickers)
    for _, row in correlations.iterrows():
        matrix.loc[row["ticker_a"], row["ticker_b"]] = row["return_corr"]
        matrix.loc[row["ticker_b"], row["ticker_a"]] = row["return_corr"]
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.index,
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            text=matrix.round(2).values,
            texttemplate="%{text}",
            hovertemplate="%{y} vs %{x}<br>相關係數=%{z:.2f}<extra></extra>",
        )
    )
    fig.update_layout(height=420, margin={"l": 10, "r": 10, "t": 20, "b": 10})
    return fig


def _build_attribution_chart(rows: pd.DataFrame, ticker: str) -> go.Figure:
    work = rows[rows["ticker"] == ticker].copy()
    work = work.sort_values("contribution")
    colors = ["#dc2626" if value < 0 else "#16a34a" for value in work["contribution"]]
    fig = go.Figure(
        go.Bar(
            x=work["contribution"] * 100,
            y=work["feature_label"],
            orientation="h",
            marker_color=colors,
            customdata=work[["value", "method"]],
            hovertemplate="%{y}<br>歸因=%{x:.3f}%<br>指標值=%{customdata[0]:.4f}<br>%{customdata[1]}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color="#64748b", line_width=1)
    fig.update_layout(height=430, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis_title="對未來報酬的模型歸因（百分點）")
    return fig


def _humanize_backtest_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    out = summary.copy()
    percent_cols = ["win_rate", "stop_loss_hit_rate", "time_exit_rate", "trailing_stop_hit_rate", "cumulative_return", "max_drawdown", "avg_trade_return"]
    for col in percent_cols:
        if col in out.columns:
            out[col] = out[col] * 100
    out = translate_dataframe_values(out, UI_LANG)
    return translate_dataframe_columns(
        out.rename(
            columns={
                "ticker": "代號",
                "strategy": "策略",
                "holding_days": "持有天數",
                "exit_rule": "出場規則",
                "trades": "交易次數",
                "win_rate": "勝率%",
                "stop_loss_hit_rate": "停損命中率%",
                "time_exit_rate": "時間出場率%",
                "trailing_stop_hit_rate": "移動停損率%",
                "cumulative_return": "累積報酬%",
                "max_drawdown": "最大回撤%",
                "avg_trade_return": "平均單筆報酬%",
                "profit_factor": "Profit Factor",
            }
        ),
        UI_LANG,
    )


def _humanize_backtest_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades.copy()
    for col in ["return_pct", "kelly_fraction"]:
        if col in out.columns:
            out[col] = out[col] * 100
    if "action" in out.columns:
        out["action"] = out["action"].map(ACTION_LABELS).fillna(out["action"])
    out = translate_dataframe_values(out, UI_LANG)
    return translate_dataframe_columns(
        out.rename(
            columns={
                "ticker": "代號",
                "entry_date": "進場日",
                "exit_date": "出場日",
                "entry_price": "進場價",
                "exit_price": "出場價",
                "return_pct": "單筆報酬%",
                "stop_hit": "是否停損",
                "exit_rule": "設定出場規則",
                "exit_reason": "實際出場原因",
                "holding_days": "設定持有天數",
                "action": "當時決策",
                "expected_return_pct": "當時模型預估%",
                "relationship_adjusted_return_pct": "當時關係調整%",
                "kelly_fraction": "當時 Kelly%",
            }
        ),
        UI_LANG,
    )


def _build_equity_chart(equity_curve: pd.DataFrame, ticker: str | None = None) -> go.Figure:
    fig = go.Figure()
    work = equity_curve.copy()
    if ticker:
        work = work[work["ticker"] == ticker]
    for name, group in work.groupby("ticker"):
        fig.add_trace(
            go.Scatter(
                x=group["date"],
                y=group["cumulative_return"] * 100,
                mode="lines+markers",
                name=str(name),
                hovertemplate="%{x}<br>" + _("累積報酬%") + "=%{y:.2f}%<extra></extra>",
            )
        )
    fig.add_hline(y=0, line_color="#64748b", line_width=1)
    fig.update_layout(height=360, margin={"l": 20, "r": 20, "t": 40, "b": 20}, yaxis_title=_("累積報酬%"), xaxis_title=_("日期"))
    return fig


def _build_scenario_comparison_chart(comparison: pd.DataFrame) -> go.Figure:
    work = comparison.copy()
    if work.empty:
        return go.Figure()
    work["label"] = work["ticker"].astype(str) + "｜" + work["strategy"].astype(str)
    work = work.sort_values("cumulative_return", ascending=True).tail(20)
    colors = ["#16a34a" if value >= 0 else "#dc2626" for value in work["cumulative_return"]]
    fig = go.Figure(
        go.Bar(
            x=work["cumulative_return"] * 100,
            y=work["label"],
            orientation="h",
            marker_color=colors,
            customdata=work[["win_rate", "max_drawdown", "stop_loss_hit_rate", "trades"]],
            hovertemplate="%{y}<br>累積報酬=%{x:.2f}%<br>勝率=%{customdata[0]:.1%}<br>最大回撤=%{customdata[1]:.2%}<br>停損/出場命中=%{customdata[2]:.1%}<br>交易=%{customdata[3]}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color="#64748b", line_width=1)
    fig.update_layout(height=520, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis_title=_("累積報酬%"))
    return fig


def _build_factor_horizon_trend_chart(summary: pd.DataFrame) -> go.Figure:
    trends = build_horizon_metric_trends(summary)
    fig = go.Figure()
    if trends.empty:
        return fig
    fig.add_trace(
        go.Scatter(
            x=trends["horizon"],
            y=trends["accuracy"] * 100,
            mode="lines+markers",
            name="測試勝率 / Accuracy",
            line={"color": "#16a34a", "width": 3},
            hovertemplate="預測%{x}天後<br>勝率=%{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trends["horizon"],
            y=trends["auc"] * 100,
            mode="lines+markers",
            name="AUC",
            line={"color": "#2563eb", "width": 3},
            hovertemplate="預測%{x}天後<br>AUC=%{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trends["horizon"],
            y=trends["baseline_up_rate"] * 100,
            mode="lines+markers",
            name="歷史上漲率 baseline",
            line={"color": "#94a3b8", "dash": "dash"},
            hovertemplate="預測%{x}天後<br>baseline=%{y:.1f}%<extra></extra>",
        )
    )
    fig.add_hline(y=50, line_color="#64748b", line_width=1, line_dash="dot")
    fig.update_layout(
        height=360,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        xaxis={"title": "預測幾天後", "dtick": 1},
        yaxis_title="百分比%",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig


def _build_factor_ticker_horizon_heatmap(summary: pd.DataFrame, metric: str = "accuracy") -> go.Figure:
    metric_labels = {
        "accuracy": "測試勝率 / Accuracy",
        "auc": "AUC",
        "baseline_up_rate": "歷史上漲率 baseline",
    }
    matrix = build_ticker_horizon_metric_matrix(summary, metric=metric)
    fig = go.Figure()
    if matrix.empty:
        return fig
    values = matrix.astype(float) * 100
    fig.add_trace(
        go.Heatmap(
            z=values.to_numpy(),
            x=[f"{int(col)}天" for col in values.columns],
            y=values.index.astype(str),
            colorscale="RdYlGn",
            zmid=50,
            zmin=0,
            zmax=100,
            text=values.round(1).astype(str) + "%",
            texttemplate="%{text}",
            hovertemplate="代號=%{y}<br>預測%{x}天後<br>" + metric_labels.get(metric, metric) + "=%{z:.1f}%<extra></extra>",
            colorbar={"title": "%"},
        )
    )
    fig.update_layout(
        height=max(280, min(720, 120 + 42 * len(values.index))),
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        xaxis_title="預測幾天後",
        yaxis_title="股票代號",
    )
    return fig


def _build_factor_importance_chart(importance: pd.DataFrame, ticker: str) -> go.Figure:
    work = importance[importance["ticker"] == ticker].copy().sort_values("importance").tail(20)
    colors = ["#16a34a" if value >= 0 else "#dc2626" for value in work["signed_contribution"]]
    fig = go.Figure(
        go.Bar(
            x=work["importance"],
            y=work["feature_label"],
            orientation="h",
            marker_color=colors,
            customdata=work[["signed_contribution", "method"]],
            hovertemplate="%{y}<br>重要度=%{x:.5f}<br>方向貢獻=%{customdata[0]:.5f}<br>%{customdata[1]}<extra></extra>",
        )
    )
    fig.update_layout(height=520, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis_title="對第 N 天漲跌分類的重要度")
    return fig


def _build_y_heatmap(heatmap: pd.DataFrame, ticker: str) -> go.Figure:
    work = heatmap[heatmap["ticker"] == ticker].copy().tail(90)
    if work.empty:
        return go.Figure()
    work["direction_label"] = work["direction"].map({1: "漲", 0: "跌/未達門檻"})
    fig = go.Figure(
        go.Heatmap(
            z=[work["forward_return"].to_numpy() * 100],
            x=work["target_date"],
            y=["第N天結果"],
            colorscale="RdYlGn",
            zmid=0,
            text=[work["return_bucket"].to_numpy()],
            hovertemplate="目標日=%{x}<br>forward return=%{z:.2f}%<br>%{text}<extra></extra>",
        )
    )
    fig.update_layout(height=180, margin={"l": 10, "r": 10, "t": 20, "b": 10}, coloraxis_colorbar_title="報酬%")
    return fig


def _humanize_factor_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    out = summary.copy()
    for col in ["baseline_up_rate", "accuracy", "auc", "target_threshold"]:
        if col in out.columns:
            out[col] = out[col] * 100
    return translate_dataframe_columns(
        out.rename(
            columns={
                "ticker": "代號",
                "samples": "樣本數",
                "train_samples": "訓練樣本",
                "test_samples": "測試樣本",
                "baseline_up_rate": "歷史上漲率%",
                "accuracy": "測試準確率%",
                "auc": "AUC%",
                "model": "模型",
                "method": "歸因方法",
                "window": "輸入天數",
                "horizon": "預測天數",
                "target_threshold": "漲跌門檻%",
            }
        ),
        UI_LANG,
    )


def _humanize_factor_importance(importance: pd.DataFrame) -> pd.DataFrame:
    if importance.empty:
        return importance
    return translate_dataframe_columns(
        importance.rename(
            columns={
                "ticker": "代號",
                "horizon": "預測天數",
                "feature_label": "因子",
                "importance": "重要度",
                "signed_contribution": "方向貢獻",
                "direction": "方向",
                "method": "方法",
            }
        ),
        UI_LANG,
    )


portfolio_load = load_local_portfolio(".")
portfolio_default_tickers = portfolio_tickers(portfolio_load.holdings)
default_ticker_text = ", ".join(portfolio_default_tickers) if portfolio_default_tickers else "AAPL, MSFT, NVDA"

# Default values for cheap global summaries. Page-specific controls live inside their tabs.
factor_window = 7
factor_horizons = [1, 3, 5, 10]
factor_threshold_pct = 0.0
factor_model_label = "Gradient Boosting"
factor_model_type = "gradient_boosting"
backtest_lookback = 120
backtest_compare_enabled = False
backtest_horizons = [3, 5, 10]
backtest_exit_rules = ["time", "stop_loss", "trailing_stop"]
trailing_stop_pct = 0.05
backtest_only_buy = False
smart_tuning_horizons = [3, 5, 10]
smart_tuning_stop_widths_pct = [3, 5, 8]
show_volume = True

with st.sidebar:
    st.header("分析設定")
    st.caption("1 選資料 → 2 調參數 → 3 看決策摘要")

    source = st.segmented_control("資料來源", ["yfinance", "csv"], default="yfinance")
    ticker_text = st.text_area("股票代號", default_ticker_text, help="可用逗號或換行分隔，例如 AAPL, MSFT, NVDA。有 my_stocks.json / my_sotcks.json 時會自動帶入持倉代號。")
    if not portfolio_load.holdings.empty:
        st.success(f"已載入持倉檔：{portfolio_load.source_path}")

    c1, c2 = st.columns(2)
    with c1:
        period = st.selectbox("歷史區間", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    with c2:
        interval = st.selectbox("K線週期", ["1d", "1wk", "1mo"], index=0)

    horizon = st.slider("決策天數", 1, 30, 5, help="用今天以前的資料，估計未來幾天後的價格方向。以前文件常寫 horizon，這裡用『決策天數』表示。")
    with st.expander("個人交易偏好", expanded=False):
        st.caption("這些不是券商下單設定，只是讓回測/策略工作台更貼近你的人工掛單習慣。")
        prefer_no_day_trade = st.checkbox("不做當沖", value=True, help="策略視覺化與回測使用隔夜/多日持有假設；同一天不會同時開倉又平倉。")
        max_orders_per_stock_per_day = st.number_input("每天每股最多掛單次數", min_value=1, max_value=5, value=1, step=1, help="目前日 K 回測會以每股每日最多一次新訊號為原則；未來接 15m/1h 時可用來限制 intraday 過度交易。")
        default_order_lots = st.number_input("預設每次掛單股數/張數", min_value=0.0, max_value=1000.0, value=1.0, step=1.0, help="只作為報表提醒，不會自動下單；美股可把 1 視為 1 股，台股可自行視為 1 張。")
        preferred_holding_days = st.select_slider("習慣持有幾天", options=[1, 5, 10, 15, 30], value=5, help="作為隔日策略工作台的預設持有天數；仍可在該頁調整。")
        st.caption(f"目前偏好：每天每股最多 {int(max_orders_per_stock_per_day)} 次、每次約 {default_order_lots:g} 股/張、{'不做當沖' if prefer_no_day_trade else '允許日內處理'}。")
    uploaded = st.file_uploader("上傳 CSV", type=["csv"], help="支援 date/ticker/open/high/low/close/volume 或中文欄位。")
    st.caption("行情資料已快取 1 小時，並寫入 docker_runtime/market_cache；Docker 重啟後仍會優先讀磁碟快取。需要最新行情時再按下方按鈕。")
    refresh = st.button("重新抓資料 / 更新分析", type="primary", use_container_width=True)
    if refresh:
        _clear_cached_market_data()
        st.session_state.shap_attribution = pd.DataFrame()
        st.session_state.shap_signature = None
        st.session_state.factor_research_report = None
        st.session_state.factor_signature = None
        st.session_state.smart_tuning_result = pd.DataFrame()
        st.session_state.smart_tuning_signature = None
        st.toast("已清除行情與分析快取，正在重新抓資料。")

st.title("📈 AI Stock 決策儀表板")
st.caption("先看決策，再看原因：價格趨勢、技術指標、股票相關性與可解釋的數學預估。此工具只做研究輔助，不自動下單。")

prices = pd.DataFrame()
tickers = _split_tickers(ticker_text)
try:
    if source == "csv" and uploaded is not None:
        prices = normalize_ohlcv(pd.read_csv(uploaded))
    elif source == "csv" and uploaded is None:
        st.info("請在左側上傳 CSV，或把資料來源切回 yfinance。")
        st.stop()
    elif tickers:
        with st.spinner("正在抓取行情並計算指標…"):
            prices = _load_yf(tickers, period, interval)
except Exception as exc:
    st.error(f"資料載入失敗：{exc}")
    st.stop()

if prices.empty:
    st.warning("目前沒有價格資料。請輸入可由 yfinance 查詢的代號，或上傳 CSV。")
    st.stop()

prices = prices.sort_values(["ticker", "date"]).reset_index(drop=True)
with st.spinner("正在計算決策、回測與可視化資料…"):
    snapshot = _cached_snapshot(prices)
    correlations = _cached_correlations(prices)
    report = _cached_decision_report(prices, horizon)
    backtest = _cached_backtest(
        prices,
        horizon=horizon,
        lookback=backtest_lookback,
        only_buy_watch=backtest_only_buy,
        trailing_stop_pct=trailing_stop_pct,
    )
    scenario_comparison = (
        _cached_scenario_comparison(
            prices,
            horizons=tuple(backtest_horizons or [horizon]),
            exit_rules=tuple(backtest_exit_rules or ["stop_loss"]),
            lookback=backtest_lookback,
            only_buy_watch=backtest_only_buy,
            trailing_stop_pct=trailing_stop_pct,
        )
        if backtest_compare_enabled
        else pd.DataFrame()
    )
visible_tickers = sorted(prices["ticker"].unique())
portfolio_order_plan = build_portfolio_order_plan(portfolio_load.holdings, report)
portfolio_summary = summarize_portfolio(portfolio_load.holdings, portfolio_order_plan)
next_day_order_plan = _cached_next_day_order_plan(prices, report, portfolio_load.holdings, lookback=20)
watchlist = build_watchlist_sparklines(prices, report)
market_heatmap = build_market_heatmap_table(prices, report)
_render_watchlist(watchlist)
shap_signature = (
    tuple(visible_tickers),
    str(prices["date"].min()),
    str(prices["date"].max()),
    int(len(prices)),
    int(horizon),
)
factor_signature = (
    tuple(visible_tickers),
    str(prices["date"].min()),
    str(prices["date"].max()),
    int(len(prices)),
    int(factor_window),
    tuple(int(h) for h in factor_horizons),
    float(factor_threshold_pct),
    str(factor_model_type),
)
smart_tuning_signature = (
    tuple(visible_tickers),
    str(prices["date"].min()),
    str(prices["date"].max()),
    int(len(prices)),
    tuple(int(h) for h in smart_tuning_horizons or [horizon]),
    tuple(backtest_exit_rules or ["time", "stop_loss", "trailing_stop"]),
    tuple(float(v) / 100 for v in smart_tuning_stop_widths_pct or [5]),
    int(backtest_lookback),
    bool(backtest_only_buy),
)
if "shap_attribution" not in st.session_state:
    st.session_state.shap_attribution = pd.DataFrame()
if "shap_signature" not in st.session_state:
    st.session_state.shap_signature = None
if "factor_research_report" not in st.session_state:
    st.session_state.factor_research_report = None
if "factor_signature" not in st.session_state:
    st.session_state.factor_signature = None
if "smart_tuning_result" not in st.session_state:
    st.session_state.smart_tuning_result = pd.DataFrame()
if "smart_tuning_signature" not in st.session_state:
    st.session_state.smart_tuning_signature = None

if report.empty:
    st.warning("資料量不足以產生決策報表；請拉長歷史區間或改用日 K。")
else:
    best = report.iloc[0]
    action = str(best["action"])
    st.subheader("今天先看這三件事")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("優先觀察", str(best["ticker"]), ACTION_BADGE.get(action, action))
    m2.metric("關係調整報酬", _fmt_pct(best.get("relationship_adjusted_return_pct", best["expected_return_pct"])), f"{best['model']}")
    m3.metric("買進參考", _fmt_price(best["suggested_buy_price"]))
    m4.metric("停損參考", _fmt_price(best["stop_loss_price"]))
    m5.metric("賣出參考", _fmt_price(best["suggested_sell_price"]))
    m6.metric("Kelly 倉位", f"{best['kelly_fraction'] * 100:.1f}%")
    st.caption(ACTION_HELP.get(action, ""))
    _render_portfolio_summary(portfolio_summary)
    _render_opportunity_radar(build_opportunity_radar(report, backtest.summary, top_n=6))
    st.subheader("市場熱力圖")
    st.caption("用格子大小呈現成交量 × 價格活躍度，用顏色呈現近 5 日報酬；適合快速找出目前最熱或最弱的觀察標的。")
    st.plotly_chart(_build_market_heatmap_chart(market_heatmap), use_container_width=True)
    dashboard_strategy_result = st.session_state.get("order_strategy_workbench_result")
    dashboard_strategy_orders = pd.DataFrame()
    if isinstance(dashboard_strategy_result, dict):
        dashboard_strategy_orders = dashboard_strategy_result.get("order_recommendations", pd.DataFrame())
    dashboard_order_plan = integrate_strategy_recommendations_into_order_plan(next_day_order_plan, dashboard_strategy_orders)
    _render_tradingview_action_board(dashboard_order_plan)

    with st.expander("怎麼讀這份報表？", expanded=False):
        st.write(
            "參考買進價偏向保守掛價；參考賣出價取近期高點、波動門檻與預估價的較高者；停損價用近期波動估算；"
            "Kelly 是半 Kelly 且有上限，適合當倉位參考，不是必然下單比例。"
        )

tab_dashboard, tab_orders, tab_charts, tab_strategy_lab, tab_research = st.tabs(["今日決策", "交易計畫", "圖表分析", "策略驗證", "研究中心"])
tab_decision = tab_dashboard
tab_portfolio = tab_orders
tab_next_day_order = tab_orders
tab_chart = tab_charts
tab_trade_vision = tab_charts
tab_order_strategy = tab_strategy_lab
with tab_dashboard:
    st.info("本頁回答：今天應優先看哪幾檔？先看優先標的、方向、風險價位；若要執行，下一步到『交易計畫』。")
with tab_orders:
    st.info("本頁回答：明天可以怎麼掛單？先處理紅色賣出/保護，再看綠色買進/加碼；下單前到『圖表分析』確認價格位置。")
with tab_charts:
    st.info("本頁回答：價格位置適合進場嗎？像 TradingView 一樣先選股票，看 K 線、支撐壓力、SMC、Entry/Stop/Target 是否合理。")
with tab_strategy_lab:
    st.info("本頁回答：這個策略近期對這檔股票有效嗎？先單檔驗證勝率、Profit Factor、最大回撤，再決定是否信任掛單訊號。")
with tab_research:
    st.info("本頁回答：模型為什麼這樣判斷？研究因子、歸因、相關性與訓練資料；一般下單不需要每天使用。")
    research_backtest_tab, research_factor_tab, research_attribution_tab, research_relation_tab, research_training_tab = st.tabs(["回測 / Smart Tuning", "因子研究", "SHAP 歸因", "股票關係", "訓練資料"])
tab_backtest = research_backtest_tab
tab_factor = research_factor_tab
tab_attribution = research_attribution_tab
tab_relation = research_relation_tab
tab_raw = research_training_tab

with tab_decision:
    st.subheader("買 / 賣 / 停損決策報表")
    _render_strategy_health(build_strategy_health_cards(backtest.summary, report))
    human_report = _humanize_report(report)
    if human_report.empty:
        st.info("目前沒有足夠資料產生報表。")
    else:
        st.dataframe(
            human_report,
            use_container_width=True,
            hide_index=True,
            column_config={
                "模型預估報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                "關係調整後報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                "Kelly 建議倉位": st.column_config.NumberColumn(format="%.1f%%"),
                "決策原因": st.column_config.TextColumn(width="large"),
                "Kelly 原因": st.column_config.TextColumn(width="large"),
                "最新收盤": st.column_config.NumberColumn(format="%.2f"),
                "預估價": st.column_config.NumberColumn(format="%.2f"),
                "參考買進價": st.column_config.NumberColumn(format="%.2f"),
                "參考賣出價": st.column_config.NumberColumn(format="%.2f"),
                "參考停損價": st.column_config.NumberColumn(format="%.2f"),
                "風險單位%": st.column_config.NumberColumn(format="%.2f%%"),
                "距60日高點%": st.column_config.NumberColumn(format="%.2f%%"),
                "60日最大回撤%": st.column_config.NumberColumn(format="%.2f%%"),
                "同/反向關係壓力%": st.column_config.NumberColumn(format="%.2f%%"),
                "RSI14": st.column_config.NumberColumn(format="%.1f"),
                "布林位置": st.column_config.NumberColumn(format="%.2f"),
                "MFI14": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        with st.expander("Kelly / 決策原因怎麼看？", expanded=False):
            st.write("為什麼 Kelly 可能是 0.0%？當模型預估報酬相對於風險單位太小，或沒有明顯勝率優勢時，半 Kelly 會保守降到 0，代表暫時不建議用這個訊號配置倉位。")
            st.write("為什麼常看到『等待確認』？當預估報酬仍在買進 / 賣出門檻內，代表模型優勢還沒有大過近期波動與回撤風險，系統會先提示等待確認。")
            st.write("表格中的『決策原因』與『Kelly 原因』會逐檔列出目前預估報酬、風險門檻與倉位為 0 的主要理由。")
        st.download_button(
            "下載決策報表 CSV",
            human_report.to_csv(index=False).encode("utf-8-sig"),
            file_name="ai_stock_decision_report.csv",
            mime="text/csv",
        )

with tab_portfolio:
    st.subheader("持倉下單計畫")
    st.caption("讀取本機 my_stocks.json / my_sotcks.json，將帳戶持倉與模型決策合併，產生停損、停利、加碼限價與減碼檢查清單。本系統不會自動下單。")
    if portfolio_load.holdings.empty:
        st.info("目前沒有讀到 my_stocks.json。若要啟用持倉分析，請把帳戶持倉 JSON 放在專案根目錄；此檔案已加入 .gitignore，不應上傳 GitHub。")
    elif portfolio_order_plan.empty:
        st.warning("已讀到持倉檔，但目前行情或決策資料不足，尚無法產生下單計畫。")
    else:
        if portfolio_load.account_label:
            st.caption(_("帳戶：{account}", account=portfolio_load.account_label))
        _render_portfolio_summary(portfolio_summary)
        st.warning("這裡是下單前的研究輔助清單，不是自動交易訊號；實際下單前請自行確認券商報價、流動性、稅費與個人風險承受度。")
        plan_display = _humanize_portfolio_order_plan(portfolio_order_plan)
        st.dataframe(
            plan_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                t("持有數量", UI_LANG): st.column_config.NumberColumn(format="%.4f"),
                t("持倉市值", UI_LANG): st.column_config.NumberColumn(format="%.2f"),
                t("持倉權重%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                t("帳戶現價", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("行情收盤", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("帳戶/行情差異%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                t("成本價", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("未實現損益", UI_LANG): st.column_config.NumberColumn(format="%.2f"),
                t("未實現損益%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                t("今日損益", UI_LANG): st.column_config.NumberColumn(format="%.2f"),
                t("Kelly%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                t("加碼限價參考", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("停損單參考", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("停利單參考", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("關係調整後報酬%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                t("操作說明", UI_LANG): st.column_config.TextColumn(width="large"),
            },
        )
        with st.expander("怎麼把這張表轉成券商操作？", expanded=False):
            st.write("停損單參考：如果你決定繼續持有，通常先把每檔股票的停損價輸入券商條件單或提醒。不要因為虧損就把停損往下移。")
            st.write("停利單參考：若現價接近停利價，可以考慮分批賣出或設定限價賣單；若模型仍等待確認，停利優先於追高加碼。")
            st.write("加碼限價參考：只有在模型偏多、Kelly 有倉位且價格接近買進參考時，才把它當加碼限價；否則先等待。")
            st.write("減碼 / 出清檢查：代表模型風險報酬偏弱；已有持股時應優先檢查是否降低曝險，而不是新增買單。")
        st.download_button(
            "下載持倉下單計畫 CSV",
            plan_display.to_csv(index=False).encode("utf-8-sig"),
            file_name="ai_stock_portfolio_order_plan.csv",
            mime="text/csv",
        )

with tab_next_day_order:
    st.subheader("隔日掛單計畫")
    st.caption("把策略級買進 / 停利 / 停損價，轉換成更接近隔日可成交波動區間的掛單研究表。這是研究輔助，不自動下單。")
    if next_day_order_plan.empty:
        st.info("目前沒有持倉資料或可規劃標的。請確認 runtime/portfolio/my_stocks.json 或 my_sotcks.json 是否存在。")
    else:
        enable_intraday_smc = st.checkbox(
            "啟用 15m / 1h / 1d SMC 多週期信心分數（首次載入較慢）",
            value=False,
            help="關閉時使用 1d SMC 快速規劃；開啟後會額外抓 15m / 1h yfinance K 線並整合 smartmoneyconcepts 訊號。",
        )
        smc_order_tickers = tuple(next_day_order_plan["ticker"].dropna().astype(str).str.upper().unique())
        if enable_intraday_smc:
            with st.spinner("正在整合 15m / 1h / 1d SMC 多週期訊號…"):
                smc_mtf_signals = _cached_smc_multitimeframe_signals(smc_order_tickers, prices, enable_intraday=True)
        else:
            smc_mtf_signals = _cached_smc_multitimeframe_signals(smc_order_tickers, prices, enable_intraday=False)
        next_day_order_plan = augment_order_plan_with_smc(next_day_order_plan, smc_mtf_signals)
        strategy_result_for_orders = st.session_state.get("order_strategy_workbench_result")
        strategy_orders_for_plan = pd.DataFrame()
        if isinstance(strategy_result_for_orders, dict):
            strategy_orders_for_plan = strategy_result_for_orders.get("order_recommendations", pd.DataFrame())
        if not strategy_orders_for_plan.empty:
            next_day_order_plan = integrate_strategy_recommendations_into_order_plan(next_day_order_plan, strategy_orders_for_plan)
            st.success("已整合上次『隔日策略工作台』回測結果：最終買賣區間會優先採用該股票歷史適配度最高的策略。")
        else:
            next_day_order_plan = integrate_strategy_recommendations_into_order_plan(next_day_order_plan, None)
        if enable_intraday_smc:
            st.caption("SMC 信心分數目前整合 15m / 1h / 1d；資料來源為 yfinance OHLCV + smartmoneyconcepts/fallback SMC engine。")
        else:
            st.caption("目前使用 1d SMC 快速模式；需要更細的 15m / 1h 掛單方向確認時，可勾選上方多週期 SMC。")
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("可規劃標的", f"{len(next_day_order_plan)}")
        n2.metric("高/中買進成交機率", f"{int(next_day_order_plan['buy_touch_probability'].isin(['HIGH', 'MEDIUM']).sum())}")
        n3.metric("高/中賣出成交機率", f"{int(next_day_order_plan['sell_touch_probability'].isin(['HIGH', 'MEDIUM']).sum())}")
        n4.metric("高優先處理", f"{int((next_day_order_plan.get('priority_score', pd.Series(dtype=float)) >= 70).sum())}")
        st.warning("此頁輸出的是隔日限價 / 停損研究計畫，不會連接券商，也不會自動下單。實際掛單前請確認即時報價、盤前盤後價差、流動性與個人風險。")
        st.markdown("#### 優先處理熱力表")
        st.caption("綠色代表買進 / 加碼急迫度，紅色代表賣出 / 減碼 / 保護急迫度；顏色越深，越應該優先打開該標的技術圖確認掛單價。若已跑過隔日策略工作台，買賣區會改用最終策略推薦區間。")
        _render_next_day_order_heatmap(next_day_order_plan)
        order_display = _humanize_next_day_order_plan(next_day_order_plan)
        dataframe_kwargs = {
            "data": order_display,
            "use_container_width": True,
            "hide_index": True,
            "column_config": {
                t("持有數量", UI_LANG): st.column_config.NumberColumn(format="%.4f"),
                t("目前價格", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("戰術停損", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("硬停損", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("策略買進價", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("策略停利價", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("最終策略適配分數", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                t("最終停損", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("最終停利", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                t("優先處理分數", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                t("買進急迫度", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                t("賣出急迫度", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                t("SMC信心分數", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                t("SMC多週期摘要", UI_LANG): st.column_config.TextColumn(width="medium"),
                t("20日中位日內波動%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                t("20日80分位日內波動%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                t("原因", UI_LANG): st.column_config.TextColumn(width="large"),
            },
        }
        try:
            selection_event = st.dataframe(
                **dataframe_kwargs,
                key="next_day_order_table",
                on_select="rerun",
                selection_mode="single-row",
            )
        except TypeError:
            selection_event = None
            st.dataframe(**dataframe_kwargs)

        selected_row_index = None
        if selection_event is not None:
            selected_rows = getattr(getattr(selection_event, "selection", None), "rows", []) or []
            if selected_rows:
                selected_row_index = int(selected_rows[0])
        if selected_row_index is not None and 0 <= selected_row_index < len(next_day_order_plan):
            st.session_state.selected_order_ticker = str(next_day_order_plan.iloc[selected_row_index]["ticker"])
        selectable_order_tickers = list(next_day_order_plan["ticker"].astype(str))
        default_selected_order = st.session_state.get("selected_order_ticker", selectable_order_tickers[0])
        default_order_index = selectable_order_tickers.index(default_selected_order) if default_selected_order in selectable_order_tickers else 0
        selected_order_ticker = st.selectbox(
            "選擇下方技術圖股票",
            selectable_order_tickers,
            index=default_order_index,
            key="selected_order_ticker_selectbox",
            help="支援新版 Streamlit 點選上方表格 row 自動切換；若瀏覽器/版本不支援，可用這個選單切換。",
        )
        st.session_state.selected_order_ticker = selected_order_ticker

        st.markdown("#### 隔日掛單技術圖")
        selected_order_row = next_day_order_plan[next_day_order_plan["ticker"].astype(str) == selected_order_ticker].iloc[0].copy()
        for src, dst in [
            ("final_buy_low", "next_day_buy_low"),
            ("final_buy_high", "next_day_buy_high"),
            ("final_sell_low", "next_day_sell_low"),
            ("final_sell_high", "next_day_sell_high"),
            ("final_stop_loss", "tactical_stop_price"),
            ("final_take_profit", "strategy_take_profit_price"),
        ]:
            if src in selected_order_row.index and pd.notna(selected_order_row.get(src)):
                selected_order_row[dst] = selected_order_row.get(src)
        selected_order_prices = prices[prices["ticker"].astype(str) == selected_order_ticker].sort_values("date").tail(160).copy()
        if selected_order_prices.empty or len(selected_order_prices) < 35:
            st.info("資料不足以產生隔日掛單技術圖，請拉長歷史區間或改用日 K。")
        else:
            tech_summary = _cached_order_technical_context(selected_order_prices, selected_order_row)
            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("RSI14", f"{tech_summary.get('rsi_14', 0):.1f}")
            s2.metric("MACD Hist", f"{tech_summary.get('macd_hist', 0):+.3f}")
            s3.metric("布林位置", f"{tech_summary.get('bb_position_20', 0):.2f}")
            s4.metric("量能比", f"{tech_summary.get('volume_ratio_20d', 1):.2f}x")
            s5.metric("UKF 動能", f"{tech_summary.get('ukf_momentum_score', 50):.1f}", str(tech_summary.get("ukf_trend_state", "NEUTRAL")))
            st.caption("圖表使用 x unified hover 與 spike line，滑鼠移到任一天可同時查看 K 線、成交量、RSI、MACD 與 UKF Momentum / UKF 動能；SMC overlay 會優先使用 smartmoneyconcepts 套件計算 FVG、Order Block、Liquidity、Swing、BOS/CHoCH，若套件或資料不足則自動退回內建規則。")
            decision_match = report[report["ticker"].astype(str) == selected_order_ticker] if not report.empty else pd.DataFrame()
            selected_decision_row = decision_match.iloc[0] if not decision_match.empty else None
            fig = build_swing_order_technical_chart(selected_order_prices, selected_order_ticker, selected_order_row, selected_decision_row, lookback=160, show_volume=True)
            st.plotly_chart(fig, use_container_width=True)
            _render_indicator_glossary()
            with st.expander("UKF 動能怎麼看？", expanded=False):
                st.write("UKF 動能是用價格報酬、RSI、MACD histogram、布林位置與量能比形成多指標動能觀測，再用狀態空間濾波平滑雜訊。它不是深度學習預測，也不代表自動下單；分數高於 58 偏多，低於 42 偏弱，中間區間代表雜訊較多。")
                st.write("若隔日買進區靠近布林下緣、RSI 回到 40-55、MACD 柱體收斂且 UKF 動能不再惡化，通常比直接追價更適合 swing trading。若價格接近賣出區但 RSI 過熱、MACD 柱體縮短，分批停利/反彈減碼的理由會更充分。")
        with st.expander("如何使用隔日掛單計畫？", expanded=True):
            st.write("隔日買進區：用最近 20 日日內波動估算，通常比策略級買進價更靠近現價，目標是提高隔日限價單有機會成交的程度。")
            st.write("隔日賣出區：適合已有持倉時做分批停利觀察；策略停利價仍可作為較長週期目標。")
            st.write("戰術停損：偏短線的隔日風險線；硬停損是策略失效線。戰術停損較容易觸發，硬停損較保守。")
            st.write("成交機率：以價位距離現價相對於最近 20 日日內波動分類；高/中代表隔日較可能碰到，低且偏策略價代表可能需要等待多日或深回檔。")
        st.download_button(
            "下載隔日掛單計畫 CSV",
            order_display.to_csv(index=False).encode("utf-8-sig"),
            file_name="ai_stock_next_day_order_plan.csv",
            mime="text/csv",
        )

with tab_order_strategy:
    st.subheader("隔日策略工作台")
    st.caption("這裡不再只依賴 Kelly 0/非 0，而是先設定『要驗證哪些股票、預計持有幾天、可承受多少停損、要測哪些策略、用多久歷史驗證』，再回測哪種策略比較符合該股票股性，最後回推隔日掛單區間與買賣迫切度。")
    with st.expander("頁籤使用目的", expanded=False):
        st.write("用途：比較同一檔股票在不同策略下的歷史表現，確認哪一種策略比較符合最近股性，再把最佳策略回寫到隔日掛單計畫。")
        st.write("方法：先選股票與預計持有天數，再選可承受停損幅度、歷史驗證期間與策略；按下回測後，先看策略適配分數，再看買賣點圖、每筆交易垂直虛線、獲利/虧損區間線、權益曲線與回撤曲線。")
        st.write("個人交易偏好：左側『個人交易偏好』目前會影響此頁的預設持有天數，並提醒回測採用每天每股最多一次、避免同日開平倉的人工掛單假設。")
    with st.expander("這些設定怎麼看？", expanded=False):
        st.write("預計持有天數：這次掛單後，假設最多觀察幾天才出場；1 天偏隔日短打，5～10 天偏 swing trading，15～30 天偏波段。")
        st.write("風險耐受度：這次策略回測與掛單區間使用的停損寬度上限；不是你的全部帳戶風險。")
        st.write("用多久歷史驗證：用最近多久資料檢查這個策略是否適合該股票；太短樣本少，太長可能混入不同市場環境。")
        st.write("策略選擇：布林、SMC、UKF、KD/MACD、SHAP proxy 是不同判斷方法；建議先單檔 + 少數策略測清楚，再全選。")
    if next_day_order_plan.empty:
        st.info("目前沒有隔日掛單計畫資料；請先確認持倉檔與行情資料。")
    else:
        if "order_strategy_workbench_result" not in st.session_state:
            st.session_state.order_strategy_workbench_result = None
        if "order_strategy_workbench_signature" not in st.session_state:
            st.session_state.order_strategy_workbench_signature = None

        available_order_tickers = list(next_day_order_plan["ticker"].dropna().astype(str).str.upper().unique())
        ctl1, ctl2, ctl3 = st.columns([0.32, 0.34, 0.34])
        with ctl1:
            strategy_scope = st.radio("要驗證哪些股票", ["全選", "自選"], horizontal=True, index=0)
            if strategy_scope == "全選":
                strategy_tickers = available_order_tickers
            else:
                strategy_tickers = st.multiselect("選擇要驗證的股票", available_order_tickers, default=available_order_tickers[:1])
        with ctl2:
            strategy_holding_days = st.select_slider("預計持有天數", options=[1, 5, 10, 15, 30], value=int(preferred_holding_days), help="這次策略回測與掛單區間都用同一個持有天數作為基準，避免 1 天短打和 30 天波段訊號混在一起。左側『習慣持有幾天』會作為預設值。")
            strategy_risk_tolerance_pct = st.slider("可承受停損幅度%", 1.0, 30.0, 10.0, step=0.5, help="用於策略回測停損與掛單風險寬度；預設 10%。")
        with ctl3:
            strategy_backtest_range = st.selectbox("用多久歷史驗證", ["1周", "2周", "1個月", "3個月", "半年", "1年"], index=3)
            selected_strategy_labels = st.multiselect(
                "選擇策略",
                list(ORDER_STRATEGIES.values()),
                default=list(ORDER_STRATEGIES.values()),
                help="策略屬於離散規則，使用勾選比拉 bar 更清楚；風險耐受度這種連續值才用 slider。",
            )
        label_to_strategy = {label: key for key, label in ORDER_STRATEGIES.items()}
        selected_strategy_keys = [label_to_strategy[label] for label in selected_strategy_labels]
        strategy_signature = (
            tuple(strategy_tickers),
            tuple(selected_strategy_keys),
            int(strategy_holding_days),
            float(strategy_risk_tolerance_pct),
            str(strategy_backtest_range),
            str(prices["date"].min()),
            str(prices["date"].max()),
            int(len(prices)),
        )
        run_order_strategy_workbench = st.button("啟動隔日策略回測", type="primary", use_container_width=True)
        if not strategy_tickers:
            st.warning("請至少選一檔股票，或改成全選。")
        elif not selected_strategy_keys:
            st.warning("請至少勾選一個策略欄位。")
        elif run_order_strategy_workbench:
            with st.spinner("正在執行隔日策略工作台回測…"):
                st.session_state.order_strategy_workbench_result = build_order_strategy_workbench(
                    prices,
                    next_day_order_plan,
                    selected_tickers=strategy_tickers,
                    strategies=selected_strategy_keys,
                    holding_days=int(strategy_holding_days),
                    risk_tolerance_pct=float(strategy_risk_tolerance_pct),
                    backtest_range=strategy_backtest_range,
                )
                st.session_state.order_strategy_workbench_signature = strategy_signature
            st.rerun()
        result = st.session_state.order_strategy_workbench_result
        if result is None:
            st.info("請先選擇股票 / 預計持有天數 / 可承受停損幅度 / 策略 / 歷史驗證期間，然後按『啟動隔日策略回測』。建議先單檔測，再全選。")
        else:
            if st.session_state.order_strategy_workbench_signature != strategy_signature:
                st.warning("目前顯示的是上一次策略工作台結果；參數已改變，若要更新請再按一次『啟動隔日策略回測』。")
            summary = result.get("summary", pd.DataFrame())
            orders = result.get("order_recommendations", pd.DataFrame())
            if summary.empty:
                st.info("目前參數下沒有足夠交易樣本。請拉長回測期間、放寬策略或選其他股票。")
            else:
                st.markdown("#### 策略勝率 / 股性適配表")
                st.caption("勝率不是唯一依據；工作台同時看平均報酬、累積報酬、Profit Factor、最大回撤與停損命中率，產生策略適配分數。策略適配分數顏色：綠色代表策略適配較高，黃色代表中性待確認，紅色代表近期不適合；這不是 SHAP 正負相關，也不是單一因子的方向貢獻。")
                with st.expander("策略適配分數顏色怎麼看？", expanded=False):
                    st.write("綠色：回測勝率、報酬、Profit Factor、回撤與停損命中率綜合後較健康，代表這個策略近期比較符合該股票股性。")
                    st.write("黃色：有部分指標可用，但仍需看買賣點圖與回撤曲線確認。")
                    st.write("紅色：近期策略適配較弱，不代表一定看空，只代表這套規則在所選期間不穩。這不是 SHAP 正負相關；SHAP 方向請到因子研究/歸因頁看。")
                st.plotly_chart(_build_strategy_score_chart(summary), use_container_width=True)
                summary_display = _humanize_strategy_workbench_summary(summary)
                st.dataframe(
                    summary_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        t("交易次數", UI_LANG): st.column_config.NumberColumn(format="%d"),
                        t("勝率%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                        t("平均報酬%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                        t("累積報酬%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                        t("最大回撤%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                        t("停損命中率%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                        t("Profit Factor", UI_LANG): st.column_config.NumberColumn(format="%.2f"),
                        t("策略適配分數", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                    },
                )
            if not orders.empty:
                st.markdown("#### 最佳掛單區間")
                st.caption("策略工作台會用回測結果重新排序買賣迫切度。『買進 / 加碼』偏綠色掛買進區，『賣出 / 減碼 / 保護』偏紅色看賣出區，『等待確認』代表仍需等技術圖確認。")
                order_display = _humanize_strategy_order_recommendations(orders)
                st.dataframe(
                    order_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        t("買賣迫切度", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                        t("策略適配分數", UI_LANG): st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                        t("買進區低", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                        t("買進區高", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                        t("賣出區低", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                        t("賣出區高", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                        t("停損價", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                        t("停利參考", UI_LANG): st.column_config.NumberColumn(format="%.3f"),
                        t("理由", UI_LANG): st.column_config.TextColumn(width="large"),
                    },
                )
                st.download_button(
                    "下載隔日策略工作台 CSV",
                    order_display.to_csv(index=False).encode("utf-8-sig"),
                    file_name="ai_stock_next_day_strategy_workbench.csv",
                    mime="text/csv",
                )

            st.markdown("#### 策略買賣點與績效曲線")
            st.caption("先選股票，再選要看的策略曲線；圖上會把策略買進/賣出點、每筆交易垂直虛線、獲利/虧損區間線、掛單區、SMC 特徵、權益曲線與回撤放在同一張圖，方便比較哪種策略更符合這檔股票的股性。")
            viz_tickers = sorted(summary["ticker"].dropna().astype(str).str.upper().unique()) if not summary.empty and "ticker" in summary.columns else strategy_tickers
            if not viz_tickers:
                st.info("目前沒有可視化的策略結果。")
            else:
                viz_col1, viz_col2, viz_col3 = st.columns([0.25, 0.45, 0.30])
                with viz_col1:
                    strategy_viz_ticker = st.selectbox("策略視覺化股票", viz_tickers, key="strategy_viz_ticker")
                strategy_labels_for_viz = [label for key, label in ORDER_STRATEGIES.items() if key in selected_strategy_keys]
                with viz_col2:
                    strategy_viz_labels = st.multiselect(
                        "策略視覺化策略",
                        ["綜合策略"] + strategy_labels_for_viz,
                        default=["綜合策略"] + strategy_labels_for_viz[:2],
                        help="可單看某一種策略，也可看綜合策略。買賣點會疊在價格圖上，下方顯示 equity 與 drawdown。",
                    )
                with viz_col3:
                    show_strategy_smc = st.checkbox("顯示 SMC 特徵", value=True, help="開啟後在價格圖中顯示 SMC Order Block / Liquidity 等輔助結構；圖例說明可在隔日掛單計畫的 glossary 對照。")
                label_to_strategy_with_composite = {"綜合策略": "COMPOSITE", **{label: key for key, label in ORDER_STRATEGIES.items()}}
                strategy_viz_keys = [label_to_strategy_with_composite[label] for label in strategy_viz_labels if label in label_to_strategy_with_composite]
                payload = build_strategy_visualization_payload(
                    prices,
                    result.get("trades", pd.DataFrame()),
                    ticker=strategy_viz_ticker,
                    strategies=strategy_viz_keys or ["COMPOSITE"],
                    order_recommendations=orders,
                    show_smc=show_strategy_smc,
                )
                st.plotly_chart(payload["figure"], use_container_width=True)
                metrics_df = payload.get("strategy_metrics", pd.DataFrame())
                if not metrics_df.empty:
                    st.markdown("##### 策略績效摘要")
                    metrics_display = metrics_df.copy()
                    metrics_display["win_rate"] = metrics_display["win_rate"] * 100
                    st.dataframe(
                        metrics_display.rename(
                            columns={
                                "strategy": "策略",
                                "trade_count": "交易次數",
                                "win_rate": "勝率%",
                                "cumulative_return_pct": "累積報酬%",
                                "max_drawdown_pct": "最大回撤%",
                                "profit_factor": "Profit Factor",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "交易次數": st.column_config.NumberColumn(format="%d"),
                            "勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                            "累積報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                            "最大回撤%": st.column_config.NumberColumn(format="%.2f%%"),
                            "Profit Factor": st.column_config.NumberColumn(format="%.2f"),
                        },
                    )
        with st.expander("為什麼這裡不再只看 Kelly？", expanded=False):
            st.write("Kelly 容易在預估優勢小於波動風險時變成 0.0%，適合作為倉位保守上限，但不適合單獨決定隔日掛單。策略工作台改用可勾選策略 + 預計持有天數 + 可承受停損幅度 + 近端回測，先確認這檔股票近期股性比較吃哪種策略，再回推買賣區間。")
            st.write("策略選擇用勾選，因為布林、SMC、UKF、KD/MACD、SHAP 因子代理是離散方法；可承受停損幅度用 slider，因為它是連續參數。")

with tab_chart:
    left, right = st.columns([1, 2])
    with left:
        selected = st.selectbox("選擇圖表代號", visible_tickers)
        chart_show_volume = st.toggle("K 線圖顯示成交量", value=True, key="price_chart_show_volume")
        selected_report = report[report["ticker"] == selected]
        if not selected_report.empty:
            row = selected_report.iloc[0]
            st.metric("最新收盤", _fmt_price(row["last_close"]), _fmt_pct(row["expected_return_pct"]))
            st.write(_("決策：{action}", action=ACTION_BADGE.get(str(row["action"]), row["action"])))
            st.write(_("參考買進：{price}", price=_fmt_price(row["suggested_buy_price"])))
            st.write(_("參考賣出：{price}", price=_fmt_price(row["suggested_sell_price"])))
            st.write(_("參考停損：{price}", price=_fmt_price(row["stop_loss_price"])))
    with right:
        one = prices[prices["ticker"] == selected].sort_values("date")
        decision_row = selected_report.iloc[0] if not selected_report.empty else None
        trades_for_chart = backtest.trades if not backtest.trades.empty else None
        fig = build_decision_price_chart(one, selected, chart_show_volume, decision_row=decision_row, backtest_trades=trades_for_chart)
        for trace in fig.data:
            if getattr(trace, "name", None):
                trace.name = _(str(trace.name))
        st.plotly_chart(fig, use_container_width=True)

with tab_trade_vision:
    st.subheader("智能交易視覺中心")
    st.caption("整合 K 線、市場結構、支撐壓力、交易計畫、MTF 矩陣與綜合分數。此頁是研究輔助，不自動下單。")
    if not visible_tickers:
        st.info("目前沒有可分析的股票代號。")
    else:
        left_col, mid_col, right_col = st.columns([0.18, 0.57, 0.25])
        with left_col:
            trade_ticker = st.selectbox("選擇 ticker", visible_tickers, key="trade_vision_ticker")
            tv_show_volume = st.toggle("顯示成交量", value=True, key="tv_show_volume")
            tv_show_structure = st.toggle("顯示 BOS / ChoCH", value=True, key="tv_show_structure")
            tv_show_zones = st.toggle("顯示支撐壓力區", value=True, key="tv_show_zones")
            tv_show_plan = st.toggle("顯示 Entry / SL / TP", value=True, key="tv_show_plan")
            tv_swing_window = st.slider("swing_window", 2, 10, 3, key="tv_swing_window")
            tv_min_break_pct = st.slider("min_break_pct", 0.1, 2.0, 0.3, step=0.1, key="tv_min_break_pct") / 100
            lookback_label = st.selectbox("chart lookback bars", ["60", "120", "240", "all"], index=1, key="tv_lookback")
        one_full = prices[prices["ticker"] == trade_ticker].sort_values("date").copy()
        if lookback_label != "all":
            one = one_full.tail(int(lookback_label)).copy()
        else:
            one = one_full.copy()
        decision_match = report[report["ticker"] == trade_ticker] if not report.empty else pd.DataFrame()
        decision_row = decision_match.iloc[0] if not decision_match.empty else None
        snapshot_match = snapshot[snapshot["ticker"] == trade_ticker] if not snapshot.empty else pd.DataFrame()
        snapshot_row = snapshot_match.iloc[0] if not snapshot_match.empty else pd.Series(dtype=object)
        if one.empty or len(one) < max(tv_swing_window * 2 + 3, 10):
            st.info("資料不足以建立 Trade Vision Center；請拉長歷史區間或改用日 K。")
        else:
            structure_result = _cached_trade_structure(one, tv_swing_window, tv_min_break_pct)
            zones = _cached_trade_zones(one, structure_result, lookback=min(len(one), 80))
            mtf_matrix = _cached_mtf_matrix(prices, trade_ticker)
            current_price = float(one["close"].iloc[-1])
            if decision_row is not None:
                trade_plan = build_trade_plan_from_decision(decision_row, current_price)
            else:
                trade_plan = build_trade_plan_from_decision(pd.Series({"ticker": trade_ticker, "action": "HOLD_WAIT", "suggested_buy_price": current_price, "stop_loss_price": current_price * 0.97, "suggested_sell_price": current_price * 1.03}), current_price)
            score = compute_trade_signal_score(snapshot_row, decision_row, structure_result["structure_events"], mtf_matrix)
            narrative = build_trade_narrative(trade_ticker, trade_plan, score, mtf_matrix, structure_result["structure_events"], zones)
            with mid_col:
                fig = build_trade_vision_chart(
                    one,
                    trade_ticker,
                    decision_row=decision_row,
                    structure=structure_result["structure_events"],
                    zones=zones,
                    signal_events=structure_result["swings"],
                    show_volume=tv_show_volume,
                    show_structure=tv_show_structure,
                    show_zones=tv_show_zones,
                    show_trade_plan=tv_show_plan,
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("#### MTF Matrix")
                st.dataframe(_humanize_mtf_matrix(mtf_matrix), use_container_width=True, hide_index=True)
                st.markdown("#### Signal Score breakdown")
                st.plotly_chart(_build_score_breakdown_chart(score), use_container_width=True)
            with right_col:
                st.markdown("#### Trade Plan")
                _render_trade_plan_card(trade_plan, score)
                st.markdown("#### AI Trade Narrative")
                for item in narrative:
                    st.write(f"• {item}")
                with st.expander("Market Structure", expanded=False):
                    st.dataframe(structure_result["structure_events"].tail(20), use_container_width=True, hide_index=True)
                with st.expander("Trade Zones", expanded=False):
                    st.dataframe(zones.tail(20), use_container_width=True, hide_index=True)

with tab_backtest:
    st.subheader("Walk-forward 回測")
    st.caption("每隔一段『預計持有天數』，只使用當下以前的資料重新產生決策報表，再用下一段行情驗證。這不是實盤成交模擬，先用來檢查策略方向、停損與回撤是否合理。")
    with st.expander("回測設定", expanded=True):
        cfg1, cfg2, cfg3 = st.columns(3)
        with cfg1:
            tab_backtest_lookback = st.slider("回測訓練視窗", 60, 260, 120, step=10, help="每次回測決策只看此前這段歷史資料。", key="tab_backtest_lookback")
            tab_backtest_only_buy = st.toggle("回測只吃偏多觀察訊號", value=False, help="關閉時會測試每個決策點的 long-only 結果；開啟時只測 BUY_WATCH。", key="tab_backtest_only_buy")
        with cfg2:
            tab_backtest_compare_enabled = st.toggle("啟用持有天數 / 出場規則比較", value=False, help="多策略比較會同時跑多組回測；需要比較時再開啟，避免頁面載入過慢。", key="tab_backtest_compare_enabled")
            tab_backtest_horizons = st.multiselect("比較持有天數", [3, 5, 10, 20, 30], default=[3, 5, 10], help="回測會比較每種持有天數的結果。", disabled=not tab_backtest_compare_enabled, key="tab_backtest_horizons")
        with cfg3:
            exit_rule_options_zh = {"時間出場": "time", "停損優先": "stop_loss", "移動停損": "trailing_stop"}
            exit_rule_display_options = translate_options(exit_rule_options_zh.keys(), UI_LANG)
            exit_rule_options = dict(zip(exit_rule_display_options, exit_rule_options_zh.values()))
            selected_exit_rule_labels = st.multiselect("比較出場規則", exit_rule_display_options, default=exit_rule_display_options, disabled=not tab_backtest_compare_enabled, key="tab_backtest_exit_rules")
            tab_backtest_exit_rules = [exit_rule_options[label] for label in selected_exit_rule_labels]
            tab_trailing_stop_pct = st.slider("移動停損幅度", 2.0, 15.0, 5.0, step=0.5, help="移動停損出場規則使用；例如 5% 代表從進場後高點回落 5% 出場。", disabled=not tab_backtest_compare_enabled, key="tab_trailing_stop_pct") / 100
        st.markdown("##### Smart Tuning Lite")
        smart1, smart2 = st.columns(2)
        with smart1:
            tab_smart_tuning_horizons = st.multiselect("Smart Tuning 持有天數", [3, 5, 10, 20], default=[3, 5, 10], help="按下 Smart Tuning 按鈕後才會掃描這些持有天數。", key="tab_smart_tuning_horizons")
        with smart2:
            tab_smart_tuning_stop_widths_pct = st.multiselect("Smart Tuning 風險寬度%", [3, 5, 8, 10], default=[3, 5, 8], help="掃描停損 / 移動停損風險寬度；數值越大越寬鬆。", key="tab_smart_tuning_stop_widths_pct")

    tab_backtest = _cached_backtest(
        prices,
        horizon=horizon,
        lookback=tab_backtest_lookback,
        only_buy_watch=tab_backtest_only_buy,
        trailing_stop_pct=tab_trailing_stop_pct,
    )
    tab_scenario_comparison = (
        _cached_scenario_comparison(
            prices,
            horizons=tuple(tab_backtest_horizons or [horizon]),
            exit_rules=tuple(tab_backtest_exit_rules or ["stop_loss"]),
            lookback=tab_backtest_lookback,
            only_buy_watch=tab_backtest_only_buy,
            trailing_stop_pct=tab_trailing_stop_pct,
        )
        if tab_backtest_compare_enabled
        else pd.DataFrame()
    )
    tab_smart_tuning_signature = (
        tuple(visible_tickers),
        str(prices["date"].min()),
        str(prices["date"].max()),
        int(len(prices)),
        tuple(int(h) for h in tab_smart_tuning_horizons or [horizon]),
        tuple(tab_backtest_exit_rules or ["time", "stop_loss", "trailing_stop"]),
        tuple(float(v) / 100 for v in tab_smart_tuning_stop_widths_pct or [5]),
        int(tab_backtest_lookback),
        bool(tab_backtest_only_buy),
    )
    if tab_backtest.summary.empty:
        st.info("資料量不足以回測；請把歷史區間拉到 1y / 2y，或降低回測訓練視窗。")
    else:
        bt_summary = _humanize_backtest_summary(tab_backtest.summary)
        top_bt = tab_backtest.summary.iloc[0]
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("最佳累積報酬", _fmt_pct(top_bt.get("cumulative_return", 0) * 100), str(top_bt.get("ticker", "")))
        b2.metric("勝率", _fmt_pct(top_bt.get("win_rate", 0) * 100))
        b3.metric("最大回撤", _fmt_pct(top_bt.get("max_drawdown", 0) * 100))
        b4.metric("停損命中率", _fmt_pct(top_bt.get("stop_loss_hit_rate", 0) * 100))

        st.markdown("#### 持有天數 / 出場規則比較")
        if not tab_backtest_compare_enabled:
            st.info("多策略比較目前未啟用。請在本頁『回測設定』打開『啟用持有天數 / 出場規則比較』後，選擇要比較的持有天數與出場規則。")
        elif tab_scenario_comparison.empty:
            st.info("目前設定下沒有足夠資料產生策略比較。")
        else:
            st.plotly_chart(_build_scenario_comparison_chart(tab_scenario_comparison), use_container_width=True)
            scenario_display = _humanize_backtest_summary(tab_scenario_comparison)
            st.dataframe(
                scenario_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "持有天數": st.column_config.NumberColumn(format="%d"),
                    "交易次數": st.column_config.NumberColumn(format="%d"),
                    "勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                    "停損命中率%": st.column_config.NumberColumn(format="%.1f%%"),
                    "時間出場率%": st.column_config.NumberColumn(format="%.1f%%"),
                    "移動停損率%": st.column_config.NumberColumn(format="%.1f%%"),
                    "累積報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                    "最大回撤%": st.column_config.NumberColumn(format="%.2f%%"),
                    "平均單筆報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                    "Profit Factor": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            st.download_button(
                "下載策略比較 CSV",
                scenario_display.to_csv(index=False).encode("utf-8-sig"),
                file_name="ai_stock_backtest_scenario_comparison.csv",
                mime="text/csv",
            )

        st.markdown("#### Smart Tuning Lite")
        st.caption("掃描持有天數、出場規則與風險寬度，依累積報酬、勝率、Profit Factor、最大回撤與停損率產生綜合分數。")
        smart_current = st.session_state.smart_tuning_signature == tab_smart_tuning_signature and not st.session_state.smart_tuning_result.empty
        run_smart = st.button(
            "執行 Smart Tuning Lite",
            type="primary",
            use_container_width=True,
            help="按下後才執行參數掃描；會比一般回測多跑數十組情境。",
        )
        if run_smart:
            with st.spinner("正在執行 Smart Tuning Lite 參數掃描…"):
                smart_result = _cached_smart_tuning_lite(
                    prices,
                    horizons=tuple(tab_smart_tuning_horizons or [horizon]),
                    exit_rules=tuple(tab_backtest_exit_rules or ["time", "stop_loss", "trailing_stop"]),
                    stop_loss_pcts=tuple(float(v) / 100 for v in tab_smart_tuning_stop_widths_pct or [5]),
                    lookback=tab_backtest_lookback,
                    only_buy_watch=tab_backtest_only_buy,
                    trailing_stop_pct=tab_trailing_stop_pct,
                )
            st.session_state.smart_tuning_result = smart_result
            st.session_state.smart_tuning_signature = tab_smart_tuning_signature
            smart_current = not smart_result.empty
        smart_result = st.session_state.smart_tuning_result
        if smart_result.empty:
            st.info("尚未執行 Smart Tuning Lite。請按上方按鈕比較持有天數、出場規則與風險寬度。")
        else:
            if not smart_current:
                st.warning("目前顯示的是上一次 Smart Tuning 結果；sidebar 資料或參數已改變。若要更新，請再按一次。")
            st.plotly_chart(_build_smart_tuning_chart(smart_result), use_container_width=True)
            smart_display = _humanize_smart_tuning(smart_result.head(60))
            st.dataframe(
                smart_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    t("排名", UI_LANG): st.column_config.NumberColumn(format="%d"),
                    t("持有天數", UI_LANG): st.column_config.NumberColumn(format="%d"),
                    t("風險寬度%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                    t("綜合分數", UI_LANG): st.column_config.NumberColumn(format="%.2f"),
                    t("勝率%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                    t("停損命中率%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                    t("累積報酬%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                    t("最大回撤%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                    "Profit Factor": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            st.download_button(
                "下載 Smart Tuning CSV",
                _humanize_smart_tuning(smart_result).to_csv(index=False).encode("utf-8-sig"),
                file_name="ai_stock_smart_tuning_lite.csv",
                mime="text/csv",
            )

        st.markdown("#### 目前決策天數的逐筆回測")
        st.dataframe(
            bt_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "交易次數": st.column_config.NumberColumn(format="%d"),
                "勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                "停損命中率%": st.column_config.NumberColumn(format="%.1f%%"),
                "累積報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                "最大回撤%": st.column_config.NumberColumn(format="%.2f%%"),
                "平均單筆報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                "Profit Factor": st.column_config.NumberColumn(format="%.2f"),
            },
        )

        if tab_backtest.equity_curve.empty:
            st.info("目前設定下沒有產生交易曲線；可關閉『只吃偏多觀察訊號』或拉長資料區間。")
        else:
            all_label = _("全部")
            bt_ticker = st.selectbox("選擇回測曲線代號", [all_label] + visible_tickers, key="bt_ticker")
            st.plotly_chart(_build_equity_chart(tab_backtest.equity_curve, None if bt_ticker == all_label else bt_ticker), use_container_width=True)

        if not tab_backtest.trades.empty:
            with st.expander("查看逐筆交易", expanded=False):
                bt_trades = _humanize_backtest_trades(tab_backtest.trades.tail(200))
                st.dataframe(
                    bt_trades,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "進場價": st.column_config.NumberColumn(format="%.2f"),
                        "出場價": st.column_config.NumberColumn(format="%.2f"),
                        "單筆報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                        "當時模型預估%": st.column_config.NumberColumn(format="%.2f%%"),
                        "當時關係調整%": st.column_config.NumberColumn(format="%.2f%%"),
                        "當時 Kelly%": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
                st.download_button(
                    "下載回測逐筆交易 CSV",
                    _humanize_backtest_trades(tab_backtest.trades).to_csv(index=False).encode("utf-8-sig"),
                    file_name="ai_stock_backtest_trades.csv",
                    mime="text/csv",
                )

with tab_factor:
    st.subheader("因子研究：過去 N 天因子 → 未來多個預測天數 漲跌")
    st.caption(
        "用 sliding window 收集歷史樣本：X 是過去 N 天 K線、KD、MACD、RSI、量能、波動與回撤等因子；"
        "y 是未來 1/3/5/10 天報酬是否高於漲跌門檻。每個預測天數獨立訓練與歸因；這是模型歸因與統計關聯，不是因果證明。"
    )
    with st.expander("因子研究設定", expanded=True):
        factor_cfg1, factor_cfg2 = st.columns(2)
        with factor_cfg1:
            factor_window = st.slider("因子輸入天數", 3, 21, 7, help="sliding window 的 X：使用過去 N 天 K線/KD/MACD/RSI 等因子。", key="tab_factor_window")
            factor_horizons = st.multiselect(
                "比較預測幾天後",
                [1, 3, 5, 10],
                default=[1, 3, 5, 10],
                help="一次比較未來 1/3/5/10 天漲跌；每個預測天數會各自訓練模型與計算 SHAP/fallback 重要度。",
                key="tab_factor_horizons",
            )
            if not factor_horizons:
                factor_horizons = [1]
        with factor_cfg2:
            factor_threshold_pct = st.slider("漲跌分類門檻%", 0.0, 2.0, 0.0, step=0.1, help="forward return 高於此門檻才標為上漲，可降低微小雜訊。", key="tab_factor_threshold_pct")
            factor_model_labels = {"Gradient Boosting": "gradient_boosting", "Random Forest": "random_forest", "Logistic Regression": "logistic"}
            factor_model_label = st.selectbox("因子模型", list(factor_model_labels), index=0, key="tab_factor_model")
            factor_model_type = factor_model_labels[factor_model_label]
    factor_signature = (
        tuple(visible_tickers),
        str(prices["date"].min()),
        str(prices["date"].max()),
        int(len(prices)),
        int(factor_window),
        tuple(int(h) for h in factor_horizons),
        float(factor_threshold_pct),
        str(factor_model_type),
    )
    st.write(
        _(
            "目前設定：過去 {window} 天因子 → 比較未來 {horizons} 天漲跌；上漲門檻 {threshold:.1f}%；模型 {model}。",
            window=factor_window,
            horizons=", ".join(str(h) for h in factor_horizons),
            threshold=factor_threshold_pct,
            model=factor_model_label,
        )
    )
    current_factor_signature = st.session_state.factor_signature
    factor_tables = st.session_state.factor_research_report
    factor_is_current = current_factor_signature == factor_signature and factor_tables is not None
    run_factor = st.button(
        "執行多個預測天數 因子研究",
        type="primary",
        use_container_width=True,
        help="按下後才針對每個預測天數建立 sliding-window dataset、訓練分類模型並計算 SHAP/fallback、相關性與分組勝率。",
    )
    if run_factor:
        with st.spinner("正在建立 sliding-window 樣本並訓練多個預測天數 因子模型…"):
            factor_tables = _cached_factor_horizon_comparison(prices, factor_window, tuple(factor_horizons), factor_threshold_pct, factor_model_type)
        st.session_state.factor_research_report = factor_tables
        st.session_state.factor_signature = factor_signature
        factor_is_current = factor_tables is not None

    if factor_tables is None:
        st.info("尚未執行因子研究。請按『執行多個預測天數 因子研究』；建議先用 1y 以上日 K，樣本會比較穩。")
    elif factor_tables.get("summary", pd.DataFrame()).empty:
        st.warning("目前資料量或漲跌樣本不足以訓練因子模型；請拉長歷史區間、降低漲跌門檻，或改用日 K。")
    else:
        if not factor_is_current:
            st.warning("目前顯示的是上一次因子研究結果；sidebar 資料或因子參數已改變。若要更新，請再按一次『執行多個預測天數 因子研究』。")
        summary_table = factor_tables["summary"]
        importance_table = factor_tables["importance"]
        correlations_table = factor_tables["correlations"]
        grouped_table = factor_tables["grouped_win_rates"]
        heatmap_table = factor_tables["y_heatmap"]
        st.markdown("#### 多個預測天數 勝率與 AUC 趨勢")
        st.plotly_chart(_build_factor_horizon_trend_chart(summary_table), use_container_width=True)
        trend_display = build_horizon_metric_trends(summary_table).copy()
        if not trend_display.empty:
            for col in ["accuracy", "auc", "baseline_up_rate"]:
                trend_display[col] = trend_display[col] * 100
            trend_display = trend_display.rename(
                columns={
                    "horizon": "預測天數",
                    "accuracy": "平均測試勝率%",
                    "auc": "平均 AUC%",
                    "baseline_up_rate": "平均歷史上漲率%",
                    "sample_count": "總樣本數",
                    "ticker_count": "股票數",
                }
            )
            st.dataframe(
                trend_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "預測天數": st.column_config.NumberColumn(format="%d"),
                    "平均測試勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                    "平均 AUC%": st.column_config.NumberColumn(format="%.1f%%"),
                    "平均歷史上漲率%": st.column_config.NumberColumn(format="%.1f%%"),
                    "總樣本數": st.column_config.NumberColumn(format="%d"),
                    "股票數": st.column_config.NumberColumn(format="%d"),
                },
            )
        st.markdown("#### 每檔股票 × 預測天數表現熱力圖")
        metric_options = {
            "測試勝率 / Accuracy": "accuracy",
            "AUC": "auc",
            "歷史上漲率 baseline": "baseline_up_rate",
        }
        heat_metric_label = st.selectbox("熱力圖指標", list(metric_options), key="factor_ticker_horizon_heatmap_metric")
        st.plotly_chart(_build_factor_ticker_horizon_heatmap(summary_table, metric_options[heat_metric_label]), use_container_width=True)
        st.caption("顏色越綠代表該股票在該預測天數的指標越高；AUC 接近 50% 代表模型排序能力接近隨機。")

        st.markdown("#### 多個預測天數 模型表現比較")
        best_factor = summary_table.sort_values(["accuracy", "auc"], ascending=False).iloc[0]
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("最佳預測天數", f"{int(best_factor.get('horizon', 0))} 天", str(best_factor.get("ticker", "")))
        f2.metric("測試準確率", _fmt_pct(best_factor.get("accuracy", 0) * 100))
        f3.metric("AUC", _fmt_pct(best_factor.get("auc", 0) * 100) if pd.notna(best_factor.get("auc", None)) else "—")
        f4.metric("歷史上漲率", _fmt_pct(best_factor.get("baseline_up_rate", 0) * 100))
        factor_summary = _humanize_factor_summary(summary_table)
        st.dataframe(
            factor_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "樣本數": st.column_config.NumberColumn(format="%d"),
                "訓練樣本": st.column_config.NumberColumn(format="%d"),
                "測試樣本": st.column_config.NumberColumn(format="%d"),
                "歷史上漲率%": st.column_config.NumberColumn(format="%.1f%%"),
                "測試準確率%": st.column_config.NumberColumn(format="%.1f%%"),
                "AUC%": st.column_config.NumberColumn(format="%.1f%%"),
                "預測天數": st.column_config.NumberColumn(format="%d"),
                "漲跌門檻%": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

        factor_ticker = st.selectbox("選擇因子研究代號", sorted(summary_table["ticker"].unique()), key="factor_ticker")
        available_horizons = sorted(int(h) for h in summary_table[summary_table["ticker"] == factor_ticker]["horizon"].unique())
        factor_detail_horizon = st.selectbox("選擇要查看的預測天數", available_horizons, key="factor_detail_horizon")
        st.markdown("#### 重要因子與相對貢獻")
        one_importance = importance_table[(importance_table["ticker"] == factor_ticker) & (importance_table["horizon"] == factor_detail_horizon)]
        if one_importance.empty:
            st.info("這檔股票 / 預測天數沒有可顯示的重要因子。")
        else:
            method = str(one_importance["method"].iloc[0])
            st.write(_("目前歸因方法：{method}", method=method))
            st.plotly_chart(_build_factor_importance_chart(importance_table[importance_table["horizon"] == factor_detail_horizon], factor_ticker), use_container_width=True)
            factor_imp_display = one_importance.copy().rename(
                columns={
                    "ticker": "代號",
                    "horizon": "預測天數",
                    "feature_label": "因子",
                    "importance": "重要度",
                    "signed_contribution": "方向貢獻",
                    "direction": "方向",
                    "method": "方法",
                }
            )
            st.dataframe(
                localize_dataframe_for_display(
                    factor_imp_display,
                    ["代號", "預測天數", "因子", "重要度", "方向貢獻", "方向", "方法"],
                    UI_LANG,
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    t("預測天數", UI_LANG): st.column_config.NumberColumn(format="%d"),
                    t("重要度", UI_LANG): st.column_config.NumberColumn(format="%.5f"),
                    t("方向貢獻", UI_LANG): st.column_config.NumberColumn(format="%.5f"),
                },
            )

        st.markdown("#### y heat：歷史每個時間點的未來漲跌結果")
        st.plotly_chart(_build_y_heatmap(heatmap_table[heatmap_table["horizon"] == factor_detail_horizon], factor_ticker), use_container_width=True)

        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown("#### 因子相關性")
            corr_display = correlations_table[(correlations_table["ticker"] == factor_ticker) & (correlations_table["horizon"] == factor_detail_horizon)].copy()
            if not corr_display.empty:
                corr_display = corr_display.rename(
                    columns={
                        "horizon": "預測天數",
                        "feature_label": "因子",
                        "spearman_corr": "Spearman",
                        "pearson_corr": "Pearson",
                        "mutual_info": "Mutual Info",
                    }
                )
                st.dataframe(
                    localize_dataframe_for_display(corr_display, ["預測天數", "因子", "Spearman", "Pearson", "Mutual Info"], UI_LANG),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        t("預測天數", UI_LANG): st.column_config.NumberColumn(format="%d"),
                        "Spearman": st.column_config.NumberColumn(format="%.4f"),
                        "Pearson": st.column_config.NumberColumn(format="%.4f"),
                        "Mutual Info": st.column_config.NumberColumn(format="%.4f"),
                    },
                )
        with c_right:
            st.markdown("#### 因子分組勝率")
            group_display = grouped_table[(grouped_table["ticker"] == factor_ticker) & (grouped_table["horizon"] == factor_detail_horizon)].copy()
            if not group_display.empty:
                group_display["up_rate"] = group_display["up_rate"] * 100
                group_display["avg_forward_return"] = group_display["avg_forward_return"] * 100
                group_display = group_display.rename(
                    columns={
                        "horizon": "預測天數",
                        "feature_label": "因子",
                        "bucket": "分位組",
                        "samples": "樣本數",
                        "up_rate": "上漲率%",
                        "avg_forward_return": "平均未來報酬%",
                    }
                )
                st.dataframe(
                    localize_dataframe_for_display(
                        group_display,
                        ["預測天數", "因子", "分位組", "樣本數", "上漲率%", "平均未來報酬%"],
                        UI_LANG,
                    ),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        t("預測天數", UI_LANG): st.column_config.NumberColumn(format="%d"),
                        t("樣本數", UI_LANG): st.column_config.NumberColumn(format="%d"),
                        t("上漲率%", UI_LANG): st.column_config.NumberColumn(format="%.1f%%"),
                        t("平均未來報酬%", UI_LANG): st.column_config.NumberColumn(format="%.2f%%"),
                    },
                )
        st.download_button(
            "下載多個預測天數 因子重要度 CSV",
            _humanize_factor_importance(importance_table).to_csv(index=False).encode("utf-8-sig"),
            file_name="ai_stock_factor_horizon_importance.csv",
            mime="text/csv",
        )

with tab_attribution:
    st.subheader("SHAP / 歸因分析")
    st.caption("這裡解釋的是技術指標對『未來報酬模型』的正/負向貢獻；按下按鈕才會計算，切換 sidebar 或分頁不會自動重算。")
    current_attr_signature = st.session_state.shap_signature
    attribution = st.session_state.shap_attribution
    attr_is_current = current_attr_signature == shap_signature and not attribution.empty

    run_attr = st.button(
        "執行 SHAP 歸因分析",
        type="primary",
        use_container_width=True,
        help="只在按下時執行 SHAP / fallback 歸因；結果會保留在目前瀏覽器 session。",
    )
    if run_attr:
        with st.spinner("正在執行 SHAP / 歸因分析…"):
            attribution = _cached_attribution(prices, horizon)
        st.session_state.shap_attribution = attribution
        st.session_state.shap_signature = shap_signature
        current_attr_signature = shap_signature
        attr_is_current = not attribution.empty

    if attribution.empty:
        st.info("尚未執行歸因分析。請按『執行 SHAP 歸因分析』；資料量較大時可能需要數秒到十幾秒。")
    else:
        if not attr_is_current:
            st.warning("目前顯示的是上一次 SHAP 歸因結果；sidebar 資料或決策天數已改變。若要更新，請再按一次『執行 SHAP 歸因分析』。")
        attr_ticker = st.selectbox("選擇歸因代號", sorted(attribution["ticker"].unique()), key="attr_ticker")
        one_attr = attribution[attribution["ticker"] == attr_ticker]
        if one_attr.empty:
            st.info("這檔股票目前沒有足夠資料產生歸因。")
        else:
            method = str(one_attr["method"].iloc[0])
            st.write(_("目前歸因方法：{method}", method=method))
            st.plotly_chart(_build_attribution_chart(attribution, attr_ticker), use_container_width=True)
            display = one_attr.copy()
            display["contribution_pct_point"] = display["contribution"] * 100
            display = display.rename(
                columns={
                    "feature_label": "指標",
                    "value": "目前值",
                    "contribution_pct_point": "歸因百分點",
                    "direction": "方向",
                    "method": "方法",
                }
            )
            st.dataframe(
                localize_dataframe_for_display(display, ["指標", "目前值", "歸因百分點", "方向", "方法"], UI_LANG),
                use_container_width=True,
                hide_index=True,
                column_config={t("歸因百分點", UI_LANG): st.column_config.NumberColumn(format="%.3f%%")},
            )
            st.info("解讀：綠色代表模型認為該指標提高未來報酬估計；紅色代表拉低估計。這是統計歸因，不代表單一因果。")

with tab_relation:
    st.subheader("股票間報酬相關性")
    if len(visible_tickers) < 2:
        st.info("至少輸入兩檔股票才會產生相關性分析。")
    else:
        st.plotly_chart(_build_corr_heatmap(correlations, visible_tickers), use_container_width=True)
        st.dataframe(correlations, use_container_width=True, hide_index=True)
        st.caption("接近 +1 代表同漲同跌程度高；接近 -1 代表反向；接近 0 代表近期關聯較低。決策表中的『同/反向關係壓力』會把這些關係與近5日同業/反向標的表現合併成輔助訊號。")

with tab_raw:
    st.subheader("研究與訓練資料中心")
    st.caption("把每天價格、技術指標、SMC/型態信號與未來報酬目標整理成一張可下載的 training data。一般使用者可檢查資料是否合理；研究者可下載後再訓練未來三天趨勢 AI model。")
    with st.expander("頁籤使用目的與簡單名詞", expanded=True):
        st.write("『等待確認』：不是沒有模型，而是舊決策總覽認為預估報酬還沒有大過近期波動與回撤風險；操作上代表先不追價、不新增倉位，已持有者優先看停損與停利。")
        st.write("『預測幾天後』：以前畫面常寫 horizon，意思就是用今天資料去看幾天後的漲跌，例如 3 天後報酬。")
        st.write("『Training Data』：每一列是一檔股票某一天，欄位分成模型輸入 X（價格/技術指標）、輔助訊號（SMC/UKF/K線型態）與模型答案 y（未來 N 天報酬/漲跌標籤）。")
        st.write("建議流程：先看決策總覽 → 隔日掛單/策略驗證 → 回測/因子研究 → 最後下載 Training Data 做模型研究。")
    with st.expander("欄位字典：Training Data 怎麼看？", expanded=False):
        st.write("`forward_return_Nd`：N 天後報酬，也就是模型要學的主要答案。")
        st.write("`target_up_Nd`：N 天後是否上漲，1 代表上漲、0 代表沒有上漲。")
        st.write("`target_available_Nd`：這一列是否真的有未來答案；最後 N 天尚未發生，所以會是 0，不應拿來訓練 y。")
        st.write("SMC 欄位：FVG、Order Block、Liquidity、BOS/ChoCH 等市場結構特徵。")
        st.write("UKF / pattern 欄位：去噪動能與 K 線型態，作為輔助特徵。")
        st.warning("這是資料集，不是已訓練完成的 AI 模型；下載後仍需切分 train/test、避免資料洩漏並做 walk-forward 驗證。")

    training_forward_days = st.selectbox("預測幾天後", [1, 3, 5, 10], index=1, help="用今天以前已知的欄位，建立未來幾天後的報酬與漲跌標籤；預設 3 天是為未來三天趨勢模型準備。")
    current_training_signature = (tuple(visible_tickers), str(prices["date"].max()) if not prices.empty else "", int(training_forward_days), len(prices))
    run_training_data = st.button("產生 Training Data", type="primary", use_container_width=True, help="按下後才整理完整欄位；首次包含 SMC/UKF 特徵時可能較慢。")
    if run_training_data or st.session_state.get("training_data_signature") == current_training_signature:
        if run_training_data:
            with st.spinner("正在整理分析結果數據 / training data…"):
                training_dataset, top_training_features = _cached_training_dataset(prices, int(training_forward_days))
            st.session_state.training_data_result = (training_dataset, top_training_features)
            st.session_state.training_data_signature = current_training_signature
        else:
            training_dataset, top_training_features = st.session_state.get("training_data_result", (pd.DataFrame(), pd.DataFrame()))

        st.markdown("#### 分析結果數據（Training Data）")
        if training_dataset.empty:
            st.info("目前資料不足，尚無法產生 training data。")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("資料列數", f"{len(training_dataset):,}")
            c2.metric("欄位數", f"{len(training_dataset.columns):,}")
            c3.metric("股票數", f"{training_dataset['ticker'].nunique():,}")
            c4.metric("預測目標", f"未來 {training_forward_days} 天")
            st.markdown("#### 最有相關性的前 N 個欄位")
            st.caption("用 Pearson/Spearman 相關性快速找出和未來報酬最有關的欄位；SMC 欄位也會一起排序。相關強度高只代表歷史一起變動較明顯，不代表一定可預測或有因果。")
            top_n_features = st.slider("顯示前幾個欄位", min_value=5, max_value=30, value=15, step=5)
            st.dataframe(
                top_training_features.head(top_n_features),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "feature": st.column_config.TextColumn("欄位"),
                    "pearson_corr": st.column_config.NumberColumn("線性相關", format="%.4f"),
                    "spearman_corr": st.column_config.NumberColumn("排名相關", format="%.4f"),
                    "abs_score": st.column_config.NumberColumn("相關強度", format="%.4f"),
                    "non_null_ratio": st.column_config.NumberColumn("資料完整度", format="%.2f"),
                },
            )
            st.markdown("#### 每日完整欄位資料")
            st.caption("每列是一檔股票某一天；包含 OHLCV、RSI/MACD/KD/布林/量能/UKF、SMC FVG/OB/Liquidity/BOS/ChoCH、K 線型態與未來報酬標籤。最後 N 天 target_available=0，代表還沒有真實未來答案。")
            selected_training_ticker = st.selectbox("查看哪一檔 training data", ["全部"] + sorted(training_dataset["ticker"].astype(str).unique()), key="training_data_ticker")
            training_view = training_dataset if selected_training_ticker == "全部" else training_dataset[training_dataset["ticker"].astype(str) == selected_training_ticker]
            st.dataframe(training_view.tail(800), use_container_width=True, hide_index=True)
            st.download_button(
                "下載 Training Data CSV",
                training_dataset.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"ai_stock_training_data_forward_{training_forward_days}d.csv",
                mime="text/csv",
            )
            st.download_button(
                "下載最相關欄位 CSV",
                top_training_features.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"ai_stock_top_training_features_forward_{training_forward_days}d.csv",
                mime="text/csv",
            )
    else:
        st.info("Training Data 尚未產生。請先選『預測幾天後』，再按『產生 Training Data』；這樣不會拖慢首頁載入。")

    st.markdown("#### 技術指標 Snapshot")
    human_snapshot = _humanize_snapshot(snapshot)
    st.dataframe(human_snapshot, use_container_width=True, hide_index=True)
    st.markdown("#### 原始標準化價格資料")
    st.dataframe(prices.tail(500), use_container_width=True, hide_index=True)

st.info("提醒：這是研究與決策輔助，不是投資建議；Futu OpenAPI 實盤/即時串接需可執行 OpenD 的主機或遠端 OpenD。")
