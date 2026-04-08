#!/usr/bin/env python3
"""
MELTS Use Cases - 实际运行案例集
=================================
每个 case 作为独立子进程运行，避免 C library 单例问题。
"""
import subprocess, sys, os, textwrap

PYLIB = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    'alphamelts-py', 'alphamelts-py-2.3.1-linux')

def run_case(code, label):
    """Run a case as a subprocess, capture only stdout (C output goes to stderr)."""
    wrapper = textwrap.dedent(f"""
import sys, os
sys.path.insert(0, {PYLIB!r})
# Redirect C library output (fd 1) to stderr so Python print is clean
_pipe_r, _pipe_w = os.pipe()
_old_fd1 = os.dup(1)
os.dup2(2, 1)  # C library stdout -> stderr
sys.stdout = os.fdopen(_old_fd1, 'w')  # Python print -> original stdout
{code}
""")
    result = subprocess.run([sys.executable, '-c', wrapper],
                          capture_output=True, text=True, timeout=300)
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.returncode != 0:
        # Extract just the error, not all C output
        err_lines = [l for l in result.stderr.split('\n')
                     if 'Traceback' in l or 'Error' in l or 'error' in l.lower()]
        if err_lines:
            print(f"  [Error: {err_lines[-1].strip()}]")


# ============================================================
CASE1 = r'''
from meltsdynamic import MELTSdynamic

MORB = {'SiO2':48.68,'TiO2':1.01,'Al2O3':17.64,'Fe2O3':0.89,'Cr2O3':0.03,
        'FeO':7.59,'MgO':9.10,'CaO':12.45,'Na2O':2.65,'K2O':0.03,'P2O5':0.08,'H2O':0.20}
WET_MORB = {**MORB, 'H2O': 2.00}

def do(name, comp, pres):
    melts = MELTSdynamic(1)
    eng = melts.engine
    for ox, val in comp.items():
        eng.setBulkComposition(ox, val)
    eng.pressure = float(pres)
    eng.temperature = 1300.0
    eng.calcEquilibriumState(0, 0)
    T = eng.temperature
    phase = eng.solidNames[0] if eng.solidNames else '?'
    return T, phase

print("给定岩浆成分和压力，找到液相线温度和首晶矿物相。\n")
print(f"  {'Composition':30s} {'P(bar)':>8} {'T_liquidus':>12} {'首晶相':>20}")
print(f"  {'-'*30} {'-'*8} {'-'*12} {'-'*20}")
T, p = do('MORB dry', MORB, 1000)
print(f"  {'N-MORB (0.2% H2O)':30s} {1000:8d} {T:10.1f} C {p:>20s}")
'''

CASE1B = r'''
from meltsdynamic import MELTSdynamic
MORB = {'SiO2':48.68,'TiO2':1.01,'Al2O3':17.64,'Fe2O3':0.89,'Cr2O3':0.03,
        'FeO':7.59,'MgO':9.10,'CaO':12.45,'Na2O':2.65,'K2O':0.03,'P2O5':0.08,'H2O':2.0}
melts = MELTSdynamic(1)
eng = melts.engine
for ox, val in MORB.items(): eng.setBulkComposition(ox, val)
eng.pressure = 1000.0; eng.temperature = 1300.0
eng.calcEquilibriumState(0, 0)
T = eng.temperature; phase = eng.solidNames[0] if eng.solidNames else '?'
print(f"  {'N-MORB (2.0% H2O)':30s} {1000:8d} {T:10.1f} C {phase:>20s}")
'''

CASE1C = r'''
from meltsdynamic import MELTSdynamic
comp = {'SiO2':51.0,'TiO2':0.80,'Al2O3':16.5,'Fe2O3':1.50,'FeO':6.50,
        'MgO':8.00,'CaO':10.50,'Na2O':2.80,'K2O':0.50,'P2O5':0.15,'H2O':3.0}
melts = MELTSdynamic(1)
eng = melts.engine
for ox, val in comp.items(): eng.setBulkComposition(ox, val)
eng.pressure = 2000.0; eng.temperature = 1300.0
eng.calcEquilibriumState(0, 0)
T = eng.temperature; phase = eng.solidNames[0] if eng.solidNames else '?'
print(f"  {'Arc Basalt (3% H2O)':30s} {2000:8d} {T:10.1f} C {phase:>20s}")
'''

