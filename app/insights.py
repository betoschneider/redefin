import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import verificar_autenticacao
from app.config import get_db
from app.models import (
    Categoria,
    FinancialInsight,
    InvestmentAsset,
    InvestmentInsight,
    InvestmentTransaction,
    Transacao,
    User,
)
from app.transactions import get_user_by_username
from app.investments import _fetch_quote

router = APIRouter(prefix="/api/insights", tags=["Insights"])


def _get_user(db: Session, username: str) -> User:
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return user


def _call_ai(prompt: str, provider: Optional[str], api_key: Optional[str]) -> str:
    """Chama a API do provedor de IA selecionado e retorna o texto gerado."""
    if not provider or not api_key:
        return (
            "⚠️ **Provedor de IA não configurado.**\n\n"
            "Acesse o **Painel de Controle** (ícone de engrenagem no cabeçalho) "
            "para configurar seu provedor de IA e chave de API antes de gerar insights."
        )

    provider = provider.lower()

    if provider == "openai":
        return _call_openai(prompt, api_key)
    elif provider == "anthropic":
        return _call_anthropic(prompt, api_key)
    elif provider == "gemini":
        return _call_gemini(prompt, api_key)
    elif provider == "deepseek":
        return _call_deepseek(prompt, api_key)
    else:
        return f"Provedor '{provider}' não suportado. Use: OpenAI, Anthropic, Gemini ou DeepSeek."


def _call_openai(prompt: str, api_key: str) -> str:
    import httpx

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "Você é um assistente especializado em finanças pessoais e investimentos. "
                        "Responda em português do Brasil de forma clara e concisa.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 1000,
                "temperature": 0.7,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro ao chamar OpenAI: {str(e)}"


def _call_anthropic(prompt: str, api_key: str) -> str:
    import httpx

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Você é um assistente especializado em finanças pessoais e investimentos. Responda em português do Brasil de forma clara e concisa.\n\n{prompt}",
                    }
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    except Exception as e:
        return f"Erro ao chamar Anthropic: {str(e)}"


def _call_gemini(prompt: str, api_key: str) -> str:
    import httpx

    try:
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"Você é um assistente especializado em finanças pessoais e investimentos. Responda em português do Brasil de forma clara e concisa.\n\n{prompt}"
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": 1000,
                    "temperature": 0.7,
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Erro ao chamar Gemini: {str(e)}"


def _call_deepseek(prompt: str, api_key: str) -> str:
    import httpx

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "Você é um assistente especializado em finanças pessoais e investimentos. "
                        "Responda em português do Brasil de forma clara e concisa.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 1000,
                "temperature": 0.7,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro ao chamar DeepSeek: {str(e)}"


