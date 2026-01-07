
# pages/2_Contas.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin

# ------------------------------------------------------------------
# Configuração da página
# ------------------------------------------------------------------
st.set_page_config(page_title="Contas a Pagar / Receber", page_icon="📅", layout="wide")
st.title("📅 Contas a Pagar / Receber")

# ------------------------------------------------------------------
# Contexto e permissões
# ------------------------------------------------------------------
ctx = get_context()

if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal antes de usar esta página.")
    st.stop()

require_admin(ctx)
gh = ctx.gh

# ------------------------------------------------------------------
# Carregamento de dados (com cache central)
# ------------------------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))

pagar_map = data["data/contas_pagar.json"]
receber_map = data["data/contas_receber.json"]

contas_pagar = pagar_map["content"]
contas_receber = receber_map["content"]

sha_map = {
    "data/contas_pagar.json": pagar_map["sha"],
    "data/contas_receber.json": receber_map["sha"],
}

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
STATUS_OPTS = ["em_aberto", "paga", "atrasada"]

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date(d):
    try:
        return pd.to_datetime(d).date()
    except Exception:
        return None

def salvar(path: str, lista: list, mensagem: str):
    """Salva no GitHub usando SHA correto e retorna novo SHA."""
    new_sha = gh.put_json(path, lista, mensagem, sha=sha_map[path])
    sha_map[path] = new_sha
    st.cache_data.clear()
    st.rerun()

def badge_status(status: str, data_ref: date):
    hoje = date.today()
    if status == "paga":
        return "✅ Paga"
    if data_ref and data_ref < hoje:
        return "🔴 Atrasada"
    if data_ref and data_ref <= (hoje + timedelta(days=7)):
        return "🟡 Próxima"
    return "🟢 Em aberto"

# ------------------------------------------------------------------
# Aba de navegação
# ------------------------------------------------------------------
tab_pagar, tab_receber = st.tabs(["💸 A Pagar", "📥 A Receber"])

# ------------------------------------------------------------------
# A PAGAR
# ------------------------------------------------------------------
with tab_pagar:
    st.subheader("💸 Contas a Pagar")

    if not contas_pagar:
        st.info("Nenhuma conta a pagar cadastrada.")
    else:
        for c in contas_pagar:
            venc = parse_date(c.get("vencimento"))
            status_atual = c.get("status", "em_aberto")

            col1, col2, col3, col4, col5 = st.columns([4, 2, 3, 2, 2])

            col1.write(f"**{c.get('descricao', '—')}**")
            col2.write(fmt_brl(float(c.get("valor", 0.0))))
            col3.write(f"Vencimento: {venc.strftime('%d/%m/%Y') if venc else '—'}")
            col4.write(badge_status(status_atual, venc))

            novo_status = col5.selectbox(
                "Status",
                STATUS_OPTS,
                index=STATUS_OPTS.index(status_atual),
                key=f"pagar-{c['id']}"
            )

            if novo_status != status_atual:
                c["status"] = novo_status
                if novo_status == "paga":
                    c["paga_em"] = date.today().isoformat()
                else:
                    c["paga_em"] = None

                salvar(
                    "data/contas_pagar.json",
                    contas_pagar,
                    f"Update conta a pagar: {c.get('descricao')} -> {novo_status}"
                )

# ------------------------------------------------------------------
# A RECEBER
# ------------------------------------------------------------------
with tab_receber:
    st.subheader("📥 Contas a Receber")

    if not contas_receber:
        st.info("Nenhuma conta a receber cadastrada.")
    else:
        for c in contas_receber:
            previsto = parse_date(c.get("previsto"))
            status_atual = c.get("status", "em_aberto")

            col1, col2, col3, col4, col5 = st.columns([4, 2, 3, 2, 2])

            col1.write(f"**{c.get('descricao', '—')}**")
            col2.write(fmt_brl(float(c.get("valor", 0.0))))
            col3.write(f"Previsto: {previsto.strftime('%d/%m/%Y') if previsto else '—'}")
            col4.write(badge_status(status_atual, previsto))

            novo_status = col5.selectbox(
                "Status",
                STATUS_OPTS,
                index=STATUS_OPTS.index(status_atual),
                key=f"receber-{c['id']}"
            )

            if novo_status != status_atual:
                c["status"] = novo_status
                if novo_status == "paga":
                    c["recebido_em"] = date.today().isoformat()
                else:
                    c["recebido_em"] = None

                salvar(
                    "data/contas_receber.json",
                    contas_receber,
                    f"Update conta a receber: {c.get('descricao')} -> {novo_status}"
                )

# ------------------------------------------------------------------
# RESUMO DE PLANEJAMENTO E FLUXO FUTURO
# ------------------------------------------------------------------
st.divider()
st.subheader("📊 Planejamento & Fluxo Futuro")

hoje = date.today()

def resumo_fluxo(lista, campo_data):
    total_aberto = 0.0
    total_atrasado = 0.0
    total_prox7 = 0.0

    for c in lista:
        if c.get("status") != "em_aberto":
            continue
        valor = float(c.get("valor", 0.0))
        d = parse_date(c.get(campo_data))
        if not d:
            continue
        if d < hoje:
            total_atrasado += valor
        elif d <= (hoje + timedelta(days=7)):
            total_prox7 += valor
        total_aberto += valor

    return total_aberto, total_atrasado, total_prox7

p_aberto, p_atraso, p_prox7 = resumo_fluxo(contas_pagar, "vencimento")
r_aberto, r_atraso, r_prox7 = resumo_fluxo(contas_receber, "previsto")

c1, c2, c3 = st.columns(3)
c1.metric("💸 A Pagar (em aberto)", fmt_brl(p_aberto))
c2.metric("🔴 Atrasadas (pagar)", fmt_brl(p_atraso))
c3.metric("🟡 Próx. 7 dias (pagar)", fmt_brl(p_prox7))

c4, c5, c6 = st.columns(3)
c4.metric("📥 A Receber (em aberto)", fmt_brl(r_aberto))
c5.metric("🔴 Atrasadas (receber)", fmt_brl(r_atraso))
c6.metric("🟡 Próx. 7 dias (receber)", fmt_brl(r_prox7))

st.success("✅ Módulo de Contas integrado ao planejamento financeiro.")
