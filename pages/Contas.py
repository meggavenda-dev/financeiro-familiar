
# pages/2_Contas.py
import streamlit as st
from datetime import date, timedelta

from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import normalizar_tx, atualizar, estornar  # CHANGE: adiciona estornar
from services.status import derivar_status
from services.utils import (
    fmt_brl,
    parse_date_safe,
    clear_cache_and_rerun,
    fmt_date_br,
    key_for,   # CHANGE
)

st.set_page_config(
    page_title="Contas a Pagar / Receber",
    page_icon="📅",
    layout="wide",
)
st.title("📅 Contas a Pagar / Receber")

# --------------------------------------------------
# Contexto / Permissões
# --------------------------------------------------
init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

require_admin(ctx)

gh = ctx.get("gh")
usuario = ctx.get("usuario_id", "u1")

# --------------------------------------------------
# Carregamento
# --------------------------------------------------
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))
trans_map = data["data/transacoes.json"]

transacoes = [
    t for t in (normalizar_tx(x) for x in trans_map["content"])
    if t is not None
]
sha_trans = trans_map["sha"]

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def salvar(msg: str):
    gh.put_json(
        "data/transacoes.json",
        transacoes,
        f"[{usuario}] {msg}",
        sha=sha_trans,
    )
    clear_cache_and_rerun()


def badge_text(tx: dict) -> str:  # CHANGE: remove HTML entities na assinatura
    """Texto amigável baseado APENAS no status lógico."""
    stx = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))
    d = parse_date_safe(tx.get("data_prevista"))
    hoje = date.today()

    if stx == "paga":
        return "✅ Paga"

    if d:
        if d < hoje:
            return "🔴 Vencida"
        if d <= hoje + timedelta(days=7):
            return "🟡 Próxima"

    return "🟢 Em aberto"


# --------------------------------------------------
# Tabs
# --------------------------------------------------
tab_pagar, tab_receber = st.tabs(["💸 A Pagar", "📥 A Receber"])

# ==================================================
# A PAGAR
# ==================================================
with tab_pagar:
    st.subheader("💸 Contas a Pagar")

    mostrar_pagas = st.checkbox(
        "Mostrar itens pagos",
        value=False,
        key="mostrar_pagas_pagar",
    )

    itens = []
    for tx in transacoes:
        if tx.get("tipo") != "despesa":
            continue
        if tx.get("excluido"):
            continue
        status = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))
        if not mostrar_pagas and status == "paga":
            continue
        itens.append(tx)

    if not itens:
        st.info("Nenhuma conta a pagar.")
    else:
        for tx in itens:
            prev = parse_date_safe(tx.get("data_prevista"))
            status = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))

            # CHANGE: adiciona coluna extra para botão Estornar
            c1, c2, c3, c4, c5, c6 = st.columns([4, 2, 3, 2, 3, 3])

            c1.write(f"**{tx.get('descricao','—')}**")
            c2.write(fmt_brl(float(tx.get("valor", 0))))
            c3.write(f"Previsto: {fmt_date_br(prev)}")
            c4.write(badge_text(tx))

            pagar_btn = c5.button(
                "Marcar como paga",
                key=key_for("pagar", tx["id"]),
                disabled=(status == "paga"),
            )
            # CHANGE: novo botão de estorno
            estornar_btn = c6.button(
                "Estornar pagamento",
                key=key_for("estornar", tx["id"]),
                disabled=(status != "paga"),
            )

            nova_prev = c5.date_input(
                "Reagendar",
                value=prev or date.today(),
                key=key_for("prev", tx["id"]),
            )

            salvar_prev = c5.button(
                "Salvar data",
                key=key_for("save-prev", tx["id"]),
                disabled=(status == "paga"),
            )

            if pagar_btn:
                tx["data_efetiva"] = date.today().isoformat()
                atualizar(transacoes, tx)
                salvar(f"Baixa pagar: {tx.get('descricao')}")

            if estornar_btn:
                estornar(tx)
                atualizar(transacoes, tx)
                salvar(f"Estorno pagar: {tx.get('descricao')}")

            if salvar_prev and nova_prev and status != "paga":
                tx["data_prevista"] = nova_prev.isoformat()
                atualizar(transacoes, tx)
                salvar(f"Reagendamento pagar → {nova_prev.isoformat()}")

