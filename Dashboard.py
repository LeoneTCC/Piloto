# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 11:09:08 2025

@author: rafae
"""

import pandas as pd
import streamlit as st
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Contratos Petrobras - Top Fornecedores",
    layout="wide",
)

st.title("📊 Contratos Petrobras")
st.subheader("Top 10 fornecedores por valor total de contratos (R$)")

# --- 1. URL DO CSV ---
CSV_URL = "https://raw.githubusercontent.com/LeoneTCC/Piloto/refs/heads/main/contratos_petrobras.csv"

# --- 2. Carregar e tratar dados ---
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL, sep=";", encoding="utf-8")
    # converter valor
    df["valor_contrato"] = (
        df["valor_contrato"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .replace("", "0")
        .astype(float)
    )
    return df

df = load_data()

# --- 3. Filtrar só contratos em reais ---
df_brl = df.loc[df["moeda"] == "R$"].copy()

# --- 4. Agrupar por fornecedor e somar ---
top_fornecedores = (
    df_brl.groupby("fornecedor", dropna=False)["valor_contrato"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)

# --- 5. Gráfico de barras ---
fig = px.bar(
    top_fornecedores,
    x="fornecedor",
    y="valor_contrato",
    title="Top 10 fornecedores por valor total de contratos (R$)",
    color="valor_contrato",
    color_continuous_scale="Blues",
)
fig.update_layout(
    xaxis_title="Fornecedor",
    yaxis_title="Valor total (R$)",
    xaxis_tickangle=45,
)

st.plotly_chart(fig, use_container_width=True)

# --- 6. Mostrar tabela opcional ---
with st.expander("📋 Ver dados usados no gráfico"):
    st.dataframe(top_fornecedores)
