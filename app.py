# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ===============================================================
# Configuração da página (painel mais largo)
# ===============================================================
st.set_page_config(layout="wide")


# ===============================================================
# Constantes de colunas
# ===============================================================
# COL_CODIGO   = "Código Interno"
COL_REGIONAL = "Regional"
COL_ESCOLA   = "Escola"

# Colunas de Redação
COL_PART_RED = [
    "1º Simulado: Participação (%)",
    "1º Teste de Redação: Participação (%)",
    "2º Teste de Redação: Participação (%)",
    "2º Simulado: Participação (%)",
    "3º Teste de Redação: Participação (%)",
    "4º Teste de Redação: Participação (%)",
]

COL_NOTAS_RED = [
    "1º Simulado: Nota",
    "1º Teste de Redação: Nota",
    "2º Teste de Redação: Nota",
    "2º Simulado: Nota",
    "3º Teste de Redação: Nota",
    "4º Teste de Redação: Nota",
]

# Colunas de Objetivas
COL_PART_OBJ = [
    "Objetivas - 1º Simulado: Participação (%)",
    "Objetivas - 2º Simulado: Participação (%)",
]

COL_ACERTOS_OBJ = [
    "Objetivas - 1º Simulado: Acertos (%)",
    "Objetivas - 2º Simulado: Acertos (%)",  # ajuste se o nome estiver ligeiramente diferente
]


# ===============================================================
# Funções auxiliares
# ===============================================================
def serie_para_float(s: pd.Series, eh_percentual: bool = False) -> pd.Series:
    """
    Converte uma Series com valores tipo '85,12%' / '202,71'
    em float. Se eh_percentual=True, remove '%'.
    """
    s = s.astype(str).str.strip()

    if eh_percentual:
        s = s.str.replace('%', '', regex=False)

    # remove separador de milhar e troca vírgula por ponto
    s = s.str.replace('.', '', regex=False)
    s = s.str.replace(',', '.', regex=False)

    return pd.to_numeric(s, errors="coerce")



def calcular_variacao(valores) -> list:
    """
    Retorna lista com variação (com sinal) em relação ao ponto anterior.
    Primeiro ponto recebe 0.0.
    """
    vals = []
    for v in valores:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            vals.append(None)
        else:
            vals.append(float(v))

    variacoes = [0.0]
    for i in range(1, len(vals)):
        if vals[i] is not None and vals[i - 1] is not None:
            variacoes.append(vals[i] - vals[i - 1])  # COM SINAL
        else:
            variacoes.append(0.0)
    return variacoes



def fmt_num_br(v):
    if pd.isna(v):
        return ""
    return f"{v:.2f}".replace(".", ",")



def fmt_percent_br(v):
    if pd.isna(v):
        return ""
    # v aqui é fração (0–1), multiplicamos por 100 pra mostrar
    return f"{v*100:.2f}%".replace(".", ",")



def fmt_nota_br(v):
    if pd.isna(v):
        return ""
    return f"{v:.2f}".replace(".", ",")



def fmt_int(v):
    if pd.isna(v):
        return ""
    return f"{int(round(v))}"


def textpositions_por_etapa(*series_y, default="top center"):
    """
    Para um conjunto de séries Y (traces) do MESMO gráfico, compara os valores EM CADA ETAPA (cada ponto do eixo X).

    Em cada ponto j:
      - maior valor válido -> rótulo em 'top center'
      - menor valor válido -> rótulo em 'bottom center'
      - empate (max == min) -> mantém 'top center' (default) para todas as séries no ponto
      - se houver <2 valores válidos no ponto -> mantém 'top center' (default)

    Retorna uma lista (uma por série) de listas de textposition (tamanho = len(y)).
    """
    ys = []
    for y in series_y:
        if isinstance(y, pd.Series):
            y = y.tolist()
        else:
            y = list(y)
        ys.append(y)

    if not ys:
        return []

    n = min(len(y) for y in ys)
    pos_all = [[default] * len(y) for y in ys]

    for j in range(n):
        vals = []
        for i, y in enumerate(ys):
            v = y[j]
            # trata None/NaN
            if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
                continue
            try:
                vals.append((i, float(v)))
            except Exception:
                continue

        if len(vals) < 2:
            continue

        max_val = max(v for _, v in vals)
        min_val = min(v for _, v in vals)

        if max_val == min_val:
            continue

        for i, v in vals:
            if v == max_val:
                pos_all[i][j] = "top center"
            elif v == min_val:
                pos_all[i][j] = "bottom center"
            else:
                pos_all[i][j] = default

    return pos_all



# ===============================================================
# 1) Carregar dados do Excel
# ===============================================================
@st.cache_data
def load_data():
    xls = pd.ExcelFile("Dados_RJ.xlsx")

    def read_sheet(sheet_name):
        df_ = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)
        df_.columns = (
            df_.columns
            .str.strip()
            .str.replace('\ufeff', '', regex=False)
        )
        return df_

    df_original   = read_sheet("Original")
    df_redacao    = read_sheet("Dados_Redação")
    df_objetivas  = read_sheet("Dados_Objetivas")
    df_particip   = read_sheet("Dados_Participação")
    df_acessos    = read_sheet("Dados_Acesso_Detalhado")

    return {
        "original": df_original,
        "redacao": df_redacao,
        "objetivas": df_objetivas,
        "participacao": df_particip,
        "acessos": df_acessos,
    }


