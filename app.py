
# app.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from github_service import GitHubService

# --------------- Config inicial ---------------

st.set_page_config(page_title="Financeiro Familiar", page_icon="💰", layout="wide")

st.title("💰 Financeiro Familiar")
st.caption("MVP — GitHub como banco de dados • Python + Streamlit")

# Carrega secrets (não faça commit de .streamlit/secrets.toml)
DEFAULT_REPO = st.secrets.get("repo_full_name", "")
DEFAULT_TOKEN = st.secrets.get("github_token", "")
DEFAULT_BRANCH = st.secrets.get("branch_name", "main")

with st.sidebar:
    st.header("🔧 Configuração")
    repo_full_name = st.text_input("Repositório (usuario/repo)", value=DEFAULT_REPO, placeholder="usuario/repo")
    github_token = st.text_input("GitHub Token (PAT)", value=DEFAULT_TOKEN, type="password")
    branch_name = st.text_input("Branch", value=DEFAULT_BRANCH)
    st.info("O token precisa de escopo 'repo'. Configure em Settings → Developer settings → Personal access tokens.")
    ready = st.button("Conectar ao GitHub")

if not ready and (not (repo_full_name and github_token)):
    st.warning("Informe repositório, token e branch na barra lateral e clique em **Conectar ao GitHub**.")
    st.stop()

# --------------- Serviço GitHub ---------------

gh = GitHubService(token=github_token, repo_full_name=repo_full_name, branch=branch_name)

# --------------- Default data ---------------

DEFAULTS = {
    "data/usuarios.json": [
        { "id": "u1", "nome": "Administrador", "perfil": "admin" }
    ],
    "data/contas.json": [
        { "id": "c1", "nome": "Conta Corrente", "tipo": "banco", "moeda": "BRL", "saldo_inicial": 0.0 }
    ],
    "data/categorias.json": {
        "receitas": [
            { "id": "cr1", "nome": "Salário" },
            { "id": "cr2", "nome": "Freelancer" },
            { "id": "cr3", "nome": "Aluguel Recebido" }
        ],
        "despesas": [
            { "id": "cd1", "nome": "Moradia" },
            { "id": "cd2", "nome": "Alimentação" },
            { "id": "cd3", "nome": "Transporte" },
            { "id": "cd4", "nome": "Educação" },
            { "id": "cd5", "nome": "Lazer" }
        ]
    },
    "data/receitas.json": [],
    "data/despesas.json": [],
    "data/contas_pagar.json": [],
    "data/contas_receber.json": [],
    "data/metas.json": []
}

# --------------- Leitura de dados ---------------

@st.cache_data(ttl=60, show_spinner=False)
def load_all():
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}
    return data

data_map = load_all()

usuarios = data_map["data/usuarios.json"]["content"]
contas = data_map["data/contas.json"]["content"]
categorias = data_map["data/categorias.json"]["content"]
receitas = data_map["data/receitas.json"]["content"]
despesas = data_map["data/despesas.json"]["content"]
contas_pagar = data_map["data/contas_pagar.json"]["content"]
contas_receber = data_map["data/contas_receber.json"]["content"]
metas = data_map["data/metas.json"]["content"]

# --------------- Filtros ---------------

with st.sidebar:
    st.header("🧮 Filtros")
    contas_opts = {c["nome"]: c["id"] for c in contas}
    conta_sel_nome = st.selectbox("Conta", options=list(contas_opts.keys()), index=0)
    conta_sel = contas_opts[conta_sel_nome]

    hoje = date.today()
    inicio = st.date_input("Início", value=date(hoje.year, hoje.month, 1))
    fim = st.date_input("Fim", value=hoje)

# --------------- Helpers ---------------

def to_df_movs(items, tipo: str):
    """Converte receitas/despesas em DataFrame padronizado."""
    if not items:
        return pd.DataFrame(columns=["id", "data", "valor", "categoria_id", "conta_id", "pessoa_id", "tipo"])
    df = pd.DataFrame(items)
    # datas
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

# --------------- Preparação dos dados ---------------

df_r_all = to_df_movs(receitas, "receita")
df_d_all = to_df_movs(despesas, "despesa")

df_r = filtrar_por_periodo_conta(df_r_all, conta_sel, inicio, fim)
df_d = filtrar_por_periodo_conta(df_d_all, conta_sel, inicio, fim)