CASE1D = r'''
from meltsdynamic import MELTSdynamic
comp = {'SiO2':77.5,'TiO2':0.08,'Al2O3':12.5,'Fe2O3':0.21,'FeO':0.47,
        'MgO':0.03,'CaO':0.43,'Na2O':3.98,'K2O':4.88,'H2O':5.5}
melts = MELTSdynamic(1)
eng = melts.engine
for ox, val in comp.items(): eng.setBulkComposition(ox, val)
eng.pressure = 2000.0; eng.temperature = 900.0
eng.calcEquilibriumState(0, 0)
T = eng.temperature; phase = eng.solidNames[0] if eng.solidNames else '?'
print(f"  {'Rhyolite (5.5% H2O)':30s} {2000:8d} {T:10.1f} C {phase:>20s}")
'''

# ============================================================
CASE2 = r'''
from meltsdynamic import MELTSdynamic

MORB = {'SiO2':48.68,'TiO2':1.01,'Al2O3':17.64,'Fe2O3':0.89,'Cr2O3':0.03,
        'FeO':7.59,'MgO':9.10,'CaO':12.45,'Na2O':2.65,'K2O':0.03,'P2O5':0.08,'H2O':0.20}
OX = ['SiO2','TiO2','Al2O3','Fe2O3','Cr2O3','FeO','MnO','MgO','NiO','CoO','CaO','Na2O','K2O','P2O5','H2O','CO2','SO3','Cl2O-1','F2O-1']

melts = MELTSdynamic(1)
eng = melts.engine
for ox, val in MORB.items(): eng.setBulkComposition(ox, val)
eng.pressure = 500.0
eng.temperature = 1300.0
eng.calcEquilibriumState(0, 0)
T_liq = eng.temperature
first = eng.solidNames[0] if eng.solidNames else '?'

print("MORB 500 bar 下逐步冷却，矿物与熔体保持化学平衡。\n")
print(f"Liquidus T = {T_liq:.1f} C, 首晶相 = {first}\n")
print(f"  {'T(C)':>7} {'SiO2':>7} {'MgO':>6} {'CaO':>6} {'FeO':>6} {'Al2O3':>7} {'矿物组合'}")
print(f"  {'-'*7} {'-'*7} {'-'*6} {'-'*6} {'-'*6} {'-'*7} {'-'*45}")

T = T_liq - 2
step = 0
while T > 1000:
    eng.temperature = T
    eng.calcEquilibriumState(1, 0)
    if eng.status.failed: break
    if eng.liquidNames and 'liquid1' in eng.liquidNames:
        d = eng.dispComposition.get('liquid1')
        if d and step % 3 == 0:
            lc = {OX[i]: float(d[i]) for i in range(len(OX))}
            solids = ', '.join(eng.solidNames) if eng.solidNames else ''
            print(f"  {T:7.0f} {lc['SiO2']:7.2f} {lc['MgO']:6.2f} {lc['CaO']:6.2f} {lc['FeO']:6.2f} {lc['Al2O3']:7.2f} {solids}")
    T -= 5
    step += 1
'''

