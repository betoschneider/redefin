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


def _build_financial_prompt(db: Session, user: User) -> str:
    """Monta o prompt de análise financeira com os dados do usuário."""
    transacoes = (
        db.query(Transacao)
        .filter(Transacao.owner_id == user.id)
        .order_by(Transacao.ano.desc(), Transacao.mes.desc())
        .limit(100)
        .all()
    )

    if not transacoes:
        return "Nenhuma movimentação financeira encontrada para gerar insights."

    # Agrupa por ano/mês
    meses = {}
    for t in transacoes:
        chave = f"{t.ano}-{t.mes:02d}"
        if chave not in meses:
            meses[chave] = {"receita": 0, "despesa": 0, "investimento": 0, "reserva": 0}
        tipo = t.tipo.lower()
        if tipo in meses[chave]:
            meses[chave][tipo] += t.valor or 0

    resumo_meses = []
    total_receitas = 0.0
    total_despesas = 0.0
    total_investimentos = 0.0
    qtd_meses = 0

    for chave in sorted(meses.keys())[-6:]:  # Últimos 6 meses
        m = meses[chave]
        saldo = m["receita"] - m["despesa"] - m["investimento"]
        resumo_meses.append(
            f"- {chave}: Receita=R${m['receita']:.2f}, Despesa=R${m['despesa']:.2f}, "
            f"Investimento=R${m['investimento']:.2f}, Saldo Final Líquido=R${saldo:.2f}"
        )
        total_receitas += m["receita"]
        total_despesas += m["despesa"]
        total_investimentos += m["investimento"]
        qtd_meses += 1

    media_receita = total_receitas / qtd_meses if qtd_meses > 0 else 0
    media_despesa = total_despesas / qtd_meses if qtd_meses > 0 else 0
    media_investimento = total_investimentos / qtd_meses if qtd_meses > 0 else 0
    taxa_investimento_media = (total_investimentos / total_receitas * 100) if total_receitas > 0 else 0.0
    taxa_poupanca_media = ((total_receitas - total_despesas) / total_receitas * 100) if total_receitas > 0 else 0.0

    # Categorias mais frequentes (apenas despesas)
    categorias = {}
    for t in transacoes:
        if t.categoria and t.tipo.lower() == "despesa":
            categorias[t.categoria] = categorias.get(t.categoria, 0) + (t.valor or 0)
    top_categorias = sorted(categorias.items(), key=lambda x: -x[1])[:5]
    cat_text = ", ".join([f"{cat}=R${v:.2f}" for cat, v in top_categorias])

    # --- Análise de Metas de Categorias ---
    # Carrega categorias cadastradas do usuário com suas metas (campo valor)
    categorias_cadastradas = db.query(Categoria).filter(Categoria.owner_id == user.id).all()
    mapa_metas = {c.nome.lower(): c.valor for c in categorias_cadastradas}

    # Soma o total por categoria de despesa e a remuneração total nos meses consolidados
    meses_resumo_chaves = set(sorted(meses.keys())[-6:])
    categorias_despesas_valores = {}
    remuneracao_acumulada = 0.0

    for t in transacoes:
        chave_t = f"{t.ano}-{t.mes:02d}"
        if chave_t not in meses_resumo_chaves:
            continue

        valor = t.valor or 0.0
        if t.tipo.lower() == "despesa" and t.categoria:
            cat_key = t.categoria.strip()
            categorias_despesas_valores[cat_key] = categorias_despesas_valores.get(cat_key, 0.0) + valor
        elif t.tipo.lower() == "receita" and t.categoria and t.categoria.strip().lower() == "remuneração":
            remuneracao_acumulada += valor

    linhas_metas = []
    for cat_nome, cat_valor in categorias_despesas_valores.items():
        meta = mapa_metas.get(cat_nome.lower(), 0.0)
        # Analisamos apenas se houver meta configurada (> 0)
        if meta > 0:
            if remuneracao_acumulada > 0:
                pct_gasto = (cat_valor / remuneracao_acumulada) * 100
            else:
                pct_gasto = 0.0

            desvio = ((pct_gasto - meta) / meta) * 100
            linhas_metas.append(
                f"- Categoria: {cat_nome} | Meta: {meta:.1f}% da Remuneração | Gasto Real: R${cat_valor:.2f} ({pct_gasto:.2f}%) | Desvio: {desvio:+.1f}%"
            )

    texto_metas = ""
    if linhas_metas:
        texto_metas = "\n**Comparativo de Metas de Gastos por Categoria (Metas em % da Remuneração vs Gasto Real):**\n" + "\n".join(linhas_metas) + "\n"

    prompt = (
        "Você é um planejador financeiro pessoal altamente capacitado. Analise os dados financeiros do usuário nos últimos meses e gere insights profundos, práticos e acionáveis.\n\n"
        f"**DADOS CONSOLIDADOS (Últimos {qtd_meses} meses analisados):**\n"
        f"- Média Mensal: Receita = R${media_receita:.2f} | Despesas = R${media_despesa:.2f} | Investimentos = R${media_investimento:.2f}\n"
        f"- Taxa Média de Poupança (Receita - Despesas): {taxa_poupanca_media:.2f}%\n"
        f"- Taxa Média de Investimento Direto: {taxa_investimento_media:.2f}%\n\n"
        f"**Histórico Mensal Detalhado:**\n"
        + "\n".join(resumo_meses)
        + f"\n\n**Top 5 Maiores Categorias de Despesas:**\n{cat_text if cat_text else 'Nenhuma despesa categorizada.'}\n"
        + texto_metas
        + "\n"
        "**DIRETRIZES DA ANÁLISE:**\n"
        "Com base nesses dados, forneça uma análise estruturada contendo:\n"
        "1. **Diagnóstico da Saúde Financeira**: Analise o balanço entre receitas, despesas e investimentos. O usuário está gastando mais do que ganha? A taxa de poupança está saudável? Como está a evolução do saldo líquido?\n"
        "2. **Tendências e Pontos de Atenção (Riscos)**: Identifique se há um crescimento nas despesas ao longo dos meses ou se alguma categoria de gasto está consumindo uma parcela desproporcional do orçamento.\n"
        "3. **Análise de Metas por Categoria**: Verifique o comparativo de metas enviadas. Aponte claramente quais categorias estouraram o orçamento planejado (desvio positivo) e quais ficaram sob controle. Sugira ações para trazer as categorias estouradas de volta à meta.\n"
        "4. **Metas e Recomendações Práticas**: Proponha 3 a 4 ações concretas, por exemplo: sugestão de corte em categorias específicas, indicação de aumento na taxa de investimento (ex: mirar em guardar 20% se estiver abaixo), ou estratégias para conter o aumento de gastos se detectada tendência de alta.\n\n"
        "Seja direto, encorajador, use tópicos e formate a resposta de maneira elegante usando Markdown."
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
    db: Session = Depends(get_db),
    username: str = Depends(verificar_autenticacao),
):
    """Retorna o último insight financeiro gerado."""
    user = _get_user(db, username)
    insight = (
        db.query(FinancialInsight)
        .filter(FinancialInsight.owner_id == user.id)
        .order_by(FinancialInsight.created_at.desc())
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
    db: Session = Depends(get_db),
    username: str = Depends(verificar_autenticacao),
):
    """Gera um novo insight financeiro usando IA."""
    user = _get_user(db, username)
    prompt = _build_financial_prompt(db, user)
    content = _call_ai(prompt, user.ai_provider, user.api_key)

    insight = FinancialInsight(content=content, owner_id=user.id)
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
