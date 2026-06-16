import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, RegularPolygon
from matplotlib.path import Path
from matplotlib.projections.polar import PolarAxes
from matplotlib.projections import register_projection
from matplotlib.spines import Spine
from matplotlib.transforms import Affine2D

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.colors import get_material_colors
except ImportError:
    print("Warning: utils not found. Using local colors.")
    def get_material_colors():
        return {"teal": {5: "#009688"}, "red": {5: "#f44336"}, "blue": {5: "#2196f3"}, "blue grey": {7: "#455a64"}}

def radar_factory(num_vars, frame='circle'):
    """
    Create a radar chart with `num_vars` axes.

    This function creates a RadarAxes projection and registers it.

    Parameters
    ----------
    num_vars : int
        Number of variables for radar chart.
    frame : {'circle', 'polygon'}
        Shape of frame surrounding axes.

    """
    # calculate evenly-spaced axis angles
    theta = np.linspace(0, 2*np.pi, num_vars, endpoint=False)

    class RadarAxes(PolarAxes):
        name = 'radar'
        # use 1 line segment to connect specified points
        RESOLUTION = 1

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # rotate plot such that the first axis is at the top
            self.set_theta_zero_location('N')

        def fill(self, *args, closed=True, **kwargs):
            """Override fill so that line is closed by default"""
            return super().fill(closed=closed, *args, **kwargs)

        def plot(self, *args, **kwargs):
            """Override plot so that line is closed by default"""
            lines = super().plot(*args, **kwargs)
            for line in lines:
                self._close_line(line)

        def _close_line(self, line):
            x, y = line.get_data()
            if x[0] != x[-1]:
                x = np.append(x, x[0])
                y = np.append(y, y[0])
                line.set_data(x, y)
                line.set_markevery([True] * (len(x) - 1) + [False])

        def set_varlabels(self, labels):
            self.set_thetagrids(np.degrees(theta), labels, fontsize=10, fontweight='bold')

        def _gen_axes_patch(self):
            # The Axes patch must be centered at (0.5, 0.5) and of radius 0.5
            # in axes coordinates.
            if frame == 'circle':
                return Circle((0.5, 0.5), 0.5)
            elif frame == 'polygon':
                return RegularPolygon((0.5, 0.5), num_vars,
                                      radius=.5, edgecolor="k")
            else:
                raise ValueError("Unknown value for 'frame': %s" % frame)

        def _gen_axes_spines(self):
            if frame == 'circle':
                return super()._gen_axes_spines()
            elif frame == 'polygon':
                # spine_type must be 'left'/'right'/'top'/'bottom'/'circle'/...
                spine = Spine(axes=self,
                              spine_type='circle',
                              path=Path.unit_regular_polygon(num_vars))
                # unit_regular_polygon gives a polygon of radius 1 centered at
                # (0, 0) but we want a polygon of radius 0.5 centered at (0.5,
                # 0.5) in axes coordinates.
                spine.set_transform(Affine2D().scale(.5).translate(.5, .5)
                                    + self.transAxes)
                return {'polar': spine}
            else:
                raise ValueError("Unknown value for 'frame': %s" % frame)

    register_projection(RadarAxes)
    return theta

def plot_performance_radar(save_path=None):
    """
    Creates a Radar Chart (Spider Plot) for performance metrics.
    """
    # 1. Data
    categories = ['Avg FPS', 'Pred Time (ms)', 'Memory (MB)']
    values = [13.02, 0.28, 245.6]
    
    # Normalize data for the radar chart (0.0 to 1.0)
    # We define "Good" values and "Bad" values or just max scale
    # For visualization, we'll normalize them relative to a "Max Cap" 
    # so they fill the chart nicely.
    # Let's say maxFPS=20, maxTime=1.0, maxMem=300
    max_values = [20, 0.5, 300] 
    normalized_values = [v / m for v, m in zip(values, max_values)]
    
    # 2. Setup
    N = len(categories)
    theta = radar_factory(N, frame='polygon')
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection='radar'))
    fig.subplots_adjust(top=0.85, bottom=0.05)
    
    # 3. Plot
    colors_lib = get_material_colors()
    line_color = colors_lib['teal'][7]
    fill_color = colors_lib['teal'][5]
    
    ax.plot(theta, normalized_values, color=line_color, linewidth=2, linestyle='-')
    ax.fill(theta, normalized_values, facecolor=fill_color, alpha=0.25)
    
    # 4. Labels
    ax.set_varlabels(categories)
    
    # Custom radial labels (remove default numeric ticks)
    ax.set_yticklabels([])
    ax.set_yticks([]) # Hide concentric circles ticks
    
    # Add actual values as annotations at vertices
    for t, val, n_val in zip(theta, values, normalized_values):
        # Position text slightly outside the vertex
        x = t
        y = n_val + 0.15
        if categories[values.index(val)] == 'Pred Time (ms)':
             label = f"{val} ms"
        elif categories[values.index(val)] == 'Memory (MB)':
             label = f"{val} MB"
        else:
             label = f"{val}"
             
        ax.text(x, y, label, ha='center', va='center', fontsize=10, fontweight='bold', color='black')

    # 5. Decoration
    # Add grid lines manually if needed or rely on default
    ax.grid(True, color='#B0BEC5', linestyle='--', linewidth=0.5, alpha=0.7)
    
    # Set radial limits
    ax.set_ylim(0, 1.2) # Leave some space for labels
    
    # Title
    plt.title("Performance Profile", y=1.1, fontsize=14, fontweight='bold', color=colors_lib['blue grey'][7])
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save_path}")
    
    plt.show()

if __name__ == "__main__":
    plot_performance_radar()