data = load_data()
df_redacao   = data["redacao"]
df_objetivas = data["objetivas"]
df_part      = data["participacao"]
df_acessos   = data["acessos"]

st.title("Painel de Participação e Desempenhos")

# ===============================================================
# 2) Seleção de regional (com base na união das abas)
# ===============================================================
regionais_set = set()

for df_src in [df_redacao, df_objetivas, df_part, df_acessos]:
    if COL_REGIONAL in df_src.columns:
        regionais_set.update(df_src[COL_REGIONAL].dropna().unique())

regionais_no_arquivo = sorted(regionais_set)

# Remove a regional "DE UNIDADES ESCOLARES PRISIONAIS E SOCIOEDUCATIVAS"
nome_excluir = "DE UNIDADES ESCOLARES PRISIONAIS E SOCIOEDUCATIVAS".upper()
regionais_no_arquivo = [
    r for r in regionais_no_arquivo
    if isinstance(r, str) and r.strip().upper() != nome_excluir
]


if not regionais_no_arquivo:
    st.error("Nenhuma regional encontrada nas planilhas.")
    st.stop()

st.markdown(
    "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Regional:</div>",
    unsafe_allow_html=True
)
regional_escolhida = st.selectbox(
    "Selecione a Regional",        # label NÃO vazio
    regionais_no_arquivo,
    label_visibility="collapsed",  # esconde visualmente o label nativo
)


# st.subheader(f"")

# ===============================================================
# 3) Abas laterais
# ===============================================================
aba = st.sidebar.radio(
    "Selecione a aba",   # qualquer texto não vazio
    [
        "Redação: Médias e Participações por Escola",
        "Redação: Comparativos entre Escolas e Regionais",
        "Objetivas: Médias e Participações por Escola",
        "Objetivas: Comparativos entre Escolas e Regionais",
        "Tempos e Volumes de Participação nas Aplicações",
        "Detalhamento de Acessos",
    ],
    label_visibility="collapsed",  # esconde o texto, mas o label existe
)



# ===============================================================
# 4) Função auxiliar: filtrar escolas válidas (sem faltantes) por aba
# ===============================================================
def filtrar_escolas_validas(df_base: pd.DataFrame, cols_part, cols_notas_ou_acertos, percentual_notas: bool):
    """
    Retorna df_regional_valid (apenas linhas sem NaN nas colunas indicadas).
    """
    df_reg_regional = df_base[df_base[COL_REGIONAL] == regional_escolhida].copy()
    if df_reg_regional.empty:
        return df_reg_regional, df_reg_regional  # vazio

    df_num = df_reg_regional.copy()

    # Converter colunas numéricas para detectar NaN
    for c in cols_part:
        if c in df_num.columns:
            df_num[c] = serie_para_float(df_num[c], eh_percentual=True)
    for c in cols_notas_ou_acertos:
        if c in df_num.columns:
            df_num[c] = serie_para_float(df_num[c], eh_percentual=percentual_notas)

    mask_valid = (
        df_num[cols_part].notna().all(axis=1) &
        df_num[cols_notas_ou_acertos].notna().all(axis=1)
    )

    df_valid = df_reg_regional[mask_valid].copy()
    return df_reg_regional, df_valid



fig = go.Figure()



