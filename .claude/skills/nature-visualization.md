---
name: nature-visualization
description: Nature journal style plotting — clean, publication-quality matplotlib figures with proper font sizing, color schemes, and layout
alwaysApply: false
---

# Nature Journal Style Visualization Standards

When generating plots for MCM/ICM papers, follow Nature journal conventions.

## Font Standards
- **Title:** 14pt bold
- **Axis labels:** 12pt
- **Tick labels:** 10pt
- **Legend:** 10pt, placed to minimize data occlusion
- **Font family:** Arial or Helvetica (sans-serif)
- **Math expressions:** Use LaTeX rendering (`rcParams['text.usetex'] = False`, use `mathtext`)

## Figure Quality
- **DPI:** 300 minimum for submitted figures
- **Format:** Vector (PDF/SVG) preferred, PNG at 300 DPI acceptable
- **Dimensions:**
  - Single column: 89mm wide
  - Double column: 183mm wide
  - Aspect ratio: golden ratio (1.618:1) or 4:3

## Color Scheme
- Use colorblind-friendly palettes (viridis, cividis, plasma)
- Avoid red-green combinations
- Use distinct markers in addition to colors for accessibility
- Grayscale should be distinguishable when printed

## Plot Components
- Remove top and right spines unless needed
- Grid lines: light gray, dashed, behind data
- Error bars: clearly visible, labeled
- Annotations: use arrows and text boxes to highlight key features
- Subplot labels: (a), (b), (c) in top-left corner, bold

## Templates Available
See `agent_app/nature_skills/Viz_Templates/` for reusable templates:
- `01_standard_line_plot.py` — Standard line plot with error bars
- `02_nature_3d_grid_refactored.py` — 3D surface with proper projection
- `03_stacked_plots_highlight.py` — Stacked subplots with highlights
- `04_hysteresis_loops_nature.py` — Hysteresis loop visualization
- `05_performance_3d_bar.py` — 3D bar chart
- `06_performance_radar.py` — Radar/spider chart for multi-criteria
- `07_performance_lollipop.py` — Lollipop chart
- `08_complex_regression_analysis.py` — Regression with confidence bands
