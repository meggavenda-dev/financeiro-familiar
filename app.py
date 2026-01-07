
# app.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.app_context import get_context, init_context
from services.data_loader import load_all

# ------------------------------------------------------------------
# Configuração geral
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Financeiro Familiar",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Financeiro Familiar")
st.caption("Dashboard inteligente de saúde financeira familiar")

# ------------------------------------------------------------------
# Contexto / Conexão
# ------------------------------------------------------------------
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
            st.success("✅ Conectado")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao conectar: {e}")

    if not ctx.connected:
        st.warning("Conecte ao GitHub para continuar.")
        st.stop()

    st.divider()
    st.header("👤 Perfil")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil")

# ------------------------------------------------------------------
# Carregamento dos dados
# ------------------------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))

receitas = data["data/receitas.json"]["content"]
despesas = data["data/despesas.json"]["content"]

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def classificar(valor, limites):
    """
    limites = (limite_verde, limite_amarelo)
    """
    if valor >= limites[0]:
        return "🟢 Amanhoável"
    if valor >= limites[1]:
        return "🟡 Atenção"
    return "🔴 Risco"

def classificar_reverso(valor, limites):
    """
    Quanto MENOR melhor (ex: renda comprometida)
    """
    if valor <= limites[0]:
        return "🟢 Amanhoável"
    if valor <= limites[1]:
        return "🟡 Atenção"
    return "🔴 Risco"

# ------------------------------------------------------------------
# Preparação dos dados (período atual)
# ------------------------------------------------------------------
hoje = date.today()
inicio = date(hoje.year, hoje.month, 1)
fim = hoje

df_r = pd.DataFrame(receitas)
df_d = pd.DataFrame(despesas)

if not df_r.empty:
    df_r["data"] = pd.to_datetime(df_r["data"]).dt.date
    df_r = df_r[(df_r["data"] >= inicio) & (df_r["data"] <= fim)]

if not df_d.empty:
    df_d["data"] = pd.to_datetime(df_d["data"]).dt.date
    df_d = df_d[(df_d["data"] >= inicio) & (df_d["data"] <= fim)]
    df_d = df_d[df_d.get("excluido", False) != True]

total_receitas = float(df_r["valor"].sum()) if not df_r.empty else 0.0
total_despesas = float(df_d["valor"].sum()) if not df_d.empty else 0.0
saldo = total_receitas - total_despesas

# ------------------------------------------------------------------
# Indicadores Inteligentes
# ------------------------------------------------------------------
taxa_poupanca = (
    (total_receitas - total_despesas) / total_receitas
    if total_receitas > 0 else 0
)

# Considera despesas "fixas" como recorrentes ou categorias essenciais
despesas_fixas = df_d[df_d.get("recorrente") == True]["valor"].sum() if not df_d.empty else 0.0

renda_comprometida = (
    despesas_fixas / total_receitas
    if total_receitas > 0 else 0
)

status_poupanca = classificar(
    taxa_poupanca,
    limites=(0.20, 0.10)
)

status_comprometimento = classificar_reverso(
    renda_comprometida,
    limites=(0.50, 0.70)
)

# ------------------------------------------------------------------
# KPIs PRINCIPAIS
# ------------------------------------------------------------------
st.subheader("📊 Resumo Financeiro do Mês")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas", fmt_brl(total_receitas))
c2.metric("Despesas", fmt_brl(total_despesas))
c3.metric("Saldo", fmt_brl(saldo))
c4.metric("Taxa de poupança", f"{taxa_poupanca*100:.1f}%")

st.divider()

# ------------------------------------------------------------------
# SAÚDE FINANCEIRA
# ------------------------------------------------------------------
st.subheader("🧠 Saúde Financeira")

h1, h2 = st.columns(2)

with h1:
    st.metric(
        "💰 Taxa de poupança",
        f"{taxa_poupanca*100:.1f}%",
        help="(Receitas - Despesas) / Receitas"
    )
    st.write(status_poupanca)

with h2:
    st.metric(
        "📉 Renda comprometida",
        f"{renda_comprometida*100:.1f}%",
        help="Despesas fixas / Receitas"
    )
    st.write(status_comprometimento)

st.divider()

# ------------------------------------------------------------------
# INTERPRETAÇÃO AUTOMÁTICA
# ------------------------------------------------------------------
st.subheader("📌 Interpretação automática")

if "🔴" in status_poupanca or "🔴" in status_comprometimento:
    st.error(
        "⚠️ Sua saúde financeira está em **RISCO**. "
        "Recomenda-se reduzir despesas fixas e aumentar a taxa de poupança."
    )
elif "🟡" in status_poupanca or "🟡" in status_comprometimento:
    st.warning(
        "⚠️ Atenção! Sua saúde financeira merece ajustes. "
        "Avalie oportunidades de economia."
    )
else:
    st.success(
        "✅ Parabéns! Sua saúde financeira está **equilibrada**."
    )

st.divider()

# ------------------------------------------------------------------
# TENDÊNCIA DO SALDO (opcional)
# ------------------------------------------------------------------
st.subheader("📈 Tendência do saldo no mês")

if not df_r.empty or not df_d.empty:
    movs = pd.concat([
        df_r.assign(valor_signed=df_r["valor"]),
        df_d.assign(valor_signed=-df_d["valor"]),
    ])
    s = movs.groupby("data")["valor_signed"].sum().cumsum()
    st.line_chart(s)
else:
    st.info("Sem dados suficientes para gerar gráfico.")
