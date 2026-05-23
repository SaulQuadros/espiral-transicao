"""
gerar_dwg.py — Geração de arquivo DXF para curva espiral de transição (Clotóide).
Referência: Antas P. M. et al, 2016. Método do Raio Conservado – Simetria de Concordância.

Sistema de coordenadas local da espiral:
  - Origem em TS
  - Eixo x: direção da tangente de entrada (azimute topográfico Az, de Norte, horário)
  - Eixo y: perpendicular, positivo no lado da curvatura
    (+y → esquerda quando s=+1; +y → direita quando s=-1)

Transformação local → global (E, N):
  E = E_TS + x_l · sin(Az) − s · y_l · cos(Az)
  N = N_TS + x_l · cos(Az) + s · y_l · sin(Az)
"""

import math
import io
import ezdxf


# ─── Transformação de coordenadas ────────────────────────────────────────────

def _loc2glob(x_l, y_l, E0, N0, Az_rad, s):
    """Transforma ponto local (x_l, y_l) → global (E, N)."""
    E = E0 + x_l * math.sin(Az_rad) - s * y_l * math.cos(Az_rad)
    N = N0 + x_l * math.cos(Az_rad) + s * y_l * math.sin(Az_rad)
    return E, N


def _spiral_xy(l, R, le):
    """Coordenadas locais (x, y) no ponto l ao longo da espiral Clotóide (Eqs. 1.89/1.90)."""
    if l <= 0:
        return 0.0, 0.0
    phi = l ** 2 / (2 * R * le)
    phi2, phi4 = phi ** 2, phi ** 4
    x = l * (1 - phi2 / 10 + phi4 / 216)
    y = (l * phi / 3) * (1 - phi2 / 14 + phi4 / 440)
    return x, y


# ─── Helpers de estaqueamento ────────────────────────────────────────────────

def _stake_label(stake_int, stake_frac):
    """Formata rótulo no padrão brasileiro: Est.726+11,53"""
    frac = f"{stake_frac:.2f}".replace('.', ',')
    return f"Est.{stake_int}+{frac}"


def _add_stake_label(msp, E, N, Az_tang_rad, s, label, h, tick_len, layer):
    """
    Desenha linha de chamada perpendicular (para dentro da curva) e rótulo da estaca.

    A direção inward (perpendicular ao eixo, voltada ao centro) é:
        dE = -s · cos(Az)
        dN =  s · sin(Az)

    O texto é rotacionado paralelo ao eixo da via para leitura natural.
    """
    # Vetor inward unitário
    dE =  -s * math.cos(Az_tang_rad)
    dN =   s * math.sin(Az_tang_rad)

    # Extremidade da linha de chamada
    Et = E + tick_len * dE
    Nt = N + tick_len * dN
    msp.add_line((E, N), (Et, Nt), dxfattribs={'layer': layer})

    # Ângulo de rotação do texto = direção da tangente (paralela ao eixo da via)
    rot = math.degrees(math.atan2(math.cos(Az_tang_rad), math.sin(Az_tang_rad)))
    if rot >  90:
        rot -= 180
    if rot < -90:
        rot += 180

    text = msp.add_text(label, dxfattribs={'height': h, 'layer': layer, 'rotation': rot})
    text.dxf.insert = (Et + h * 0.4 * dE, Nt + h * 0.4 * dN)


# ─── Cálculo dos pontos globais da curva completa ────────────────────────────

