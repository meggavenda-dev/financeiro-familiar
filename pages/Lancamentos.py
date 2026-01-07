
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
# HELPERS (definidos antes do uso)
# ==================================================
def ensure_list(obj):
    """Garante lista de dicionários válidos."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        return [obj]
    return []

def parse_date(d):
    """Converte string ISO para date."""
    if isinstance(d, date):
        return d
    try:
        return datetime.fromisoformat(str(d)).date()
    except Exception:
        return None

def competencia_from_date(d: date) -> str:
    """YYYY-MM de uma data."""
    return f"{d.year}-{d.month:02d}"

def competencia_label(comp: str) -> str:
    """JAN/26 a partir de YYYY-MM."""
    try:
        y, m = comp.split("-")
        meses = ["JAN","FEV","MAR","ABR","MAI","JUN","JUL","AGO","SET","OUT","NOV","DEZ"]
        return f"{meses[int(m)-1]}/{y[-2:]}"
    except Exception:
        return comp

def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def next_numero(itens: list) -> int:
    """Próximo número amigável sequencial."""
    nums = [int(x.get("numero", 0)) for x in itens if isinstance(x.get("numero", None), (int, float, str))]
    nums = [int(n) for n in nums if str(n).isdigit()]
    return (max(nums) + 1) if nums else 1

def calcular_status(item: dict) -> str:
    """
    Status calculado para UX:
    - 'paga' quando item.status == 'paga'
    - 'atrasada' se data < hoje e não paga
    - 'em_aberto' se data == hoje e não paga (mais amigável)
    - 'planejada' se data > hoje e não paga
    Mantém compat com status técnico existente (prevista/pendente/paga).
    """
    st_raw = item.get("status", "prevista")
    if st_raw == "paga":
        return "paga"
    d = parse_date(item.get("data"))
    if not d:
        return "planejada"
    hoje = date.today()
    if d < hoje:
        return "atrasada"
    if d == hoje:
        return "em_aberto"
    return "planejada"

def badge_status(st_calc: str) -> str:
    mapping = {
        "planejada": "📝 Planejada",
        "em_aberto": "⏳ Em aberto",
        "atrasada": "🔴 Atrasada",
        "paga": "✅ Paga",
    }
    return mapping.get(st_calc, st_calc)

def salvar_json_despesas(gh, payload: list, mensagem: str, sha_atual: str):
    """
    Salva e atualiza SHA no session_state (controle de concorrência).
    """
    try:
        new_sha = gh.put_json("data/despesas.json", payload, mensagem, sha=sha_atual)
        st.session_state["sha_despesas"] = new_sha
        st.cache_data.clear()
        st.success("✅ Alterações salvas.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar no GitHub: {e}")

# ==================================================
# CONFIGURAÇÃO DA PÁGINA
# ==================================================
st.set_page_config(page_title="Lançamentos", page_icon="📝", layout="wide")
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
# CARREGAMENTO SEGURO
# ==================================================
data = load_all((ctx.repo_full_name, ctx.branch_name))

despesas_map = data["data/despesas.json"]
despesas = ensure_list(despesas_map.get("content"))
sha_inicial = despesas_map.get("sha")
if "sha_despesas" not in st.session_state:
    st.session_state["sha_despesas"] = sha_inicial

# Campos auxiliares (opcional): categorias e contas
categorias_map = data.get("data/categorias.json", {"content": []})
contas_map = data.get("data/contas.json", {"content": []})
categorias = ensure_list(categorias_map.get("content"))
contas = ensure_list(contas_map.get("content"))

def categoria_opts():
    return {c.get("id", "cd1"): c.get("nome", c.get("id", "cd1")) for c in categorias} or {"cd1": "Geral"}

def conta_opts():
    return {c.get("id", "c1"): c.get("nome", c.get("id", "c1")) for c in contas} or {"c1": "Conta Principal"}

# ==================================================
# DERIVAÇÃO DE COMPETÊNCIA (para dados antigos)
# ==================================================
for d in despesas:
    if "competencia" not in d or not d["competencia"]:
        ddata = parse_date(d.get("data"))
        if ddata:
            d["competencia"] = competencia_from_date(ddata)

competencias = sorted({d["competencia"] for d in despesas if d.get("competencia")}, reverse=True)
default_comp = competencia_from_date(date.today())
if default_comp not in competencias:
    competencias.append(default_comp)
competencias = sorted(set(competencias), reverse=True)

# ==================================================
# FILTROS
# ==================================================
st.subheader("🔍 Filtros")

colf1, colf2, colf3 = st.columns([2,2,2])
comp_select = colf1.selectbox("Competência (mês)", options=competencias, format_func=competencia_label, index=0)
status_filter = colf2.selectbox("Status", options=["Todos", "Planejada", "Em aberto", "Atrasada", "Paga"])
busca_texto = colf3.text_input("Buscar por descrição / observações")

def match_status_calc(d):
    sc = calcular_status(d)
    if status_filter == "Todos":
        return True
    return {
        "Planejada": "planejada",
        "Em aberto": "em_aberto",
        "Atrasada": "atrasada",
        "Paga": "paga",
    }[status_filter] == sc

def filtrar_itens(ds):
    out = []
    for d in ds:
        if d.get("excluido"):
            continue
        if d.get("competencia") != comp_select:
            continue
        if not match_status_calc(d):
            continue
        if busca_texto:
            txt = f"{d.get('descricao','')} {d.get('observacoes','')}".lower()
            if busca_texto.lower() not in txt:
                continue
        out.append(d)
    return out

mes_itens = filtrar_itens(despesas)

# ==================================================
# RESUMO MENSAL
# ==================================================
st.subheader(f"📅 Resumo — {competencia_label(comp_select)}")

def soma_por_status(ds, alvo):
    return sum(float(x.get("valor", 0.0)) for x in ds if calcular_status(x) == alvo)

total_mes = sum(float(x.get("valor", 0.0)) for x in mes_itens)
total_pago = soma_por_status(mes_itens, "paga")
total_aberto = soma_por_status(mes_itens, "em_aberto")
total_atrasado = soma_por_status(mes_itens, "atrasada")
total_planejado = soma_por_status(mes_itens, "planejada")

kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("✅ Pago", fmt_brl(total_pago))
kc2.metric("⏳ Em aberto (hoje)", fmt_brl(total_aberto))
kc3.metric("🔴 Atrasado", fmt_brl(total_atrasado))
kc4.metric("📝 Planejado (futuro)", fmt_brl(total_planejado))

st.progress((total_pago / total_mes) if total_mes > 0 else 0.0)

st.divider()

# ==================================================
# CADASTRO — MODO RÁPIDO + AVANÇADO
# ==================================================
st.subheader("➕ Novo lançamento")

cat_map = categoria_opts()
conta_map = conta_opts()

with st.form("novo_lancamento"):
    c1, c2, c3 = st.columns([2,2,2])
    descricao = c1.text_input("Descrição", placeholder="Ex.: Supermercado, Internet, Luz")
    valor = c2.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_ref = c3.date_input("Data", value=date.today())

    c4, c5 = st.columns([2,2])
    conta_nome = c4.selectbox("Conta", options=list(conta_map.values()))
    marcado_pago = c5.checkbox("Já paguei", value=False)

    with st.expander("⚙️ Detalhes avançados"):
        a1, a2 = st.columns(2)
        categoria_nome = a1.selectbox("Categoria", options=list(cat_map.values()))
        observacoes = a2.text_input("Observações")
        b1, b2 = st.columns(2)
        parcelar = b1.checkbox("Parcelar?")
        qtd_parcelas = b2.number_input("Qtd. parcelas", min_value=1, max_value=60, value=1, disabled=not parcelar)

    salvar_btn = st.form_submit_button("Salvar")

if salvar_btn:
    # Resolve IDs a partir dos nomes
    inv_cat = {v: k for k, v in cat_map.items()}
    inv_conta = {v: k for k, v in conta_map.items()}

    comp_new = competencia_from_date(data_ref)
    numero_new = next_numero(despesas)
    ref_new = f"{competencia_label(comp_new)}-{numero_new}"

    base_item = {
        "id": novo_id("d"),
        "numero": numero_new,
        "referencia": ref_new,

        "descricao": descricao.strip(),
        "valor": float(valor),
        "data": data_ref.isoformat(),
        "competencia": comp_new,

        "status": ("paga" if marcado_pago else "prevista"),  # manter compat com app
        "paga_em": (datetime.now().isoformat() if marcado_pago else None),

        "categoria_id": inv_cat.get(categoria_nome, "cd1"),
        "conta_id": inv_conta.get(conta_nome, "c1"),

        "recorrente": False,
        "parcelamento": None,
        "group_id": None,

        "excluido": False,
        "observacoes": observacoes.strip(),
        "criado_em": datetime.now().isoformat(),
    }

    if parcelar and int(qtd_parcelas) > 1:
        # Gerar parcelas mensais e atribuir numero/referencia únicos
        parcelas = gerar_parcelas(base_item, int(qtd_parcelas))
        for p in parcelas:
            # Atualiza competencia conforme data da parcela
            pd_date = parse_date(p.get("data"))
            p["competencia"] = competencia_from_date(pd_date) if pd_date else comp_new
            # Novo numero/ref para cada parcela
            numero_new = next_numero(despesas)
            p["numero"] = numero_new
            p["referencia"] = f"{competencia_label(p['competencia'])}-{numero_new}"
            criar(despesas, p)
        salvar_json_despesas(gh, despesas, f"Add despesa parcelada ({qtd_parcelas}x)", st.session_state["sha_despesas"])
    else:
        criar(despesas, base_item)
        salvar_json_despesas(gh, despesas, "Add despesa", st.session_state["sha_despesas"])

# ==================================================
# LISTA POR COMPETÊNCIA (com ações)
# ==================================================
st.subheader(f"📋 Lançamentos — {competencia_label(comp_select)}")

lista_mes = [d for d in despesas if d.get("competencia") == comp_select and not d.get("excluido")]
if not lista_mes:
    st.info("Nenhum lançamento para este mês.")
else:
    # Preparar DF com status calculado e badge
    df = pd.DataFrame(lista_mes)
    df["data_date"] = df["data"].apply(parse_date)
    df["status_calc"] = df.apply(lambda r: calcular_status(r), axis=1)
    df["status_badge"] = df["status_calc"].apply(badge_status)

    cols_show = ["numero", "referencia", "descricao", "data_date", "valor", "status_badge", "observacoes"]
    df_show = df[cols_show].rename(columns={
        "numero": "Nº",
        "referencia": "Ref.",
        "descricao": "Descrição",
        "data_date": "Data",
        "valor": "Valor",
        "status_badge": "Status",
        "observacoes": "Obs."
    }).sort_values("Data", ascending=False)

    st.dataframe(df_show, use_container_width=True)

    st.markdown("### ✏️ Ações")
    ac1, ac2, ac3 = st.columns([3,3,2])
    editar_num = ac1.number_input("Editar (Nº)", min_value=1, step=1)
    excluir_num = ac2.number_input("Excluir (Nº)", min_value=1, step=1)
    executar = ac3.button("Executar")

    if executar:
        alvo_edit = next((x for x in lista_mes if int(x.get("numero", 0)) == int(editar_num)), None)
        alvo_del = next((x for x in lista_mes if int(x.get("numero", 0)) == int(excluir_num)), None)

        if alvo_del:
            ok = excluir(despesas, alvo_del["id"])
            if ok:
                salvar_json_despesas(gh, despesas, f"Remove despesa Nº {alvo_del.get('numero')}", st.session_state["sha_despesas"])
            else:
                st.error("Não foi possível excluir.")
        elif alvo_edit:
            st.markdown(f"#### Editando Nº {alvo_edit.get('numero')} — {alvo_edit.get('descricao','')}")
            with st.form("editar_item"):
                e1, e2, e3 = st.columns(3)
                novo_desc = e1.text_input("Descrição", value=alvo_edit.get("descricao", ""))
                novo_valor = e2.number_input("Valor (R$)", min_value=0.01, step=0.01, value=float(alvo_edit.get("valor", 0.0)))
                nova_data = e3.date_input("Data", value=parse_date(alvo_edit.get("data")) or date.today())

                e4, e5 = st.columns(2)
                novo_status_vis = e4.selectbox("Status", options=["Planejada", "Em aberto", "Atrasada", "Paga"],
                                               index=["Planejada","Em aberto","Atrasada","Paga"].index(
                                                   {"planejada":"Planejada","em_aberto":"Em aberto","atrasada":"Atrasada","paga":"Paga"}[calcular_status(alvo_edit)]
                                               ))
                nova_obs = e5.text_input("Observações", value=alvo_edit.get("observacoes",""))

                ok_btn = st.form_submit_button("Salvar edição")

            if ok_btn:
                # Traduz status visível de volta ao técnico mais próximo
                vis_to_tec = {
                    "Planejada": "prevista",
                    "Em aberto": "pendente",
                    "Atrasada": "pendente",
                    "Paga": "paga",
                }
                novo_status_tec = vis_to_tec.get(novo_status_vis, "prevista")

                # Recalcula competência e referência se mudou a data
                comp_new = competencia_from_date(nova_data)
                ref_new = f"{competencia_label(comp_new)}-{alvo_edit.get('numero')}"

                item_editado = alvo_edit.copy()
                item_editado.update({
                    "descricao": novo_desc.strip(),
                    "valor": float(novo_valor),
                    "data": nova_data.isoformat(),
                    "competencia": comp_new,
                    "referencia": ref_new,
                    "status": novo_status_tec,
                    "paga_em": (datetime.now().isoformat() if novo_status_tec == "paga" else None),
                    "observacoes": nova_obs.strip(),
                    "atualizado_em": datetime.now().isoformat(),
                })

                atualizar(despesas, item_editado)
                salvar_json_despesas(gh, despesas, f"Edit despesa Nº {alvo_edit.get('numero')}", st.session_state["sha_despesas"])
        else:
            st.info("Informe o Nº de um lançamento para editar ou excluir.")
