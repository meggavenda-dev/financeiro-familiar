
# pages/1_Lancamentos.py
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import uuid

from services.app_context import get_context
from services.data_loader import load_all
from services.permissions import require_admin
from services.finance_core import novo_id, criar, atualizar, remover

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(page_title="Lançamentos", page_icon="📝", layout="wide")
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
despesas = despesas_map.get("content") or []
sha_despesas = despesas_map.get("sha")

# Opcional: carregar auxiliares (categorias, tipos, contas)
categorias_map = data.get("data/categorias.json", {"content": []})
tipos_map = data.get("data/tipos.json", {"content": []})
contas_map = data.get("data/contas.json", {"content": []})

categorias = categorias_map.get("content") or []
tipos = tipos_map.get("content") or []
contas = contas_map.get("content") or []

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date(d):
    if d is None:
        return None
    try:
        if isinstance(d, date):
            return d
        return pd.to_datetime(d).date()
    except Exception:
        return None

def salvar(lista: list, mensagem: str):
    """Salva despesa no GitHub usando SHA correto e faz rerun."""
    try:
        new_sha = gh.put_json("data/despesas.json", lista, mensagem, sha=sha_despesas)
        # Atualiza sha local
        global sha_despesas
        sha_despesas = new_sha
        st.cache_data.clear()
        st.success("✅ Alterações salvas.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar no GitHub: {e}")

def categoria_opts():
    # id -> nome; se não houver arquivo, usa fallback básico
    if categorias:
        return {c["id"]: c.get("nome", c["id"]) for c in categorias}
    return {"cd1": "Geral"}

def tipo_opts():
    if tipos:
        return {t["id"]: t.get("nome", t["id"]) for t in tipos}
    return {"td1": "Despesa"}

def conta_opts():
    if contas:
        return {c["id"]: c.get("nome", c["id"]) for c in contas}
    return {"c1": "Conta Principal"}

def validar_item(item: dict) -> list:
    erros = []
    if float(item.get("valor", 0)) <= 0:
        erros.append("Valor deve ser positivo.")
    d = parse_date(item.get("data"))
    if d is None:
        erros.append("Data inválida.")
    if item.get("status") not in ["prevista", "pendente", "paga"]:
        erros.append("Status inválido.")
    # Parcelamento coerente
    parc = item.get("parcelamento")
    if parc:
        qtd = parc.get("qtd_parcelas", 0)
        if not isinstance(qtd, int) or qtd < 1:
            erros.append("Quantidade de parcelas deve ser um inteiro >= 1.")
    return erros

def gerar_parcelas_base(valor_total: float, qtd: int):
    """Distribui valor total em parcelas com ajuste de centavos na última."""
    base = round(valor_total / qtd, 2)
    valores = [base] * qtd
    soma = sum(valores)
    ajuste = round(valor_total - soma, 2)
    valores[-1] = round(valores[-1] + ajuste, 2)
    return valores

def gerar_recorrencias(data_inicial: date, freq: str, count: int):
    """Retorna lista de datas futuras conforme frequência."""
    dts = []
    d = data_inicial
    for i in range(count):
        dts.append(d)
        if freq == "mensal":
            # simplificação: adiciona ~30 dias (ou avançar mês via pandas)
            d = (pd.to_datetime(d) + pd.DateOffset(months=1)).date()
        elif freq == "semanal":
            d = d + timedelta(days=7)
        elif freq == "trimestral":
            d = (pd.to_datetime(d) + pd.DateOffset(months=3)).date()
        elif freq == "anual":
            d = (pd.to_datetime(d) + pd.DateOffset(years=1)).date()
        else:
            break
    return dts

# --------------------------------------------------
# Filtros / Visualização
# --------------------------------------------------
st.subheader("🔍 Filtros")

colf1, colf2, colf3, colf4 = st.columns(4)
dt_ini = colf1.date_input("Início", value=date.today().replace(day=1))
dt_fim = colf2.date_input("Fim", value=date.today())
cat_filter = colf3.selectbox("Categoria", options=["Todas"] + list(categoria_opts().values()))
status_filter = colf4.selectbox("Status", options=["Todos", "prevista", "pendente", "paga"])

def filtrar(ds):
    out = []
    for d in ds:
        ddata = parse_date(d.get("data"))
        if not ddata or ddata < dt_ini or ddata > dt_fim:
            continue
        if status_filter != "Todos" and d.get("status") != status_filter:
            continue
        # Map categoria_id -> nome
        cat_map = categoria_opts()
        cat_nome = cat_map.get(d.get("categoria_id"), d.get("categoria_id"))
        if cat_filter != "Todas" and cat_nome != cat_filter:
            continue
        if d.get("excluido") is True:
            continue
        out.append(d)
    return out

filtradas = filtrar(despesas)

