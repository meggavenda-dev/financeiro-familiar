
# services/permissions.py
import streamlit as st

def require_admin(cfg_or_ctx):
    """Aceita AppConfig (imutável) ou dict (session_state)."""
    perfil = None
    if isinstance(cfg_or_ctx, dict):
        perfil = cfg_or_ctx.get("perfil", "comum")
    else:
        # objeto AppConfig
        perfil = getattr(cfg_or_ctx, "perfil", "comum")

    if perfil != "admin":
        st.error("Acesso restrito ao administrador.")
        st.stop()
