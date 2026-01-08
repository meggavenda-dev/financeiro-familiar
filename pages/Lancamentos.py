
# pages/1_Lancamentos.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional

# --------------------------------------------------
# Imports internos
# --------------------------------------------------
from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import (
    novo_id,
    criar,
    atualizar,
    excluir,
    gerar_parcelas,
    normalizar_tx,
    baixar,
    estornar,
)
from services.status import derivar_status, status_badge
from services.competencia import competencia_from_date, label_competencia
from services.utils import (
    fmt_brl,
    clear_cache_and_rerun,
    fmt_date_br,
    key_for,
)
from services.layout import responsive_columns, is_mobile
from services.ui import section, responsive_dataframe, card

# --------------------------------------------------
# Helper local
# --------------------------------------------------
def _parse_br_date(raw: str) -> Optional[date]:
    try:
        return datetime.strptime((raw or "").strip(), "%d/%m/%Y").date()
    except Exception:
        return None


# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Lançamentos",
    page_icon="🧾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("🧾 Lançamentos (Transações)")

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

categorias = data.get("data/categorias.json", {}).get("content", [])
contas = data.get("data/contas.json", {}).get("content", [])

# --------------------------------------------------
# Utilitários locais
# --------------------------------------------------
cat_map = {c.get("id"): c.get("nome") for c in categorias}
inv_cat = {v: k for k, v in cat_map.items()}

conta_map = {c.get("id"): c.get("nome") for c in contas}
inv_conta = {v: k for k, v in conta_map.items()}

# --------------------------------------------------
# Filtros
# --------------------------------------------------
competencias = sorted(
    {
        competencia_from_date(
            pd.to_datetime(x.get("data_prevista") or x.get("data_efetiva")).date()
        )
        for x in transacoes
        if (x.get("data_prevista") or x.get("data_efetiva"))
    },
    reverse=True,
)

default_comp = competencia_from_date(date.today())
if default_comp not in competencias:
    competencias.append(default_comp)

section("🔍 Filtros")

colf = responsive_columns(desktop=4, mobile=1)

comp_select = colf[0].selectbox(
    "Competência",
    options=competencias,
    format_func=label_competencia,
)

busca_texto = colf[1].text_input("Buscar por descrição")

somente_aberto = colf[2].checkbox("Somente em aberto")

tipo_filter = colf[3].selectbox(
    "Tipo",
    ["todos", "despesa", "receita"],
)

# --------------------------------------------------
# Filtragem
# --------------------------------------------------
def filtrar(ds):
    out = []
    for d in ds:
        dt_ref = d.get("data_prevista") or d.get("data_efetiva")
        if not dt_ref:
            continue

        comp = competencia_from_date(pd.to_datetime(dt_ref).date())
        if comp != comp_select:
            continue

        if tipo_filter != "todos" and d.get("tipo") != tipo_filter:
            continue

        if busca_texto and busca_texto.lower() not in d.get("descricao", "").lower():
            continue

        if somente_aberto and derivar_status(
            d.get("data_prevista"),
            d.get("data_efetiva"),
        ) == "paga":
            continue

        out.append(d)
    return out


lista_mes = filtrar(transacoes)

# --------------------------------------------------
# Resumo
# --------------------------------------------------
section(f"📅 Resumo — {label_competencia(comp_select)}")

def soma(tipo: str, status: Optional[str] = None):
    total = 0.0
    for t in lista_mes:
        if t.get("tipo") != tipo:
            continue
        st_calc = derivar_status(t.get("data_prevista"), t.get("data_efetiva"))
        if status and st_calc != status:
            continue
        total += float(t.get("valor", 0))
    return total


cols_resumo = responsive_columns(desktop=2, mobile=1)
cols_resumo[0].metric("📥 Receitas pagas", fmt_brl(soma("receita", "paga")))
cols_resumo[1].metric("💸 Despesas pagas", fmt_brl(soma("despesa", "paga")))

st.divider()

# --------------------------------------------------
# Cadastro
# --------------------------------------------------
section("➕ Nova transação")

with st.form("nova_tx"):
    cols = responsive_columns(desktop=4, mobile=1)
    tipo = cols[0].selectbox("Tipo", ["despesa", "receita"])
    valor = cols[1].number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_prev_br = cols[2].text_input(
        "Data prevista (dd/mm/aaaa)",
        value=fmt_date_br(date.today()),
    )
    conta_nome = cols[3].selectbox(
        "Conta",
        options=list(conta_map.values()) or ["Conta padrão"],
    )

    cols2 = responsive_columns(desktop=2, mobile=1)
    categoria_nome = cols2[0].selectbox(
        "Categoria",
        options=list(cat_map.values()) or ["Geral"],
    )
    descricao = cols2[1].text_input("Descrição")

    cols3 = responsive_columns(desktop=2, mobile=1)
    parcelar = cols3[0].checkbox("Parcelar?")
    qtd_parc = cols3[1].number_input(
        "Qtd. parcelas",
        min_value=1,
        max_value=60,
        value=1,
        disabled=not parcelar,
    )

    pagar_agora = st.checkbox("Marcar como paga/recebida")

    salvar = st.form_submit_button("Salvar")

