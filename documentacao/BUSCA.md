# Recuperação das informações e tempo de resposta

A busca inicial reconhecia poucas formas de escrever uma pergunta. “Férias” não correspondia a “recesso”, palavras de conversa reduziam a pontuação e uma pergunta pelo vestibular encontrava matrículas e listas de chamada antes da data do exame. Na relação de cursos, o código podia usar a entrada do sumário em vez da identificação no corpo do PPC.

## Como a busca funciona

A consulta passa pela política de uso e depois segue uma destas rotas:

- Cursos oferecidos: lê os nomes na seção de identificação dos PPCs publicados, descartando o sumário. A instrução do Gemini deixa explícito como usar essas identificações.
- FAQ da secretaria: identifica mensalidade, horários, modalidade, nível e links da grade; recorta a resposta do documento ativo e filtra por curso. As variações não dependem da igualdade literal com a pergunta cadastrada. A fonte e sua manutenção estão descritas em `FAQ.md`.
- Duração e modalidade: reconhece a propriedade consultada e recupera o campo separadamente para cada curso pedido. “IA”, “I.A.” e o nome por extenso apontam para o mesmo curso; o mesmo vale para ESG e seu nome completo. A apresentação associa cada campo ao nome extraído do PPC.
- Calendário: identifica o assunto e separa exame do vestibular, inscrição, isenção, matrícula, recesso e feriado. Mês, ano e edição do vestibular são tratados antes da ordenação dos resultados.
- Outros assuntos: combina a busca literal do SQLite FTS5 com um índice linguístico derivado dos mesmos textos ativos. A segunda busca reconhece flexões portuguesas e admite aproximações restritas para palavras digitadas incorretamente.

O índice linguístico usa o algoritmo português Snowball. Ele não é um modelo de IA, não baixa pesos nem chama uma API. Os documentos continuam persistidos no SQLite; o índice auxiliar é reconstruído em memória quando muda uma versão ou um metadado. Antes de interpretar a consulta, um corretor restrito trata abreviações e erros simples com alternativa inequívoca, preservando números, palavras válidas e siglas. A validação de segurança continua recebendo o texto original.

As listas literal e linguística são combinadas por Reciprocal Rank Fusion. A classificação mantém a cobertura da pergunta, prefere o corpo dos documentos ao sumário e considera a afinidade das seções. Isso melhora a recuperação sem tratar a pontuação como uma probabilidade de a resposta estar correta.

A busca textual continua sendo o padrão e não consome a cota de embeddings. O adaptador vetorial Gemini permanece opcional.

## Calendário e datas

Os filtros preservam a expressão “Previsão” encontrada no calendário. Uma data prevista não é apresentada como confirmada. Inscrição no vestibular não é confundida com solicitação de isenção da taxa.

O ano do ingresso também pode ser diferente do ano da prova. No documento incluído, o vestibular do primeiro semestre de 2027 tem exame previsto para 13 de dezembro de 2026. Consultar essa edição não deve descartar o evento por ele ocorrer no ano anterior.

O texto oficial de atualização incluído nesta revisão confirma o exame e registra a prorrogação das inscrições da mesma edição. A busca retira a previsão quando existe atualização explícita da mesma etapa e edição, mantendo conflitos entre fatos confirmados disponíveis para recusa. A resposta mostra o semestre de ingresso separado da data de inscrição. Não confunde prazo de pagamento com possibilidade de fazer uma nova inscrição.

Apenas o intervalo de recesso explicitamente publicado pode ser respondido. O código não deduz férias de dezembro a partir do término das aulas e não inventa data de uma prova de disciplina.

Uma pergunta sobre férias também recupera o próximo início das aulas depois do recesso, quando ele está publicado na mesma versão do calendário e a até 45 dias do fim do intervalo. O início administrativo do semestre não substitui o início das aulas. O resultado mostra o recesso oficial e o retorno com rótulos separados, preservando condições adicionais do texto original.

## Perguntas em sequência

O contexto conserva a última pergunta respondida durante a sessão, dentro do prazo de retenção. A resolução considera curso e assunto: depois de “Quanto dura IA?”, “e o de ESG?” recupera a duração de ESG. Uma pergunta explícita sobre os dois cursos tem prioridade sobre o curso anterior. A expressão “é presencial?” pode aproveitar o curso já resolvido.

