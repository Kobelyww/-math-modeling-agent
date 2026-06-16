import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import gaussian_kde, linregress

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.colors import get_material_colors
    from utils.plot_tools import apply_style
except ImportError:
    print("Warning: utils not found. Using local colors.")
    def get_material_colors():
        return {
            "deep purple": {3: "#b39ddb", 7: "#512da8"},
            "red": {3: "#ef9a9a", 7: "#d32f2f"},
            "blue grey": {7: "#455a64"}
        }
    def apply_style(style):
        print(f"Mock apply style: {style}")

def calculate_metrics(y_true, y_pred):
    """Calculate RMSE and R2 manually to avoid sklearn dependency."""
    rmse = np.sqrt(np.mean((y_true - y_pred)**2))
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    r2 = 1 - (ss_res / ss_tot)
    return rmse, r2

def make_dummy_data(n_samples=100, noise=0.5):
    """Generate dummy regression data."""
    np.random.seed(42)
    X = np.random.uniform(25, 65, n_samples)
    y_true = X + np.random.normal(0, noise, n_samples)
    y_pred = y_true * 0.95 + 2 + np.random.normal(0, noise, n_samples)
    return y_true, y_pred

def add_marginal_plot(fig, sub_spec, y_true_train, y_pred_train, y_true_test, y_pred_test, title_tag):
    """
    Creates a joint plot (Scatter + Marginal KDEs) within a given GridSpec slot.
    """
    # Create inner GridSpec for Main, Top, Right axes
    gs_inner = gridspec.GridSpecFromSubplotSpec(
        2, 2, subplot_spec=sub_spec,
        width_ratios=[4, 1], height_ratios=[1, 4],
        wspace=0.05, hspace=0.05
    )

    ax_main = fig.add_subplot(gs_inner[1, 0])
    ax_top = fig.add_subplot(gs_inner[0, 0], sharex=ax_main)
    ax_right = fig.add_subplot(gs_inner[1, 1], sharey=ax_main)

    colors = get_material_colors()
    c_train = colors['deep purple'][7]
    c_test = colors['red'][7]
    
    # Main Scatter
    ax_main.scatter(y_true_train, y_pred_train, c=c_train, alpha=0.6, label='Train', edgecolor='white', s=40)
    ax_main.scatter(y_true_test, y_pred_test, c=c_test, alpha=0.7, label='Test', edgecolor='white', s=40)
    
    # Ideal Fit Line
    lims = [
        np.min([ax_main.get_xlim(), ax_main.get_ylim()]),  # min of both axes
        np.max([ax_main.get_xlim(), ax_main.get_ylim()]),  # max of both axes
    ]
    ax_main.plot(lims, lims, 'k--', alpha=0.75, zorder=0, label='Ideal fit')
    
    # Calculate Stats
    rmse_train, r2_train = calculate_metrics(y_true_train, y_pred_train)
    rmse_test, r2_test = calculate_metrics(y_true_test, y_pred_test)

    # Custom Legend
    stats_text = (
        f"Train: RMSE: {rmse_train:.2f}, R²: {r2_train:.2f}\n"
        f"Test: RMSE: {rmse_test:.2f}, R²: {r2_test:.2f}"
    )
    # Using simple legend for now, could be enhanced
    ax_main.legend(loc='upper left', fontsize=7, frameon=True)
    
    # Marginal Top (KDE)
    x_grid = np.linspace(lims[0], lims[1], 100)
    kde_train_x = gaussian_kde(y_true_train)(x_grid)
    kde_test_x = gaussian_kde(y_true_test)(x_grid)
    
    ax_top.fill_between(x_grid, kde_train_x, color=c_train, alpha=0.3)
    ax_top.plot(x_grid, kde_train_x, color=c_train, lw=1)
    ax_top.fill_between(x_grid, kde_test_x, color=c_test, alpha=0.3)
    ax_top.plot(x_grid, kde_test_x, color=c_test, lw=1)
    ax_top.axis('off')

    # Marginal Right (KDE) - Rotated
    kde_train_y = gaussian_kde(y_pred_train)(x_grid)
    kde_test_y = gaussian_kde(y_pred_test)(x_grid)
    
    ax_right.fill_betweenx(x_grid, kde_train_y, color=c_train, alpha=0.3)
    ax_right.plot(kde_train_y, x_grid, color=c_train, lw=1)
    ax_right.fill_betweenx(x_grid, kde_test_y, color=c_test, alpha=0.3)
    ax_right.plot(kde_test_y, x_grid, color=c_test, lw=1)
    ax_right.axis('off')
    
    # Labels
    ax_main.set_xlabel("True Oil Yield(wt%)", fontsize=8)
    ax_main.set_ylabel("Predicted Oil Yield(wt%)", fontsize=8)
    
    # Title Tag
    ax_top.text(0, 1.2, title_tag, transform=ax_top.transAxes, 
                fontsize=12, fontweight='bold', va='bottom', ha='left')

