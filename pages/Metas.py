
# pages/3_Metas.py
import streamlit as st
from datetime import date
import pandas as pd

from services.app_context import get_context
from services.data_loader import load_all

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(page_title="Metas Financeiras", page_icon="🎯", layout="wide")
st.title("🎯 Metas Financeiras")

# --------------------------------------------------
# Contexto / Conexão
# --------------------------------------------------
ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal para acessar as metas.")
    st.stop()

gh = ctx.gh

# --------------------------------------------------
# Carregamento de dados (com sanitização defensiva)
# --------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))

metas_map = data.get("data/metas.json", {"content": [], "sha": None})
metas_raw = metas_map.get("content", [])
sha_metas = metas_map.get("sha")

# ⚠️ Sanitiza: garante que só vamos trabalhar com dicts
metas = [m for m in metas_raw if isinstance(m, dict)]

def salvar():
    """Salva 'metas' sanitizadas e atualiza SHA."""
    global sha_metas
    new_sha = gh.put_json("data/metas.json", metas, "Update metas financeiras", sha=sha_metas)
    sha_metas = new_sha
    st.cache_data.clear()
    st.rerun()

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def fmt_brl(v: float) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def meses_restantes(data_meta: str) -> int:
    """Calcula quantos meses faltam até a data_meta (mínimo 1)."""
    try:
        d = date.fromisoformat(str(data_meta))
        meses = (d.year - date.today().year) * 12 + (d.month - date.today().month)
        return max(meses, 1)
    except Exception:
        return 1

def calc_aporte(meta: dict) -> float:
    """Aporte mensal sugerido para atingir a meta no prazo."""
    try:
        valor_meta = float(meta.get("valor_meta", 0.0))
        acumulado = float(meta.get("valor_atual", 0.0))
    except Exception:
        return 0.0
    if valor_meta <= 0 or acumulado >= valor_meta:
        return 0.0
    meses = meses_restantes(meta.get("data_meta"))
    return (valor_meta - acumulado) / meses if meses > 0 else 0.0

def progresso(meta: dict) -> float:
    """0..1 do progresso da meta."""
    try:
        valor_meta = float(meta.get("valor_meta", 0.0))
        acumulado = float(meta.get("valor_atual", 0.0))
    except Exception:
        return 0.0
    if valor_meta <= 0:
        return 0.0
    return min(max(acumulado / valor_meta, 0.0), 1.0)

# --------------------------------------------------
# Cadastro de nova meta (ADMIN)
# --------------------------------------------------
is_admin = (ctx.perfil == "admin")

if is_admin:
    with st.expander("➕ Cadastrar nova meta"):
        with st.form("nova_meta"):
            nome = st.text_input("Nome da meta")
            valor_meta = st.number_input("Valor da meta (R$)", min_value=1.0)
            data_meta = st.date_input("Data limite")

            # Regras automáticas (opcional)
            tipo_regra = st.selectbox("Regra automática", ["manual", "percentual_receita"])
            pct = st.number_input("Percentual da receita (0 a 1)", min_value=0.0, max_value=1.0,
                                  step=0.05, value=0.10, disabled=(tipo_regra != "percentual_receita"))

            salvar_btn = st.form_submit_button("Salvar meta")

        if salvar_btn:
            # Insere somente dict válido e completo
            metas.append({
                "id": f"m-{len(metas)+1}",
                "nome": (nome or "").strip(),
                "valor_meta": float(valor_meta),
                "valor_atual": 0.0,
                "data_meta": data_meta.isoformat(),
                "observacoes": "",
                "regra": {"tipo": tipo_regra, "percentual": float(pct) if tipo_regra == "percentual_receita" else 0.0},
                "ativa": True,
            })
            salvar()

# --------------------------------------------------
# Exibição das metas (com defesa total)
# --------------------------------------------------
if not metas:
    st.info("Nenhuma meta cadastrada.")
    st.stop()

for meta in metas:
    # 🔐 Defesa: só processa dicts e com campos previstos
    if not isinstance(meta, dict):
        continue

    nome_meta = (meta.get("nome") or "Meta").strip()
    valor_meta = meta.get("valor_meta", 0.0)
    valor_atual = meta.get("valor_atual", 0.0)
    data_limite = meta.get("data_meta", "—")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader(nome_meta)
        pct = progresso(meta)
        st.progress(pct)
        st.caption(f"Progresso: **{pct*100:.1f}%**")

        st.write(f"🎯 Meta: **{fmt_brl(valor_meta)}**")
        st.write(f"💰 Acumulado: **{fmt_brl(valor_atual)}**")
        st.write(f"📅 Data limite: **{data_limite}**")

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
            st.success("🎉 Meta atingida ou sem necessidade de aporte.")

        # Admin pode ajustar valor acumulado manualmente
        if is_admin:
            try:
                atual = float(meta.get("valor_atual", 0.0))
            except Exception:
                atual = 0.0
            novo_valor = st.number_input(
                "Atualizar valor acumulado",
                min_value=0.0,
                value=atual,
                key=f"acc-{meta.get('id','sem-id')}"
            )
            # Atualiza somente se mudou
            if novo_valor != atual:
                meta["valor_atual"] = float(novo_valor)
                salvar()

    st.divider()

st.success("✅ Metas carregadas com sucesso.")
