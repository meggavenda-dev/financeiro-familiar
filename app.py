
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from services.app_context import get_context
from services.data_loader import load_all

st.set_page_config("Financeiro Familiar", "💰", layout="wide")
st.title("💰 Financeiro Familiar")

ctx = get_context()

with st.sidebar:
    st.subheader("👤 Usuário")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil")

    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()

data = load_all((st.secrets["repo_full_name"], st.secrets.get("branch_name", "main")))

receitas = data["data/receitas.json"]["content"]
despesas = data["data/despesas.json"]["content"]

df_r = pd.DataFrame(receitas)
df_d = pd.DataFrame(despesas)

total_r = df_r["valor"].sum() if not df_r.empty else 0
total_d = df_d["valor"].sum() if not df_d.empty else 0

c1, c2, c3 = st.columns(3)
c1.metric("Receitas", f"R$ {total_r:,.2f}")
c2.metric("Despesas", f"R$ {total_d:,.2f}")
c3.metric("Saldo", f"R$ {total_r-total_d:,.2f}")

st.success("✅ Dashboard integrado aos módulos")
