
# app.py
import sys
from pathlib import Path
from datetime import date

import streamlit as st
import pandas as pd

# -------------------------------------------------
# Ajuste de path
# -------------------------------------------------
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.app_context import get_context, init_context
from services.data_loader import load_all, listar_categorias
from services.finance_core import normalizar_tx, saldo_atual
from services.utils import fmt_brl, fmt_date_br

st.set_page_config(
    page_title="Financeiro Familiar",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Financeiro Familiar")
st.caption("Dashboard inteligente de saúde financeira familiar")

# -------------------------------------------------
# Contexto / Conexão
# -------------------------------------------------
init_context()
ctx = get_context()

with st.sidebar:
    st.header("🔧 Conexão")

    st.text_input(
        "Repositório (owner/repo)",
        key="repo_full_name",
        value=ctx.get("repo_full_name", "")
    )
    st.text_input(
        "GitHub Token",
        key="github_token",
        type="password",
        value=ctx.get("github_token", "")
    )
    st.text_input(
        "Branch",
        key="branch_name",
        value=ctx.get("branch_name", "main")
    )

    if st.button("Conectar"):
        from github_service import GitHubService
        try:
            ctx["gh"] = GitHubService(
                token=st.session_state["github_token"],
                repo_full_name=st.session_state["repo_full_name"],
                branch=st.session_state["branch_name"],
            )
            ctx["connected"] = True
            st.cache_data.clear()
            st.success("✅ Conectado ao GitHub")
            st.rerun()
        except Exception as e:
            ctx["connected"] = False
            st.error(f"Erro ao conectar: {e}")

    if not ctx.get("connected"):
        st.warning("Conecte ao GitHub para continuar.")
        st.stop()

    st.divider()
    st.header("👤 Perfil")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil")

# -------------------------------------------------
# Carregamento de dados
# -------------------------------------------------
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

transacoes = [
    t for t in (normalizar_tx(x) for x in data["data/transacoes.json"]["content"])
    if t is not None
]
contas = data["data/contas.json"]["content"]

# -------------------------------------------------
# KPIs do mês
# -------------------------------------------------
hoje = date.today()
inicio = date(hoje.year, hoje.month, 1)

df = pd.DataFrame(transacoes)

rec_real = des_real = rec_prev = des_prev = 0.0

if not df.empty:
    df["data_prevista"] = pd.to_datetime(df["data_prevista"], errors="coerce").dt.date
    df["data_efetiva"] = pd.to_datetime(df["data_efetiva"], errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)

    realizadas = df[df["data_efetiva"].between(inicio, hoje)]
    previstas = df[
        df["data_efetiva"].isna()
        & df["data_prevista"].between(inicio, hoje)
    ]

    rec_real = realizadas.query("tipo == 'receita'")["valor"].sum()
    des_real = realizadas.query("tipo == 'despesa'")["valor"].sum()
    rec_prev = previstas.query("tipo == 'receita'")["valor"].sum()
    des_prev = previstas.query("tipo == 'despesa'")["valor"].sum()

saldo_real = rec_real - des_real
saldo_prev = rec_prev - des_prev

# -------------------------------------------------
# Saldo total das contas
# -------------------------------------------------
saldo_total = sum(saldo_atual(c, transacoes) for c in contas)

# -------------------------------------------------
# KPIs — Realizado
# -------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Receitas realizadas (mês)",
    fmt_brl(rec_real),
    help=f"{fmt_date_br(inicio)} → {fmt_date_br(hoje)}"
)

c2.metric(
    "Despesas realizadas (mês)",
    fmt_brl(des_real),
    help=f"{fmt_date_br(inicio)} → {fmt_date_br(hoje)}"
)

c3.metric(
    "Saldo realizado (mês)",
    fmt_brl(saldo_real)
)

c4.metric(
    "Saldo total (contas)",
    fmt_brl(saldo_total),
    help="Saldo inicial + transações efetivadas"
)

# -------------------------------------------------
# KPIs — Previsto
# -------------------------------------------------
c5, c6, c7 = st.columns(3)

c5.metric("Receitas previstas (mês)", fmt_brl(rec_prev))
c6.metric("Despesas previstas (mês)", fmt_brl(des_prev))
c7.metric("Saldo previsto (mês)", fmt_brl(saldo_prev))

st.divider()

# -------------------------------------------------
# CHANGE: gráfico com eixo temporal real
# -------------------------------------------------
st.subheader("📈 Tendência de saldo no mês")

incluir_previstas = st.checkbox(
    "Incluir previstas (projeção)",
    value=False
)

if not df.empty:
    base = df[df["data_efetiva"].notna()].copy()
    base["data_ref"] = base["data_efetiva"]

    if incluir_previstas:
        prevs = df[df["data_efetiva"].isna()].copy()
        prevs["data_ref"] = prevs["data_prevista"]
        base = pd.concat([base, prevs])

    base = base[
        base["data_ref"].between(inicio, hoje)
    ]

    base["signed"] = base.apply(
        lambda r: r["valor"] if r["tipo"] == "receita" else -r["valor"],
        axis=1
    )

    serie = (
        base.groupby("data_ref")["signed"]
        .sum()
        .sort_index()
        .cumsum()
    )

    st.line_chart(pd.DataFrame({"Saldo acumulado": serie}))

else:
    st.info("Sem dados suficientes para gerar o gráfico.")

st.divider()

# -------------------------------------------------
# Despesas por categoria
# -------------------------------------------------
st.subheader("🧩 Despesas por categoria (mês)")

if not df.empty:
    cats, _ = listar_categorias(ctx["gh"])
    cat_map = {c["id"]: c["nome"] for c in cats}

    despesas_mes = df[
        (df["tipo"] == "despesa")
        & df["data_efetiva"].between(inicio, hoje)
    ].copy()

    if despesas_mes.empty:
        st.info("Sem despesas realizadas neste mês.")
    else:
        despesas_mes["categoria"] = despesas_mes["categoria_id"].map(cat_map).fillna("Sem categoria")
        agg = despesas_mes.groupby("categoria")["valor"].sum().sort_values(ascending=False)
        st.bar_chart(agg)

else:
    st.info("Sem dados para agrupamento.")
