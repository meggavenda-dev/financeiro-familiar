
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

# -------------------- helpers locais --------------------
def _parse_br_date_or_error(raw: str) -> date | None:
    """Converte 'dd/mm/aaaa' para date. Retorna None se inválido."""
    try:
        return datetime.strptime((raw or "").strip(), "%d/%m/%Y").date()
    except Exception:
        return None

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
transacoes = [t for t in (normalizar_tx(x) for x in trans_map["content"]) if t is not None]
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
colf1, colf2, colf3, colf4 = st.columns([2, 2, 2, 2])
comp_select = colf1.selectbox("Competência (mês)", options=competencias, format_func=label_competencia, index=0)
busca_texto = colf2.text_input("Buscar por descrição/código")
somente_em_aberto = colf3.checkbox("Somente em aberto (não pagas)", value=False)
tipo_filter = colf4.selectbox("Tipo", ["todos", "despesa", "receita"], index=0)

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
# Resumo Mensal (por tipo e status)
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

total_rec = soma_por_tipo_e_status(mes_itens, tipo="receita", status=None)
total_des = soma_por_tipo_e_status(mes_itens, tipo="despesa", status=None)
rec_pagas = soma_por_tipo_e_status(mes_itens, tipo="receita", status="paga")
des_pagas = soma_por_tipo_e_status(mes_itens, tipo="despesa", status="paga")
rec_abertas = total_rec - rec_pagas
des_abertas = total_des - des_pagas
rec_vencidas = soma_por_tipo_e_status(mes_itens, tipo="receita", status="vencida")
des_vencidas = soma_por_tipo_e_status(mes_itens, tipo="despesa", status="vencida")

l1c1, l1c2 = st.columns(2)
l1c1.metric("📥 Receitas pagas (mês)", fmt_brl(rec_pagas))
l1c2.metric("💸 Despesas pagas (mês)", fmt_brl(des_pagas))

l2c1, l2c2 = st.columns(2)
l2c1.metric("📥 Receitas em aberto (mês)", fmt_brl(rec_abertas))
l2c2.metric("💸 Despesas em aberto (mês)", fmt_brl(des_abertas))

l3c1, l3c2 = st.columns(2)
l3c1.metric("📥 Receitas vencidas (mês)", fmt_brl(rec_vencidas))
l3c2.metric("💸 Despesas vencidas (mês)", fmt_brl(des_vencidas))

st.divider()

# --------------------------------------------------
# Cadastro — novo / parcelado (data BR texto + validação)
# --------------------------------------------------
st.subheader("➕ Nova transação")
cat_map = cat_opts()
conta_map = conta_opts()

