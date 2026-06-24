from pathlib import Path


def test_app_connects_local_portfolio_to_sidebar_and_order_tab() -> None:
    app = Path("src/ai_stock/app.py").read_text(encoding="utf-8")

    assert "load_local_portfolio" in app
    assert "default_ticker_text" in app
    assert "持倉下單計畫" in app
    assert "build_portfolio_order_plan" in app
    assert "_humanize_portfolio_order_plan" in app


def test_gitignore_excludes_private_portfolio_files() -> None:
    path = Path(".gitignore")
    if not path.exists():
        # Docker image only copies runtime code/tests; local repo hygiene is tested outside the image.
        return
    gitignore = path.read_text(encoding="utf-8")

    assert "my_stocks.json" in gitignore
    assert "my_sotcks.json" in gitignore
