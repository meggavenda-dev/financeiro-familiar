
# pages/2_Contas.py
import streamlit as st
from datetime import date
from github_service import GitHubService

st.title("📅 Contas a Pagar / Receber")

gh = GitHubService(
    token=st.secrets["github_token"],
    repo_full_name=st.secrets["repo_full_name"]
)

contas_pagar, sha_p = gh.get_json("data/contas_pagar.json", [])
contas_receber, sha_r = gh.get_json("data/contas_receber.json", [])

aba = st.tabs(["A Pagar", "A Receber"])

for conta, tab, sha, path in [
    (contas_pagar, aba[0], sha_p, "data/contas_pagar.json"),
    (contas_receber, aba[1], sha_r, "data/contas_receber.json"),
]:
    with tab:
        for c in conta:
            col1, col2, col3 = st.columns([4, 2, 2])
            col1.write(f"**{c['descricao']}**")
            col2.write(f"R$ {c['valor']:.2f}")
            novo = col3.selectbox(
                "Status",
                ["em_aberto", "paga", "atrasada"],
                index=["em_aberto", "paga", "atrasada"].index(c["status"]),
                key=c["id"]
            )
            if novo != c["status"]:
                c["status"] = novo
                gh.put_json(path, conta, f"Update status: {c['descricao']}", sha=sha)
                st.rerun()
