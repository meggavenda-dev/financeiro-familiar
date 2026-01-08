
# services/utils.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Any

# ---------------------------------------------------------
# CHANGE: formatação BRL robusta (negativos e tolerância)
# ---------------------------------------------------------
def fmt_brl(v: Any) -> str:
    """Formata valores em BRL com sinal correto e tolerância a erro."""
    try:
        val = float(v)
    except (ValueError, TypeError):
        val = 0.0

    abs_val = abs(val)
    s = f"{abs_val:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    prefix = "-" if val < 0 else ""
    return f"{prefix}R$ {s}"


# ---------------------------------------------------------
# CHANGE: parser de datas defensivo
# ---------------------------------------------------------
def parse_date_safe(d):
    """Converte para date aceitando date, datetime e ISO string."""
    if d is None:
        return None
    try:
        if isinstance(d, date) and not isinstance(d, datetime):
            return d
        if isinstance(d, datetime):
            return d.date()
        return pd.to_datetime(d, errors="coerce").date()
    except Exception:
        return None


def fmt_date_br(d) -> str:
    """Formata qualquer data como dd/mm/aaaa ou '—'."""
    obj = parse_date_safe(d)
    return obj.strftime("%d/%m/%Y") if obj else "—"


def fmt_series_date_br(s: pd.Series) -> pd.Series:
    """Formata uma Series de datas para dd/mm/aaaa."""
    return s.apply(fmt_date_br)


# ---------------------------------------------------------
# CHANGE: helper de chaves únicas para widgets Streamlit
# ---------------------------------------------------------
def key_for(*parts) -> str:
    """Gera chaves únicas e estáveis para widgets."""
    return "-".join(str(p) for p in parts if p is not None)


# ---------------------------------------------------------
# Cache & rerun
# ---------------------------------------------------------
def clear_cache_and_rerun():
    """Limpa cache de dados e reroda a app."""
    st.cache_data.clear()
    st.rerun()


# ---------------------------------------------------------
# Helper de data de referência (linha DataFrame)
# ---------------------------------------------------------
def data_ref_row(r) -> date | None:
    """
    Deriva data de referência por linha:
    - data efetiva se existir
    - senão data prevista
    """
    return parse_date_safe(r.get("data_efetiva") or r.get("data_prevista"))
