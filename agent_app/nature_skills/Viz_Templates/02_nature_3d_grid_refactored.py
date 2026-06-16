import sys
import os
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

# --- 关键点 1: 动态添加路径以便导入 utils ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) 
sys.path.append(project_root)

# --- 关键点 2: 导入复用的模块 ---
from utils.colors import get_nature_teal_magenta_cmap
from utils.plot_tools import save_fig
from utils.data_loader import load_data # <--- 新增导入

# --- 关键点 3: 加载复用的样式 ---
style_path = os.path.join(project_root, 'styles', 'nature.mplstyle')
plt.style.use(style_path)

def generate_mock_surface(i, j):
    """(保持原有的数据生成逻辑不变)"""
    x = np.linspace(-2, 2, 30)
    y = np.linspace(-2, 2, 30)
    X, Y = np.meshgrid(x, y)
    depth = 1.0 + 0.2 * i
    width = 0.5 + 0.1 * j
    Z = -depth * np.exp(-(X**2 + Y**2) / width) 
    Z = (Z - Z.min()) / (Z.max() - Z.min())
    Z = Z * 1e-5
    return X, Y, Z

def plot_nature_grid():
    # --- 演示：如何加载数据 ---
    try:
        # 只需要文件名，不需要关心绝对路径
        df = load_data('test_pfecap_dc_qv_cv.csv')
        print(f"Successfully loaded data with shape: {df.shape}")
        print("Columns:", df.columns.tolist())
    except Exception as e:
        print(f"Warning: Could not load data example ({e})")

    # 1. 准备画布
    fig = plt.figure(figsize=(12, 10))
    
    # 2. 获取复用的颜色
    my_cmap = get_nature_teal_magenta_cmap()
    
    rows, cols = 4, 4
    global_z_min, global_z_max = 0, 1e-5 

    for r in range(rows):
        for c in range(cols):
            ax = fig.add_subplot(rows, cols, r * cols + c + 1, projection='3d')
            
            X, Y, Z = generate_mock_surface(r, c)
            
            # 绘图逻辑
            ax.plot_surface(X, Y, Z, cmap=my_cmap, 
                          vmin=global_z_min, vmax=global_z_max,
                          rstride=2, cstride=2, 
                          alpha=0.9, linewidth=0.1, edgecolors='k')
            
            ax.contour(X, Y, Z, zdir='z', offset=global_z_min, cmap=my_cmap, alpha=0.5)

            # 样式调整
            ax.set_zlim(global_z_min, global_z_max)
            ax.view_init(elev=30, azim=-45)
            ax.set_xticklabels([]); ax.set_yticklabels([]); ax.set_zticklabels([])
            ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
            ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
            ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))

            if r == 0:
                ax.set_title(f"$C_2: F_0: V_{{TH}}={1.1 - 0.3*c:.1f}$ V", pad=10)
            if c == 0:
                ax.text2D(-0.2, 0.5, f"$C_1: F_0: V_{{TH}}={1.1 - 0.3*r:.1f}$ V", 
                          transform=ax.transAxes, rotation=90, va='center')

    # --- Colorbar ---
    from matplotlib import cm
    fig.subplots_adjust(right=0.85, hspace=0.1, wspace=0.1)
    cbar_ax = fig.add_axes([0.88, 0.35, 0.02, 0.3]) 
    norm = mcolors.Normalize(vmin=global_z_min, vmax=global_z_max)
    sm = cm.ScalarMappable(cmap=my_cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.set_label('ML current (A)', labelpad=10)
    cbar.ax.yaxis.set_major_formatter(plt.FormatStrFormatter('%.0e'))

    # --- 箭头说明 ---
    import matplotlib.lines as lines
    fig.text(0.02, 0.5, "C1 boundary increases with V_TH", 
             rotation=90, va='center', fontsize=12, color='#E07020', fontweight='bold')
    line = lines.Line2D([0.04, 0.04], [0.2, 0.8], transform=fig.transFigure, 
                       color='#E07020', linewidth=2, marker='^', markersize=10, markevery=(1, 1))
    fig.add_artist(line)

    # 使用工具保存
    output_dir = os.path.join(current_dir, 'output')
    save_fig(fig, 'nature_3d_grid_refactored', output_dir=output_dir)
    print(f"Plot saved to {output_dir}")

if __name__ == "__main__":
    plot_nature_grid()
