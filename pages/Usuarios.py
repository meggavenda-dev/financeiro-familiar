
# pages/Usuarios.py
import streamlit as st
import pandas as pd

# --------------------------------------------------
# Imports internos
# --------------------------------------------------
from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import novo_id
from services.utils import key_for
from services.layout import responsive_columns, is_mobile
from services.ui import section, card

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Usuários",
    page_icon="👥",
    layout="centered",
    initial_sidebar_state="collapsed",
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
# ➕ Novo usuário
# --------------------------------------------------
section("➕ Cadastrar novo usuário")

with st.form("novo_usuario"):
    cols = responsive_columns(desktop=3, mobile=1)

    nome = cols[0].text_input("Nome")
    perfil = cols[1].selectbox("Perfil", ["admin", "comum"])
    ativo = cols[2].checkbox("Ativo", True)

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
# 🔍 Filtros
# --------------------------------------------------
section("🔍 Filtros")

cols_f = responsive_columns(desktop=3, mobile=1)
filtro_texto = cols_f[0].text_input("Buscar por nome")
filtro_perfil = cols_f[1].selectbox("Perfil", ["todos", "admin", "comum"])
filtro_status = cols_f[2].selectbox("Status", ["todos", "ativos", "inativos"])

# --------------------------------------------------
# Filtragem
# --------------------------------------------------
def filtrar(lista):
    out = []
    for u in lista:
        nome_ok = True
        perfil_ok = True
        status_ok = True

        if filtro_texto:
            nome_ok = filtro_texto.lower() in (u.get("nome", "")).lower()

        if filtro_perfil != "todos":
            perfil_ok = (u.get("perfil") == filtro_perfil)

        if filtro_status == "ativos":
            status_ok = bool(u.get("ativo", True))
        elif filtro_status == "inativos":
            status_ok = not bool(u.get("ativo", True))

        if nome_ok and perfil_ok and status_ok:
            out.append(u)

    return out

filtrados = filtrar(usuarios)

# --------------------------------------------------
# 📚 Lista de usuários
# --------------------------------------------------
section("📚 Usuários cadastrados")

if not filtrados:
    st.info("Nenhum usuário encontrado.")
else:
    # -------------------------------
    # MOBILE — cards com edição inline
    # -------------------------------
    if is_mobile():
        for u in filtrados:
            uid = u.get("id")

            card(
                u.get("nome", "—"),
                [
                    f"Perfil: {'Admin' if u.get('perfil') == 'admin' else 'Comum'}",
                    f"Status: {'Ativo' if bool(u.get('ativo', True)) else 'Inativo'}",
                ],
            )

            cols = responsive_columns(desktop=4, mobile=1)

            novo_nome = cols[0].text_input(
                "Nome",
                value=u.get("nome", ""),
                key=key_for("nome", uid),
            )

            novo_perfil = cols[1].selectbox(
                "Perfil",
                ["admin", "comum"],
                index=0 if u.get("perfil") == "admin" else 1,
                key=key_for("perfil", uid),
            )

            novo_ativo = cols[2].checkbox(
                "Ativo",
                value=bool(u.get("ativo", True)),
                key=key_for("ativo", uid),
            )

            if cols[3].button("💾 Salvar", key=key_for("save", uid)):
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

            if st.button("🗑️ Excluir", key=key_for("del", uid)):
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

            st.divider()

    # -------------------------------
    # DESKTOP — tabela + edição por linha
    # -------------------------------
    else:
        rows = [{
            "ID": u.get("id"),
            "Nome": u.get("nome", ""),
            "Perfil": "Admin" if u.get("perfil") == "admin" else "Comum",
            "Ativo": bool(u.get("ativo", True)),
        } for u in filtrados]

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📤 Exportar CSV",
            data=csv,
            file_name="usuarios.csv",
            mime="text/csv",
        )

        st.divider()
        section("✏️ Editar / Excluir")

        for u in filtrados:
            uid = u.get("id")

            cols = responsive_columns(desktop=4)

            novo_nome = cols[0].text_input(
                "Nome",
                value=u.get("nome", ""),
                key=key_for("nome-d", uid),
            )

            novo_perfil = cols[1].selectbox(
                "Perfil",
                ["admin", "comum"],
                index=0 if u.get("perfil") == "admin" else 1,
                key=key_for("perfil-d", uid),
            )

            novo_ativo = cols[2].checkbox(
                "Ativo",
                value=bool(u.get("ativo", True)),
                key=key_for("ativo-d", uid),
            )

            if cols[3].button("Salvar", key=key_for("save-d", uid)):
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

            # Excluir
            if st.button("Excluir", key=key_for("del-d", uid)):
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
