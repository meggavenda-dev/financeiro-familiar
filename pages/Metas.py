
# pages/3_Metas.py
import streamlit as st
from datetime import date
import pandas as pd

from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.utils import fmt_brl, fmt_date_br

st.set_page_config(
    page_title="Metas Financeiras",
    page_icon="🎯",
    layout="wide",
)
st.title("🎯 Metas Financeiras")

# --------------------------------------------------
# Contexto
# --------------------------------------------------
init_context()
ctx = get_context()
if not ctx.get("connected"):
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

gh = ctx.get("gh")
usuario = ctx.get("usuario_id", "u1")
is_admin = ctx.get("perfil") == "admin"

# --------------------------------------------------
# Carregamento
# --------------------------------------------------
data = load_all((ctx["repo_full_name"], ctx["branch_name"]))
metas_map = data.get("data/metas.json", {"content": [], "sha": None})
metas = [m for m in metas_map.get("content", []) if isinstance(m, dict)]
sha = metas_map.get("sha")

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def meses_restantes(data_meta: str) -> int:
    try:
        d = date.fromisoformat(str(data_meta))
        meses = (d.year - date.today().year) * 12 + (d.month - date.today().month)
        return max(meses, 0)  # CHANGE: permite zero
    except Exception:
        return 0


def progresso(meta: dict) -> float:
    try:
        meta_val = float(meta.get("valor_meta", 0))
        atual = float(meta.get("valor_atual", 0))
    except Exception:
        return 0.0
    if meta_val <= 0:
        return 0.0
    return min(max(atual / meta_val, 0), 1)


def aporte_sugerido(meta: dict) -> float:
    try:
        meta_val = float(meta.get("valor_meta", 0))
        atual = float(meta.get("valor_atual", 0))
    except Exception:
        return 0.0

    faltante = meta_val - atual
    if faltante <= 0:
        return 0.0

    meses = meses_restantes(meta.get("data_meta"))
    if meses <= 0:
        return 0.0

    return faltante / meses


def salvar(msg: str):
    nonlocal_sha = globals().get("_sha_metas")
    new_sha = gh.put_json(
        "data/metas.json",
        metas,
        f"[{usuario}] {msg}",
        sha=sha,
    )
    return new_sha


# --------------------------------------------------
# Cadastro
# --------------------------------------------------
if is_admin:
    with st.expander("➕ Nova meta"):
        with st.form("nova_meta"):
            nome = st.text_input("Nome da meta")
            valor_meta = st.number_input("Valor da meta (R$)", min_value=1.0)
            data_meta = st.date_input("Data limite")

            salvar_btn = st.form_submit_button("Salvar")

        if salvar_btn:
            metas.append({
                "id": f"m-{len(metas)+1}",
                "nome": (nome or "").strip(),
                "valor_meta": float(valor_meta),
                "valor_atual": 0.0,
                "data_meta": data_meta.isoformat(),
                "ativa": True,
            })
            gh.put_json(
                "data/metas.json",
                metas,
                f"[{usuario}] Cria meta financeira",
                sha=sha,
            )
            st.cache_data.clear()
            st.success("Meta criada.")
            st.rerun()

# --------------------------------------------------
# Exibição
# --------------------------------------------------
if not metas:
    st.info("Nenhuma meta cadastrada.")
    st.stop()

for meta in metas:
    nome = meta.get("nome", "Meta")
    valor_meta = meta.get("valor_meta", 0.0)
    valor_atual = meta.get("valor_atual", 0.0)
    data_limite = meta.get("data_meta")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader(nome)

        pct = progresso(meta)
        st.progress(pct)
        st.caption(f"Progresso: **{pct*100:.1f}%**")
        st.write(f"🎯 Meta: **{fmt_brl(valor_meta)}**")
        st.write(f"💰 Acumulado: **{fmt_brl(valor_atual)}**")
        st.write(f"📅 Data limite: **{fmt_date_br(data_limite)}**")

        if meses_restantes(data_limite) == 0 and valor_atual < valor_meta:
            st.error("🔴 Meta vencida sem atingir o valor.")

    with col2:
        aporte = aporte_sugerido(meta)
        meses = meses_restantes(data_limite)

        if aporte > 0:
            st.metric(
                "Aporte mensal sugerido",
                fmt_brl(aporte),
                help=f"{meses} mês(es) restantes",
            )
        else:
            st.success("✅ Meta atingida ou sem aporte necessário.")

        if is_admin:
            novo_valor = st.number_input(
                "Atualizar valor acumulado",
                min_value=0.0,
                value=float(valor_atual),
                key=f"acc-{meta.get('id')}",
            )
            if novo_valor != valor_atual:
                meta["valor_atual"] = float(novo_valor)
                gh.put_json(
                    "data/metas.json",
                    metas,
                    f"[{usuario}] Atualiza valor acumulado",
                    sha=sha,
                )
                st.cache_data.clear()
                st.rerun()

    st.divider()

st.success("✅ Metas carregadas com sucesso.")
