
# pages/Categorias.py
import streamlit as st
import pandas as pd

from services.app_context import init_context, get_context
from services.data_loader import (
    load_all,
    listar_categorias,
    adicionar_categoria,
    atualizar_categoria,
    excluir_categoria,
)
from services.permissions import require_admin
from services.utils import key_for  # CHANGE

st.set_page_config(
    page_title="Categorias",
    page_icon="🏷️",
    layout="wide",
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

cats, sha = listar_categorias(gh)
cats = [c for c in cats if isinstance(c, dict)]

# --------------------------------------------------
# CHANGE: garantir códigos apenas se necessário
# --------------------------------------------------
existing = {c.get("codigo") for c in cats if isinstance(c.get("codigo"), int)}
next_code = max(existing) + 1 if existing else 1

changed = False
for c in cats:
    if not isinstance(c.get("codigo"), int):
        c["codigo"] = next_code
        next_code += 1
        changed = True

if changed:
    gh.put_json(
        "data/categorias.json",
        cats,
        f"[{usuario}] Normaliza código numérico",
        sha=sha,
    )
    st.cache_data.clear()

# --------------------------------------------------
# Nova categoria
# --------------------------------------------------
with st.expander("➕ Nova categoria", expanded=True):
    col1, col2, col3 = st.columns([4, 2, 2])

    nome = col1.text_input("Nome")
    tipo = col2.selectbox("Tipo", ["despesa", "receita"])
    codigo = col3.number_input(
        "Código (opcional)",
        min_value=1,
        step=1,
        format="%d",
    )

    if st.button("Adicionar", type="primary"):
        if not (nome or "").strip():
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
                    f"Categoria '{nova['nome']}' adicionada (código {nova['codigo']})."
                )
                st.rerun()
            except Exception as e:
                st.error(str(e))

st.divider()

# --------------------------------------------------
# Filtros
# --------------------------------------------------
f1, f2 = st.columns([3, 2])
filtro_texto = f1.text_input("Buscar por nome ou código")
filtro_tipo = f2.selectbox("Tipo", ["todos", "despesa", "receita"])

df = pd.DataFrame(cats)
df = df[["codigo", "nome", "tipo", "id"]].sort_values(["tipo", "nome"])

if filtro_texto:
    s = filtro_texto.lower()
    df = df[df.apply(
        lambda r: s in str(r["nome"]).lower() or s in str(r["codigo"]),
        axis=1,
    )]

if filtro_tipo != "todos":
    df = df[df["tipo"] == filtro_tipo]

# --------------------------------------------------
# Lista
# --------------------------------------------------
st.subheader("📚 Categorias")

if df.empty:
    st.info("Nenhuma categoria encontrada.")
else:
    for row in df.to_dict(orient="records"):
        cid = row["id"]

        c1, c2, c3, c4, c5 = st.columns([2, 4, 2, 2, 2])

        c1.write(f"**{row['codigo']}**")
        c2.write(row["nome"])
        c3.write("Despesa" if row["tipo"] == "despesa" else "Receita")

        editar = c4.button("✏️ Editar", key=key_for("edit", cid))
        excluir = c5.button("🗑️ Excluir", key=key_for("del", cid))

        if editar:
            with st.form(key_for("form-edit", cid)):
                e1, e2, e3 = st.columns([2, 4, 2])

                novo_codigo = e1.number_input(
                    "Código",
                    min_value=1,
                    step=1,
                    format="%d",
                    value=int(row["codigo"]),
                )
                novo_nome = e2.text_input("Nome", value=row["nome"])
                novo_tipo = e3.selectbox(
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
                    st.error("Código já existe em outra categoria.")

        if excluir:
            ok = excluir_categoria(gh, cid)
            if ok:
                st.success("Categoria removida.")
                st.rerun()
            else:
                st.error("Falha ao remover categoria.")

st.caption(
    "💡 Dica: utilize códigos numéricos (ex.: 101 Supermercado, 201 Internet)."
)
