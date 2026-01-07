
# services/permissions.py
import streamlit as st

def require_admin(ctx):
    if ctx.perfil != "admin":
        st.error("Acesso restrito ao administrador.")
        st.stop()
