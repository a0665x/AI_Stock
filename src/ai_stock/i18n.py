from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
import re

import pandas as pd

LANGUAGES: dict[str, str] = {
    "zh": "繁體中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
}

_LANGUAGE_ALIASES = {
    "繁體中文": "zh",
    "中文": "zh",
    "English": "en",
    "日本語": "ja",
    "한국어": "ko",
}

# UI labels are keyed by the existing Traditional Chinese copy so the Streamlit app can
# keep one readable source of truth while offering four display languages.
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "語言": {"en": "Language", "ja": "言語", "ko": "언어"},
    "AI Stock 決策儀表板": {"en": "AI Stock Decision Dashboard", "ja": "AI Stock 意思決定ダッシュボード", "ko": "AI Stock 의사결정 대시보드"},
    "📈 AI Stock 決策儀表板": {"en": "📈 AI Stock Decision Dashboard", "ja": "📈 AI Stock 意思決定ダッシュボード", "ko": "📈 AI Stock 의사결정 대시보드"},
    "先看決策，再看原因：價格趨勢、技術指標、股票相關性與可解釋的數學預估。此工具只做研究輔助，不自動下單。": {"en": "Start with the decision, then inspect the reasons: price trend, technical indicators, stock relationships, and explainable quantitative estimates. This tool is for research support only and never places trades.", "ja": "まず判断を確認し、その理由として価格トレンド、テクニカル指標、銘柄間の関係、説明可能な数理予測を確認します。このツールは研究支援のみで、自動売買は行いません。", "ko": "먼저 결정을 보고, 가격 추세·기술 지표·종목 관계·설명 가능한 수학적 추정으로 이유를 확인하세요. 이 도구는 연구 보조용이며 자동 주문을 하지 않습니다."},
    "提醒：這是研究與決策輔助，不是投資建議；Futu OpenAPI 實盤/即時串接需可執行 OpenD 的主機或遠端 OpenD。": {"en": "Reminder: this is research and decision support, not investment advice. Live/real-time Futu OpenAPI requires a machine that can run OpenD or a remote OpenD service.", "ja": "注意：これは研究・意思決定支援であり、投資助言ではありません。Futu OpenAPI の実運用/リアルタイム接続には OpenD を実行できるマシンまたはリモート OpenD が必要です。", "ko": "알림: 이는 연구 및 의사결정 보조 도구이며 투자 조언이 아닙니다. Futu OpenAPI 실시간 연동에는 OpenD 실행 가능 호스트 또는 원격 OpenD가 필요합니다."},
    "1 選資料 → 2 調參數 → 3 看決策摘要": {"en": "1 Choose data → 2 Tune parameters → 3 Read the decision summary", "ja": "1 データ選択 → 2 パラメータ調整 → 3 判断サマリー確認", "ko": "1 데이터 선택 → 2 파라미터 조정 → 3 결정 요약 확인"},
    "資料來源": {"en": "Data source", "ja": "データソース", "ko": "데이터 소스"},
    "股票代號": {"en": "Tickers", "ja": "銘柄コード", "ko": "종목 코드"},
    "可用逗號或換行分隔，例如 AAPL, MSFT, NVDA": {"en": "Separate with commas or new lines, e.g. AAPL, MSFT, NVDA", "ja": "カンマまたは改行で区切ります。例：AAPL, MSFT, NVDA", "ko": "쉼표 또는 줄바꿈으로 구분하세요. 예: AAPL, MSFT, NVDA"},
    "歷史區間": {"en": "History range", "ja": "履歴期間", "ko": "기간"},
    "K線週期": {"en": "K-line interval", "ja": "ローソク足間隔", "ko": "캔들 주기"},
    "決策天數": {"en": "Decision horizon", "ja": "判断日数", "ko": "결정 기간"},
    "分析設定": {"en": "Analysis settings", "ja": "分析設定", "ko": "분석 설정"},
    "K 線圖顯示成交量": {"en": "Show volume on candlestick chart", "ja": "ローソク足チャートに出来高を表示", "ko": "캔들 차트에 거래량 표시"},
    "重新抓資料 / 更新分析": {"en": "Refresh data / recompute analysis", "ja": "データ再取得 / 分析更新", "ko": "데이터 새로고침 / 분석 업데이트"},
    "已清除行情與分析快取，正在重新抓資料。": {"en": "Market and analysis caches cleared. Fetching fresh data.", "ja": "市場データと分析キャッシュを削除しました。再取得中です。", "ko": "시세 및 분석 캐시를 지웠습니다. 새 데이터를 가져오는 중입니다."},
    "行情資料已快取 1 小時，並寫入 docker_runtime/market_cache；Docker 重啟後仍會優先讀磁碟快取。需要最新行情時再按下方按鈕。": {"en": "Market data is cached for 1 hour and persisted under docker_runtime/market_cache. After Docker restarts, disk cache is still used first. Press the button below when you need fresh data.", "ja": "市場データは1時間キャッシュされ、docker_runtime/market_cache に保存されます。Docker再起動後もディスクキャッシュを優先します。最新データが必要な場合は下のボタンを押してください。", "ko": "시세 데이터는 1시간 캐시되며 docker_runtime/market_cache에 저장됩니다. Docker 재시작 후에도 디스크 캐시를 우선 사용합니다. 최신 데이터가 필요하면 아래 버튼을 누르세요."},
    "正在抓取行情並計算指標…": {"en": "Fetching market data and computing indicators…", "ja": "市場データ取得と指標計算中…", "ko": "시세 데이터를 가져오고 지표를 계산 중…"},
    "正在計算決策、回測與可視化資料…": {"en": "Computing decisions, backtests, and visualizations…", "ja": "判断・バックテスト・可視化データを計算中…", "ko": "결정, 백테스트, 시각화 데이터를 계산 중…"},
    "目前沒有價格資料。請輸入可由 yfinance 查詢的代號，或上傳 CSV。": {"en": "No price data available. Enter tickers supported by yfinance or upload a CSV.", "ja": "価格データがありません。yfinanceで取得できる銘柄を入力するか、CSVをアップロードしてください。", "ko": "가격 데이터가 없습니다. yfinance에서 조회 가능한 종목을 입력하거나 CSV를 업로드하세요."},
    "資料載入失敗：{exc}": {"en": "Data loading failed: {exc}", "ja": "データ読み込み失敗：{exc}", "ko": "데이터 로드 실패: {exc}"},
    "決策報表": {"en": "Decision report", "ja": "判断レポート", "ko": "결정 보고서"},
    "價格圖表": {"en": "Price charts", "ja": "価格チャート", "ko": "가격 차트"},
    "回測": {"en": "Backtest", "ja": "バックテスト", "ko": "백테스트"},
    "因子研究": {"en": "Factor research", "ja": "ファクター研究", "ko": "팩터 연구"},
    "##### 因子研究": {"en": "##### Factor research", "ja": "##### ファクター研究", "ko": "##### 팩터 연구"},
    "歸因分析": {"en": "Attribution", "ja": "寄与度分析", "ko": "기여도 분석"},
    "SHAP / 歸因分析": {"en": "SHAP / Attribution", "ja": "SHAP / 寄与度分析", "ko": "SHAP / 기여도 분석"},
    "股票關係": {"en": "Stock relationships", "ja": "銘柄関係", "ko": "종목 관계"},
    "資料明細": {"en": "Data details", "ja": "データ詳細", "ko": "데이터 상세"},
    "今天先看這三件事": {"en": "Start with these three things", "ja": "まずこの3点を見る", "ko": "먼저 이 세 가지를 보세요"},
    "優先觀察": {"en": "Top watch", "ja": "優先監視", "ko": "우선 관찰"},
    "預估報酬": {"en": "Expected return", "ja": "予想リターン", "ko": "예상 수익률"},
    "關係調整報酬": {"en": "Relationship-adjusted return", "ja": "関係調整後リターン", "ko": "관계 조정 수익률"},
    "買進參考": {"en": "Buy reference", "ja": "買い参考", "ko": "매수 참고"},
    "停損參考": {"en": "Stop-loss reference", "ja": "損切り参考", "ko": "손절 참고"},
    "賣出參考": {"en": "Sell reference", "ja": "売り参考", "ko": "매도 참고"},
    "Kelly 倉位": {"en": "Kelly position", "ja": "Kelly ポジション", "ko": "Kelly 비중"},
    "怎麼讀這份報表？": {"en": "How to read this report", "ja": "このレポートの読み方", "ko": "이 보고서 읽는 법"},
    "買 / 賣 / 停損決策報表": {"en": "Buy / Sell / Stop-loss decision report", "ja": "買い / 売り / 損切り判断レポート", "ko": "매수 / 매도 / 손절 결정 보고서"},
    "Kelly / 決策原因怎麼看？": {"en": "How to read Kelly / decision reasons", "ja": "Kelly / 判断理由の読み方", "ko": "Kelly / 결정 이유 읽는 법"},
    "下載決策報表 CSV": {"en": "Download decision report CSV", "ja": "判断レポートCSVをダウンロード", "ko": "결정 보고서 CSV 다운로드"},
    "技術指標 Snapshot": {"en": "Technical indicator snapshot", "ja": "テクニカル指標スナップショット", "ko": "기술 지표 스냅샷"},
    "Walk-forward 回測": {"en": "Walk-forward backtest", "ja": "ウォークフォワード・バックテスト", "ko": "워크포워드 백테스트"},
    "勝率": {"en": "Win rate", "ja": "勝率", "ko": "승률"},
    "最大回撤": {"en": "Max drawdown", "ja": "最大ドローダウン", "ko": "최대 낙폭"},
    "停損命中率": {"en": "Stop-loss hit rate", "ja": "損切りヒット率", "ko": "손절 적중률"},
    "累積報酬%": {"en": "Cumulative return %", "ja": "累積リターン%", "ko": "누적 수익률%"},
    "交易次數": {"en": "Trades", "ja": "取引回数", "ko": "거래 수"},
    "平均單筆報酬%": {"en": "Avg trade return %", "ja": "平均取引リターン%", "ko": "평균 거래 수익률%"},
    "下載回測逐筆交易 CSV": {"en": "Download backtest trades CSV", "ja": "バックテスト取引CSVをダウンロード", "ko": "백테스트 거래 CSV 다운로드"},
    "持有天數 / 出場規則比較": {"en": "Holding days / exit-rule comparison", "ja": "保有日数 / 出口ルール比較", "ko": "보유 기간 / 청산 규칙 비교"},
    "多 horizon 勝率與 AUC 趨勢": {"en": "Multi-horizon win-rate and AUC trend", "ja": "複数 horizon の勝率・AUC トレンド", "ko": "다중 horizon 승률 및 AUC 추세"},
    "每檔股票 × horizon 表現熱力圖": {"en": "Ticker × horizon performance heatmap", "ja": "銘柄 × horizon パフォーマンスヒートマップ", "ko": "종목 × horizon 성과 히트맵"},
    "多 horizon 模型表現比較": {"en": "Multi-horizon model performance comparison", "ja": "複数 horizon モデル性能比較", "ko": "다중 horizon 모델 성과 비교"},
    "重要因子與相對貢獻": {"en": "Important factors and relative contribution", "ja": "重要ファクターと相対寄与", "ko": "중요 팩터와 상대 기여도"},
    "因子相關性": {"en": "Factor correlations", "ja": "ファクター相関", "ko": "팩터 상관"},
    "因子分組勝率": {"en": "Grouped factor win rates", "ja": "ファクター分位別勝率", "ko": "팩터 그룹별 승률"},
    "y heat：歷史每個時間點的未來漲跌結果": {"en": "y heat: future outcome at each historical point", "ja": "y heat：各過去時点の将来結果", "ko": "y heat: 각 과거 시점의 미래 결과"},
    "執行多 horizon 因子研究": {"en": "Run multi-horizon factor research", "ja": "複数 horizon ファクター研究を実行", "ko": "다중 horizon 팩터 연구 실행"},
    "執行 SHAP 歸因分析": {"en": "Run SHAP attribution", "ja": "SHAP 寄与度分析を実行", "ko": "SHAP 기여도 분석 실행"},
    "正在建立 sliding-window 樣本並訓練多 horizon 因子模型…": {"en": "Building sliding-window samples and training multi-horizon factor models…", "ja": "スライディングウィンドウ標本を作成し、複数 horizon のファクターモデルを学習中…", "ko": "슬라이딩 윈도우 샘플을 만들고 다중 horizon 팩터 모델을 학습 중…"},
    "正在執行 SHAP / 歸因分析…": {"en": "Running SHAP / attribution analysis…", "ja": "SHAP / 寄与度分析を実行中…", "ko": "SHAP / 기여도 분석 실행 중…"},
    "測試勝率 / Accuracy": {"en": "Test win rate / Accuracy", "ja": "テスト勝率 / Accuracy", "ko": "테스트 승률 / Accuracy"},
    "AUC": {"en": "AUC", "ja": "AUC", "ko": "AUC"},
    "歷史上漲率 baseline": {"en": "Historical up-rate baseline", "ja": "過去上昇率 baseline", "ko": "과거 상승률 baseline"},
    "熱力圖指標": {"en": "Heatmap metric", "ja": "ヒートマップ指標", "ko": "히트맵 지표"},
    "選擇因子研究代號": {"en": "Select factor-research ticker", "ja": "ファクター研究の銘柄を選択", "ko": "팩터 연구 종목 선택"},
    "選擇要查看的 horizon": {"en": "Select horizon", "ja": "表示する horizon を選択", "ko": "볼 horizon 선택"},
    "股票間報酬相關性": {"en": "Stock return correlations", "ja": "銘柄間リターン相関", "ko": "종목 간 수익률 상관"},
    "原始標準化價格資料": {"en": "Raw normalized price data", "ja": "標準化済み価格データ", "ko": "정규화된 원시 가격 데이터"},
    "選擇圖表代號": {"en": "Select chart ticker", "ja": "チャート銘柄を選択", "ko": "차트 종목 선택"},
    "選擇歸因代號": {"en": "Select attribution ticker", "ja": "寄与度分析の銘柄を選択", "ko": "기여도 분석 종목 선택"},
    "選擇回測曲線代號": {"en": "Select backtest curve ticker", "ja": "バックテスト曲線の銘柄を選択", "ko": "백테스트 곡선 종목 선택"},
    "全部": {"en": "All", "ja": "すべて", "ko": "전체"},
    "代號": {"en": "Ticker", "ja": "銘柄", "ko": "종목"},
    "決策": {"en": "Decision", "ja": "判断", "ko": "결정"},
    "最新收盤": {"en": "Last close", "ja": "最新終値", "ko": "최근 종가"},
    "模型預估報酬%": {"en": "Model expected return %", "ja": "モデル予想リターン%", "ko": "모델 예상 수익률%"},
    "關係調整後報酬%": {"en": "Relationship-adjusted return %", "ja": "関係調整後リターン%", "ko": "관계 조정 수익률%"},
    "參考買進價": {"en": "Buy reference price", "ja": "買い参考価格", "ko": "매수 참고가"},
    "參考賣出價": {"en": "Sell reference price", "ja": "売り参考価格", "ko": "매도 참고가"},
    "參考停損價": {"en": "Stop-loss reference price", "ja": "損切り参考価格", "ko": "손절 참고가"},
    "Kelly 建議倉位": {"en": "Kelly suggested position", "ja": "Kelly 推奨ポジション", "ko": "Kelly 권장 비중"},
    "決策原因": {"en": "Decision reason", "ja": "判断理由", "ko": "결정 이유"},
    "Kelly 原因": {"en": "Kelly reason", "ja": "Kelly 理由", "ko": "Kelly 이유"},
    "風險單位%": {"en": "Risk unit %", "ja": "リスク単位%", "ko": "위험 단위%"},
    "距60日高點%": {"en": "From 60D high %", "ja": "60日高値からの距離%", "ko": "60일 고점 대비%"},
    "60日最大回撤%": {"en": "60D max drawdown %", "ja": "60日最大ドローダウン%", "ko": "60일 최대 낙폭%"},
    "同/反向關係壓力%": {"en": "Same/opposite relationship pressure %", "ja": "同/逆方向関係圧力%", "ko": "동/역방향 관계 압력%"},
    "模型": {"en": "Model", "ja": "モデル", "ko": "모델"},
    "偏多觀察": {"en": "Bullish watch", "ja": "強気監視", "ko": "상승 관찰"},
    "等待確認": {"en": "Wait for confirmation", "ja": "確認待ち", "ko": "확인 대기"},
    "減碼/避開": {"en": "Reduce / avoid", "ja": "縮小 / 回避", "ko": "축소 / 회피"},
    "🟢 偏多觀察": {"en": "🟢 Bullish watch", "ja": "🟢 強気監視", "ko": "🟢 상승 관찰"},
    "🟡 等待確認": {"en": "🟡 Wait for confirmation", "ja": "🟡 確認待ち", "ko": "🟡 확인 대기"},
    "預估優勢不夠明顯，先觀察，不急著追價。": {"en": "The estimated edge is not clear enough; observe first and avoid chasing price.", "ja": "推定優位性がまだ明確ではありません。まず観察し、追いかけ買いは避けます。", "ko": "추정 우위가 아직 뚜렷하지 않습니다. 먼저 관찰하고 추격 매수는 피합니다."},
    "🔴 減碼/避開": {"en": "🔴 Reduce / avoid", "ja": "🔴 縮小 / 回避", "ko": "🔴 축소 / 회피"},
    "時間出場": {"en": "Time exit", "ja": "時間で終了", "ko": "시간 청산"},
    "停損優先": {"en": "Stop-loss first", "ja": "損切り優先", "ko": "손절 우선"},
    "移動停損": {"en": "Trailing stop", "ja": "トレーリングストップ", "ko": "트레일링 스톱"},
    "time": {"en": "Time exit", "ja": "時間で終了", "ko": "시간 청산"},
    "stop_loss": {"en": "Stop-loss", "ja": "損切り", "ko": "손절"},
    "trailing_stop": {"en": "Trailing stop", "ja": "トレーリングストップ", "ko": "트레일링 스톱"},
    "因子輸入天數": {"en": "Factor input window", "ja": "ファクター入力日数", "ko": "팩터 입력 기간"},
    "比較預測天數 horizon": {"en": "Compare prediction horizons", "ja": "予測 horizon を比較", "ko": "예측 horizon 비교"},
    "漲跌分類門檻%": {"en": "Up/down classification threshold %", "ja": "上昇/下落分類しきい値%", "ko": "상승/하락 분류 임계값%"},
    "因子模型": {"en": "Factor model", "ja": "ファクターモデル", "ko": "팩터 모델"},
    "回測訓練視窗": {"en": "Backtest training window", "ja": "バックテスト学習ウィンドウ", "ko": "백테스트 학습 창"},
    "啟用持有天數 / 出場規則比較": {"en": "Enable holding-days / exit-rule comparison", "ja": "保有日数 / 出口ルール比較を有効化", "ko": "보유 기간 / 청산 규칙 비교 활성화"},
    "比較持有天數": {"en": "Compare holding days", "ja": "保有日数を比較", "ko": "보유 기간 비교"},
    "比較出場規則": {"en": "Compare exit rules", "ja": "出口ルールを比較", "ko": "청산 규칙 비교"},
    "移動停損幅度": {"en": "Trailing-stop distance", "ja": "トレーリングストップ幅", "ko": "트레일링 스톱 폭"},
    "回測只吃偏多觀察訊號": {"en": "Backtest only bullish-watch signals", "ja": "強気監視シグナルのみバックテスト", "ko": "상승 관찰 신호만 백테스트"},
    "上傳 CSV": {"en": "Upload CSV", "ja": "CSVをアップロード", "ko": "CSV 업로드"},
    "用於 ARIMA / 線性模型的預估 horizon。": {"en": "Forecast horizon used by ARIMA / linear models.", "ja": "ARIMA / 線形モデルで使う予測 horizon。", "ko": "ARIMA / 선형 모델에 사용하는 예측 horizon입니다."},
    "sliding window 的 X：使用過去 N 天 K線/KD/MACD/RSI 等因子。": {"en": "Sliding-window X: use the past N days of candlestick/KD/MACD/RSI factors.", "ja": "スライディングウィンドウの X：過去 N 日のローソク足/KD/MACD/RSI などを使用。", "ko": "슬라이딩 윈도우 X: 과거 N일의 캔들/KD/MACD/RSI 팩터를 사용합니다."},
    "一次比較未來 1/3/5/10 天漲跌；每個 horizon 會各自訓練模型與計算 SHAP/fallback 重要度。": {"en": "Compare future 1/3/5/10-day direction at once; each horizon trains its own model and SHAP/fallback importance.", "ja": "将来 1/3/5/10 日の上げ下げを一括比較します。各 horizon で個別にモデルと SHAP/fallback 重要度を計算します。", "ko": "미래 1/3/5/10일 방향을 한 번에 비교합니다. 각 horizon은 별도 모델과 SHAP/fallback 중요도를 계산합니다."},
    "forward return 高於此門檻才標為上漲，可降低微小雜訊。": {"en": "Only forward returns above this threshold count as up, reducing tiny-noise labels.", "ja": "forward return がこのしきい値を超えた場合のみ上昇とし、小さなノイズを減らします。", "ko": "forward return이 이 임계값보다 높을 때만 상승으로 표시해 작은 노이즈를 줄입니다."},
    "每次回測決策只看此前這段歷史資料。": {"en": "Each backtest decision only sees this much prior history.", "ja": "各バックテスト判断はこの期間分の過去データだけを参照します。", "ko": "각 백테스트 결정은 이 길이만큼의 이전 데이터만 봅니다."},
    "多策略比較會同時跑多組回測；需要比較時再開啟，避免首頁載入過慢。": {"en": "Runs multiple backtests at once; enable only when needed to keep the first render fast.", "ja": "複数のバックテストを同時に実行します。初期表示を速く保つため、必要な時だけ有効にしてください。", "ko": "여러 백테스트를 동시에 실행합니다. 첫 화면을 빠르게 유지하려면 필요할 때만 켜세요."},
    "回測會比較每種持有天數的結果。": {"en": "Backtest compares each selected holding period.", "ja": "選択した各保有日数の結果を比較します。", "ko": "선택한 각 보유 기간의 결과를 비교합니다."},
    "移動停損出場規則使用；例如 5% 代表從進場後高點回落 5% 出場。": {"en": "Used by trailing-stop exits; 5% means exit after a 5% drop from the post-entry high.", "ja": "トレーリングストップ出口で使用。5% はエントリー後高値から 5% 下落で終了を意味します。", "ko": "트레일링 스톱 청산에 사용합니다. 5%는 진입 후 고점에서 5% 하락하면 청산한다는 뜻입니다."},
    "關閉時會測試每個決策點的 long-only 結果；開啟時只測 BUY_WATCH。": {"en": "Off: test long-only results at every decision point. On: test only BUY_WATCH signals.", "ja": "オフ：各判断点の long-only 結果をテスト。オン：BUY_WATCH のみテスト。", "ko": "끄면 모든 결정 지점의 long-only 결과를 테스트하고, 켜면 BUY_WATCH만 테스트합니다."},
    "支援 date/ticker/open/high/low/close/volume 或中文欄位。": {"en": "Supports date/ticker/open/high/low/close/volume or Chinese columns.", "ja": "date/ticker/open/high/low/close/volume または中国語列に対応。", "ko": "date/ticker/open/high/low/close/volume 또는 중국어 컬럼을 지원합니다."},
    "請在左側上傳 CSV，或把資料來源切回 yfinance。": {"en": "Upload a CSV on the left, or switch the data source back to yfinance.", "ja": "左側で CSV をアップロードするか、データソースを yfinance に戻してください。", "ko": "왼쪽에서 CSV를 업로드하거나 데이터 소스를 yfinance로 다시 바꾸세요."},
    "資料量不足以產生決策報表；請拉長歷史區間或改用日 K。": {"en": "Not enough data to generate a decision report; extend the history range or use daily candles.", "ja": "判断レポートを生成するデータが不足しています。履歴期間を延ばすか日足を使用してください。", "ko": "결정 보고서를 만들 데이터가 부족합니다. 기간을 늘리거나 일봉을 사용하세요。"},
}


