"""
app.py — Streamlit: Gerador de Curva Espiral de Transição (Clotóide) em DXF.
Disciplina: Transportes — Projeto Geométrico de Rodovias — Univertix 2026/1
Referência: Antas P. M. et al, 2016.

Uso:
    streamlit run app.py
"""

import sys
import os
import math

import streamlit as st
import matplotlib.pyplot as plt

# ── Importar módulos do projeto ───────────────────────────────────────────────
_scripts = os.path.join(os.path.dirname(__file__), 'scripts')
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

from calc_transicao import comprimentos_transicao, elementos_espiral
from gerar_dwg import calcular_pontos_curva, gerar_dxf_bytes


# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Espiral de Transição — DXF",
    layout="wide",
)

st.title("Gerador de Curva Espiral de Transição")
st.markdown(
    "**Disciplina:** Transportes — Projeto Geométrico de Rodovias &nbsp;|&nbsp; "
    "Univertix 2026/1 &nbsp;|&nbsp; "
    "Ref.: Antas P. M. et al, 2016"
)
st.divider()


# ── Formulário de entrada ─────────────────────────────────────────────────────
with st.form("form_espiral"):
    col_esp, col_pos = st.columns(2, gap="large")

    with col_esp:
        st.subheader("Parâmetros da espiral")

        v = st.number_input(
            "Velocidade **v** (km/h)",
            min_value=20.0, max_value=200.0, value=80.0, step=5.0,
        )
        R = st.number_input(
            "Raio **R** (m)",
            min_value=50.0, max_value=5000.0, value=350.0, step=10.0,
        )
        AC = st.number_input(
            "Ângulo central **AC** (graus)",
            min_value=1.0, max_value=179.0, value=65.0, step=1.0,
        )
        le = st.number_input(
            "**le** adotado (m)",
            min_value=1.0, max_value=3000.0, value=105.0, step=5.0,
            help="Shortt (desejável): le = ⌈0,071·v³/R⌉₅.  "
                 "Para v=80 km/h, R=350 m → 105 m.",
        )
        direction = st.radio(
            "Sentido da curva",
            options=["E — Esquerda", "D — Direita"],
            horizontal=True,
        )

    with col_pos:
        st.subheader("Posicionamento global")

        ref_opt = st.radio(
            "Coordenadas referentes a:",
            options=["TS  (Tangente–Espiral)", "PI  (Vértice das tangentes)"],
            horizontal=True,
        )
        E_ref = st.number_input(
            "**E** — coordenada Leste (m)",
            value=0.0, format="%.3f", step=1.0,
        )
        N_ref = st.number_input(
            "**N** — coordenada Norte (m)",
            value=0.0, format="%.3f", step=1.0,
        )

        st.markdown("**Azimute da tangente de entrada** (grau / minuto / segundo)")
        c1, c2, c3 = st.columns(3)
        az_g = c1.number_input("Graus",  min_value=0,   max_value=359,  value=0,   step=1)
        az_m = c2.number_input("Min",    min_value=0,   max_value=59,   value=0,   step=1)
        az_s = c3.number_input("Seg",    min_value=0.0, max_value=59.99, value=0.0, step=1.0)
        Az_deg = az_g + az_m / 60 + az_s / 3600

    submitted = st.form_submit_button(
        "Calcular e gerar DXF",
        type="primary",
        use_container_width=True,
    )


