
# pages/2_Contas.py
import streamlit as st
from datetime import date, timedelta

# --------------------------------------------------
# Imports internos
# --------------------------------------------------
from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import normalizar_tx, atualizar, estornar
from services.status import derivar_status
from services.utils import (
    fmt_brl,
    parse_date_safe,
    clear_cache_and_rerun,
    fmt_date_br,
    key_for,
)
from services.layout import responsive_columns, is_mobile
from services.ui import section, card

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Contas a Pagar / Receber",
    page_icon="📅",
    layout="centered",
    initial_sidebar_state="collapsed",
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
# Helper de salvamento
# --------------------------------------------------
def salvar(msg: str):
    gh.put_json(
        "data/transacoes.json",
        transacoes,
        f"[{usuario}] {msg}",
        sha=sha_trans,
    )
    clear_cache_and_rerun()

# --------------------------------------------------
# Badge amigável
# --------------------------------------------------
def badge_text(tx: dict) -> str:
    status = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))
    d = parse_date_safe(tx.get("data_prevista"))
    hoje = date.today()

    if status == "paga":
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
    section("💸 Contas a pagar")

    mostrar_pagas = st.checkbox("Mostrar contas pagas", value=False)

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

            # -------------------------------
            # MOBILE
            # -------------------------------
            if is_mobile():
                card(
                    tx.get("descricao", "Despesa"),
                    [
                        f"Valor: {fmt_brl(tx.get('valor', 0))}",
                        f"Previsto: {fmt_date_br(prev)}",
                        badge_text(tx),
                    ],
                )

                cols = responsive_columns(desktop=2, mobile=1)

                if cols[0].button(
                    "✅ Marcar paga",
                    key=key_for("pagar", tx["id"]),
                    disabled=(status == "paga"),
                ):
                    tx["data_efetiva"] = date.today().isoformat()
                    atualizar(transacoes, tx)
                    salvar(f"Baixa pagar {tx.get('descricao')}")

                if cols[1].button(
                    "↩️ Estornar",
                    key=key_for("estornar", tx["id"]),
                    disabled=(status != "paga"),
                ):
                    estornar(tx)
                    atualizar(transacoes, tx)
                    salvar(f"Estorno pagar {tx.get('descricao')}")

                nova_prev = st.date_input(
                    "Reagendar",
                    value=prev or date.today(),
                    key=key_for("prev", tx["id"]),
                )

                if st.button(
                    "Salvar nova data",
                    key=key_for("save-prev", tx["id"]),
                    disabled=(status == "paga"),
                ):
                    tx["data_prevista"] = nova_prev.isoformat()
                    atualizar(transacoes, tx)
                    salvar(f"Reagendamento pagar {tx.get('descricao')}")

                st.divider()

            # -------------------------------
            # DESKTOP
            # -------------------------------
            else:
                c1, c2, c3, c4, c5 = st.columns([4, 2, 2, 2, 2])

                c1.write(f"**{tx.get('descricao','—')}**")
                c2.write(fmt_brl(tx.get("valor", 0)))
                c3.write(fmt_date_br(prev))
                c4.write(badge_text(tx))

                if c5.button("✅ Pagar", key=key_for("pay-d", tx["id"]), disabled=(status == "paga")):
                    tx["data_efetiva"] = date.today().isoformat()
                    atualizar(transacoes, tx)
                    salvar(f"Baixa pagar {tx.get('descricao')}")

# ==================================================
# A RECEBER
# ==================================================
with tab_receber:
    section("📥 Contas a receber")

    mostrar_recebidas = st.checkbox("Mostrar recebidas", value=False)

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

            if is_mobile():
                card(
                    tx.get("descricao", "Receita"),
                    [
                        f"Valor: {fmt_brl(tx.get('valor', 0))}",
                        f"Previsto: {fmt_date_br(prev)}",
                        badge_text(tx),
                    ],
                )

                cols = responsive_columns(desktop=2, mobile=1)

                if cols[0].button(
                    "✅ Marcar recebida",
                    key=key_for("recv", tx["id"]),
                    disabled=(status == "paga"),
                ):
                    tx["data_efetiva"] = date.today().isoformat()
                    atualizar(transacoes, tx)
                    salvar(f"Baixa receber {tx.get('descricao')}")

                if cols[1].button(
                    "↩️ Estornar",
                    key=key_for("undo-rec", tx["id"]),
                    disabled=(status != "paga"),
                ):
                    estornar(tx)
                    atualizar(transacoes, tx)
                    salvar(f"Estorno receber {tx.get('descricao')}")

                nova_prev = st.date_input(
                    "Reagendar",
                    value=prev or date.today(),
                    key=key_for("prev-rec", tx["id"]),
                )

                if st.button(
                    "Salvar nova data",
                    key=key_for("save-prev-rec", tx["id"]),
                    disabled=(status == "paga"),
                ):
                    tx["data_prevista"] = nova_prev.isoformat()
                    atualizar(transacoes, tx)
                    salvar(f"Reagendamento receber {tx.get('descricao')}")

                st.divider()

            else:
                c1, c2, c3, c4, c5 = st.columns([4, 2, 2, 2, 2])

                c1.write(f"**{tx.get('descricao','—')}**")
                c2.write(fmt_brl(tx.get("valor", 0)))
                c3.write(fmt_date_br(prev))
                c4.write(badge_text(tx))

                if c5.button("✅ Receber", key=key_for("recv-d", tx["id"]), disabled=(status == "paga")):
                    tx["data_efetiva"] = date.today().isoformat()
                    atualizar(transacoes, tx)
                    salvar(f"Baixa receber {tx.get('descricao')}")

# --------------------------------------------------
# Resumo futuro
# --------------------------------------------------
st.divider()
section("📊 Planejamento futuro")

hoje = date.today()

def resumo(tipo):
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
        if d < hoje:
            vencido += v
        elif d <= hoje + timedelta(days=7):
            prox7 += v

    return total, vencido, prox7

p_aberto, p_vencido, p_prox7 = resumo("despesa")
r_aberto, r_vencido, r_prox7 = resumo("receita")

cols_resumo = responsive_columns(desktop=3, mobile=1)
cols_resumo[0].metric("💸 A pagar (aberto)", fmt_brl(p_aberto))
cols_resumo[1].metric("🔴 Vencidas", fmt_brl(p_vencido))
cols_resumo[2].metric("🟡 Próx. 7 dias", fmt_brl(p_prox7))

cols_resumo2 = responsive_columns(desktop=3, mobile=1)
cols_resumo2[0].metric("📥 A receber (aberto)", fmt_brl(r_aberto))
cols_resumo2[1].metric("🔴 Vencidas", fmt_brl(r_vencido))
cols_resumo2[2].metric("🟡 Próx. 7 dias", fmt_brl(r_prox7))
