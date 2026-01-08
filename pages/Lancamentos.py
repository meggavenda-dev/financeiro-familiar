
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
from services.utils import fmt_brl, clear_cache_and_rerun, fmt_date_br

# --------------------------------------------------
# Página
# --------------------------------------------------
st.set_page_config(page_title="Lançamentos (Transações)", page_icon="🧾", layout="wide")
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
# Filtros de competência e texto
# --------------------------------------------------
competencias = sorted(
    {competencia_from_date(pd.to_datetime(x.get("data_prevista") or x.get("data_efetiva")).date())
     for x in transacoes if (x.get("data_prevista") or x.get("data_efetiva"))},
    reverse=True
)
default_comp = competencia_from_date(date.today())
if default_comp not in competencias:
    competencias.append(default_comp)
competencias = sorted(set(competencias), reverse=True)

st.subheader("🔍 Filtros")
colf1, colf2, colf3 = st.columns([2, 2, 2])
comp_select = colf1.selectbox("Competência (mês)", options=competencias,
                              format_func=label_competencia, index=0)
busca_texto = colf2.text_input("Buscar por descrição")
somente_em_aberto = colf3.checkbox("Somente em aberto (não pagas)", value=False)

def filtrar_por_comp(ds):
    out = []
    for d in ds:
        dt_str = d.get("data_prevista") or d.get("data_efetiva")
        if not dt_str:
            continue
        comp = competencia_from_date(pd.to_datetime(dt_str).date())
        if comp != comp_select:
            continue
        if busca_texto:
            txt = f"{d.get('descricao','')}".lower()
            if busca_texto.lower() not in txt:
                continue
        if somente_em_aberto:
            if derivar_status(d.get("data_prevista"), d.get("data_efetiva")) == "paga":
                continue
        out.append(d)
    return out

mes_itens = filtrar_por_comp(transacoes)

# --------------------------------------------------
# Resumo Mensal (clarificado por tipo e status)
# --------------------------------------------------
st.subheader(f"📅 Resumo — {label_competencia(comp_select)}")

def soma_por_tipo_e_status(ds, tipo: str, status: str | None = None) -> float:
    total = 0.0
    for x in ds:
        if x.get("tipo") != tipo:
            continue
        st_calc = derivar_status(x.get("data_prevista"), x.get("data_efetiva"))
        if status is not None and st_calc != status:
            continue
        total += float(x.get("valor", 0.0))
    return total

# Totais por tipo (mês)
total_rec = soma_por_tipo_e_status(mes_itens, tipo="receita", status=None)
total_des = soma_por_tipo_e_status(mes_itens, tipo="despesa", status=None)

# Pagas
rec_pagas = soma_por_tipo_e_status(mes_itens, tipo="receita", status="paga")
des_pagas = soma_por_tipo_e_status(mes_itens, tipo="despesa", status="paga")

# Em aberto (não pagas)
rec_abertas = total_rec - rec_pagas
des_abertas = total_des - des_pagas

# Vencidas
rec_vencidas = soma_por_tipo_e_status(mes_itens, tipo="receita", status="vencida")
des_vencidas = soma_por_tipo_e_status(mes_itens, tipo="despesa", status="vencida")

# Linha 1 — pagas
l1c1, l1c2 = st.columns(2)
l1c1.metric("📥 Receitas pagas (mês)", fmt_brl(rec_pagas), help="Receitas com data efetiva na competência selecionada")
l1c2.metric("💸 Despesas pagas (mês)", fmt_brl(des_pagas), help="Despesas com data efetiva na competência selecionada")

# Linha 2 — em aberto
l2c1, l2c2 = st.columns(2)
l2c1.metric("📥 Receitas em aberto (mês)", fmt_brl(rec_abertas), help="Receitas ainda não efetivadas na competência")
l2c2.metric("💸 Despesas em aberto (mês)", fmt_brl(des_abertas), help="Despesas ainda não efetivadas na competência")

# Linha 3 — vencidas
l3c1, l3c2 = st.columns(2)
l3c1.metric("📥 Receitas vencidas (mês)", fmt_brl(rec_vencidas), help="Receitas não pagas com data prevista passada")
l3c2.metric("💸 Despesas vencidas (mês)", fmt_brl(des_vencidas), help="Despesas não pagas com data prevista passada")

