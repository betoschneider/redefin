# Controle Financeiro Pessoal

Aplicativo web de controle financeiro pessoal com duas áreas isoladas dentro da mesma aplicação:

- **Controle Financeiro**: lançamentos mensais, saldos, filtros, gráficos, importação/exportação CSV e autenticação.
- **Carteira de Investimento**: acompanhamento de ativos B3, cotações via Yahoo Finance, metas de alocação, sugestão de aporte, importação/exportação CSV e auditoria.

O projeto usa **FastAPI**, **SQLAlchemy**, **SQLite**, **Alembic** e frontend em **HTML/CSS/JavaScript** sem framework.

---

## Funcionalidades

### Autenticação

- Cadastro de usuário com senha.
- Configuração de 2FA via Google Authenticator, com QR Code e chave manual.
- Login em duas etapas: senha e código TOTP.
- Redefinição de senha validada por TOTP.
- Login via Google OAuth por popup.
- Sessão por cookie `session_token` e suporte a header `Authorization`.
- Limite opcional de criação de contas via variável `ACCOUNT_QUOTA`.

### Controle Financeiro

#### Dashboard de Métricas

Quatro cards exibidos no topo da visão, sempre juntos:

| Card | O que mostra |
|---|---|
| **Saldo Projetado do Mês** | Receitas − demais tipos do mês atual (ou mês filtrado). Inclui delta % vs. mês anterior quando a visão é "Ano Completo". |
| **Saldo Efetivo do Mês** | Igual ao Projetado, mas apenas lançamentos com `pago = true`. |
| **Saldo Total do Ano Projetado** | Soma de todas as receitas − demais tipos considerando os 12 meses do ano. **Não é afetado pelo filtro de mês.** Inclui delta % comparado ao Saldo Total Efetivo do ano anterior. |
| **Saldo Total do Ano Efetivo** | Igual ao anterior, mas apenas valores efetivados. **Não é afetado pelo filtro de mês.** |

O delta % do **Saldo Total do Ano Projetado** é calculado em relação ao **Saldo Total Efetivo do ano anterior**, carregado automaticamente em segundo plano. O tooltip de cada delta exibe os valores de referência para contexto.

#### Gráfico de Evolução Mensal

- Posicionado **acima das métricas**, logo após os controles de navegação.
- Exibe receitas, despesas, investimentos e reservas mês a mês para o ano selecionado.

#### Filtros e Controles

Todos os filtros e ações ficam na mesma barra, acima da tabela:

- **Ano**: seleciona o ano dos lançamentos (janela de 4 anos).
- **Mês**: filtra a visão por mês específico ou mantém "Ano Completo". O filtro de mês **não** afeta os cards de Saldo Total do Ano.
- **Tipo**: filtra as linhas da tabela por Receita, Despesa, Investimento ou Reserva.
- **Categoria**: filtra as linhas da tabela por categoria.
- **+ Adicionar**: insere nova linha em branco no topo da tabela.
- **Propagar**: aparece quando um mês específico está selecionado; preenche meses seguintes com o valor do mês atual (apenas onde o valor for zero).
- **Exportar / Importar CSV**.
- **Salvar**: persiste todos os lançamentos no servidor.

#### Tabela de Lançamentos

- Edição inline de Item, Tipo, Categoria, Valor e status de pago (checkbox).
- Colunas de meses exibidas conforme filtro de Mês selecionado.
- **Cabeçalho do mês atual destacado** com cor de fundo diferenciada (roxo semitransparente) e borda inferior, facilitando a localização visual.
- Linhas coloridas por tipo (verde = Receita, vermelho = Despesa, azul = Investimento, amarelo = Reserva).
- Exclusão de linha com confirmação.

#### Detalhamento Econômico

Abaixo da tabela, com gráficos de:

- **Proporção por Categoria** (rosca).
- **Ranking de Itens** (barras horizontais).
- Filtro para exibir apenas valores efetivados.
- Seletor de tipo a explodir (Receita, Despesa, Investimento ou Reserva).

#### Outras Funcionalidades

- Propagação de valores do mês atual para meses seguintes.
- Replicação automática de estrutura do ano mais recente ao abrir ano atual/futuro sem dados.
- Tema claro/escuro persistido no navegador, com re-renderização automática dos gráficos.
- Importação/exportação CSV de lançamentos.

