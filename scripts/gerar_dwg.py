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
from ezdxf.enums import TextEntityAlignment


# ─── Configuração da prancha (A1 paisagem) ───────────────────────────────────

_PAPER_W_MM = 841
_PAPER_H_MM = 594
_MARGIN_MM  = 15
_STRIP_FRAC = 0.08    # faixa de legenda como fração da altura total
_STD_SCALES = [100, 200, 250, 500, 750, 1000, 1250, 1500, 2000, 2500, 5000, 10000]


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
    """Formata rótulo no padrão brasileiro: E726+11,53"""
    frac = f"{stake_frac:.2f}".replace('.', ',')
    return f"E{stake_int}+{frac}"


def _add_stake_label(msp, E, N, Az_tang_rad, s, label, h, tick_len, layer):
    """
    Desenha linha de chamada perpendicular (para dentro da curva) e rótulo da estaca.

    A direção inward (perpendicular ao eixo, voltada ao centro) é:
        dE = -s · cos(Az)
        dN =  s · sin(Az)

    Alinhamento MIDDLE_CENTER: ponto de inserção é o centro do texto,
    então a normalização da rotação ±180° não causa sobreposição com a curva.
    O centro é posicionado `gap = h * 4.5` além do fim do segmento de chamada,
    garantindo ≈ 1.5h de folga entre o segmento e a borda mais próxima do texto
    (estimativa: ~10 chars × 0.6h/char → meia-largura ≈ 3h).
    """
    # Vetor inward unitário
    dE = -s * math.cos(Az_tang_rad)
    dN =  s * math.sin(Az_tang_rad)

    # Extremidade da linha de chamada
    Et = E + tick_len * dE
    Nt = N + tick_len * dN
    msp.add_line((E, N), (Et, Nt), dxfattribs={'layer': layer})

    # Ângulo de rotação = direção do tick (paralelo à linha de chamada)
    rot = math.degrees(math.atan2(dN, dE))
    if rot >  90:
        rot -= 180
    if rot < -90:
        rot += 180

    # Centro do texto a gap além do fim do segmento
    gap = h * 4.5
    cx = Et + gap * dE
    cy = Nt + gap * dN
    text = msp.add_text(label, dxfattribs={'height': h, 'layer': layer, 'rotation': rot})
    text.set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)


# ─── Prancha, Norte e Raio ────────────────────────────────────────────────────

def _compute_layout(all_pts):
    """
    Calcula escala normalizada e dimensões da prancha A1 centrada no desenho.
    Retorna (scale, frame_W, frame_H, strip_H, ox, oy) onde (ox, oy) é o canto
    inferior-esquerdo da prancha em coordenadas modelo.
    """
    Es = [p[0] for p in all_pts]
    Ns = [p[1] for p in all_pts]
    cx = (min(Es) + max(Es)) / 2
    cy = (min(Ns) + max(Ns)) / 2
    span_E = max(Es) - min(Es)
    span_N = max(Ns) - min(Ns)

    avail_W_mm = _PAPER_W_MM - 2 * _MARGIN_MM
    avail_H_mm = _PAPER_H_MM * (1 - _STRIP_FRAC) - 2 * _MARGIN_MM

    scale_raw = max(span_E / (avail_W_mm / 1000),
                    span_N / (avail_H_mm / 1000))
    scale = next((s for s in _STD_SCALES if s >= scale_raw * 1.15), _STD_SCALES[-1])

    frame_W = _PAPER_W_MM / 1000 * scale
    frame_H = _PAPER_H_MM / 1000 * scale
    strip_H = frame_H * _STRIP_FRAC

    # Centraliza o conteúdo na área útil acima da faixa de legenda
    content_cy_offset = strip_H + (frame_H - strip_H) / 2
    ox = cx - frame_W / 2
    oy = cy - content_cy_offset

    return scale, frame_W, frame_H, strip_H, ox, oy


def _draw_frame(msp, ox, oy, W, H, strip_H, scale, layer='PRANCHA'):
    """Borda da prancha A1 + faixa de legenda na base com título e escala."""
    # Borda externa
    msp.add_lwpolyline(
        [(ox, oy), (ox + W, oy), (ox + W, oy + H), (ox, oy + H)],
        close=True, dxfattribs={'layer': layer},
    )
    # Separador da legenda
    msp.add_line((ox, oy + strip_H), (ox + W, oy + strip_H),
                 dxfattribs={'layer': layer})

    h = strip_H * 0.28
    cy_leg = oy + strip_H * 0.50

    t1 = msp.add_text(
        'Espiral de Transição — Clotóide',
        dxfattribs={'height': h, 'layer': layer},
    )
    t1.set_placement((ox + W * 0.50, cy_leg), align=TextEntityAlignment.MIDDLE_CENTER)

    t2 = msp.add_text(
        f'Escala  1:{scale}',
        dxfattribs={'height': h, 'layer': layer},
    )
    t2.set_placement((ox + W * 0.07, cy_leg), align=TextEntityAlignment.MIDDLE_LEFT)


