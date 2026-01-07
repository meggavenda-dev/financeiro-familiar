
# pages/3_Metas.py
import streamlit as st
from datetime import date
import pandas as pd

from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(page_title="Metas Financeiras", page_icon="🎯", layout="wide")
st.title("🎯 Metas Financeiras")

# --------------------------------------------------
# Contexto / Permissões
# --------------------------------------------------
ctx = get_context()

if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal para acessar as metas.")
    st.stop()

# Metas podem ser VISUALIZADAS por todos,
# mas apenas ADMIN pode alterar/cadastrar
is_admin = ctx.perfil == "admin"
gh = ctx.gh

# --------------------------------------------------
# Carregamento de dados
# --------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))

metas_map = data["data/metas.json"]
metas = metas_map["content"]
sha_metas = metas_map["sha"]

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def meses_restantes(data_meta: str) -> int:
    try:
        d = date.fromisoformat(data_meta)
        meses = (d.year - date.today().year) * 12 + (d.month - date.today().month)
        return max(meses, 1)
    except Exception:
        return 1

def calc_aporte(meta: dict) -> float:
    valor_meta = float(meta.get("valor_meta", 0.0))
    acumulado = float(meta.get("valor_acumulado", 0.0))
    if acumulado >= valor_meta:
        return 0.0
    meses = meses_restantes(meta.get("data_meta"))
    return (valor_meta - acumulado) / meses

def progresso(meta: dict) -> float:
    valor_meta = float(meta.get("valor_meta", 0.0))
    acumulado = float(meta.get("valor_acumulado", 0.0))
    if valor_meta <= 0:
        return 0.0
    return min(acumulado / valor_meta, 1.0)

def salvar():
    gh.put_json(
        "data/metas.json",
        metas,
        "Update metas financeiras",
        sha=sha_metas
    )
    st.cache_data.clear()
    st.rerun()

# --------------------------------------------------
# Cadastro de nova meta (ADMIN)
# --------------------------------------------------
if is_admin:
    with st.expander("➕ Cadastrar nova meta"):
        with st.form("nova_meta"):
            nome = st.text_input("Nome da meta")
            valor_meta = st.number_input("Valor da meta (R$)", min_value=1.0)
            data_meta = st.date_input("Data limite")
            salvar_btn = st.form_submit_button("Salvar meta")

        if salvar_btn:
            metas.append({
                "id": f"m-{len(metas)+1}",
                "nome": nome,
                "valor_meta": float(valor_meta),
                "valor_acumulado": 0.0,
                "data_meta": data_meta.isoformat(),
                "observacoes": "",
            })
            salvar()

# --------------------------------------------------
# Exibição das metas
# --------------------------------------------------
if not metas:
    st.info("Nenhuma meta cadastrada.")
    st.stop()

for meta in metas:
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader(meta.get("nome", "Meta"))
        pct = progresso(meta)
        st.progress(pct)
        st.caption(f"Progresso: **{pct*100:.1f}%**")

        st.write(f"🎯 Meta: **{fmt_brl(meta.get('valor_meta', 0))}**")
        st.write(f"💰 Acumulado: **{fmt_brl(meta.get('valor_acumulado', 0))}**")
        st.write(f"📅 Data limite: **{meta.get('data_meta', '—')}**")

    with col2:
        aporte = calc_aporte(meta)
        meses = meses_restantes(meta.get("data_meta"))

        if aporte > 0:
            st.metric(
                "Aporte mensal sugerido",
                fmt_brl(aporte),
                help=f"Baseado em {meses} meses restantes"
            )
        else:
            st.success("🎉 Meta atingida!")

        # Admin pode ajustar valor acumulado manualmente
        if is_admin:
            novo_valor = st.number_input(
                "Atualizar valor acumulado",
                min_value=0.0,
                value=float(meta.get("valor_acumulado", 0.0)),
                key=f"acc-{meta['id']}"
            )
            if novo_valor != float(meta.get("valor_acumulado", 0.0)):
                meta["valor_acumulado"] = novo_valor
                salvar()

    st.divider()

st.success("✅ Metas carregadas com sucesso.")