# ── Processamento ─────────────────────────────────────────────────────────────
if submitted:
    dir_code = 'E' if direction.startswith('E') else 'D'
    ref_code = 'TS' if ref_opt.startswith('TS') else 'PI'

    # ── Validações ────────────────────────────────────────────────────────────
    comp = comprimentos_transicao(v, R, AC)
    erros = []
    if le < comp['le_min']:
        erros.append(
            f"le = {le:.2f} m < le_mín = {comp['le_min']:.2f} m (Barnett). "
            "Aumente o comprimento de transição."
        )
    if le > comp['le_max']:
        erros.append(
            f"le = {le:.2f} m > le_máx = {comp['le_max']:.2f} m. "
            "Reduza o comprimento de transição."
        )

    for msg in erros:
        st.error(msg)

    if not erros:
        # ── Calcular elementos geométricos ────────────────────────────────────
        elem = elementos_espiral(v, R, AC, le)

        s      = 1 if dir_code == 'E' else -1
        Az_in  = math.radians(Az_deg)

        if ref_code == 'PI':
            E_TS = E_ref - elem['TT'] * math.sin(Az_in)
            N_TS = N_ref - elem['TT'] * math.cos(Az_in)
        else:
            E_TS, N_TS = E_ref, N_ref

        spiral1, arc_pts, spiral2, pontos = calcular_pontos_curva(
            elem, R, AC, le, E_TS, N_TS, Az_deg, dir_code
        )

        # ── Validação dos comprimentos ────────────────────────────────────────
        st.subheader("Comprimentos de transição")
        cv1, cv2, cv3, cv4 = st.columns(4)
        cv1.metric("le_mín (Barnett)", f"{comp['le_min']:.2f} m")
        cv2.metric("le_des (Shortt)", f"{comp['le_des']:.2f} m")
        cv3.metric("le_máx", f"{comp['le_max']:.2f} m")
        ok_icon = "OK" if comp['le_min'] <= le <= comp['le_max'] else "FORA DO INTERVALO"
        cv4.metric("le adotado", f"{le:.2f} m", delta=ok_icon)

        # ── Elementos geométricos ─────────────────────────────────────────────
        st.subheader("Elementos geométricos")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Phi", elem['Phi_dms'])
        e2.metric("TT",  f"{elem['TT']:.2f} m")
        e3.metric("Es",  f"{elem['Es']:.2f} m")
        e4.metric("Dtheta", f"{elem['Dtheta']:.2f} m")

        e5, e6, e7, e8 = st.columns(4)
        e5.metric("q",  f"{elem['q']:.3f} m")
        e6.metric("p",  f"{elem['p']:.3f} m")
        e7.metric("Xc", f"{elem['Xc']:.3f} m")
        e8.metric("Yc", f"{elem['Yc']:.3f} m")

        # ── Coordenadas globais dos pontos notáveis ───────────────────────────
        st.subheader("Coordenadas globais dos pontos notáveis")
        tab_data = {
            nome: {"E (m)": f"{E:.3f}", "N (m)": f"{N:.3f}"}
            for nome, (E, N) in pontos.items()
            if nome != 'Centro'
        }
        st.table(tab_data)

        # ── Plot matplotlib ───────────────────────────────────────────────────
        st.subheader("Visualização")

        fig, ax = plt.subplots(figsize=(9, 9))

        s1E, s1N = zip(*spiral1)
        aE,  aN  = zip(*arc_pts)
        s2E, s2N = zip(*spiral2)

        ax.plot(s1E, s1N, color='#1f77b4', lw=2.2, label=f'1ª Espiral (TS→SC,  le={le:.0f} m)')
        ax.plot(aE,  aN,  color='#d62728', lw=2.2, label=f'Arco Circular (SC→CS, Dθ={elem["Dtheta"]:.2f} m)')
        ax.plot(s2E, s2N, color='#2ca02c', lw=2.2, label=f'2ª Espiral (CS→ST,  le={le:.0f} m)')

        # Tangentes externas
        Az_out = Az_in - s * math.radians(AC)
        ext    = elem['TT'] * 0.25
        E_PI, N_PI = pontos['PI']
        E_ST, N_ST = pontos['ST']

        ax.plot(
            [E_TS - ext * math.sin(Az_in), E_PI],
            [N_TS - ext * math.cos(Az_in), N_PI],
            color='gray', lw=1.0, ls='--', alpha=0.7, label='Tangentes',
        )
        ax.plot(
            [E_PI, E_ST + ext * math.sin(Az_out)],
            [N_PI, N_ST + ext * math.cos(Az_out)],
            color='gray', lw=1.0, ls='--', alpha=0.7,
        )

        # Pontos notáveis
        cores_pt = {
            'TS': '#1f77b4', 'SC': '#9467bd',
            'CS': '#8c564b', 'ST': '#2ca02c', 'PI': '#666666',
        }
        for nome, (E, N) in pontos.items():
            if nome == 'Centro':
                ax.plot(E, N, '+', color='#d62728', ms=8, mew=1.5)
                continue
            cor = cores_pt.get(nome, 'black')
            ax.plot(E, N, 'o', color=cor, ms=7, zorder=5)
            ax.annotate(
                nome, (E, N),
                textcoords="offset points", xytext=(6, 6),
                fontsize=9, fontweight='bold', color=cor,
            )

        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('E (m)')
        ax.set_ylabel('N (m)')
        ax.legend(loc='best', fontsize=9)
        ax.set_title(
            f'Espiral de Transição — R = {R:.0f} m,  le = {le:.0f} m,  AC = {AC:.1f}°,  '
            f'{"Esquerda" if dir_code == "E" else "Direita"}',
            fontsize=11,
        )
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        # ── Download DXF ──────────────────────────────────────────────────────
        st.subheader("Arquivo DXF")
        try:
            dxf_bytes = gerar_dxf_bytes(
                elem, R, AC, le, E_ref, N_ref, Az_deg, ref_code, dir_code
            )
            st.download_button(
                label="Baixar DXF  (abrir no AutoCAD)",
                data=dxf_bytes,
                file_name=f"espiral_R{R:.0f}_le{le:.0f}.dxf",
                mime="application/octet-stream",
                use_container_width=True,
            )
            st.caption(
                "Layers no DXF: **TANGENTES** (cinza/tracejado) · "
                "**ESPIRAL_1** (azul) · **CIRCULAR** (vermelho) · "
                "**ESPIRAL_2** (verde) · **PONTOS** (amarelo) · **COTAS** (branco)."
            )
        except Exception as exc:
            st.error(f"Erro ao gerar DXF: {exc}")
            st.info("Verifique se a biblioteca `ezdxf` está instalada (`pip install ezdxf`).")