st.divider()

# --------------------------------------------------
# Cadastro — novo / parcelado
# --------------------------------------------------
st.subheader("➕ Nova transação")

cat_map = cat_opts()
conta_map = conta_opts()

with st.form("nova_tx"):
    c1, c2, c3, c4 = st.columns([2, 1, 2, 2])
    tipo = c1.selectbox("Tipo", ["despesa", "receita"])
    valor = c2.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_prev = c3.date_input("Data prevista", value=date.today())
    conta_nome = c4.selectbox("Conta", options=list(conta_map.values()))

    d1, d2 = st.columns([2, 2])
    categoria_nome = d1.selectbox("Categoria", options=list(cat_map.values()))
    descricao = d2.text_input("Descrição", placeholder="Ex.: Supermercado, Internet, Salário")

    e1, e2 = st.columns([2, 2])
    parcelar = e1.checkbox("Parcelar?")
    qtd_parc = e2.number_input("Qtd. parcelas", min_value=1, max_value=60, value=1, disabled=not parcelar)

    pagar_hoje = st.checkbox("Marcar como paga/recebida imediatamente")

    salvar_btn = st.form_submit_button("Salvar")

if salvar_btn:
    inv_cat = {v: k for k, v in cat_map.items()}
    inv_conta = {v: k for k, v in conta_map.items()}
    base = {
        "id": novo_id("tx"),
        "tipo": tipo,
        "descricao": (descricao or "").strip(),
        "valor": float(valor),
        "data_prevista": data_prev.isoformat(),
        "data_efetiva": (date.today().isoformat() if pagar_hoje else None),
        "conta_id": inv_conta.get(conta_nome, "c1"),
        "categoria_id": inv_cat.get(categoria_nome),
        "excluido": False,
        "parcelamento": None,
        "recorrente": False,
    }
    if parcelar and int(qtd_parc) > 1:
        pars = gerar_parcelas(base, int(qtd_parc))
        for p in pars:
            criar(transacoes, p)
        gh.put_json("data/transacoes.json", transacoes, f"Add {qtd_parc} parcelas", sha=sha_trans)
        clear_cache_and_rerun()
    else:
        criar(transacoes, base)
        gh.put_json("data/transacoes.json", transacoes, "Add transação", sha=sha_trans)
        clear_cache_and_rerun()

# --------------------------------------------------
# Lista por competência (com ações por linha)
# --------------------------------------------------
st.subheader(f"📋 Lançamentos — {label_competencia(comp_select)}")

lista_mes = mes_itens
if not lista_mes:
    st.info("Nenhum lançamento para este mês.")