_TRANSLATIONS.update(
    {
        "參考買進價偏向保守掛價；參考賣出價取近期高點、波動門檻與預估價的較高者；停損價用近期波動估算；Kelly 是半 Kelly 且有上限，適合當倉位參考，不是必然下單比例。": {
            "en": "The buy reference is a conservative limit-price idea; the sell reference uses the higher of recent highs, volatility thresholds, and forecast price; stop-loss uses recent volatility; Kelly is half-Kelly with caps, useful as a position-size reference rather than an order instruction.",
            "ja": "買い参考値は保守的な指値の目安です。売り参考値は直近高値・変動率しきい値・予測価格の高い方を使います。損切りは直近変動率で見積もります。Kelly は上限付きの半 Kelly で、注文比率ではなくポジション参考値です。",
            "ko": "매수 참고가는 보수적인 지정가 아이디어입니다. 매도 참고가는 최근 고점, 변동성 임계값, 예측가 중 높은 값을 사용합니다. 손절가는 최근 변동성으로 추정합니다. Kelly는 상한이 있는 half-Kelly로, 실제 주문 비율이 아니라 포지션 참고값입니다.",
        },
        "決策：{action}": {"en": "Decision: {action}", "ja": "判断：{action}", "ko": "결정: {action}"},
        "參考買進：{price}": {"en": "Buy reference: {price}", "ja": "買い参考：{price}", "ko": "매수 참고: {price}"},
        "參考賣出：{price}": {"en": "Sell reference: {price}", "ja": "売り参考：{price}", "ko": "매도 참고: {price}"},
        "參考停損：{price}": {"en": "Stop-loss reference: {price}", "ja": "損切り参考：{price}", "ko": "손절 참고: {price}"},
        "每隔 horizon 天，只使用當下以前的資料重新產生決策報表，再用下一段行情驗證。這不是實盤成交模擬，先用來檢查策略方向、停損與回撤是否合理。": {
            "en": "Every horizon days, the backtest rebuilds the decision report using only data available up to that point, then validates it on the next price segment. This is not a live execution simulator; it is for checking whether strategy direction, stop-loss behavior, and drawdown are reasonable.",
            "ja": "horizon 日ごとに、その時点以前のデータだけで判断レポートを再生成し、次の価格区間で検証します。これは実取引の約定シミュレーションではなく、戦略方向・損切り・ドローダウンが妥当かを確認するものです。",
            "ko": "horizon일마다 해당 시점 이전 데이터만 사용해 결정 보고서를 다시 만들고 다음 가격 구간에서 검증합니다. 실거래 체결 시뮬레이터가 아니라 전략 방향, 손절, 낙폭이 합리적인지 확인하는 용도입니다.",
        },
        "最佳累積報酬": {"en": "Best cumulative return", "ja": "最高累積リターン", "ko": "최고 누적 수익률"},
        "多策略比較目前未啟用。請在左側打開『啟用持有天數 / 出場規則比較』後，選擇要比較的持有天數與出場規則。": {
            "en": "Multi-strategy comparison is currently disabled. Turn on ‘Enable holding-days / exit-rule comparison’ in the sidebar, then choose the holding days and exit rules to compare.",
            "ja": "複数戦略比較は現在無効です。左側で「保有日数 / 出口ルール比較を有効化」をオンにし、比較する保有日数と出口ルールを選択してください。",
            "ko": "다중 전략 비교가 현재 꺼져 있습니다. 왼쪽에서 ‘보유 기간 / 청산 규칙 비교 활성화’를 켠 뒤 비교할 보유 기간과 청산 규칙을 선택하세요.",
        },
        "#### 目前決策天數的逐筆回測": {"en": "#### Trade-by-trade backtest for the current decision horizon", "ja": "#### 現在の判断日数に対する取引別バックテスト", "ko": "#### 현재 결정 기간의 거래별 백테스트"},
        "因子研究：過去 N 天因子 → 未來多 horizon 漲跌": {"en": "Factor research: past N-day factors → future multi-horizon direction", "ja": "ファクター研究：過去 N 日ファクター → 将来の複数 horizon 方向", "ko": "팩터 연구: 과거 N일 팩터 → 미래 다중 horizon 방향"},
        "用 sliding window 收集歷史樣本：X 是過去 N 天 K線、KD、MACD、RSI、量能、波動與回撤等因子；y 是未來 1/3/5/10 天 forward return 是否高於漲跌門檻。每個 horizon 獨立訓練與歸因；這是模型歸因與統計關聯，不是因果證明。": {
            "en": "Historical samples are collected with sliding windows: X contains past N-day candlestick, KD, MACD, RSI, volume, volatility, and drawdown factors; y is whether the future 1/3/5/10-day forward return exceeds the up/down threshold. Each horizon is trained and attributed independently. This is model attribution and statistical association, not causal proof.",
            "ja": "スライディングウィンドウで履歴サンプルを収集します。X は過去 N 日のローソク足、KD、MACD、RSI、出来高、変動率、ドローダウンなどのファクター、y は将来 1/3/5/10 日の forward return が上下しきい値を超えるかどうかです。各 horizon は独立して学習・寄与度分析されます。これはモデル寄与度と統計的関連であり、因果証明ではありません。",
            "ko": "슬라이딩 윈도우로 과거 샘플을 수집합니다. X는 과거 N일 캔들, KD, MACD, RSI, 거래량, 변동성, 낙폭 팩터이고 y는 미래 1/3/5/10일 forward return이 상승/하락 임계값을 넘는지 여부입니다. 각 horizon은 독립적으로 학습 및 기여도 분석됩니다. 이는 모델 기여도와 통계적 연관이지 인과 증명이 아닙니다.",
        },
        "目前設定：過去 {window} 天因子 → 比較未來 {horizons} 天漲跌；上漲門檻 {threshold:.1f}%；模型 {model}。": {"en": "Current setting: past {window}-day factors → compare future {horizons}-day direction; up threshold {threshold:.1f}%; model {model}.", "ja": "現在の設定：過去 {window} 日ファクター → 将来 {horizons} 日方向を比較；上昇しきい値 {threshold:.1f}%；モデル {model}。", "ko": "현재 설정: 과거 {window}일 팩터 → 미래 {horizons}일 방향 비교; 상승 임계값 {threshold:.1f}%; 모델 {model}."},
        "尚未執行因子研究。請按『執行多 horizon 因子研究』；建議先用 1y 以上日 K，樣本會比較穩。": {"en": "Factor research has not been run yet. Press ‘Run multi-horizon factor research’. Daily candles with at least 1y of history are recommended for more stable samples.", "ja": "ファクター研究はまだ実行されていません。「複数 horizon ファクター研究を実行」を押してください。安定したサンプルには 1y 以上の日足を推奨します。", "ko": "팩터 연구가 아직 실행되지 않았습니다. ‘다중 horizon 팩터 연구 실행’을 누르세요. 더 안정적인 샘플을 위해 1y 이상 일봉을 권장합니다."},
        "顏色越綠代表該股票在該 horizon 的指標越高；AUC 接近 50% 代表模型排序能力接近隨機。": {"en": "Greener means the ticker scores higher at that horizon; AUC near 50% means the model ranking ability is close to random.", "ja": "緑が濃いほど、その銘柄のその horizon における指標が高いことを示します。AUC が 50% に近い場合、モデルの順位付け能力はランダムに近いです。", "ko": "초록색일수록 해당 종목이 해당 horizon에서 더 높은 지표를 보입니다. AUC가 50%에 가까우면 모델의 순위화 능력이 무작위에 가깝다는 뜻입니다."},
        "最佳 horizon": {"en": "Best horizon", "ja": "最良 horizon", "ko": "최적 horizon"},
        "測試準確率": {"en": "Test accuracy", "ja": "テスト精度", "ko": "테스트 정확도"},
        "歷史上漲率": {"en": "Historical up-rate", "ja": "過去上昇率", "ko": "과거 상승률"},
        "目前歸因方法：{method}": {"en": "Attribution method: {method}", "ja": "寄与度分析方法：{method}", "ko": "기여도 방법: {method}"},
        "查看逐筆交易": {"en": "View individual trades", "ja": "個別取引を見る", "ko": "개별 거래 보기"},
        "累積報酬%": {"en": "Cumulative return %", "ja": "累積リターン%", "ko": "누적 수익률%"},
        "日期": {"en": "Date", "ja": "日付", "ko": "날짜"},
    "預測天數": {"en": "Prediction horizon", "ja": "予測日数", "ko": "예측 기간"},
    "因子": {"en": "Factor", "ja": "ファクター", "ko": "팩터"},
    "重要度": {"en": "Importance", "ja": "重要度", "ko": "중요도"},
    "方向貢獻": {"en": "Signed contribution", "ja": "方向付き寄与", "ko": "방향 기여도"},
    "方向": {"en": "Direction", "ja": "方向", "ko": "방향"},
    "方法": {"en": "Method", "ja": "方法", "ko": "방법"},
    "正向": {"en": "Positive", "ja": "プラス", "ko": "양의 방향"},
    "負向": {"en": "Negative", "ja": "マイナス", "ko": "음의 방향"},
        "正在建立 sliding-window 樣本並訓練多 horizon 因子模型…": {"en": "Building sliding-window samples and training multi-horizon factor models…", "ja": "スライディングウィンドウのサンプルを構築し、複数 horizon ファクターモデルを学習しています…", "ko": "슬라이딩 윈도우 샘플을 만들고 다중 horizon 팩터 모델을 학습 중입니다…"},
        "按下後才針對每個 horizon 建立 sliding-window dataset、訓練分類模型並計算 SHAP/fallback、相關性與分組勝率。": {"en": "After pressing, the app builds a sliding-window dataset for each horizon, trains a classifier, and computes SHAP/fallback attribution, correlations, and grouped win rates.", "ja": "押すと、各 horizon ごとにスライディングウィンドウ dataset を作成し、分類モデルを学習して SHAP/fallback、相関、グループ別勝率を計算します。", "ko": "버튼을 누르면 각 horizon별 슬라이딩 윈도우 dataset을 만들고 분류 모델을 학습한 뒤 SHAP/fallback 기여도, 상관관계, 구간별 승률을 계산합니다."},
    }
)