def _build_financial_prompt(db: Session, user: User, ano: Optional[int] = None) -> str:
    """Monta o prompt de análise financeira com os dados do usuário.

    Regras temporais:
    - Meses passados: considera apenas efetivados (pago=True)
    - Meses futuros: considera apenas previstos (pago=False)
    - Mês atual: considera ambos (efetivado + previsto)
    """
    if not ano:
        ano = datetime.now().year

    # Busca TODAS as transações do ano (sem limit)
    transacoes = (
        db.query(Transacao)
        .filter(Transacao.owner_id == user.id, Transacao.ano == ano)
        .order_by(Transacao.mes, Transacao.item)
        .all()
    )

    if not transacoes:
        return "Nenhuma movimentação financeira encontrada para gerar insights."

    now = datetime.now()
    mes_atual = now.month if now.year == ano else 12

    # Filtra transações pelas regras temporais e organiza em tabela
    linhas_tabela = []
    meses_agregados = {}
    categorias_despesa = {}
    categorias_todas = {}
    total_receitas = 0.0
    total_despesas = 0.0
    total_investimentos = 0.0
    total_reservas = 0.0

    for t in transacoes:
        # Aplica regra temporal
        if t.mes < mes_atual:
            # Mês passado: só efetivado
            if not t.pago:
                continue
            status = "Efetivado"
        elif t.mes > mes_atual:
            # Mês futuro: só previsto
            if t.pago:
                continue
            status = "Previsto"
        else:
            # Mês atual: ambos
            status = "Efetivado" if t.pago else "Previsto"

        valor = t.valor or 0.0
        tipo = t.tipo.lower()

        # Linha detalhada da tabela
        linhas_tabela.append(
            f"| {t.mes:02d}/{ano} | {t.item[:40]:40s} | {t.categoria[:30]:30s} | {t.tipo[:15]:15s} | R${valor:>10.2f} | {status:11s} |"
        )

        # Agrega por mês
        chave_mes = t.mes
        if chave_mes not in meses_agregados:
            meses_agregados[chave_mes] = {"receita": 0.0, "despesa": 0.0, "investimento": 0.0, "reserva": 0.0}
        if tipo in meses_agregados[chave_mes]:
            meses_agregados[chave_mes][tipo] += valor

        # Categorias de despesa
        if tipo == "despesa" and t.categoria:
            categorias_despesa[t.categoria] = categorias_despesa.get(t.categoria, 0.0) + valor

        # Todas as categorias
        if t.categoria:
            chave_cat = f"{t.tipo}:{t.categoria}"
            categorias_todas[chave_cat] = categorias_todas.get(chave_cat, 0.0) + valor

        # Totais
        if tipo == "receita":
            total_receitas += valor
        elif tipo == "despesa":
            total_despesas += valor
        elif tipo == "investimento":
            total_investimentos += valor
        elif tipo == "reserva":
            total_reservas += valor

    # --- Monta o resumo mensal ---
    resumo_meses = []
    for mes in range(1, 13):
        if mes in meses_agregados:
            m = meses_agregados[mes]
            saldo = m["receita"] - m["despesa"] - m["investimento"] - m["reserva"]
            indicador = "◉ ATUAL" if mes == mes_atual else ("○ PASSADO" if mes < mes_atual else "◎ FUTURO")
            resumo_meses.append(
                f"| {indicador:10s} | {mes:02d}/{ano} | Receita=R${m['receita']:>10.2f} | Despesa=R${m['despesa']:>10.2f} | Investimento=R${m['investimento']:>10.2f} | Reserva=R${m['reserva']:>10.2f} | Saldo=R${saldo:>10.2f} |"
            )

    # --- Metas de categorias ---
    categorias_cadastradas = db.query(Categoria).filter(Categoria.owner_id == user.id).all()
    mapa_metas = {c.nome.lower(): c.valor for c in categorias_cadastradas}

    # Calcula % de cada categoria de despesa em relação à receita total
    linhas_metas = []
    for cat_nome, cat_valor in sorted(categorias_despesa.items(), key=lambda x: -x[1]):
        meta = mapa_metas.get(cat_nome.lower(), 0.0)
        pct_receita = (cat_valor / total_receitas * 100) if total_receitas > 0 else 0.0
        if meta > 0:
            desvio = pct_receita - meta
            alerta = "🔴 ACIMA DA META" if desvio > 0 else "🟢 DENTRO DA META"
            linhas_metas.append(
                f"| {cat_nome:30s} | Gasto R${cat_valor:>10.2f} | {pct_receita:>5.1f}% da Receita | Meta: {meta:.1f}% | Desvio: {desvio:+.1f}pp | {alerta:20s} |"
            )
        else:
            linhas_metas.append(
                f"| {cat_nome:30s} | Gasto R${cat_valor:>10.2f} | {pct_receita:>5.1f}% da Receita | Meta: --- | --- | --- |"
            )

    texto_metas = ""
    if linhas_metas:
        texto_metas = (
            "\n**📊 Análise de Metas por Categoria de Despesa (% da Receita Total):**\n"
            "| Categoria                       | Valor Gasto       | % da Receita | Meta   | Desvio   | Status                |\n"
            "|---------------------------------|-------------------|-------------|--------|----------|-----------------------|\n"
            + "\n".join(linhas_metas)
            + "\n"
        )

    # --- Top categorias ---
    top_receitas = sorted(
        [(k.split(":")[1], v) for k, v in categorias_todas.items() if k.startswith("receita:")],
        key=lambda x: -x[1]
    )[:3]
    top_despesas = sorted(categorias_despesa.items(), key=lambda x: -x[1])[:5]

    texto_receitas = ", ".join([f"{cat}=R${v:.2f}" for cat, v in top_receitas]) if top_receitas else "Nenhuma"
    texto_despesas = ", ".join([f"{cat}=R${v:.2f}" for cat, v in top_despesas]) if top_despesas else "Nenhuma"

    saldo_anual = total_receitas - total_despesas - total_investimentos - total_reservas
    taxa_poupanca = ((total_receitas - total_despesas) / total_receitas * 100) if total_receitas > 0 else 0.0
    taxa_investimento = (total_investimentos / total_receitas * 100) if total_receitas > 0 else 0.0

    prompt = (
        "Você é um planejador financeiro pessoal altamente capacitado. "
        "Analise os dados financeiros do usuário e gere insights profundos, práticos e acionáveis.\n\n"
        f"**📋 DADOS DO ANO {ano}**\n\n"
        f"**Totais Acumulados do Ano:**\n"
        f"| Indicador               | Valor           |\n"
        f"|-------------------------|-----------------|\n"
        f"| Receita Total           | R${total_receitas:>10.2f} |\n"
        f"| Despesa Total           | R${total_despesas:>10.2f} |\n"
        f"| Investimento Total      | R${total_investimentos:>10.2f} |\n"
        f"| Reserva Total           | R${total_reservas:>10.2f} |\n"
        f"| Saldo Líquido Anual     | R${saldo_anual:>10.2f} |\n"
        f"| Taxa de Poupança        | {taxa_poupanca:>9.2f}% |\n"
        f"| Taxa de Investimento    | {taxa_investimento:>9.2f}% |\n\n"
        f"**📅 Resumo por Mês (○=Efetivado, ◉=Atual, ◎=Previsto):**\n"
        "| Indicador   | Mês      | Receita         | Despesa         | Investimento     | Reserva          | Saldo            |\n"
        "|-------------|----------|-----------------|-----------------|------------------|------------------|------------------|\n"
        + "\n".join(resumo_meses)
        + f"\n\n"
        f"**🔝 Top 3 Fontes de Receita:**\n{texto_receitas}\n\n"
        f"**🔝 Top 5 Categorias de Despesa:**\n{texto_despesas}\n\n"
        + texto_metas
        + "\n"
        "**📄 TABELA DETALHADA DE LANÇAMENTOS:**\n"
        "Abaixo estão todos os lançamentos considerados na análise (já filtrados pelas regras temporais: "
        "meses passados mostram apenas efetivados, meses futuros mostram apenas previstos, mês atual mostra ambos).\n\n"
        "```\n"
        "| Mês     | Item                                      | Categoria                     | Tipo            | Valor         | Status       |\n"
        "|---------|-------------------------------------------|-------------------------------|-----------------|---------------|--------------|\n"
        + "\n".join(linhas_tabela)
        + "\n```\n\n"
        "**DIRETRIZES DA ANÁLISE:**\n"
        "Com base EXCLUSIVAMENTE nos dados reais fornecidos acima, produza uma análise estruturada:\n\n"
        "1. **Diagnóstico da Saúde Financeira**: Analise o balanço receitas vs despesas vs investimentos. "
        "O usuário está gastando mais do que ganha? A taxa de poupança está saudável? "
        "Use valores CONCRETOS dos dados fornecidos (não invente valores).\n\n"
        "2. **Tendências e Riscos**: Identifique tendências reais nos dados. "
        "Há crescimento de despesas? Alguma categoria consome % excessivo? "
        "Destaque valores EXATOS das categorias problemáticas.\n\n"
        "3. **Análise de Metas**: Compare os gastos reais com as metas configuradas. "
        "Aponte quais categorias estão dentro ou fora da meta, usando os percentuais fornecidos.\n\n"
        "4. **Recomendações Práticas**: 3-4 ações concretas baseadas nos dados. "
        "Sugira cortes em categorias específicas com valores factíveis, "
        "proponha metas de investimento, ou estratégias para equilibrar o orçamento.\n\n"
        "**IMPORTANTE:**\n"
        "- Baseie-se APENAS nos números fornecidos acima\n"
        "- NÃO invente valores, meses ou categorias que não estão na tabela\n"
        "- Seja direto, use tópicos e formate em Markdown elegante\n"
        "- A análise deve refletir EXATAMENTE o que os dados mostram"
    )
    return prompt