Esse tratamento cobre referências curtas reconhecidas; não representa memória ilimitada nem resolução garantida de qualquer conversa. Uma consulta sem resposta não substitui a última pergunta respondida.

## Contexto enviado ao Gemini

O gerador recebe evidências completas dentro de um orçamento de texto, sem duplicações literais. Os textos não são cortados ao meio. Diferenças de negação ou ressalva são mantidas: duas passagens parecidas podem expressar informações diferentes.

O Gemini continua selecionando números de trechos, sem acesso a ferramentas, SQL ou execução de código. O servidor verifica os identificadores e materializa o texto original. As fontes continuam internas e não aparecem na resposta da conversa.

Os cabeçalhos internos identificam o curso e o papel de cada evidência. Se a seleção válida inclui parte de um grupo reconhecido pela busca, o servidor mantém os campos relacionados: as fichas dos cursos pedidos ou o par recesso/retorno. A complementação só ocorre após uma seleção respondida e válida; não transforma uma falha ou seleção insuficiente em resposta local. A formatação rotula os valores publicados, sem calcular prazos ou inventar datas.

## Redução da espera

Para os modelos Gemini 3 de texto, a chamada usa raciocínio `LOW` e mantém a temperatura padrão do modelo. A configuração anterior forçava temperatura zero e deixava o esforço de raciocínio no padrão. Esse ajuste segue a documentação da família Gemini 3; não representa um prazo garantido pelo provedor.

Consultas independentes podem usar as vagas de atendimento simultaneamente. A trava que serializava toda a geração foi retirada. Os limites de capacidade permanecem e uma chamada que excedeu o prazo continua ocupando sua vaga até sua thread encerrar.

O transporte reserva tempos curtos para conexão e usa o orçamento restante na leitura. O prazo total continua sendo `RAG_TEMPO_TOTAL`, sem repetir indefinidamente erros de cota ou de configuração.

Seleções respondidas e validadas podem ser reutilizadas por três minutos, com limite de quantidade. A chave inclui o digest da pergunta e as versões, os textos e os metadados das evidências. A seleção é validada novamente na leitura. Não são guardadas respostas insuficientes ou falhas; alterar ou excluir uma fonte impede usar a seleção anterior.

Para duração, modalidade e recesso, variações reconhecidas podem usar a mesma chave quando recuperam exatamente as mesmas evidências. Termos fora do vocabulário previsto, como uma condição para transferidos, preservam a pergunta original na chave. A identidade do curso e o papel das evidências também participam da invalidação.

HTTP 429 do Gemini é tratado como limite do provedor, com estado `cota` e HTTP 429 na rota pública. A mensagem não é confundida com ausência de informações. Uma cota diária esgotada exige disponibilidade no projeto Google; esperas curtas ou mudanças no código não aumentam esse limite.

Os logs informam quantidade de candidatos, pontuação de recuperação, duração das etapas e acerto do cache. Não registram pergunta, texto do documento, resposta, senha ou chave de API.

## Verificação

A suíte verifica perguntas informais, os três PDFs reais, a distinção entre etapas do vestibular, o ano de ingresso, o uso do corpo dos PPCs, a invalidação dos índices e do cache, a concorrência e o orçamento HTTP.

Nesta revisão, as oito perguntas principais da secretaria foram exercitadas com sucesso no Gemini real, incluindo variações com erros de escrita. A primeira chamada recuperou uma falha HTTP 503 transitória; as demais foram concluídas. A suíte controlada verifica também cotas, falhas de rede, negações, atualização das fontes, contexto e invalidação do cache. Os detalhes estão em `VALIDACAO.md`.

Esses resultados validam os casos exercitados, sem transformar uma busca lexical em compreensão semântica universal. Perguntas novas e documentos diferentes devem entrar na avaliação do acervo.

## Referências técnicas

- [SQLite FTS5: BM25, tokenização e sinônimos](https://www.sqlite.org/fts5.html)
- [Snowball: algoritmo de radicais portugueses](https://snowballstem.org/algorithms/portuguese/stemmer.html)
- [Microsoft: recuperação de informações e Reciprocal Rank Fusion](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-information-retrieval)
- [Google: configuração do Gemini 3](https://ai.google.dev/gemini-api/docs/gemini-3)
- [Google: configuração de raciocínio na geração](https://ai.google.dev/gemini-api/docs/generate-content/thinking)
