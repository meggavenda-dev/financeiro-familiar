
# pages/Categorias.py
import streamlit as st
import pandas as pd

# --------------------------------------------------
# Imports internos
# --------------------------------------------------
from services.app_context import init_context, get_context
from services.data_loader import (
    load_all,
    listar_categorias,
    adicionar_categoria,
    atualizar_categoria,
    excluir_categoria,
)
from services.permissions import require_admin
from services.utils import key_for
from services.layout import responsive_columns, is_mobile
from services.ui import section, card

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Categorias",
    page_icon="🏷️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("🏷️ Categorias")

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
load_all((ctx["repo_full_name"], ctx["branch_name"]))

categorias, sha = listar_categorias(gh)
categorias = [c for c in categorias if isinstance(c, dict)]

# --------------------------------------------------
# Próximo código automático
# --------------------------------------------------
codigos = [c.get("codigo") for c in categorias if isinstance(c.get("codigo"), int)]
next_code = max(codigos) + 1 if codigos else 1

# --------------------------------------------------
# Nova categoria
# --------------------------------------------------
section("➕ Nova categoria")

with st.expander("Cadastrar", expanded=True):
    cols = responsive_columns(desktop=3, mobile=1)

    nome = cols[0].text_input("Nome")
    tipo = cols[1].selectbox("Tipo", ["despesa", "receita"])
    codigo = cols[2].number_input(
        "Código (opcional)",
        min_value=1,
        step=1,
        format="%d",
        value=next_code,
    )

    if st.button("Adicionar", type="primary"):
        if not nome.strip():
            st.error("Informe um nome válido.")
        else:
            try:
                nova = adicionar_categoria(
                    gh,
                    nome=nome,
                    tipo=tipo,
                    codigo=int(codigo) if codigo else None,
                )
                st.success(
                    f"Categoria '{nova['nome']}' criada (código {nova['codigo']})."
                )
                st.rerun()
            except Exception as e:
                st.error(str(e))

st.divider()

# --------------------------------------------------
# Filtros
# --------------------------------------------------
section("🔍 Filtros")

cols = responsive_columns(desktop=2, mobile=1)

filtro_texto = cols[0].text_input("Buscar por nome ou código")
filtro_tipo = cols[1].selectbox(
    "Tipo",
    ["todos", "despesa", "receita"],
)

# --------------------------------------------------
# Listagem
# --------------------------------------------------
section("📚 Categorias cadastradas")

df = pd.DataFrame(categorias)
df = df[["codigo", "nome", "tipo", "id"]].sort_values(["tipo", "nome"])

if filtro_texto:
    s = filtro_texto.lower()
    df = df[df.apply(
        lambda r: s in str(r["nome"]).lower() or s in str(r["codigo"]),
        axis=1,
    )]

if filtro_tipo != "todos":
    df = df[df["tipo"] == filtro_tipo]

if df.empty:
    st.info("Nenhuma categoria encontrada.")
else:
    # -------------------------------
    # MOBILE
    # -------------------------------
    if is_mobile():
        for row in df.to_dict(orient="records"):
            cid = row["id"]

            card(
                f"{row['codigo']} — {row['nome']}",
                [f"Tipo: {row['tipo'].capitalize()}"],
            )

            c1, c2 = responsive_columns(desktop=2, mobile=1)

            if c1.button("✏️ Editar", key=key_for("edit", cid)):
                with st.form(key=key_for("form-edit", cid)):
                    nome_e = st.text_input("Nome", value=row["nome"])
                    tipo_e = st.selectbox(
                        "Tipo",
                        ["despesa", "receita"],
                        index=0 if row["tipo"] == "despesa" else 1,
                    )
                    codigo_e = st.number_input(
                        "Código",
                        min_value=1,
                        step=1,
                        value=int(row["codigo"]),
                    )

                    salvar = st.form_submit_button("Salvar")

                if salvar:
                    ok = atualizar_categoria(
                        gh,
                        categoria_id=cid,
                        nome=nome_e,
                        tipo=tipo_e,
                        codigo=int(codigo_e),
                    )
                    if ok:
                        st.success("Categoria atualizada.")
                        st.rerun()
                    else:
                        st.error("Código já existe.")

            if c2.button("🗑️ Excluir", key=key_for("del", cid)):
                if excluir_categoria(gh, cid):
                    st.success("Categoria removida.")
                    st.rerun()
                else:
                    st.error("Falha ao remover.")

            st.divider()

    # -------------------------------
    # DESKTOP
    # -------------------------------
    else:
        for row in df.to_dict(orient="records"):
            cid = row["id"]

            c1, c2, c3, c4, c5 = st.columns([2, 4, 2, 2, 2])
            c1.write(f"**{row['codigo']}**")
            c2.write(row["nome"])
            c3.write("Despesa" if row["tipo"] == "despesa" else "Receita")

            editar = c4.button("✏️ Editar", key=key_for("edit-d", cid))
            excluir = c5.button("🗑️ Excluir", key=key_for("del-d", cid))

            if editar:
                with st.form(key=key_for("form-edit-d", cid)):
                    ec1, ec2, ec3 = st.columns([2, 4, 2])
                    novo_codigo = ec1.number_input(
                        "Código",
                        min_value=1,
                        step=1,
                        value=int(row["codigo"]),
                    )
                    novo_nome = ec2.text_input("Nome", value=row["nome"])
                    novo_tipo = ec3.selectbox(
                        "Tipo",
                        ["despesa", "receita"],
                        index=0 if row["tipo"] == "despesa" else 1,
                    )

                    salvar = st.form_submit_button("Salvar", type="primary")

                if salvar:
                    ok = atualizar_categoria(
                        gh,
                        categoria_id=cid,
                        nome=novo_nome,
                        tipo=novo_tipo,
                        codigo=int(novo_codigo),
                    )
                    if ok:
                        st.success("Categoria atualizada.")
                        st.rerun()
                    else:
                        st.error("Código já existe.")

            if excluir:
                ok = excluir_categoria(gh, cid)
                if ok:
                    st.success("Categoria removida.")
                    st.rerun()
                else:
                    st.error("Falha ao remover.")

st.caption("💡 Dica: use códigos numéricos (ex.: 101 Mercado, 201 Internet).")
