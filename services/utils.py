
# services/utils.py
import streamlit as st
import pandas as pd

def fmt_brl(v) -> str:
    """Formata valores em BRL de forma tolerante."""
    try:
        val = float(v)
    except (ValueError, TypeError):
        val = 0.0
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date_safe(d):
    """Converte para date com tolerância a erros."""
    try:
        return pd.to_datetime(d).date()
    except Exception:
        return None

def clear_cache_and_rerun():
    """Limpa cache de dados e reroda a app/página."""
    st.cache_data.clear()
    st.rerun()

def save_json_and_refresh(gh, path, obj, msg, sha):
    """Helper para salvar JSON (com SHA) e atualizar UI."""
    new_sha = gh.put_json(path, obj, msg, sha=sha)
    st.cache_data.clear()
    st.rerun()
    return new_sha
