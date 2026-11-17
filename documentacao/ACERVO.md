# Leitura dos documentos institucionais

O acervo inicial usa os três PDFs enviados com o projeto: o calendário de 2026 e os PPCs de IA e ESG. Também inclui a FAQ real da secretaria e uma atualização pública do Vestibular para ingresso em 2027, ambas em TXT. A criação do índice não depende de arquivos de exemplo nem de um catálogo na pasta `dados`.

A extração considera as sete páginas do calendário, as 98 páginas do PPC de IA e as 92 páginas do PPC de ESG. Os PDFs são inspecionados para conteúdo ativo e processados sem executar suas instruções. O programa trata o texto dos documentos como informação para consulta, nunca como instruções de sistema.

## Preparação do texto

Nos PPCs, cabeçalhos repetidos e marcas de diagramação são retirados da cópia textual. Os dados gerais são separados em campos para evitar que a busca confunda, por exemplo, a duração de uma aula com o prazo para concluir o curso. Os números e as ressalvas do texto não são corrigidos nem completados por suposição.

O calendário tem uma grade mensal e uma tabela de eventos. O mês aparece no cabeçalho, enquanto cada evento pode conter somente o dia. A preparação associa cada evento ao mês correto e preserva períodos e datas a definir. Também considera a continuação de fevereiro na página seguinte, apesar da ordem interna dos elementos do PDF.

A extração não altera os arquivos originais. Identificadores detectados nos documentos institucionais são ocultados antes da publicação dos textos. Uploads permanecem sujeitos à validação que recusa conteúdo pessoal ou instruções suspeitas.

A FAQ é separada por `Assunto:` antes de dividir o texto em trechos. Isso impede juntar horários de um curso com respostas de outro assunto. As respostas usadas na busca são recortes literais da versão publicada, com os metadados de origem preservados.

## Limites das fontes

O início do semestre e o início das aulas são eventos distintos no calendário: no segundo semestre de 2026, aparecem em 27 de julho e 3 de agosto, respectivamente. A resposta deve respeitar o evento perguntado.

O recesso oficial publicado vai de 10 a 25 de julho. Nas perguntas sobre férias, ele é apresentado junto do início das aulas em 3 de agosto, com rótulos separados. As datas não são alteradas para produzir um único intervalo. A associação é feita na consulta e depende da mesma fonte e versão.

As fichas de duração preservam o prazo mínimo e o máximo de cada PPC. Os nomes são extraídos da identificação dos cursos e acrescentados à apresentação; não há uma tabela externa de prazos substituindo os PDFs. Esses rótulos são derivados durante a consulta e não exigem uma nova tabela no banco.

O PPC de IA tem divergência na carga de estágio: a identificação e a seção de estágio indicam 200 horas, mas um parágrafo da organização curricular menciona 240 horas. O programa preserva os documentos e orienta o Gemini a não decidir conflitos. A faculdade precisa confirmar ou retificar esse tipo de informação; alterar o texto extraído para eliminar a divergência produziria uma fonte diferente do PDF.

Esses documentos não trazem um cronograma individual de provas de Banco de Dados. A presença da disciplina e de critérios gerais de avaliação não permite deduzir uma data de prova.

## Sincronização

As tabelas são criadas quando ausentes. A publicação de cada PDF ocorre em transação: uma falha mantém a versão anterior daquele documento. A lista de fontes administradas pela pasta local é confirmada depois da carga completa. Assim, a retirada de um PDF local não apaga documentos independentes enviados pelo painel.

Na busca textual padrão, uma mudança na versão da preparação textual também invalida a identidade do índice. A aplicação não renomeia automaticamente um índice antigo como se ele já tivesse sido reconstruído.