# ============================================================
CASE3 = r'''
from meltsdynamic import MELTSdynamic
OX = ['SiO2','TiO2','Al2O3','Fe2O3','Cr2O3','FeO','MnO','MgO','NiO','CoO','CaO','Na2O','K2O','P2O5','H2O','CO2','SO3','Cl2O-1','F2O-1']
MORB = {'SiO2':48.68,'TiO2':1.01,'Al2O3':17.64,'Fe2O3':0.89,'Cr2O3':0.03,
        'FeO':7.59,'MgO':9.10,'CaO':12.45,'Na2O':2.65,'K2O':0.03,'P2O5':0.08,'H2O':0.20}

melts = MELTSdynamic(1)
eng = melts.engine
for ox, val in MORB.items(): eng.setBulkComposition(ox, val)
eng.pressure = 500.0; eng.temperature = 1300.0
eng.setSystemProperties(["Log fO2 Path: FMQ", "Mode: Fractionate Solids"])
eng.calcEquilibriumState(0, 0)
T_liq = eng.temperature
first = eng.solidNames[0] if eng.solidNames else '?'

print("MORB 分离结晶(P=500 bar, fO2=FMQ)。每步移除结晶固相。\n")
print(f"Liquidus T = {T_liq:.1f} C, 首晶相 = {first}\n")
print(f"  {'T(C)':>7} {'SiO2':>7} {'Al2O3':>7} {'FeO':>7} {'MgO':>6} {'CaO':>6} {'Na2O':>6} {'矿物'}")
print(f"  {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*6} {'-'*6} {'-'*6} {'-'*35}")

T = T_liq - 1; step = 0; f_sio2 = l_sio2 = 0
while T > 900:
    eng.temperature = T
    eng.calcEquilibriumState(1, 1)
    if eng.status.failed: break
    if eng.liquidNames and 'liquid1' in eng.liquidNames:
        d = eng.dispComposition.get('liquid1')
        if d:
            lc = {OX[i]: float(d[i]) for i in range(len(OX))}
            if step == 0: f_sio2 = lc['SiO2']
            l_sio2 = lc['SiO2']
            if step % 8 == 0:
                solids = ', '.join(list(eng.solidNames)[:4]) if eng.solidNames else ''
                print(f"  {T:7.0f} {lc['SiO2']:7.2f} {lc['Al2O3']:7.2f} {lc['FeO']:7.2f} {lc['MgO']:6.2f} {lc['CaO']:6.2f} {lc['Na2O']:6.2f} {solids}")
    T -= 3; step += 1
print(f"\n熔体演化: SiO2 {f_sio2:.1f}% -> {l_sio2:.1f}%")
'''

# ============================================================
CASE4 = r'''
from meltsdynamic import MELTSdynamic
OX = ['SiO2','TiO2','Al2O3','Fe2O3','Cr2O3','FeO','MnO','MgO','NiO','CoO','CaO','Na2O','K2O','P2O5','H2O','CO2','SO3','Cl2O-1','F2O-1']
MORB = {'SiO2':48.68,'TiO2':1.01,'Al2O3':17.64,'Fe2O3':0.89,'Cr2O3':0.03,
        'FeO':7.59,'MgO':9.10,'CaO':12.45,'Na2O':2.65,'K2O':0.03,'P2O5':0.08,'H2O':0.20}

print("对比干/湿 MORB 在 2000 bar 下的结晶差异。")
print("水会抑制斜长石稳定性、降低液相线温度。\n")

for label, h2o in [('Dry (0.2% H2O)', 0.2), ('Wet (2.0% H2O)', 2.0)]:
    melts = MELTSdynamic(1)
    eng = melts.engine
    comp = {**MORB, 'H2O': h2o}
    for ox, val in comp.items(): eng.setBulkComposition(ox, val)
    eng.pressure = 2000.0; eng.temperature = 1400.0
    eng.calcEquilibriumState(0, 0)
    T_liq = eng.temperature
    first = eng.solidNames[0] if eng.solidNames else '?'
    plag_T = None
    print(f"--- {label} ---")
    print(f"Liquidus T = {T_liq:.1f} C, 首晶相 = {first}")
    print(f"  {'T(C)':>7} {'SiO2':>7} {'Al2O3':>7} {'MgO':>6} {'矿物'}")
    print(f"  {'-'*7} {'-'*7} {'-'*7} {'-'*6} {'-'*40}")
    T = T_liq - 2; step = 0
    while T > 1050:
        eng.temperature = T
        eng.calcEquilibriumState(1, 0)
        if eng.status.failed: break
        solids = list(eng.solidNames) if eng.solidNames else []
        if plag_T is None and any('plagioclase' in s for s in solids):
            plag_T = T
        if eng.liquidNames and 'liquid1' in eng.liquidNames:
            d = eng.dispComposition.get('liquid1')
            if d and step % 4 == 0:
                lc = {OX[i]: float(d[i]) for i in range(len(OX))}
                phases = ', '.join(solids)
                print(f"  {T:7.0f} {lc['SiO2']:7.2f} {lc['Al2O3']:7.2f} {lc['MgO']:6.2f} {phases}")
        T -= 5; step += 1
    if plag_T:
        print(f"  -> 斜长石出现温度: {plag_T:.0f} C")
    print()
'''

