
# pages/Usuarios.py
import streamlit as st

from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import novo_id
from services.utils import key_for  # CHANGE

st.set_page_config(
    page_title="Usuários",
    page_icon="👥",
    layout="wide",
)
st.title("👥 Usuários")

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
usuario_atual = ctx.get("usuario_id", "u1")

# --------------------------------------------------
# Carregamento
# --------------------------------------------------
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))
usuarios_map = data.get("data/usuarios.json", {"content": [], "sha": None})

usuarios = [u for u in usuarios_map.get("content", []) if isinstance(u, dict)]
sha = usuarios_map.get("sha")

# --------------------------------------------------
# Novo usuário
# --------------------------------------------------
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
            usuarios.append({
                "id": novo_id("u"),
                "nome": nome.strip(),
                "perfil": perfil,
                "ativo": bool(ativo),
            })
            gh.put_json(
                "data/usuarios.json",
                usuarios,
                f"[{usuario_atual}] Cria usuário",
                sha=sha,
            )
            st.cache_data.clear()
            st.success(f"Usuário '{nome}' adicionado.")
            st.rerun()

st.divider()

# --------------------------------------------------
# Lista de usuários
# --------------------------------------------------
st.subheader("📚 Lista de usuários")

if not usuarios:
    st.info("Nenhum usuário cadastrado.")
    st.stop()

for u in usuarios:
    uid = u.get("id")

    c1, c2, c3, c4 = st.columns([4, 2, 2, 2])

    with c1:
        novo_nome = st.text_input(
            "Nome",
            value=u.get("nome", ""),
            key=key_for("nome", uid),
        )

    with c2:
        novo_perfil = st.selectbox(
            "Perfil",
            ["admin", "comum"],
            index=0 if u.get("perfil") == "admin" else 1,
            key=key_for("perfil", uid),
        )

    with c3:
        novo_ativo = st.checkbox(
            "Ativo",
            value=bool(u.get("ativo", True)),
            key=key_for("ativo", uid),
        )

    with c4:
        if st.button("Salvar", key=key_for("save", uid)):
            changed = False

            if u.get("nome") != (novo_nome or "").strip():
                u["nome"] = (novo_nome or "").strip()
                changed = True

            if u.get("perfil") != novo_perfil:
                u["perfil"] = novo_perfil
                changed = True

            if bool(u.get("ativo", True)) != bool(novo_ativo):
                u["ativo"] = bool(novo_ativo)
                changed = True

            if changed:
                gh.put_json(
                    "data/usuarios.json",
                    usuarios,
                    f"[{usuario_atual}] Atualiza usuário {uid}",
                    sha=sha,
                )
                st.cache_data.clear()
                st.success("Alterações salvas.")
                st.rerun()
            else:
                st.info("Nenhuma alteração detectada.")

        if st.button("Excluir", key=key_for("del", uid)):
            usuarios = [x for x in usuarios if x.get("id") != uid]
            gh.put_json(
                "data/usuarios.json",
                usuarios,
                f"[{usuario_atual}] Remove usuário {uid}",
                sha=sha,
            )
            st.cache_data.clear()
            st.success("Usuário removido.")
            st.rerun()