if salvar:
    dt = _parse_br_date(data_prev_br)
    if not dt:
        st.error("Data inválida.")
    else:
        codigos = [
            t.get("codigo")
            for t in transacoes
            if isinstance(t.get("codigo"), int)
        ]
        next_code = max(codigos) + 1 if codigos else 1

        base = {
            "id": novo_id("tx"),
            "codigo": next_code,
            "tipo": tipo,
            "descricao": descricao.strip(),
            "valor": float(valor),
            "data_prevista": dt.isoformat(),
            "data_efetiva": date.today().isoformat() if pagar_agora else None,
            "conta_id": inv_conta.get(conta_nome),
            "categoria_id": inv_cat.get(categoria_nome),
            "excluido": False,
        }

        if parcelar and qtd_parc > 1:
            parcelas = gerar_parcelas(base, int(qtd_parc))
            for p in parcelas:
                criar(transacoes, p)
            gh.put_json(
                "data/transacoes.json",
                transacoes,
                f"[{usuario}] Parcelamento x{qtd_parc}",
                sha=sha_trans,
            )
        else:
            criar(transacoes, base)
            gh.put_json(
                "data/transacoes.json",
                transacoes,
                f"[{usuario}] Nova transação",
                sha=sha_trans,
            )

        clear_cache_and_rerun()

st.divider()

# --------------------------------------------------
# Lista
# --------------------------------------------------
section("📋 Lançamentos do mês")

if not lista_mes:
    st.info("Nenhum lançamento.")
else:
    df = pd.DataFrame(lista_mes)
    df["Status"] = df.apply(
        lambda r: status_badge(
            derivar_status(
                r.get("data_prevista"),
                r.get("data_efetiva"),
            )
        ),
        axis=1,
    )
    df["Valor"] = df["valor"].apply(fmt_brl)
    df["Prevista"] = df["data_prevista"].apply(fmt_date_br)

    show = df[["codigo", "descricao", "Valor", "Prevista", "Status"]].rename(
        columns={"descricao": "Descrição"}
    )

    responsive_dataframe(show)

    st.divider()

    # Ações individuais (cards no mobile)
    for tx in lista_mes:
        status = derivar_status(tx.get("data_prevista"), tx.get("data_efetiva"))

        if is_mobile():
            card(
                f"{tx.get('codigo')} — {tx.get('descricao')}",
                [
                    fmt_brl(tx.get("valor")),
                    status_badge(status),
                ],
            )

            c1, c2 = responsive_columns(desktop=2, mobile=1)
            if c1.button(
                "Marcar paga/recebida",
                disabled=(status == "paga"),
                key=key_for("pay", tx["id"]),
            ):
                baixar(tx)
                atualizar(transacoes, tx)
                gh.put_json(
                    "data/transacoes.json",
                    transacoes,
                    f"[{usuario}] Baixa {tx['id']}",
                    sha=sha_trans,
                )
                clear_cache_and_rerun()

            if c2.button(
                "Estornar",
                disabled=(status != "paga"),
                key=key_for("undo", tx["id"]),
            ):
                estornar(tx)
                atualizar(transacoes, tx)
                gh.put_json(
                    "data/transacoes.json",
                    transacoes,
                    f"[{usuario}] Estorno {tx['id']}",
                    sha=sha_trans,
                )
                clear_cache_and_rerun()

        else:
            with st.expander(
                f"{tx.get('codigo')} — {tx.get('descricao')}",
                expanded=False,
            ):
                cols = responsive_columns(desktop=3)
                cols[0].write(fmt_brl(tx.get("valor")))
                cols[1].write(fmt_date_br(tx.get("data_prevista")))
                cols[2].write(status_badge(status))

                b1, b2 = st.columns(2)
                if b1.button("✅ Baixar", key=key_for("pay-d", tx["id"])):
                    baixar(tx)
                    atualizar(transacoes, tx)
                    gh.put_json(
                        "data/transacoes.json",
                        transacoes,
                        f"[{usuario}] Baixa {tx['id']}",
                        sha=sha_trans,
                    )
                    clear_cache_and_rerun()

                if b2.button("↩️ Estornar", key=key_for("undo-d", tx["id"])):
                    estornar(tx)
                    atualizar(transacoes, tx)
                    gh.put_json(
                        "data/transacoes.json",
                        transacoes,
                        f"[{usuario}] Estorno {tx['id']}",
                        sha=sha_trans,
                    )
                    clear_cache_and_rerun()