with st.form("nova_tx"):
    c1, c2, c3, c4 = st.columns([2, 1, 2, 2])
    tipo = c1.selectbox("Tipo", ["despesa", "receita"])
    valor = c2.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_prev_br_str = c3.text_input("Data prevista (dd/mm/aaaa)", value=fmt_date_br(date.today()))
    c3.caption("Use o formato **dd/mm/aaaa** (ex.: 08/01/2026)")
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
    data_prev_dt = _parse_br_date_or_error(data_prev_br_str)
    if not data_prev_dt:
        st.error("Data prevista inválida. Use dd/mm/aaaa.")
    else:
        inv_cat = {v: k for k, v in cat_map.items()}
        inv_conta = {v: k for k, v in conta_map.items()}
        existing_codes = [t.get("codigo") for t in transacoes if isinstance(t.get("codigo"), int)]
        next_code = (max(existing_codes) + 1) if existing_codes else 1

        base = {
            "id": novo_id("tx"),
            "codigo": next_code,
            "tipo": tipo,
            "descricao": (descricao or "").strip(),
            "valor": float(valor),
            "data_prevista": data_prev_dt.isoformat(),
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
# Lista por competência — tabela compacta com Código + ações por linha
# --------------------------------------------------
st.subheader(f"📋 Lançamentos — {label_competencia(comp_select)}")

lista_mes = mes_itens
if not lista_mes:
    st.info("Nenhum lançamento para este mês.")
else:
    df = pd.DataFrame(lista_mes)

    df["status"] = df.apply(lambda r: derivar_status(r.get("data_prevista"), r.get("data_efetiva")), axis=1)
    df["Status"] = df["status"].apply(status_badge)

    df["Prevista (BR)"] = df["data_prevista"].apply(lambda x: fmt_date_br(x))
    df["Efetiva (BR)"] = df["data_efetiva"].apply(lambda x: fmt_date_br(x))

    conta_map_rev = {c.get("id"): c.get("nome") for c in contas}
    cat_map_rev = {c.get("id"): c.get("nome") for c in categorias}
    df["Conta"] = df["conta_id"].map(conta_map_rev).fillna(df["conta_id"])
    df["Categoria"] = df["categoria_id"].map(cat_map_rev).fillna(df["categoria_id"])
    df["Tipo"] = df["tipo"].map({"despesa": "💸 Despesa", "receita": "📥 Receita"}).fillna(df["tipo"])

    df["_sort_prev"] = pd.to_datetime(df["data_prevista"], errors="coerce")
    df = df.rename(columns={"descricao": "Descrição"})
    show_cols = ["codigo", "Tipo", "Descrição", "valor", "Prevista (BR)", "Efetiva (BR)", "Status", "Conta", "Categoria", "id"]
    show_df = df[show_cols].sort_values(["_sort_prev", "codigo"], ascending=[False, True]).drop(columns=["id"]).reset_index(drop=True)

    # Exportar CSV dos itens filtrados
    csv_bytes = show_df.to_csv(index=False).encode("utf-8")
    st.download_button("📤 Exportar CSV (filtros aplicados)", data=csv_bytes, file_name=f"lancamentos_{comp_select}.csv", mime="text/csv")

    st.dataframe(show_df, use_container_width=True, hide_index=True)

    st.markdown("### ✏️ Ações por linha")
    for row in df.sort_values(["_sort_prev", "codigo"], ascending=[False, True]).to_dict(orient="records"):
        r_id = row["id"]
        r_code = row.get("codigo")
        alvo = next((x for x in transacoes if x.get("id") == r_id), None)
        if not alvo:
            continue

        c1, c2, c3, c4, c5 = st.columns([2, 4, 2, 2, 3])
        c1.write(f"**{r_code}**")
        c2.write(f"{row['Descrição']}")
        c3.write(fmt_brl(float(row["valor"])))
        c4.write(row["Status"])
        pagar_btn = c5.button("Marcar como paga/recebida", key=f"pay-{r_id}", disabled=("✅" in row["Status"]))

        editar_exp = st.expander(f"Editar — {r_code}", expanded=False)
        excluir_btn = st.button("Excluir", key=f"del-{r_id}")

        if pagar_btn:
            baixar(alvo)
            atualizar(transacoes, alvo)
            gh.put_json("data/transacoes.json", transacoes, f"Baixa {r_id}", sha=sha_trans)
            clear_cache_and_rerun()

        with editar_exp:
            with st.form(f"edit-{r_id}"):
                e1, e2 = st.columns([2, 2])
                novo_tipo = e1.selectbox("Tipo", ["despesa", "receita"], index=["despesa", "receita"].index(alvo.get("tipo", "despesa")))
                novo_valor = e2.number_input("Valor (R$)", min_value=0.01, step=0.01, value=float(alvo.get("valor", 0.0)))

                prev_str = fmt_date_br(alvo.get("data_prevista"))
                nova_prev_str = st.text_input("Data prevista (dd/mm/aaaa)", value=prev_str, key=f"edit-prev-{r_id}")
                st.caption("Use o formato **dd/mm/aaaa**")

                e4 = st.text_input("Descrição", value=alvo.get("descricao", ""), key=f"edit-desc-{r_id}")
                limpar_pagamento = st.checkbox("Estornar (remover pagamento)?", value=False, key=f"edit-estornar-{r_id}")

                ok_btn = st.form_submit_button("Salvar edição", type="primary")

            if ok_btn:
                nova_prev_dt = _parse_br_date_or_error(nova_prev_str)
                if not nova_prev_dt:
                    st.error("Data prevista inválida (dd/mm/aaaa).")
                else:
                    item_editado = alvo.copy()
                    item_editado.update({
                        "tipo": novo_tipo,
                        "valor": float(novo_valor),
                        "data_prevista": nova_prev_dt.isoformat(),
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

