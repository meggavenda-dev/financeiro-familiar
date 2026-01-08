
# app.py
import sys
from pathlib import Path
from datetime import date
import calendar

import streamlit as st
import pandas as pd

# -------------------------------------------------
# Ajuste de path
# -------------------------------------------------
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# -------------------------------------------------
# Imports internos
# -------------------------------------------------
from services.app_context import get_context, init_context
from services.data_loader import load_all, listar_categorias
from services.finance_core import normalizar_tx, saldo_atual
from services.utils import fmt_brl, fmt_date_br
from services.layout import responsive_columns, is_mobile
from services.ui import section

# -------------------------------------------------
# Configuração da página (MOBILE-FIRST)
# -------------------------------------------------
st.set_page_config(
    page_title="Financeiro Familiar",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("💰 Financeiro Familiar")
st.caption("Dashboard inteligente de saúde financeira familiar")

# -------------------------------------------------
# Contexto / Sessão
# -------------------------------------------------
init_context()
ctx = get_context()

# -------------------------------------------------
# Sidebar (controle + conexão)
# -------------------------------------------------
with st.sidebar:
    st.subheader("📱 Interface")
    st.toggle("Modo mobile", key="modo_mobile")

    st.divider()
    st.subheader("🔧 Conexão")

    st.text_input(
        "Repositório (owner/repo)",
        key="repo_full_name",
        value=ctx.get("repo_full_name", ""),
    )

    st.text_input(
        "GitHub Token",
        key="github_token",
        type="password",
        value=ctx.get("github_token", ""),
    )

    st.text_input(
        "Branch",
        key="branch_name",
        value=ctx.get("branch_name", "main"),
    )

    if st.button("Conectar", use_container_width=True):
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
            st.error(str(e))

    if not ctx.get("connected"):
        st.warning("Conecte ao GitHub para continuar.")
        st.stop()

    st.divider()
    st.subheader("👤 Perfil")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil")

# -------------------------------------------------
# Helpers locais (normalização robusta)
# -------------------------------------------------
def _parse_date_any(series: pd.Series) -> pd.Series:
    """
    Tenta converter para date com duas passadas:
    1) ISO/geral
    2) Formato brasileiro (dayfirst=True)
    Retorna uma Series de objetos date (ou NaT quando não possível).
    """
    s1 = pd.to_datetime(series, errors="coerce")
    mask = s1.isna()
    if mask.any():
        s2 = pd.to_datetime(series[mask], errors="coerce", dayfirst=True)
        s1 = s1.copy()
        s1[mask] = s2
    return s1.dt.date

def _normalizar_df(transacoes: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(transacoes)
    if df.empty:
        return df

    # Valor
    df["valor"] = pd.to_numeric(df.get("valor"), errors="coerce").fillna(0.0)

    # Soft-delete
    df["excluido"] = df.get("excluido", False)
    df["excluido"] = df["excluido"].fillna(False)
    df = df[df["excluido"] == False]

    # Tipo normalizado
    df["tipo"] = (
        df.get("tipo")
          .astype(str)
          .str.strip()
          .str.lower()
    )
    df = df[df["tipo"].isin(["despesa", "receita"])]

    # Datas com tolerância (ISO + dd/mm/aaaa)
    df["data_prevista"] = _parse_date_any(df.get("data_prevista"))
    df["data_efetiva"]  = _parse_date_any(df.get("data_efetiva"))

    # Data de referência única
    df["data_ref"] = df["data_efetiva"].combine_first(df["data_prevista"])

    # Remover linhas sem referência de data
    df = df.dropna(subset=["data_ref"])

    return df.reset_index(drop=True)

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
# Datas de trabalho
# -------------------------------------------------
hoje = date.today()
inicio = date(hoje.year, hoje.month, 1)
fim_mes = date(hoje.year, hoje.month, calendar.monthrange(hoje.year, hoje.month)[1])

# -------------------------------------------------
# DataFrame normalizado
# -------------------------------------------------
df = _normalizar_df(transacoes)

rec_real = des_real = rec_prev = des_prev = 0.0

if not df.empty:
    # Período corrente (até hoje) para realizados
    periodo_real = df[df["data_ref"].between(inicio, hoje)]
    realizadas = periodo_real[periodo_real["data_efetiva"].notna()]

    # Período do mês inteiro para previstas (planejamento)
    periodo_prev = df[df["data_ref"].between(inicio, fim_mes)]
    previstas = periodo_prev[periodo_prev["data_efetiva"].isna()]

    rec_real = realizadas.query("tipo == 'receita'")["valor"].sum()
    des_real = realizadas.query("tipo == 'despesa'")["valor"].sum()

    rec_prev = previstas.query("tipo == 'receita'")["valor"].sum()
    des_prev = previstas.query("tipo == 'despesa'")["valor"].sum()

saldo_real = rec_real - des_real
saldo_prev = rec_prev - des_prev

# -------------------------------------------------
# Saldo total das contas (caixa real)
# -------------------------------------------------
saldo_total = sum(saldo_atual(c, transacoes) for c in contas)

# -------------------------------------------------
# Helper: renderização segura de KPIs em N colunas
# -------------------------------------------------
def render_kpis(items, desktop_cols=4, mobile_cols=1):
    cols = responsive_columns(desktop=desktop_cols, mobile=mobile_cols)
    n = len(cols)
    for i, it in enumerate(items):
        col = cols[i % n]
        if len(it) == 3:
            label, value, help_txt = it
            col.metric(label, value, help=help_txt)
        else:
            label, value = it
            col.metric(label, value)

# -------------------------------------------------
# KPIs — Realizado
# -------------------------------------------------
section("📊 Resultado do mês")

kpis_realizado = [
    ("Receitas realizadas", fmt_brl(rec_real), f"{fmt_date_br(inicio)} → {fmt_date_br(hoje)}"),
    ("Despesas realizadas", fmt_brl(des_real), f"{fmt_date_br(inicio)} → {fmt_date_br(hoje)}"),
    ("Saldo realizado", fmt_brl(saldo_real)),
    ("Saldo total", fmt_brl(saldo_total), "Saldo inicial + transações efetivadas"),
]
render_kpis(kpis_realizado, desktop_cols=4, mobile_cols=1)

# -------------------------------------------------
# KPIs — Planejamento (mês inteiro)
# -------------------------------------------------
section("📅 Planejamento")

kpis_previsto = [
    ("Receitas previstas", fmt_brl(rec_prev)),
    ("Despesas previstas", fmt_brl(des_prev)),
    ("Saldo previsto", fmt_brl(saldo_prev)),
]
render_kpis(kpis_previsto, desktop_cols=3, mobile_cols=1)

st.divider()

# -------------------------------------------------
# Gráfico de saldo acumulado
# -------------------------------------------------
section("📈 Tendência de saldo no mês")

incluir_previstas = st.checkbox("Incluir previstas (projeção)", value=False)

if not df.empty:
    base = df.copy()

    # Se não incluir previstas, mantenha apenas efetivadas e até hoje
    if not incluir_previstas:
        base = base[base["data_efetiva"].notna()]
        base = base[base["data_ref"].between(inicio, hoje)]
    else:
        # Com previstas, considere o mês inteiro
        base = base[base["data_ref"].between(inicio, fim_mes)]

    if base.empty:
        st.info("Sem dados suficientes para gerar o gráfico.")
    else:
        base["signed"] = base.apply(
            lambda r: r["valor"] if r["tipo"] == "receita" else -r["valor"],
            axis=1,
        )

        serie = (
            base.groupby("data_ref")["signed"]
            .sum()
            .sort_index()
            .cumsum()
        )

        st.line_chart(
            pd.DataFrame({"Saldo acumulado": serie}),
            height=240 if is_mobile() else 420,
        )
else:
    st.info("Sem dados suficientes para gerar o gráfico.")

st.divider()

# -------------------------------------------------
# Despesas por categoria (mês inteiro)
# -------------------------------------------------
section("🧩 Despesas por categoria (mês)", "Inclui realizadas e previstas")

if not df.empty:
    cats, _ = listar_categorias(ctx["gh"])
    cat_map = {c["id"]: c["nome"] for c in cats}

    despesas_mes = df[
        (df["tipo"] == "despesa") &
        (df["data_ref"].between(inicio, fim_mes))
    ].copy()

    if despesas_mes.empty:
        st.info("Sem despesas no período.")
    else:
        despesas_mes["Categoria"] = (
            despesas_mes["categoria_id"]
            .map(cat_map)
            .fillna("Sem categoria")
        )

        graf = (
            despesas_mes
            .groupby("Categoria")["valor"]
            .sum()
            .sort_values(ascending=False)
        )

        st.bar_chart(
            graf,
            height=240 if is_mobile() else 420,
        )
else:
    st.info("Sem dados para agrupamento.")

# -------------------------------------------------
# 🔍 Diagnóstico (opcional)
# -------------------------------------------------
with st.expander("🔍 Diagnóstico (use para conferir filtros)", expanded=False):
    st.write("Registros totais em DF normalizado:", len(df))
    if not df.empty:
        st.write("Receitas realizadas (até hoje):", int(((df["tipo"] == "receita") & (df["data_efetiva"].notna()) & (df["data_ref"].between(inicio, hoje))).sum()))
        st.write("Despesas realizadas (até hoje):", int(((df["tipo"] == "despesa") & (df["data_efetiva"].notna()) & (df["data_ref"].between(inicio, hoje))).sum()))
        st.write("Receitas previstas (mês inteiro):", int(((df["tipo"] == "receita") & (df["data_efetiva"].isna()) & (df["data_ref"].between(inicio, fim_mes))).sum()))
        st.write("Despesas previstas (mês inteiro):", int(((df["tipo"] == "despesa") & (df["data_efetiva"].isna()) & (df["data_ref"].between(inicio, fim_mes))).sum()))

        st.write("Amostra de despesas (mês inteiro):")
        amostra = df[(df["tipo"] == "despesa") & (df["data_ref"].between(inicio, fim_mes))].head(10)
        st.dataframe(amostra[["descricao", "valor", "data_prevista", "data_efetiva", "data_ref", "categoria_id"]])