# ===============================================================
# 5) ABA: MÉDIAS E PARTICIPAÇÕES POR ESCOLA (Redação)
# ===============================================================
if aba == "Redação: Médias e Participações por Escola":
    # Filtra regionais e escolas válidas
    if COL_REGIONAL not in df_redacao.columns:
        st.error(f"A aba Dados_Redação não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    for c in COL_PART_RED + COL_NOTAS_RED:
        if c not in df_redacao.columns:
            st.error(f"Coluna '{c}' não encontrada em Dados_Redação.")
            st.stop()

    df_reg_red, df_reg_red_valid = filtrar_escolas_validas(
        df_redacao, COL_PART_RED, COL_NOTAS_RED, percentual_notas=False
    )

    if df_reg_red_valid.empty:
        st.warning("Nenhuma escola desta regional possui todos os dados de redação completos.")
        st.stop()

    # Escolha de escola + busca (apenas escolas sem faltantes)
    escolas_validas = sorted(df_reg_red_valid[COL_ESCOLA].dropna().unique())

    # Remove a linha da regional da lista de escolas (comparação robusta)
    reg_norm = regional_escolhida.strip().upper()
    escolas_validas = [
        e for e in escolas_validas
        if isinstance(e, str) and e.strip().upper() != reg_norm
    ]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Escola:</div>",
            unsafe_allow_html=True
        )
        escola_dropdown = st.selectbox(
            "Escola",
            escolas_validas,
            key="escola_dropdown_red_medias",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Buscar escola:</div>",
            unsafe_allow_html=True
        )
        termo_busca = st.text_input(
            "Buscar escola",
            key="busca_escola_red_medias",
            label_visibility="collapsed",
        )

    escola_escolhida = escola_dropdown
    if termo_busca:
        termo_lower = termo_busca.lower()
        filtradas = [e for e in escolas_validas if termo_lower in e.lower()]
        if filtradas:
            escola_escolhida = filtradas[0]
            st.caption(f"Busca: usando a escola **{escola_escolhida}**")
        else:
            st.info("Nenhuma escola encontrada para esse termo de busca.")

    df_escola = df_reg_red_valid[df_reg_red_valid[COL_ESCOLA] == escola_escolhida].copy()
    if df_escola.empty:
        st.warning("Não há dados completos para a escola selecionada.")
        st.stop()

    # Série única (primeira linha)
    part = serie_para_float(df_escola[COL_PART_RED].iloc[0], eh_percentual=True)
    notas = serie_para_float(df_escola[COL_NOTAS_RED].iloc[0], eh_percentual=False)

    part_frac  = part / 100.0
    notas_norm = notas / 1000.0

    etapas_red = [
        "1º Simulado",
        "1º Teste de Redação",
        "2º Teste de Redação",
        "2º Simulado",
        "3º Teste de Redação",
        "4º Teste de Redação",
    ]

    fig_red_medias = go.Figure()

    # Ajuste automático de rótulos (maior em cima, menor em baixo) em CADA avaliação
    pos_nota, pos_part = textpositions_por_etapa(notas_norm, part_frac)


    # Média da escola (preto, linha contínua)
    fig_red_medias.add_trace(
        go.Scatter(
            x=etapas_red,
            y=notas_norm,
            mode="lines+markers+text",
            name="Média da escola",
            text=[f"{v:.2f}" if pd.notna(v) else "" for v in notas],
            textposition=pos_nota,
            marker=dict(color="#000000"),
            line=dict(color="#000000"),
            hovertemplate="Etapa: %{x}<br>Nota: %{text}<extra></extra>",
        )
    )

    # Participação da escola (azul, linha contínua)
    fig_red_medias.add_trace(
        go.Scatter(
            x=etapas_red,
            y=part_frac,
            mode="lines+markers+text",
            name="Participação da escola",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part],
            textposition=pos_part,
            marker=dict(color="#1f77b4"),
            line=dict(color="#1f77b4"),
            hovertemplate="Etapa: %{x}<br>Participação: %{text}<extra></extra>",
        )
    )

    fig_red_medias.update_layout(
        title=dict(
            text=f"Médias e Participações por Escola (Redação): {escola_escolhida}",
            font=dict(size=26)
        ),
        font=dict(size=16),
        height=800,
        hoverlabel=dict(font_size=18),
        legend=dict(font=dict(size=16)),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(tickfont=dict(size=16)),
    )

    st.plotly_chart(fig_red_medias, use_container_width=True)

    # Tabela da regional (Redação)
    st.subheader("Participações e notas de redação da regional selecionada")
    cols_tabela = [COL_ESCOLA] + COL_PART_RED + COL_NOTAS_RED
    df_tabela = df_reg_red[cols_tabela].copy()

    # 1) converter para número
    for c in COL_PART_RED:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=True) / 100.0  # fração 0–1
    for c in COL_NOTAS_RED:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=False)

    # 2) aplicar formatação, mantendo o tipo float
    styler_red = df_tabela.style.format(
        {c: fmt_percent_br for c in COL_PART_RED} |
        {c: fmt_nota_br    for c in COL_NOTAS_RED}
    )

    st.dataframe(styler_red, use_container_width=True, hide_index=True)



