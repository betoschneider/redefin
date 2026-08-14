# RedeFin

**Controle Financeiro e Balanceador de Carteira de Investimentos**

Aplicativo web com duas áreas integradas dentro da mesma aplicação:

- **Controle Financeiro**: lançamentos mensais, saldos, filtros, gráficos, gerenciamento de categorias, importação/exportação CSV e autenticação.
- **Carteira de Investimento**: acompanhamento de ativos B3, cotações via Yahoo Finance, metas de alocação, sugestão de aporte, página de gerenciamento de ativos e importação/exportação CSV.

O projeto usa **FastAPI**, **SQLAlchemy**, **SQLite**, **Alembic** e frontend em **HTML/CSS/JavaScript** sem framework.

---

## Funcionalidades

### Autenticação

- Cadastro de usuário com senha.
- Configuração de 2FA via Google Authenticator, com QR Code e chave manual.
- Login em duas etapas: senha e código TOTP.
- Redefinição de senha validada por TOTP.
- Login via Google OAuth por popup, com botão modernizado contendo o logo oficial do Google.
- Exibição automática da foto de perfil do Google no botão quando o usuário está logado no navegador.
- Sessão por cookie `session_token` e suporte a header `Authorization`.
- Limite opcional de criação de contas via variável `ACCOUNT_QUOTA`.

### Controle Financeiro

A área de **Controle Financeiro** é acessada pela aba homônima na barra de título. Logo abaixo do título há uma barra de subtítulo com o nome da área e o botão **Gerenciar Categorias**, que dá acesso à página de configuração de tipos e categorias.

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

- **Ano**: seleciona o ano dos lançamentos.
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
- **Cabeçalho do mês atual destacado** com cor de fundo diferenciada e borda inferior.
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

#### Insights de IA (Controle Financeiro)

- Geração de análise financeira via IA (OpenAI, Anthropic, Gemini ou DeepSeek) com base nos lançamentos do ano selecionado.
- **Caixa de diálogo opcional**: o usuário pode escrever uma pergunta (ex.: objetivo financeiro ou recomendação) que é adicionada ao prompt padrão da IA.
- Se a caixa estiver vazia, o insight é gerado apenas com o prompt padrão.

---

### Carteira de Investimento

Seção acessada pela aba **Carteira** na barra de título. A área possui uma barra de subtítulo com o nome, o status das cotações, botão de atualização e o botão **Gerenciar Carteira**.

A área da carteira possui uma leve variação visual (fundo sutilmente azulado no tema escuro, borda esquerda nos cards) para diferenciá-la da área de Controle Financeiro, funcionando tanto no tema claro quanto no escuro.

#### Métricas

- **Patrimônio total** — valor total da carteira com base nas cotações atuais.
  - `metric-delta`: diferença percentual entre o valor atual e o custo médio de compra (tooltip: custo total e data da consulta anterior).
  - `metric-delta-lastest`: diferença percentual entre o valor atual e o valor registrado na consulta anterior (tooltip: data da consulta anterior).
- Total de ativos monitorados.
- Soma das metas.

#### Tabela de Ativos

- Ativos ordenados pelo desvio da meta (menor para o maior).
- Colunas: Ativo, Empresa, Qtd, Preço atual, Total, Meta, % Atual, Desvio, Ramo, Grupo.
- Linhas coloridas por grupo do ativo.
- Cotações via `yfinance` com cache de 1 hora.
- Fallback para tickers B3/fracionários (ex: `PETR4F` → `PETR4.SA`).

#### Gráfico de Desvio da Meta

- Barras horizontais coloridas pela cor do grupo, sem bordas.
- Linha vertical no zero.

#### Evolução da Carteira

- **Histórico diário**: a cada consulta à API de portfólio é gravada uma linha por dia (tabela `investment_history`) com patrimônio total, yield (%) e data/hora. Se houver mais de uma consulta no mesmo dia, apenas a mais recente é mantida (upsert).
- **Gráfico misto**: patrimônio em área (eixo esquerdo, R$) + yield em linha (eixo direito, %), com filtro de período **6M / 12M / 24M / Tudo** aplicado no client.
- **Estado vazio**: enquanto não houver consultas, o gráfico exibe uma mensagem informativa.
- O gráfico é renderizado abaixo das métricas e atualizado ao ativar a aba, no refresh de cotações e após aportes/importações.

#### Gerenciamento de Carteira

Página acessada pelo botão **Gerenciar Carteira** no subtítulo da área de investimento, com:

