
import streamlit as st
from github_service import GitHubService

def get_context():
    if "gh" not in st.session_state:
        gh = GitHubService(
            token=st.secrets["github_token"],
            repo_full_name=st.secrets["repo_full_name"],
            branch=st.secrets.get("branch_name", "main")
        )
        st.session_state.gh = gh

    return {
        "gh": st.session_state.gh,
        "usuario_id": st.session_state.get("usuario_id", "u1"),
        "perfil": st.session_state.get("perfil", "admin"),
    }