_TRANSLATIONS.update(
    {
        "今日機會雷達": {"en": "Today’s Opportunity Radar", "ja": "本日の機会レーダー", "ko": "오늘의 기회 레이더"},
        "把決策、Kelly、回測勝率與買賣價位濃縮成卡片；先看顏色與原因，再進表格細查。": {"en": "Condenses decisions, Kelly sizing, backtest win rate, and trading levels into cards. Read the color and reason first, then inspect the table.", "ja": "判断、Kelly、バックテスト勝率、売買水準をカードに集約します。まず色と理由を見てから表を確認してください。", "ko": "결정, Kelly 비중, 백테스트 승률, 매매 가격대를 카드로 요약합니다. 먼저 색상과 이유를 보고 표를 확인하세요."},
        "調整報酬": {"en": "Adj. return", "ja": "調整後リターン", "ko": "조정 수익률"},
        "回測勝率": {"en": "Backtest win rate", "ja": "バックテスト勝率", "ko": "백테스트 승률"},
        "回測報酬": {"en": "Backtest return", "ja": "バックテストリターン", "ko": "백테스트 수익률"},
        "買進": {"en": "Buy", "ja": "買い", "ko": "매수"},
        "停損": {"en": "Stop", "ja": "損切り", "ko": "손절"},
        "策略健檢卡": {"en": "Strategy Health Cards", "ja": "戦略ヘルスチェックカード", "ko": "전략 상태 점검 카드"},
        "把回測勝率、最大回撤、Profit Factor、樣本數與 Kelly 狀態轉成可讀警訊。": {"en": "Turns backtest win rate, max drawdown, Profit Factor, sample size, and Kelly state into readable warnings.", "ja": "バックテスト勝率、最大ドローダウン、Profit Factor、サンプル数、Kelly 状態を読みやすい警告に変換します。", "ko": "백테스트 승률, 최대 낙폭, Profit Factor, 샘플 수, Kelly 상태를 읽기 쉬운 경고로 바꿉니다."},
        "樣本數不足": {"en": "Insufficient sample size", "ja": "サンプル不足", "ko": "샘플 수 부족"},
        "最大回撤偏高": {"en": "High max drawdown", "ja": "最大ドローダウン高め", "ko": "최대 낙폭 높음"},
        "Profit Factor 低於 1": {"en": "Profit Factor below 1", "ja": "Profit Factor が 1 未満", "ko": "Profit Factor 1 미만"},
        "勝率偏低": {"en": "Low win rate", "ja": "勝率が低い", "ko": "승률 낮음"},
        "累積報酬為負": {"en": "Negative cumulative return", "ja": "累積リターンがマイナス", "ko": "누적 수익률 음수"},
        "策略健檢通過": {"en": "Strategy health passed", "ja": "戦略ヘルスチェック通過", "ko": "전략 점검 통과"},
        "樣本數不足：{ticker} 目前只有 {trades} 筆回測交易，勝率與報酬只能當方向參考。": {"en": "Insufficient sample size: {ticker} has only {trades} backtest trades, so win rate and return should be directional references only.", "ja": "サンプル不足：{ticker} はバックテスト取引が {trades} 件のみです。勝率とリターンは方向参考に留めてください。", "ko": "샘플 수 부족: {ticker}의 백테스트 거래가 {trades}건뿐이므로 승률과 수익률은 방향 참고로만 보세요."},
        "最大回撤偏高：{ticker} 最大回撤 {max_drawdown_pct:.1f}%，需要降低倉位、提高停損或改用更保守出場規則。": {"en": "High max drawdown: {ticker} max drawdown is {max_drawdown_pct:.1f}%; reduce position size, tighten stop-loss, or use a more conservative exit rule.", "ja": "最大ドローダウン高め：{ticker} の最大ドローダウンは {max_drawdown_pct:.1f}% です。ポジションを下げる、損切りを強める、より保守的な出口ルールを検討してください。", "ko": "최대 낙폭 높음: {ticker}의 최대 낙폭은 {max_drawdown_pct:.1f}%입니다. 비중을 줄이거나 손절을 강화하거나 더 보수적인 청산 규칙을 쓰세요."},
        "Profit Factor 低於 1：{ticker} 獲利交易不足以覆蓋虧損交易，暫不適合只靠此策略進場。": {"en": "Profit Factor below 1: {ticker} winning trades do not cover losing trades; this strategy alone is not suitable for entries yet.", "ja": "Profit Factor が 1 未満：{ticker} は利益取引が損失取引を補えていません。この戦略だけでのエントリーはまだ適しません。", "ko": "Profit Factor 1 미만: {ticker}의 이익 거래가 손실 거래를 덮지 못합니다. 아직 이 전략만으로 진입하기는 부적절합니다."},
        "勝率偏低：{ticker} 回測勝率 {win_rate_pct:.1f}%，需搭配更強確認訊號。": {"en": "Low win rate: {ticker} backtest win rate is {win_rate_pct:.1f}%; stronger confirmation signals are needed.", "ja": "勝率が低い：{ticker} のバックテスト勝率は {win_rate_pct:.1f}% です。より強い確認シグナルが必要です。", "ko": "승률 낮음: {ticker}의 백테스트 승률은 {win_rate_pct:.1f}%입니다. 더 강한 확인 신호가 필요합니다."},
        "累積報酬為負：{ticker} 在目前參數下累積報酬為 {cumulative_return_pct:.1f}%，代表策略方向暫時不佳。": {"en": "Negative cumulative return: {ticker} cumulative return is {cumulative_return_pct:.1f}% under current parameters, suggesting the strategy direction is currently weak.", "ja": "累積リターンがマイナス：{ticker} は現在パラメータで {cumulative_return_pct:.1f}% です。戦略方向は一時的に弱い可能性があります。", "ko": "누적 수익률 음수: 현재 파라미터에서 {ticker}의 누적 수익률은 {cumulative_return_pct:.1f}%로, 전략 방향이 약함을 시사합니다."},
        "等待確認：{ticker} Kelly 為 0 且決策為等待確認，代表模型優勢尚未大過近期風險。": {"en": "Wait for confirmation: {ticker} Kelly is 0 and the decision is neutral, meaning the model edge is not larger than recent risk yet.", "ja": "確認待ち：{ticker} は Kelly が 0 で判断も中立です。モデル優位性がまだ直近リスクを上回っていません。", "ko": "확인 대기: {ticker}의 Kelly가 0이고 결정도 중립입니다. 모델 우위가 아직 최근 위험보다 크지 않습니다."},
        "策略健檢通過：目前回測沒有明顯樣本不足、回撤過高或 Profit Factor 過低警訊。": {"en": "Strategy health passed: no obvious low sample size, excessive drawdown, or weak Profit Factor warning in the current backtest.", "ja": "戦略ヘルスチェック通過：現在のバックテストでは、サンプル不足、過大ドローダウン、Profit Factor 低下の明確な警告はありません。", "ko": "전략 점검 통과: 현재 백테스트에서 샘플 부족, 과도한 낙폭, 낮은 Profit Factor 경고가 뚜렷하지 않습니다."},
        "參考買進": {"en": "Buy reference", "ja": "買い参考", "ko": "매수 참고"},
        "參考賣出": {"en": "Sell reference", "ja": "売り参考", "ko": "매도 참고"},
        "參考停損": {"en": "Stop-loss reference", "ja": "損切り参考", "ko": "손절 참고"},
        "回測進場 B": {"en": "Backtest entry B", "ja": "バックテスト買い B", "ko": "백테스트 진입 B"},
        "回測出場 S": {"en": "Backtest exit S", "ja": "バックテスト売り S", "ko": "백테스트 청산 S"},
    }
)