valor_receitas = float(df_r["valor"].sum()) if not df_r.empty else 0.0
valor_despesas = float(df_d["valor"].sum()) if not df_d.empty else 0.0
saldo_periodo = valor_receitas - valor_despesas

saldo_inicial = 0.0
for c in contas:
    if c["id"] == conta_sel:
        saldo_inicial = float(c.get("saldo_inicial", 0.0))
        break

# Saldo projetado = saldo inicial + todas as receitas/despesas até fim do período (conta selecionada)
df_r_proj = filtrar_por_periodo_conta(df_r_all, conta_sel, date.min, fim)
df_d_proj = filtrar_por_periodo_conta(df_d_all, conta_sel, date.min, fim)
saldo_projetado = saldo_inicial + float(df_r_proj["valor"].sum()) - float(df_d_proj["valor"].sum())

# --------------- KPIs ---------------

col1, col2, col3, col4 = st.columns(4)
col1.metric("Receitas (período)", f"R$ {valor_receitas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col2.metric("Despesas (período)", f"R$ {valor_despesas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("Saldo (período)", f"R$ {saldo_periodo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col4.metric("Saldo projetado", f"R$ {saldo_projetado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.divider()

# --------------- Gráfico: saldo acumulado diário ---------------

st.subheader("📈 Saldo acumulado diário (período)")

def saldo_diario(df_r: pd.DataFrame, df_d: pd.DataFrame, dt_inicio: date, dt_fim: date, saldo_base: float):
    # junta movimentos em uma única série diária
    df_r2 = df_r.copy()
    df_d2 = df_d.copy()
    df_r2["valor_signed"] = df_r2["valor"]  # + para receitas
    df_d2["valor_signed"] = -df_d2["valor"]  # - para despesas
    df = pd.concat([df_r2[["data", "valor_signed"]], df_d2[["data", "valor_signed"]]], ignore_index=True)
    if df.empty:
        idx = pd.date_range(dt_inicio, dt_fim)
        return pd.DataFrame({"data": idx, "saldo": saldo_base})
    df = df.groupby(df["data"].dt.date)["valor_signed"].sum().sort_index().reset_index()
    # reindexa todos os dias
    idx = pd.date_range(dt_inicio, dt_fim)
    s = df.set_index(pd.to_datetime(df["data"]))["valor_signed"].reindex(idx, fill_value=0.0).cumsum() + saldo_base
    out = pd.DataFrame({"data": idx, "saldo": s.values})
    return out

df_saldo = saldo_diario(df_r_proj, df_d_proj, inicio, fim, saldo_inicial)
st.line_chart(df_saldo.set_index("data"))

# --------------- Gráfico: receitas vs despesas por mês ---------------

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
m = pd.merge(m_r, m_d, on="ano_mes", how="outer").fillna(0.0)
m_sorted = m.sort_values("ano_mes")
st.bar_chart(m_sorted.set_index("ano_mes"))

# --------------- Gráfico: despesas por categoria (pizza) ---------------

st.subheader("🥧 Despesas por categoria (período)")
if df_d.empty:
    st.info("Sem despesas no período selecionado.")
else:
    df_d["categoria_nome"] = df_d["categoria_id"].apply(lambda cid: nome_categoria(cid, "despesa"))
    gcat = df_d.groupby("categoria_nome")["valor"].sum().reset_index()
    # Streamlit não tem nativo 'pie', usamos tabela e barras horizontais como MVP
    st.dataframe(gcat.rename(columns={"categoria_nome": "Categoria", "valor": "Total (R$)"}))
    st.bar_chart(gcat.set_index("categoria_nome"))

st.divider()

# --------------- Próximos passos (UI placeholders) ---------------

st.subheader("🧩 Próximos passos do app")
st.markdown("""
- **Lançamentos**: criar páginas para cadastrar Receitas/Despesas e salvar no GitHub com commit automático.
- **Contas a Pagar/Receber**: listar, alterar status (em aberto/paga/atrasada) e refletir no fluxo.
- **Metas**: exibir progresso (%), sugerir aporte mensal, e check de aderência.
- **Perfis de usuários**: permissões por perfil (admin vs comum).
""")
