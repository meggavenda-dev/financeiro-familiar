
# services/layout.py
import streamlit as st


def is_mobile() -> bool:
    """
    Modo mobile controlado explicitamente pelo usuário.
    Evita heurísticas frágeis.
    """
    return st.session_state.get("modo_mobile", False)


def responsive_columns(desktop: int, mobile: int = 1):
    """
    Retorna colunas responsivas.
    """
    cols = mobile if is_mobile() else desktop
    return st.columns(cols)


def responsive_value(desktop, mobile):
    """
    Retorna valores diferentes conforme o modo.
    """
    return mobile if is_mobile() else desktop

