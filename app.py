
# app.py
import streamlit as st
import pandas as pd
from datetime import date
from requests.exceptions import RequestException, Timeout
from github_service import GitHubService


st.set_page_config(
    page_title="Financeiro Familiar",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Financeiro Familiar")
st.caption("MVP — GitHub como banco de dados • Python + Streamlit")


# ---- Secrets / Config ----
DEFAULT_REPO = st.secrets.get("repo_full_name", "")
DEFAULT_TOKEN = st.secrets.get("github_token", "")
DEFAULT_BRANCH = st.secrets.get("branch_name", "main")

with st.sidebar:
    st.header("🔧 Configuração")
    repo_full_name = st.text_input("Repositório (owner/repo)", DEFAULT_REPO)
    github_token = st.text_input("GitHub Token (PAT)", DEFAULT_TOKEN, type="password")
    branch_name = st.text_input("Branch", DEFAULT_BRANCH)

    auto_connect = bool(repo_full_name and github_token)
    connect_click = st.button("Conectar ao GitHub")

should_connect = auto_connect or connect_click

if not should_connect:
    st.warning("Configure secrets ou informe os dados na barra lateral.")
    st.stop()


# ---- GitHub Service ----
try:
    gh = GitHubService(
        token=github_token,
        repo_full_name=repo_full_name,
        branch=branch_name
    )
except Exception as e:
    st.error(f"Erro ao inicializar GitHubService: {e}")
    st.stop()


# ---- Defaults ----
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


@st.cache_data(ttl=60)
def load_all():
    data = {}
    for path, default in DEFAULTS.items():
        obj, sha = gh.ensure_file(path, default)
        data[path] = {"content": obj, "sha": sha}
    return data


try:
    data_map = load_all()
except (RequestException, Timeout, Exception) as e:
    st.error("Erro ao carregar dados do GitHub")
    st.code(str(e))
    st.stop()


usuarios = data_map["data/usuarios.json"]["content"]
contas = data_map["data/contas.json"]["content"]
categorias = data_map["data/categorias.json"]["content"]
receitas = data_map["data/receitas.json"]["content"]
despesas = data_map["data/despesas.json"]["content"]


# ---- Sidebar Filtros ----
with st.sidebar:
    st.header("🧮 Filtros")

    contas_opts = {c["nome"]: c["id"] for c in contas}
    conta_nome = st.selectbox("Conta", list(contas_opts.keys()))
    conta_id = contas_opts[conta_nome]

    hoje = date.today()
    inicio = st.date_input("Início", date(hoje.year, hoje.month, 1))
    fim = st.date_input("Fim", hoje)


# ---- Helpers ----
def to_df(items, tipo):
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    df["data"] = pd.to_datetime(df["data"])
    df["tipo"] = tipo
    return df


def filtrar(df):
    if df.empty:
        return df
    return df[
        (df["conta_id"] == conta_id)
        & (df["data"].dt.date >= inicio)
        & (df["data"].dt.date <= fim)
    ]


df_r_all = to_df(receitas, "receita")
df_d_all = to_df(despesas, "despesa")

df_r = filtrar(df_r_all)
df_d = filtrar(df_d_all)

receita_total = df_r["valor"].sum() if not df_r.empty else 0
despesa_total = df_d["valor"].sum() if not df_d.empty else 0
saldo = receita_total - despesa_total

saldo_inicial = next(
    (c["saldo_inicial"] for c in contas if c["id"] == conta_id),
    0.0
)

# ---- KPIs ----
c1, c2, c3 = st.columns(3)
fmt = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

c1.metric("Receitas", fmt(receita_total))
c2.metric("Despesas", fmt(despesa_total))
c3.metric("Saldo", fmt(saldo))

st.divider()

st.subheader("📊 Receitas vs Despesas")

chart = pd.DataFrame({
    "Receitas": [receita_total],
    "Despesas": [despesa_total]
})

st.bar_chart(chart)

st.success("✅ App carregado com sucesso.")
