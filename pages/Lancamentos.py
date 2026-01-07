
import streamlit as st
from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import *
from datetime import date

ctx = get_context()
require_admin(ctx)
gh = ctx.gh

data = load_all((ctx.repo_full_name, ctx.branch_name))

despesas_map = data["data/despesas.json"]
despesas = despesas_map["content"]
sha = despesas_map["sha"]

st.title("📝 Lançamentos")

with st.form("nova_despesa"):
    valor = st.number_input("Valor", min_value=0.01)
    obs = st.text_input("Observação")
    salvar = st.form_submit_button("Salvar")

if salvar:
    item = {
        "id": novo_id("d"),
        "data": date.today().isoformat(),
        "valor": valor,
        "categoria_id": "cd1",
        "tipo_id": "td1",
        "conta_id": "c1",
        "status": "prevista",
        "recorrente": False,
        "parcelamento": None,
        "excluido": False,
        "observacoes": obs
    }
    criar(despesas, item)
    gh.put_json("data/despesas.json", despesas, "Add despesa", sha=sha)
    st.cache_data.clear()
    st.rerun()