# ===============================================================
# 5.1) ABA: COMPARATIVOS ENTRE ESCOLAS E REGIONAIS (Redação)
# ===============================================================
elif aba == "Redação: Comparativos entre Escolas e Regionais":
    # Filtra regionais e escolas válidas
    if COL_REGIONAL not in df_redacao.columns:
        st.error(f"A aba Dados_Redação não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    for c in COL_PART_RED + COL_NOTAS_RED:
        if c not in df_redacao.columns:
            st.error(f"Coluna '{c}' não encontrada em Dados_Redação.")
            st.stop()

    df_reg_red, df_reg_red_valid = filtrar_escolas_validas(
        df_redacao, COL_PART_RED, COL_NOTAS_RED, percentual_notas=False
    )

    if df_reg_red_valid.empty:
        st.warning("Nenhuma escola desta regional possui todos os dados de redação completos.")
        st.stop()

    # Escolha de escola + busca (apenas escolas sem faltantes)
    escolas_validas = sorted(df_reg_red_valid[COL_ESCOLA].dropna().unique())

    # Remove a linha da regional da lista de escolas (comparação robusta)
    reg_norm = regional_escolhida.strip().upper()
    escolas_validas = [
        e for e in escolas_validas
        if isinstance(e, str) and e.strip().upper() != reg_norm
    ]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Escola:</div>",
            unsafe_allow_html=True
        )
        escola_dropdown = st.selectbox(
            "Escola",
            escolas_validas,
            key="escola_dropdown_red_comp",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Buscar escola:</div>",
            unsafe_allow_html=True
        )
        termo_busca = st.text_input(
            "Buscar escola",
            key="busca_escola_red_comp",
            label_visibility="collapsed",
        )

    escola_escolhida = escola_dropdown
    if termo_busca:
        termo_lower = termo_busca.lower()
        filtradas = [e for e in escolas_validas if termo_lower in e.lower()]
        if filtradas:
            escola_escolhida = filtradas[0]
            st.caption(f"Busca: usando a escola **{escola_escolhida}**")
        else:
            st.info("Nenhuma escola encontrada para esse termo de busca.")

    df_escola = df_reg_red_valid[df_reg_red_valid[COL_ESCOLA] == escola_escolhida].copy()
    if df_escola.empty:
        st.warning("Não há dados completos para a escola selecionada.")
        st.stop()

    # Série da ESCOLA
    part = serie_para_float(df_escola[COL_PART_RED].iloc[0], eh_percentual=True)
    notas = serie_para_float(df_escola[COL_NOTAS_RED].iloc[0], eh_percentual=False)

    part_frac  = part / 100.0
    notas_norm = notas / 1000.0

    etapas_red = [
        "1º Simulado",
        "1º Teste de Redação",
        "2º Teste de Redação",
        "2º Simulado",
        "3º Teste de Redação",
        "4º Teste de Redação",
    ]

    # Série da REGIONAL (linha onde Escola ≈ nome da regional)
    mask_regional = (
        df_reg_red[COL_ESCOLA]
        .astype(str)
        .str.strip()
        .str.upper()
        == reg_norm
    )
    df_regional_row = df_reg_red[mask_regional].copy()

    part_reg = None
    notas_reg = None
    if not df_regional_row.empty:
        part_reg = serie_para_float(df_regional_row[COL_PART_RED].iloc[0], eh_percentual=True)
        notas_reg = serie_para_float(df_regional_row[COL_NOTAS_RED].iloc[0], eh_percentual=False)

    # ---------------------------
    # Gráfico 1: Médias (Escola vs Regional)
    # ---------------------------
    fig_medias = go.Figure()

    # Ajuste automático de rótulos (maior em cima, menor em baixo) em CADA avaliação
    pos_med_escola = ["top center"] * len(etapas_red)
    pos_med_reg    = ["top center"] * len(etapas_red)
    if notas_reg is not None:
        pos_med_escola, pos_med_reg = textpositions_por_etapa(notas_norm, (notas_reg / 1000.0))


    fig_medias.add_trace(
        go.Scatter(
            x=etapas_red,
            y=notas_norm,
            mode="lines+markers+text",
            name="Média da escola",
            text=[f"{v:.2f}" if pd.notna(v) else "" for v in notas],
            textposition=pos_med_escola,
            marker=dict(color="#2ca02c"),  # verde
            line=dict(color="#2ca02c"),
            hovertemplate="Etapa: %{x}<br>Média da escola: %{text}<extra></extra>",
        )
    )

    if notas_reg is not None:
        fig_medias.add_trace(
            go.Scatter(
                x=etapas_red,
                y=(notas_reg / 1000.0),
                mode="lines+markers+text",
                name="Média da regional",
                text=[f"{v:.2f}" if pd.notna(v) else "" for v in notas_reg],
                textposition=pos_med_reg,
                marker=dict(color="#FF8C00"),  # laranja
                line=dict(color="#FF8C00"),
                hovertemplate="Etapa: %{x}<br>Média da regional: %{text}<extra></extra>",
            )
        )

    fig_medias.update_layout(
        title=dict(
            text=f"Redação - Médias - {escola_escolhida}",
            font=dict(size=24)
        ),
        font=dict(size=16),
        height=800,
        hoverlabel=dict(font_size=18),
        legend=dict(font=dict(size=16)),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(tickfont=dict(size=16)),
    )

    # ---------------------------
    # Gráfico 2: Participações (Escola vs Regional)
    # ---------------------------
    fig_part = go.Figure()

    # Ajuste automático de rótulos (maior em cima, menor em baixo) em CADA avaliação
    pos_part_escola = ["top center"] * len(etapas_red)
    pos_part_reg    = ["top center"] * len(etapas_red)
    if part_reg is not None:
        pos_part_escola, pos_part_reg = textpositions_por_etapa(part_frac, (part_reg / 100.0))


    fig_part.add_trace(
        go.Scatter(
            x=etapas_red,
            y=part_frac,
            mode="lines+markers+text",
            name="Participação da escola",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part],
            textposition=pos_part_escola,
            marker=dict(color="#2ca02c"),  # verde
            line=dict(color="#2ca02c"),
            hovertemplate="Etapa: %{x}<br>Participação da escola: %{text}<extra></extra>",
        )
    )

    if part_reg is not None:
        fig_part.add_trace(
            go.Scatter(
                x=etapas_red,
                y=(part_reg / 100.0),
                mode="lines+markers+text",
                name="Participação da regional",
                text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part_reg],
                textposition=pos_part_reg,
                marker=dict(color="#FF8C00"),  # laranja
                line=dict(color="#FF8C00"),
                hovertemplate="Etapa: %{x}<br>Participação da regional: %{text}<extra></extra>",
            )
        )

    fig_part.update_layout(
        title=dict(
            text=f"Redação - Participações - {escola_escolhida}",
            font=dict(size=24)
        ),
        font=dict(size=16),
        height=800,
        hoverlabel=dict(font_size=18),
        legend=dict(font=dict(size=16)),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(tickfont=dict(size=16)),
    )

    st.plotly_chart(fig_medias, use_container_width=True)
    st.plotly_chart(fig_part, use_container_width=True)

    # Tabela da regional (Redação)
    st.subheader("Participações e notas de redação da regional selecionada")
    cols_tabela = [COL_ESCOLA] + COL_PART_RED + COL_NOTAS_RED
    df_tabela = df_reg_red[cols_tabela].copy()

    for c in COL_PART_RED:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=True) / 100.0
    for c in COL_NOTAS_RED:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=False)

    styler_red = df_tabela.style.format(
        {c: fmt_percent_br for c in COL_PART_RED} |
        {c: fmt_nota_br    for c in COL_NOTAS_RED}
    )

    st.dataframe(styler_red, use_container_width=True, hide_index=True)