else:
    df = pd.DataFrame(lista_mes)
    df["status"] = df.apply(lambda r: derivar_status(r.get("data_prevista"), r.get("data_efetiva")), axis=1)
    df["status_badge"] = df["status"].apply(status_badge)

    # Colunas formatadas BR
    df["Data prevista (BR)"] = df["data_prevista"].apply(lambda x: fmt_date_br(x))
    df["Data efetiva (BR)"] = df["data_efetiva"].apply(lambda x: fmt_date_br(x))

    # Coluna auxiliar para ordenação por data prevista real
    df["_data_prevista_sort"] = pd.to_datetime(df["data_prevista"], errors="coerce")

    df_show = df[["tipo", "descricao", "valor", "Data prevista (BR)", "Data efetiva (BR)", "status_badge", "id", "_data_prevista_sort"]].rename(columns={
        "tipo": "Tipo", "descricao": "Descrição", "valor": "Valor", "status_badge": "Status", "id": "ID"
    }).sort_values("_data_prevista_sort", ascending=False).drop(columns=["_data_prevista_sort"])

    # Exportar CSV dos itens filtrados
    csv_bytes = df_show.to_csv(index=False).encode("utf-8")
    st.download_button("📤 Exportar CSV (filtros aplicados)", data=csv_bytes, file_name=f"lancamentos_{comp_select}.csv", mime="text/csv")

    st.dataframe(df_show, use_container_width=True)

    st.markdown("### ✏️ Ações por linha")
    for row in df_show.to_dict(orient="records"):
        r_id = row["ID"]
        alvo = next((x for x in transacoes if x.get("id") == r_id), None)
        if not alvo:
            continue
        col1, col2, col3, col4, col5 = st.columns([4, 2, 3, 2, 4])
        col1.write(f"**{row['Descrição']}**")
        col2.write(fmt_brl(float(row["Valor"])))
        col3.write(f"Prevista: {row['Data prevista (BR)']}")
        col4.write(row["Status"])
        pagar_btn = col5.button("Marcar como paga/recebida", key=f"pay-{r_id}", disabled=(row["Status"] == "✅ Paga"))
        editar_exp = st.expander(f"Editar — {r_id}", expanded=False)
        excluir_btn = st.button("Excluir", key=f"del-{r_id}")

        if pagar_btn:
            baixar(alvo)
            atualizar(transacoes, alvo)
            gh.put_json("data/transacoes.json", transacoes, f"Baixa {r_id}", sha=sha_trans)
            clear_cache_and_rerun()

        with editar_exp:
            with st.form(f"edit-{r_id}"):
                e1, e2, e3 = st.columns(3)
                novo_tipo = e1.selectbox("Tipo", ["despesa", "receita"], index=["despesa", "receita"].index(alvo.get("tipo", "despesa")))
                novo_valor = e2.number_input("Valor (R$)", min_value=0.01, step=0.01, value=float(alvo.get("valor", 0.0)))
                # date_input mostra em UI; persistimos como ISO
                nova_prev = e3.date_input("Data prevista", value=pd.to_datetime(alvo.get("data_prevista")).date() if alvo.get("data_prevista") else date.today())

                e4 = st.text_input("Descrição", value=alvo.get("descricao", ""))
                limpar_pagamento = st.checkbox("Estornar (remover pagamento)?", value=False)

                ok_btn = st.form_submit_button("Salvar edição")

            if ok_btn:
                item_editado = alvo.copy()
                item_editado.update({
                    "tipo": novo_tipo,
                    "valor": float(novo_valor),
                    "data_prevista": nova_prev.isoformat(),
                    "descricao": (e4 or "").strip(),
                    "data_efetiva": None if limpar_pagamento else alvo.get("data_efetiva"),
                    "atualizado_em": datetime.now().isoformat(),
                })
                atualizar(transacoes, item_editado)
                gh.put_json("data/transacoes.json", transacoes, f"Edita {r_id}", sha=sha_trans)
                clear_cache_and_rerun()

        if excluir_btn:
            excluir(transacoes, r_id)
            gh.put_json("data/transacoes.json", transacoes, f"Exclui {r_id}", sha=sha_trans)
            clear_cache_and_rerun()

st.divider()

# --------------------------------------------------
# 💰 Orçamento mensal por categoria (visão)
# --------------------------------------------------
st.subheader("💰 Orçamento mensal por categoria")

if not orcamentos:
    st.info("Nenhum orçamento cadastrado em data/orcamentos.json. Você pode gerenciar na página **Orçamentos**.")
else:
    cat_names = {c.get("id"): c.get("nome") for c in categorias}
    gastos_cat = {}
    for it in mes_itens:
        cid = it.get("categoria_id")
        gastos_cat[cid] = gastos_cat.get(cid, 0.0) + float(it.get("valor", 0.0))

    rows = []
    for o in orcamentos:
        cid = o.get("categoria_id")
        limite = float(o.get("limite_mensal", 0.0))
        gasto = float(gastos_cat.get(cid, 0.0))
        uso = (gasto / limite) if limite > 0 else 0.0
        rows.append({
            "Categoria": cat_names.get(cid, cid),
            "Limite": fmt_brl(limite),
            "Gasto": fmt_brl(gasto),
            "% Uso": f"{uso*100:.1f}%",
            "Status": ("🔴 Estourado" if limite > 0 and gasto > limite else ("🟡 Próximo" if uso >= 0.8 else "🟢 OK")),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    estouradas = [r for r in rows if "Estourado" in r["Status"]]
    if estouradas:
        nomes = ", ".join(r["Categoria"] for r in estouradas)
        st.error(f"🔔 Orçamento estourado: {nomes}")
