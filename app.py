
# app.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from services.app_context import get_context, init_context
from services.data_loader import load_all

# ---------------- Config ----------------
st.set_page_config(page_title="Financeiro Familiar", page_icon="💰", layout="wide")
st.title("💰 Financeiro Familiar")
st.caption("MVP — GitHub como banco de dados • Python + Streamlit")

# ---------------- Contexto / Conexão ----------------
init_context()
ctx = get_context()

with st.sidebar:
    st.header("🔧 Conexão com GitHub")
    st.text_input("Repositório (owner/repo)", key="repo_full_name", value=ctx.repo_full_name or "")
    st.text_input("GitHub Token (PAT)", key="github_token", type="password", value=ctx.github_token or "")
    st.text_input("Branch", key="branch_name", value=ctx.branch_name or "main")
    connect_click = st.button("Conectar ao GitHub")

    if connect_click:
        try:
            ctx.gh = ctx.gh if "gh" in ctx and ctx.gh else None
            # força recriação do serviço com os valores atuais
            from github_service import GitHubService
            ctx.gh = GitHubService(
                token=st.session_state.github_token,
                repo_full_name=st.session_state.repo_full_name,
                branch=st.session_state.branch_name
            )
            ctx.connected = True
            st.success("✅ Conectado ao GitHub.")
            st.rerun()
        except Exception as e:
            ctx.connected = False
            st.error(f"Falha ao conectar ao GitHub: {e}")

    st.header("👤 Usuário / Perfil")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil", index=0)
    st.caption(f"Usuário atual: {ctx.usuario_id} • Perfil: {ctx.perfil}")

    st.header("🔄 Cache")
    if st.button("Atualizar dados (limpar cache)"):
        st.cache_data.clear()
        st.success("Cache limpo.")
        st.rerun()

# Se não conectado, interrompe com orientação
if not ctx.connected:
    st.warning("Informe repositório e token na barra lateral, e clique em **Conectar ao GitHub**.")
    st.stop()

# ---------------- Leitura de dados ----------------
data = load_all((ctx.repo_full_name, ctx.branch_name))

usuarios = data["data/usuarios.json"]["content"]
contas = data["data/contas.json"]["content"]
categorias = data["data/categorias.json"]["content"]
receitas = data["data/receitas.json"]["content"]
despesas = data["data/despesas.json"]["content"]
contas_pagar = data["data/contas_pagar.json"]["content"]
contas_receber = data["data/contas_receber.json"]["content"]
metas = data["data/metas.json"]["content"]

# ---------------- Filtros ----------------
with st.sidebar:
    st.header("🧮 Filtros do Dashboard")
    contas_opts = {c["nome"]: c["id"] for c in contas} if contas else {"Conta Corrente": "c1"}
    conta_sel_nome = st.selectbox("Conta", options=list(contas_opts.keys()), index=0)
    conta_sel = contas_opts[conta_sel_nome]
    hoje = date.today()
    inicio = st.date_input("Início", value=date(hoje.year, hoje.month, 1))
    fim = st.date_input("Fim", value=hoje)

# ---------------- Helpers ----------------
def to_df_movs(items, tipo: str):
    if not items:
        return pd.DataFrame(columns=["id", "data", "valor", "categoria_id", "conta_id", "pessoa_id", "tipo"])
    df = pd.DataFrame(items)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["tipo"] = tipo
    return df

def filtrar_por_periodo_conta(df: pd.DataFrame, conta_id: str, dt_inicio: date, dt_fim: date):
    if df.empty:
        return df
    m = (df["conta_id"] == conta_id) & (df["data"].dt.date >= dt_inicio) & (df["data"].dt.date <= dt_fim)
    return df.loc[m].copy()

def nome_categoria(cat_id: str, tipo: str):
    grupo = "receitas" if tipo == "receita" else "despesas"
    for c in categorias.get(grupo, []):
        if c["id"] == cat_id:
            return c["nome"]
    return "N/A"

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ---------------- Preparação ----------------
df_r_all = to_df_movs(receitas, "receita")
df_d_all = to_df_movs(despesas, "despesa")
df_r = filtrar_por_periodo_conta(df_r_all, conta_sel, inicio, fim)
df_d = filtrar_por_periodo_conta(df_d_all, conta_sel, inicio, fim)