# ===============================================================
# 6) ABA: MÉDIAS E PARTICIPAÇÕES POR ESCOLA (Objetivas)
# ===============================================================
elif aba == "Objetivas: Médias e Participações por Escola":
    # Conferência das colunas
    if COL_REGIONAL not in df_objetivas.columns:
        st.error(f"A aba Dados_Objetivas não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    for c in COL_PART_OBJ + COL_ACERTOS_OBJ:
        if c not in df_objetivas.columns:
            st.error(f"Coluna '{c}' não encontrada em Dados_Objetivas.")
            st.stop()

    # Filtra (escolas completas) dentro da regional selecionada
    df_reg_obj, df_reg_obj_valid = filtrar_escolas_validas(
        df_objetivas, COL_PART_OBJ, COL_ACERTOS_OBJ, percentual_notas=True
    )

    if df_reg_obj_valid.empty:
        st.warning("Nenhuma escola desta regional possui todos os dados de objetivas completos.")
        st.stop()

    escolas_validas = sorted(df_reg_obj_valid[COL_ESCOLA].dropna().unique())

    # Remove a linha da regional da lista de escolas (comparação robusta)
    reg_norm = regional_escolhida.strip().upper()
    escolas_validas = [
        e for e in escolas_validas
        if isinstance(e, str) and e.strip().upper() != reg_norm
    ]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Escola:</div>",
            unsafe_allow_html=True
        )
        escola_dropdown = st.selectbox(
            "Escola",
            escolas_validas,
            key="escola_dropdown_obj_medias",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Buscar escola:</div>",
            unsafe_allow_html=True
        )
        termo_busca = st.text_input(
            "Buscar escola",
            key="busca_escola_obj_medias",
            label_visibility="collapsed",
        )

    escola_escolhida = escola_dropdown
    if termo_busca:
        termo_lower = termo_busca.lower()
        filtradas = [e for e in escolas_validas if termo_lower in e.lower()]
        if filtradas:
            escola_escolhida = filtradas[0]
            st.caption(f"Busca: usando a escola **{escola_escolhida}**")
        else:
            st.info("Nenhuma escola encontrada para esse termo de busca.")

    # Linha da escola escolhida (dados completos)
    df_escola = df_reg_obj_valid[df_reg_obj_valid[COL_ESCOLA] == escola_escolhida].copy()
    if df_escola.empty:
        st.warning("Não há dados completos para a escola selecionada.")
        st.stop()

    part_obj = serie_para_float(df_escola[COL_PART_OBJ].iloc[0], eh_percentual=True)
    acertos_obj = serie_para_float(df_escola[COL_ACERTOS_OBJ].iloc[0], eh_percentual=True)

    part_obj_frac    = part_obj / 100.0
    acertos_obj_frac = acertos_obj / 100.0

    etapas_obj = ["1º Simulado", "2º Simulado"]

    fig_obj_medias = go.Figure()

    # Ajuste automático de rótulos (maior em cima, menor em baixo) em CADA avaliação
    pos_acertos, pos_part = textpositions_por_etapa(acertos_obj_frac, part_obj_frac)


    # Acertos da escola (preto, linha contínua)
    fig_obj_medias.add_trace(
        go.Scatter(
            x=etapas_obj,
            y=acertos_obj_frac,
            mode="lines+markers+text",
            name="Acertos da escola",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in acertos_obj],
            textposition=pos_acertos,
            marker=dict(color="#000000"),
            line=dict(color="#000000"),
            hovertemplate="Etapa: %{x}<br>Acertos: %{text}<extra></extra>",
        )
    )

    # Participação da escola (azul, linha contínua)
    fig_obj_medias.add_trace(
        go.Scatter(
            x=etapas_obj,
            y=part_obj_frac,
            mode="lines+markers+text",
            name="Participação da escola",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part_obj],
            textposition=pos_part,
            marker=dict(color="#1f77b4"),
            line=dict(color="#1f77b4"),
            hovertemplate="Etapa: %{x}<br>Participação: %{text}<extra></extra>",
        )
    )

    fig_obj_medias.update_layout(
        title=dict(
            text=f"Médias e Participações por Escola (Objetivas): {escola_escolhida}",
            font=dict(size=26)
        ),
        font=dict(size=16),
        height=800,
        hoverlabel=dict(font_size=18),
        legend=dict(font=dict(size=16)),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(tickfont=dict(size=16)),
    )

    st.plotly_chart(fig_obj_medias, use_container_width=True)

    # Tabela da regional (Objetivas)
    st.subheader("Participações e acertos (provas objetivas) da regional selecionada")
    cols_tabela = [COL_ESCOLA] + COL_PART_OBJ + COL_ACERTOS_OBJ
    df_tabela = df_reg_obj[cols_tabela].copy()

    for c in COL_PART_OBJ:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=True) / 100.0
    for c in COL_ACERTOS_OBJ:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=True) / 100.0

    styler_obj = df_tabela.style.format(
        {c: fmt_percent_br for c in COL_PART_OBJ} |
        {c: fmt_percent_br for c in COL_ACERTOS_OBJ}
    )

    st.dataframe(styler_obj, use_container_width=True, hide_index=True)



