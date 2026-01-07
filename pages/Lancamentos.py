
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
    gerar_parcelas,
)

# ==================================================
# HELPERS DE SEGURANÇA (DEVEM VIR PRIMEIRO)
# ==================================================
def ensure_list(obj):
    """Garante lista de dicionários válidos"""
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        return [obj]
    return []

def parse_date(d):
    try:
        return datetime.fromisoformat(d).date()
    except Exception:
        return None

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==================================================
# CONFIGURAÇÃO DA PÁGINA
# ==================================================
st.set_page_config(
    page_title="Lançamentos",
    page_icon="📝",
    layout="wide"
)
st.title("📝 Lançamentos")

# ==================================================
# CONTEXTO / PERMISSÕES
# ==================================================
ctx = get_context()

if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()

require_admin(ctx)
gh = ctx.gh

# ==================================================
# CARREGAMENTO DE DADOS (SEGURO)
# ==================================================
data = load_all((ctx.repo_full_name, ctx.branch_name))

despesas_map = data["data/despesas.json"]
despesas = ensure_list(despesas_map.get("content"))
sha_despesas = despesas_map.get("sha")

def despesas_ativas():
    return [
        d for d in despesas
        if isinstance(d, dict) and not d.get("excluido", False)
    ]

def salvar(lista, mensagem):
    gh.put_json(
        "data/despesas.json",
        lista,
        mensagem,
        sha=sha_despesas
    )
    st.cache_data.clear()
    st.success("✅ Alterações salvas.")
    st.rerun()

# ==================================================
# NOVO LANÇAMENTO
# ==================================================
st.subheader("➕ Novo lançamento")

with st.form("nova_despesa"):
    c1, c2, c3 = st.columns(3)

    valor = c1.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_ref = c2.date_input("Data", value=date.today())
    status = c3.selectbox("Status", ["prevista", "pendente", "paga"])

    observacoes = st.text_input("Observações")

    st.markdown("### 🔢 Parcelamento")
    p1, p2 = st.columns(2)

    parcelado = p1.checkbox("Parcelar?")
    qtd_parcelas = p2.number_input(
        "Qtd. parcelas",
        min_value=1,
        value=1,
        disabled=not parcelado
    )

    salvar_btn = st.form_submit_button("Salvar")

if salvar_btn:
    base = {
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

    if parcelado and qtd_parcelas > 1:
        parcelas = gerar_parcelas(base, int(qtd_parcelas))
        for p in parcelas:
            criar(despesas, p)
        salvar(despesas, f"Add despesa parcelada ({qtd_parcelas}x)")
    else:
        criar(despesas, base)
        salvar(despesas, "Add despesa")

# ==================================================
# LISTAGEM
# ==================================================
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

# ==================================================
# AÇÕES
# ==================================================
st.markdown("### ✏️ Ações")

c1, c2 = st.columns(2)
editar_id = c1.text_input("ID para editar")
excluir_id = c2.text_input("ID para excluir")

# ---------------- EXCLUIR ----------------
if excluir_id and st.button("🗑️ Excluir"):
    if excluir(despesas, excluir_id):
        salvar(despesas, f"Remove despesa {excluir_id}")
    else:
        st.error("ID não encontrado.")

# ---------------- EDITAR ----------------
if editar_id:
    item = next((x for x in despesas_ativas() if x["id"] == editar_id), None)

    if not item:
        st.error("ID não encontrado.")
    else:
        with st.form("editar"):
            v = st.number_input("Valor", min_value=0.01, value=float(item["valor"]))
            d = st.date_input("Data", value=parse_date(item["data"]))
            s = st.selectbox("Status", ["prevista", "pendente", "paga"],
                             index=["prevista","pendente","paga"].index(item["status"]))
            obs = st.text_input("Observações", value=item.get("observacoes",""))
            ok = st.form_submit_button("Salvar edição")

        if ok:
            item.update({
                "valor": float(v),
                "data": d.isoformat(),
                "status": s,
                "observacoes": obs.strip(),
            })
            atualizar(despesas, item)
            salvar(despesas, f"Edit despesa {editar_id}")
