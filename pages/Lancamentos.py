
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
    normalizar_tx,
    baixar,
    estornar,
)
from services.status import status_badge, derivar_status
from services.competencia import competencia_from_date, label_competencia

# --------------------------------------------------
# Página
# --------------------------------------------------
st.set_page_config(page_title="Lançamentos (Transações)", page_icon="🧾", layout="wide")
st.title("🧾 Lançamentos")

# --------------------------------------------------
# Contexto / Permissões
# --------------------------------------------------
ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

require_admin(ctx)
gh = ctx.gh

# --------------------------------------------------
# Carregamento
# --------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))

trans_map = data["data/transacoes.json"]
transacoes = [normalizar_tx(x) for x in trans_map["content"]]
sha_trans = trans_map["sha"]

categorias = data.get("data/categorias.json", {"content": []})["content"]
contas = data.get("data/contas.json", {"content": []})["content"]
orcamentos = data.get("data/orcamentos.json", {"content": []})["content"]

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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
colf1, colf2 = st.columns([2,2])
comp_select = colf1.selectbox("Competência (mês)", options=competencias,
                              format_func=label_competencia, index=0)
busca_texto = colf2.text_input("Buscar por descrição")

def filtrar_por_comp(ds):
    out = []
    for d in ds:
        # usa data_prevista como referência de competência
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
        out.append(d)
    return out

mes_itens = filtrar_por_comp(transacoes)

# --------------------------------------------------
# Resumo Mensal
# --------------------------------------------------
st.subheader(f"📅 Resumo — {label_competencia(comp_select)}")

def soma(ds, tipo=None, status=None):
    total = 0.0
    for x in ds:
        if tipo and x.get("tipo") != tipo: 
            continue
        st_calc = derivar_status(x.get("data_prevista"), x.get("data_efetiva"))
        if status and st_calc != status:
            continue
        total += float(x.get("valor", 0.0))
    return total

total_receitas = soma(mes_itens, tipo="receita")
total_despesas = soma(mes_itens, tipo="despesa")
total_pago = soma(mes_itens, status="paga")
total_vencido = soma(mes_itens, status="vencida")

kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("📥 Receitas (mês)", fmt_brl(total_receitas))
kc2.metric("💸 Despesas (mês)", fmt_brl(total_despesas))
kc3.metric("✅ Pago", fmt_brl(total_pago))
kc4.metric("🔴 Vencido", fmt_brl(total_vencido))

st.divider()

# --------------------------------------------------
# Cadastro — novo / parcelado
# --------------------------------------------------
st.subheader("➕ Nova transação")

cat_map = cat_opts()
conta_map = conta_opts()

with st.form("nova_tx"):
    c1, c2, c3, c4 = st.columns([2,1,2,2])
    tipo = c1.selectbox("Tipo", ["despesa", "receita"])
    valor = c2.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_prev = c3.date_input("Data prevista", value=date.today())
    conta_nome = c4.selectbox("Conta", options=list(conta_map.values()))

    d1, d2 = st.columns([2,2])
    categoria_nome = d1.selectbox("Categoria", options=list(cat_map.values()))
    descricao = d2.text_input("Descrição", placeholder="Ex.: Supermercado, Internet, Salário")

    e1, e2 = st.columns([2,2])
    parcelar = e1.checkbox("Parcelar?")
    qtd_parc = e2.number_input("Qtd. parcelas", min_value=1, max_value=60, value=1, disabled=not parcelar)

    pagar_hoje = st.checkbox("Marcar como paga/recebida imediatamente")

    salvar_btn = st.form_submit_button("Salvar")

