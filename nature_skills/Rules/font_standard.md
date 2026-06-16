# Scientific Visualization Font & Style Standard

This standard applies to all matplotlib/seaborn visualizations in this project to ensure publication-quality output (Origin-style).

## 1. Font Settings
- **Font Family**: `Times New Roman`
- **Base Font Size**: `22` (Previously 11)
- **Title Font Size**: `28` (Bold). *Note: Prefer LaTeX captions over embedded titles. Save sub-plots as separate files (e.g., _a.png, _b.png) for flexible LaTeX layout.*
- **Axis Label Font Size**: `22` (Inherits default) or `24`
- **Tick Label Font Size**: `20` (Previously 10)
- **Annotation/Text Font Size**: `18` (Previously 9)
- **Legend Font Size**: `20` (Previously 10)

## 2. Axis & Ticks Configuration
- **Spines (Borders)**: 
  - Show ALL spines (Top, Bottom, Left, Right).
  - Creates a "Box" look.
- **Tick Direction**: `in` (Inward facing) for all ticks.
- **Tick Visibility**:
  - **Left & Bottom**: Show Ticks and Labels.
  - **Right & Top**: Show Spine (Line) ONLY. No Ticks, No Labels.

## 3. Implementation Snippet (Matplotlib)

```python
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['font.size'] = 22
plt.rcParams['axes.linewidth'] = 1.5
plt.rcParams['figure.dpi'] = 300
plt.rcParams['axes.titleweight'] = 'bold'

# Spines (Box Style)
plt.rcParams['axes.spines.top'] = True
plt.rcParams['axes.spines.right'] = True

# Ticks
plt.rcParams['xtick.direction'] = 'in'
plt.rcParams['ytick.direction'] = 'in'
plt.rcParams['xtick.top'] = False      # No ticks on top spine
plt.rcParams['ytick.right'] = False    # No ticks on right spine
```