# ==================================================
# A RECEBER
# ==================================================
with tab_receber:
    st.subheader("📥 Contas a Receber")

    mostrar_recebidas = st.checkbox(
        "Mostrar itens recebidos",
        value=False,
        key="mostrar_pagas_receber",
    )

    itens = []
    for tx in transacoes:
        if tx.get("tipo") != "receita":
            continue
        if tx.get("excluido"):
            continue
        status = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))
        if not mostrar_recebidas and status == "paga":
            continue
        itens.append(tx)

    if not itens:
        st.info("Nenhuma conta a receber.")
    else:
        for tx in itens:
            prev = parse_date_safe(tx.get("data_prevista"))
            status = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))

            # CHANGE: adiciona coluna extra para botão Estornar
            c1, c2, c3, c4, c5, c6 = st.columns([4, 2, 3, 2, 3, 3])

            c1.write(f"**{tx.get('descricao','—')}**")
            c2.write(fmt_brl(float(tx.get("valor", 0))))
            c3.write(f"Previsto: {fmt_date_br(prev)}")
            c4.write(badge_text(tx))

            receber_btn = c5.button(
                "Marcar como recebida",
                key=key_for("receber", tx["id"]),
                disabled=(status == "paga"),
            )
            # CHANGE: novo botão de estorno
            estornar_btn = c6.button(
                "Estornar recebimento",
                key=key_for("estornar-rec", tx["id"]),
                disabled=(status != "paga"),
            )

            nova_prev = c5.date_input(
                "Reagendar",
                value=prev or date.today(),
                key=key_for("prev-rec", tx["id"]),
            )

            salvar_prev = c5.button(
                "Salvar data",
                key=key_for("save-prev-rec", tx["id"]),
                disabled=(status == "paga"),
            )

            if receber_btn:
                tx["data_efetiva"] = date.today().isoformat()
                atualizar(transacoes, tx)
                salvar(f"Baixa receber: {tx.get('descricao')}")

            if estornar_btn:
                estornar(tx)
                atualizar(transacoes, tx)
                salvar(f"Estorno receber: {tx.get('descricao')}")

            if salvar_prev and nova_prev and status != "paga":
                tx["data_prevista"] = nova_prev.isoformat()
                atualizar(transacoes, tx)
                salvar(f"Reagendamento receber → {nova_prev.isoformat()}")

# --------------------------------------------------
# Resumo futuro
# --------------------------------------------------
st.divider()
st.subheader("📊 Planejamento & Fluxo Futuro")  # CHANGE: remove HTML entity

hoje = date.today()

def resumo(tipo: str):
    total, vencido, prox7 = 0.0, 0.0, 0.0
    for tx in transacoes:
        if tx.get("tipo") != tipo:
            continue
        if tx.get("excluido"):
            continue

        status = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))
        if status == "paga":
            continue

        v = float(tx.get("valor", 0))
        d = parse_date_safe(tx.get("data_prevista"))
        if not d:
            continue

        total += v
        if d < hoje:  # CHANGE: remove &lt;
            vencido += v
        elif d <= hoje + timedelta(days=7):  # CHANGE: remove &lt;=
            prox7 += v

    return total, vencido, prox7


p_aberto, p_vencido, p_prox7 = resumo("despesa")
r_aberto, r_vencido, r_prox7 = resumo("receita")

c1, c2, c3 = st.columns(3)
c1.metric("💸 A Pagar (aberto)", fmt_brl(p_aberto))
c2.metric("🔴 Vencidas (pagar)", fmt_brl(p_vencido))
c3.metric("🟡 Próx. 7 dias (pagar)", fmt_brl(p_prox7))

c4, c5, c6 = st.columns(3)
c4.metric("📥 A Receber (aberto)", fmt_brl(r_aberto))
c5.metric("🔴 Vencidas (receber)", fmt_brl(r_vencido))
c6.metric("🟡 Próx. 7 dias (receber)", fmt_brl(r_prox7))