def _build_investment_prompt(db: Session, user: User) -> str:
    """Monta o prompt de análise de investimentos com os dados do usuário."""
    ativos = (
        db.query(InvestmentAsset)
        .filter(InvestmentAsset.owner_id == user.id)
        .all()
    )

    if not ativos:
        return "Nenhum ativo de investimento encontrado para gerar insights."

    # Calcula os valores com base na cotação atual
    detalhes_ativos = []
    total_mercado = 0.0
    total_custo = 0.0

    for a in ativos:
        qtd = a.quantity or 0
        preco_compra = a.purchase_price or 0.0
        custo_total = qtd * preco_compra
        total_custo += custo_total

        # Preço atual de mercado (cotação do Yahoo Finance)
        preco_atual = _fetch_quote(a.ticker)
        if preco_atual is None or preco_atual <= 0:
            preco_atual = preco_compra

        valor_mercado = qtd * preco_atual
        total_mercado += valor_mercado

        detalhes_ativos.append({
            "ticker": a.ticker,
            "company": a.company,
            "quantity": qtd,
            "purchase_price": preco_compra,
            "current_price": preco_atual,
            "market_value": valor_mercado,
            "target": a.target or 0.0,
            "sector": a.sector or "Não informado",
            "group": a.group or "Não informado"
        })

    linhas_ativos = []
    for d in detalhes_ativos:
        pct_atual = (d["market_value"] / total_mercado * 100) if total_mercado > 0 else 0.0
        desvio = pct_atual - d["target"]
        linhas_ativos.append(
            f"- Ativo: {d['ticker']} ({d['company']}) | Grupo: {d['group']} | Setor: {d['sector']}\n"
            f"  Qtd: {d['quantity']} cotas | PM: R${d['purchase_price']:.2f} | Preço Atual: R${d['current_price']:.2f}\n"
            f"  Vl. Atual: R${d['market_value']:.2f} | Part. Atual: {pct_atual:.2f}% | Meta: {d['target']:.2f}% | Desvio: {desvio:+.2f}%"
        )

    # Transações recentes
    txs = (
        db.query(InvestmentTransaction)
        .filter(InvestmentTransaction.owner_id == user.id)
        .order_by(InvestmentTransaction.id.desc())
        .limit(10)
        .all()
    )
    tx_text = ""
    if txs:
        tx_text = "\n**Últimas transações de compra realizadas:**\n" + "\n".join(
            [f"- {tx.ticker}: {tx.quantity} cotas a R${tx.purchase_price:.2f}" for tx in txs]
        )

    yield_pct = ((total_mercado / total_custo - 1) * 100) if total_custo > 0 else 0.0

    prompt = (
        "Você é um assistente especializado em investimentos de renda variável focado em balanceamento de ativos (Asset Allocation) na B3.\n"
        "Analise a carteira de investimentos abaixo e forneça insights práticos e objetivos.\n\n"
        f"**DADOS DA CARTEIRA:**\n"
        f"- Valor Total de Mercado atual: R${total_mercado:.2f}\n"
        f"- Custo Total de Aquisição: R${total_custo:.2f}\n"
        f"- Rendimento da Carteira: {yield_pct:+.2f}%\n\n"
        "**Composição dos Ativos (com metas de balanceamento e desvios):**\n"
        + "\n".join(linhas_ativos)
        + tx_text
        + "\n\n"
        "**DIRETRIZES IMPORTANTES PARA A ANÁLISE:**\n"
        "1. Esta carteira é focada em BALANCEAMENTO DE ATIVOS DA B3 (ações, FIIs, ETFs, etc.).\n"
        "2. NUNCA fale sobre renda fixa (como Selic, Tesouro Direto, CDB, LCI, LCA ou poupança). O foco do usuário para essa carteira é estritamente renda variável e rebalanceamento dela.\n"
        "3. Identifique quais ativos estão mais subalocados (com maior desvio negativo, ou seja, onde a Alocação Atual está abaixo da Meta) e sugira priorizá-los nos próximos aportes para ajudar a reequilibrar a carteira.\n"
        "4. A análise deve ser prática, objetiva, livre de jargões desnecessários, organizada em tópicos claros e formatada em Markdown.\n\n"
        "**ESTRUTURA DA RESPOSTA:**\n"
        "1. **Análise de Alocação**: Resumo de como os ativos estão distribuídos em comparação com as metas estabelecidas.\n"
        "2. **Sugestão para os Próximos Aportes**: Indique claramente quais ativos devem ser priorizados nos próximos aportes com base nos desvios negativos, justificando de forma simples.\n"
        "3. **Riscos e Concentração**: Aponte se há algum ativo muito sobrealocado (desvio positivo alto) ou concentração excessiva em algum setor/grupo.\n"
        "4. **Recomendações Práticas**: Ações de rebalanceamento inteligentes (priorizar aportes nos subalocados em vez de vender ativos, minimizando custos fiscais)."
    )
    return prompt


