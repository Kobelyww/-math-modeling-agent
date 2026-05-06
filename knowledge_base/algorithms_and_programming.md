# 数学建模算法与Python编程实践

## 一、优化问题求解

### 线性规划 Python 实现
```python
# 方法1：scipy
from scipy.optimize import linprog
import numpy as np

# min c^T x  s.t. A_ub @ x <= b_ub, A_eq @ x == b_eq, bounds
c = np.array([-1, -2])           # 目标系数（注意正负号）
A_ub = np.array([[1, 1], [2, 1]])
b_ub = np.array([5, 8])
bounds = [(0, None), (0, None)]  # x >= 0

result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
print(result.x, -result.fun)

# 方法2：pulp（更直观，支持LP和MILP）
import pulp as pl
model = pl.LpProblem("example", pl.LpMaximize)
x1 = pl.LpVariable("x1", lowBound=0, cat="Continuous")
x2 = pl.LpVariable("x2", lowBound=0, cat="Continuous")
model += x1 + 2*x2                # 目标函数
model += x1 + x2 <= 5             # 约束1
model += 2*x1 + x2 <= 8           # 约束2
model.solve()
print(pl.value(x1), pl.value(x2), pl.value(model.objective))
```

### 整数规划
```python
import pulp as pl
# 与LP类似，但 cat="Integer" 或 cat="Binary"
x = pl.LpVariable("x", lowBound=0, cat="Integer")
y = pl.LpVariable("y", cat="Binary")
# 逻辑约束：如果y=0则x=0（大M法）
M = 1000
model += x <= M * y
```

### 非线性规划
```python
from scipy.optimize import minimize

def objective(x):
    return x[0]**2 + x[1]**2 + 2*x[0]*x[1]

def constraint1(x):
    return x[0] + x[1] - 1  # >= 0

cons = [{"type": "ineq", "fun": constraint1}]
bounds = [(-10, 10), (-10, 10)]
result = minimize(objective, x0=[0, 0], bounds=bounds, constraints=cons)
```

### 遗传算法求解
```python
# 使用 geatpy / scipy.optimize.differential_evolution
from scipy.optimize import differential_evolution

def fitness(x):
    return x[0]**2 + x[1]**2  # 最小化

bounds = [(-10, 10), (-10, 10)]
result = differential_evolution(fitness, bounds, strategy='best1bin',
                                maxiter=1000, popsize=30, seed=42)
```

## 二、评价模型实现

### AHP 层次分析法
```python
import numpy as np

def ahp_weight(matrix):
    """输入判断矩阵，返回权重和CR值"""
    n = matrix.shape[0]
    # 特征向量法
    eigenvalues, eigenvectors = np.linalg.eig(matrix)
    max_eigen = np.max(eigenvalues.real)
    idx = np.argmax(eigenvalues.real)
    weights = eigenvectors[:, idx].real
    weights = weights / weights.sum()  # 归一化

    # 一致性检验
    RI = [0, 0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
    CI = (max_eigen - n) / (n - 1)
    CR = CI / RI[n-1] if n <= 10 else CI / 1.49
    return weights, CR

# 示例：3维判断矩阵
A = np.array([[1, 3, 5],
              [1/3, 1, 2],
              [1/5, 1/2, 1]])
w, cr = ahp_weight(A)
print(f"权重: {w}, CR: {cr:.4f}")  # CR < 0.1 通过一致性检验
```

### TOPSIS 熵权法
```python
def entropy_topsis(data, weights=None):
    """data: n个方案 × m个指标（已正向化）"""
    n, m = data.shape
    # 标准化
    Z = data / np.sqrt((data**2).sum(axis=0))

    # 熵权法确定权重（如果未提供）
    if weights is None:
        P = (data + 1e-10) / (data + 1e-10).sum(axis=0)
        e = -np.sum(P * np.log(P), axis=0) / np.log(n)
        weights = (1 - e) / (1 - e).sum()

    # 加权标准化
    Z_w = Z * weights

    # 正负理想解
    Z_plus = Z_w.max(axis=0)
    Z_minus = Z_w.min(axis=0)

    # 距离和贴近度
    D_plus = np.sqrt(((Z_w - Z_plus)**2).sum(axis=1))
    D_minus = np.sqrt(((Z_w - Z_minus)**2).sum(axis=1))
    C = D_minus / (D_plus + D_minus)
    return C, weights
```

## 三、预测模型实现

### ARIMA 时间序列
```python
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

# 平稳性检验
def check_stationarity(series):
    result = adfuller(series.dropna())
    return result[1] < 0.05  # p<0.05 则平稳

# ARIMA(p,d,q)
model = ARIMA(train, order=(p, d, q))
fitted = model.fit()
forecast = fitted.forecast(steps=n)
```