- **Tabela editável** com todos os ativos: Empresa, Ativo (ticker), Quantidade, Meta (%), Ramo e Grupo — todas as colunas editáveis inline.
- **Adição** de novos ativos e **remoção** com confirmação.
- **Ordenação automática** por ticker (ativo).
- **Importação e exportação CSV** exclusivos desta página.
- **Salvar** os dados da carteira no servidor.
- **Disclaimer** na primeira visita, informando que o usuário ainda não possui ativos cadastrados, com redirecionamento automático para a página de gerenciamento.

#### Simulador de Aporte

- Input de valor a investir e quantidade de ativos.
- Sugestão automática priorizando os ativos com maior distância negativa da meta.
- Edição manual das cotas sugeridas.
- Cálculo de total sugerido, sobra e novo desvio após aporte.
- Checkbox de confirmação antes de atualizar a carteira.

#### CSV

- Importação/exportação CSV da carteira, disponível na página de **Gerenciamento de Carteira**.

#### Insights de IA (Carteira de Investimentos)

- Geração de análise da carteira via IA (OpenAI, Anthropic, Gemini ou DeepSeek) com base nos ativos e metas de alocação.
- **Caixa de diálogo opcional**: o usuário pode escrever uma pergunta (ex.: qual ativo priorizar no próximo aporte) que é adicionada ao prompt padrão da IA.
- Se a caixa estiver vazia, o insight é gerado apenas com o prompt padrão.

---

## Formatos CSV

### Lançamentos Financeiros (Controle Financeiro)

A exportação gera um **único arquivo CSV** com três seções: `TIPOS`, `CATEGORIAS` e `TRANSACOES`. A importação lê o mesmo formato (também aceita o formato antigo, apenas com a seção de lançamentos).

```csv
=== TIPOS ===
nome,is_protegido
Receita,True
Despesa,True
Investimento,False

=== CATEGORIAS ===
tipo,nome,valor,is_protegido
Receita,Remuneração,0.00,True
Despesa,Alimentação,35.00,False

=== TRANSACOES ===
Data,Item,Tipo,Categoria,Valor,Pago
01/01/2026,Salário,Receita,Trabalho,5000,True
01/01/2026,Aluguel,Despesa,Moradia,1500,False
```

Observações:

- A importação substitui todos os lançamentos existentes do usuário e atualiza/cria tipos e categorias conforme o arquivo.
- Tipos e categorias marcados como protegidos no sistema não são alterados pela importação.
- Se a seção `TRANSACOES` não estiver presente no arquivo, os lançamentos existentes são mantidos.
- Datas aceitas incluem `DD/MM/YYYY` e `YYYY-MM-DD`.
- `Pago` aceita valores como `True`, `False`, `1`, `0`, `pago` e `efetivado`.
- Tamanho máximo do arquivo: 5 MB.

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
app/
  main.py               App FastAPI, CORS, Auth Google e mount /static
  config.py             Config (.env), Engine, SessionLocal, Base
  models.py             Modelos SQLAlchemy (unificados)
  transactions.py       Router de transações + settings (tipos/categorias)
  investments.py        Router de investimentos + yfinance
  auth.py               Sessões e autenticação
  static/
    index.html
    carteira-investimento.html
    google_oauth_callback.html
    css/
      style.css
    js/
      app.js
alembic/
  env.py
  versions/
    bb8a7514b4ee_banco_unificado_v1.py   ← migração única (todas as tabelas)
data/
scripts/
  alembic_stamp_head_if_needed.py
  import_csv.py
.env
Dockerfile
docker-compose.yml
pyproject.toml
uv.lock
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

### 3. Instalar dependências

```bash
uv sync
```

### 4. Aplicar migrations

```bash
uv run alembic upgrade head
```

> Por padrão, o app usa `sqlite:///./data/controle_financeiro.db`.
>
> **Nota**: As migrations são aplicadas automaticamente no startup do servidor (`app/main.py`), então
> basta rodar o servidor. O `alembic upgrade head` manual é opcional. Bancos antigos criados por
> `create_all` (sem `alembic_version`) são detectados e marcados automaticamente antes do upgrade.

### 5. Rodar o servidor

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8520
```

Acesse: `http://127.0.0.1:8520`

