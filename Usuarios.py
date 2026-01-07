
# pages/4_Usuarios.py
import streamlit as st
from github_service import GitHubService

st.title("👥 Usuários")

gh = GitHubService(
    token=st.secrets["github_token"],
    repo_full_name=st.secrets["repo_full_name"]
)

usuarios, sha = gh.get_json("data/usuarios.json", [])

for u in usuarios:
    st.write(f"**{u['nome']}** — Perfil: {u['perfil']}")