# --- Endpoints de Insights Financeiros ---


class InsightResponse(BaseModel):
    id: int
    content: str
    created_at: str


@router.get("/financial", response_model=InsightResponse)
def get_financial_insight(
    ano: Optional[int] = None,
    db: Session = Depends(get_db),
    username: str = Depends(verificar_autenticacao),
):
    """Retorna o último insight financeiro gerado."""
    user = _get_user(db, username)
    query = db.query(FinancialInsight).filter(FinancialInsight.owner_id == user.id)
    if ano:
        query = query.filter(FinancialInsight.ano == ano)
    insight = (
        query.order_by(FinancialInsight.created_at.desc())
        .first()
    )
    if not insight:
        return InsightResponse(
            id=-1,
            content="Nenhum insight gerado ainda. Clique em 'Gerar Insights' para começar.",
            created_at="",
        )
    return InsightResponse(
        id=insight.id,
        content=insight.content,
        created_at=insight.created_at.isoformat(),
    )


@router.post("/financial/generate", response_model=InsightResponse)
def generate_financial_insight(
    ano: Optional[int] = None,
    db: Session = Depends(get_db),
    username: str = Depends(verificar_autenticacao),
):
    """Gera um novo insight financeiro usando IA."""
    user = _get_user(db, username)
    prompt = _build_financial_prompt(db, user, ano=ano)
    content = _call_ai(prompt, user.ai_provider, user.api_key)

    insight = FinancialInsight(content=content, owner_id=user.id, ano=ano)
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return InsightResponse(
        id=insight.id,
        content=insight.content,
        created_at=insight.created_at.isoformat(),
    )


