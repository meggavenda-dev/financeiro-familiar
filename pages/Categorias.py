
# pages/Categorias.py
import streamlit as st
import pandas as pd

from services.app_context import get_config, get_context
from services.data_loader import load_categories
from services.permissions import require_admin
from services.utils import save_json_and_refresh

st.set_page_config(page_title="Categorias", page_icon="🏷️", layout="wide")
st.title("🏷️ Categorias de Receitas e Despesas")

cfg = get_config()
if not cfg.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(cfg)

ctx = get_context()
gh = ctx.get("gh")
cats_map = load_categories((cfg.repo_full_name, cfg.branch_name))
cats = cats_map["content"]
sha = cats_map["sha"]

st.subheader("📚 Editor de categorias")
df = pd.DataFrame(cats)[["id", "nome", "tipo"]].sort_values(["tipo", "nome"])

edited = st.data_editor(
    df,
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    column_config={
        "tipo": st.column_config.SelectboxColumn("Tipo", options=["despesa","receita"]),
    }
)

if st.button("Salvar alterações", type="primary"):
    novos = edited.to_dict(orient="records")
    # validações mínimas
    for c in novos:
        c["id"] = str(c.get("id") or "").strip() or f"cat-{len(novos)}"
        c["nome"] = (c.get("nome") or "").strip()
        if c.get("tipo") not in ("despesa","receita"):
            c["tipo"] = "despesa"
    save_json_and_refresh(gh, "data/categorias.json", novos, "Atualiza categorias (editor)", sha)

st.caption("Dica: use o editor acima para adicionar/alterar/excluir categorias em lote.")
