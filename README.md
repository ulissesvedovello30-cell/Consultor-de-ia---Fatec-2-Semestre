# Consultor da Fatec Rio Claro

Chatbot para consultar os PPCs de Inteligência Artificial e ESG, o calendário acadêmico e as perguntas frequentes da secretaria da Fatec Rio Claro. A conversa é pública, sem cadastro. A secretaria entra na administração para publicar, substituir ou retirar documentos.

O projeto usa RAG: primeiro procura informações nos documentos publicados e depois envia a pergunta e os trechos encontrados ao Gemini. A resposta é montada com as passagens selecionadas e validadas pelo servidor. Os nomes dos arquivos e as páginas ficam no controle interno, sem aparecer na conversa.

## Como rodar

Extraia o ZIP em uma pasta nova. Assim, a execução começa sem os bancos e os arquivos temporários da versão anterior.

Abra essa pasta no VS Code e execute o `main.py`. Também é possível iniciar pelo terminal da pasta:

```powershell
python main.py
```

O `main.py` chama a preparação do ambiente, cria a `.venv` quando ela não existe, recupera o `pip` se necessário e instala as dependências. Nas próximas execuções, reutiliza o ambiente preparado. Não é necessário ativar a venv manualmente.

A primeira instalação precisa de internet. O atendimento precisa de uma chave Gemini válida e com cota disponível. A configuração fica no `.env` ao lado do `main.py`; um arquivo existente é preservado.

Depois da preparação, o servidor abre o navegador em **http://127.0.0.1:8000**. Se o navegador não abrir, acesse esse endereço. `Ctrl+C` encerra o servidor. A origem pode ser alterada em `APP_ORIGIN`, mantendo o mesmo endereço usado para acessar a aplicação.

A revisão atual foi executada com Python 3.12.14; a versão anterior também foi verificada com Python 3.14.3. O iniciador exige Python 3.12 ou superior; a instalação também depende de haver versões das bibliotecas compatíveis com o interpretador escolhido.

## Documentos incluídos

| Pasta | Documento |
| --- | --- |
| `documentos/cursos/ia/` | PPC de Inteligência Artificial |
| `documentos/cursos/esg/` | PPC de Gestão da Sustentabilidade Ambiental, Social e Governança Corporativa |
| `documentos/calendario/` | Calendário acadêmico de 2026, retificado |
| `documentos/secretaria/` | FAQ real encaminhada pela secretaria, em TXT |
| `documentos/vestibular/` | Atualização oficial da edição de ingresso no primeiro semestre de 2027, consultada em 17/11/2026 |

Os PDFs originais foram mantidos. A indexação remove cabeçalhos repetidos dos PPCs e separa campos como modalidade, carga horária e prazo de integralização. No calendário, cada evento recebe o mês e o ano do seu bloco para que a data continue completa depois da divisão em trechos.

Não há pasta `dados` nem documentos de demonstração no acervo inicial. A FAQ acompanha a origem das informações; seus textos ficam no acervo, sem respostas fixas no código Python.

## Banco e atualização do acervo

O banco não acompanha o ZIP. Na primeira execução, o programa cria `runtime/acervo.sqlite3` e publica os textos extraídos dos PDFs. Também cria `runtime/seguranca.sqlite3` para o controle técnico de tentativas de login.

A cada inicialização, o programa compara o conteúdo dos arquivos PDF, TXT e DOCX da pasta `documentos`, inclusive nas subpastas. Um arquivo igual é reutilizado; um arquivo novo ou alterado é indexado. Se um documento antes administrado por essa pasta for removido, ele sai do índice. Documentos enviados pelo painel são preservados.

Os nomes dos documentos devem ser únicos, mesmo em subpastas diferentes. Para identificar o curso de um PPC, mantenha seus documentos em uma pasta chamada `ia` ou `esg`. Documentos gerais, como o calendário, ficam sem filtro de curso. Na FAQ, o campo `Curso:` identifica as respostas específicas de IA ou ESG.

A pasta de documentos é a origem do acervo inicial. Excluir pelo painel um PDF que continua nessa pasta faz com que ele volte no próximo início. Para retirá-lo de forma permanente, remova também o arquivo local e reinicie.

Não apague o banco em cada execução: ele guarda o índice e as publicações da administração. Para atualizar os PDFs locais, substitua os arquivos e reinicie o programa. Falhas de extração não substituem a versão já publicada daquele documento.

