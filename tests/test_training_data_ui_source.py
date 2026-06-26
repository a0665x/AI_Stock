from pathlib import Path

APP = Path("src/ai_stock/app.py")


def test_training_data_center_ui_exists_and_uses_plain_language() -> None:
    source = APP.read_text()
    assert "Training Data Studio：分析結果數據" in source
    assert "分析結果數據（Training Data）" in source
    assert "預測幾天後" in source
    assert "等待確認" in source
    assert "不是沒有模型" in source
    assert "Training Data" in source
    assert "SMC 欄位也會一起排序" in source
    assert "產生 Training Data" in source
    assert "欄位字典：Training Data 怎麼看？" in source
    assert "target_available_Nd" in source
    assert "不是已訓練完成的 AI 模型" in source
    assert "不會拖慢首頁載入" in source
    assert "下載 Training Data CSV" in source


def test_training_data_center_wires_cached_builder() -> None:
    source = APP.read_text()
    assert "from ai_stock.training_data import build_training_dataset, compute_top_training_features" in source
    assert "def _cached_training_dataset" in source
    assert "build_training_dataset(prices, forward_days=forward_days" in source
    assert "compute_top_training_features(dataset" in source
