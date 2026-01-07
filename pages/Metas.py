
# pages/3_Metas.py
import streamlit as st
from datetime import date
from services.app_context import get_context
from services.data_loader import load_all

st.set_page_config("Metas", "🎯", layout="wide")
st.title("🎯 Metas Financeiras")

ctx = get_context()
data = load_all((st.secrets["repo_full_name"], st.secrets.get("branch_name", "main")))

metas = data["data/metas.json"]["content"]

if not metas:
    st.info("Nenhuma meta cadastrada.")
    st.stop()

for m in metas:
    valor_meta = float(m["valor_meta"])
    acumulado = float(m["valor_acumulado"])
    progresso = min(acumulado / valor_meta, 1.0)

    meses = max((date.fromisoformat(m["data_meta"]) - date.today()).days // 30, 1)
    aporte = (valor_meta - acumulado) / meses if acumulado < valor_meta else 0

    st.subheader(m["nome"])
    st.progress(progresso)
    st.write(f"Meta: R$ {valor_meta:,.2f}")
    st.write(f"Acumulado: R$ {acumulado:,.2f}")
    st.write(f"Progresso: {progresso*100:.1f}%")
    st.info(f"Sugestão de aporte mensal: **R$ {aporte:,.2f}**")
