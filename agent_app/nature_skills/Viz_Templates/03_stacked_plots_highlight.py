import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d

# 添加项目根目录到 sys.path 以便导入 utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.colors import get_material_colors
except ImportError:
    # Fallback if utils not found (e.g. running standalone without project structure)
    print("Warning: utils.colors not found. Using local color definition.")
    def get_material_colors():
        return {
             "blue grey": {0: "#eceff1", 1: "#cfd8dc", 2: "#b0bec5", 3: "#90a4ae", 4: "#78909c", 5: "#607d8b", 6: "#546e7a", 7: "#455a64", 8: "#37474f", 9: "#263238"},
             "yellow": {0: "#fffde7", 1: "#fff9c4", 2: "#fff59d", 3: "#fff176", 4: "#ffee58", 5: "#ffeb3b", 6: "#fdd835", 7: "#fbc02d", 8: "#f9a825", 9: "#f57f17"}
        }

def plot_stacked_highlight(save_path=None):
    """
    创建一个带有局部高亮的堆叠图 (Stacked Plot with Local Highlighting)。
    复刻自 Scientific Visualization Book 的 stacked-plots.py。
    """
    
    # 1. 获取颜色字典
    material = get_material_colors()
    
    # 2. 生成模拟数据 (实际使用时请替换为加载真实数据)
    # ---------------------------------------------------------
    np.random.seed(1)
    X = np.linspace(0, 1, 500)
    
    # Y0 是堆叠的基线，初始为全 1 (即第一层从 y=1 开始，或者作为偏移量)
    Y0 = np.ones(len(X))
    
    # 3. 设置绘图
    plt.figure(figsize=(8, 4))
    ax = plt.subplot(1, 1, 1)
    
    # 4. 循环绘制每一层
    # 我们绘制 10 层
    for i in range(10):
        # 生成每一层的数据：基线 Y0 + 随机波动
        # 波动幅度随层数增加而减小 (1/(i+1))
        Y = Y0 + np.random.uniform(0, 1 / (i + 1), len(X))
        
        # 使用高斯滤波平滑数据，使其看起来更自然
        Y = gaussian_filter1d(Y, 3)
        
        # -----------------------------------------------------
        # 核心逻辑：两次 fill_between 实现局部高亮
        # -----------------------------------------------------
        
        # (A) 绘制背景层 (默认颜色)
        # 使用 material["blue grey"] 色系，颜色深浅随 i 变化
        # 9-i 使得底层颜色较深，顶层较浅 (或者相反，取决于字典定义)
        ax.fill_between(
            X,
            Y,
            Y0,
            edgecolor="white",
            linewidth=0.25,
            facecolor=material["blue grey"][9 - i],
            label=f"Layer {i}" if i == 0 else None # 仅标记第一个以便图例(如果需要)
        )
        
        # (B) 绘制高亮区域
        # 仅在 X 的特定索引范围 [325:425] 内绘制
        # 使用 material["yellow"] 色系进行高亮
        ax.fill_between(
            X[325:425], 
            Y[325:425], 
            Y0[325:425], 
            facecolor=material["yellow"][9 - i]
        )
        
        # (C) 绘制高亮区域的边缘线 (黑色，增强对比度)
        ax.plot(X[325:425], Y[325:425], color="black", linewidth=0.25)
        
        # 更新基线 Y0，下一层将堆叠在当前层之上
        Y0 = Y

    # 5. 添加辅助线指示高亮区域范围
    ax.axvline(X[325], color="black", linestyle="--")
    ax.axvline(X[424], color="black", linestyle="--")

    # 6. 设置坐标轴样式
    ax.set_xlim(0, 1)
    ax.set_xticks([]) # 隐藏 X 轴刻度
    
    ax.set_ylim(1, 3) # 根据数据范围调整
    ax.set_yticks([]) # 隐藏 Y 轴刻度
    
    # 移除边框 (Spines)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
        print(f"Figure saved to {save_path}")
    
    plt.show()

if __name__ == "__main__":
    plot_stacked_highlight()