
import streamlit as st
from services.app_context import init_context, get_context
from services.data_loader import load_all

st.set_page_config(page_title="Financeiro Familiar", page_icon="💰", layout="wide")
st.title("💰 Financeiro Familiar")
st.caption("SaaS de finanças pessoais com fluxo unificado de transações")

init_context()
ctx = get_context()

with st.sidebar:
    st.header("🔧 Conexão")
    st.text_input("Repositório (owner/repo)", key="repo_full_name", value=ctx.repo_full_name or "")
    st.text_input("GitHub Token", key="github_token", type="password", value=ctx.github_token or "")
    st.text_input("Branch", key="branch_name", value=ctx.branch_name or "main")
    if st.button("Conectar"):
        from github_service import GitHubService
        try:
            ctx.gh = GitHubService(
                token=st.session_state.github_token,
                repo_full_name=st.session_state.repo_full_name,
                branch=st.session_state.branch_name,
            )
            ctx.connected = True
            st.cache_data.clear()
            st.success("✅ Conectado ao GitHub")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao conectar: {e}")
    if not ctx.connected:
        st.warning("Conecte ao GitHub para continuar.")
        st.stop()
    st.divider()
    st.header("👤 Perfil")
    st.selectbox("Perfil", ["admin", "comum"], key="perfil")

st.success("Navegue pelas páginas: Dashboard, Transações, Calendário, Metas, Contas, Usuários.")