### 灰色预测 GM(1,1)
```python
import numpy as np

def gm11(x0, predict_n=1):
    """x0: 原始序列(一维numpy array), predict_n: 预测步数"""
    # 级比检验
    n = len(x0)
    lambda_k = x0[:-1] / x0[1:]
    lower, upper = np.exp(-2/(n+1)), np.exp(2/(n+1))
    if not ((lower < lambda_k) & (lambda_k < upper)).all():
        print("警告：部分级比不在可容覆盖区间内")
    # 一次累加
    x1 = np.cumsum(x0)
    # 紧邻均值生成
    Z = -0.5 * (x1[1:] + x1[:-1])
    # 最小二乘估计
    B = np.column_stack([Z, np.ones(n-1)])
    Y = x0[1:]
    a, b = np.linalg.lstsq(B, Y, rcond=None)[0]
    # 时间响应函数
    def predict(k):
        return (x0[0] - b/a) * np.exp(-a*k) + b/a
    # 预测
    x1_hat = np.array([predict(k + 1) for k in range(n + predict_n - 1)])
    x0_hat = np.diff(np.insert(x1_hat, 0, 0))
    # 精度检验
    residual = x0 - x0_hat[:n]
    C = residual.std() / x0.std()  # 后验差比
    P = (np.abs(residual - residual.mean()) < 0.6745 * x0.std()).mean()
    return x0_hat[-predict_n:], {'C': C, 'P': P}
```

### 随机森林预测
```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, GridSearchCV

# 调参
param_grid = {
    'n_estimators': [100, 200, 500],
    'max_depth': [None, 10, 20, 30],
    'min_samples_split': [2, 5, 10]
}
rf = RandomForestRegressor(random_state=42)
grid = GridSearchCV(rf, param_grid, cv=5, scoring='neg_mean_squared_error')
grid.fit(X_train, y_train)
print(grid.best_params_)
# 特征重要性
importances = grid.best_estimator_.feature_importances_
```

## 四、微分方程数值解

### ODE 数值解
```python
from scipy.integrate import solve_ivp
import numpy as np

# SIR模型
def sir(t, y, beta, gamma):
    S, I, R = y
    N = S + I + R
    dS = -beta * S * I / N
    dI = beta * S * I / N - gamma * I
    dR = gamma * I
    return [dS, dI, dR]

solution = solve_ivp(sir, [0, 100], [999, 1, 0],
                     args=(0.3, 0.1), max_step=0.5)
```

### 龙格库塔法（自实现）
```python
def rk4(f, y0, t_span, h):
    """经典四阶Runge-Kutta"""
    t0, t_end = t_span
    n = int((t_end - t0) / h)
    y = np.zeros((n+1, len(y0)))
    y[0] = y0
    t = np.linspace(t0, t_end, n+1)

    for i in range(n):
        k1 = h * np.array(f(t[i], y[i]))
        k2 = h * np.array(f(t[i] + h/2, y[i] + k1/2))
        k3 = h * np.array(f(t[i] + h/2, y[i] + k2/2))
        k4 = h * np.array(f(t[i] + h, y[i] + k3))
        y[i+1] = y[i] + (k1 + 2*k2 + 2*k3 + k4) / 6
    return t, y
```

## 五、蒙特卡洛模拟

```python
import numpy as np

def monte_carlo_pi(n=1000000):
    """用蒙特卡洛计算π值"""
    x = np.random.uniform(-1, 1, n)
    y = np.random.uniform(-1, 1, n)
    inside = (x**2 + y**2) <= 1
    pi_est = 4 * inside.sum() / n
    return pi_est

# 期权定价
def option_price_mc(S0, K, r, sigma, T, n=100000):
    """欧式看涨期权蒙特卡洛定价"""
    z = np.random.standard_normal(n)
    ST = S0 * np.exp((r - 0.5*sigma**2)*T + sigma*np.sqrt(T)*z)
    payoff = np.maximum(ST - K, 0)
    return np.exp(-r*T) * payoff.mean()
```

## 六、图论算法实现

### 最短路
```python
import networkx as nx
# Dijkstra
G = nx.Graph()
G.add_weighted_edges_from([(1, 2, 3), (2, 3, 1), (1, 3, 7)])
path = nx.shortest_path(G, source=1, target=3, weight='weight')
length = nx.shortest_path_length(G, source=1, target=3, weight='weight')
# TSP：使用google OR-Tools或启发式
```

### 最小生成树
```python
mst = nx.minimum_spanning_tree(G, weight='weight')
```

## 七、可视化要点

```python
import matplotlib.pyplot as plt
import seaborn as sns
# 论文插图要求：
# - 中文字体：plt.rcParams['font.sans-serif'] = ['SimHei']
# - 高DPI：plt.savefig('fig.png', dpi=300, bbox_inches='tight')
# - 清晰的图例和轴标签
# - 配色方案：sns.color_palette("husl", 8)
```
