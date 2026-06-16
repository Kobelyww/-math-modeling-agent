import sys
import os
import matplotlib.pyplot as plt
import numpy as np

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.colors import get_material_colors
except ImportError:
    print("Warning: utils not found. Using local colors.")
    def get_material_colors():
        return {"teal": {5: "#009688"}, "red": {5: "#f44336"}, "blue": {5: "#2196f3"}, "blue grey": {7: "#455a64"}}

def plot_performance_lollipop(save_path=None):
    """
    Creates a Lollipop Chart for performance metrics.
    A clean, 2D alternative to bar charts.
    """
    # 1. Data
    categories = ['Avg FPS', 'Pred Time (ms)', 'Memory (MB)']
    values = [13.02, 0.28, 245.6]
    
    # 2. Setup Figure
    fig, ax = plt.subplots(figsize=(8, 4), dpi=300)
    
    # 3. Colors
    colors_lib = get_material_colors()
    colors = [
        colors_lib['teal'][7], 
        colors_lib['deep orange'][7], 
        colors_lib['blue grey'][7]
    ]
    
    # 4. Plot Lollipop
    # Create a stem plot manually for better control
    y_pos = np.arange(len(categories))
    
    # Draw horizontal lines (stems)
    # We normalized lengths just for visual balance if we wanted, but here let's try
    # simply plotting them on different x-scales? 
    # NO, lollipop works best when sharing an axis. 
    # Since units are different, we can't share X axis easily.
    # Solution: Normalize "Visual Length" but label "Real Value".
    
    # Normalize to 0-1 range for plotting
    max_visual_length = 0.8
    # Assign relative visual importance/length
    visual_lengths = [0.65, 0.45, 0.85] 
    
    for i, (y, length, color, val) in enumerate(zip(y_pos, visual_lengths, colors, values)):
        # Line (Stem)
        ax.hlines(y=y, xmin=0, xmax=length, color=color, alpha=0.6, linewidth=2)
        
        # Point (Candy)
        ax.plot(length, y, 'o', markersize=12, color=color, alpha=1.0)
        
        # Label (Value)
        # Position label to the right of the dot
        label_text = f"{val}"
        if i == 1: label_text += " ms"
        elif i == 2: label_text += " MB"
        
        ax.text(length + 0.05, y, label_text, 
                va='center', ha='left', 
                fontsize=11, fontweight='bold', color=color)

    # 5. Axes & Labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=11, fontweight='bold', family='sans-serif')
    
    # Remove X axis (visual lengths are symbolic)
    ax.set_xticks([])
    
    # Invert Y axis to have first item on top
    ax.invert_yaxis()
    
    # 6. Aesthetics (Clean / Scientific)
    # Remove spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False) # Remove left spine too, names are enough
    
    # Add Title
    ax.set_title("Performance Statistics (Lollipop Chart)", 
                 loc='left', fontsize=12, fontweight='bold', color='#37474f', pad=20)
    
    # Set X limit to accommodate labels
    ax.set_xlim(0, 1.2)

    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save_path}")
    
    plt.show()

if __name__ == "__main__":
    plot_performance_lollipop()
