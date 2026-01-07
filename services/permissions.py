
# services/permissions.py
import streamlit as st


def require_admin(ctx):
    """Levanta erro de permissão (ou interrompe a página) para perfis não-admin."""
    if ctx.perfil != "admin":
        st.error("Acesso restrito ao administrador.")
        st.stop()