# ============================================================
CASE5 = r'''
from meltsdynamic import MELTSdynamic
MORB = {'SiO2':48.68,'TiO2':1.01,'Al2O3':17.64,'Fe2O3':0.89,'Cr2O3':0.03,
        'FeO':7.59,'MgO':9.10,'CaO':12.45,'Na2O':2.65,'K2O':0.03,'P2O5':0.08,'H2O':0.20}

print("同一 MORB 成分在不同压力下的液相线和结晶序列。\n")
print(f"  {'P(bar)':>8} {'T_liq(C)':>10} {'首晶相':>18} {'结晶序列'}")
print(f"  {'-'*8} {'-'*10} {'-'*18} {'-'*50}")

for P in [1, 500, 2000, 5000, 10000]:
    melts = MELTSdynamic(1)
    eng = melts.engine
    for ox, val in MORB.items(): eng.setBulkComposition(ox, val)
    eng.pressure = float(P); eng.temperature = 1400.0
    eng.calcEquilibriumState(0, 0)
    T_liq = eng.temperature
    first = eng.solidNames[0] if eng.solidNames else '?'
    phases_seen = []
    T = T_liq - 2
    while T > 1000:
        eng.temperature = T
        eng.calcEquilibriumState(1, 0)
        if eng.status.failed: break
        for s in (eng.solidNames or []):
            base = s.rstrip('0123456789')
            if base not in phases_seen: phases_seen.append(base)
        T -= 5
    seq = ' -> '.join(phases_seen[:6])
    print(f"  {P:8d} {T_liq:8.1f} C {first:>18s} {seq}")
'''

# ============================================================
CASE6 = r'''
from meltsdynamic import MELTSdynamic
comp = {'SiO2':77.5,'TiO2':0.08,'Al2O3':12.5,'Fe2O3':0.21,'FeO':0.47,
        'MgO':0.03,'CaO':0.43,'Na2O':3.98,'K2O':4.88,'H2O':5.5}

print("高硅流纹岩(Bishop Tuff)在不同压力下的矿物出现温度。")
print("用于地压计：反推岩浆储存深度。\n")
print(f"  {'P(bar)':>8} {'~depth':>8} {'T_liq':>8} {'T_qtz':>8} {'T_fspar':>8} {'T_plag':>8}")
print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

for P in [500, 1000, 1750, 2500]:
    melts = MELTSdynamic(1)
    eng = melts.engine
    for ox, val in comp.items(): eng.setBulkComposition(ox, val)
    eng.pressure = float(P); eng.temperature = 900.0
    eng.calcEquilibriumState(0, 0)
    T_liq = eng.temperature
    qtz_T = fsp_T = plag_T = None
    T = T_liq - 1
    while T > 650:
        eng.temperature = T
        eng.calcEquilibriumState(1, 0)
        if eng.status.failed: break
        ss = ' '.join(eng.solidNames) if eng.solidNames else ''
        if 'quartz' in ss and qtz_T is None: qtz_T = T
        if ('feldspar' in ss or 'sanidine' in ss) and fsp_T is None: fsp_T = T
        if 'plagioclase' in ss and plag_T is None: plag_T = T
        T -= 2
    depth = P * 100 / (2700 * 9.81)
    q = f"{qtz_T:.0f}" if qtz_T else "-"
    f = f"{fsp_T:.0f}" if fsp_T else "-"
    p = f"{plag_T:.0f}" if plag_T else "-"
    print(f"  {P:8d} {depth:6.1f}km {T_liq:6.1f}C {q:>8} {f:>8} {p:>8}")
'''