# --------------------------------------------------
# KPI / Resumo
# --------------------------------------------------
st.subheader("📊 Resumo")
df = pd.DataFrame(filtradas) if filtradas else pd.DataFrame(columns=["valor","categoria_id","status","conta_id","recorrente"])
total = float(df["valor"].sum()) if not df.empty else 0.0
recorrentes_total = float(df[df["recorrente"] == True]["valor"].sum()) if not df.empty and "recorrente" in df.columns else 0.0
pendentes = float(df[df["status"] == "pendente"]["valor"].sum()) if not df.empty else 0.0

kc1, kc2, kc3 = st.columns(3)
kc1.metric("Total filtrado", fmt_brl(total))
kc2.metric("Recorrentes", fmt_brl(recorrentes_total))
kc3.metric("Pendentes", fmt_brl(pendentes))

st.divider()

# --------------------------------------------------
# Tabela com ações (Editar / Excluir)
# --------------------------------------------------
st.subheader("📋 Lançamentos filtrados")
if not filtradas:
    st.info("Nenhum lançamento encontrado para os filtros atuais.")
else:
    # Mostra o essencial
    table_cols = ["id", "data", "valor", "status", "categoria_id", "tipo_id", "conta_id", "observacoes", "tags"]
    df_show = pd.DataFrame([{k: d.get(k) for k in table_cols} for d in filtradas])
    # Formatação
    if not df_show.empty:
        df_show["valor"] = df_show["valor"].astype(float).round(2)
    st.dataframe(df_show, use_container_width=True)

    # Ações por ID
    st.write("### ✏️ Ações")
    col_a1, col_a2, col_a3 = st.columns([3, 3, 1])
    id_edit = col_a1.text_input("ID para editar")
    id_del = col_a2.text_input("ID para excluir")
    exec_btn = col_a3.button("Executar")

    if exec_btn:
        if id_del:
            alvo = next((x for x in despesas if x.get("id") == id_del), None)
            if not alvo:
                st.error(f"ID não encontrado para exclusão: {id_del}")
            else:
                remover(despesas, alvo)
                salvar(despesas, f"Remove lançamento {id_del}")
        elif id_edit:
            alvo = next((x for x in despesas if x.get("id") == id_edit), None)
            if not alvo:
                st.error(f"ID não encontrado para edição: {id_edit}")
            else:
                with st.expander(f"Editar lançamento {id_edit}", expanded=True):
                    # form de edição
                    cat_map = categoria_opts()
                    tipo_map = tipo_opts()
                    conta_map = conta_opts()

                    col_e1, col_e2, col_e3 = st.columns(3)
                    novo_valor = col_e1.number_input("Valor", min_value=0.01, value=float(alvo.get("valor", 0.0)))
                    nova_data = col_e2.date_input("Data", value=parse_date(alvo.get("data")) or date.today())
                    novo_status = col_e3.selectbox("Status", ["prevista","pendente","paga"], index=["prevista","pendente","paga"].index(alvo.get("status","prevista")))

                    col_e4, col_e5, col_e6 = st.columns(3)
                    nova_cat_nome = col_e4.selectbox("Categoria", list(cat_map.values()), index=list(cat_map.values()).index(cat_map.get(alvo.get("categoria_id"), list(cat_map.values())[0])))
                    novo_tipo_nome = col_e5.selectbox("Tipo", list(tipo_map.values()), index=list(tipo_map.values()).index(tipo_map.get(alvo.get("tipo_id"), list(tipo_map.values())[0])))
                    nova_conta_nome = col_e6.selectbox("Conta", list(conta_map.values()), index=list(conta_map.values()).index(conta_map.get(alvo.get("conta_id"), list(conta_map.values())[0])))

                    novas_obs = st.text_input("Observações", value=alvo.get("observacoes",""))
                    novas_tags = st.text_input("Tags (separadas por vírgula)", value=",".join(alvo.get("tags", [])))

                    salvar_edicao = st.button("Salvar edição")

                    if salvar_edicao:
                        # resolve os IDs de volta pelos nomes:
                        inv_cat = {v:k for k,v in cat_map.items()}
                        inv_tipo = {v:k for k,v in tipo_map.items()}
                        inv_conta = {v:k for k,v in conta_map.items()}

                        alvo["valor"] = float(novo_valor)
                        alvo["data"] = nova_data.isoformat()
                        alvo["status"] = novo_status
                        alvo["categoria_id"] = inv_cat.get(nova_cat_nome, alvo.get("categoria_id"))
                        alvo["tipo_id"] = inv_tipo.get(novo_tipo_nome, alvo.get("tipo_id"))
                        alvo["conta_id"] = inv_conta.get(nova_conta_nome, alvo.get("conta_id"))
                        alvo["observacoes"] = novas_obs
                        alvo["tags"] = [t.strip() for t in novas_tags.split(",") if t.strip()]

                        erros = validar_item(alvo)
                        if erros:
                            st.error("Erros: " + "; ".join(erros))
                        else:
                            atualizar(despesas, alvo)  # finance_core.update by id
                            salvar(despesas, f"Edit lançamento {alvo.get('id')}")

                    # Se parcelado, mostra grupo
                    group_id = alvo.get("group_id")
                    if group_id:
                        st.write("Parcelas do grupo:")
                        group_items = [x for x in despesas if x.get("group_id") == group_id]
                        gdf = pd.DataFrame(group_items)
                        if not gdf.empty:
                            gdf_show = gdf[["id","data","valor","status","observacoes"]].copy()
                            st.dataframe(gdf_show, use_container_width=True)

