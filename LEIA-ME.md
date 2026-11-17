# Consultor Fatec Rio Claro

O chatbot responde dúvidas públicas usando os PPCs de IA e ESG e as perguntas frequentes da secretaria. O visitante pergunta sem cadastro. O painel administrativo permite publicar, substituir e excluir documentos.

## Correção da cota de embeddings

O projeto agora usa **Gemini para as respostas e SQLite FTS5 para recuperar os documentos**. Esse é um RAG textual: a busca seleciona fontes por palavras e BM25; o Gemini seleciona os números dos trechos relevantes, e o servidor recupera os textos originais com suas citações. Não existe um modelo generativo local.

O erro EmbedContentRequestsPerDay... limite=1000 era da cota diária de embeddings. O acervo incluído gera 1.039 trechos. Mais repetições ou outra chave no mesmo projeto não removem esse limite.

No modo padrão, preparar os PPCs, abrir o site, pesquisar o acervo e publicar arquivos **não faz chamadas de embeddings**. O Gemini é chamado quando há evidências para responder a uma pergunta. A geração tem seus próprios limites: esta mudança elimina a dependência dos embeddings, não concede cota ilimitada ao modelo de respostas.

A busca textual depende da correspondência de termos e de alguns equivalentes explícitos. Ela não tem a mesma capacidade semântica de um modelo de embeddings. Perguntas sem evidência suficiente podem exigir reformulação. A pontuação exibida é cobertura de termos, não confiança factual.

## Como rodar no VS Code

Abra a pasta que contém main.py, selecione o arquivo e clique em **Executar arquivo Python**. O main cria ou reutiliza a .venv, recupera o pip se necessário, confere dependências e inicia o servidor. A equipe usa Python 3.15; o iniciador aceita Python 3.12 ou superior.

O main.py, as credenciais e os bancos existentes foram preservados na entrega. Se sua pasta local tiver um .env ou um runtime mais recente, mantenha esses arquivos ao atualizar o código. Não substitua progresso local por uma cópia antiga do banco.

A chave fica somente no .env, ao lado de servidor.py. Os modelos configurados continuam disponíveis; não é preciso trocar a chave nem contratar outro provedor para usar a busca textual.

A configuração é:
~~~dotenv
CHATBOT_PERFIL=mvp
BUSCA_ACERVO=textual
GEMINI_API_KEY=
GEMINI_MODELO=gemini-3.5-flash
~~~
Mantenha sua chave no campo existente. Se BUSCA_ACERVO não estiver no .env, o padrão já é textual. O modelo de geração explícito do seu arquivo é respeitado. A aplicação não troca de modelo silenciosamente.

O .env é criado a partir de .env.example somente se não existir. Na primeira utilização também é necessário configurar o administrador:
~~~text
.venv\Scripts\python.exe preparar_admin.py
.venv\Scripts\python.exe configurar_2fa.py
~~~
O e-mail identifica uma conta local; não é login com Google nem acesso à caixa postal. Use uma senha própria do aplicativo. O segundo fator continua obrigatório.

## Primeira carga e banco existente

O programa cria as tabelas ausentes e o FTS5 com gatilhos transacionais. Os textos de versões já publicadas ficam disponíveis para busca textual sem chamar embeddings. A identidade do método de recuperação fica registrada na versão. Trechos novos publicados pelo modo textual não contêm vetores artificiais; o campo legado de embedding fica vazio.

Os arquivos iniciais são indexados a partir dos originais incluídos. O marcador acervo_inicial_fts5_v1 é separado da carga vetorial antiga. Uma carga interrompida reaproveita documentos já publicados. Depois da conclusão, reiniciar não restaura arquivos excluídos pelo administrador.

A substituição apaga a versão antiga na mesma transação; os gatilhos mantêm o FTS5 consistente em substituições e exclusões. Só são consultadas versões ativas e dentro da vigência.

O acervo continua em runtime/acervo.sqlite3; a proteção do login usa runtime/seguranca.sqlite3. Faça backup com os processos parados. Use uma instância do servidor neste MVP.

## Fluxo de uma pergunta

