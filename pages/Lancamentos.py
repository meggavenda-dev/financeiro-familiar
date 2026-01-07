
# pages/1_Lancamentos.py
import streamlit as st
import pandas as pd
from datetime import date, datetime

from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import (
    novo_id,
    criar,
    atualizar,
    excluir,
    gerar_parcelas,
)

# ==================================================
# HELPERS DE SEGURANÇA (DEVEM VIR PRIMEIRO)
# ==================================================
def ensure_list(obj):
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        return [obj]
    return []

def parse_date(d):
    try:
        return datetime.fromisoformat(d).date()
    except Exception:
        return None

def competencia_from_date(d: date) -> str:
    return f"{d.year}-{d.month:02d}"

def competencia_label(comp: str) -> str:
    try:
        y, m = comp.split("-")
        meses = ["JAN","FEV","MAR","ABR","MAI","JUN","JUL","AGO","SET","OUT","NOV","DEZ"]
        return f"{meses[int(m)-1]}/{y[-2:]}"
    except Exception:
        return comp

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_status(item: dict) -> str:
    if item.get("status") == "paga":
        return "paga"
    d = parse_date(item.get("data"))
    hoje = date.today()
    if not d:
        return "planejada"
    if d < hoje:
        return "atrasada"
    if d == hoje:
        return "em_aberto"
    return "planejada"

def normalize_item(d: dict) -> dict:
    """
    Garante que todas as colunas usadas na UI existam.
    Evita KeyError com dados antigos.
    """
    d = d.copy()
    d.setdefault("numero", None)
    d.setdefault("referencia", "")
    d.setdefault("descricao", "")
    d.setdefault("observacoes", "")
    d.setdefault("status", "prevista")
    d.setdefault("excluido", False)
    d.setdefault("competencia", competencia_from_date(parse_date(d["data"])) if d.get("data") else None)
    return d

# ==================================================
# CONFIGURAÇÃO DA PÁGINA
# ==================================================
st.set_page_config(page_title="Lançamentos", page_icon="📝", layout="wide")
st.title("📝 Lançamentos")

# ==================================================
# CONTEXTO / PERMISSÕES
# ==================================================
ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

require_admin(ctx)
gh = ctx.gh

# ==================================================
# CARREGAMENTO DE DADOS (SEGURO)
# ==================================================
data = load_all((ctx.repo_full_name, ctx.branch_name))
despesas_map = data["data/despesas.json"]
despesas = ensure_list(despesas_map.get("content"))
sha_despesas = despesas_map.get("sha")

# Migração leve (em memória): garante competencia
for d in despesas:
    if not d.get("competencia"):
        dt = parse_date(d.get("data"))
        if dt:
            d["competencia"] = competencia_from_date(dt)

# ==================================================
# FILTRO POR COMPETÊNCIA
# ==================================================
competencias = sorted({d["competencia"] for d in despesas if d.get("competencia")}, reverse=True)
if not competencias:
    competencias = [competencia_from_date(date.today())]

comp_sel = st.selectbox(
    "📅 Competência",
    options=competencias,
    format_func=competencia_label
)

lista_mes = [
    normalize_item(d) for d in despesas
    if not d.get("excluido") and d.get("competencia") == comp_sel
]

# ==================================================
# RESUMO MENSAL
# ==================================================
def soma_status(ds, alvo):
    return sum(float(x.get("valor", 0.0)) for x in ds if calcular_status(x) == alvo)

total = sum(float(x.get("valor", 0.0)) for x in lista_mes)

c1, c2, c3, c4 = st.columns(4)
c1.metric("✅ Pago", fmt_brl(soma_status(lista_mes, "paga")))
c2.metric("⏳ Em aberto", fmt_brl(soma_status(lista_mes, "em_aberto")))
c3.metric("🔴 Atrasado", fmt_brl(soma_status(lista_mes, "atrasada")))
c4.metric("📝 Planejado", fmt_brl(soma_status(lista_mes, "planejada")))

st.progress((soma_status(lista_mes, "paga") / total) if total > 0 else 0)

st.divider()

# ==================================================
# LISTAGEM (À PROVA DE KEYERROR)
# ==================================================
st.subheader("📋 Lançamentos do mês")

if not lista_mes:
    st.info("Nenhum lançamento neste mês.")
    st.stop()

df = pd.DataFrame(lista_mes)

df["data_date"] = df["data"].apply(parse_date)
df["status_calc"] = df.apply(calcular_status, axis=1)
df["status_badge"] = df["status_calc"].map({
    "planejada": "📝 Planejada",
    "em_aberto": "⏳ Em aberto",
    "atrasada": "🔴 Atrasada",
    "paga": "✅ Paga",
})

cols_show = [
    "numero",
    "referencia",
    "descricao",
    "data_date",
    "valor",
    "status_badge",
    "observacoes",
]

# Criar colunas faltantes
for col in cols_show:
    if col not in df.columns:
        df[col] = None

df_show = (
    df[cols_show]
    .rename(columns={
        "numero": "Nº",
        "referencia": "Ref.",
        "descricao": "Descrição",
        "data_date": "Data",
        "valor": "Valor",
        "status_badge": "Status",
        "observacoes": "Obs.",
    })
    .sort_values("Data", ascending=False)
)

st.dataframe(df_show, use_container_width=True)

# ==================================================
# AÇÕES BÁSICAS
# ==================================================
st.markdown("### ✏️ Ações")
col1, col2 = st.columns(2)
edit_id = col1.text_input("Editar (ID técnico)")
del_id = col2.text_input("Excluir (ID técnico)")

if del_id and st.button("Excluir"):
    if excluir(despesas, del_id):
        gh.put_json("data/despesas.json", despesas, f"Remove {del_id}", sha=sha_despesas)
        st.cache_data.clear()
        st.rerun()
    else:
        st.error("ID não encontrado.")