---

### Carteira de Investimento

Seção acessada pela aba **Carteira**, isolada dos controles do Controle Financeiro.

#### Métricas

- Patrimônio total.
- Total de ativos monitorados.
- Soma das metas.

#### Tabela de Ativos

- Ativos ordenados pelo desvio da meta (menor para o maior).
- Colunas: Ativo, Empresa, Qtd, Preço atual, Total, Meta, % Atual, Desvio, Ramo, Grupo.
- Linhas coloridas por grupo do ativo.
- Cotações via `yfinance` com cache de 1 hora.
- Fallback para tickers B3/fracionários (ex: `PETR4F` → `PETR4.SA`).

#### Gráfico de Desvio da Meta

- Barras horizontais coloridas pela cor do grupo.
- Linha vertical no zero.
- Borda indicando desvio positivo ou negativo.

#### Simulador de Aporte

- Input de valor a investir e quantidade de ativos.
- Sugestão automática priorizando os ativos com maior distância negativa da meta.
- Edição manual das cotas sugeridas.
- Cálculo de total sugerido, sobra e novo desvio após aporte.
- Checkbox de confirmação antes de atualizar a carteira.

#### CSV e Auditoria

- Importação/exportação CSV da carteira.
- Auditoria de ações relevantes registrada em `audit_logs`.

---

### Auditoria

Eventos registrados em `audit_logs`:

- Cadastro de conta.
- Login etapa 1 (senha).
- Login completo com 2FA.
- Login via Google.
- Cadastro via Google.
- Reset de senha.
- Logout.
- Importação de carteira.
- Confirmação de aporte.

---

## Formatos CSV

### Lançamentos Financeiros

Cabeçalho esperado:

```csv
Data,Item,Tipo,Categoria,Valor,Pago
```

Exemplo:

```csv
01/01/2026,Salário,Receita,Trabalho,5000,True
01/01/2026,Aluguel,Despesa,Moradia,1500,False
```

Observações:

- A importação substitui todos os lançamentos existentes do usuário.
- Datas aceitas incluem `DD/MM/YYYY` e `YYYY-MM-DD`.
- `Pago` aceita valores como `True`, `False`, `1`, `0`, `pago` e `efetivado`.
- Valores ausentes ou nulos são tratados como `0.0`.

### Carteira de Investimento

Cabeçalho esperado:

```csv
Empresa,Ativo,Quantidade,Meta,Ramo,Grupo
```

Exemplo:

```csv
Empresa,Ativo,Quantidade,Meta,Ramo,Grupo
Petrobras,PETR4F,55,2.5,Commodities e Materiais Básicos,Gigante Cíclica
Sanepar,SAPR4F,26,5.71,Utilidade Pública - Energia e Saneamento,Trio de Ferro
B3,B3SA3F,13,5.71,Financeiro / Seguros e Bolsa,Trio de Ferro
```

Observações:

- A importação remove os dados atuais da carteira do usuário antes de inserir o CSV.
- Também há suporte a cabeçalhos em inglês: `company,ticker,quantity,target,sector,group`.
- `Meta` pode usar ponto ou vírgula como separador decimal.

---

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic.
- **Banco**: SQLite.
- **Autenticação**: bcrypt, pyotp, Google OAuth.
- **Finanças/mercado**: yfinance.
- **Frontend**: HTML5, CSS customizado, JavaScript, Chart.js, FontAwesome.
- **Dependências**: uv.
- **Testes**: pytest.

---

## Estrutura Principal

```text
backend/app/
  main.py           Rotas FastAPI e montagem do frontend
  models.py         Modelos SQLAlchemy
  schemas.py        Schemas Pydantic
  crud.py           Operações de banco
  finance.py        Consulta/cache de cotações

frontend/
  index.html
  css/style.css
  js/app.js         Controle financeiro, auth, CSV e navegação
  js/charts.js      Gráficos do controle financeiro
  js/investments.js Carteira de investimento

alembic/versions/
  61f5ca4cd77f_create_initial_tables.py
  d191e4391174_add_owner_id_to_transactions.py
  7a9d3b1f4c2c_add_audit_logs_table.py
  8c2f1b4d5a7a_add_investment_assets_table.py
```

---

## Como Executar Localmente

