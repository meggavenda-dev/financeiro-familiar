
# pages/1_Lancamentos.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from github_service import GitHubService

st.set_page_config(page_title="Lançamentos", page_icon="📝", layout="wide")
st.title("📝 Lançamentos Financeiros")

# ---- Secrets / GitHub ----
repo = st.secrets["repo_full_name"]
token = st.secrets["github_token"]
branch = st.secrets.get("branch_name", "main")

gh = GitHubService(token=token, repo_full_name=repo, branch=branch)

# ---- Carrega dados base ----
categorias, _ = gh.get_json("data/categorias.json", {})
contas, _ = gh.get_json("data/contas.json", [])
receitas, sha_r = gh.get_json("data/receitas.json", [])
despesas, sha_d = gh.get_json("data/despesas.json", [])

# ---- Formulário ----
with st.form("form_lancamento", clear_on_submit=True):
    tipo = st.radio("Tipo", ["Receita", "Despesa"], horizontal=True)
    data_lanc = st.date_input("Data", date.today())
    valor = st.number_input("Valor", min_value=0.01, step=0.01)

    cats = categorias["receitas"] if tipo == "Receita" else categorias["despesas"]
    cat_map = {c["nome"]: c["id"] for c in cats}
    categoria_nome = st.selectbox("Categoria", list(cat_map.keys()))

    conta_map = {c["nome"]: c["id"] for c in contas}
    conta_nome = st.selectbox("Conta", list(conta_map.keys()))

    obs = st.text_input("Observação")

    salvar = st.form_submit_button("💾 Salvar")

# ---- Salvamento ----
if salvar:
    novo = {
        "id": f"{'r' if tipo == 'Receita' else 'd'}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "data": data_lanc.isoformat(),
        "valor": float(valor),
        "categoria_id": cat_map[categoria_nome],
        "conta_id": conta_map[conta_nome],
        "pessoa_id": "u1",
        "observacoes": obs
    }

    if tipo == "Receita":
        receitas.append(novo)
        gh.put_json("data/receitas.json", receitas, f"Add receita: {valor}", sha=sha_r)
    else:
        despesas.append(novo)
        gh.put_json("data/despesas.json", despesas, f"Add despesa: {valor}", sha=sha_d)

    st.success("✅ Lançamento salvo com sucesso!")

# ---- Últimos lançamentos ----
st.divider()
st.subheader("📄 Lançamentos recentes")

df = pd.DataFrame(receitas + despesas)
if not df.empty:
    df["data"] = pd.to_datetime(df["data"])
    st.dataframe(df.sort_values("data", ascending=False).head(20))
else:
    st.info("Nenhum lançamento registrado ainda.")