valor_receitas = float(df_r["valor"].sum()) if not df_r.empty else 0.0
valor_despesas = float(df_d["valor"].sum()) if not df_d.empty else 0.0
saldo_periodo = valor_receitas - valor_despesas
saldo_inicial = next((float(c.get("saldo_inicial", 0.0)) for c in contas if c["id"] == conta_sel), 0.0)

df_r_proj = filtrar_por_periodo_conta(df_r_all, conta_sel, date.min, fim)
df_d_proj = filtrar_por_periodo_conta(df_d_all, conta_sel, date.min, fim)
saldo_projetado = saldo_inicial + float(df_r_proj["valor"].sum()) - float(df_d_proj["valor"].sum())

# ---------------- KPIs ----------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Receitas (período)", fmt_brl(valor_receitas))
col2.metric("Despesas (período)", fmt_brl(valor_despesas))
col3.metric("Saldo (período)", fmt_brl(saldo_periodo))
col4.metric("Saldo projetado", fmt_brl(saldo_projetado))

st.divider()

# ---------------- Gráfico: saldo acumulado diário ----------------
st.subheader("📈 Saldo acumulado diário (período)")
def saldo_diario(df_r: pd.DataFrame, df_d: pd.DataFrame, dt_inicio: date, dt_fim: date, saldo_base: float):
    df_r2 = df_r.copy(); df_d2 = df_d.copy()
    df_r2["valor_signed"] = df_r2["valor"]
    df_d2["valor_signed"] = -df_d2["valor"]
    df = pd.concat([df_r2[["data", "valor_signed"]], df_d2[["data", "valor_signed"]]], ignore_index=True)
    if df.empty:
        idx = pd.date_range(dt_inicio, dt_fim)
        return pd.DataFrame({"data": idx, "saldo": saldo_base})
    df = df.groupby(df["data"].dt.date)["valor_signed"].sum().sort_index().reset_index()
    idx = pd.date_range(dt_inicio, dt_fim)
    s = df.set_index(pd.to_datetime(df["data"]))["valor_signed"].reindex(idx, fill_value=0.0).cumsum() + saldo_base
    return pd.DataFrame({"data": idx, "saldo": s.values})

df_saldo = saldo_diario(df_r_proj, df_d_proj, inicio, fim, saldo_inicial)
st.line_chart(df_saldo.set_index("data"))

# ---------------- Receitas vs Despesas por mês ----------------
st.subheader("📊 Receitas vs Despesas por mês (conta selecionada)")
def by_month(df: pd.DataFrame, label: str):
    if df.empty:
        return pd.DataFrame(columns=["ano_mes", label])
    m = df.copy()
    m["ano_mes"] = m["data"].dt.strftime("%Y-%m")
    g = m.groupby("ano_mes")["valor"].sum().reset_index()
    g.rename(columns={"valor": label}, inplace=True)
    return g

m_r = by_month(df_r_proj, "Receitas")
m_d = by_month(df_d_proj, "Despesas")
m = pd.merge(m_r, m_d, on="ano_mes", how="outer").fillna(0.0).sort_values("ano_mes")
st.bar_chart(m.set_index("ano_mes"))

# ---------------- Despesas por categoria ----------------
st.subheader("🥧 Despesas por categoria (período)")
if df_d.empty:
    st.info("Sem despesas no período selecionado.")
else:
    df_d["categoria_nome"] = df_d["categoria_id"].apply(lambda cid: nome_categoria(cid, "despesa"))
    gcat = df_d.groupby("categoria_nome")["valor"].sum().reset_index()
    st.dataframe(gcat.rename(columns={"categoria_nome": "Categoria", "valor": "Total (R$)"}))
    st.bar_chart(gcat.set_index("categoria_nome"))

st.divider()
st.success("✅ Dashboard integrado aos módulos.")