# ===============================================================
# 6.1) ABA: COMPARATIVOS ENTRE ESCOLAS E REGIONAIS (Objetivas)
# ===============================================================
elif aba == "Objetivas: Comparativos entre Escolas e Regionais":
    # Conferência das colunas
    if COL_REGIONAL not in df_objetivas.columns:
        st.error(f"A aba Dados_Objetivas não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    for c in COL_PART_OBJ + COL_ACERTOS_OBJ:
        if c not in df_objetivas.columns:
            st.error(f"Coluna '{c}' não encontrada em Dados_Objetivas.")
            st.stop()

    # Filtra (escolas completas) dentro da regional selecionada
    df_reg_obj, df_reg_obj_valid = filtrar_escolas_validas(
        df_objetivas, COL_PART_OBJ, COL_ACERTOS_OBJ, percentual_notas=True
    )

    if df_reg_obj_valid.empty:
        st.warning("Nenhuma escola desta regional possui todos os dados de objetivas completos.")
        st.stop()

    escolas_validas = sorted(df_reg_obj_valid[COL_ESCOLA].dropna().unique())

    reg_norm = regional_escolhida.strip().upper()
    escolas_validas = [
        e for e in escolas_validas
        if isinstance(e, str) and e.strip().upper() != reg_norm
    ]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Escola:</div>",
            unsafe_allow_html=True
        )
        escola_dropdown = st.selectbox(
            "Escola",
            escolas_validas,
            key="escola_dropdown_obj_comp",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Buscar escola:</div>",
            unsafe_allow_html=True
        )
        termo_busca = st.text_input(
            "Buscar escola",
            key="busca_escola_obj_comp",
            label_visibility="collapsed",
        )

    escola_escolhida = escola_dropdown
    if termo_busca:
        termo_lower = termo_busca.lower()
        filtradas = [e for e in escolas_validas if termo_lower in e.lower()]
        if filtradas:
            escola_escolhida = filtradas[0]
            st.caption(f"Busca: usando a escola **{escola_escolhida}**")
        else:
            st.info("Nenhuma escola encontrada para esse termo de busca.")

    # Linha da escola escolhida (dados completos)
    df_escola = df_reg_obj_valid[df_reg_obj_valid[COL_ESCOLA] == escola_escolhida].copy()
    if df_escola.empty:
        st.warning("Não há dados completos para a escola selecionada.")
        st.stop()

    part_obj = serie_para_float(df_escola[COL_PART_OBJ].iloc[0], eh_percentual=True)
    acertos_obj = serie_para_float(df_escola[COL_ACERTOS_OBJ].iloc[0], eh_percentual=True)

    part_obj_frac    = part_obj / 100.0
    acertos_obj_frac = acertos_obj / 100.0

    etapas_obj = ["1º Simulado", "2º Simulado"]

    # Linha da REGIONAL (onde "Escola" ≈ nome da regional)
    mask_regional_obj = (
        df_reg_obj[COL_ESCOLA].astype(str).str.strip().str.upper() == reg_norm
    )
    df_regional_row_obj = df_reg_obj[mask_regional_obj].copy()

    part_obj_reg = None
    acertos_obj_reg = None
    if not df_regional_row_obj.empty:
        part_obj_reg = serie_para_float(df_regional_row_obj[COL_PART_OBJ].iloc[0], eh_percentual=True)
        acertos_obj_reg = serie_para_float(df_regional_row_obj[COL_ACERTOS_OBJ].iloc[0], eh_percentual=True)

    # ---------------------------
    # Gráfico 1: Acertos (Escola vs Regional)
    # ---------------------------
    fig_acertos = go.Figure()

    # Ajuste automático de rótulos (maior em cima, menor em baixo) em CADA avaliação
    pos_acertos_escola = ["top center"] * len(etapas_obj)
    pos_acertos_reg    = ["top center"] * len(etapas_obj)
    if acertos_obj_reg is not None:
        pos_acertos_escola, pos_acertos_reg = textpositions_por_etapa(acertos_obj_frac, (acertos_obj_reg / 100.0))


    fig_acertos.add_trace(
        go.Scatter(
            x=etapas_obj,
            y=acertos_obj_frac,
            mode="lines+markers+text",
            name="Acertos da escola",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in acertos_obj],
            textposition=pos_acertos_escola,
            marker=dict(color="#2ca02c"),  # verde
            line=dict(color="#2ca02c"),
            hovertemplate="Etapa: %{x}<br>Acertos da escola: %{text}<extra></extra>",
        )
    )

    if acertos_obj_reg is not None:
        fig_acertos.add_trace(
            go.Scatter(
                x=etapas_obj,
                y=(acertos_obj_reg / 100.0),
                mode="lines+markers+text",
                name="Acertos da regional",
                text=[f"{v:.2f}%" if pd.notna(v) else "" for v in acertos_obj_reg],
                textposition=pos_acertos_reg,
                marker=dict(color="#FF8C00"),  # laranja
                line=dict(color="#FF8C00"),
                hovertemplate="Etapa: %{x}<br>Acertos da regional: %{text}<extra></extra>",
            )
        )

    fig_acertos.update_layout(
        title=dict(
            text=f"Provas Objetivas - Níveis de Acertos - {escola_escolhida}",
            font=dict(size=24)
        ),
        font=dict(size=16),
        height=800,
        hoverlabel=dict(font_size=18),
        legend=dict(font=dict(size=16)),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(tickfont=dict(size=16)),
    )

    # ---------------------------
    # Gráfico 2: Participação (Escola vs Regional)
    # ---------------------------
    fig_part = go.Figure()

    # Ajuste automático de rótulos (maior em cima, menor em baixo) em CADA avaliação
    pos_part_escola = ["top center"] * len(etapas_obj)
    pos_part_reg    = ["top center"] * len(etapas_obj)
    if part_obj_reg is not None:
        pos_part_escola, pos_part_reg = textpositions_por_etapa(part_obj_frac, (part_obj_reg / 100.0))


    fig_part.add_trace(
        go.Scatter(
            x=etapas_obj,
            y=part_obj_frac,
            mode="lines+markers+text",
            name="Participação da escola",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part_obj],
            textposition=pos_part_escola,
            marker=dict(color="#2ca02c"),  # verde
            line=dict(color="#2ca02c"),
            hovertemplate="Etapa: %{x}<br>Participação da escola: %{text}<extra></extra>",
        )
    )

    if part_obj_reg is not None:
        fig_part.add_trace(
            go.Scatter(
                x=etapas_obj,
                y=(part_obj_reg / 100.0),
                mode="lines+markers+text",
                name="Participação da regional",
                text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part_obj_reg],
                textposition=pos_part_reg,
                marker=dict(color="#FF8C00"),  # laranja
                line=dict(color="#FF8C00"),
                hovertemplate="Etapa: %{x}<br>Participação da regional: %{text}<extra></extra>",
            )
        )

    fig_part.update_layout(
        title=dict(
            text=f"Provas Objetivas - Participação - {escola_escolhida}",
            font=dict(size=24)
        ),
        font=dict(size=16),
        height=800,
        hoverlabel=dict(font_size=18),
        legend=dict(font=dict(size=16)),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(tickfont=dict(size=16)),
    )

    st.plotly_chart(fig_acertos, use_container_width=True)
    st.plotly_chart(fig_part, use_container_width=True)

    # Tabela da regional (Objetivas)
    st.subheader("Participações e acertos (provas objetivas) da regional selecionada")
    cols_tabela = [COL_ESCOLA] + COL_PART_OBJ + COL_ACERTOS_OBJ
    df_tabela = df_reg_obj[cols_tabela].copy()

    for c in COL_PART_OBJ:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=True) / 100.0
    for c in COL_ACERTOS_OBJ:
        df_tabela[c] = serie_para_float(df_tabela[c], eh_percentual=True) / 100.0

    styler_obj = df_tabela.style.format(
        {c: fmt_percent_br for c in COL_PART_OBJ} |
        {c: fmt_percent_br for c in COL_ACERTOS_OBJ}
    )

    st.dataframe(styler_obj, use_container_width=True, hide_index=True)