def calcular_pontos_curva(elem, R, AC_deg, le, E_TS, N_TS, Az_in_deg, direction='E', n_pts=150):
    """
    Calcula os pontos globais (E, N) da curva completa TS → SC → CS → ST.

    Parâmetros
    ----------
    elem       : dict — saída de elementos_espiral()
    R, AC_deg  : raio (m) e ângulo central (graus)
    le         : comprimento de transição adotado (m)
    E_TS, N_TS : coordenadas globais do ponto TS
    Az_in_deg  : azimute da tangente de entrada (graus topográficos, 0–360)
    direction  : 'E' (esquerda/left) | 'D' (direita/right)
    n_pts      : número de pontos por segmento

    Retorna
    -------
    spiral1, arc_pts, spiral2 : listas de (E, N)
    pontos : dict  {'TS', 'SC', 'CS', 'ST', 'PI', 'Centro'}
    """
    s       = 1 if direction == 'E' else -1
    Az_in   = math.radians(Az_in_deg)
    Az_out  = Az_in - s * math.radians(AC_deg)

    Phi_rad   = elem['Phi_rad']
    theta_rad = math.radians(elem['theta_deg'])
    q, p      = elem['q'], elem['p']
    Xc, Yc    = elem['Xc'], elem['Yc']
    TT        = elem['TT']

    def fwd(x_l, y_l):
        return _loc2glob(x_l, y_l, E_TS, N_TS, Az_in, s)

    # ── 1ª espiral: TS → SC ──────────────────────────────────────────────────
    spiral1 = [fwd(*_spiral_xy(le * i / n_pts, R, le)) for i in range(n_pts + 1)]
    E_SC, N_SC = spiral1[-1]

    # ── Centro do arco circular (coordenadas locais: q, p+R) ─────────────────
    E_ctr, N_ctr = fwd(q, p + R)

    # ── Arco circular: SC → CS ───────────────────────────────────────────────
    # Ângulo matemático (de East, CCW) do vetor Centro→SC
    ang_SC = math.atan2(N_SC - N_ctr, E_SC - E_ctr)
    arc_pts = []
    for i in range(n_pts + 1):
        a = ang_SC + s * theta_rad * i / n_pts
        arc_pts.append((E_ctr + R * math.cos(a), N_ctr + R * math.sin(a)))
    E_CS, N_CS = arc_pts[-1]

    # ── PI e ST ──────────────────────────────────────────────────────────────
    E_PI = E_TS + TT * math.sin(Az_in)
    N_PI = N_TS + TT * math.cos(Az_in)
    E_ST = E_PI + TT * math.sin(Az_out)
    N_ST = N_PI + TT * math.cos(Az_out)

    # ── 2ª espiral: CS → ST ──────────────────────────────────────────────────
    # Parametriza a partir de ST em direção reversa (tangente de saída invertida).
    # A transformação usa s_2 = −s para manter o lado correto da curvatura.
    Az_back = Az_out + math.pi

    def rev(x_l, y_l):
        return _loc2glob(x_l, y_l, E_ST, N_ST, Az_back, -s)

    spiral2_rev = [rev(*_spiral_xy(le * i / n_pts, R, le)) for i in range(n_pts + 1)]
    spiral2 = list(reversed(spiral2_rev))   # ordena CS → ST

    pontos = {
        'TS':     (E_TS,  N_TS),
        'SC':     (E_SC,  N_SC),
        'CS':     (E_CS,  N_CS),
        'ST':     (E_ST,  N_ST),
        'PI':     (E_PI,  N_PI),
        'Centro': (E_ctr, N_ctr),
    }
    return spiral1, arc_pts, spiral2, pontos


# ─── Geração do arquivo DXF ──────────────────────────────────────────────────

