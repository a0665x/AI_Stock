# 2026-06-20 Web UI i18n and GitHub hygiene

## 使用者需求
- Web UI 文字與資訊切分成中 / 英 / 日 / 韓，多國語言右上角切換。
- 建立 `.gitignore`，避免上傳 codex / agent / 本機環境 / token / cache 線索。
- 將 `tutor_guide.md` 放入 `spec/`。
- 重新整理 README，讓 repo 使用者看得懂啟動與操作流程。
- 不代為 push；只提供使用者剩餘 git 指令。

## 本次修改
- 新增 `src/ai_stock/i18n.py`：語言 registry、翻譯函式、dataframe 欄位翻譯 helper。
- `src/ai_stock/app.py`：右上角新增語言選擇；安裝 Streamlit 顯示文字 wrapper，讓 title/header/markdown/info/button/tabs/metric 等主要 UI 字串依語言切換；報表欄位也支援翻譯。
- 新增 `.gitignore`：排除 `.venv/`、runtime/cache/log、secrets/tokens、`.codex/`、`.claude/`、`.cursor/`、`.hermes/`、AGENTS.md、CLAUDE.md、transcript/session 等本機 agent 痕跡。
- 將根目錄 `tutor_guide.md` 移到 `spec/tutor_guide.md`。
- 重寫 `README.md`：功能、Docker 快速啟動、UI 操作、快取、本機開發、GitHub push 指令。
- 更新 spec 入口文件。
- 新增 `tests/test_i18n.py`。

## 注意
- i18n 採用「繁中原文作 key」的字典策略；未知字串會 fallback 原文，不影響功能。
- 不翻譯底層 dataframe/model 欄位，只翻譯顯示層與人類可讀欄位，避免破壞計算邏輯。
