
# services/ui.py
import streamlit as st
from services.layout import is_mobile


def section(title: str, caption: str | None = None):
    st.subheader(title)
    if caption:
        st.caption(caption)


def card(title: str, lines: list[str]):
    """
    Card visual simples para mobile.
    """
    with st.container(border=True):
        st.markdown(f"**{title}**")
        for l in lines:
            st.write(l)


def responsive_dataframe(df):
    """
    Tabela no desktop → cartões no mobile
    """
    if is_mobile():
        for row in df.to_dict(orient="records"):
            with st.container(border=True):
                for k, v in row.items():
                    st.write(f"**{k}:** {v}")
    else:
        st.dataframe(df, use_container_width=True)