def gerar_dxf_bytes(elem, R, AC_deg, le, E_ref, N_ref,
                    Az_in_deg, ref_point='TS', direction='E',
                    estaqueamento=None, n_pts=150):
    """
    Gera a curva espiral completa em formato DXF e retorna os bytes prontos
    para download ou escrita em arquivo.

    Parâmetros
    ----------
    elem          : dict — saída de elementos_espiral()
    R, AC_deg     : raio (m) e ângulo central (graus)
    le            : comprimento de transição adotado (m)
    E_ref, N_ref  : coordenadas do ponto de referência
    Az_in_deg     : azimute da tangente de entrada (graus topográficos)
    ref_point     : 'TS' | 'PI'
    direction     : 'E' (esquerda) | 'D' (direita)
    estaqueamento : dict — saída de estaqueamento_pontos() (opcional)
                    Quando fornecido, insere linhas de chamada perpendiculares
                    com rótulos "Est.726+11,53" em TS, SC, CS e ST.
    n_pts         : pontos por segmento da curva

    Layers no DXF
    -------------
    TANGENTES      — cinza    — tangentes externas (tracejado)
    ESPIRAL_1      — azul     — 1ª espiral (TS→SC)
    CIRCULAR       — vermelho — arco circular (SC→CS)
    ESPIRAL_2      — verde    — 2ª espiral (CS→ST)
    PONTOS         — amarelo  — marcadores dos pontos notáveis
    COTAS          — branco   — rótulos de nome (TS, SC, CS, ST, PI)
    ESTAQUEAMENTO  — ciano    — linhas de chamada e rótulos de estaca
    """
    s     = 1 if direction == 'E' else -1
    Az_in = math.radians(Az_in_deg)

    # Converter referência PI → TS, se necessário
    if ref_point == 'PI':
        TT   = elem['TT']
        E_TS = E_ref - TT * math.sin(Az_in)
        N_TS = N_ref - TT * math.cos(Az_in)
    else:
        E_TS, N_TS = E_ref, N_ref

    spiral1, arc_pts, spiral2, pontos = calcular_pontos_curva(
        elem, R, AC_deg, le, E_TS, N_TS, Az_in_deg, direction, n_pts
    )

    # ── Criar documento DXF ──────────────────────────────────────────────────
    doc = ezdxf.new('R2010', setup=True)   # carrega linetypes padrão (DASHED, etc.)
    msp = doc.modelspace()

    for nome, cor in [
        ('TANGENTES',     8),   # cinza
        ('ESPIRAL_1',     5),   # azul
        ('CIRCULAR',      1),   # vermelho
        ('ESPIRAL_2',     3),   # verde
        ('PONTOS',        2),   # amarelo
        ('COTAS',         7),   # branco / preto
        ('ESTAQUEAMENTO', 4),   # ciano
    ]:
        doc.layers.add(nome, color=cor)

    # ── Tangentes externas ───────────────────────────────────────────────────
    Az_out = Az_in - s * math.radians(AC_deg)
    ext    = elem['TT'] * 0.3
    E_TS_g, N_TS_g = pontos['TS']
    E_PI,   N_PI   = pontos['PI']
    E_ST,   N_ST   = pontos['ST']

    msp.add_line(
        (E_TS_g - ext * math.sin(Az_in),  N_TS_g - ext * math.cos(Az_in)),
        (E_PI, N_PI),
        dxfattribs={'layer': 'TANGENTES', 'linetype': 'DASHED'},
    )
    msp.add_line(
        (E_PI, N_PI),
        (E_ST + ext * math.sin(Az_out), N_ST + ext * math.cos(Az_out)),
        dxfattribs={'layer': 'TANGENTES', 'linetype': 'DASHED'},
    )

    # ── Curvas como polylines ────────────────────────────────────────────────
    msp.add_lwpolyline(spiral1, dxfattribs={'layer': 'ESPIRAL_1'})
    msp.add_lwpolyline(arc_pts, dxfattribs={'layer': 'CIRCULAR'})
    msp.add_lwpolyline(spiral2, dxfattribs={'layer': 'ESPIRAL_2'})

    # ── Marcadores e rótulos ─────────────────────────────────────────────────
    h      = R * 0.012          # altura de texto proporcional ao raio
    r_mark = R * 0.004          # raio do círculo marcador

    for nome, (E, N) in pontos.items():
        if nome == 'Centro':
            msp.add_circle((E, N), radius=r_mark * 0.6,
                           dxfattribs={'layer': 'PONTOS', 'color': 8})
            continue
        msp.add_circle((E, N), radius=r_mark, dxfattribs={'layer': 'PONTOS'})
        text = msp.add_text(nome, dxfattribs={'height': h, 'layer': 'COTAS'})
        text.dxf.insert = (E + h * 0.7, N + h * 0.7)

    # ── Estaqueamento: linhas de chamada perpendiculares + rótulos ──────────
    if estaqueamento is not None:
        Phi_rad = elem['Phi_rad']
        AC_rad  = math.radians(AC_deg)

        # Azimute da tangente em cada ponto notável
        az_pts = {
            'TS': Az_in,
            'SC': Az_in - s * Phi_rad,
            'CS': Az_in - s * (AC_rad - Phi_rad),
            'ST': Az_out,
        }

        tick_len = R * 0.06     # comprimento da linha de chamada
        h_stake  = R * 0.016    # altura do texto de estaca

        for nome in ('TS', 'SC', 'CS', 'ST'):
            E, N = pontos[nome]
            si, sf = estaqueamento[nome][0], estaqueamento[nome][1]
            _add_stake_label(
                msp, E, N,
                Az_tang_rad=az_pts[nome],
                s=s,
                label=_stake_label(si, sf),
                h=h_stake,
                tick_len=tick_len,
                layer='ESTAQUEAMENTO',
            )

    # ── Serializar para bytes ────────────────────────────────────────────────
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode('utf-8')
