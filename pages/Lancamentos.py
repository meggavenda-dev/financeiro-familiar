
# pages/1_Lancamentos.py
import streamlit as st
import pandas as pd
from datetime import date, datetime

from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import (
    novo_id,
    criar,
    editar,
    atualizar,
    excluir,
    remover,
    gerar_parcelas,
)

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Lançamentos",
    page_icon="📝",
    layout="wide"
)
st.title("📝 Lançamentos")

# --------------------------------------------------
# Contexto / Permissões
# --------------------------------------------------
ctx = get_context()

if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

require_admin(ctx)
gh = ctx.gh

# --------------------------------------------------
# Carregamento de dados
# --------------------------------------------------
data = load_all((ctx.repo_full_name, ctx.branch_name))


despesas_map = data["data/despesas.json"]
despesas = ensure_list(despesas_map.get("content"))
sha_despesas = despesas_map.get("sha")

def despesas_ativas():
    return [
        d for d in despesas
        if isinstance(d, dict) and not d.get("excluido", False)
    ]


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def ensure_list(obj):
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        return [obj]
    return []

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date(d):
    try:
        return datetime.fromisoformat(d).date()
    except Exception:
        return None

def salvar(lista, mensagem):
    gh.put_json(
        "data/despesas.json",
        lista,
        mensagem,
        sha=sha_despesas
    )
    st.cache_data.clear()
    st.success("✅ Alterações salvas com sucesso.")
    st.rerun()

def despesas_ativas():
    return [d for d in despesas if not d.get("excluido")]

# --------------------------------------------------
# NOVO LANÇAMENTO
# --------------------------------------------------
st.subheader("➕ Novo lançamento")

with st.form("nova_despesa"):
    col1, col2, col3 = st.columns(3)

    valor = col1.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_ref = col2.date_input("Data", value=date.today())
    status = col3.selectbox("Status", ["prevista", "pendente", "paga"])

    observacoes = st.text_input("Observações")

    st.markdown("### 🔢 Parcelamento (opcional)")
    colp1, colp2 = st.columns(2)
    parcelado = colp1.checkbox("Parcelar?")
    qtd_parcelas = colp2.number_input(
        "Qtd. parcelas",
        min_value=1,
        max_value=48,
        value=1,
        disabled=not parcelado
    )

    salvar_btn = st.form_submit_button("Salvar")

if salvar_btn:
    item_base = {
        "id": novo_id("d"),
        "data": data_ref.isoformat(),
        "valor": float(valor),
        "categoria_id": "cd1",
        "tipo_id": "td1",
        "conta_id": "c1",
        "status": status,
        "recorrente": False,
        "parcelamento": None,
        "excluido": False,
        "observacoes": observacoes.strip(),
    }

    # ----------------------------
    # PARCELADO
    # ----------------------------
    if parcelado and qtd_parcelas > 1:
        parcelas = gerar_parcelas(item_base, int(qtd_parcelas))
        for p in parcelas:
            criar(despesas, p)
        salvar(despesas, f"Add despesa parcelada ({qtd_parcelas}x)")
    else:
        criar(despesas, item_base)
        salvar(despesas, "Add despesa")

# --------------------------------------------------
# LISTAGEM E EDIÇÃO
# --------------------------------------------------
st.divider()
st.subheader("📋 Lançamentos existentes")

ativas = despesas_ativas()

if not ativas:
    st.info("Nenhum lançamento cadastrado.")
    st.stop()

df = pd.DataFrame(ativas)
df["data"] = df["data"].apply(parse_date)
df = df.sort_values("data", ascending=False)

st.dataframe(
    df[["id", "data", "valor", "status", "observacoes"]],
    use_container_width=True
)

# --------------------------------------------------
# AÇÕES (Editar / Excluir)
# --------------------------------------------------
st.markdown("### ✏️ Ações")

col1, col2 = st.columns(2)

editar_id = col1.text_input("ID para editar")
excluir_id = col2.text_input("ID para excluir")

# ----------------------------
# EXCLUIR
# ----------------------------
if excluir_id:
    if st.button("🗑️ Excluir lançamento"):
        ok = excluir(despesas, excluir_id)
        if ok:
            salvar(despesas, f"Remove despesa {excluir_id}")
        else:
            st.error("ID não encontrado.")

# ----------------------------
# EDITAR
# ----------------------------
if editar_id:
    item = next((x for x in despesas if x.get("id") == editar_id and not x.get("excluido")), None)

    if not item:
        st.error("ID não encontrado ou excluído.")
    else:
        st.markdown("### ✏️ Editando lançamento")
        with st.form("editar_despesa"):
            col1, col2, col3 = st.columns(3)

            novo_valor = col1.number_input(
                "Valor",
                min_value=0.01,
                value=float(item["valor"])
            )
            nova_data = col2.date_input(
                "Data",
                value=parse_date(item["data"])
            )
            novo_status = col3.selectbox(
                "Status",
                ["prevista", "pendente", "paga"],
                index=["prevista", "pendente", "paga"].index(item["status"])
            )

            novas_obs = st.text_input(
                "Observações",
                value=item.get("observacoes", "")
            )

            salvar_edicao = st.form_submit_button("Salvar edição")

        if salvar_edicao:
            item_editado = item.copy()
            item_editado.update({
                "valor": float(novo_valor),
                "data": nova_data.isoformat(),
                "status": novo_status,
                "observacoes": novas_obs.strip(),
            })

            atualizar(despesas, item_editado)
            salvar(despesas, f"Edit despesa {editar_id}")
