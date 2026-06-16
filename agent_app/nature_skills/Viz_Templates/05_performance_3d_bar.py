import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.text import TextPath
from matplotlib.transforms import Affine2D
import mpl_toolkits.mplot3d.art3d as art3d
from mpl_toolkits.mplot3d import Axes3D

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.colors import get_material_colors
except ImportError:
    print("Warning: utils not found. Using local colors.")
    def get_material_colors():
        return {"teal": {5: "#009688"}, "red": {5: "#f44336"}, "blue": {5: "#2196f3"}}

def text3d(ax, xyz, s, zdir="z", size=0.1, angle=0, **kwargs):
    """
    Plots 3D text by converting 2D text path to 3D patch.
    Adapted from scientific-visualization-book-master/code/typography/projection-3d-gaussian.py
    """
    x, y, z = xyz
    if zdir == "y":
        xy, z = (x, z), y
    elif zdir == "x":
        xy, z = (y, z), x
    else:
        xy, z = (x, y), z
        
    # Use default sans-serif font to ensure compatibility
    path = TextPath((0, 0), s, size=size, prop=dict(family="sans-serif", weight='bold'))
    V = path.vertices
    # Center the text horizontally
    V[:, 0] -= (V[:, 0].max() - V[:, 0].min()) / 2
    
    trans = Affine2D().rotate(angle).translate(xy[0], xy[1])
    path = PathPatch(trans.transform_path(path), **kwargs)
    ax.add_patch(path)
    art3d.pathpatch_2d_to_3d(path, z=z, zdir=zdir)

def plot_performance_metrics_3d(save_path=None):
    """
    Creates a 3D Bar Chart for performance metrics (FPS, Time, Memory).
    Uses normalized heights for visual balance while displaying actual values.
    """
    # 1. Data
    categories = ['Avg FPS', 'Pred Time\n(ms)', 'Memory\n(MB)']
    values = [13.02, 0.28, 245.6]
    units = ['', 'ms', 'MB']
    
    # Colors for each metric (Nature Style / Material Design)
    # Using deeper shades (Index 7) for professional look and better contrast
    colors_lib = get_material_colors()
    bar_colors = [
        colors_lib['teal'][7],       # Deep Teal for FPS
        colors_lib['deep orange'][7], # Deep Orange for Time
        colors_lib['blue grey'][7]    # Blue Grey for Memory
    ]

    # 2. Normalize values for plotting
    # We want them to have roughly comparable heights in the plot
    # Let's map them to a 0.2 - 1.0 range
    max_height = 1.0
    plot_heights = [0.65, 0.45, 0.85] # Adjusted for aesthetic balance
    
    # 3. Setup Figure
    # Use higher DPI for 'Nature' quality
    fig = plt.figure(figsize=(8, 6), dpi=300)
    ax = fig.add_subplot(111, projection='3d')
    
    # 4. Create 3D Bars
    # x positions
    x_pos = [1, 3, 5]
    y_pos = [0, 0, 0]
    z_pos = [0, 0, 0]
    
    # Thinner bars for elegance
    dx = [0.6, 0.6, 0.6] 
    dy = [0.6, 0.6, 0.6] 
    dz = plot_heights

    # Create bars with edge colors for definition
    # shade=True gives the 3D effect.
    ax.bar3d(x_pos, y_pos, z_pos, dx, dy, dz, 
             color=bar_colors, 
             edgecolor='white', linewidth=0.5, 
             alpha=1.0, shade=True)

    # 5. Add Text Labels (Actual Values)
    # Use Arial font for Nature standard
    font_props = {'family': 'sans-serif', 'weight': 'bold', 'size': 10}
    
    for i, (x, h, val, unit) in enumerate(zip(x_pos, plot_heights, values, units)):
        # Label on top of bar
        label_text = f"{val}\n{unit}" if unit else f"{val}"
        
        # Position text floating above the bar
        ax.text(x + dx[i]/2, 0, h + 0.05, label_text, 
                ha='center', va='bottom', zdir='y', **font_props)

    # 6. Set Labels for Axes
    ax.set_xticks([p + dx[0]/2 for p in x_pos])
    ax.set_xticklabels(categories, fontsize=9, fontweight='bold', family='sans-serif')
    
    # Hide Y and Z axes ticks
    ax.set_yticks([])
    ax.set_zticks([])
    
    # 7. Aesthetics (Nature/Scientific Style)
    # Remove panes background to make it look "floating"
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    
    # Remove all axis lines (spines)
    ax.xaxis.line.set_color((1.0, 1.0, 1.0, 0.0))
    ax.yaxis.line.set_color((1.0, 1.0, 1.0, 0.0))
    ax.zaxis.line.set_color((1.0, 1.0, 1.0, 0.0))
    
    # Remove grid
    ax.grid(False)
    
    # Adjust view angle for a better "isometric-like" look
    ax.view_init(elev=25, azim=-60)
    
    # Title
    ax.set_title("Performance Statistics", fontsize=12, fontweight='bold', y=0.95, family='sans-serif')

    # Tight layout often fails with 3D, so we use subplots_adjust if needed
    # But let's try tight_layout with pad
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300)
        print(f"Figure saved to {save_path}")
        
    plt.show()

if __name__ == "__main__":
    plot_performance_metrics_3d()