Para desenvolvimento com reload automático:

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8520
```

---

## Variáveis de Ambiente

Crie ou edite `.env` conforme necessário:

```env
DATABASE_URL=sqlite:///./data/controle_financeiro.db
SECRET_KEY=sua_chave_secreta_aqui
GOOGLE_CLIENT_ID=seu_client_id_aqui
GOOGLE_CLIENT_SECRET=seu_client_secret_aqui
QUOTE_CACHE_TTL=3600
ACCOUNT_QUOTA=0
# COOKIE_SECURE=auto | 1 | 0
#   auto (padrão): cookie Secure apenas sobre HTTPS
#   1: força Secure (use quando o app estiver atrás de proxy TLS sem --proxy-headers)
#   0: nunca Secure (apenas desenvolvimento local)
COOKIE_SECURE=auto
```

Notas:

- `ACCOUNT_QUOTA=0` significa sem limite de criação de contas. Qualquer valor positivo limita o número máximo de usuários.
- `DATABASE_URL` é opcional no modo local; há fallback no código.
- `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` são usados no login Google OAuth (Authorization Code Flow).
  Obtenha ambos no [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
- `QUOTE_CACHE_TTL` define o cache de cotações do `yfinance` em segundos.
- `COOKIE_SECURE` controla o atributo `Secure` do cookie de sessão (ver comentário no `.env`). O cookie já é `HttpOnly` e `SameSite=Lax` por padrão.

---

## Docker

O `docker-compose.yml` monta:

- `./data:/app/data` para persistir o SQLite.

As migrations são aplicadas automaticamente no startup da aplicação (dentro do container),
então um banco do zero é criado com o schema completo via alembic.

> **Permissões do volume**: o container roda como usuário não-root de **UID 1000**.
> O diretório `./data` no host precisa ser gravável por esse UID. Se o dono do
> `./data` no host tiver outro UID, ajuste com:
>
> ```bash
> sudo chown -R 1000:1000 ./data
> ```
>
> (O `chmod 775 ./data` do passo abaixo só é suficiente se o UID 1000 for dono
> ou estiver no grupo do diretório.)

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
uv run python -m compileall app
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
| `GET` | `/api/transactions?ano=YYYY` | Lista lançamentos do ano |
| `POST` | `/api/transactions/bulk-save?ano=YYYY` | Salva todos os lançamentos do ano |
| `GET` | `/api/transactions/anos` | Lista anos com lançamentos |
| `GET` | `/api/transactions/download` | Exporta CSV completo |
| `POST` | `/api/transactions/upload` | Importa CSV (substitui dados) |
| `GET` | `/api/transactions/dropdown-data` | Tipos e categorias para dropdowns |
| `GET` | `/api/transactions/dashboard/categoria-comparativo` | Comparativo categorias vs metas |

### Configurações (Tipos e Categorias)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/settings/tipos` | Lista tipos (Receita, Despesa...) |
| `POST` | `/api/settings/tipos` | Cria novo tipo |
| `PUT` | `/api/settings/tipos/{id}` | Altera nome do tipo |
| `DELETE` | `/api/settings/tipos/{id}` | Remove tipo (se não protegido) |
| `GET` | `/api/settings/categorias` | Lista categorias do usuário |
| `POST` | `/api/settings/categorias` | Cria nova categoria |
| `PUT` | `/api/settings/categorias/{id}` | Altera categoria |
| `DELETE` | `/api/settings/categorias/{id}` | Remove categoria (se não protegida) |

### Carteira de Investimento

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/investments` | Lista ativos da carteira |
| `GET` | `/api/investments/portfolio` | Dados com cotações e cálculos |
| `POST` | `/api/investments/upload` | Importa CSV da carteira |
| `GET` | `/api/investments/download` | Exporta CSV da carteira |
| `POST` | `/api/investments/contribution` | Confirma aporte sugerido |

### Insights de IA

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/insights/financial` | Último insight financeiro gerado |
| `POST` | `/api/insights/financial/generate` | Gera insight financeiro (body opcional: `{"question": "..."}`) |
| `GET` | `/api/insights/investment` | Último insight de investimentos gerado |
| `POST` | `/api/insights/investment/generate` | Gera insight de investimentos (body opcional: `{"question": "..."}`) |

---

## Observações de Uso

- As abas **Controle Financeiro** e **Carteira** ficam na barra de título. Ao alternar, o subtítulo correspondente é exibido logo abaixo, e filtros/gráficos da outra área são ocultados.
- O botão **Gerenciar Categorias** aparece no subtítulo do Controle Financeiro e abre a página de configurações de tipos e categorias.
- O botão **Gerenciar Carteira** aparece no subtítulo da Carteira e abre a página de gerenciamento de ativos.
- Os cards **Saldo Total do Ano** sempre refletem o ano inteiro, independentemente do filtro de mês selecionado.
- O comparativo % do **Saldo Total do Ano Projetado** é calculado em relação ao Saldo Total Efetivo do ano anterior, carregado em background após o carregamento principal.
- O cache das cotações fica em memória; reiniciar o servidor limpa o cache.
- A consulta ao Yahoo Finance depende de conectividade e disponibilidade externa.
- Em caso de cache do navegador, os assets usam versão `?v=34`; incremente em `app/static/index.html` ao fazer deploy de mudanças estáticas.

