
# services/utils.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Any, Optional


# ---------------------------------------------------------
# Formatação de moeda (BRL) robusta
# ---------------------------------------------------------
def fmt_brl(v: Any) -> str:
    """
    Formata valores em BRL com sinal correto e tolerância a erros.
    - Aceita int, float, str numérica; fallback para 0.0 quando inválido.
    - Negativos exibem prefixo '-'.
    - Usa separadores padrão brasileiro (ponto para milhar, vírgula para decimal).
    """
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
# Parser de datas defensivo
# ---------------------------------------------------------
def parse_date_safe(d: Any) -> Optional[date]:
    """
    Converte para `date` aceitando:
      - date
      - datetime (usa .date())
      - string no formato ISO (ou reconhecível pelo pandas)
    Retorna None se inválido.
    """
    if d is None:
        return None

    try:
        if isinstance(d, date) and not isinstance(d, datetime):
            return d
        if isinstance(d, datetime):
            return d.date()
        # pandas lida com variadas strings, inclusive ISO
        return pd.to_datetime(d, errors="coerce").date()
    except Exception:
        return None


def fmt_date_br(d: Any) -> str:
    """
    Formata qualquer data como 'dd/mm/aaaa' ou '—' quando inválida.
    """
    obj = parse_date_safe(d)
    return obj.strftime("%d/%m/%Y") if obj else "—"


def fmt_series_date_br(s: pd.Series) -> pd.Series:
    """
    Formata uma Series de datas para 'dd/mm/aaaa', com tolerância a valores inválidos.
    """
    return s.apply(fmt_date_br)


# ---------------------------------------------------------
# Chaves únicas para widgets Streamlit
# ---------------------------------------------------------
def key_for(*parts: Any) -> str:
    """
    Gera chaves únicas e estáveis para widgets do Streamlit.
    - Concatena partes não nulas com '-'.
    - Converte cada parte para string de forma segura.
    """
    return "-".join(str(p) for p in parts if p is not None)


# ---------------------------------------------------------
# Cache & rerun (qualquer página)
# ---------------------------------------------------------
def clear_cache_and_rerun() -> None:
    """
    Limpa o cache de dados (`st.cache_data`) e reroda a aplicação.
    Útil após gravações no GitHub (persistência de JSON).
    """
    st.cache_data.clear()
    st.rerun()


# ---------------------------------------------------------
# Data de referência por linha (helpers de DF)
# ---------------------------------------------------------
def data_ref_row(r: dict) -> Optional[date]:
    """
    Deriva a data de referência por linha de transação:
    - Prioriza `data_efetiva`; caso ausente, usa `data_prevista`.
    Retorna `date` ou `None`.
    """
    return parse_date_safe(r.get("data_efetiva") or r.get("data_prevista"))

