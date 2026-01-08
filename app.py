
# app.py
import sys
from pathlib import Path

# ---- Corrige ImportError: garante a raiz no sys.path ----
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
from datetime import date

from services.app_context import get_context, init_context
from services.data_loader import load_all, listar_categorias
from services.finance_core import normalizar_tx, saldo_atual
from services.utils import fmt_brl, data_ref_row, fmt_date_br

st.set_page_config(page_title="Financeiro Familiar", page_icon="💰", layout="wide")
st.title("💰 Financeiro Familiar")
st.caption("Dashboard inteligente de saúde financeira familiar")

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
# KPIs do mês — Realizadas vs Previstas
# -------------------------------------------------
hoje = date.today()
inicio = date(hoje.year, hoje.month, 1)

df = pd.DataFrame(transacoes)
if not df.empty:
    df["data_prevista_date"] = pd.to_datetime(df["data_prevista"], errors="coerce").dt.date
    df["data_efetiva_date"] = pd.to_datetime(df["data_efetiva"], errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["tipo"] = df["tipo"].astype(str)

    realizadas = df[df["data_efetiva_date"].between(inicio, hoje, inclusive="both")]
    previstas = df[(df["data_efetiva_date"].isna()) & (df["data_prevista_date"].between(inicio, hoje, inclusive="both"))]

    rec_real = float(realizadas[realizadas["tipo"] == "receita"]["valor"].sum())
    des_real = float(realizadas[realizadas["tipo"] == "despesa"]["valor"].sum())
    rec_prev = float(previstas[previstas["tipo"] == "receita"]["valor"].sum())
    des_prev = float(previstas[previstas["tipo"] == "despesa"]["valor"].sum())
else:
    rec_real = des_real = rec_prev = des_prev = 0.0

saldo_real = rec_real - des_real
saldo_prev = rec_prev - des_prev

# Saldos por conta (calculados com transações pagas)
saldo_total = 0.0
for conta in contas:
    saldo_total += saldo_atual(conta, transacoes)

# KPIs — Realizado
c1, c2, c3, c4 = st.columns(4)
c1.metric("Receitas realizadas (mês)", fmt_brl(rec_real), help=f"Somatório de receitas com data efetiva entre {fmt_date_br(inicio)} e {fmt_date_br(hoje)}")
c2.metric("Despesas realizadas (mês)", fmt_brl(des_real), help=f"Somatório de despesas com data efetiva entre {fmt_date_br(inicio)} e {fmt_date_br(hoje)}")
c3.metric("Saldo realizado (mês)", fmt_brl(saldo_real), help="Receitas realizadas − Despesas realizadas")
c4.metric("Saldo total (contas)", fmt_brl(saldo_total), help="Saldo inicial + histórico de transações efetivadas (todas as datas)")

# KPIs — Previsto
c5, c6, c7 = st.columns(3)
c5.metric("Receitas previstas (mês)", fmt_brl(rec_prev), help=f"Receitas sem data efetiva, previstas entre {fmt_date_br(inicio)} e {fmt_date_br(hoje)}")
c6.metric("Despesas previstas (mês)", fmt_brl(des_prev), help=f"Despesas sem data efetiva, previstas entre {fmt_date_br(inicio)} e {fmt_date_br(hoje)}")
c7.metric("Saldo previsto (mês)", fmt_brl(saldo_prev), help="Receitas previstas − Despesas previstas")

st.divider()

# -------------------------------------------------
# Tendência de saldo no mês (cash vs projeção)
# -------------------------------------------------
st.subheader("📈 Tendência de saldo no mês")
incluir_previstas = st.checkbox("Incluir previstas (projeção)", value=False, help="Quando marcado, inclui lançamentos previstos ainda não efetivados.")
if not df.empty:
    # Base: apenas efetivas para fluxo de caixa real
    efetivas = df.dropna(subset=["data_efetiva_date"]).copy()
    efetivas["data_ref"] = efetivas["data_efetiva_date"]
    efetivas = efetivas[(efetivas["data_ref"] >= inicio) & (efetivas["data_ref"] <= hoje)]

    if incluir_previstas:
        prevs = df[df["data_efetiva_date"].isna()].copy()
        prevs["data_ref"] = prevs["data_prevista_date"]
        prevs = prevs[(prevs["data_ref"] >= inicio) & (prevs["data_ref"] <= hoje)]
        base_df = pd.concat([efetivas, prevs], ignore_index=True)
    else:
        base_df = efetivas

    receitas_df = base_df[base_df["tipo"] == "receita"].copy()
    despesas_df = base_df[base_df["tipo"] == "despesa"].copy()

    receitas_df["valor_signed"] = receitas_df["valor"]
    despesas_df["valor_signed"] = -despesas_df["valor"]

    movs = pd.concat(
        [receitas_df[["data_ref", "valor_signed"]], despesas_df[["data_ref", "valor_signed"]]],
        ignore_index=True
    ).sort_values("data_ref")

    # Index como string BR para facilitar leitura no gráfico
    saldo_diario = movs.groupby("data_ref")["valor_signed"].sum()
    saldo_diario.index = saldo_diario.index.map(lambda d: fmt_date_br(d))
    st.line_chart(saldo_diario.cumsum())
else:
    st.info("Sem dados suficientes para gerar gráfico.")

st.divider()

# -------------------------------------------------
# Despesas por categoria (realizadas no mês)
# -------------------------------------------------
st.subheader("🧩 Despesas por categoria (realizadas no mês)")
if not df.empty:
    cats, _ = listar_categorias(ctx["gh"])
    cat_map = {c["id"]: c["nome"] for c in cats}
    realizadas_df = df.dropna(subset=["data_efetiva_date"]).copy()
    realizadas_df = realizadas_df[
        (realizadas_df["data_efetiva_date"] >= inicio) & (realizadas_df["data_efetiva_date"] <= hoje)
    ]
    despesas_df = realizadas_df[realizadas_df["tipo"] == "despesa"].copy()
    if despesas_df.empty:
        st.info("Sem despesas realizadas neste mês.")
    else:
        despesas_df["categoria_nome"] = despesas_df["categoria_id"].map(cat_map).fillna("Sem categoria")
        agg = despesas_df.groupby("categoria_nome")["valor"].sum().sort_values(ascending=False)
        st.bar_chart(agg)
else:
    st.info("Sem dados para agrupar por categoria.")
