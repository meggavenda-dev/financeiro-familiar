
# pages/Categorias.py
import streamlit as st
import pandas as pd

from services.app_context import init_context, get_context
from services.data_loader import (
    load_all,
    listar_categorias,
    adicionar_categoria,
)
from services.permissions import require_admin

st.set_page_config(page_title="Categorias", page_icon="🏷️", layout="wide")
st.title("🏷️ Categorias de Receitas e Despesas")

# --------------------------------------------------
# Contexto
# --------------------------------------------------
init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)

gh = ctx.get("gh")
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))

# --------------------------------------------------
# Carrega categorias
# --------------------------------------------------
cats, sha = listar_categorias(gh)
cats = [c for c in cats if isinstance(c, dict)]

# --------------------------------------------------
# Nova categoria (compacto)
# --------------------------------------------------
with st.expander("➕ Nova categoria", expanded=True):
    col1, col2, col3 = st.columns([4, 2, 2])
    with col1:
        nome_novo = st.text_input("Nome", placeholder="Ex.: Supermercado, Internet, Salário…", key="novo_nome")
    with col2:
        tipo_novo = st.selectbox("Tipo", ["despesa", "receita"], key="novo_tipo")
    with col3:
        if st.button("Adicionar", type="primary", use_container_width=True):
            if not (nome_novo or "").strip():
                st.error("Informe um nome válido.")
            else:
                nova = adicionar_categoria(gh, nome_novo, tipo_novo)
                st.success(f"Categoria '{nova['nome']}' adicionada.")
                st.rerun()

st.divider()

# --------------------------------------------------
# Filtros
# --------------------------------------------------
st.subheader("🔍 Filtros")
f1, f2, f3 = st.columns([3, 2, 2])
with f1:
    filtro_texto = st.text_input("Buscar por nome", placeholder="Digite parte do nome…")
with f2:
    filtro_tipo = st.selectbox("Tipo", ["todos", "despesa", "receita"], index=0)
with f3:
    ordenar_por = st.selectbox("Ordenar por", ["nome", "tipo"], index=0)

# Aplica filtros
df = pd.DataFrame(cats)
if df.empty:
    st.info("Nenhuma categoria cadastrada.")
    st.stop()

df = df[["id", "nome", "tipo"]].copy()

if filtro_texto:
    df = df[df["nome"].str.contains(filtro_texto, case=False, na=False)]

if filtro_tipo != "todos":
    df = df[df["tipo"] == filtro_tipo]

df = df.sort_values(by=[ordenar_por, "nome"]).reset_index(drop=True)

# --------------------------------------------------
# Lista compacta com edição inline
# --------------------------------------------------
st.subheader("📚 Lista (editar por linha)")
st.caption("Dica: edite diretamente na tabela e clique em **Salvar alterações** para persistir.")

# Configuração do editor
col_config = {
    "id": st.column_config.TextColumn("ID", disabled=True, help="Identificador interno"),
    "nome": st.column_config.TextColumn("Nome", help="Nome da categoria"),
    "tipo": st.column_config.SelectboxColumn(
        "Tipo", options=["despesa", "receita"], help="Classificação da categoria"
    ),
}

edited_df = st.data_editor(
    df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config=col_config,
    key="cats_editor",
)

# Detecta mudanças comparando com df original
mudou = not edited_df.equals(df)

btns = st.columns([2, 2, 6])
salvar_alteracoes = btns[0].button("💾 Salvar alterações", type="primary", disabled=not mudou)
st.caption("Selecione linhas para excluir em massa.")

# Seleção de linhas para exclusão
selected_rows = st.dataframe(
    edited_df,
    use_container_width=True,
    hide_index=True
)  # apenas visual extra (opcional)

# Para exclusão em massa com IDs, pedimos a lista de IDs selecionados
ids_para_excluir = st.text_input(
    "IDs para excluir (separe por vírgula)",
    placeholder="Ex.: cat-202501011200-1a2b, cat-202501011205-3c4d",
    help="Copie os IDs das linhas que deseja excluir e cole aqui."
)
excluir_em_massa = btns[1].button("🗑️ Excluir selecionados")

# --------------------------------------------------
# Persistência: salvar alterações
# --------------------------------------------------
if salvar_alteracoes:
    # Constrói mapa por ID e aplica mudanças de edited_df no array original
    original = cats[:]  # lista de dicts
    edited_records = edited_df.to_dict(orient="records")
    by_id = {c["id"]: c for c in original}

    # Validação básica: nome não vazio, tipo válido
    for r in edited_records:
        if not (r.get("nome") or "").strip():
            st.error(f"Nome inválido para ID {r.get('id')}. Operação abortada.")
            st.stop()
        if r.get("tipo") not in ("despesa", "receita"):
            st.error(f"Tipo inválido para ID {r.get('id')}. Operação abortada.")
            st.stop()

    # Aplica alterações
    for r in edited_records:
        if r["id"] in by_id:
            by_id[r["id"]]["nome"] = r["nome"].strip()
            by_id[r["id"]]["tipo"] = r["tipo"]

    # Persiste
    novos_cats = list(by_id.values())
    new_sha = gh.put_json("data/categorias.json", novos_cats, "Atualiza categorias (edição em lote)", sha=sha)
    st.cache_data.clear()
    st.success("Alterações salvas com sucesso.")
    st.rerun()

# --------------------------------------------------
# Exclusão em massa
# --------------------------------------------------
if excluir_em_massa:
    ids = [x.strip() for x in (ids_para_excluir or "").split(",") if x.strip()]
    if not ids:
        st.warning("Informe ao menos um ID válido, separado por vírgula.")
    else:
        # Filtra removendo IDs informados
        remaining = [c for c in cats if c.get("id") not in ids]
        if len(remaining) == len(cats):
            st.info("Nenhum ID informado foi encontrado. Nada a excluir.")
        else:
            gh.put_json("data/categorias.json", remaining, f"Remove categorias em massa: {', '.join(ids)}", sha=sha)
            st.cache_data.clear()
            st.success(f"Removidas {len(cats) - len(remaining)} categorias.")
            st.rerun()

st.divider()
st.caption("Mantenha nomes claros e consistentes para facilitar relatórios.")
