# app.py
import streamlit as st
import pandas as pd
from datetime import date

from services.app_context import get_context, init_context
from services.data_loader import load_all, listar_categorias
from services.finance_core import normalizar_tx, saldo_atual
from services.status import derivar_status

st.set_page_config(page_title="Financeiro Familiar", page_icon="💰", layout="wide")
st.title("💰 Financeiro Familiar")
st.caption("Dashboard inteligente de saúde financeira familiar")

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# -------------------------------------------------
# Conexão
# -------------------------------------------------
init_context()
ctx = get_context()

with st.sidebar:
    st.header("🔧 Conexão")
    st.text_input("Repositório (owner/repo)", key="repo_full_name", value=ctx["repo_full_name"] or "")
    st.text_input("GitHub Token", key="github_token", type="password", value=ctx["github_token"] or "")
    st.text_input("Branch", key="branch_name", value=ctx["branch_name"] or "main")

    if st.button("Conectar"):
        from github_service import GitHubService
        try:
            ctx["gh"] = GitHubService(
                token=st.session_state["github_token"],
                repo_full_name=st.session_state["repo_full_name"],
                branch=st.session_state["branch_name"]
            )
            ctx["connected"] = True
            st.cache_data.clear()
            st.success("✅ Conectado ao GitHub")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao conectar: {e}")

    if not ctx.get("connected"):
        st.warning("Conecte ao GitHub para continuar.")
        st.stop()

    st.divider()
    st.header("👤 Perfil")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil")

# -------------------------------------------------
# Dados
# -------------------------------------------------
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

# ✅ Normalização defensiva
transacoes = [
    t for t in (normalizar_tx(x) for x in data["data/transacoes.json"]["content"])
    if t is not None
]
contas = data["data/contas.json"]["content"]

# -------------------------------------------------
# KPIs básicos do mês corrente
# -------------------------------------------------
hoje = date.today()
inicio = date(hoje.year, hoje.month, 1)

df = pd.DataFrame(transacoes)
if not df.empty:
    df["data_ref"] = pd.to_datetime(
        df["data_efetiva"].fillna(df["data_prevista"]),
        errors="coerce"
    ).dt.date
    df = df[(df["data_ref"] >= inicio) & (df["data_ref"] <= hoje)]
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["tipo"] = df["tipo"].astype(str)
    df["status"] = df.apply(lambda r: derivar_status(r.get("data_prevista"), r.get("data_efetiva")), axis=1)

total_receitas = float(df[df["tipo"] == "receita"]["valor"].sum()) if not df.empty else 0.0
total_despesas = float(df[df["tipo"] == "despesa"]["valor"].sum()) if not df.empty else 0.0
saldo_mes = total_receitas - total_despesas

# Saldos por conta (calculados com transações pagas)
saldo_total = 0.0
for conta in contas:
    saldo_total += saldo_atual(conta, transacoes)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas (mês)", fmt_brl(total_receitas))
c2.metric("Despesas (mês)", fmt_brl(total_despesas))
c3.metric("Saldo do mês", fmt_brl(saldo_mes))
c4.metric("Saldo total (contas)", fmt_brl(saldo_total))

st.divider()

st.subheader("📈 Tendência de saldo no mês")
if not df.empty:
    receitas_df = df[df["tipo"] == "receita"].copy()
    despesas_df = df[df["tipo"] == "despesa"].copy()

    receitas_df["valor_signed"] = receitas_df["valor"]
    despesas_df["valor_signed"] = -despesas_df["valor"]

    movs = pd.concat([receitas_df[["data_ref", "valor_signed"]],
                      despesas_df[["data_ref", "valor_signed"]]], ignore_index=True)
    movs = movs.sort_values("data_ref")
    saldo_diario = movs.groupby("data_ref")["valor_signed"].sum().cumsum()
    st.line_chart(saldo_diario)
else:
    st.info("Sem dados suficientes para gerar gráfico.")

st.divider()
st.subheader("🧩 Despesas por categoria (mês)")
if not df.empty:
    cats, _ = listar_categorias(ctx["gh"])
    cat_map = {c["id"]: c["nome"] for c in cats}
    despesas_df = df[df["tipo"] == "despesa"].copy()
    despesas_df["categoria_nome"] = despesas_df["categoria_id"].map(cat_map).fillna("Sem categoria")
    agg = despesas_df.groupby("categoria_nome")["valor"].sum().sort_values(ascending=False)
    st.bar_chart(agg)
else:
    st.info("Sem despesas no período para agrupar por categoria.")
