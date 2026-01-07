
# pages/2_Contas.py
import streamlit as st
from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin

st.set_page_config("Contas", "📅", layout="wide")
st.title("📅 Contas a Pagar / Receber")

ctx = get_context()
require_admin(ctx)
gh = ctx["gh"]

data = load_all((st.secrets["repo_full_name"], st.secrets.get("branch_name", "main")))

pagar = data["data/contas_pagar.json"]["content"]
receber = data["data/contas_receber.json"]["content"]

for label, lista, path in [
    ("A Pagar", pagar, "data/contas_pagar.json"),
    ("A Receber", receber, "data/contas_receber.json"),
]:
    st.subheader(label)
    if not lista:
        st.info(f"Nenhuma conta {label.lower()}.")
        continue

    for c in lista:
        col1, col2, col3 = st.columns([4, 2, 2])
        col1.write(f"**{c['descricao']}**")
        col2.write(f"R$ {c['valor']:.2f}")
        novo = col3.selectbox(
            "Status",
            ["em_aberto", "paga", "atrasada"],
            index=["em_aberto", "paga", "atrasada"].index(c["status"]),
            key=c["id"],
        )
        if novo != c["status"]:
            c["status"] = novo
            gh.put_json(path, lista, f"Update status: {c['descricao']} -> {novo}")
            st.cache_data.clear()
            st.rerun()
