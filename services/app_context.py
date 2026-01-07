
import streamlit as st
from github_service import GitHubService

def init_context():
    if "gh" not in st.session_state:
        st.session_state.gh = GitHubService(
            token=st.secrets["github_token"],
            repo_full_name=st.secrets["repo_full_name"],
            branch=st.secrets.get("branch_name", "main")
        )

    if "usuario_id" not in st.session_state:
        st.session_state.usuario_id = "u1"

    if "perfil" not in st.session_state:
        st.session_state.perfil = "admin"

def get_context():
    init_context()
    return st.session_state
