
# pages/1_Lancamentos.py
import streamlit as st
from datetime import date, datetime
from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin

st.set_page_config(page_title="Lançamentos", page_icon="📝", layout="wide")
st.title("📝 Lançamentos")

ctx = get_context()
if not ctx.connected:
    st.warning("Conecte ao GitHub na página principal.")
    st.stop()
require_admin(ctx)
gh = ctx.gh

data = load_all((ctx.repo_full_name, ctx.branch_name))
categorias = data["data/categorias.json"]["content"]
contas = data["data/contas.json"]["content"]
receitas = data["data/receitas.json"]["content"]
despesas = data["data/despesas.json"]["content"]

with st.form("novo_lancamento", clear_on_submit=True):
    tipo = st.radio("Tipo", ["Receita", "Despesa"], horizontal=True)
    data_l = st.date_input("Data", date.today())
    valor = st.number_input("Valor", min_value=0.01, step=0.01)

    cats = categorias["receitas"] if tipo == "Receita" else categorias["despesas"]
    cat = st.selectbox("Categoria", [c["nome"] for c in cats])
    conta = st.selectbox("Conta", [c["nome"] for c in contas])
    obs = st.text_input("Observação")

    salvar = st.form_submit_button("💾 Salvar")

if salvar:
    item = {
        "id": f"{'r' if tipo=='Receita' else 'd'}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "data": data_l.isoformat(),
        "valor": float(valor),
        "categoria_id": next(c["id"] for c in cats if c["nome"] == cat),
        "conta_id": next(c["id"] for c in contas if c["nome"] == conta),
        "pessoa_id": ctx.usuario_id,
        "observacoes": obs,
    }
    if tipo == "Receita":
        receitas.append(item)
        gh.put_json("data/receitas.json", receitas, f"Add receita: {valor}")
    else:
        despesas.append(item)
        gh.put_json("data/despesas.json", despesas, f"Add despesa: {valor}")

    st.success("✅ Lançamento salvo")
    st.cache_data.clear()
    st.rerun()

st.divider()
st.subheader("📄 Lançamentos recentes")
todos = receitas + despesas
if todos:
    st.dataframe(
        sorted(todos, key=lambda x: x["data"], reverse=True)[:20],
        use_container_width=True
    )
else:
    st.info("Nenhum lançamento cadastrado.")