### 1. Pré-requisitos

- Python 3.12+
- `uv`

Instalação do `uv`, caso necessário:

```bash
pip install uv
```

### 2. Entrar na pasta do projeto

Execute os comandos a partir da raiz do projeto:

```bash
cd /home/beto/projetos/controle-financeiro
```

> Se executado em outra pasta, o Python pode não encontrar o pacote `backend` e retornar `ModuleNotFoundError: No module named 'backend'`.

### 3. Instalar dependências

```bash
uv sync
```

### 4. Aplicar migrations

```bash
uv run alembic upgrade head
```

> Por padrão, o app local usa `sqlite:///./controle_financeiro.db`. No Docker, a variável `DATABASE_URL` aponta para `sqlite:///./data/controle_financeiro.db`.

### 5. Rodar o servidor

```bash
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8520
```

Acesse: `http://127.0.0.1:8520`

Para desenvolvimento com reload automático:

```bash
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8520
```

---

## Variáveis de Ambiente

Crie ou edite `.env` conforme necessário:

```env
ACCOUNT_QUOTA=0
DATABASE_URL=sqlite:///./controle_financeiro.db
```

Notas:

- `ACCOUNT_QUOTA=0` significa sem limite de criação de contas. Qualquer valor positivo limita o número máximo de usuários.
- `DATABASE_URL` é opcional no modo local; há fallback no código.
- O Google OAuth usa o Client ID configurado na meta tag `google-client-id` em `frontend/index.html`.

---

## Docker

O `docker-compose.yml` monta:

- `./data:/app/data` para persistir o SQLite.
- `./frontend:/app/frontend:ro` para refletir mudanças no frontend sem rebuild.

Subir a aplicação:

```bash
mkdir -p ./data
chmod 775 ./data
docker compose up --build -d
```

Acesse: `http://127.0.0.1:8520`

Parar:

```bash
docker compose down
```

---

## Testes e Validações

Rodar a suíte de testes:

```bash
PYTHONPATH=. uv run pytest -q
```

Verificar sintaxe Python:

```bash
uv run python -m compileall backend/app
```

Verificar sintaxe dos scripts frontend:

```bash
node --check frontend/js/app.js
node --check frontend/js/investments.js
```

---

## Endpoints Principais

### Autenticação

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/auth/register` | Cadastro de usuário |
| `POST` | `/api/auth/login/step1` | Login etapa 1 (senha) |
| `POST` | `/api/auth/login/step2` | Login etapa 2 (TOTP) |
| `POST` | `/api/auth/login/google` | Login via Google OAuth |
| `POST` | `/api/auth/reset-password` | Redefinição de senha |
| `POST` | `/api/auth/logout` | Logout |

### Controle Financeiro

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/transacoes?ano=YYYY` | Lista lançamentos do ano |
| `POST` | `/api/transacoes/bulk-save?ano=YYYY` | Salva todos os lançamentos do ano |
| `GET` | `/api/transacoes/download` | Exporta CSV completo |
| `POST` | `/api/transacoes/upload` | Importa CSV (substitui dados) |

### Carteira de Investimento

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/investments` | Lista ativos da carteira |
| `GET` | `/api/investments/portfolio` | Dados com cotações e cálculos |
| `POST` | `/api/investments/upload` | Importa CSV da carteira |
| `GET` | `/api/investments/download` | Exporta CSV da carteira |
| `POST` | `/api/investments/contribution` | Confirma aporte sugerido |

### Auditoria

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/audit-logs` | Lista eventos de auditoria |

---

## Observações de Uso

- A aba **Controle Financeiro** e a aba **Carteira** são áreas independentes; ao alternar, filtros e gráficos da outra área são ocultados.
- Os cards **Saldo Total do Ano** sempre refletem o ano inteiro, independentemente do filtro de mês selecionado.
- O comparativo % do **Saldo Total do Ano Projetado** é calculado em relação ao Saldo Total Efetivo do ano anterior, carregado em background após o carregamento principal.
- O cache das cotações fica em memória; reiniciar o servidor limpa o cache.
- A consulta ao Yahoo Finance depende de conectividade e disponibilidade externa.
- Em caso de cache do navegador, os assets usam versão `?v=12`; incremente em `frontend/index.html` ao fazer deploy de mudanças estáticas.