def normalize_language(value: str | None) -> str:
    if not value:
        return "zh"
    if value in LANGUAGES:
        return value
    return _LANGUAGE_ALIASES.get(value, "zh")


def t(text: Any, lang: str = "zh", **kwargs: Any) -> str:
    """Translate a UI string. Unknown strings fall back to the original copy."""
    if not isinstance(text, str):
        text = str(text)
    code = normalize_language(lang)
    translated = text if code == "zh" else _TRANSLATIONS.get(text, {}).get(code, text)
    if translated == text and code != "zh":
        heading_match = re.match(r"^(#{1,6}\s+)(.+)$", text)
        if heading_match:
            prefix, body = heading_match.groups()
            translated_body = _TRANSLATIONS.get(body, {}).get(code, body)
            translated = prefix + translated_body
    if kwargs:
        try:
            return translated.format(**kwargs)
        except Exception:
            return translated
    return translated


def translate_mapping(mapping: Mapping[str, Any], lang: str) -> dict[str, Any]:
    return {key: t(value, lang) if isinstance(value, str) else value for key, value in mapping.items()}


_REASON_PATTERNS: list[tuple[re.Pattern[str], dict[str, str]]] = [
    (
        re.compile(r"等待確認：預估報酬 ([+-]?\d+(?:\.\d+)?)% 仍在 ±(\d+(?:\.\d+)?)% 門檻內；代表模型優勢尚未明顯大過近期波動與回撤風險。"),
        {
            "en": "Wait for confirmation: expected return {0}% is still within the ±{1}% threshold; the model edge is not clearly larger than recent volatility and drawdown risk.",
            "ja": "確認待ち：予想リターン {0}% はまだ ±{1}% のしきい値内です。モデルの優位性が直近の変動率とドローダウンリスクを明確に上回っていません。",
            "ko": "확인 대기: 예상 수익률 {0}%가 아직 ±{1}% 임계값 안에 있습니다. 모델 우위가 최근 변동성과 낙폭 위험보다 충분히 크지 않습니다.",
        },
    ),
    (
        re.compile(r"偏多觀察：預估報酬 ([+-]?\d+(?:\.\d+)?)% 高於買進門檻 (\d+(?:\.\d+)?)%；門檻已納入波動與回撤懲罰 (\d+(?:\.\d+)?)%。"),
        {
            "en": "Bullish watch: expected return {0}% is above the buy threshold {1}%; the threshold includes volatility and drawdown penalty {2}%.",
            "ja": "強気監視：予想リターン {0}% は買いしきい値 {1}% を上回っています。しきい値には変動率とドローダウンペナルティ {2}% が含まれます。",
            "ko": "상승 관찰: 예상 수익률 {0}%가 매수 임계값 {1}%보다 높습니다. 임계값에는 변동성과 낙폭 페널티 {2}%가 반영됩니다.",
        },
    ),
    (
        re.compile(r"減碼/避開：預估報酬 ([+-]?\d+(?:\.\d+)?)% 低於負向門檻 -(\d+(?:\.\d+)?)%；風險報酬不對稱。"),
        {
            "en": "Reduce / avoid: expected return {0}% is below the negative threshold -{1}%; risk and reward are asymmetric.",
            "ja": "縮小 / 回避：予想リターン {0}% は負のしきい値 -{1}% を下回っています。リスクとリターンが非対称です。",
            "ko": "축소 / 회피: 예상 수익률 {0}%가 음의 임계값 -{1}%보다 낮습니다. 위험 대비 보상이 비대칭입니다.",
        },
    ),
    (
        re.compile(r"Kelly 為 0：預估報酬 ([+-]?\d+(?:\.\d+)?)%，風險單位 (\d+(?:\.\d+)?)%，在保守勝率假設 (\d+)% 下，約需大於 (\d+(?:\.\d+)?)% 的優勢才值得配置。"),
        {
            "en": "Kelly is 0: expected return {0}%, risk unit {1}%, and under a conservative win-rate assumption {2}%, the edge needs to be greater than about {3}% before allocating.",
            "ja": "Kelly は 0：予想リターン {0}%、リスク単位 {1}% です。保守的な勝率仮定 {2}% では、配分するには約 {3}% を超える優位性が必要です。",
            "ko": "Kelly는 0입니다: 예상 수익률 {0}%, 위험 단위 {1}%이며, 보수적 승률 가정 {2}%에서는 약 {3}%보다 큰 우위가 있어야 배분할 만합니다.",
        },
    ),
    (
        re.compile(r"Kelly (\d+(?:\.\d+)?)%：預估報酬 ([+-]?\d+(?:\.\d+)?)% 相對風險單位 (\d+(?:\.\d+)?)% 已有正優勢，但仍已套用半 Kelly 保守折減。"),
        {
            "en": "Kelly {0}%: expected return {1}% has a positive edge versus risk unit {2}%, with conservative half-Kelly reduction applied.",
            "ja": "Kelly {0}%：予想リターン {1}% はリスク単位 {2}% に対して正の優位性がありますが、保守的な半 Kelly に減額済みです。",
            "ko": "Kelly {0}%: 예상 수익률 {1}%는 위험 단위 {2}% 대비 양의 우위가 있으나 보수적 half-Kelly가 적용되었습니다.",
        },
    ),
    (
        re.compile(r"Kelly 為 0：缺少足夠或有效的預估報酬 / 風險資料。"),
        {
            "en": "Kelly is 0: there is not enough valid expected-return / risk data.",
            "ja": "Kelly は 0：十分または有効な予想リターン / リスクデータがありません。",
            "ko": "Kelly는 0입니다: 충분하거나 유효한 예상 수익률 / 위험 데이터가 없습니다.",
        },
    ),
]


