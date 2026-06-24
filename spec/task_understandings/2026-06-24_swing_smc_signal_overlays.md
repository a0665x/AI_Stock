# 2026-06-24 Swing chart SMC signal overlays

## Request
Add more swing-trading / SMC-style visual signals to the next-day order technical chart:

- Fair Value Gap (FVG)
- Inverse FVG (IFVG)
- Engulfing candles
- Swing High / Swing Low
- Swing Failure Pattern (SFP)
- Market Structure
- Structure Break / BOS

## Implementation
Updated `src/ai_stock/swing_order_chart.py`:

- `detect_swing_structure_signals()` wraps the shared Trade Vision market-structure engine so the order chart and Trade Vision Center use consistent swing/BOS/ChoCH semantics.
- `detect_fvg_ifvg_zones()` detects three-candle bullish/bearish fair-value gaps and marks invalidated zones as IFVG when later closes break through the far side.
- `detect_sfp_events()` detects sweep-and-close-back-inside swing failure patterns against prior swing highs/lows.
- `build_swing_order_technical_chart()` now overlays:
  - FVG / IFVG zones as translucent rectangles and markers
  - Swing High / Swing Low markers
  - BOS / ChoCH event markers
  - SFP markers
  - Existing engulfing / doji / hammer / strong-body candle labels

## Interpretation
These overlays are visual evidence for next-day order planning, not automatic trade commands:

- FVG shows imbalance zones that price may revisit.
- IFVG shows a failed imbalance that may role-flip into resistance/support.
- Engulfing candles help confirm buyer/seller control near an order level.
- Swing highs/lows define structure reference points.
- SFP marks likely stop sweeps / false breakouts that may reverse.
- BOS/ChoCH marks continuation or direction change.

## Verification
- Added regression coverage in `tests/test_swing_order_chart.py`.
- Host test suite: `62 passed`.
- Compile check: `python -m compileall src` passed.
