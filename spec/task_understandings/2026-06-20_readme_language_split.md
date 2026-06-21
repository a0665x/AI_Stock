# README language split for GitHub repo

## Goal
Prepare the repository landing page for public GitHub visitors by making English the default README while keeping a Traditional Chinese guide available as a separate file.

## Changes
- `README.md` is now the default English GitHub landing page.
- `README-en.md` is a standalone English copy for explicit language linking.
- `README-zh.md` is the Traditional Chinese guide.
- README language navigation uses a simple GitHub-compatible HTML block:
  - English
  - 繁體中文
- The UI screenshot gallery remains in the README using horizontal-scroll HTML/CSS. If GitHub or another renderer strips some inline CSS, the screenshots still render as normal images.

## Notes
- The Web UI itself still supports Traditional Chinese, English, Japanese, and Korean through `src/ai_stock/i18n.py`.
- Repository documentation currently provides English and Traditional Chinese README files; English is the default for international users.
- Do not include GitHub tokens, `.env`, runtime cache, Docker runtime data, or agent traces in the repository. `.gitignore` already excludes these categories.

## Verification
- Confirmed README files exist:
  - `README.md`
  - `README-en.md`
  - `README-zh.md`
- Confirmed screenshot links still point to `docs/images/*.png`.
