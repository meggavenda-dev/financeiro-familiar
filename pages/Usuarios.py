
# pages/4_Usuarios.py
import streamlit as st
from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin

st.set_page_config(page_title="Usuários", page_icon="👥", layout="wide")
st.title("👥 Usuários")

ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)
gh = ctx.gh

data = load_all((ctx.repo_full_name, ctx.branch_name))
usuarios = data["data/usuarios.json"]["content"]

if not usuarios:
    st.info("Nenhum usuário cadastrado.")
else:
    for u in usuarios:
        st.write(f"**{u['nome']}** — Perfil: `{u['perfil']}`")
