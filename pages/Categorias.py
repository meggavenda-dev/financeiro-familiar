# pages/Categorias.py
import streamlit as st
import pandas as pd

from services.app_context import get_context
from services.data_loader import load_all, listar_categorias, adicionar_categoria, atualizar_categoria, excluir_categoria
from services.permissions import require_admin

st.set_page_config(page_title="Categorias", page_icon="🏷️", layout="wide")
st.title("🏷️ Categorias de Receitas e Despesas")

from services.app_context import init_context, get_context

init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)

gh = ctx.get("gh")
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

# Form de criação
st.subheader("➕ Adicionar nova categoria")
col1, col2, col3 = st.columns([3,2,1])
with col1:
    nome = st.text_input("Nome da categoria", placeholder="Ex.: Internet, Academia, Bônus...")
with col2:
    tipo = st.selectbox("Tipo", ["despesa", "receita"])
with col3:
    if st.button("Adicionar", type="primary"):
        if not (nome or "").strip():
            st.error("Informe um nome válido.")
        else:
            nova = adicionar_categoria(gh, nome, tipo)
            st.success(f"Categoria '{nova['nome']}' adicionada.")
            st.rerun()

st.divider()
st.subheader("📚 Lista de categorias")

cats, sha = listar_categorias(gh)
if not cats:
    st.info("Nenhuma categoria cadastrada.")
    st.stop()

df = pd.DataFrame(cats)
df = df[["id", "nome", "tipo"]].sort_values(["tipo", "nome"])
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("✏️ Editar / Excluir")

for c in df.to_dict(orient="records"):
    col1, col2, col3, col4 = st.columns([4,2,2,2])
    with col1:
        novo_nome = st.text_input("Nome", value=c["nome"], key=f"nome-{c['id']}")
    with col2:
        novo_tipo = st.selectbox("Tipo", ["despesa", "receita"], index=0 if c["tipo"]=="despesa" else 1, key=f"tipo-{c['id']}")
    with col3:
        if st.button("Salvar alterações", key=f"salvar-{c['id']}"):
            ok = atualizar_categoria(gh, c["id"], novo_nome, novo_tipo)
            if ok:
                st.success(f"Categoria '{novo_nome}' atualizada.")
                st.rerun()
            else:
                st.error("Falha ao atualizar.")
    with col4:
        if st.button("Excluir", key=f"excluir-{c['id']}"):
            ok = excluir_categoria(gh, c["id"])
            if ok:
                st.success(f"Categoria '{c['nome']}' removida.")
                st.rerun()
            else:
                st.error("Falha ao remover.")

st.caption("Dica: mantenha os nomes claros e consistentes para facilitar relatórios.")
