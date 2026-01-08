
# services/utils.py
import streamlit as st
import pandas as pd
from datetime import date, datetime

def fmt_brl(v) -> str:
    """Formata valores em BRL de forma tolerante."""
    try:
        val = float(v)
    except (ValueError, TypeError):
        val = 0.0
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date_safe(d):
    """Converte para date com tolerância a erros (aceita str, date, datetime)."""
    if d is None:
        return None
    try:
        if isinstance(d, date):
            return d
        if isinstance(d, datetime):
            return d.date()
        return pd.to_datetime(d, dayfirst=False, errors="coerce").date()
    except Exception:
        return None

def fmt_date_br(d) -> str:
    """Formata qualquer data para dd/mm/aaaa; retorna '—' se ausente/ inválida."""
    obj = parse_date_safe(d)
    return obj.strftime("%d/%m/%Y") if obj else "—"

def fmt_series_date_br(s: pd.Series) -> pd.Series:
    """Formata uma Series de datas para dd/mm/aaaa (strings)."""
    return s.apply(lambda x: fmt_date_br(x))

def clear_cache_and_rerun():
    """Limpa cache de dados e reroda a app/página."""
    st.cache_data.clear()
    st.rerun()

def data_ref_row(r) -> pd.Timestamp.date:
    """
    Helper: derivar data de referência por linha:
    - Prioriza data efetiva, se existir
    - Senão, usa data prevista
    """
    return pd.to_datetime(r.get("data_efetiva") or r.get("data_prevista"), errors="coerce").date()
