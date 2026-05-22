"""
calc_transicao.py — Módulo de cálculo para Curva Espiral de Transição (Clotóide)
Referência: Antas P. M. et al, 2016. Método do Raio Conservado – Simetria de Concordância.

Fórmulas principais (numeração do documento de referência):
  Eq. 1.88  Φ = le / (2R)
  Eq. 1.89  x = l [1 - φ²/10 + φ⁴/216]
  Eq. 1.90  y = (l·φ/3) [1 - φ²/14 + φ⁴/440]
  Eq. 1.82  p = Yc - R(1 - cosΦ)
  Eq. 1.83  q = Xc - R·senΦ
  Eq. 1.84  TT = q + (R+p)·tg(AC/2)
  Eq. 1.85  t  = p·sec(AC/2)
  Eq. 1.86  Es = (p+R)·sec(AC/2) - R
  Eq. 1.96  le_min (Barnett) = 0,036·v³/R
  Eq. 1.101 le_max = R·AC·π/180
  Eq. 1.102 le_des (Shortt) = 0,071·v³/R
  Eq. 1.87  φ = l² / (2·R·le)
  Eq. 1.104 ds_l = (180/π)·arctan(y/x)  [graus]
"""

import math


# ─────────────────────────────────────────────────────────────
# Funções auxiliares
# ─────────────────────────────────────────────────────────────

def _dms(deg_dec):
    """Converte graus decimais para (grau, min, seg)."""
    d = int(deg_dec)
    m_frac = (deg_dec - d) * 60
    m = int(m_frac)
    s = (m_frac - m) * 60
    return d, m, s


def _dms_str(deg_dec):
    d, m, s = _dms(deg_dec)
    return f"{d:02d}° {m:02d}' {s:05.2f}\""


