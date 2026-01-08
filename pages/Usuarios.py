
# pages/Usuarios.py
import streamlit as st
from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import novo_id

st.set_page_config(page_title="Usuários", page_icon="👥", layout="wide")
st.title("👥 Usuários")

init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)

gh = ctx.get("gh")
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))
usuarios_map = data.get("data/usuarios.json", {"content": [], "sha": None})
usuarios = [u for u in usuarios_map.get("content", []) if isinstance(u, dict)]
sha = usuarios_map.get("sha")

st.subheader("➕ Cadastrar novo usuário")
with st.form("novo_usuario"):
    nome = st.text_input("Nome")
    perfil = st.selectbox("Perfil", ["admin", "comum"])
    ativo = st.checkbox("Ativo", True)
    salvar = st.form_submit_button("Salvar")
    if salvar:
        if not (nome or "").strip():
            st.error("Informe um nome válido.")
        else:
            usuarios.append({"id": novo_id("u"), "nome": nome.strip(), "perfil": perfil, "ativo": ativo})
            gh.put_json("data/usuarios.json", usuarios, "Novo usuário", sha=sha)
            st.cache_data.clear()
            st.success(f"Usuário '{nome}' adicionado.")
            st.rerun()

st.divider()
st.subheader("📚 Lista de usuários")
if not usuarios:
    st.info("Nenhum usuário cadastrado.")
    st.stop()

for u in usuarios:
    col1, col2, col3, col4 = st.columns([4,2,2,2])
    with col1:
        novo_nome = st.text_input("Nome", value=u.get("nome",""), key=f"u-nome-{u['id']}")
    with col2:
        novo_perfil = st.selectbox("Perfil", ["admin", "comum"], index=0 if u.get("perfil")=="admin" else 1, key=f"u-perfil-{u['id']}")
    with col3:
        novo_ativo = st.checkbox("Ativo", value=bool(u.get("ativo", True)), key=f"u-ativo-{u['id']}")
    with col4:
        if st.button("Salvar", key=f"u-salvar-{u['id']}"):
            u["nome"] = (novo_nome or "").strip()
            u["perfil"] = novo_perfil
            u["ativo"] = bool(novo_ativo)
            gh.put_json("data/usuarios.json", usuarios, f"Atualiza usuário: {u['id']}", sha=sha)
            st.cache_data.clear()
            st.success("Alterações salvas.")
            st.rerun()
        if st.button("Excluir", key=f"u-excluir-{u['id']}"):
            usuarios = [x for x in usuarios if x.get("id") != u["id"]]
            gh.put_json("data/usuarios.json", usuarios, f"Remove usuário: {u['id']}", sha=sha)
            st.cache_data.clear()
            st.success("Usuário removido.")
            st.rerun()
