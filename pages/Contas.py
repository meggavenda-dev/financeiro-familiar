
# pages/2_Contas.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import normalizar_tx, atualizar
from services.status import derivar_status, status_badge

# --------------------------------------------------
# Página
# --------------------------------------------------
st.set_page_config(page_title="Contas a Pagar / Receber", page_icon="📅", layout="wide")
st.title("📅 Contas a Pagar / Receber")

# --------------------------------------------------
# Contexto
# --------------------------------------------------
ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal antes de usar esta página.")
    st.stop()

require_admin(ctx)
gh = ctx.gh

# --------------------------------------------------
# Dados (unificados)
# --------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))
trans_map = data["data/transacoes.json"]
transacoes = [normalizar_tx(x) for x in trans_map["content"]]
sha_trans = trans_map["sha"]

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date_safe(d):
    try:
        return pd.to_datetime(d).date()
    except Exception:
        return None

def salvar(transacoes, mensagem: str):
    new_sha = gh.put_json("data/transacoes.json", transacoes, mensagem, sha=sha_trans)
    st.cache_data.clear()
    st.rerun()

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
    pagar_items = [x for x in transacoes if x.get("tipo") == "despesa" and not x.get("excluido")]
    if not pagar_items:
        st.info("Nenhuma conta a pagar cadastrada.")
    else:
        for c in pagar_items:
            prev = parse_date_safe(c.get("data_prevista"))
            col1, col2, col3, col4, col5 = st.columns([4,2,3,2,2])
            col1.write(f"**{c.get('descricao', '—')}**")
            col2.write(fmt_brl(float(c.get("valor", 0.0))))
            col3.write(f"Previsto: {prev.strftime('%d/%m/%Y') if prev else '—'}")
            col4.write(badge_calc(c))

            status_atual = derivar_status(c.get("data_prevista"), c.get("data_efetiva"))
            novo_status = col5.selectbox(
                "Status",
                ["planejada","vencendo","vencida","paga"],
                index=["planejada","vencendo","vencida","paga"].index(status_atual),
                key=f"pagar-{c['id']}"
            )

            # aplicar mudança (paga -> set data_efetiva; outros -> limpar)
            if novo_status != status_atual:
                if novo_status == "paga":
                    c["data_efetiva"] = date.today().isoformat()
                else:
                    c["data_efetiva"] = None
                atualizar(transacoes, c)
                salvar(transacoes, f"Update pagar: {c.get('descricao')} -> {novo_status}")

# -------------------- A RECEBER (receita) --------------------
with tab_receber:
    st.subheader("📥 Contas a Receber")
    receber_items = [x for x in transacoes if x.get("tipo") == "receita" and not x.get("excluido")]
    if not receber_items:
        st.info("Nenhuma conta a receber cadastrada.")
    else:
        for c in receber_items:
            prev = parse_date_safe(c.get("data_prevista"))
            col1, col2, col3, col4, col5 = st.columns([4,2,3,2,2])
            col1.write(f"**{c.get('descricao', '—')}**")
            col2.write(fmt_brl(float(c.get("valor", 0.0))))
            col3.write(f"Previsto: {prev.strftime('%d/%m/%Y') if prev else '—'}")
            col4.write(badge_calc(c))

            status_atual = derivar_status(c.get("data_prevista"), c.get("data_efetiva"))
            novo_status = col5.selectbox(
                "Status",
                ["planejada","vencendo","vencida","paga"],
                index=["planejada","vencendo","vencida","paga"].index(status_atual),
                key=f"receber-{c['id']}"
            )

            if novo_status != status_atual:
                if novo_status == "paga":
                    c["data_efetiva"] = date.today().isoformat()
                else:
                    c["data_efetiva"] = None
                atualizar(transacoes, c)
                salvar(transacoes, f"Update receber: {c.get('descricao')} -> {novo_status}")

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
c2.metric("🔴 Vencidas (pagar)", fmt_brl(p_vencido))
c3.metric("🟡 Próx. 7 dias (pagar)", fmt_brl(p_prox7))

c4, c5, c6 = st.columns(3)
c4.metric("📥 A Receber (em aberto)", fmt_brl(r_aberto))
c5.metric("🔴 Vencidas (receber)", fmt_brl(r_vencido))
c6.metric("🟡 Próx. 7 dias (receber)", fmt_brl(r_prox7))

st.success("✅ Módulo de Contas integrado ao planejamento financeiro.")
