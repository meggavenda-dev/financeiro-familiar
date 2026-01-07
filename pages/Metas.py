
# pages/3_Metas.py
import streamlit as st
from datetime import date
from github_service import GitHubService

st.title("🎯 Metas Financeiras")

gh = GitHubService(
    token=st.secrets["github_token"],
    repo_full_name=st.secrets["repo_full_name"]
)

metas, _ = gh.get_json("data/metas.json", [])

for m in metas:
    progresso = m["valor_acumulado"] / m["valor_meta"]
    meses = max((date.fromisoformat(m["data_meta"]) - date.today()).days // 30, 1)
    aporte = (m["valor_meta"] - m["valor_acumulado"]) / meses

    st.subheader(m["nome"])
    st.progress(min(progresso, 1.0))
    st.write(f"📅 Até {m['data_meta']}")
    st.write(f"💰 Meta: R$ {m['valor_meta']:.2f}")
    st.write(f"📈 Progresso: {progresso*100:.1f}%")
    st.info(f"Sugestão de aporte mensal: **R$ {aporte:.2f}**")
