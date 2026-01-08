
# pages/1_Lancamentos.py
import streamlit as st
import pandas as pd
from datetime import date, datetime

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
)
from services.status import derivar_status, status_badge
from services.competencia import competencia_from_date, label_competencia
from services.utils import (
    fmt_brl,
    clear_cache_and_rerun,
    fmt_date_br,
    key_for,               # CHANGE
)

# --------------------------------------------------
# Helpers locais
# --------------------------------------------------
def _parse_br_date(raw: str) -> date | None:   # CHANGE (nome simplificado)
    """Converte 'dd/mm/aaaa' para date. Retorna None se inválido."""
    try:
        return datetime.strptime((raw or "").strip(), "%d/%m/%Y").date()
    except Exception:
        return None


# --------------------------------------------------
# Página
# --------------------------------------------------
st.set_page_config(
    page_title="Lançamentos (Transações)",
    page_icon="🧾",
    layout="wide",
)
st.title("🧾 Lançamentos")

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
usuario = ctx.get("usuario_id", "u1")  # CHANGE

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

categorias = data.get("data/categorias.json", {"content": []})["content"]
contas = data.get("data/contas.json", {"content": []})["content"]
orcamentos = data.get("data/orcamentos.json", {"content": []})["content"]

def cat_opts():
    return {c.get("id"): c.get("nome") for c in categorias} or {"cat1": "Geral"}

def conta_opts():
    return {c.get("id"): c.get("nome") for c in contas} or {"c1": "Conta Principal"}

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

competencias = sorted(set(competencias), reverse=True)

st.subheader("🔍 Filtros")
f1, f2, f3, f4 = st.columns([2, 2, 2, 2])

comp_select = f1.selectbox(
    "Competência (mês)",
    options=competencias,
    format_func=label_competencia,
)

busca_texto = f2.text_input("Buscar por descrição/código")
somente_em_aberto = f3.checkbox("Somente em aberto (não pagas)")
tipo_filter = f4.selectbox("Tipo", ["todos", "despesa", "receita"])

def filtrar_por_comp(ds):
    out = []
    for d in ds:
        dt_str = d.get("data_prevista") or d.get("data_efetiva")
        if not dt_str:
            continue

        comp = competencia_from_date(pd.to_datetime(dt_str).date())
        if comp != comp_select:
            continue

        if tipo_filter != "todos" and d.get("tipo") != tipo_filter:
            continue

        if busca_texto:
            txt = f"{d.get('descricao','')} {d.get('codigo','')}".lower()
            if busca_texto.lower() not in txt:
                continue

        if somente_em_aberto:
            if derivar_status(d.get("data_prevista"), d.get("data_efetiva")) == "paga":
                continue

        out.append(d)
    return out

mes_itens = filtrar_por_comp(transacoes)

# --------------------------------------------------
# Resumo mensal
# --------------------------------------------------
st.subheader(f"📅 Resumo — {label_competencia(comp_select)}")

def soma(ds, tipo, status=None) -> float:
    total = 0.0
    for x in ds:
        if x.get("tipo") != tipo:
            continue
        st_calc = derivar_status(x.get("data_prevista"), x.get("data_efetiva"))
        if status is not None and st_calc != status:
            continue
        total += float(x.get("valor", 0.0))
    return total

rec_total = soma(mes_itens, "receita")
des_total = soma(mes_itens, "despesa")
rec_pagas = soma(mes_itens, "receita", "paga")
des_pagas = soma(mes_itens, "despesa", "paga")

# --------------------------------------------------
# Cadastro
# --------------------------------------------------
st.subheader("➕ Nova transação")

cat_map = cat_opts()
conta_map = conta_opts()

with st.form("nova_tx"):
    c1, c2, c3, c4 = st.columns([2, 1, 2, 2])

    tipo = c1.selectbox("Tipo", ["despesa", "receita"])
    valor = c2.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_prev_br = c3.text_input(
        "Data prevista (dd/mm/aaaa)",
        value=fmt_date_br(date.today()),
    )
    conta_nome = c4.selectbox("Conta", options=list(conta_map.values()))

    categoria_nome = st.selectbox("Categoria", options=list(cat_map.values()))
    descricao = st.text_input("Descrição")

    parcelar = st.checkbox("Parcelar?")
    qtd_parc = st.number_input(
        "Qtd. parcelas",
        min_value=1,
        max_value=60,
        value=1,
        disabled=not parcelar,
    )

    pagar_hoje = st.checkbox("Marcar como paga/recebida")

    salvar = st.form_submit_button("Salvar")

if salvar:
    dprev = _parse_br_date(data_prev_br)
    if not dprev:
        st.error("Data prevista inválida (dd/mm/aaaa).")
    else:
        inv_cat = {v: k for k, v in cat_map.items()}
        inv_conta = {v: k for k, v in conta_map.items()}
        cods = [t.get("codigo") for t in transacoes if isinstance(t.get("codigo"), int)]
        next_code = max(cods) + 1 if cods else 1

        base = {
            "id": novo_id("tx"),
            "codigo": next_code,
            "tipo": tipo,
            "descricao": descricao.strip(),
            "valor": float(valor),
            "data_prevista": dprev.isoformat(),
            "data_efetiva": date.today().isoformat() if pagar_hoje else None,
            "conta_id": inv_conta.get(conta_nome, "c1"),
            "categoria_id": inv_cat.get(categoria_nome),
            "excluido": False,
            "parcelamento": None,
            "recorrente": False,
        }

        if parcelar and qtd_parc > 1:
            for p in gerar_parcelas(base, qtd_parc):
                criar(transacoes, p)
            gh.put_json(
                "data/transacoes.json",
                transacoes,
                f"[{usuario}] Add {qtd_parc} parcelas",
                sha=sha_trans,
            )
        else:
            criar(transacoes, base)
            gh.put_json(
                "data/transacoes.json",
                transacoes,
                f"[{usuario}] Add transação",
                sha=sha_trans,
            )

        clear_cache_and_rerun()
