
# pages/4_Usuarios.py
import streamlit as st
from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin

st.set_page_config("Usuários", "👥", layout="wide")
st.title("👥 Usuários")

ctx = get_context()
require_admin(ctx)
gh = ctx["gh"]

data = load_all((st.secrets["repo_full_name"], st.secrets.get("branch_name", "main")))

usuarios = data["data/usuarios.json"]["content"]

for u in usuarios:
    st.write(f"**{u['nome']}** — Perfil: `{u['perfil']}`")