def expand_spacing(text, spacing=1):
    """
    Manually expand character spacing by inserting thin spaces.
    Standard Matplotlib does not support letter-spacing natively without LaTeX.
    """
    # Use unicode hair space or thin space
    # \u2009 is thin space, \u200a is hair space.
    spacer = '\u2009' * spacing 
    return spacer.join(list(text))

def add_stats_scatter(fig, sub_spec, r2_vals, rmse_vals, std_vals, title_tag):
    """
    Creates the RMSE vs R2 scatter plot with color mapping.
    """
    ax = fig.add_subplot(sub_spec)
    
    # Color mapping
    sc = ax.scatter(r2_vals, rmse_vals, c=std_vals, cmap='coolwarm', 
                    edgecolor='k', alpha=0.8, s=50)
    
    # Reference lines (Mean)
    mean_r2 = np.mean(r2_vals)
    mean_rmse = np.mean(rmse_vals)
    ax.axvline(mean_r2, color='r', linestyle='--', alpha=0.7)
    ax.axhline(mean_rmse, color='r', linestyle='--', alpha=0.7)
    
    # Labels with expanded spacing
    # R M S E and S T D
    label_rmse = expand_spacing("RMSE", 1)
    label_r2 = "R²" # Don't expand superscripts naively
    label_std = expand_spacing("STD", 1)

    ax.set_xlabel(label_r2, fontsize=8)
    ax.set_ylabel(label_rmse, fontsize=8, labelpad=10)
    
    # Colorbar
    cbar = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(label_std, rotation=270, labelpad=20, fontsize=8)
    
    # Stats Box
    stats_text = (
        f"R² = {np.mean(r2_vals):.3f} ± {np.std(r2_vals):.3f}\n"
        f"RMSE = {np.mean(rmse_vals):.3f} ± {np.std(rmse_vals):.3f}\n"
        f"STD = {np.mean(std_vals):.3f} ± {np.std(std_vals):.3f}"
    )
    props = dict(boxstyle='round', facecolor='white', alpha=0.9)
    ax.text(0.05, 0.05, stats_text, transform=ax.transAxes, fontsize=7,
            verticalalignment='bottom', bbox=props)
            
    # Title Tag
    ax.text(-0.1, 1.05, title_tag, transform=ax.transAxes, 
            fontsize=12, fontweight='bold', va='bottom', ha='right')

def plot_complex_regression_analysis(save_path=None):
    """
    Replicates the complex multi-panel regression analysis figure.
    """
    # 0. Apply Times New Roman Style
    apply_style('times_new_roman')

    # 1. Setup Grid
    fig = plt.figure(figsize=(12, 8)) # DPI handled by style or defaults
    outer_grid = gridspec.GridSpec(2, 3, width_ratios=[1, 1, 1], height_ratios=[1, 1], wspace=0.3, hspace=0.3)
    
    # 2. Top Row: Joint Plots (a, b, c)
    tags_top = ['(a)', '(b)', '(c)']
    for i in range(3):
        # Generate varied dummy data for each column
        noise = 2.0 + i * 0.5
        y_true_tr, y_pred_tr = make_dummy_data(100, noise=noise)
        y_true_te, y_pred_te = make_dummy_data(50, noise=noise*1.5)
        
        add_marginal_plot(fig, outer_grid[0, i], y_true_tr, y_pred_tr, y_true_te, y_pred_te, tags_top[i])
        
    # 3. Bottom Row: Stats Scatter (d, e, f)
    tags_bottom = ['(d)', '(e)', '(f)']
    for i in range(3):
        # Generate dummy stats data
        np.random.seed(i+10)
        r2_vals = np.random.uniform(0.85, 0.98, 100)
        rmse_vals = 3.5 - 1.5 * r2_vals + np.random.normal(0, 0.1, 100)
        std_vals = np.random.uniform(8, 10, 100)
        
        add_stats_scatter(fig, outer_grid[1, i], r2_vals, rmse_vals, std_vals, tags_bottom[i])
        
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save_path}")
        
    plt.show()

if __name__ == "__main__":
    plot_complex_regression_analysis()