## Busca e respostas

O padrão `BUSCA_ACERVO=textual` usa a pesquisa FTS5 do SQLite, com filtros de curso, tratamento dos eventos do calendário e uma busca auxiliar por radicais portugueses. Os resultados literal e linguístico são combinados antes da seleção das evidências. O Gemini participa da seleção da resposta; não é usado para gerar embeddings nesse modo. A biblioteca Snowball é instalada pelo `main.py` e executa apenas o algoritmo linguístico, sem baixar um modelo de IA.

Perguntas sobre duração ou modalidade recuperam o campo correspondente de cada curso pedido. A resposta apresenta o nome completo junto dos valores, distinguindo duração mínima e prazo máximo. Siglas, nomes por extenso e expressões como “quanto dura cada curso?” são reconhecidos. Numa sequência como “Quanto dura IA?” e “e o de ESG?”, a segunda pergunta mantém o assunto e troca o curso.

A FAQ complementa os PPCs com gratuidade, horários, nível de ensino, links da grade e a ressalva das disciplinas assíncronas. Cada pergunta é indexada em seu próprio bloco. Sem um curso informado, as dúvidas gerais abrangem os dois cursos; um curso informado ou herdado da conversa delimita os resultados.

A interpretação aceita abreviações, ausência de acentos e correções restritas de digitação. Não altera datas, números ou siglas. Uma aproximação ambígua permanece como foi escrita, salvo quando a concordância explícita resolve o plural. Consultas com condições não cobertas pela FAQ seguem a busca documental.

No vestibular, a resposta diferencia a época usual dos processos, o período de inscrição e o semestre de ingresso. O texto oficial incluído registra a prorrogação para ingresso em 2027 e substitui a previsão anterior da mesma etapa e edição. Pagamento não é tratado como nova inscrição. O conteúdo é uma cópia datada; o aplicativo não consulta o site ao vivo nem afirma que uma previsão está aberta agora.

Nas perguntas sobre férias, o consultor apresenta o recesso oficial e o próximo início das aulas publicado no mesmo calendário. Esses eventos continuam separados: o fim do recesso não é tratado como data de volta às aulas.

Consultas respondidas podem reutilizar por três minutos uma seleção validada. Variações reconhecidas dessas perguntas estruturadas também podem reutilizá-la; qualificadores desconhecidos mantêm consultas separadas. A chave é vinculada às evidências atuais; substituir ou excluir um documento impede usar uma seleção antiga. Consultas independentes não ficam aguardando uma única geração serial. O prazo total continua configurado em `RAG_TEMPO_TOTAL`.

Se o Gemini recusar uma chamada por cota, a interface informa o limite do serviço. Isso não significa que a informação está ausente dos documentos. Reiniciar o programa ou repetir a pergunta não renova uma cota diária esgotada.

O adaptador vetorial pode ser habilitado com `BUSCA_ACERVO=gemini`. Ele também depende da disponibilidade e das cotas do modelo de embeddings configurado. Trocar de modo não é necessário para consultar os PDFs incluídos.

Exemplos de perguntas:

- Quando é o Hackathon?
- Quando começam as aulas do segundo semestre de 2026?
- Qual a duração do curso de IA?
- No caso, quanto dura cada curso? O de IA e o de ESG?
- Quando começam as férias na Fatec?
- Qual a carga horária do curso de ESG?
- Quais disciplinas tem IA?

A data de uma prova específica só pode ser respondida se estiver em um documento publicado. Uma ementa de Banco de Dados não informa a data da avaliação. Quando não há evidência suficiente, o consultor informa que não encontrou a resposta.

## Administração

O login usa `ADMIN_USUARIO`, `ADMIN_SENHA_HASH` e `ADMIN_TOTP_SECRET` (segundo fator obrigatório no MVP). São credenciais próprias do projeto. Usar um endereço Gmail como usuário não significa entrar com a senha da conta Google.

Para preparar as credenciais depois de rodar o `main.py`, use o Python da venv no terminal da raiz:

```powershell
.venv\Scripts\python.exe -m ferramentas.administracao.preparar_admin
.venv\Scripts\python.exe -m ferramentas.administracao.configurar_2fa
```