def translate_text_value(value: Any, lang: str) -> Any:
    if not isinstance(value, str):
        return value
    code = normalize_language(lang)
    if code == "zh":
        return value
    direct = t(value, code)
    if direct != value:
        return direct
    for pattern, templates in _REASON_PATTERNS:
        match = pattern.fullmatch(value)
        if match:
            return templates.get(code, value).format(*match.groups())
    return value


def translate_dataframe_values(df: pd.DataFrame, lang: str) -> pd.DataFrame:
    if df.empty or normalize_language(lang) == "zh":
        return df
    out = df.copy()
    object_cols = out.select_dtypes(include=["object", "string"]).columns
    for col in object_cols:
        out[col] = out[col].map(lambda value: translate_text_value(value, lang))
    return out


def translate_options(options: Iterable[Any], lang: str) -> list[Any]:
    return [translate_text_value(option, lang) for option in options]


def translate_dataframe_columns(df: pd.DataFrame, lang: str) -> pd.DataFrame:
    if df.empty or normalize_language(lang) == "zh":
        return df
    return df.rename(columns={col: t(str(col), lang) for col in df.columns})


def localize_dataframe_for_display(df: pd.DataFrame, columns: Iterable[str] | None, lang: str) -> pd.DataFrame:
    """Select canonical display columns first, then translate values and headers.

    Streamlit tables often use Traditional Chinese display names as the app's
    canonical UI schema. If a table is translated before selecting columns,
    later code like df[["代號", "預測天數"]] fails in English/Japanese/Korean
    because those headers have already become Ticker/Prediction horizon/etc.
    This helper keeps the safe order in one place:

    1. select existing canonical columns while silently ignoring optional misses;
    2. translate cell values such as decision labels/reason strings;
    3. translate column headers for the active UI language.
    """
    out = df.copy()
    if columns is not None:
        existing = [column for column in columns if column in out.columns]
        out = out[existing]
    out = translate_dataframe_values(out, lang)
    return translate_dataframe_columns(out, lang)

