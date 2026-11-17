# Perguntas frequentes e manutenção das respostas

O arquivo `documentos/secretaria/FAQ_secretaria.txt` contém as informações encaminhadas pela secretaria. Ele é uma fonte institucional do RAG, não um conjunto de respostas colocado no código. O documento é publicado no mesmo SQLite usado pelos PPCs e pode ser substituído ou retirado como as outras fontes.

## Assuntos atendidos

| Pergunta | Evidência principal |
| --- | --- |
| Cursos oferecidos | Identificação no corpo dos PPCs, com os dois nomes completos |
| Mensalidade | FAQ: cursos gratuitos e existência de taxa de inscrição no Vestibular |
| Horário das aulas | FAQ, com uma ficha para IA e outra para ESG |
| Presencial ou a distância | FAQ: presencial com algumas disciplinas assíncronas |
| Inscrições no Vestibular | Periodicidade da FAQ, calendário por edição e atualização oficial quando publicada |
| Acesso à grade | FAQ com os links oficiais de cada curso |
| Duração | Campos de integralização dos PPCs, com mínimo e máximo separados |
| Superior ou técnico | FAQ: cursos superiores de tecnologia |

Sem curso explícito, essas propriedades abrangem os cursos disponíveis. Isso evita pedir o nome do curso para uma dúvida que tem resposta geral. Numa conversa, uma propriedade curta pode aproveitar o curso anterior; um pedido explícito sobre os dois cursos tem prioridade.

## Formato da FAQ

Cada bloco tem `Assunto:`, `Pergunta:` e `Resposta:`. As fichas de horário e grade também têm `Curso: IA` ou `Curso: ESG`. Uma linha em branco separa os blocos. Mantenha cada resposta curta e completa, com suas condições no mesmo bloco. Não mude os identificadores de assunto sem ajustar a interpretação correspondente.

A extração separa os blocos antes do fatiamento. A recuperação lê os campos do conteúdo ativo e envia somente a resposta correspondente para seleção pelo Gemini. Os rótulos internos não aparecem na conversa.

Os códigos de assunto identificam propriedades; horários, preços, links e prazos vêm dos documentos. Trocar o texto e reiniciar o serviço atualiza o índice. Uma mudança nas evidências também invalida a seleção antiga no cache. Um arquivo local excluído pelo painel será republicado no próximo início enquanto continuar em `documentos`; para uma retirada permanente, remova também a cópia local.

## Interpretação e limites

As consultas são normalizadas para busca. O texto original continua passando pelas regras de dados pessoais e instruções suspeitas. O corretor aceita uma edição simples com alternativa única e usa concordância explícita para alguns plurais ambíguos. Ele não tenta corrigir livremente qualquer frase e não altera os documentos.

Horários da secretaria, custos de outros serviços, condições para estrangeiros e cursos não identificados não são respondidos pela FAQ geral. Esses pedidos seguem a busca nos demais documentos. Perguntas complexas, erros muito extensos ou dados ainda não publicados podem continuar sem resposta.

## Vestibular e atualização oficial

A mensagem da secretaria descreve duas épocas usuais de processo seletivo. Ela não fornece um intervalo exato de inscrições. O calendário acadêmico contém previsões por edição; o documento de atualização registra o prazo efetivamente prorrogado do ingresso no primeiro semestre de 2027.

A atualização foi conferida em 17/11/2026 no [calendário oficial](https://vestibular.fatec.sp.gov.br/calendario/) e no [comunicado de prorrogação do CPS](https://www.cps.sp.gov.br/centro-paula-souza-prorroga-inscricoes-para-o-vestibular-das-fatecs-ate-16-de-novembro/). O prazo de inscrição é distinto do prazo exclusivo para pagamento. Uma nova prorrogação ou outro edital exige publicar a fonte atualizada; não há coleta automática da internet durante a conversa.
