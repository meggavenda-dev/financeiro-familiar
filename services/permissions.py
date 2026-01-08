
# services/permissions.py
import streamlit as st

def require_admin(ctx):
    perfil = ctx.get("perfil", "comum")
    if perfil != "admin":
        st.error("Acesso restrito ao administrador.")
        st.stop()
