# app.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.app_context import get_context, init_context
from services.data_loader import load_all

# -------------------------------------------------
# CONFIGURAÇÃO GERAL
# -------------------------------------------------
st.set_page_config(
    page_title="Financeiro Familiar",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Financeiro Familiar")
st.caption("Dashboard inteligente de saúde financeira familiar")

# -------------------------------------------------
# FUNÇÕES DE SEGURANÇA DE DADOS (CORREÇÃO DEFINITIVA)
# -------------------------------------------------
def ensure_list(obj):
    """
    Garante que sempre retornamos uma lista de dicionários,
    evitando erro do pandas ao criar DataFrame.
    """
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return [obj]
    return []

# -------------------------------------------------
# CONTEXTO / CONEXÃO
# -------------------------------------------------
init_context()
ctx = get_context()

with st.sidebar:
    st.header("🔧 Conexão")
    st.text_input("Repositório (owner/repo)", key="repo_full_name", value=ctx.repo_full_name or "")
    st.text_input("GitHub Token", key="github_token", type="password", value=ctx.github_token or "")
    st.text_input("Branch", key="branch_name", value=ctx.branch_name or "main")

    if st.button("Conectar"):
        from github_service import GitHubService
        try:
            ctx.gh = GitHubService(
                token=st.session_state.github_token,
                repo_full_name=st.session_state.repo_full_name,
                branch=st.session_state.branch_name
            )
            ctx.connected = True
            st.cache_data.clear()
            st.success("✅ Conectado ao GitHub")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao conectar: {e}")

    if not ctx.connected:
        st.warning("Conecte ao GitHub para continuar.")
        st.stop()

    st.divider()
    st.header("👤 Perfil")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil")

# -------------------------------------------------
# CARREGAMENTO DOS DADOS
# -------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))

receitas_raw = data["data/receitas.json"]["content"]
despesas_raw = data["data/despesas.json"]["content"]

# ✅ AQUI ESTÁ A CORREÇÃO-CHAVE
receitas = ensure_list(receitas_raw)
despesas = ensure_list(despesas_raw)

# -------------------------------------------------
# DATAFRAMES (AGORA SEGUROS)
# -------------------------------------------------
df_r = pd.DataFrame(receitas)
df_d = pd.DataFrame(despesas)

# -------------------------------------------------
# PREPARAÇÃO DO PERÍODO ATUAL
# -------------------------------------------------
hoje = date.today()
inicio = date(hoje.year, hoje.month, 1)
fim = hoje

if not df_r.empty:
    df_r["data"] = pd.to_datetime(df_r["data"], errors="coerce").dt.date
    df_r = df_r[(df_r["data"] >= inicio) & (df_r["data"] <= fim)]

if not df_d.empty:
    df_d["data"] = pd.to_datetime(df_d["data"], errors="coerce").dt.date
    if "excluido" in df_d.columns:
        df_d = df_d[df_d["excluido"] != True]
    df_d = df_d[(df_d["data"] >= inicio) & (df_d["data"] <= fim)]

# -------------------------------------------------
# KPIs BÁSICOS
# -------------------------------------------------
total_receitas = float(df_r["valor"].sum()) if not df_r.empty else 0.0
total_despesas = float(df_d["valor"].sum()) if not df_d.empty else 0.0
saldo = total_receitas - total_despesas

# -------------------------------------------------
# INDICADORES INTELIGENTES
# -------------------------------------------------
taxa_poupanca = (
    (total_receitas - total_despesas) / total_receitas
    if total_receitas > 0 else 0
)

despesas_fixas = (
    df_d[df_d.get("recorrente", False) == True]["valor"].sum()
    if not df_d.empty else 0.0
)

renda_comprometida = (
    despesas_fixas / total_receitas
    if total_receitas > 0 else 0
)

# -------------------------------------------------
# FUNÇÕES VISUAIS
# -------------------------------------------------
def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def classificar(valor, bom, alerta):
    if valor >= bom:
        return "🟢 Amanhoável"
    if valor >= alerta:
        return "🟡 Atenção"
    return "🔴 Risco"

def classificar_reverso(valor, bom, alerta):
    if valor <= bom:
        return "🟢 Amanhoável"
    if valor <= alerta:
        return "🟡 Atenção"
    return "🔴 Risco"

status_poupanca = classificar(taxa_poupanca, 0.20, 0.10)
status_comprometimento = classificar_reverso(renda_comprometida, 0.50, 0.70)

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
st.subheader("📊 Resumo Financeiro do Mês")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas", fmt_brl(total_receitas))
c2.metric("Despesas", fmt_brl(total_despesas))
c3.metric("Saldo", fmt_brl(saldo))
c4.metric("Taxa de poupança", f"{taxa_poupanca*100:.1f}%")

st.divider()

st.subheader("🧠 Saúde Financeira")

h1, h2 = st.columns(2)

with h1:
    st.metric("💰 Taxa de poupança", f"{taxa_poupanca*100:.1f}%")
    st.write(status_poupanca)

with h2:
    st.metric("📉 Renda comprometida", f"{renda_comprometida*100:.1f}%")
    st.write(status_comprometimento)

st.divider()

st.subheader("📌 Interpretação Automática")

if "🔴" in status_poupanca or "🔴" in status_comprometimento:
    st.error(
        "⚠️ Sua saúde financeira está em **RISCO**. "
        "Recomenda-se reduzir despesas fixas e aumentar a poupança."
    )
elif "🟡" in status_poupanca or "🟡" in status_comprometimento:
    st.warning(
        "⚠️ Atenção! Ajustes podem melhorar sua saúde financeira."
    )
else:
    st.success("✅ Parabéns! Sua saúde financeira está equilibrada.")

# -------------------------------------------------
# TENDÊNCIA DO SALDO
# -------------------------------------------------
st.subheader("📈 Tendência de saldo no mês")

if not df_r.empty or not df_d.empty:
    movs = pd.concat([
        df_r.assign(valor_signed=df_r["valor"]),
        df_d.assign(valor_signed=-df_d["valor"]),
    ])
    saldo_diario = movs.groupby("data")["valor_signed"].sum().cumsum()
    st.line_chart(saldo_diario)
else:
    st.info("Sem dados suficientes para gerar gráfico.")