---

## 🔒 Ajustes de Segurança Implementados

### Vulnerabilidades Críticas Corrigidas

1. **Login Google — `id_token` sem verificação de assinatura**: o token era apenas decodificado (base64) e checava-se somente o `aud`, o que permitia forjar um token com email arbitrário (account takeover). Agora o `id_token` é validado no Google (`oauth2.googleapis.com/tokeninfo`), conferindo **assinatura, `aud`, `iss` e `exp`** antes de autenticar.

2. **Login Google — `redirect_uri` derivado de input do usuário**: o `state` (origin) era usado diretamente para montar o `redirect_uri`, permitindo roubo do authorization code. Agora a origem é validada contra uma **allowlist fixa** (`REDIRECT_ORIGINS_PERMITIDOS`) antes de montar a URL.

3. **Cookie de Sessão sem `HttpOnly`**: o cookie `session_token` agora é `HttpOnly` + `SameSite=Lax` (+ `Secure` conforme `COOKIE_SECURE`), impedindo leitura via JS. O frontend não envia mais header `Authorization` — a autenticação é feita pelo cookie, e a verificação de sessão no carregamento usa o novo endpoint `GET /api/auth/status`.

4. **Sessões sem expiração**: as sessões em memória agora têm **TTL de 2h com renovação deslizante** (cada requisição autenticada estende a sessão) e são podadas automaticamente.

5. **Sem limite de taxa nos endpoints de autenticação**: implementado limitador em memória (janela deslizante) por IP em `register`, `login/step1`, `login/step2`, `reset-password` e `login/google` — impede força bruta e enumeração de contas.

6. **CORS permissivo**: removida a origem `https://google.com` do `allow_origins`; apenas domínios confiáveis permanecem (com `allow_credentials=True`).

### Vulnerabilidades Importantes Corrigidas

1. **API key de IA exposta em texto puro**: a chave agora é **mascarada** em todas as respostas de perfil (`••••abcd`). O frontend só envia `api_key` quando o usuário digita uma chave nova; campo vazio remove a chave; campo mascarado mantém a existente.

2. **Exclusão de conta incompleta**: `delete_account` agora também remove `investment_history` e `investment_metrics`, invalida a sessão e apaga o cookie.

3. **Sem política de senha**: senhas agora exigem **mínimo de 8 caracteres** no registro, na redefinição e na troca de senha.

4. **Mensagens de erro vazando detalhes internos**: erros do fluxo Google OAuth são logados no servidor e devolvidos com mensagem genérica ao client.

### Boas Práticas de Segurança

- **Hash de Senha com `bcrypt`**: as funções `hash_password` e `verify_password` utilizam `bcrypt`.
- **Autenticação de Dois Fatores (2FA) com TOTP**: registro, login em dois passos e redefinição de senha usam `pyotp`.
- **Validação de Entrada com Pydantic** em todos os endpoints.
- **Quota de Contas** via `ACCOUNT_QUOTA` para evitar esgotamento de recursos.
- **Escopo por usuário**: todas as consultas (incluindo o novo `investment_history`) são filtradas por `owner_id` (sem IDOR).
- **Autorização em todas as rotas**: todo endpoint de dados depende de `verificar_autenticacao`.

### Nota sobre sessões e limite de taxa em memória

Ambos vivem em memória: sessões são perdidas no restart e o limite de taxa é por processo. Para múltiplas instâncias ou maior robustez, migrar para Redis (ex.: `slowapi`/`fastapi-limiter` + sessões em Redis/PostgreSQL).

---

## 📚 Recursos Adicionais

- [OWASP Top 10](https://owasp.org/www-project-top-ten/): Lista das 10 vulnerabilidades de segurança mais críticas em aplicações web.
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/): Documentação oficial do FastAPI sobre segurança.
- [CORS MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS): Documentação sobre CORS e como configurá-lo corretamente.
- [bcrypt](https://pypi.org/project/bcrypt/): Documentação da biblioteca `bcrypt` para hash de senhas.
- [pyotp](https://pypi.org/project/pyotp/): Documentação da biblioteca `pyotp` para autenticação de dois fatores.
