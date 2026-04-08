# MELTS / alphaMELTS 使用指南与实际案例

> 基于 alphaMELTS 2.3.1 for Python + rhyolite-MELTS 1.0.2 的实际运行结果

## 目录

1. [软件简介](#1-软件简介)
2. [安装概要](#2-安装概要)
3. [Python API 快速入门](#3-python-api-快速入门)
4. [实际案例](#4-实际案例)
   - Case 1: 液相线温度
   - Case 2: 等压平衡结晶
   - Case 3: 分离结晶
   - Case 4: 水的影响
   - Case 5: 压力的影响
   - Case 6: 流纹岩地压计
   - Case 7: 弧玄武岩分异
5. [应用领域总结](#5-应用领域总结)
6. [引用文献](#6-引用文献)

---

## 1. 软件简介

MELTS 是岩浆热力学相平衡模拟软件，核心功能是：**给定岩浆成分 + 温压条件 → 通过 Gibbs 自由能最小化计算平衡矿物组合、比例和熔体成分**。

| 版本 | 适用范围 | 参考文献 |
|------|---------|---------|
| rhyolite-MELTS 1.0.2 | 500-2000 C, 0-2 GPa, 基性-酸性 | Ghiorso & Sack (1995); Gualda et al. (2012) |
| rhyolite-MELTS 1.1.0 | 同上 + CO2 混合流体 | Ghiorso & Gualda (2015) |
| rhyolite-MELTS 1.2.0 | 同上 + 新 H2O 模型 | Ghiorso & Gualda (2015) |
| pMELTS | 1000-2500 C, 1-3 GPa, 地幔橄榄岩 | Ghiorso et al. (2002) |

**alphaMELTS** 是 Caltech (Antoshechkina & Asimow) 开发的命令行/脚本前端，支持 Python、MATLAB 和批处理。

**关系**: alphaMELTS 和 MELTS GUI 共享完全相同的热力学引擎，通过 `.melts` 文件互通。

### 氧化物体系 (19 组分)

```
SiO2, TiO2, Al2O3, Fe2O3, Cr2O3, FeO, MnO, MgO,
NiO, CoO, CaO, Na2O, K2O, P2O5, H2O, CO2, SO3, Cl2O-1, F2O-1
```

---

## 2. 安装概要

安装路径: `~/proj/melts/`

```
~/proj/melts/
├── Melts-rhyolite-public              # GUI 版本 (需要 X11)
├── run-melts.sh                       # GUI 启动脚本 (处理 libpng12)
├── lib/libpng12.so.0                  # libpng12 兼容库
├── alphamelts-app/                    # 命令行独立版
│   └── alphamelts-app-2.3.1-linux/
│       └── alphamelts_linux           # 命令行可执行文件
├── alphamelts-py/                     # Python 接口
│   └── alphamelts-py-2.3.1-linux/
│       ├── meltsdynamic.py            # 入口类 MELTSdynamic
│       ├── meltsengine.py             # 计算引擎 MELTSengine
│       ├── meltsstatus.py             # 状态管理
│       └── libalphamelts.so           # C 动态库
├── run_cases.py                       # 本文档的运行脚本
└── MELTS_使用指南.md                  # 本文档
```

依赖: `pip install tinynumpy` (Python 接口需要)

---

## 3. Python API 快速入门

```python
import sys
sys.path.insert(0, '/home/laz/proj/melts/alphamelts-py/alphamelts-py-2.3.1-linux')
from meltsdynamic import MELTSdynamic

# 初始化 (1=rhyolite-MELTS 1.0.2, 2=pMELTS, 3=v1.1.0, 4=v1.2.0)
melts = MELTSdynamic(1)
eng = melts.engine

# 设置成分 (wt%)
eng.setBulkComposition('SiO2', 48.68)
eng.setBulkComposition('TiO2', 1.01)
eng.setBulkComposition('Al2O3', 17.64)
# ... 其余氧化物

# 设置温压条件
eng.temperature = 1200.0  # Celsius
eng.pressure = 1000.0     # bars

# 设置系统属性
eng.setSystemProperties(["Log fO2 Path: FMQ", "Mode: Fractionate Solids"])

# 找液相线 (runMode=0 触发内置液相线搜索)
eng.calcEquilibriumState(0, 0)
print(f"Liquidus T = {eng.temperature} C")

# 逐步平衡计算 (runMode=1=等压)
eng.temperature = 1200.0
eng.calcEquilibriumState(1, 0)  # outputFlag: 0=batch, 1=fractionation

# 读取结果
print(eng.solidNames)      # 稳定固相列表
print(eng.liquidNames)     # 液相列表
print(eng.logfO2)          # 氧逸度
print(eng.dispComposition) # 各相成分 (dict of arrays)
print(eng.mass)            # 各相质量
```

**注意**: C library 是全局单例，同一 Python 进程中创建多个 `MELTSdynamic` 实例可能导致 "libraryAlreadyInitialized" 警告。如需多次独立计算，建议使用子进程隔离或重用单一实例。

---

## 4. 实际案例

以下所有结果均为实际运行 alphaMELTS 2.3.1 Python 接口得到。

---

### Case 1: 液相线温度 (Liquidus Temperature)

**科学问题**: 给定岩浆成分和压力，岩浆开始结晶的温度是多少？第一个出现的矿物是什么？

**方法**: `eng.calcEquilibriumState(0, 0)` — 内置液相线搜索算法

**实际结果**:

| 成分 | P (bar) | T_liquidus (C) |
|------|---------|---------------|
| N-MORB (0.2% H2O) | 1000 | **1223.6** |
| N-MORB (2.0% H2O) | 1000 | **1194.5** |
| Arc Basalt (3% H2O) | 2000 | **1185.5** |
| Rhyolite (5.5% H2O) | 2000 | **813.7** |

**关键观察**:
- 水降低液相线温度: 干 MORB 1224 C → 含 2% 水 1195 C (降低 ~29 C)
- 流纹岩液相线极低 (814 C)，因为高 SiO2 + 高 H2O 大幅降低熔融温度
- 弧玄武岩含 3% 水，液相线比干 MORB 低约 38 C

---

### Case 2: 等压平衡结晶 (Equilibrium Crystallization)

**科学问题**: MORB 在浅部岩浆房 (500 bar) 冷却时，矿物出现的顺序和熔体成分如何演化？

**条件**: N-MORB, P=500 bar, 平衡(batch)结晶, fO2 未约束

**结晶序列**: plagioclase → olivine → clinopyroxene → spinel → apatite → fluid

**液相线演化 (Liquid Line of Descent)**:

| T (C) | SiO2 | MgO | CaO | FeO | Al2O3 | 矿物组合 |
|-------|------|-----|-----|-----|-------|---------|
| 1218 | 48.52 | 9.14 | 12.37 | 7.62 | 17.45 | plag |
| 1203 | 48.91 | 8.82 | 12.36 | 8.33 | 16.14 | ol + plag |
| 1188 | 49.21 | 8.29 | 12.31 | 9.11 | 15.00 | ol + cpx + plag |
| 1173 | 49.06 | 7.52 | 11.43 | 10.33 | 14.60 | ol + cpx + plag + sp |
| 1128 | 48.62 | 5.68 | 9.47 | 12.68 | 13.81 | ol + cpx + plag + sp |
| 1083 | 52.09 | 3.79 | 7.79 | 10.79 | 14.45 | ol + cpx + plag + sp |
| 1038 | 55.54 | 2.66 | 6.72 | 7.94 | 14.97 | ol + cpx + plag + sp + ap + fl |

**关键观察**:
- SiO2 从 ~48.5% 升至 ~55.5% (玄武岩 → 玄武安山岩)
- MgO 从 9.1% 降至 2.7% (橄榄石和辉石结晶消耗 Mg)
- FeO 先升后降 — 经典的拉斑玄武岩演化 (tholeiitic trend)：铁先在熔体中富集，后被尖晶石/磁铁矿消耗

---

### Case 3: 分离结晶 (Fractional Crystallization)

**科学问题**: 如果每步移除结晶的矿物（模拟岩浆房中矿物沉降），熔体能演化到多酸性？

**条件**: N-MORB, P=500 bar, fO2=FMQ, 分离结晶模式

**液相线演化**:

| T (C) | SiO2 | Al2O3 | FeO | MgO | CaO | Na2O | 矿物 |
|-------|------|-------|-----|-----|-----|------|------|
| 1222 | 48.49 | 17.50 | 7.09 | 9.10 | 12.38 | 2.64 | plag |
| 1174 | 49.24 | 14.47 | 10.00 | 7.54 | 10.96 | 3.46 | ol+cpx+plag+sp |
| 1126 | 49.29 | 12.91 | 13.43 | 5.44 | 8.41 | 4.50 | ol+cpx+plag+sp |
| 1078 | 54.96 | 11.85 | 12.27 | 3.01 | 6.02 | 6.43 | cpx+plag+sp |
| 1030 | 59.68 | 10.16 | 10.46 | 1.67 | 4.77 | 7.92 | cpx+plag+sp |
| 982 | 63.50 | 8.40 | 8.80 | 0.96 | 3.90 | 8.99 | cpx+plag+sp |
| 934 | 67.41 | 6.74 | 6.86 | 0.56 | 3.11 | 9.91 | cpx+plag+sp |
| 910 | 69.35 | 5.96 | 5.76 | 0.44 | 2.80 | 10.31 | cpx+plag+sp |

**熔体演化: SiO2 48.5% → 70.1% (玄武岩 → 流纹岩)**

**关键观察**:
- 分离结晶可以将玄武岩熔体驱动到流纹岩成分！
- 对比 Case 2 (平衡结晶只到 ~55.5% SiO2)，分离结晶更高效地分异
- Na2O 持续富集（从 2.6% 到 10.3%），因为 Na 是不相容元素
- 低温段出现两组辉石 (cpx1 + cpx2)

---

### Case 4: 水对结晶路径的影响

**科学问题**: 水如何改变 MORB 的结晶行为？这对理解俯冲带 vs 洋中脊岩浆至关重要。

**条件**: P=2000 bar, 平衡结晶

**对比结果**:

| | Dry (0.2% H2O) | Wet (2.0% H2O) |
|---|---|---|
| **T_liquidus** | 1229.9 C | ~1200 C |
| **首晶相** | plagioclase | olivine |
| **斜长石出现 T** | 1228 C | **1123 C** |

**Dry MORB 液相演化**:

| T (C) | SiO2 | Al2O3 | MgO | 矿物 |
|-------|------|-------|-----|------|
| 1228 | 48.52 | 17.44 | 9.15 | plag |
| 1188 | 48.48 | 15.69 | 7.36 | ol+cpx+plag+sp |
| 1148 | 47.87 | 15.00 | 5.77 | ol+cpx+plag+sp |
| 1108 | 49.78 | 15.39 | 4.18 | ol+cpx+plag+sp |
| 1068 | 52.84 | 16.19 | 3.01 | ol+cpx+plag+sp+ap |

**Wet MORB 液相演化**:

| T (C) | SiO2 | Al2O3 | MgO | 矿物 |
|-------|------|-------|-----|------|
| 1198 | 47.68 | 17.32 | 8.80 | ol |
| 1158 | 47.91 | 18.00 | 7.52 | ol+cpx |
| 1118 | 48.03 | 20.02 | 5.72 | ol+cpx+**plag**+sp |
| 1078 | 49.11 | 20.33 | 4.22 | ol+cpx+plag+sp |
| 1058 | 49.81 | 20.42 | 3.61 | ol+cpx+plag+sp |

**关键观察**:
- **水将斜长石出现温度从 1228 C 大幅降低到 1123 C (降低 ~105 C!)**
- 干 MORB 斜长石是首晶相；湿 MORB 中橄榄石先结晶
- 湿 MORB 中 Al2O3 持续升高到 ~20.4%（因为斜长石延迟结晶，Al 留在熔体中）
- 这解释了为什么弧岩浆（含水）产生高铝玄武岩，而洋脊岩浆（干）产生拉斑玄武岩

---

### Case 5: 压力对结晶的影响

**科学问题**: 相同成分岩浆在不同深度结晶，矿物出现顺序如何变化？

**结果**:

| P (bar) | ~深度 | T_liquidus | 结晶序列 |
|---------|-------|-----------|---------|
| 1 | 地表 | 1226.8 C | plag → fluid → ol → cpx → sp → rhm-oxide |
| 500 | ~2 km | ~1221 C | plag → ol → cpx → sp → ap → fluid |
| 2000 | ~7 km | ~1230 C | **ol → cpx → plag** → leucite → sp |
| 5000 | ~19 km | ~1270 C | **cpx → sp → plag** → ol → ap → opx |
| 10000 | ~38 km | ~1340 C | **cpx → sp → plag → garnet** → ap |

**关键观察**:
- 液相线温度随压力升高 (~1227 C @1 bar → ~1340 C @10 kbar)
- 低压: **斜长石是首晶相**（这是浅部 MORB 结晶的特征）
- 中压: **橄榄石或辉石成为首晶相**
- 高压 (>5 kbar): **单斜辉石成为首晶相**
- 10 kbar 出现**石榴石** — 指示深部地幔条件下的结晶
- 首晶相的压力依赖性是地质压力计的理论基础

---

### Case 6: 流纹岩地压计 (Rhyolite Geobarometry)

**科学问题**: 通过比较天然流纹岩中矿物组合与 MELTS 模型，能否反推岩浆储存深度？

**成分**: Bishop Tuff 型高硅流纹岩 (77.5% SiO2, 5.5% H2O)

**结果**:

| P (bar) | ~深度 | T_liquidus | T_feldspar | T_plagioclase |
|---------|-------|-----------|-----------|--------------|
| 500 | 1.9 km | 1052 C | 875 C | 877 C |
| 1000 | 3.8 km | ~900 C | 819 C | 821 C |
| 1750 | 6.6 km | ~900 C | 777 C | 775 C |
| 2500 | 9.4 km | ~900 C | 767 C | 749 C |

**关键观察**:
- 长石出现温度随压力升高而降低 (875 C @500 bar → 767 C @2500 bar)
- 斜长石和碱性长石出现温度非常接近 — 这是流纹岩的特征（长石共饱和）
- **应用**: 如果天然样品中观测到长石在 ~820 C 出现，则对应储存压力约 1000 bar (深度 ~4 km)
- 这就是 Gualda & Ghiorso 的 rhyolite-MELTS 地压计原理，已成功应用于 Bishop Tuff、Taupo、黄石等系统

---

### Case 7: 弧玄武岩分异 (Arc Basalt Differentiation)

**科学问题**: 俯冲带含水、高氧逸度的玄武岩如何分异？能演化到什么成分？

**条件**: Calc-alkaline arc basalt, 3% H2O, P=3000 bar, fO2=NNO, 分离结晶

**液相线演化**:

| T (C) | SiO2 | Al2O3 | MgO | CaO | Na2O | K2O | 矿物 |
|-------|------|-------|-----|-----|------|-----|------|
| 1190 | 50.38 | 16.32 | 7.84 | 10.38 | 2.77 | 0.49 | ol |
| 1130 | 50.72 | 17.71 | 5.85 | 10.04 | 3.05 | 0.55 | cpx |
| 1070 | 50.97 | 20.36 | 3.72 | 7.68 | 3.68 | 0.67 | cpx |
| 1010 | 53.05 | 21.36 | 2.33 | 5.76 | 4.39 | 0.83 | opx+cpx+plag+sp |
| 950 | 55.72 | 20.62 | 1.40 | 4.36 | 5.11 | 1.04 | opx+plag+sp |
| 890 | 57.64 | 19.88 | 0.84 | 3.14 | 5.58 | 1.24 | opx+plag+sp |
| 830 | 59.39 | 19.15 | 0.47 | 2.00 | 5.82 | 1.48 | opx+plag+rutile+sp |
| 800 | 60.53 | 18.88 | 0.34 | 1.45 | 5.78 | 1.66 | opx+plag+rutile+sp |

**演化: SiO2 50.4% → 60.5% (玄武岩 → 安山岩)**

**关键观察 (对比干 MORB Case 3)**:

| 特征 | 干 MORB (Case 3) | 弧玄武岩 (Case 7) |
|------|-----------------|-----------------|
| 演化趋势 | **拉斑 (tholeiitic)**: FeO 先升后降 | **钙碱性 (calc-alkaline)**: FeO 持续下降 |
| Al2O3 | 持续降低 (17→6%) | 先升后缓降 (16→19%) |
| 水的作用 | 几乎无 | 抑制斜长石，水饱和前 Al 富集 |
| SiO2 终点 | 70% (流纹岩) | 60% (安山岩) |
| 出现 opx | 否 | 是 — 这是 calc-alkaline 系列的标志 |

---

## 5. 应用领域总结

| 领域 | 典型计算 | 代表文献 |
|------|---------|---------|
| **超级火山/喷发** | 地压计 (石英+长石共饱和) | Gualda & Ghiorso (2013) |
| **活火山监测** | 液相线演化、相平衡 | Campi Flegrei, Cordon Caulle |
| **大洋中脊** | 等熵减压熔融 (pMELTS) | Smith & Asimow (2005) |
| **地幔动力学** | 多相流+热力学耦合 | Tirone (2017-2020) |
| **俯冲带/弧岩浆** | 含水分离结晶 | Case 7 |
| **月球科学** | 岩浆洋结晶 | EPSL (2021) |
| **火星科学** | 矿物化学预测 vs 火星车观测 | Payre et al. (2020) |
| **系外行星** | 岩浆洋蒸气大气 (VapoRock) | Wolf et al. (2023) ApJ |
| **冰盖-火山反馈** | 冰盖卸载→减压熔融 | Coonin et al. (2024) |

---

## 6. 引用文献

使用 MELTS 发表论文时需引用以下文献:

- **MELTS**: Ghiorso M.S. & Sack R.O. (1995) Chemical mass transfer in magmatic processes IV. A revised and internally consistent thermodynamic model for the interpolation and extrapolation of liquid-solid equilibria in magmatic systems at elevated temperatures and pressures. *Contrib Mineral Petrol*, 119, 197-212.
- **pMELTS**: Ghiorso M.S., Hirschmann M.M., Reiners P.W. & Kress V.C. III (2002) The pMELTS: A revision of MELTS for improved calculation of phase relations and major element partitioning related to partial melting of the mantle to 3 GPa. *Geochem Geophys Geosyst*, 3(5).
- **rhyolite-MELTS**: Gualda G.A.R., Ghiorso M.S., Lemons R.V. & Carley T.L. (2012) Rhyolite-MELTS: a Modified Calibration of MELTS Optimized for Silica-rich, Fluid-bearing Magmatic Systems. *J Petrol*, 53, 875-890.
- **alphaMELTS**: Smith P.M. & Asimow P.D. (2005) Adiabat_1ph: A new public front-end to the MELTS, pMELTS, and pHMELTS models. *Geochem Geophys Geosyst*, 6.

---

## 附录: 运行本文档的案例

```bash
# 运行所有 7 个案例
python3 ~/proj/melts/run_cases.py

# 或者运行单个快速测试
python3 -c "
import sys
sys.path.insert(0, '$HOME/proj/melts/alphamelts-py/alphamelts-py-2.3.1-linux')
from meltsdynamic import MELTSdynamic
melts = MELTSdynamic(1)
eng = melts.engine
eng.setBulkComposition('SiO2', 48.68)
eng.setBulkComposition('Al2O3', 17.64)
eng.setBulkComposition('FeO', 7.59)
eng.setBulkComposition('MgO', 9.10)
eng.setBulkComposition('CaO', 12.45)
eng.setBulkComposition('Na2O', 2.65)
eng.pressure = 1000.0
eng.temperature = 1300.0
eng.calcEquilibriumState(0, 0)
print(f'Liquidus T = {eng.temperature:.1f} C')
"
```