def _draw_north_arrow(msp, x, y, size, layer='NORTE'):
    """
    Seta Norte centrada em (x, y), apontando para o Norte geográfico (+N no DXF).
    Composta por haste, triângulo e letra N.
    """
    hw       = size * 0.22
    shaft_b  = y - size * 0.40
    arr_base = y + size * 0.05
    arr_tip  = y + size * 0.42

    # Haste
    msp.add_line((x, shaft_b), (x, arr_base), dxfattribs={'layer': layer})
    # Ponta triangular
    msp.add_lwpolyline(
        [(x, arr_tip), (x - hw, arr_base), (x + hw, arr_base)],
        close=True, dxfattribs={'layer': layer},
    )
    # Círculo na base
    msp.add_circle((x, shaft_b), radius=size * 0.08, dxfattribs={'layer': layer})
    # Letra N
    h_n = size * 0.30
    t = msp.add_text('N', dxfattribs={'height': h_n, 'layer': layer})
    t.set_placement((x, arr_tip + h_n * 0.85), align=TextEntityAlignment.MIDDLE_CENTER)


def _draw_radius_line(msp, E_ctr, N_ctr, E_SC, N_SC, R, layer='RAIO'):
    """
    Segmento de reta do centro do arco até SC (comprimento = R exato)
    com rótulo 'R = XXX,XX m' deslocado perpendicularmente ao segmento.
    """
    dx = E_SC - E_ctr
    dy = N_SC - N_ctr
    dist = math.hypot(dx, dy)
    ux, uy = dx / dist, dy / dist

    msp.add_line((E_ctr, N_ctr), (E_SC, N_SC), dxfattribs={'layer': layer})

    # Ponto médio + deslocamento perpendicular
    mx, my = E_ctr + ux * dist * 0.5, N_ctr + uy * dist * 0.5
    px, py = -uy, ux   # perpendicular unitário

    rot = math.degrees(math.atan2(uy, ux))
    if rot >  90: rot -= 180
    if rot < -90: rot += 180

    h = R * 0.018
    label = f'R = {R:.2f} m'.replace('.', ',')
    t = msp.add_text(label, dxfattribs={'height': h, 'layer': layer, 'rotation': rot})
    t.set_placement(
        (mx + px * h * 1.8, my + py * h * 1.8),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )


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
                    com rótulos "E726+11,53" em TS, SC, CS e ST.
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
    RAIO           — magenta  — segmento centro→SC com valor do raio
    NORTE          — branco   — seta Norte Verdadeiro
    PRANCHA        — cinza    — borda da prancha A1 e legenda
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
    doc = ezdxf.new('R2010', setup=True)
    msp = doc.modelspace()

    for nome, cor in [
        ('TANGENTES',     8),   # cinza
        ('ESPIRAL_1',     5),   # azul
        ('CIRCULAR',      1),   # vermelho
        ('ESPIRAL_2',     3),   # verde
        ('PONTOS',        2),   # amarelo
        ('COTAS',         7),   # branco / preto
        ('ESTAQUEAMENTO', 4),   # ciano
        ('RAIO',          6),   # magenta
        ('NORTE',         7),   # branco
        ('PRANCHA',       8),   # cinza
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
    h      = R * 0.012
    r_mark = R * 0.004

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

        az_pts = {
            'TS': Az_in,
            'SC': Az_in - s * Phi_rad,
            'CS': Az_in - s * (AC_rad - Phi_rad),
            'ST': Az_out,
        }

        tick_len = R * 0.06
        h_stake  = R * 0.008

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

    # ── Raio: segmento centro → SC ───────────────────────────────────────────
    E_SC, N_SC   = pontos['SC']
    E_ctr, N_ctr = pontos['Centro']
    _draw_radius_line(msp, E_ctr, N_ctr, E_SC, N_SC, R)

    # ── Prancha A1 com escala dinâmica ───────────────────────────────────────
    all_pts = spiral1 + arc_pts + spiral2 + list(pontos.values())
    scale, frame_W, frame_H, strip_H, ox, oy = _compute_layout(all_pts)
    _draw_frame(msp, ox, oy, frame_W, frame_H, strip_H, scale)

    # ── Seta Norte: canto superior direito da área de desenho ─────────────────
    na_size = frame_H * 0.055
    na_x = ox + frame_W - na_size * 2.5
    na_y = oy + strip_H + (frame_H - strip_H) * 0.88
    _draw_north_arrow(msp, na_x, na_y, na_size)

    # ── Serializar para bytes ────────────────────────────────────────────────
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode('utf-8')