# ============================================================
CASE7 = r'''
from meltsdynamic import MELTSdynamic
OX = ['SiO2','TiO2','Al2O3','Fe2O3','Cr2O3','FeO','MnO','MgO','NiO','CoO','CaO','Na2O','K2O','P2O5','H2O','CO2','SO3','Cl2O-1','F2O-1']
comp = {'SiO2':51.0,'TiO2':0.80,'Al2O3':16.5,'Fe2O3':1.50,'FeO':6.50,
        'MgO':8.00,'CaO':10.50,'Na2O':2.80,'K2O':0.50,'P2O5':0.15,'H2O':3.0}

melts = MELTSdynamic(1)
eng = melts.engine
for ox, val in comp.items(): eng.setBulkComposition(ox, val)
eng.pressure = 3000.0; eng.temperature = 1300.0
eng.setSystemProperties(["Log fO2 Path: NNO", "Mode: Fractionate Solids"])
eng.calcEquilibriumState(0, 0)
T_liq = eng.temperature
first = eng.solidNames[0] if eng.solidNames else '?'

print(f"弧玄武岩(3%H2O)分离结晶, P=3000 bar, fO2=NNO\n")
print(f"Liquidus T = {T_liq:.1f} C, 首晶相 = {first}\n")
print(f"  {'T(C)':>7} {'SiO2':>7} {'Al2O3':>7} {'MgO':>6} {'CaO':>6} {'Na2O':>6} {'K2O':>6} {'矿物'}")
print(f"  {'-'*7} {'-'*7} {'-'*7} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*35}")

T = T_liq - 1; step = 0; f_sio2 = l_sio2 = 0
while T > 800:
    eng.temperature = T
    eng.calcEquilibriumState(1, 1)
    if eng.status.failed: break
    if eng.liquidNames and 'liquid1' in eng.liquidNames:
        d = eng.dispComposition.get('liquid1')
        if d:
            lc = {OX[i]: float(d[i]) for i in range(len(OX))}
            if step == 0: f_sio2 = lc['SiO2']
            l_sio2 = lc['SiO2']
            if step % 10 == 0:
                solids = ', '.join(list(eng.solidNames)[:4]) if eng.solidNames else ''
                print(f"  {T:7.0f} {lc['SiO2']:7.2f} {lc['Al2O3']:7.2f} {lc['MgO']:6.2f} {lc['CaO']:6.2f} {lc['Na2O']:6.2f} {lc['K2O']:6.2f} {solids}")
    T -= 3; step += 1
if f_sio2 and l_sio2:
    rock = "流纹岩" if l_sio2>69 else "英安岩" if l_sio2>63 else "安山岩" if l_sio2>57 else "玄武安山岩" if l_sio2>52 else "玄武岩"
    print(f"\n演化: SiO2 {f_sio2:.1f}% -> {l_sio2:.1f}% ({rock})")
'''

# ============================================================
if __name__ == '__main__':
    print("="*70)
    print("  MELTS Use Cases — 实际运行案例集")
    print("  alphaMELTS 2 for Python | rhyolite-MELTS 1.0.2")
    print("="*70)

    run_case(CASE1, "CASE 1: 液相线温度 (Liquidus Temperature)")
    run_case(CASE1B, "CASE 1 (续)")
    run_case(CASE1C, "CASE 1 (续)")
    run_case(CASE1D, "CASE 1 (续)")
    run_case(CASE2, "CASE 2: 等压平衡结晶 (Equilibrium Crystallization)")
    run_case(CASE3, "CASE 3: 分离结晶 (Fractional Crystallization)")
    run_case(CASE4, "CASE 4: 水的影响 (Effect of H2O)")
    run_case(CASE5, "CASE 5: 压力的影响 (Pressure Effect)")
    run_case(CASE6, "CASE 6: 流纹岩地压计 (Rhyolite Geobarometry)")
    run_case(CASE7, "CASE 7: 弧玄武岩分异 (Arc Basalt Differentiation)")

    print("\n" + "="*70)
    print("  All cases completed!")
    print("="*70)