# ===============================================================
# 7) ABA: Tempos e Volumes de Participação nas Aplicações
# ===============================================================
# ===============================================================
elif aba == "Tempos e Volumes de Participação nas Aplicações":
    if COL_REGIONAL not in df_part.columns:
        st.error(f"A aba Dados_Participação não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    # Filtra pela regional escolhida (inclui escolas + linha de total da regional)
    df_part_reg_all = df_part[df_part[COL_REGIONAL] == regional_escolhida].copy()

    if df_part_reg_all.empty:
        st.warning("Não há registros de tempos/volumes de participação para esta regional.")
    else:
        # Colunas numéricas: de D até I  → índices 3 a 8 (0-based)
        cols_num_part = df_part_reg_all.columns[3:9]

        # Converter todas as linhas (escolas + regional) para número inteiro
        for c in cols_num_part:
            df_part_reg_all[c] = serie_para_float(
                df_part_reg_all[c], eh_percentual=False
            ).round()

        # Separa a linha de TOTAL da regional (Escola ≈ nome da regional)
        reg_norm = regional_escolhida.strip().upper()
        mask_regional = (
            df_part_reg_all[COL_ESCOLA]
            .astype(str)
            .str.strip()
            .str.upper()
            == reg_norm
        )

        df_regional_tot = df_part_reg_all[mask_regional].copy()
        # df_part_reg: só escolas (sem a linha de total)
        df_part_reg = df_part_reg_all[~mask_regional].copy()

        # Valores da regional por avaliação (para aparecer no hover)
        if not df_regional_tot.empty:
            linha_reg = df_regional_tot.iloc[0]
            reg_values = [linha_reg[c] for c in cols_num_part]
        else:
            # se não houver linha de regional, preenche com None
            reg_values = [None] * len(cols_num_part)

        if df_part_reg.empty:
            st.warning("Não há escolas individuais com dados nesta regional.")
            st.stop()

        # Dropdown de escolas da regional (já sem a linha de total)
        escolas_reg = sorted(df_part_reg[COL_ESCOLA].dropna().unique())

        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Escola:</div>",
            unsafe_allow_html=True
        )
        escola_escolhida = st.selectbox(
            "Escola",
            escolas_reg,
            key="escola_dropdown_part",
            label_visibility="collapsed",
        )

        # Filtra a escola escolhida
        df_escola_part = df_part_reg[df_part_reg[COL_ESCOLA] == escola_escolhida].copy()

        if df_escola_part.empty:
            st.warning("Não há registros de participação para a escola selecionada.")
        else:
            # Considera a primeira linha da escola
            linha = df_escola_part.iloc[0]
            x_labels = ["1º Simulado", "1º Teste de Redação", "2º Teste de Redação", "2º Simulado", "3º Teste de Redação", "4º Teste de Redação"]
            y_values = [linha[c] for c in cols_num_part]

            # Monta hover com variação abs., variação % e participantes da regional
            hover_texts = []
            prev_val = None
            for i, (label, val) in enumerate(zip(x_labels, y_values)):
                reg_val = reg_values[i] if i < len(reg_values) else None
                reg_str = fmt_int(reg_val) if reg_val is not None and not pd.isna(reg_val) else "-"

                if pd.isna(val):
                    hover_texts.append(f"Participantes (Regional): {reg_str}")
                elif prev_val is None or pd.isna(prev_val):
                    # primeiro ponto: só o valor + participantes da regional
                    hover_texts.append(
                        "<br>Participantes (Regional): "
                        + reg_str
                    )
                else:
                    var_abs = val - prev_val
                    if prev_val != 0 and not pd.isna(prev_val):
                        var_pct = (var_abs / prev_val) * 100
                        var_pct_str = f"{var_pct:.2f}%".replace(".", ",")
                    else:
                        var_pct_str = "-"
                    hover_texts.append(
                        "<br>Variação Absoluta: "
                        + fmt_int(var_abs)
                        + "<br>Variação Relativa: "
                        + var_pct_str
                        + "<br>Participantes (Regional): "
                        + reg_str
                    )
                prev_val = val

            # Gráfico de linhas
            fig_part = go.Figure()
            fig_part.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=y_values,
                    mode="lines+markers+text",
                    name="Valores (Escola)",
                    text=[fmt_int(v) if not pd.isna(v) else "" for v in y_values],
                    textposition="top center",
                    hoverinfo="text",
                    hovertext=hover_texts,
                )
            )

            fig_part.update_layout(
                title=dict(
                    text=f"Tempos e Volumes de Participação: {escola_escolhida}",
                    font=dict(size=24)
                ),
                font=dict(size=16),
                height=800,
                yaxis=dict(
                    title="",
                    showticklabels=False,
                ),
                xaxis=dict(
                    tickfont=dict(size=16)
                ),
                hoverlabel=dict(font_size=18),
            )

            st.plotly_chart(fig_part, use_container_width=True)

        # Tabela completa da regional (APENAS ESCOLAS, sem total da regional)
        styler_part = df_part_reg.style.format(
            {c: fmt_int for c in cols_num_part}
        )

        st.subheader("Tempos e Volumes de Participação nas Aplicações")
        st.dataframe(styler_part, use_container_width=True, hide_index=True)