if salvar_btn:
    inv_cat = {v:k for k,v in cat_map.items()}
    inv_conta = {v:k for k,v in conta_map.items()}
    base = {
        "id": novo_id("tx"),
        "tipo": tipo,
        "descricao": descricao.strip(),
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
        new_sha = gh.put_json("data/transacoes.json", transacoes, f"Add {qtd_parc} parcelas", sha=sha_trans)
        sha_trans = new_sha
        st.cache_data.clear()
        st.success("✅ Parcelas adicionadas.")
        st.rerun()
    else:
        criar(transacoes, base)
        new_sha = gh.put_json("data/transacoes.json", transacoes, "Add transação", sha=sha_trans)
        sha_trans = new_sha
        st.cache_data.clear()
        st.success("✅ Transação adicionada.")
        st.rerun()

# --------------------------------------------------
# Lista por competência (com ações)
# --------------------------------------------------
st.subheader(f"📋 Lançamentos — {label_competencia(comp_select)}")

lista_mes = mes_itens
if not lista_mes:
    st.info("Nenhum lançamento para este mês.")
else:
    df = pd.DataFrame(lista_mes)
    df["status"] = df.apply(lambda r: derivar_status(r.get("data_prevista"), r.get("data_efetiva")), axis=1)
    df["status_badge"] = df["status"].apply(status_badge)
    df["Data prevista"] = pd.to_datetime(df["data_prevista"], errors="coerce").dt.date
    df["Data efetiva"] = pd.to_datetime(df["data_efetiva"], errors="coerce").dt.date

    show = df[["tipo", "descricao", "valor", "Data prevista", "Data efetiva", "status_badge", "id"]].rename(columns={
        "tipo": "Tipo", "descricao": "Descrição", "valor": "Valor", "status_badge": "Status", "id": "ID"
    }).sort_values("Data prevista", ascending=False)

    st.dataframe(show, use_container_width=True)

    st.markdown("### ✏️ Ações")
    ac1, ac2, ac3, ac4 = st.columns([3,3,3,2])
    id_edit = ac1.text_input("ID para editar")
    id_del = ac2.text_input("ID para excluir")
    id_pagar = ac3.text_input("ID para marcar como pago/recebido")
    executar = ac4.button("Executar")

    if executar:
        alvo_edit = next((x for x in transacoes if x.get("id") == id_edit), None)
        alvo_del = next((x for x in transacoes if x.get("id") == id_del), None)
        alvo_pay = next((x for x in transacoes if x.get("id") == id_pagar), None)

        if alvo_del:
            ok = excluir(transacoes, alvo_del["id"])
            if ok:
                new_sha = gh.put_json("data/transacoes.json", transacoes, f"Exclui {alvo_del['id']}", sha=sha_trans)
                sha_trans = new_sha
                st.cache_data.clear(); st.rerun()
            else:
                st.error("Não foi possível excluir.")
        elif alvo_pay:
            baixar(alvo_pay)
            atualizar(transacoes, alvo_pay)
            new_sha = gh.put_json("data/transacoes.json", transacoes, f"Baixa {alvo_pay['id']}", sha=sha_trans)
            sha_trans = new_sha
            st.cache_data.clear(); st.rerun()
        elif alvo_edit:
            st.markdown(f"#### Editando {alvo_edit.get('id')} — {alvo_edit.get('descricao','')}")
            with st.form("editar_item"):
                e1, e2, e3 = st.columns(3)
                novo_tipo = e1.selectbox("Tipo", ["despesa", "receita"], index=["despesa","receita"].index(alvo_edit.get("tipo","despesa")))
                novo_valor = e2.number_input("Valor (R$)", min_value=0.01, step=0.01, value=float(alvo_edit.get("valor", 0.0)))
                nova_prev = e3.date_input("Data prevista", value=pd.to_datetime(alvo_edit.get("data_prevista")).date() if alvo_edit.get("data_prevista") else date.today())

                e4 = st.text_input("Descrição", value=alvo_edit.get("descricao",""))
                limpar_pagamento = st.checkbox("Estornar (remover pagamento)?", value=False)

                ok_btn = st.form_submit_button("Salvar edição")

            if ok_btn:
                item_editado = alvo_edit.copy()
                item_editado.update({
                    "tipo": novo_tipo,
                    "valor": float(novo_valor),
                    "data_prevista": nova_prev.isoformat(),
                    "descricao": e4.strip(),
                    "data_efetiva": None if limpar_pagamento else alvo_edit.get("data_efetiva"),
                    "atualizado_em": datetime.now().isoformat(),
                })
                atualizar(transacoes, item_editado)
                new_sha = gh.put_json("data/transacoes.json", transacoes, f"Edita {alvo_edit.get('id')}", sha=sha_trans)
                sha_trans = new_sha
                st.cache_data.clear(); st.rerun()
        else:
            st.info("Informe um ID válido para editar, excluir ou pagar.")

st.divider()

# --------------------------------------------------
# 💰 Orçamento mensal por categoria (opcional)
# --------------------------------------------------
st.subheader("💰 Orçamento mensal por categoria")

if not orcamentos:
    st.info("Nenhum orçamento cadastrado em data/orcamentos.json.")
else:
    # mapa nomes categoria
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