def m_to_stake(m, spacing=20):
    """Converte distância em metros para notação de estaca (inteira, fração)."""
    stake = int(m // spacing)
    frac = m - stake * spacing
    return stake, round(frac, 4)


def stake_to_m(stake, frac, spacing=20):
    return stake * spacing + frac


# ─────────────────────────────────────────────────────────────
# Comprimentos de transição
# ─────────────────────────────────────────────────────────────

def comprimentos_transicao(v, R, AC_deg):
    """
    Calcula le_min (Barnett), le_max e le_des (Shortt).
    Retorna le_des arredondado para cima ao múltiplo de 5.
    """
    le_min = 0.036 * v**3 / R
    le_max = R * AC_deg * math.pi / 180
    le_des_raw = 0.071 * v**3 / R
    le_des = math.ceil(le_des_raw / 5) * 5
    return {
        'le_min':     round(le_min, 4),
        'le_max':     round(le_max, 4),
        'le_des_raw': round(le_des_raw, 4),
        'le_des':     float(le_des),
    }


# ─────────────────────────────────────────────────────────────
# Elementos geométricos da espiral
# ─────────────────────────────────────────────────────────────

def elementos_espiral(v, R, AC_deg, le):
    """
    Calcula todos os elementos geométricos da curva espiral de transição.
    Retorna dicionário com Φ, Xc, Yc, q, p, TT, t, Es, θ, Dθ.
    """
    # Ângulo central da espiral (rad)
    Phi = le / (2 * R)
    Phi2 = Phi ** 2
    Phi4 = Phi ** 4

    # Coordenadas do ponto SC
    Xc = le * (1 - Phi2 / 10 + Phi4 / 216)
    Yc = (le * Phi / 3) * (1 - Phi2 / 14 + Phi4 / 440)

    # Coordenadas PC' (ponto circular transladado)
    q = Xc - R * math.sin(Phi)
    p = Yc - R * (1 - math.cos(Phi))

    AC_rad = math.radians(AC_deg)
    TT = q + (R + p) * math.tan(AC_rad / 2)
    t  = p / math.cos(AC_rad / 2)
    Es = (p + R) / math.cos(AC_rad / 2) - R

    # Ângulo central do trecho circular
    Phi_deg = math.degrees(Phi)
    theta_deg = AC_deg - 2 * Phi_deg
    theta_rad = math.radians(theta_deg)
    Dtheta = R * theta_rad

    return {
        'Phi_rad':   Phi,
        'Phi_deg':   Phi_deg,
        'Phi_dms':   _dms_str(Phi_deg),
        'Xc':        round(Xc, 6),
        'Yc':        round(Yc, 6),
        'q':         round(q, 6),
        'p':         round(p, 6),
        'TT':        round(TT, 6),
        't':         round(t, 6),
        'Es':        round(Es, 6),
        'theta_deg': round(theta_deg, 6),
        'theta_dms': _dms_str(theta_deg),
        'Dtheta':    round(Dtheta, 6),
    }


# ─────────────────────────────────────────────────────────────
# Estaqueamento dos pontos notáveis
# ─────────────────────────────────────────────────────────────

def estaqueamento_pontos(PI_stake, PI_frac, TT, le, Dtheta, spacing=20):
    """
    Calcula as estacas TS, SC, CS e ST.
    PI_stake: estaca inteira do PI
    PI_frac:  fração em metros do PI
    """
    PI_m  = stake_to_m(PI_stake, PI_frac, spacing)
    TS_m  = PI_m - TT
    SC_m  = TS_m + le
    CS_m  = SC_m + Dtheta
    ST_m  = CS_m + le

    return {
        'PI':  (PI_stake, PI_frac, PI_m),
        'TS':  (*m_to_stake(TS_m, spacing), TS_m),
        'SC':  (*m_to_stake(SC_m, spacing), SC_m),
        'CS':  (*m_to_stake(CS_m, spacing), CS_m),
        'ST':  (*m_to_stake(ST_m, spacing), ST_m),
    }


# ─────────────────────────────────────────────────────────────
# Ponto genérico da espiral
# ─────────────────────────────────────────────────────────────

def ponto_espiral(l, R, le):
    """
    Calcula φ, x, y e ds para um ponto à distância l da origem TS.
    ds é a deflexão acumulada em graus decimais (e DMS).
    """
    phi  = l**2 / (2 * R * le)
    phi2 = phi**2
    phi4 = phi**4

    x = l * (1 - phi2 / 10 + phi4 / 216)
    y = (l * phi / 3) * (1 - phi2 / 14 + phi4 / 440)

    ds_rad = math.atan2(y, x) if x != 0 else 0.0
    ds_deg = math.degrees(ds_rad)

    return {
        'phi_rad': phi,
        'phi_deg': math.degrees(phi),
        'x':       round(x, 6),
        'y':       round(y, 6),
        'ds_deg':  round(ds_deg, 7),
        'ds_dms':  _dms_str(ds_deg),
    }


# ─────────────────────────────────────────────────────────────
# Caderneta de locação (tabela de estaqueamento)
# ─────────────────────────────────────────────────────────────

def caderneta_locacao(R, le, TS_m, SC_m, spacing=20):
    """
    Gera todas as linhas da caderneta de locação da espiral.
    Retorna lista de dicts com: stake_int, stake_frac, chord, l, phi, x, y, ds_deg, ds_dms
    """
    first_int = math.ceil(TS_m / spacing)
    last_int  = math.floor(SC_m / spacing)

    positions_m = [TS_m]
    for s in range(first_int, last_int + 1):
        pos = s * spacing
        if abs(pos - TS_m) > 1e-9 and abs(pos - SC_m) > 1e-9:
            positions_m.append(pos)
    if abs(SC_m - TS_m) > 1e-9:
        positions_m.append(SC_m)
    positions_m.sort()

    rows = []
    for i, pos_m in enumerate(positions_m):
        l     = round(pos_m - TS_m, 6)
        chord = round(pos_m - positions_m[i - 1], 4) if i > 0 else 0.0
        pt    = ponto_espiral(l, R, le)

        si, sf = m_to_stake(pos_m, spacing)
        rows.append({
            'stake_int':  si,
            'stake_frac': round(sf, 2),
            'chord_m':    chord,
            'l':          l,
            'phi_rad':    round(pt['phi_rad'], 6),
            'x':          pt['x'],
            'y':          pt['y'],
            'ds_deg':     pt['ds_deg'],
            'ds_dms':     pt['ds_dms'],
        })
    return rows


# ─────────────────────────────────────────────────────────────
# Solução completa (todos os exercícios de uma vez)
# ─────────────────────────────────────────────────────────────

def solucao_completa(v, R, AC_deg, e, lf, PI_stake, PI_frac, spacing=20, chord_base=20):
    """
    Executa o roteiro completo para uma curva espiral de transição.
    Retorna dict com todos os resultados agrupados.
    """
    comp  = comprimentos_transicao(v, R, AC_deg)
    le    = comp['le_des']
    elem  = elementos_espiral(v, R, AC_deg, le)
    pts   = estaqueamento_pontos(PI_stake, PI_frac, elem['TT'], le, elem['Dtheta'], spacing)
    table = caderneta_locacao(R, le, pts['TS'][2], pts['SC'][2], spacing)

    return {
        'entrada': {'v': v, 'R': R, 'AC_deg': AC_deg, 'e': e, 'lf': lf,
                    'PI_stake': PI_stake, 'PI_frac': PI_frac,
                    'spacing': spacing, 'chord_base': chord_base},
        'comprimentos': comp,
        'elementos': elem,
        'estaqueamento': pts,
        'caderneta': table,
    }


# ─────────────────────────────────────────────────────────────
# Impressão de resultados
# ─────────────────────────────────────────────────────────────

def print_resultado(res):
    e = res['entrada']
    c = res['comprimentos']
    el = res['elementos']
    pt = res['estaqueamento']
    tb = res['caderneta']

    print("=" * 65)
    print("CURVA ESPIRAL DE TRANSIÇÃO — SOLUÇÃO COMPLETA")
    print("=" * 65)
    print(f"  v = {e['v']} km/h  |  R = {e['R']} m  |  AC = {e['AC_deg']}°")
    print(f"  e = {e['e']}%  |  lf = {e['lf']} m  |  Est.(PI) = {e['PI_stake']}+{e['PI_frac']:.2f}")
    print()

    print("─── Ex. 1  Comprimentos de transição ───────────────────────")
    print(f"  le_min  (Barnett) = {c['le_min']:.2f} m")
    print(f"  le_max            = {c['le_max']:.2f} m")
    print(f"  le_des  (Shortt)  = {c['le_des_raw']:.2f} m  →  arredondado: {c['le_des']:.2f} m")
    print(f"  Verificação: {c['le_min']:.2f} ≤ {c['le_des']:.2f} ≤ {c['le_max']:.2f}  ✓")
    print()

    print("─── Ex. 2  Elementos da espiral (le = {:.2f} m) ─────────────".format(c['le_des']))
    print(f"  Φ  = {el['Phi_rad']:.6f} rad  =  {el['Phi_dms']}")
    print(f"  Xc = {el['Xc']:.6f} m  ≅  {el['Xc']:.2f} m")
    print(f"  Yc = {el['Yc']:.6f} m  ≅  {el['Yc']:.2f} m")
    print(f"  q  = {el['q']:.6f} m  ≅  {el['q']:.2f} m")
    print(f"  p  = {el['p']:.6f} m  ≅  {el['p']:.2f} m")
    print(f"  TT = {el['TT']:.6f} m  ≅  {el['TT']:.2f} m")
    print(f"  t  = {el['t']:.6f} m  ≅  {el['t']:.2f} m")
    print(f"  Es = {el['Es']:.6f} m  ≅  {el['Es']:.2f} m")
    print(f"  θ  = {el['theta_deg']:.6f}°  =  {el['theta_dms']}")
    print(f"  Dθ = {el['Dtheta']:.6f} m  ≅  {el['Dtheta']:.2f} m")
    print()

    def fmt_st(tup):
        return f"{tup[0]}+{tup[1]:.2f}  ({tup[2]:.4f} m)"

    print("─── Ex. 3  Estaqueamento dos pontos notáveis ────────────────")
    print(f"  Est.(PI) = {fmt_st(pt['PI'])}")
    print(f"  Est.(TS) = {fmt_st(pt['TS'])}")
    print(f"  Est.(SC) = {fmt_st(pt['SC'])}")
    print(f"  Est.(CS) = {fmt_st(pt['CS'])}")
    print(f"  Est.(ST) = {fmt_st(pt['ST'])}")
    print()

    print("─── Ex. 4  Caderneta de locação da 1ª espiral ───────────────")
    hdr = f"{'Estaca':>10}  {'Corda':>7}  {'l (m)':>8}  {'φ (rad)':>10}  {'x (m)':>12}  {'y (m)':>10}  ds (dms)"
    print(hdr)
    print("─" * len(hdr))
    for r in tb:
        label = f"TS–{r['stake_int']}" if r['l'] == 0 else \
                (f"SC–{r['stake_int']}" if abs(r['l'] - c['le_des']) < 1e-6 else str(r['stake_int']))
        chord_str = f"{r['chord_m']:.2f} m" if r['l'] > 0 else "—"
        print(f"  {label:>8}  {chord_str:>7}  {r['l']:>8.2f}  {r['phi_rad']:>10.6f}"
              f"  {r['x']:>12.6f}  {r['y']:>10.7f}  {r['ds_dms']}")
    print("=" * 65)


# ─────────────────────────────────────────────────────────────
# CLI — execução direta
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Exercício ORIGINAL (referência)
    print("\n>>> EXERCÍCIO ORIGINAL (referência do documento)\n")
    orig = solucao_completa(
        v=100, R=600, AC_deg=60, e=9, lf=3.6,
        PI_stake=847, PI_frac=12.20,
        spacing=20, chord_base=20,
    )
    print_resultado(orig)

    # Novo exercício
    print("\n>>> NOVO EXERCÍCIO (valores diferentes)\n")
    novo = solucao_completa(
        v=80, R=350, AC_deg=65, e=8, lf=3.6,
        PI_stake=740, PI_frac=7.80,
        spacing=20, chord_base=20,
    )
    print_resultado(novo)
