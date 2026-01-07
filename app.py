
# app.py
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from github_service import GitHubService

# ---------------- Config inicial ----------------
st.set_page_config(page_title="Financeiro Familiar", page_icon="💰", layout="wide")
st.title("💰 Financeiro Familiar")
st.caption("MVP — GitHub como banco de dados • Python + Streamlit")

# ---------------- Secrets / Conexão GitHub ----------------
DEFAULT_REPO = st.secrets.get("repo_full_name", "")
DEFAULT_TOKEN = st.secrets.get("github_token", "")
DEFAULT_BRANCH = st.secrets.get("branch_name", "main")

with st.sidebar:
    st.header("🔧 Configuração")
    repo_full_name = st.text_input("Repositório (owner/repo)", value=DEFAULT_REPO, placeholder="usuario/repo")
    github_token = st.text_input("GitHub Token (PAT)", value=DEFAULT_TOKEN, type="password")
    branch_name = st.text_input("Branch", value=DEFAULT_BRANCH)
    st.info("O token precisa de escopo 'repo'.")
    ready = st.button("Conectar ao GitHub")

# Conecta automaticamente se secrets estiverem preenchidos
if not ready and (not (repo_full_name and github_token)):
    st.warning("Informe repositório, token e branch na barra lateral e clique em **Conectar ao GitHub**.")
    st.stop()

gh = GitHubService(token=github_token, repo_full_name=repo_full_name, branch=branch_name)

# ---------------- Defaults ----------------
DEFAULTS = {
    "data/usuarios.json": [
        {"id": "u1", "nome": "Administrador", "perfil": "admin"}
    ],
    "data/contas.json": [
        {"id": "c1", "nome": "Conta Corrente", "tipo": "banco", "moeda": "BRL", "saldo_inicial": 0.0}
    ],
    "data/categorias.json": {
        "receitas": [
            {"id": "cr1", "nome": "Salário"},
            {"id": "cr2", "nome": "Freelancer"},
            {"id": "cr3", "nome": "Aluguel Recebido"}
        ],
        "despesas": [
            {"id": "cd1", "nome": "Moradia"},
            {"id": "cd2", "nome": "Alimentação"},
            {"id": "cd3", "nome": "Transporte"},
            {"id": "cd4", "nome": "Educação"},
            {"id": "cd5", "nome": "Lazer"}
        ]
    },
    "data/receitas.json": [],
    "data/despesas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    "data/metas.json": []
}

# ---------------- Leitura com cache ----------------
@st.cache_data(ttl=60, show_spinner=False)
def load_all(gh_service: GitHubService):
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh_service.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}
    return data

with st.sidebar:
    if st.button("🔄 Atualizar dados (limpar cache)"):
        st.cache_data.clear()

data_map = load_all(gh)

usuarios = data_map["data/usuarios.json"]["content"]
contas = data_map["data/contas.json"]["content"]
categorias = data_map["data/categorias.json"]["content"]
receitas = data_map["data/receitas.json"]["content"]
despesas = data_map["data/despesas.json"]["content"]
contas_pagar = data_map["data/contas_pagar.json"]["content"]
contas_receber = data_map["data/contas_receber.json"]["content"]
metas = data_map["data/metas.json"]["content"]

# ---------------- Sidebar: Usuário & Filtros ----------------
with st.sidebar:
    st.header("👤 Usuário")
    users_opts = {u["nome"]: u["id"] for u in usuarios} if usuarios else {"Administrador": "u1"}
    usuario_sel_nome = st.selectbox("Usuário atual", options=list(users_opts.keys()), index=0)
    usuario_sel = users_opts[usuario_sel_nome]
    st.caption(f"Perfil: {next((u['perfil'] for u in usuarios if u['id'] == usuario_sel), 'admin')}")

with st.sidebar:
    st.header("🧮 Filtros")
    contas_opts = {c["nome"]: c["id"] for c in contas}
    conta_sel_nome = st.selectbox("Conta", options=list(contas_opts.keys()), index=0)
    conta_sel = contas_opts[conta_sel_nome]
    hoje = date.today()
    inicio = st.date_input("Início", value=date(hoje.year, hoje.month, 1))
    fim = st.date_input("Fim", value=hoje)

# ---------------- Helpers ----------------
def to_df_movs(items, tipo: str):
    """Converte receitas/despesas em DataFrame padronizado."""
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

# ---------------- Preparação de dados ----------------
df_r_all = to_df_movs(receitas, "receita")
df_d_all = to_df_movs(despesas, "despesa")

df_r = filtrar_por_periodo_conta(df_r_all, conta_sel, inicio, fim)
df_d = filtrar_por_periodo_conta(df_d_all, conta_sel, inicio, fim)

valor_receitas = float(df_r["valor"].sum()) if not df_r.empty else 0.0
valor_despesas = float(df_d["valor"].sum()) if not df_d.empty else 0.0
saldo_periodo = valor_receitas - valor_despesas

