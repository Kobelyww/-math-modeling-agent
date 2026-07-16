---
name: mcm-model-selection
description: Reference guide for mathematical model selection — when to use differential equations, optimization, machine learning, graph theory, etc.
alwaysApply: false
---

# MCM/ICM Model Selection Reference

Quick reference for choosing the right mathematical model for each problem type.

## Optimization Problems (most common in MCM)
| Problem Type | Recommended Model | Solving Algorithm |
|-------------|-------------------|-------------------|
| Resource allocation | Linear/Integer Programming | Simplex, Branch & Bound |
| Multi-objective trade-offs | Multi-Objective Optimization | NSGA-II, MOEA/D |
| Scheduling/Timetabling | Mixed Integer Programming | Gurobi/CPLEX heuristic |
| Network flow | Min-Cost Max-Flow | Ford-Fulkerson, Dinic |
| Location selection | Facility Location Model | Genetic Algorithm, PSO |

## Prediction & Forecasting
| Problem Type | Recommended Model | Notes |
|-------------|-------------------|-------|
| Time series (trend) | ARIMA, SARIMA | Requires stationarity check |
| Time series (complex) | LSTM, Prophet | For non-linear patterns |
| Regression prediction | Multiple Linear / Ridge / Lasso | Feature engineering critical |
| Classification | Random Forest, XGBoost, SVM | Ensemble methods preferred |
| Small sample | Grey Model GM(1,1) | Classic MCM technique |

## Evaluation & Decision
| Problem Type | Recommended Model | Notes |
|-------------|-------------------|-------|
| Multi-criteria decision | AHP, TOPSIS, Entropy Weight | Combine for robustness |
| Fuzzy evaluation | Fuzzy Comprehensive Evaluation | For vague criteria |
| Efficiency evaluation | DEA (Data Envelopment Analysis) | Non-parametric |
| Risk assessment | Bayesian Network, Monte Carlo | Quantify uncertainty |

## Dynamic Systems
| Problem Type | Recommended Model | Notes |
|-------------|-------------------|-------|
| Population dynamics | ODE (Lotka-Volterra, SIR) | Continuous time |
| Discrete time evolution | Difference Equations | Discrete steps |
| Spatial spread | PDE (Diffusion/Reaction-Diffusion) | Continuous space+time |
| Agent-based | Cellular Automata, ABM | Complex emergent behavior |

## Graph & Network
| Problem Type | Recommended Model | Notes |
|-------------|-------------------|-------|
| Shortest path | Dijkstra, A* | Weighted graphs |
| Network robustness | Percolation Theory | Node/edge failure |
| Community detection | Louvain, Spectral Clustering | Modular structure |
| Influence spread | Independent Cascade, Linear Threshold | Social networks |

## Parameter Estimation & Sensitivity
- Always perform **sensitivity analysis** — vary key parameters ±20% and observe output changes
- Use **Monte Carlo simulation** for probabilistic sensitivity
- Report **Sobol indices** for global sensitivity when possible
- **Morris method** for screening unimportant parameters in high-dimensional models