# ===============================================================
# 8) ABA: Detalhamento de Acessos
# ===============================================================
elif aba == "Detalhamento de Acessos":
    if COL_REGIONAL not in df_acessos.columns:
        st.error(f"A aba Dados_Acesso_Detalhado não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    # Filtra pela regional escolhida (inclui escolas + total da regional)
    df_acessos_reg_all = df_acessos[df_acessos[COL_REGIONAL] == regional_escolhida].copy()

    if df_acessos_reg_all.empty:
        st.warning("Não há registros de acessos detalhados para esta regional.")
    else:
        # Remove a linha de total da regional (Escola ≈ nome da regional)
        reg_norm = regional_escolhida.strip().upper()
        mask_regional = (
            df_acessos_reg_all[COL_ESCOLA]
            .astype(str)
            .str.strip()
            .str.upper()
            == reg_norm
        )
        df_acessos_reg = df_acessos_reg_all[~mask_regional].copy()

        if df_acessos_reg.empty:
            st.warning("Não há escolas individuais com registros de acessos nesta regional.")
        else:
            # Colunas numéricas: de C até J → índices 2 a 9 (0-based)
            cols_num_acessos = df_acessos_reg.columns[2:10]

            for c in cols_num_acessos:
                df_acessos_reg[c] = (
                    serie_para_float(df_acessos_reg[c], eh_percentual=True) / 100.0
                )

            styler_acessos = df_acessos_reg.style.format(
                {c: fmt_percent_br for c in cols_num_acessos}
            )

            st.subheader("Detalhamento de Acessos")

            st.dataframe(styler_acessos, use_container_width=True, hide_index=True)



