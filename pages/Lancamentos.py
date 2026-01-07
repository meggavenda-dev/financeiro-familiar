
import streamlit as st
from datetime import date, datetime
from services.app_context import get_context
from services.permissions import require_admin
from services.data_loader import load_all

st.title("📝 Lançamentos")

ctx = get_context()
require_admin(ctx)
gh = ctx["gh"]

data = load_all((st.secrets["repo_full_name"], st.secrets.get("branch_name", "main")))
receitas = data["data/receitas.json"]["content"]

with st.form("novo"):
    valor = st.number_input("Valor", min_value=0.01)
    data_l = st.date_input("Data", date.today())
    salvar = st.form_submit_button("Salvar")

if salvar:
    receitas.append({
        "id": f"r-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "data": data_l.isoformat(),
        "valor": valor
    })
    gh.put_json("data/receitas.json", receitas, "Add receita")
    st.success("✅ Receita salva")
    st.cache_data.clear()
    st.rerun()
