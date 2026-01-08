
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

st.set_page_config(page_title="Categorias", page_icon="🏷️", layout="wide")
st.title("🏷️ Categorias")

# ---------------- Contexto ----------------
init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)

gh = ctx.get("gh")
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

# ---------------- Dados ----------------
cats, sha = listar_categorias(gh)
cats = [c for c in cats if isinstance(c, dict)]

# Garantir que todas têm 'codigo' numérico (auto-preencher ao carregar)
existing_codes = {c.get("codigo") for c in cats if isinstance(c.get("codigo"), int)}
next_code = (max(existing_codes) + 1) if existing_codes else 1
for c in cats:
    if c.get("codigo") is None or not isinstance(c.get("codigo"), int):
        c["codigo"] = next_code
        next_code += 1
# Persistir caso tenha sido gerado código
gh.put_json("data/categorias.json", cats, "Garantir campo 'codigo' (numérico)", sha=sha)
st.cache_data.clear()

# ---------------- Nova categoria ----------------
with st.expander("➕ Nova categoria", expanded=True):
    c1, c2, c3 = st.columns([4, 2, 2])
    with c1:
        nome_novo = st.text_input("Nome", placeholder="Ex.: Supermercado, Internet, Salário…")
    with c2:
        tipo_novo = st.selectbox("Tipo", ["despesa", "receita"])
    with c3:
        codigo_novo = st.number_input("Código (opcional)", min_value=1, step=1, format="%d")

    if st.button("Adicionar", type="primary"):
        if not (nome_novo or "").strip():
            st.error("Informe um nome válido.")
        else:
            nova = adicionar_categoria(gh, nome_novo, tipo_novo, codigo=int(codigo_novo) if codigo_novo else None)
            st.success(f"Categoria '{nova['nome']}' adicionada (código {nova['codigo']}).")
            st.rerun()

st.divider()

# ---------------- Filtros ----------------
f1, f2 = st.columns([3, 2])
filtro_texto = f1.text_input("Buscar por nome/código")
filtro_tipo = f2.selectbox("Tipo", ["todos", "despesa", "receita"], index=0)

df = pd.DataFrame(cats)
df = df[["codigo", "nome", "tipo", "id"]].sort_values(["tipo", "nome"]).reset_index(drop=True)

if filtro_texto:
    s = filtro_texto.strip().lower()
    df = df[df.apply(lambda r: s in str(r["nome"]).lower() or s in str(r["codigo"]), axis=1)]

if filtro_tipo != "todos":
    df = df[df["tipo"] == filtro_tipo]

# ---------------- Lista compacta com ações ----------------
st.subheader("📚 Categorias")
if df.empty:
    st.info("Nenhuma categoria encontrada com os filtros atuais.")
else:
    for row in df.to_dict(orient="records"):
        cid = row["id"]
        codigo = row["codigo"]
        nome = row["nome"]
        tipo = row["tipo"]

        col1, col2, col3, col4, col5 = st.columns([2, 4, 2, 2, 2])
        col1.write(f"**{codigo}**")
        col2.write(nome)
        col3.write("Despesa" if tipo == "despesa" else "Receita")

        # Editar
        editar = col4.button("✏️ Editar", key=f"edit-{cid}")
        excluir = col5.button("🗑️ Excluir", key=f"del-{cid}")

        if editar:
            with st.form(f"form-edit-{cid}", clear_on_submit=False):
                e1, e2, e3 = st.columns([2, 4, 2])
                novo_codigo = e1.number_input("Código", min_value=1, step=1, format="%d", value=int(codigo))
                novo_nome = e2.text_input("Nome", value=nome)
                novo_tipo = e3.selectbox("Tipo", ["despesa", "receita"], index=0 if tipo == "despesa" else 1)
                salvar_ed = st.form_submit_button("Salvar alterações", type="primary")

            if salvar_ed:
                # validar código único
                if any(c for c in cats if c.get("id") != cid and c.get("codigo") == int(novo_codigo)):
                    st.error(f"Código {novo_codigo} já existe em outra categoria.")
                elif not (novo_nome or "").strip():
                    st.error("Nome inválido.")
                else:
                    ok = atualizar_categoria(gh, categoria_id=cid, nome=novo_nome, tipo=novo_tipo, codigo=int(novo_codigo))
                    if ok:
                        st.success("Categoria atualizada.")
                        st.rerun()
                    else:
                        st.error("Falha ao atualizar.")

        if excluir:
            ok = excluir_categoria(gh, cid)
            if ok:
                st.success(f"Categoria '{nome}' removida.")
                st.rerun()
            else:
                st.error("Falha ao remover.")

st.caption("Dica: use códigos numéricos para facilitar a identificação rápida. Ex.: 101 Supermercado, 201 Internet.")
