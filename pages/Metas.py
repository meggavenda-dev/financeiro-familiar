
# pages/3_Metas.py
import streamlit as st
from datetime import date

# --------------------------------------------------
# Imports internos
# --------------------------------------------------
from services.app_context import init_context, get_context
from services.data_loader import load_all
from services.utils import fmt_brl, fmt_date_br
from services.layout import responsive_columns, is_mobile
from services.ui import section, card

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Metas Financeiras",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
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
        return max(meses, 0)
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
    faltante = float(meta.get("valor_meta", 0)) - float(meta.get("valor_atual", 0))
    if faltante <= 0:
        return 0.0

    meses = meses_restantes(meta.get("data_meta"))
    if meses <= 0:
        return 0.0

    return faltante / meses

# --------------------------------------------------
# Cadastro de nova meta (ADMIN)
# --------------------------------------------------
if is_admin:
    section("➕ Nova meta")

    with st.form("nova_meta"):
        cols = responsive_columns(desktop=3, mobile=1)

        nome = cols[0].text_input("Nome da meta")
        valor_meta = cols[1].number_input(
            "Valor da meta (R$)",
            min_value=1.0,
            step=100.0,
        )
        data_meta = cols[2].date_input("Data limite")

        salvar = st.form_submit_button("Salvar")

    if salvar:
        if not nome.strip():
            st.error("Informe um nome válido.")
        else:
            metas.append({
                "id": f"m-{len(metas)+1}",
                "nome": nome.strip(),
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

st.divider()

# --------------------------------------------------
# Listagem de metas
# --------------------------------------------------
if not metas:
    st.info("Nenhuma meta cadastrada.")
    st.stop()

section("📌 Suas metas")

for meta in metas:
    nome = meta.get("nome", "Meta")
    valor_meta = float(meta.get("valor_meta", 0))
    valor_atual = float(meta.get("valor_atual", 0))
    data_limite = meta.get("data_meta")

    pct = progresso(meta)
    meses = meses_restantes(data_limite)
    aporte = aporte_sugerido(meta)

    # -------------------------------
    # MOBILE
    # -------------------------------
    if is_mobile():
        card(
            nome,
            [
                f"🎯 Meta: {fmt_brl(valor_meta)}",
                f"💰 Acumulado: {fmt_brl(valor_atual)}",
                f"📅 Limite: {fmt_date_br(data_limite)}",
                f"📊 Progresso: {pct*100:.1f}%",
            ],
        )

        st.progress(pct)

        if aporte > 0:
            st.metric("Aporte mensal sugerido", fmt_brl(aporte))

        if meses == 0 and valor_atual < valor_meta:
            st.error("🔴 Meta vencida sem atingir o valor.")

        if is_admin:
            novo_valor = st.number_input(
                "Atualizar valor acumulado",
                min_value=0.0,
                value=valor_atual,
                key=f"acc-{meta.get('id')}",
            )

            if novo_valor != valor_atual:
                meta["valor_atual"] = novo_valor
                gh.put_json(
                    "data/metas.json",
                    metas,
                    f"[{usuario}] Atualiza meta {nome}",
                    sha=sha,
                )
                st.cache_data.clear()
                st.rerun()

        st.divider()

    # -------------------------------
    # DESKTOP
    # -------------------------------
    else:
        col1, col2 = responsive_columns(desktop=2)

        with col1:
            st.subheader(nome)
            st.progress(pct)
            st.caption(f"{pct*100:.1f}% concluído")
            st.write(f"🎯 Meta: **{fmt_brl(valor_meta)}**")
            st.write(f"💰 Acumulado: **{fmt_brl(valor_atual)}**")
            st.write(f"📅 Limite: **{fmt_date_br(data_limite)}**")

            if meses == 0 and valor_atual < valor_meta:
                st.error("🔴 Meta vencida sem atingir o valor.")

        with col2:
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
                    value=valor_atual,
                    key=f"acc-d-{meta.get('id')}",
                )

                if novo_valor != valor_atual:
                    meta["valor_atual"] = novo_valor
                    gh.put_json(
                        "data/metas.json",
                        metas,
                        f"[{usuario}] Atualiza meta {nome}",
                        sha=sha,
                    )
                    st.cache_data.clear()
                    st.rerun()

        st.divider()

st.success("✅ Metas carregadas com sucesso.")