_PHASE2_TRANSLATIONS = {
    "##### Watchlist": {"en": "##### Watchlist", "ja": "##### ウォッチリスト", "ko": "##### 관심 목록"},
    "##### Smart Tuning Lite": {"en": "##### Smart Tuning Lite", "ja": "##### Smart Tuning Lite", "ko": "##### Smart Tuning Lite"},
    "Smart Tuning 持有天數": {"en": "Smart Tuning holding days", "ja": "Smart Tuning 保有日数", "ko": "Smart Tuning 보유 기간"},
    "Smart Tuning 風險寬度%": {"en": "Smart Tuning risk width %", "ja": "Smart Tuning リスク幅%", "ko": "Smart Tuning 위험 폭%"},
    "按下 Smart Tuning 按鈕後才會掃描這些持有天數。": {"en": "These holding periods are scanned only after pressing the Smart Tuning button.", "ja": "Smart Tuning ボタンを押した後に、これらの保有日数をスキャンします。", "ko": "Smart Tuning 버튼을 누른 뒤 이 보유 기간을 스캔합니다."},
    "掃描停損 / 移動停損風險寬度；數值越大越寬鬆。": {"en": "Scan stop-loss / trailing-stop risk widths; larger values are looser.", "ja": "損切り / トレーリングストップのリスク幅をスキャンします。値が大きいほど緩くなります。", "ko": "손절 / 트레일링 스톱 위험 폭을 스캔합니다. 값이 클수록 더 느슨합니다."},
    "市場熱力圖": {"en": "Market heatmap", "ja": "市場ヒートマップ", "ko": "시장 히트맵"},
    "用格子大小呈現成交量 × 價格活躍度，用顏色呈現近 5 日報酬；適合快速找出目前最熱或最弱的觀察標的。": {"en": "Tile size shows volume × price activity, while color shows 5-day return; useful for spotting the hottest or weakest watchlist names quickly.", "ja": "タイルサイズは出来高×価格の活発度、色は直近5日リターンを示します。最も強い/弱い監視銘柄を素早く探すのに役立ちます。", "ko": "타일 크기는 거래량 × 가격 활발도를, 색상은 최근 5일 수익률을 나타냅니다. 가장 뜨겁거나 약한 관심 종목을 빠르게 찾는 데 유용합니다."},
    "5日報酬%": {"en": "5D return %", "ja": "5日リターン%", "ko": "5일 수익률%"},
    "Smart Tuning Lite": {"en": "Smart Tuning Lite", "ja": "Smart Tuning Lite", "ko": "Smart Tuning Lite"},
    "掃描持有天數、出場規則與風險寬度，依累積報酬、勝率、Profit Factor、最大回撤與停損率產生綜合分數。": {"en": "Scans holding days, exit rules, and risk widths, then scores them using cumulative return, win rate, Profit Factor, max drawdown, and stop-loss hit rate.", "ja": "保有日数、出口ルール、リスク幅をスキャンし、累積リターン、勝率、Profit Factor、最大ドローダウン、損切り率で総合スコア化します。", "ko": "보유 기간, 청산 규칙, 위험 폭을 스캔한 뒤 누적 수익률, 승률, Profit Factor, 최대 낙폭, 손절 적중률로 종합 점수를 계산합니다."},
    "執行 Smart Tuning Lite": {"en": "Run Smart Tuning Lite", "ja": "Smart Tuning Lite を実行", "ko": "Smart Tuning Lite 실행"},
    "按下後才執行參數掃描；會比一般回測多跑數十組情境。": {"en": "Runs the parameter scan only after clicking; it evaluates dozens more scenarios than the normal backtest.", "ja": "クリック後にのみパラメータスキャンを実行します。通常のバックテストより数十件多いシナリオを評価します。", "ko": "클릭한 뒤에만 파라미터 스캔을 실행합니다. 일반 백테스트보다 수십 개 더 많은 시나리오를 평가합니다."},
    "正在執行 Smart Tuning Lite 參數掃描…": {"en": "Running Smart Tuning Lite parameter scan…", "ja": "Smart Tuning Lite パラメータスキャンを実行中…", "ko": "Smart Tuning Lite 파라미터 스캔 실행 중…"},
    "尚未執行 Smart Tuning Lite。請按上方按鈕比較持有天數、出場規則與風險寬度。": {"en": "Smart Tuning Lite has not run yet. Press the button above to compare holding days, exit rules, and risk widths.", "ja": "Smart Tuning Lite はまだ実行されていません。上のボタンで保有日数、出口ルール、リスク幅を比較してください。", "ko": "Smart Tuning Lite가 아직 실행되지 않았습니다. 위 버튼을 눌러 보유 기간, 청산 규칙, 위험 폭을 비교하세요."},
    "目前顯示的是上一次 Smart Tuning 結果；sidebar 資料或參數已改變。若要更新，請再按一次。": {"en": "Showing the previous Smart Tuning result; sidebar data or parameters changed. Press again to update.", "ja": "前回の Smart Tuning 結果を表示しています。sidebar のデータまたはパラメータが変更されました。更新するには再度押してください。", "ko": "이전 Smart Tuning 결과를 표시 중입니다. sidebar 데이터 또는 파라미터가 변경되었습니다. 업데이트하려면 다시 누르세요."},
    "下載 Smart Tuning CSV": {"en": "Download Smart Tuning CSV", "ja": "Smart Tuning CSV をダウンロード", "ko": "Smart Tuning CSV 다운로드"},
    "排名": {"en": "Rank", "ja": "順位", "ko": "순위"},
    "情境": {"en": "Scenario", "ja": "シナリオ", "ko": "시나리오"},
    "風險寬度%": {"en": "Risk width %", "ja": "リスク幅%", "ko": "위험 폭%"},
    "綜合分數": {"en": "Composite score", "ja": "総合スコア", "ko": "종합 점수"},
}
_TRANSLATIONS.update(_PHASE2_TRANSLATIONS)

