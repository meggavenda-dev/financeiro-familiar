
# pages/2_Contas.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.app_context import get_config, get_context
from services.data_loader import load_transactions
from services.permissions import require_admin
from services.finance_core import normalizar_tx
from services.status import derivar_status
from services.utils import fmt_brl, parse_date_safe, save_json_and_refresh

st.set_page_config(page_title="Contas a Pagar / Receber", page_icon="📅", layout="wide")
st.title("📅 Contas a Pagar / Receber")

cfg = get_config()
if not cfg.connected:
    st.warning("Conecte ao GitHub na página principal antes de usar esta página.")
    st.stop()
require_admin(cfg)

ctx = get_context()
gh = ctx.get("gh")

trans_map = load_transactions((cfg.repo_full_name, cfg.branch_name))
transacoes = [t for t in (normalizar_tx(x) for x in trans_map["content"]) if t is not None]
sha_trans = trans_map["sha"]

df = pd.DataFrame(transacoes)
if df.empty:
    st.info("Nenhuma transação encontrada.")
    st.stop()

df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
df["prev"] = pd.to_datetime(df["data_prevista"], errors="coerce").dt.date
df["status"] = df.apply(lambda r: derivar_status(r.get("data_prevista"), r.get("data_efetiva")), axis=1)
df = df[~df["excluido"].astype(bool)]

def badge_calc_row(row):
    st_calc = row["status"]
    d = row["prev"]
    hoje = date.today()
    if st_calc == "paga":
        return "✅ Paga"
    if d and d < hoje:
        return "🔴 Vencida"
    if d and d <= (hoje + timedelta(days=7)):
        return "🟡 Próxima"
    return "🟢 Em aberto"

df["badge"] = df.apply(badge_calc_row, axis=1)

tab_pagar, tab_receber = st.tabs(["💸 A Pagar", "📥 A Receber"])

with tab_pagar:
    st.subheader("💸 A Pagar")
    pagar_view = df[df["tipo"] == "despesa"].copy().sort_values("prev")
    st.dataframe(pagar_view[["descricao","valor","prev","badge","id"]], use_container_width=True)
    sel_ids = st.multiselect("IDs para marcar como pagos", options=list(pagar_view["id"]))
    if st.button("Marcar selecionados como pagos"):
        changed = False
        for tx in transacoes:
            if tx.get("id") in sel_ids:
                tx["data_efetiva"] = date.today().isoformat()
                changed = True
        if changed:
            save_json_and_refresh(gh, "data/transacoes.json", transacoes, f"Baixa múltipla pagar ({len(sel_ids)})", sha_trans)

with tab_receber:
    st.subheader("📥 A Receber")
    receber_view = df[df["tipo"] == "receita"].copy().sort_values("prev")
    st.dataframe(receber_view[["descricao","valor","prev","badge","id"]], use_container_width=True)
    sel_ids = st.multiselect("IDs para marcar como recebidos", options=list(receber_view["id"]), key="rec_sel")
    if st.button("Marcar selecionados como recebidos"):
        changed = False
        for tx in transacoes:
            if tx.get("id") in sel_ids:
                tx["data_efetiva"] = date.today().isoformat()
                changed = True
        if changed:
            save_json_and_refresh(gh, "data/transacoes.json", transacoes, f"Baixa múltipla receber ({len(sel_ids)})", sha_trans)

st.divider()
st.subheader("📊 Planejamento & Fluxo Futuro (em aberto)")
hoje = date.today()

def resumo_fluxo(lista, tipo):
    total_aberto = 0.0
    total_vencido = 0.0
    total_prox7 = 0.0
    for c in lista:
        if c.get("tipo") != tipo:
            continue
        stc = derivar_status(c.get("data_prevista"), c.get("data_efetiva"))
        if stc == "paga":
            continue
        valor = float(c.get("valor", 0.0))
        d = parse_date_safe(c.get("data_prevista"))
        if not d:
            continue
        if d < hoje:
            total_vencido += valor
        elif d <= (hoje + timedelta(days=7)):
            total_prox7 += valor
        total_aberto += valor
    return total_aberto, total_vencido, total_prox7

p_aberto, p_vencido, p_prox7 = resumo_fluxo(transacoes, "despesa")
r_aberto, r_vencido, r_prox7 = resumo_fluxo(transacoes, "receita")

c1, c2, c3 = st.columns(3)
c1.metric("💸 A Pagar (em aberto)", fmt_brl(p_aberto))
c2.metric("🔴 Vencidas (pagar)", fmt_brl(p_vencido))
c3.metric("🟡 Próx. 7 dias (pagar)", fmt_brl(p_prox7))

c4, c5, c6 = st.columns(3)
c4.metric("📥 A Receber (em aberto)", fmt_brl(r_aberto))
c5.metric("🔴 Vencidas (receber)", fmt_brl(r_vencido))
c6.metric("🟡 Próx. 7 dias (receber)", fmt_brl(r_prox7))