# --- Endpoints de Insights de Investimentos ---


@router.get("/investment", response_model=InsightResponse)
def get_investment_insight(
    db: Session = Depends(get_db),
    username: str = Depends(verificar_autenticacao),
):
    """Retorna o último insight de investimentos gerado."""
    user = _get_user(db, username)
    insight = (
        db.query(InvestmentInsight)
        .filter(InvestmentInsight.owner_id == user.id)
        .order_by(InvestmentInsight.created_at.desc())
        .first()
    )
    if not insight:
        return InsightResponse(
            id=-1,
            content="Nenhum insight gerado ainda. Clique em 'Gerar Insights' para começar.",
            created_at="",
        )
    return InsightResponse(
        id=insight.id,
        content=insight.content,
        created_at=insight.created_at.isoformat(),
    )


@router.post("/investment/generate", response_model=InsightResponse)
def generate_investment_insight(
    db: Session = Depends(get_db),
    username: str = Depends(verificar_autenticacao),
):
    """Gera um novo insight de investimentos usando IA."""
    user = _get_user(db, username)
    prompt = _build_investment_prompt(db, user)
    content = _call_ai(prompt, user.ai_provider, user.api_key)

    insight = InvestmentInsight(content=content, owner_id=user.id)
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return InsightResponse(
        id=insight.id,
        content=insight.content,
        created_at=insight.created_at.isoformat(),
    )
