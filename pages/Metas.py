
# pages/3_Metas.py
import streamlit as st
from datetime import date
from services.app_context import get_context
from services.data_loader import load_all

st.set_page_config(page_title="Metas", page_icon="🎯", layout="wide")
st.title("🎯 Metas Financeiras")

ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

data = load_all((ctx.repo_full_name, ctx.branch_name))
metas = data["data/metas.json"]["content"]

if not metas:
    st.info("Nenhuma meta cadastrada.")
    st.stop()

for m in metas:
    valor_meta = float(m.get("valor_meta", 0.0))
    acumulado = float(m.get("valor_acumulado", 0.0))
    progresso = min(acumulado / valor_meta, 1.0) if valor_meta > 0 else 0.0

    try:
        meses = max((date.fromisoformat(m["data_meta"]) - date.today()).days // 30, 1)
    except Exception:
        meses = 1
    aporte = (valor_meta - acumulado) / meses if acumulado < valor_meta else 0.0

    st.subheader(m.get("nome", "Meta"))
    st.progress(progresso)
    st.write(f"Meta: R$ {valor_meta:,.2f}")
    st.write(f"Acumulado: R$ {acumulado:,.2f}")
    st.write(f"Progresso: {progresso*100:.1f}%")
    st.info(f"Sugestão de aporte mensal: **R$ {aporte:,.2f}**")
