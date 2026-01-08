
# services/utils.py
import streamlit as st
import pandas as pd
from datetime import date

def fmt_brl(v) -> str:
    try:
        val = float(v)
    except (ValueError, TypeError):
        val = 0.0
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date_safe(d):
    try:
        return pd.to_datetime(d).date()
    except Exception:
        return None

def clear_cache_and_rerun():
    st.cache_data.clear()
    st.rerun()
