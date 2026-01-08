
# pages/Orcamentos.py
import streamlit as st
import pandas as pd

from services.app_context import init_context, get_context
from services.data_loader import load_all, listar_categorias
from services.permissions import require_admin
from services.utils import fmt_brl

st.set_page_config(page_title="Orçamentos", page_icon="📊", layout="wide")
st.title("📊 Orçamentos por Categoria")

# Contexto
init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)

gh = ctx.get("gh")
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

orc_map = data.get("data/orcamentos.json", {"content": [], "sha": None})
orcamentos = [o for o in orc_map.get("content", []) if isinstance(o, dict)]
sha = orc_map.get("sha")

cats, _ = listar_categorias(gh)
cat_map = {c["id"]: c["nome"] for c in cats}

# Criar novo orçamento
st.subheader("➕ Cadastrar orçamento")
with st.form("novo_orc"):
    col1, col2 = st.columns([3,2])
    categoria_nome = col1.selectbox("Categoria", options=list(cat_map.values()))
    limite = col2.number_input("Limite mensal (R$)", min_value=0.01, step=0.01)
    salvar_btn = st.form_submit_button("Salvar")
    if salvar_btn:
        inv_cat = {v:k for k,v in cat_map.items()}
        orcamentos.append({
            "id": f"o-{len(orcamentos)+1}",
            "categoria_id": inv_cat.get(categoria_nome),
            "limite_mensal": float(limite),
            "ativo": True,
        })
        gh.put_json("data/orcamentos.json", orcamentos, "Novo orçamento", sha=sha)
        st.cache_data.clear()
        st.success("Orçamento cadastrado.")
        st.rerun()

st.divider()
st.subheader("📚 Orçamentos cadastrados")
if not orcamentos:
    st.info("Nenhum orçamento cadastrado.")
else:
    rows = []
    for o in orcamentos:
        rows.append({
            "ID": o.get("id"),
            "Categoria": cat_map.get(o.get("categoria_id"), o.get("categoria_id")),
            "Limite Mensal": fmt_brl(o.get("limite_mensal", 0.0)),
            "Ativo": bool(o.get("ativo", True)),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.divider()
st.subheader("✏️ Editar / Excluir")
for o in orcamentos:
    c1, c2, c3, c4 = st.columns([4,2,2,2])
    with c1:
        cat_atual = cat_map.get(o.get("categoria_id"), "—")
        idx = list(cat_map.values()).index(cat_atual) if cat_atual in cat_map.values() else 0
        novo_cat = st.selectbox("Categoria", options=list(cat_map.values()), index=idx, key=f"orc-cat-{o['id']}")
    with c2:
        novo_lim = st.number_input("Limite (R$)", min_value=0.01, step=0.01, value=float(o.get("limite_mensal", 0.0)), key=f"orc-lim-{o['id']}")
    with c3:
        novo_ativo = st.checkbox("Ativo", value=bool(o.get("ativo", True)), key=f"orc-ativo-{o['id']}")
    with c4:
        if st.button("Salvar", key=f"orc-save-{o['id']}"):
            inv_cat = {v:k for k,v in cat_map.items()}
            o["categoria_id"] = inv_cat.get(novo_cat, o.get("categoria_id"))
            o["limite_mensal"] = float(novo_lim)
            o["ativo"] = bool(novo_ativo)
            gh.put_json("data/orcamentos.json", orcamentos, f"Atualiza orçamento {o['id']}", sha=sha)
            st.cache_data.clear()
            st.success("Orçamento atualizado.")
            st.rerun()
        if st.button("Excluir", key=f"orc-del-{o['id']}"):
            orcamentos = [x for x in orcamentos if x.get("id") != o["id"]]
            gh.put_json("data/orcamentos.json", orcamentos, f"Remove orçamento {o['id']}", sha=sha)
            st.cache_data.clear()
            st.success("Orçamento removido.")
            st.rerun()
