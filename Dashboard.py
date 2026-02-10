# -*- coding: utf-8 -*-
"""
Dashboard Petrobras - Resultados Preliminares (MVP)
Tema dark + KPIs + Top 10 fornecedores + Análise de Mercado (sem módulo de risco/vigência)

@author: rafae
"""

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------
# CONFIG / THEME
# ---------------------------
st.set_page_config(
    page_title="Petrobras | Contratos - Dashboard",
        layout="wide",
)

DARK_CSS = """
<style>
:root {
  --bg: #0E1117;
  --panel: #151A22;
  --panel2: #11151C;
  --text: #E6EAF2;
  --muted: #D7DEEE;
  --border: rgba(255,255,255,0.12);
  --shadow: 0 8px 24px rgba(0,0,0,0.35);
  --radius: 16px;
}

html, body, [class*="css"]  {
  background-color: var(--bg) !important;
  color: var(--text) !important;
}

section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, #0B0E14 0%, #0E1117 100%) !important;
  border-right: 1px solid var(--border);
}

.block-container{
  padding-top: 1.0rem;
  padding-bottom: 2.0rem;
}

h1, h2, h3, h4 {
  letter-spacing: -0.02em;
}

.card {
  background: linear-gradient(180deg, var(--panel) 0%, var(--panel2) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  box-shadow: var(--shadow);
}

.card-title{
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 8px;
}

.card-value{
  font-size: 1.55rem;
  font-weight: 700;
  line-height: 1.2;
}

.card-sub{
  font-size: 0.85rem;
  color: var(--muted);
  margin-top: 6px;
}

.hr {
  height: 1px;
  background: var(--border);
  margin: 10px 0 18px 0;
}
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"

# ---------------------------
# HELPERS (FORMATAÇÃO)
# ---------------------------
def fmt_int_pt(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")

def fmt_mm_pt(valor_reais: float) -> str:
    mm = int(round(float(valor_reais) / 1_000_000, 0)) if valor_reais else 0
    return fmt_int_pt(mm)

def fmt_reais_pt(valor_reais: float) -> str:
    v = int(round(float(valor_reais), 0)) if valor_reais else 0
    return fmt_int_pt(v)

def safe_str_series(s: pd.Series) -> pd.Series:
    return s.astype(str).fillna("").str.strip()

# ---------------------------
# DATA SOURCE
# ---------------------------
DEFAULT_CSV_URL = "https://raw.githubusercontent.com/LeoneTCC/Piloto/refs/heads/main/contratos_petrobras.csv"

st.sidebar.markdown("## ⚙️ Controles")
csv_url = st.sidebar.text_input("CSV (URL raw GitHub)", value=DEFAULT_CSV_URL)

# Navegação (1 arquivo só)
st.sidebar.markdown("## Páginas")
page = st.sidebar.radio(
    "Selecione",
    options=["Visão Global", "Análise por objeto"],
    index=0,
)

# ---------------------------
# LOAD / CLEAN
# ---------------------------
@st.cache_data(show_spinner=False)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, sep=";", encoding="utf-8")

    # normalizações defensivas
    if "moeda" in df.columns:
        df["moeda"] = safe_str_series(df["moeda"])
    else:
        df["moeda"] = ""

    # valor -> float
    if "valor_contrato" in df.columns:
        df["valor_contrato"] = (
            df["valor_contrato"]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .replace("", "0")
            .fillna("0")
            .astype(float)
        )
    else:
        df["valor_contrato"] = 0.0

    # datas -> datetime
    for col in ["inicio_vigencia", "fim_vigencia", "data_log_inclusao", "data_log_alteracao"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    # campos textuais defensivos
    for col in ["fornecedor", "objeto", "situacao", "modalidade", "unidade_adm"]:
        if col in df.columns:
            df[col] = safe_str_series(df[col])
        else:
            df[col] = ""

    # contrato id (para contagem)
    if "sq_contrato" not in df.columns:
        df["sq_contrato"] = ""

    return df

with st.spinner("Carregando dados..."):
    df = load_data(csv_url)

# ---------------------------
# HEADER
# ---------------------------
st.markdown("## Petrobras | Contratos")
st.markdown(
    "<div class='card-sub'>Resultados preliminares — KPIs + rankings + análises de mercado (base: Portal de Transparência Petrobras)</div>",
    unsafe_allow_html=True
)
st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

# ---------------------------
# BASE FILTER (BRL)
# ---------------------------
df_brl = df.loc[df["moeda"] == "R$"].copy()

# Filtros globais (aplicados em ambas as páginas)
# período (fim_vigencia) — mantém, mas você pode desligar se quiser
min_date = df_brl["fim_vigencia"].min()
max_date = df_brl["fim_vigencia"].max()

if pd.isna(min_date) or pd.isna(max_date):
    min_date = pd.Timestamp("2000-01-01")
    max_date = pd.Timestamp.today()

st.sidebar.markdown("### Filtros globais")
date_range = st.sidebar.date_input(
    "Período (fim da vigência)",
    value=(min_date.date(), max_date.date()),
)

situacoes = sorted([s for s in df_brl["situacao"].dropna().unique().tolist() if s.strip() != ""])
situacao_sel = st.sidebar.multiselect(
    "Situação",
    options=situacoes,
    default=situacoes[:],
)

keyword_obj = st.sidebar.text_input("Buscar no objeto (palavra-chave)", value="")

df_f = df_brl.copy()

# filtro datas
if isinstance(date_range, tuple) and len(date_range) == 2:
    d0 = pd.Timestamp(date_range[0])
    d1 = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    if "fim_vigencia" in df_f.columns:
        df_f = df_f.loc[
            (df_f["fim_vigencia"].notna())
            & (df_f["fim_vigencia"] >= d0)
            & (df_f["fim_vigencia"] <= d1)
        ]

# filtro situacao
if situacao_sel:
    df_f = df_f.loc[df_f["situacao"].isin(situacao_sel)]

# filtro keyword no objeto
if keyword_obj.strip():
    df_f = df_f.loc[df_f["objeto"].str.contains(keyword_obj.strip(), case=False, na=False)]

# ===========================
# PAGE 1 — VISÃO EXECUTIVA
# ===========================
if page == "Visão Global":
    # ---------------------------
    # KPIs
    # ---------------------------
    today = pd.Timestamp.today()
    valor_total = float(df_f["valor_contrato"].sum())
    qtd_contratos = int(len(df_f))
    qtd_fornecedores = int(df_f["fornecedor"].nunique(dropna=True))
    ticket_medio = float(valor_total / qtd_contratos) if qtd_contratos > 0 else 0.0

    # vencendo em 90 dias (mantido, já que você já tem — NÃO é “página de risco”, é um KPI simples)
    venc_90 = 0
    if "fim_vigencia" in df_f.columns:
        lim = today + pd.Timedelta(days=90)
        venc_90 = int(df_f.loc[
            df_f["fim_vigencia"].notna()
            & (df_f["fim_vigencia"] >= today)
            & (df_f["fim_vigencia"] <= lim)
        ].shape[0])

    ativos = 0
    if "fim_vigencia" in df_f.columns:
        ativos = int(df_f.loc[df_f["fim_vigencia"].notna() & (df_f["fim_vigencia"] >= today)].shape[0])

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    def card(container, title, value, sub=""):
        container.markdown(
            f"""
            <div class="card">
                <div class="card-title">{title}</div>
                <div class="card-value">{value}</div>
                <div class="card-sub">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    card(c1, "Valor Total (MM R$)", fmt_mm_pt(valor_total), "Somatório (BRL)")
    card(c2, "Contratos (#)", fmt_int_pt(qtd_contratos), "Contagem")
    card(c3, "Fornecedores", fmt_int_pt(qtd_fornecedores), "Únicos")
    card(c4, "Ticket médio (R$)", fmt_reais_pt(ticket_medio), "Valor/contrato")
    card(c5, "Ativos hoje", fmt_int_pt(ativos), "Base: Dia atual")
    card(c6, "Vencem em 90 dias", fmt_int_pt(venc_90), "Próximo da expiração")

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    # ---------------------------
    # TOP 10 (VALOR) + TOP 10 (QTD) — gráficos simétricos
    # ---------------------------
    left, right = st.columns([1, 1])

    top10_valor = (
        df_f.groupby("fornecedor", dropna=False)["valor_contrato"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )

    total_base = float(df_f["valor_contrato"].sum()) if len(df_f) else 0.0
    if total_base > 0:
        top10_valor["participacao_%"] = (top10_valor["valor_contrato"] / total_base) * 100
    else:
        top10_valor["participacao_%"] = 0.0

    fig_valor = px.bar(
        top10_valor,
        x="fornecedor",
        y="valor_contrato",
        text=top10_valor["participacao_%"].map(lambda x: f"{x:.1f}%"),
        title="Top 10 fornecedores por valor total de contratos (R$)",
        template=PLOTLY_TEMPLATE
    )
    fig_valor.update_layout(
        height=520,
        title_font_size=18,
        xaxis_title="Fornecedor",
        yaxis_title="Valor total (R$)",
        xaxis_tickangle=35,
        margin=dict(l=20, r=20, t=60, b=120),
    )
    fig_valor.update_traces(textposition="outside", cliponaxis=False)

    left.markdown("<div class='card'>", unsafe_allow_html=True)
    left.plotly_chart(fig_valor, use_container_width=True)
    left.markdown("</div>", unsafe_allow_html=True)

    top10_qtd = (
        df_f.groupby("fornecedor", dropna=False)["sq_contrato"]
        .count()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
        .rename(columns={"sq_contrato": "qtd_contratos"})
    )

    fig_qtd = px.bar(
        top10_qtd,
        x="fornecedor",
        y="qtd_contratos",
        title="Top 10 fornecedores por quantidade de contratos (#)",
        template=PLOTLY_TEMPLATE
    )
    fig_qtd.update_layout(
        height=520,
        title_font_size=18,  # igual ao da esquerda
        xaxis_title="Fornecedor",
        yaxis_title="Qtd contratos",
        xaxis_tickangle=35,
        margin=dict(l=20, r=20, t=60, b=120),  # igual ao da esquerda
    )

    right.markdown("<div class='card'>", unsafe_allow_html=True)
    right.plotly_chart(fig_qtd, use_container_width=True)
    right.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------
    # TABELA DETALHADA (TOP 10 POR VALOR) — ESQUERDA
    # ---------------------------
    if "fim_vigencia" in df_f.columns:
        det_valor = (
            df_f.loc[df_f["fornecedor"].isin(top10_valor["fornecedor"])]
            .groupby("fornecedor", dropna=False)
            .agg(
                valor_total=("valor_contrato", "sum"),
                qtd=("sq_contrato", "count"),
                ultimo_fim=("fim_vigencia", "max"),
                primeiro_inicio=("inicio_vigencia", "min"),
            )
            .reset_index()
        )
    else:
        det_valor = (
            df_f.loc[df_f["fornecedor"].isin(top10_valor["fornecedor"])]
            .groupby("fornecedor", dropna=False)
            .agg(valor_total=("valor_contrato", "sum"), qtd=("sq_contrato", "count"))
            .reset_index()
        )

    det_valor = det_valor.sort_values("valor_total", ascending=False)
    det_valor["valor_total_MM"] = (
        (det_valor["valor_total"] / 1_000_000).round(0).astype(int).apply(fmt_int_pt)
    )
    det_valor = det_valor.drop(columns=["valor_total"])

    left.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    with left:
        with st.expander("📋 Ver tabela (Top 10 por valor)"):
            if "ultimo_fim" in det_valor.columns:
                det_valor["ultimo_fim"] = det_valor["ultimo_fim"].dt.date
            if "primeiro_inicio" in det_valor.columns:
                det_valor["primeiro_inicio"] = det_valor["primeiro_inicio"].dt.date

            det_valor = det_valor.rename(columns={
                "fornecedor": "Fornecedor",
                "valor_total_MM": "Valor total (MM R$)",
                "qtd": "Qtd contratos",
                "ultimo_fim": "Último fim vigência",
                "primeiro_inicio": "Primeiro início vigência"
            })

            st.dataframe(det_valor, use_container_width=True, hide_index=True)

    # ---------------------------
    # TABELA DETALHADA (TOP 10 POR QTD) — DIREITA
    # ---------------------------
    if "fim_vigencia" in df_f.columns:
        det_qtd = (
            df_f.loc[df_f["fornecedor"].isin(top10_qtd["fornecedor"])]
            .groupby("fornecedor", dropna=False)
            .agg(
                valor_total=("valor_contrato", "sum"),
                qtd=("sq_contrato", "count"),
                ultimo_fim=("fim_vigencia", "max"),
                primeiro_inicio=("inicio_vigencia", "min"),
            )
            .reset_index()
        )
    else:
        det_qtd = (
            df_f.loc[df_f["fornecedor"].isin(top10_qtd["fornecedor"])]
            .groupby("fornecedor", dropna=False)
            .agg(valor_total=("valor_contrato", "sum"), qtd=("sq_contrato", "count"))
            .reset_index()
        )

    det_qtd = det_qtd.sort_values("qtd", ascending=False)
    det_qtd["valor_total_MM"] = (
        (det_qtd["valor_total"] / 1_000_000).round(0).astype(int).apply(fmt_int_pt)
    )
    det_qtd = det_qtd.drop(columns=["valor_total"])

    right.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    with right:
        with st.expander("📋 Ver tabela (Top 10 por quantidade)"):
            if "ultimo_fim" in det_qtd.columns:
                det_qtd["ultimo_fim"] = det_qtd["ultimo_fim"].dt.date
            if "primeiro_inicio" in det_qtd.columns:
                det_qtd["primeiro_inicio"] = det_qtd["primeiro_inicio"].dt.date

            det_qtd = det_qtd.rename(columns={
                "fornecedor": "Fornecedor",
                "valor_total_MM": "Valor total (MM R$)",
                "qtd": "Qtd contratos",
                "ultimo_fim": "Último fim vigência",
                "primeiro_inicio": "Primeiro início vigência"
            })

            st.dataframe(det_qtd, use_container_width=True, hide_index=True)

# ===========================
# PAGE 2 — ANÁLISE DE MERCADO 
# ===========================
else:
    # ---------------------------
    # CONTROLES DA PÁGINA 2
    # ---------------------------
    st.sidebar.markdown("### Segmentação por objeto")

    # “Categoria” aqui é um filtro por palavra-chave no objeto.
    # Você pode manter o texto livre (já tem) e adicionar presets rápidos.
    presets = [
        "(Nenhum preset)",
        "transporte",
        "manutenção",
        "serviços",
        "obra",
        "engenharia",
        "equipamento",
        "tecnologia",
        "software",
        "licença",
        "consultoria",
        "turbina",
        "bomba",
        "válvula",
    ]
    preset = st.sidebar.selectbox("Preset de categoria (objeto)", options=presets, index=0)
    cat_text = st.sidebar.text_input("Categoria (texto livre no objeto)", value="")

    top_n_share = st.sidebar.slider("Top N para market share", min_value=5, max_value=30, value=10, step=1)

    # aplica filtro de “categoria” na base já filtrada globalmente
    df_cat = df_f.copy()
    cat_query = ""

    if preset != "(Nenhum preset)":
        cat_query = preset.strip()

    if cat_text.strip():
        # se usuário escrever algo, prioriza texto livre
        cat_query = cat_text.strip()

    if cat_query:
        df_cat = df_cat.loc[df_cat["objeto"].str.contains(cat_query, case=False, na=False)]

    # ---------------------------
    # KPIs “de mercado” (categoria)
    # ---------------------------
    st.markdown("### Análise de Mercado (base filtrada)")
    st.markdown(
        "<div class='card-sub'>Market share, concentração (CR4/CR10), Pareto, dispersão (valor vs quantidade) e evolução temporal.</div>",
        unsafe_allow_html=True
    )
    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    total_cat = float(df_cat["valor_contrato"].sum())
    contratos_cat = int(len(df_cat))
    fornecedores_cat = int(df_cat["fornecedor"].nunique(dropna=True))
    ticket_cat = float(total_cat / contratos_cat) if contratos_cat > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)

    def card(container, title, value, sub=""):
        container.markdown(
            f"""
            <div class="card">
                <div class="card-title">{title}</div>
                <div class="card-value">{value}</div>
                <div class="card-sub">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    card(c1, "Categoria (objeto)", cat_query if cat_query else "Sem recorte", "Filtro por palavra no objeto")
    card(c2, "Valor total (MM R$)", fmt_mm_pt(total_cat), "Somatório (categoria)")
    card(c3, "Contratos (#)", fmt_int_pt(contratos_cat), "Contagem (categoria)")
    card(c4, "Ticket médio (R$)", fmt_reais_pt(ticket_cat), "Valor/contrato (categoria)")

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    # ---------------------------
    # MARKET SHARE + CR4/CR10 + PARETO
    # ---------------------------
    # share por fornecedor
    share = (
        df_cat.groupby("fornecedor", dropna=False)["valor_contrato"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"valor_contrato": "valor_total"})
    )
    base_val = float(share["valor_total"].sum()) if len(share) else 0.0
    share["share_%"] = (share["valor_total"] / base_val * 100) if base_val > 0 else 0.0
    share["share_%"] = share["share_%"].fillna(0.0)

    # CR4 / CR10
    cr4 = float(share.head(4)["share_%"].sum()) if len(share) else 0.0
    cr10 = float(share.head(10)["share_%"].sum()) if len(share) else 0.0

    # Pareto (cumulativo)
    share["cum_%"] = share["share_%"].cumsum()

    top_share = share.head(top_n_share).copy()
    top_share["valor_MM"] = (top_share["valor_total"] / 1_000_000).round(0).astype(int)

    # layout em 2 colunas
    a, b = st.columns([1, 1])

    # gráfico market share
    fig_share = px.bar(
        top_share,
        x="fornecedor",
        y="share_%",
        title=f"Market share (Top {top_n_share}) — participação no valor total (%)",
        template=PLOTLY_TEMPLATE
    )
    fig_share.update_layout(
        height=460,
        title_font_size=18,
        xaxis_title="Fornecedor",
        yaxis_title="Participação (%)",
        xaxis_tickangle=35,
        margin=dict(l=20, r=20, t=60, b=120),
    )

    a.markdown("<div class='card'>", unsafe_allow_html=True)
    a.plotly_chart(fig_share, use_container_width=True)
    a.markdown("</div>", unsafe_allow_html=True)

    # Pareto (linha cumulativa) + barras (share)
    pareto = share.head(max(top_n_share, 10)).copy()
    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(
        x=pareto["fornecedor"],
        y=pareto["share_%"],
        name="Share (%)"
    ))
    fig_pareto.add_trace(go.Scatter(
        x=pareto["fornecedor"],
        y=pareto["cum_%"],
        name="Cumulativo (%)",
        mode="lines+markers",
        yaxis="y2"
    ))
    fig_pareto.update_layout(
        template=PLOTLY_TEMPLATE,
        height=460,
        title=f"Pareto — share + cumulativo (Top {max(top_n_share, 10)})",
        title_font_size=18,
        xaxis=dict(title="Fornecedor", tickangle=35),
        yaxis=dict(title="Share (%)"),
        yaxis2=dict(title="Cumulativo (%)", overlaying="y", side="right", range=[0, 100]),
        margin=dict(l=20, r=20, t=60, b=120),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    b.markdown("<div class='card'>", unsafe_allow_html=True)
    b.plotly_chart(fig_pareto, use_container_width=True)
    b.markdown("</div>", unsafe_allow_html=True)

    # cards CR4/CR10
    c1, c2 = st.columns(2)
    card(c1, "CR4 (%)", f"{cr4:.1f}", "Soma do share dos 4 maiores")
    card(c2, "CR10 (%)", f"{cr10:.1f}", "Soma do share dos 10 maiores")

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    # ---------------------------
    # SCATTER: VALOR vs QTD (fornecedores)
    # ---------------------------
    agg = (
        df_cat.groupby("fornecedor", dropna=False)
        .agg(
            valor_total=("valor_contrato", "sum"),
            qtd_contratos=("sq_contrato", "count")
        )
        .reset_index()
    )
    agg["valor_MM"] = agg["valor_total"] / 1_000_000

    fig_scatter = px.scatter(
        agg,
        x="qtd_contratos",
        y="valor_MM",
        hover_name="fornecedor",
        title="Dispersão — fornecedores (Qtd contratos vs Valor total)",
        template=PLOTLY_TEMPLATE
    )
    fig_scatter.update_layout(
        height=520,
        title_font_size=18,
        xaxis_title="Qtd contratos (#)",
        yaxis_title="Valor total (MM R$)",
        margin=dict(l=20, r=20, t=60, b=60),
    )

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.plotly_chart(fig_scatter, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------
    # EVOLUÇÃO TEMPORAL (ano) — usando início de vigência
    # ---------------------------
    df_time = df_cat.copy()
    if "inicio_vigencia" in df_time.columns:
        df_time["ano"] = df_time["inicio_vigencia"].dt.year
    else:
        df_time["ano"] = pd.NA

    df_time = df_time.dropna(subset=["ano"])
    if len(df_time):
        serie = (
            df_time.groupby("ano")["valor_contrato"]
            .sum()
            .sort_index()
            .reset_index()
            .rename(columns={"valor_contrato": "valor_total"})
        )
        serie["valor_MM"] = serie["valor_total"] / 1_000_000

        fig_time = px.line(
            serie,
            x="ano",
            y="valor_MM",
            markers=True,
            title="Evolução temporal — valor contratado por ano (início da vigência)",
            template=PLOTLY_TEMPLATE
        )
        fig_time.update_layout(
            height=420,
            title_font_size=18,
            xaxis_title="Ano",
            yaxis_title="Valor (MM R$)",
            margin=dict(l=20, r=20, t=60, b=60),
        )

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.plotly_chart(fig_time, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Não há dados suficientes de 'inicio_vigencia' para montar a evolução temporal com o recorte atual.")

    # ---------------------------
    # TABELA: TOP PLAYERS (market share)
    # ---------------------------
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    with st.expander("📋 Ver tabela — Top players (market share)"):
        t = share.copy()
        t["Valor total (MM R$)"] = (t["valor_total"] / 1_000_000).round(0).astype(int).apply(fmt_int_pt)
        t["Share (%)"] = t["share_%"].map(lambda x: f"{x:.2f}")
        t["Cumulativo (%)"] = t["cum_%"].map(lambda x: f"{x:.2f}")
        t = t.rename(columns={"fornecedor": "Fornecedor"})[["Fornecedor", "Valor total (MM R$)", "Share (%)", "Cumulativo (%)"]]
        st.dataframe(t.head(50), use_container_width=True, hide_index=True)


