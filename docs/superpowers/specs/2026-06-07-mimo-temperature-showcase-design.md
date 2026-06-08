# MiMo Temperature Experiment Showcase

## Goal

Add the completed MiMo generation experiment to the interview showcase without
altering the historical RAGAS iteration chart.

## Placement

Insert a new section directly after the existing RAGAS iteration section. Keep
the current editorial luxury visual language: dark ink, warm ivory, restrained
gold accents, sharp borders, and oversized numeric typography.

## Content

- Compare T00, T02, T03, and Thinking, plus the later D4P Frozen strict
  generation-model control.
- Show Faithfulness, Answer Relevancy, Context Precision, and the three-metric
  mean for every group.
- Highlight T02 as the recommended production setting while showing D4P Frozen
  as the highest-Faithfulness control.
- State that T00 leads Answer Relevancy and Context Precision, while T02 wins
  Faithfulness and the overall mean.
- State that Thinking is slower and does not outperform T02.
- State that D4P is more faithful, MiMo is more relevant, and the two are
  approximately tied when comparing the answer-dependent metrics.
- Keep all values visible in an accessible HTML table in addition to the visual
  bars.

## Interaction And Responsiveness

- Use CSS-driven horizontal metric bars so the section works without external
  chart libraries.
- Preserve keyboard-accessible horizontal scrolling for the comparison table.
- Stack the experiment cards on narrow screens.

## Files

- `frontend/showcase.html`
- `docs/index.html`
- `backend/tests/test_showcase_page.py`

The two HTML entry points must remain synchronized.