saldo_inicial = next((float(c.get("saldo_inicial", 0.0)) for c in contas if c["id"] == conta_sel), 0.0)

# Saldo projetado = saldo inicial + todas as receitas/despesas até fim do período (conta selecionada)
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

# ---------------- Gráfico: receitas vs despesas por mês ----------------
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

# ---------------- Resumo: Contas a Pagar / Receber ----------------
st.subheader("📅 Resumo de Contas a Pagar / Receber (período)")

def to_df_contas(items, tipo: str):
    if not items:
        return pd.DataFrame(columns=["id", "descricao", "valor", "conta_id", "status", "data_ref", "tipo"])
    df = pd.DataFrame(items).copy()
    # Para pagar usamos 'vencimento', para receber usamos 'previsto'
    col_data = "vencimento" if tipo == "pagar" else "previsto"
    df["data_ref"] = pd.to_datetime(df[col_data], errors="coerce")
    df["tipo"] = tipo
    return df

df_p_all = to_df_contas(contas_pagar, "pagar")
df_rc_all = to_df_contas(contas_receber, "receber")

def filtrar_contas(df: pd.DataFrame, conta_id: str, dt_inicio: date, dt_fim: date):
    if df.empty:
        return df
    m = (df["conta_id"] == conta_id) & (df["data_ref"].dt.date >= dt_inicio) & (df["data_ref"].dt.date <= dt_fim)
    return df.loc[m].copy()

df_p = filtrar_contas(df_p_all, conta_sel, inicio, fim)
df_rc = filtrar_contas(df_rc_all, conta_sel, inicio, fim)

total_pagar_aberto = float(df_p[df_p["status"] == "em_aberto"]["valor"].sum()) if not df_p.empty else 0.0
total_receber_aberto = float(df_rc[df_rc["status"] == "em_aberto"]["valor"].sum()) if not df_rc.empty else 0.0

# Atrasadas: data_ref < hoje e status em_aberto
hoje_dt = hoje
atrasadas = df_p[(df_p["status"] == "em_aberto") & (df_p["data_ref"].dt.date < hoje_dt)] if not df_p.empty else pd.DataFrame()
qt_atrasadas = len(atrasadas)
val_atrasadas = float(atrasadas["valor"].sum()) if not atrasadas.empty else 0.0

# Próximas 7 dias
prox_7 = df_p[(df_p["status"] == "em_aberto") & (df_p["data_ref"].dt.date >= hoje_dt) & (df_p["data_ref"].dt.date <= (hoje_dt + timedelta(days=7)))] if not df_p.empty else pd.DataFrame()
qt_prox7 = len(prox_7)
val_prox7 = float(prox_7["valor"].sum()) if not prox_7.empty else 0.0

c1, c2, c3 = st.columns(3)
c1.metric("A pagar (em aberto)", fmt_brl(total_pagar_aberto))
c2.metric("A receber (em aberto)", fmt_brl(total_receber_aberto))
c3.metric("Atrasadas (qtd / valor)", f"{qt_atrasadas} / {fmt_brl(val_atrasadas)}")

st.caption(f"Próximas 7 dias em aberto: {qt_prox7} • {fmt_brl(val_prox7)}")

# ---------------- Resumo: Metas ----------------
st.divider()
st.subheader("🎯 Metas — progresso rápido")

if metas:
    for m in metas[:3]:  # mostra as top 3
        nome = m.get("nome", "Meta")
        valor_meta = float(m.get("valor_meta", 0.0))
        valor_acumulado = float(m.get("valor_acumulado", 0.0))
        data_meta = m.get("data_meta")
        progresso = (valor_acumulado / valor_meta) if valor_meta > 0 else 0.0
        progresso = max(0.0, min(progresso, 1.0))
        # meses restantes
        try:
            meses_rest = max((date.fromisoformat(data_meta) - hoje).days // 30, 1)
        except Exception:
            meses_rest = 1
        aporte_sugerido = (valor_meta - valor_acumulado) / meses_rest if valor_meta > valor_acumulado else 0.0

        st.write(f"**{nome}** — Meta: {fmt_brl(valor_meta)} • Acumulado: {fmt_brl(valor_acumulado)} • Até {data_meta or '—'}")
        st.progress(progresso)
        st.caption(f"Sugestão de aporte mensal: **{fmt_brl(aporte_sugerido)}**")
else:
    st.info("Nenhuma meta cadastrada. Cadastre em **Metas** na barra de páginas.")

# ---------------- Navegação / Próximos passos ----------------
st.divider()
st.subheader("🧭 Navegação")
st.markdown("""
Use o menu **Pages** (barra lateral) para:
- **📝 Lançamentos**: cadastrar Receitas/Despesas (commit automático)
- **📅 Contas**: listar e alterar status de A Pagar/A Receber
- **🎯 Metas**: progresso e aporte sugerido
- **👥 Usuários**: perfis e permissões
""")
