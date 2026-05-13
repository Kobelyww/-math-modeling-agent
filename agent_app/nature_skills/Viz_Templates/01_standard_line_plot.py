import matplotlib.pyplot as plt
import numpy as np
import sys
import os

# 将项目根目录加入路径，以便导入 utils
# 假设此文件在 templates/ 目录下，根目录是上一级
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from utils.plot_tools import save_fig

# 1. 加载样式 (这是解耦的关键)
# 也可以叠加样式: plt.style.use(['seaborn-whitegrid', '../styles/paper_base.mplstyle'])
style_path = os.path.join(project_root, 'styles', 'paper_base.mplstyle')
plt.style.use(style_path)

def generate_mock_data():
    """模拟实验数据"""
    x = np.linspace(0, 10, 50)
    y1 = np.sin(x) + np.random.normal(0, 0.1, 50)
    y2 = np.cos(x) + np.random.normal(0, 0.1, 50)
    # 模拟误差
    y1_err = 0.1 + 0.05 * np.sqrt(x)
    y2_err = 0.1 + 0.05 * np.sqrt(x)
    return x, y1, y1_err, y2, y2_err

def main():
    # 2. 准备数据
    x, y1, err1, y2, err2 = generate_mock_data()

    # 3. 创建画布 (使用面向对象的方法，不要用 plt.plot)
    fig, ax = plt.subplots()

    # 4. 绘图逻辑
    # 实验组 1
    ax.errorbar(x, y1, yerr=err1, fmt='o', label='Experiment A', 
                capsize=3, elinewidth=1, markeredgewidth=1)
    # 实验组 2
    ax.plot(x, y2, linestyle='--', label='Model B')
    ax.fill_between(x, y2 - err2, y2 + err2, alpha=0.3)

    # 5. 装饰图表
    ax.set_xlabel('Time ($t$) / s')
    ax.set_ylabel('Voltage ($V$) / mV')
    ax.set_title('Standard Scientific Line Plot')
    ax.legend(loc='upper right', frameon=False) # 论文中常去掉图例边框
    
    # 局部微调 (如果样式表不满足)
    ax.set_xlim(0, 10)
    
    # 6. 保存
    # 自动保存到 templates/output/
    output_dir = os.path.join(current_dir, 'output')
    save_fig(fig, 'example_line_plot', output_dir=output_dir)
    print(f"Plot saved to {output_dir}")
    # plt.show() # 如果在无界面环境运行可注释掉

if __name__ == "__main__":
    main()