No Linux e macOS, substitua `.venv\Scripts\python.exe` por `.venv/bin/python`. As ferramentas perguntam os dados necessários. O painel aceita PDF, DOCX e TXT públicos, com validação de conteúdo e limites de tamanho. O modo de acesso remoto por túnel exige a configuração de segurança prevista no projeto.

## Organização

| Pasta | Responsabilidade |
| --- | --- |
| `aplicacao/inicializacao/` | Preparação da venv, composição e servidor |
| `aplicacao/configuracao/` | Parâmetros e caminhos da aplicação |
| `aplicacao/core/` e `aplicacao/dominio/` | Atendimento, resultados e regras compartilhadas |
| `aplicacao/servicos/acervo/` | Descoberta, publicação e sincronização dos documentos |
| `aplicacao/servicos/extracao/` | Leitura e preparação dos textos dos PDFs |
| `aplicacao/servicos/recuperacao/` | Busca, classificação, calendário e catálogo de cursos |
| `aplicacao/servicos/recuperacao/linguagem/` | Radicais portugueses, índice auxiliar e fusão das buscas |
| `aplicacao/servicos/recuperacao/planejamento/` | Identificação do assunto, campos por curso e nomes completos |
| `aplicacao/servicos/recuperacao/perguntas/` | Intenções da FAQ e recorte de respostas por assunto e curso |
| `aplicacao/servicos/respostas/apresentacao/` | Identificação dos cursos e apresentação dos campos validados |
| `aplicacao/servicos/respostas/otimizacao/` | Contexto compacto e cache de seleções validadas |
| `aplicacao/servicos/respostas/` | Política de uso, prazo e validação da seleção |
| `aplicacao/servicos/gemini/` | Contrato de geração e adaptador de embeddings |
| `aplicacao/infra/` | Persistência, repositórios, cliente HTTP e túnel opcional |
| `aplicacao/seguranca/` | Proteção do acesso, documentos e requisições |
| `aplicacao/web/` | Rotas, administração e arquivos da interface |
| `ferramentas/` | Configuração administrativa e utilitários de diagnóstico |
| `documentacao/` | Funcionamento do acervo, privacidade e segurança |
| `tests/` e `tests_front/` | Verificações automatizadas e dependências substitutas de teste |

O `main.py` permanece na raiz e apenas chama o iniciador. Os geradores controlados usados pelos testes ficam em `tests/apoio`; não são selecionados pelo atendimento.

O [guia em PDF](documentacao/guia/fluxo_chatbot_fatec.pdf) explica o fluxo, os módulos e as decisões de implementação. A manutenção da FAQ está descrita em [documentacao/FAQ.md](documentacao/FAQ.md).

## Fluxo da execução

1. O `main.py` prepara ou reutiliza o ambiente e inicia o servidor com o Python da venv.
2. A composição abre o SQLite e confere os PDFs institucionais.
3. O extrator valida os arquivos em um processo separado, prepara os textos e publica as versões novas.
4. O visitante faz uma pergunta; as rotas validam a sessão, a entrada e os limites de uso.
5. A busca recupera as evidências e o Gemini seleciona as que respondem à pergunta.
6. O servidor valida a seleção e devolve o texto à interface, sem a lista de fontes.

## Verificações do projeto

Para instalar as dependências de desenvolvimento:

```powershell
python main.py --preparar --dev
.venv\Scripts\python.exe -m pytest
```

Os testes cobrem os PDFs reais, a atualização do acervo, o transporte Gemini, o login, os uploads e as rotas. As chamadas remotas são substituídas por respostas controladas durante a suíte; isso não verifica continuamente a chave nem a cota da conta Google. Esta revisão também incluiu chamadas de integração ao Gemini real, descritas em [documentacao/BUSCA.md](documentacao/BUSCA.md).

O teste da interface usa Node.js 22 ou superior. Depois de preparar as dependências de desenvolvimento, entre em `tests_front`, execute `npm ci` e depois `npm test`. O teste abre uma aplicação isolada e usa o transporte ASGI, sem precisar iniciar outro servidor.

## Túnel opcional

O suporte a ngrok continua disponível. Com as credenciais administrativas, o autenticador e `NGROK_AUTHTOKEN` configurados, execute `python main.py --ngrok`. O endereço público passa a ser a origem da aplicação enquanto o túnel estiver ativo.

O perfil executável desta entrega é Gemini com SQLite. PostgreSQL permanece reservado e não é apresentado como um banco já configurado.