st.divider()

# --------------------------------------------------
# Novo Lançamento
# --------------------------------------------------
st.subheader("➕ Novo lançamento")

cat_map = categoria_opts()
tipo_map = tipo_opts()
conta_map = conta_opts()

with st.form("nova_despesa"):
    col1, col2, col3 = st.columns(3)
    valor = col1.number_input("Valor (R$)", min_value=0.01, step=0.01)
    data_ref = col2.date_input("Data", value=date.today())
    status = col3.selectbox("Status", ["prevista","pendente","paga"], index=0)

    col4, col5, col6 = st.columns(3)
    categoria_nome = col4.selectbox("Categoria", options=list(cat_map.values()))
    tipo_nome = col5.selectbox("Tipo", options=list(tipo_map.values()))
    conta_nome = col6.selectbox("Conta", options=list(conta_map.values()))

    observacoes = st.text_input("Observações")
    tags_input = st.text_input("Tags (separadas por vírgula)")

    st.markdown("### 🔁 Recorrência / Parcelamento (opcional)")
    rec_col1, rec_col2, rec_col3 = st.columns(3)
    usar_recorrencia = rec_col1.checkbox("Recorrente?")
    freq = rec_col2.selectbox("Frequência", options=["mensal","semanal","trimestral","anual"], index=0, disabled=not usar_recorrencia)
    qtd_rec = rec_col3.number_input("Quantidade de ocorrências", min_value=1, max_value=36, value=6, disabled=not usar_recorrencia)

    par_col1, par_col2 = st.columns(2)
    usar_parcelamento = par_col1.checkbox("Parcelado?")
    qtd_parcelas = par_col2.number_input("Qtd. parcelas", min_value=1, max_value=60, value=1, disabled=not usar_parcelamento)

    comprovante = st.text_input("Link de comprovante (opcional)")

    salvar_btn = st.form_submit_button("Salvar")

if salvar_btn:
    inv_cat = {v:k for k,v in cat_map.items()}
    inv_tipo = {v:k for k,v in tipo_map.items()}
    inv_conta = {v:k for k,v in conta_map.items()}

    base_item = {
        "id": novo_id("d"),
        "data": data_ref.isoformat(),
        "valor": float(valor),
        "categoria_id": inv_cat.get(categoria_nome, "cd1"),
        "tipo_id": inv_tipo.get(tipo_nome, "td1"),
        "conta_id": inv_conta.get(conta_nome, "c1"),
        "status": status,
        "recorrente": bool(usar_recorrencia),
        "parcelamento": None,
        "excluido": False,
        "observacoes": observacoes.strip(),
        "tags": [t.strip() for t in tags_input.split(",") if t.strip()],
        "comprovante_url": comprovante.strip() or None,
    }

    erros = validar_item(base_item)
    if erros:
        st.error("Erros: " + "; ".join(erros))
    else:
        items_to_create = []

        # Caso parcelamento
        if usar_parcelamento and int(qtd_parcelas) > 1:
            group_id = f"parcel-{uuid.uuid4().hex[:8]}"
            valores = gerar_parcelas_base(float(valor), int(qtd_parcelas))
            datas = []
            # parcelas mensais por padrão
            d = data_ref
            for i in range(int(qtd_parcelas)):
                datas.append(d)
                d = (pd.to_datetime(d) + pd.DateOffset(months=1)).date()

            for i in range(int(qtd_parcelas)):
                it = base_item.copy()
                it["id"] = novo_id("d")
                it["valor"] = valores[i]
                it["data"] = datas[i].isoformat()
                it["parcelamento"] = {
                    "qtd_parcelas": int(qtd_parcelas),
                    "parcela_num": i + 1
                }
                it["group_id"] = group_id
                items_to_create.append(it)
        else:
            items_to_create.append(base_item)

        # Caso recorrente (gera além do item base)
        if usar_recorrencia:
            dts = gerar_recorrencias(data_ref, freq, int(qtd_rec))
            # Se também parcelado, geralmente recorrência é aplicada no "item base", aqui vamos gerar itens iguais no futuro
            # (Você pode ajustar para regras específicas do seu fluxo)
            # Primeiro item já está em items_to_create; gerar demais
            for rd in dts[1:]:
                it = base_item.copy()
                it["id"] = novo_id("d")
                it["data"] = rd.isoformat()
                it["recorrente"] = True
                items_to_create.append(it)

        # Finalmente, criar todos e salvar
        for it in items_to_create:
            criar(despesas, it)

        msg = "Add despesa"
        if usar_parcelamento and int(qtd_parcelas) > 1:
            msg += f" (parcelado x{int(qtd_parcelas)})"
        if usar_recorrencia:
            msg += f" (recorrente {freq} x{int(qtd_rec)})"

        salvar(despesas, msg)
