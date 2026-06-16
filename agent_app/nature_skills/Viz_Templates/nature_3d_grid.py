import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from matplotlib import cm

def create_custom_cmap():
    """
    复刻图片中的配色：深墨绿 -> 浅绿 -> 白 -> 浅粉 -> 深洋红
    """
    # 颜色锚点：根据图片吸取的大致颜色
    colors = [
        '#005545',  # 深墨绿 (Dark Teal) - 底部
        '#66B2A0',  # 浅青 (Light Teal)
        '#FFFFFF',  # 白 (White) - 中间过渡
        '#F090B0',  # 浅粉 (Light Pink)
        '#C02070'   # 深洋红 (Deep Magenta) - 顶部
    ]
    # 创建线性渐变色图，分成 256 个级别
    return mcolors.LinearSegmentedColormap.from_list("NatureTealMagenta", colors, N=256)

def generate_mock_surface(i, j):
    """
    生成模拟的漏斗状曲面数据
    i, j 控制形状的变化，模拟图片中参数变化的效果
    """
    x = np.linspace(-2, 2, 30)
    y = np.linspace(-2, 2, 30)
    X, Y = np.meshgrid(x, y)
    
    # 模拟函数：一个势阱 + 一些扰动
    # 随着 i, j 增加，势阱可能变深或变宽
    depth = 1.0 + 0.2 * i
    width = 0.5 + 0.1 * j
    
    # 高斯分布倒数模拟漏斗
    Z = -depth * np.exp(-(X**2 + Y**2) / width) 
    
    # 归一化到 0-1 之间方便上色，然后缩放到类似电流的数量级
    Z = (Z - Z.min()) / (Z.max() - Z.min())
    Z = Z * 1e-5 # 模拟 10^-5 量级
    
    return X, Y, Z

def plot_nature_grid():
    # 1. 设置出版级参数
    plt.rcParams.update({
        'font.family': 'Arial',
        'font.size': 10,
        'axes.linewidth': 0.5,
    })

    # 2. 准备画布
    fig = plt.figure(figsize=(12, 10)) # 宽 12 英寸，高 10 英寸
    
    # 自定义色卡
    my_cmap = create_custom_cmap()
    
    # 3. 循环绘制 4x4 网格
    rows, cols = 4, 4
    axes = []
    
    # 这里的 min/max 用于统一所有子图的颜色映射范围
    global_z_min, global_z_max = 0, 1e-5 

    for r in range(rows):
        for c in range(cols):
            # 添加 3D 子图
            ax = fig.add_subplot(rows, cols, r * cols + c + 1, projection='3d')
            axes.append(ax)
            
            # 生成数据
            X, Y, Z = generate_mock_surface(r, c)
            
            # 绘制曲面
            # rstride/cstride 控制网格密度，linewidth=0.1 细线描边增强立体感
            surf = ax.plot_surface(X, Y, Z, cmap=my_cmap, 
                                 vmin=global_z_min, vmax=global_z_max,
                                 rstride=2, cstride=2, 
                                 alpha=0.9, linewidth=0.1, edgecolors='k')
            
            # 绘制底部的投影轮廓 (contour)
            ax.contour(X, Y, Z, zdir='z', offset=global_z_min, cmap=my_cmap, alpha=0.5)

            # --- 调整样式 ---
            ax.set_zlim(global_z_min, global_z_max)
            ax.view_init(elev=30, azim=-45) # 统一视角
            
            # 去掉复杂的背景和坐标轴数字 (根据图片风格，只保留刻度线或完全简化)
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            ax.set_zticklabels([])
            
            # 简单的边框颜色
            ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
            ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
            ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))

            # 行列标题 (仅在边缘添加)
            if r == 0:
                ax.set_title(f"$C_2: F_0: V_{{TH}}={1.1 - 0.3*c:.1f}$ V", fontsize=11, pad=10)
            if c == 0:
                # 使用 text2D 在左侧添加行标
                ax.text2D(-0.2, 0.5, f"$C_1: F_0: V_{{TH}}={1.1 - 0.3*r:.1f}$ V", 
                          transform=ax.transAxes, rotation=90, va='center', fontsize=11)

    # 4. 添加共用 Colorbar
    # 在右侧预留位置
    fig.subplots_adjust(right=0.85, hspace=0.1, wspace=0.1)
    cbar_ax = fig.add_axes([0.88, 0.35, 0.02, 0.3]) # [left, bottom, width, height]
    
    # 创建 Colorbar
    norm = mcolors.Normalize(vmin=global_z_min, vmax=global_z_max)
    sm = cm.ScalarMappable(cmap=my_cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    
    # Colorbar 标签
    cbar.set_label('ML current (A)', fontsize=12, labelpad=10)
    # 设置刻度格式为科学计数法
    cbar.ax.yaxis.set_major_formatter(plt.FormatStrFormatter('%.0e'))

    # 5. 添加左侧大箭头说明 (模拟图片左侧的橙色箭头)
    fig.text(0.02, 0.5, "C1 boundary increases with V_TH", 
             rotation=90, va='center', fontsize=12, color='#E07020', fontweight='bold')
    # 绘制箭头 (用 line 代替)
    import matplotlib.lines as lines
    line = lines.Line2D([0.04, 0.04], [0.2, 0.8], transform=fig.transFigure, 
                       color='#E07020', linewidth=2, marker='^', markersize=10, markevery=(1, 1))
    fig.add_artist(line)

    output_path = 'nature_3d_grid_repro.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Plot saved to {output_path}")

if __name__ == "__main__":
    plot_nature_grid()