1. A API valida a sessão, os campos e os limites de uso.
2. A política recusa padrões pessoais e instruções suspeitas.
3. A busca reconhece perguntas equivalentes da FAQ; depois consulta o FTS5 com as variantes usadas na normalização dos termos.
4. O curso e a vigência limitam os candidatos. A busca prioriza cobertura integral e o corpo das seções, evitando que sumários e menções parciais ocupem as primeiras posições.
5. O Gemini recebe a pergunta e os trechos selecionados e retorna os números das evidências, sem precisar reescrever o conteúdo.
6. O servidor valida os números e recupera as passagens literais do acervo, preservando espaços, quebras de linha, negações e fontes.

Sem evidência suficiente, o chatbot informa isso. Falhas da API são comunicadas ao visitante; não são substituídas por uma resposta local inventada.

## Documentos disponíveis e respostas não encontradas

O pacote inclui os PPCs de Inteligência Artificial e ESG e a FAQ da secretaria. Esses arquivos permitem consultar cursos, mensalidade, horários e características curriculares. Eles não incluem um calendário oficial com as datas das provas e dos eventos da faculdade.

Perguntas como “Quando é a prova de Banco de Dados?” dependem da publicação do calendário correspondente pelo painel administrativo. Menções a avaliação, provas ou calendário dentro de um PPC não informam quando uma prova será aplicada. O chatbot deve manter a resposta de informação insuficiente quando a data não estiver nas fontes.

Os exemplos da interface agora usam perguntas respondidas pela FAQ incluída. Para consultar calendários, publique documentos reais com curso, período, ano e vigência quando esses dados forem aplicáveis. Não é necessário recriar o banco nem alterar a chave para usar as correções de recuperação; os textos já indexados continuam sendo aproveitados.

A busca reconhece flexões como “matérias” e “disciplinas”, retira expressões conversacionais e usa a mesma correspondência na consulta e na pontuação. O limiar textual continua em 0,75; ele não foi reduzido para aceitar qualquer menção ao assunto.

Falhas 500/503 na geração têm até duas repetições, com esperas de 1 e 2 segundos dentro do prazo total. Cota diária de geração não é repetida por essa política. Uma falha persistente continua sendo informada ao visitante. Os registros técnicos distinguem recuperação sem evidências, seleção insuficiente e resposta rejeitada, sem registrar perguntas, trechos ou credenciais.

## Administração e privacidade

O upload continua aceitando PDF, DOCX e TXT, com revisão de conteúdo público, autorização administrativa, limites de tamanho e extração isolada. A chave não vai para o navegador. O login mantém senha com hash, TOTP e proteção contra tentativas repetidas.

Perguntas não são gravadas no banco do acervo. O contexto é temporário. Revise documentos e configurações de operação conforme PRIVACIDADE.md e SEGURANCA.md; filtros não garantem identificação universal de dados pessoais.

## Opções do iniciador

~~~text
python main.py --preparar
python main.py --dev --preparar
python main.py --ngrok
~~~
O ngrok permanece opcional e desativado por padrão. Requer token e configuração de segurança. O .bat continua sendo um atalho para o mesmo main.

## Modo vetorial opcional

Quem tiver cota disponível pode configurar BUSCA_ACERVO=gemini e GEMINI_EMBEDDING compatível com o adaptador. A inicialização textual não muda automaticamente para esse modo. Ao trocar de recuperação, execute preparar_acervo.py --forcar com o servidor parado e republique uploads adicionais, porque índices e marcadores não são intercambiáveis.

Não troque simplesmente o ID do embedding por um modelo de outro fornecedor ou formato: espaços vetoriais e contratos de API podem ser diferentes. PostgreSQL/pgvector continua reservado para uma etapa futura, sem implementação neste pacote.

## Referências

- SQLite FTS5 e BM25: https://www.sqlite.org/fts5.html
- RAG com índices textuais ou vetoriais: https://learn.microsoft.com/en-us/azure/foundry/concepts/retrieval-augmented-generation
- Cotas por projeto do Gemini: https://ai.google.dev/gemini-api/docs/rate-limits
- Orientações do suporte Google para 429: https://discuss.ai.google.dev/t/handling-429-503-errors-from-the-gemini-api/124640
