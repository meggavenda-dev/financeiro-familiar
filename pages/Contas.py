
# pages/2_Contas.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import normalizar_tx, atualizar
from services.status import derivar_status
from services.utils import fmt_brl, parse_date_safe, clear_cache_and_rerun, fmt_date_br

# --------------------------------------------------
# Página
# --------------------------------------------------
st.set_page_config(page_title="Contas a Pagar / Receber", page_icon="📅", layout="wide")
st.title("📅 Contas a Pagar / Receber")

# --------------------------------------------------
# Contexto
# --------------------------------------------------
init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal antes de usar esta página.")
    st.stop()

require_admin(ctx)
gh = ctx.get("gh")

# --------------------------------------------------
# Dados (unificados)
# --------------------------------------------------
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))
trans_map = data["data/transacoes.json"]
transacoes = [
    t for t in (normalizar_tx(x) for x in trans_map["content"])
    if t is not None
]
sha_trans = trans_map["sha"]

def salvar(transacoes, mensagem: str):
    gh.put_json("data/transacoes.json", transacoes, mensagem, sha=sha_trans)
    clear_cache_and_rerun()

def badge_calc(tx):
    st_calc = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))
    d = parse_date_safe(tx.get("data_prevista"))
    hoje = date.today()
    if st_calc == "paga":
        return "✅ Paga"
    if d and d < hoje:
        return "🔴 Vencida"
    if d and d <= (hoje + timedelta(days=7)):
        return "🟡 Próxima"
    return "🟢 Em aberto"

tab_pagar, tab_receber = st.tabs(["💸 A Pagar", "📥 A Receber"])

# -------------------- A PAGAR (despesa) --------------------
with tab_pagar:
    st.subheader("💸 Contas a Pagar")
    mostrar_pagas_pagar = st.checkbox("Mostrar itens pagos", value=False, key="mostrar_pagas_pagar")

    pagar_items = []
    for x in transacoes:
        if x.get("tipo") != "despesa":
            continue
        if x.get("excluido"):
            continue
        stx = derivar_status(x.get("data_prevista"), x.get("data_efetiva"))
        if not mostrar_pagas_pagar and stx == "paga":
            continue
        pagar_items.append(x)

    if not pagar_items:
        st.info("Nenhuma conta a pagar para o filtro selecionado.")
    else:
        for c in pagar_items:
            prev = parse_date_safe(c.get("data_prevista"))
            status_atual = derivar_status(c.get("data_prevista"), c.get("data_efetiva"))

            col1, col2, col3, col4, col5 = st.columns([4, 2, 3, 2, 3])
            col1.write(f"**{c.get('descricao', '—')}**")
            col2.write(fmt_brl(float(c.get("valor", 0.0))))
            col3.write(f"Previsto: {fmt_date_br(prev)}")
            col4.write(badge_calc(c))

            pagar_btn = col5.button("Marcar como paga", key=f"pagar-{c['id']}", disabled=(status_atual == "paga"))
            nova_prev = col5.date_input("Reagendar", value=prev or date.today(), key=f"prev-{c['id']}")
            salvar_prev = col5.button("Salvar data", key=f"save-prev-{c['id']}")

            if pagar_btn:
                c["data_efetiva"] = date.today().isoformat()
                atualizar(transacoes, c)
                salvar(transacoes, f"Baixa pagar: {c.get('descricao')}")

            if salvar_prev and nova_prev and (not c.get("data_efetiva")):
                c["data_prevista"] = nova_prev.isoformat()
                atualizar(transacoes, c)
                salvar(transacoes, f"Reagendamento pagar: {c.get('descricao')} -> {nova_prev.isoformat()}")

# -------------------- A RECEBER (receita) --------------------
with tab_receber:
    st.subheader("📥 Contas a Receber")
    mostrar_pagas_receber = st.checkbox("Mostrar itens recebidos", value=False, key="mostrar_pagas_receber")

    receber_items = []
    for x in transacoes:
        if x.get("tipo") != "receita":
            continue
        if x.get("excluido"):
            continue
        stx = derivar_status(x.get("data_prevista"), x.get("data_efetiva"))
        if not mostrar_pagas_receber and stx == "paga":
            continue
        receber_items.append(x)

    if not receber_items:
        st.info("Nenhuma conta a receber para o filtro selecionado.")
    else:
        for c in receber_items:
            prev = parse_date_safe(c.get("data_prevista"))
            status_atual = derivar_status(c.get("data_prevista"), c.get("data_efetiva"))

            col1, col2, col3, col4, col5 = st.columns([4, 2, 3, 2, 3])
            col1.write(f"**{c.get('descricao', '—')}**")
            col2.write(fmt_brl(float(c.get("valor", 0.0))))
            col3.write(f"Previsto: {fmt_date_br(prev)}")
            col4.write(badge_calc(c))

            receber_btn = col5.button("Marcar como recebida", key=f"receber-{c['id']}", disabled=(status_atual == "paga"))
            nova_prev = col5.date_input("Reagendar", value=prev or date.today(), key=f"prev-rec-{c['id']}")
            salvar_prev = col5.button("Salvar data", key=f"save-prev-rec-{c['id']}")

            if receber_btn:
                c["data_efetiva"] = date.today().isoformat()
                atualizar(transacoes, c)
                salvar(transacoes, f"Baixa receber: {c.get('descricao')}")

            if salvar_prev and nova_prev and (not c.get("data_efetiva")):
                c["data_prevista"] = nova_prev.isoformat()
                atualizar(transacoes, c)
                salvar(transacoes, f"Reagendamento receber: {c.get('descricao')} -> {nova_prev.isoformat()}")

# -------------------- Resumo futuro --------------------
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
c2.metric("🔴 Vencidas (pagar)", fmt_brl(p_vencido), help="Vencidas até hoje")
c3.metric("🟡 Próx. 7 dias (pagar)", fmt_brl(p_prox7))

c4, c5, c6 = st.columns(3)
c4.metric("📥 A Receber (em aberto)", fmt_brl(r_aberto))
c5.metric("🔴 Vencidas (receber)", fmt_brl(r_vencido), help="Vencidas até hoje")
c6.metric("🟡 Próx. 7 dias (receber)", fmt_brl(r_prox7))

st.success("✅ Módulo de Contas mostra apenas itens em aberto por padrão. Use os checkboxes para auditoria de pagos/recebidos.")
