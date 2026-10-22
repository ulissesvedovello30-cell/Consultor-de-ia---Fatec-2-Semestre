# Consultor Fatec — site, API, MySQL e Gemini

Versão preparada em 22/10/2026. Python 3.12 ou superior. O ZIP inclui frontend e backend na mesma aplicação. Não é necessário Node para usar o site.

## Começar pelo teste no navegador

Extraia em uma pasta nova. No terminal do VS Code, dentro dessa pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe iniciar.py
```

Escolha **1 — Demonstração**. O servidor abre o navegador quando estiver pronto. Se isso não acontecer, acesse **http://127.0.0.1:8000**. Mantenha o terminal aberto; `Ctrl+C` encerra o serviço.

O modo 1 usa SQLite real via SQLAlchemy, documentos fictícios e recuperação lexical, sem Gemini, MySQL, downloads de modelos ou credenciais. Não é equivalente à busca semântica. Há um aviso permanente de demonstração no site. A consulta pública funciona imediatamente e não exige login.

Para testar o painel administrativo, encerre o servidor, execute o comando abaixo e inicie novamente:

```powershell
.\.venv\Scripts\python.exe preparar_admin.py
```

O comando pede usuário e senha, deriva um hash scrypt e grava somente o hash no `.env`. Não há senha padrão. No site, entre em **Administração**. As perguntas continuam abertas ao público.

No VS Code também é possível selecionar o interpretador `.venv`, abrir `iniciar.py` e usar **Run Python File in Terminal**, ou usar as configurações de F5 incluídas em `.vscode/launch.json`.

## Configurar o modo oficial

1. Copie `.env.example` para `.env` **somente se ainda não existir um `.env`**. Preserve as configurações já preenchidas pelo comando do administrador.
2. Preencha `MYSQL_HOST`, `MYSQL_PORTA`, `MYSQL_USUARIO`, `MYSQL_SENHA` e `MYSQL_DATABASE` com a conexão ao banco existente.
3. Faça backup do banco e execute `infra/schema_rag.sql` nele, por exemplo no phpMyAdmin. O script cria apenas `rag_documento`, `rag_versao` e `rag_trecho`. Não altera cadastro de alunos ou notas.
4. Preencha `GEMINI_API_KEY`. A chave nunca vai para HTML, JavaScript, cookie ou resposta HTTP.
5. Liste os modelos disponíveis à sua chave:

```powershell
.\.venv\Scripts\python.exe verificar_gemini.py
```

6. Copie um ID compatível com `generateContent` para `GEMINI_MODELO`. O campo fica vazio de propósito: disponibilidade e ciclo de vida dependem da conta e do provedor. Não usamos um nome presumido. `GEMINI_EMBEDDING` vem configurado como `gemini-embedding-001`; confirme a disponibilidade na sua conta.
7. Configure o administrador com `preparar_admin.py` e o segundo fator com `configurar_2fa.py`. O modo oficial exige senha e código do autenticador; sem ambos, o login fica indisponível. Preencha `PRIVACIDADE_RESPONSAVEL` e `PRIVACIDADE_CONTATO`, que aparecem no aviso do site.
8. Execute `iniciar.py` e escolha **2**, ou rode:

```powershell
.\.venv\Scripts\python.exe servidor.py --abrir
```

9. Entre como administrador e envie documentos públicos revisados. O modo oficial começa com o acervo do MySQL; **não carrega os exemplos fictícios**. Sem documentos, o consultor informa que não encontrou evidência.

Não há Qwen, Torch, Transformers, MiniLM, Ollama ou outro modelo local nesta versão. A inferência e os embeddings oficiais usam REST da API Gemini via HTTPX.

## Como funciona o RAG

Publicação: validação do arquivo e dos padrões de privacidade → extração do texto → trechos curtos → embeddings Gemini com tarefa `RETRIEVAL_DOCUMENT` → transação no MySQL.

Consulta: sessão anônima → limites de uso e filtros de entrada → embedding da pergunta com tarefa `RETRIEVAL_QUERY` → comparação de cosseno em memória com vetores do MySQL → filtro de similaridade e metadados → Gemini seleciona evidências → validação estrita → resposta com fontes.

O sistema envia ao Gemini apenas os trechos recuperados para a geração, não o acervo inteiro a cada pergunta. Na indexação, todos os textos aprovados precisam ser enviados para criar seus embeddings. O modelo de embedding não é trocado silenciosamente: seu identificador e dimensão fazem parte da identidade do índice. Trocar modelo exige reindexar.

### Respostas verificáveis

O modo de resposta é **extrativo com seleção por Gemini**: o modelo seleciona trechos integrais que respondam à pergunta. O servidor recusa texto que não corresponda integralmente a uma fonte citada, admitindo somente retirar o marcador inicial de lista. Isso evita aceitar uma paráfrase inventada com citação válida e impede remover uma negação dentro do trecho. Não é um assistente generalista nem usa pesquisa na internet.

JSON inválido, referência inexistente, geração truncada, bloqueio do provedor ou informação insuficiente não recebem citações fabricadas. A correspondência textual não prova relevância ou veracidade do documento; a instituição precisa revisar fontes e avaliar as perguntas reais. Trechos podem conter informações extras, justamente por serem exibidos integralmente.

O limiar `0.65` é um ponto de partida para calibrar, **não uma garantia de qualidade**. Avalie perguntas pertinentes, fora do assunto, ambíguas e sem resposta. Similaridade não é probabilidade de acerto.

### Atualizar e excluir

O nome normalizado identifica o documento. Reenviar o mesmo nome cria uma versão nova e muda o ponteiro ativo em transação; depois apaga textos e vetores antigos nessa mesma transação. Se houver falha antes do commit, o documento anterior permanece. Um nome diferente representa outro documento.

A exclusão pelo painel remove fisicamente documento, versões, textos e vetores do esquema RAG. A aplicação recarrega o acervo antes de cada busca; mudanças feitas por outro processo aparecem nas próximas consultas. Uma resposta já em processamento pode ter capturado o snapshot anterior. Fontes substituídas ou excluídas deixam de abrir.

Informe curso, turma/período, ano, vigência e URL oficial quando relevantes. Em ambiguidades entre metadados recuperados, o sistema pede esclarecimento. Filtros não resolvem automaticamente todos os conflitos semânticos.

PDF, DOCX e TXT são aceitos, até 25 MB por upload. PDFs protegidos, com mais de 300 páginas ou com páginas sem texto suficiente são recusados; aplique OCR antes. O processamento não tem OCR automático. DOCX tem limite de expansão. O upload é sequencial e só anuncia sucesso após a gravação. Há prazo de cinco minutos para indexação remota; divida documentos maiores.

Os trechos são pré-divididos por caracteres. Na API de embeddings, `autoTruncate=false` impede aceitar silenciosamente uma entrada cortada; se o limite remoto for excedido, a operação falha e preserva a versão anterior. Não mantemos tokenizer local nem presumimos equivalência entre caracteres e tokens.

## Segurança e falhas

A revisão inclui um módulo separado em `seguranca/`, proteção persistente contra força bruta, segundo fator, validação estrita de JSON, limites gerais de tráfego e extração documental em subprocesso. Leia **SEGURANCA.md** para cotas, recuperação do segundo fator e implantação do proxy. `deploy/` contém exemplos Nginx com restrição de administração por IP/VPN.

- Visitante não autentica nem fornece RA. A sessão anônima serve apenas a contexto, CSRF e limites.
- Administrador autentica no servidor; cada rota de documentos verifica autorização. Cookie HttpOnly, SameSite=Strict e Secure em HTTPS, rotação após login, expiração em 30 minutos, hash scrypt e limites de tentativas.
- Operações de escrita exigem token CSRF. A aplicação valida Host e Origin; não habilita CORS amplo.
- Frontend usa texto seguro, sem inserir saída do modelo como HTML. Fontes possuem URLs locais validadas. CSP restringe scripts e conexões à própria origem. Não há CDN, analytics ou fontes externas.
- Falhas de rede, HTTP 4xx/5xx, limite do provedor, JSON inválido, vetores inválidos e timeout são tratados. Não há retry automático de geração que possa multiplicar custos. O cliente informa o erro e permite repetir conscientemente.
- Prazo total do atendimento inclui fila, embeddings e geração. As threads mantêm a capacidade ocupada até realmente terminarem, mesmo quando o navegador desiste. Timeouts HTTP também limitam cada fase; não são um mecanismo de interrupção instantânea de threads.
- Perguntas e documentos são tratados como dados não confiáveis. Há padrões preventivos contra injeções comuns, instrução de sistema restrita e resposta extrativa validada. Nenhuma ferramenta, execução de código, SQL ou navegação é disponibilizada ao Gemini.
- Padrões detectam alguns CPFs, telefones, e-mails, identificadores rotulados e instruções suspeitas. Não detectam todos os nomes, identificadores ou ataques obfuscados. Um arquivo recusado deve ser revisado, não liberado automaticamente.

Os `if` restantes validam invariantes e decisões normais. Falhas de I/O, parsing, HTTP e banco são capturadas com `try/except`; não usamos exceções artificiais como substituição de toda condição. Funções de execução têm até dez linhas não vazias de lógica, excluindo docstrings/comentários e assinatura. As funções auxiliares possuem docstrings; as interfaces centrais também documentam argumentos e retornos, seguindo convenções de PEP 257.

## Privacidade

Leia **PRIVACIDADE.md** antes de atendimento institucional. O pacote implementa controles técnicos, **não uma certificação de conformidade com a LGPD**. Finalidade, base legal, responsabilidades, contratos, público-alvo, incidentes e retenção de backups dependem da instituição.

O aviso de privacidade é acessível antes da pergunta e explica o envio ao Google. “Limpar conversa” remove o contexto da aplicação; não desfaz dados já enviados ao provedor. A conta administrativa mantém usuário, hash de senha e segredo TOTP no servidor; o banco técnico guarda cotas pseudonimizadas e prevenção de repetição, conforme `SEGURANCA.md`.

## MySQL antigo e implantação

Se você vinha usando `trecho_documento`, essa tabela não é apagada nem migrada automaticamente. Crie o novo esquema e **reindexe documentos públicos revisados**: os vetores MiniLM antigos não são compatíveis com Gemini. A tabela legada e backups devem ter destinação definida pela instituição, especialmente se continham dados pessoais.

Use um usuário MySQL com acesso apenas às três tabelas RAG e sem acesso a notas/alunos. O bootstrap do esquema deve ser realizado separadamente por quem administra o banco. O aplicativo oficial não executa `create_all` no MySQL.

O comando entregue escuta somente em `127.0.0.1`, com um worker. Para publicar, use proxy HTTPS no mesmo servidor e `APP_ORIGIN` com a origem pública exata. Não exponha o MySQL ou o Uvicorn diretamente. Sessões e cotas gerais são locais ao processo; múltiplos workers exigem estado compartilhado. As cotas de login persistem em SQLite técnico separado. O exemplo de proxy e a confiança explícita em `TRUSTED_PROXIES` estão em `SEGURANCA.md`; o aplicativo não confia automaticamente em `X-Forwarded-For`.

## Testes e manutenção

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam SQLite e transporte HTTP simulado para Gemini. `VALIDACAO.md` descreve o que foi e não foi executado. Os testes opcionais de JavaScript usam jsdom e API HTTP real, sem motor gráfico. Para eles, instale Node 22+, execute `npm install` em `tests_front`, inicie `python -m tests.servidor_ui` em um terminal e execute `npm test` em `tests_front` em outro. Esse servidor é exclusivamente local e usa uma senha fictícia publicada no código de teste.

Pastas: `core/` orquestra conversa; `servicos/` contém RAG, políticas e Gemini; `infra/` contém MySQL e HTTP; `web/` contém API, segurança e frontend; `dominio/` contém dados/erros; `tests/` e `tests_front/` verificam os fluxos.

Para a versão final, retire `debug_web.py`, `dados/`, `tests/`, `tests_front/` e as opções de demonstração do launcher. Não ative demonstração no serviço oficial. Ajuste o import de `debug_web` em `servidor.aplicativo` ao retirar esse arquivo. O debug nunca pode ser ativado pelo navegador.
