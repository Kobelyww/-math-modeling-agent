import sys
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Add project root to sys.path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.data_loader import load_data
    from utils.colors import get_material_colors
except ImportError:
    print("Warning: utils not found. Please ensure you are running this from the templates directory.")
    sys.exit(1)

def configure_nature_style():
    """
    Configures Matplotlib rcParams to meet Nature journal standards.
    """
    plt.rcParams.update({
        # Figure size (single column is ~89mm = 3.5 inches)
        'figure.figsize': (3.5, 5), # 2 rows, so taller
        'figure.dpi': 300,
        
        # Fonts
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 8,
        'axes.labelsize': 8,
        'axes.titlesize': 8,
        'xtick.labelsize': 7,
        'ytick.labelsize': 7,
        'legend.fontsize': 7,
        
        # Lines
        'lines.linewidth': 1.0,
        'lines.markersize': 4,
        
        # Axes
        'axes.linewidth': 0.8,
        'axes.edgecolor': 'black',
        'axes.grid': False, # Clean look
        
        # Ticks
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.size': 3,
        'ytick.major.size': 3,
        'xtick.major.width': 0.6,
        'ytick.major.width': 0.6,
        'xtick.top': True,    # Box style
        'ytick.right': True,  # Box style
    })

def plot_hysteresis_loops(save_path=None):
    """
    Loads ferroelectric data and plots Q-V and C-V hysteresis loops
    in a Nature-publication ready style.
    """
    # 1. Load Data
    try:
        df = load_data('test_pfecap_dc_qv_cv.csv')
    except FileNotFoundError:
        print("Data file not found. Please ensure 'test_pfecap_dc_qv_cv.csv' is in the 'data' directory.")
        return

    # 2. Setup Style
    configure_nature_style()
    colors = get_material_colors()
    
    # Define colors for Forward and Reverse scans
    # Using 'blue' and 'red' from material palette for high contrast
    color_fwd = colors['blue'][8]  # Deep Blue
    color_rev = colors['red'][8]   # Deep Red

    # 3. Create Plot (2 rows, 1 column)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.5, 5), sharex=False)
    
    # --- Subplot 1: Q-V Loop ---
    # Plot Forward
    ax1.plot(df['Vfe_f_V'], df['Q_f_uC_cm2'], 
             color=color_fwd, label='Forward ($Q_1$)', zorder=10)
    # Plot Reverse
    ax1.plot(df['Vfe_r_V'], df['Q_r_uC_cm2'], 
             color=color_rev, label='Reverse ($Q_2$)', zorder=10)

    # Labels and Title
    ax1.set_ylabel('Charge Density ($\mu$C/cm$^2$)')
    # ax1.set_xlabel('Voltage (V)') # Shared axis concept, but better to label both in this layout
    ax1.set_xlabel('Voltage (V)')
    
    # Ticks formatting
    ax1.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax1.xaxis.set_minor_locator(ticker.MultipleLocator(0.5))
    ax1.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    
    # Legend
    ax1.legend(loc='upper left', frameon=False, handlelength=1.5)
    
    # Add a tag (a) for Nature style figures
    ax1.text(-0.15, 1.05, 'a', transform=ax1.transAxes, 
             fontsize=10, fontweight='bold', va='top', ha='right')

    # --- Subplot 2: C-V Loop ---
    # Plot Forward
    ax2.plot(df['Vfe_f_V'], df['C_f_uF_cm2'], 
             color=color_fwd, label='Forward ($C_1$)', zorder=10)
    # Plot Reverse
    ax2.plot(df['Vfe_r_V'], df['C_r_uF_cm2'], 
             color=color_rev, label='Reverse ($C_2$)', zorder=10)

    # Labels
    ax2.set_ylabel(r'Capacitance ($\mu$F/cm$^2$)')
    ax2.set_xlabel('Voltage (V)')
    
    # Ticks formatting
    ax2.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax2.xaxis.set_minor_locator(ticker.MultipleLocator(0.5))
    ax2.yaxis.set_minor_locator(ticker.AutoMinorLocator())

    # Legend (Optional, if redundant)
    # ax2.legend(loc='upper center', frameon=False)
    
    # Add a tag (b)
    ax2.text(-0.15, 1.05, 'b', transform=ax2.transAxes, 
             fontsize=10, fontweight='bold', va='top', ha='right')

    # 4. Final Layout Adjustments
    plt.tight_layout()
    
    # Save or Show
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save_path}")
    
    plt.show()

if __name__ == "__main__":
    plot_hysteresis_loops()
