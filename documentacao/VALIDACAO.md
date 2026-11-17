# Verificação da aplicação

A suíte usa bancos temporários e os três PDFs incluídos para conferir extração, datas completas do calendário, dados gerais dos cursos e filtros de recuperação. Também verifica a sincronização de arquivos novos, alterados e removidos, a reutilização de conteúdo idêntico e a preservação da versão ativa quando um PDF está inválido.

As rotas são exercitadas com sessão pública, login administrativo, proteção contra tentativas repetidas, CSRF, validação de JSON e uploads. A apresentação sem fontes é verificada separadamente do controle interno das evidências.

O transporte Gemini é substituído por respostas controladas para conferir requisições, seleção de trechos, cotas, falhas HTTP, respostas inválidas e prazos. Não há gerador alternativo selecionado pelo aplicativo quando o Gemini falha.

A inicialização do ambiente é verificada em uma pasta com espaços, incluindo criação e reutilização da venv e recuperação do pip. A interface tem um teste de envio de perguntas, limpeza, login, publicação, exclusão e tratamento de falhas de rede.

A revisão atual foi executada com Python 3.12.14. As regressões incluem as perguntas das imagens, variantes de duração, identificação dos cursos, troca de curso na conversa e consulta coletiva após uma pergunta individual. O calendário é verificado com recesso e retorno às aulas na mesma versão, sem usar o início administrativo do semestre. Ressalvas, limites mínimo e máximo e passagens com quebra de linha são preservados.

Nesta revisão, as oito perguntas principais da secretaria foram respondidas com o Gemini real, incluindo variações com erros de escrita. A primeira chamada encontrou uma falha HTTP 503 transitória e a repetição limitada recuperou o atendimento. As consultas exercitaram mensalidade, modalidade, horários, inscrições, cursos, grade, duração e nível de ensino. Isso verifica esses casos nesta execução; disponibilidade e cota continuam sendo condições do serviço externo.

Os testes da FAQ conferem segmentação por assunto, recuperação sem curso informado, nomes completos, atualização e exclusão das fontes, invalidação do cache, correções conservadoras, filtros de segurança e distinção entre previsão, prorrogação, ingresso e pagamento. As falhas HTTP 429, dados inválidos e tempos excedidos também são testados com transporte controlado, sem consumir cotas.

A disponibilidade do modelo e da cota continua sendo uma condição da conta configurada. A documentação de busca registra os problemas encontrados e os ajustes realizados.
