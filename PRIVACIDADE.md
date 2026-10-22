# Privacidade e responsabilidades de operação

Documento técnico de apoio, atualizado em 22/10/2026. Não substitui a avaliação da instituição e não declara conformidade automática com a LGPD.

## O que o código implementa

| Informação | Uso e retenção no aplicativo |
|---|---|
| Pergunta do visitante | Processamento em memória; apenas a última pergunta respondida pode ser usada como contexto por 10 minutos. Limpeza periódica a cada 30 segundos. Não é gravada no MySQL. |
| Respostas e mensagens na página | Memória da página, sem localStorage ou histórico persistente; removidas ao limpar/recarregar. |
| Sessão anônima | Token aleatório em cookie técnico, no máximo uma hora; sem cadastro do visitante. |
| IP | Recebido pela conexão; convertido em HMAC com segredo efêmero para limites de uso. Chaves expiram pela janela de 60 segundos, com limpeza periódica de até 30 segundos. Não há log de IP bruto na configuração entregue. HMAC é pseudonimização, não promessa de anonimização. |
| Proteção do login | HMAC estável de IP/conta e timestamps em SQLite técnico separado: tentativas expiram em 15 minutos mais até 30 segundos de limpeza enquanto o serviço está ativo. Segredo HMAC e último passo TOTP permanecem para cotas/replay. Não guarda senha nem código TOTP em claro. Arquivos SQLite/WAL e backups exigem política própria de retenção. |
| Administrador | Usuário, hash scrypt e segredo TOTP no `.env`; senha em memória somente na autenticação. Sessão administrativa dura 30 minutos. Trocar senha ou segundo fator exige reiniciar o servidor, revogando sessões em memória. |
| Arquivos de upload | Diretório temporário removido em `finally` ao concluir ou falhar. Interrupção abrupta do processo/SO pode exigir limpeza operacional de temporários. |
| Documentos públicos | Texto extraído, metadados e embeddings persistidos no MySQL enquanto publicados. Versões antigas são apagadas na substituição; exclusão remove todas as versões daquele documento. |
| Logs da aplicação | Classe do erro, sem perguntas, respostas, senhas ou chave de API. Access log do Uvicorn desativado. Configure proxies, plataforma e observabilidade com a mesma minimização. |

Há rotas para limpar o contexto e para apagar a sessão corrente, sem permitir acessar ou apagar a sessão de outro visitante. Requisições em andamento podem já ter enviado dados ao provedor; a exclusão local não reverte esse envio. Backups e tabela legada não são apagados pelo painel.

## Gemini e envio externo

O modo de demonstração não envia dados ao Gemini. No modo oficial:

1. Cada trecho aprovado do documento é enviado para embeddings.
2. A pergunta, e eventualmente a referência anterior limitada, é enviada para obter o vetor de busca.
3. A pergunta e os trechos recuperados são enviados ao gerador para selecionar evidências.

Não são enviados cookies, IPs do visitante, credenciais de administrador ou credenciais MySQL como conteúdo do modelo. O serviço Google pode tratar metadados de conexão do servidor e informações de uso segundo seu contrato. Não habilitamos ferramentas de pesquisa na internet, execução de código nem logs opt-in de datasets.

Os termos consultados distinguem serviços gratuitos e pagos. Nos gratuitos, há previsão de uso de entradas/saídas para melhoria dos produtos e restrições para informações pessoais/confidenciais. Nos pagos, o Google declara que não usa prompts/respostas para melhorar produtos, mas prevê registros limitados para segurança e outras finalidades, além de possíveis transferências internacionais. Apagar a conversa no nosso aplicativo não apaga esses registros.

Os termos consultados também contêm restrição de público menor de 18 anos para clientes da API. Uma faculdade pode ter estudantes menores: avalie a compatibilidade do serviço e do contrato antes de publicar. O código não coleta data de nascimento nem usa uma declaração fictícia de idade para contornar essa avaliação. Se necessário, a instituição deve escolher uma oferta/contrato adequado ao seu público.

## Decisões que cabem à instituição

- Definir controlador, operadores, finalidade, base legal e canal para titulares; preencher os campos de contato do `.env` e revisar o aviso do site.
- Revisar o acervo antes da publicação. Informação pública pode conter dados pessoais; o sistema não identifica todos eles. Não usar notas, cadastros, CPFs, RAs, credenciais ou documentos individuais de alunos.
- Avaliar o contrato Google utilizado, público-alvo, retenção, transferências internacionais e medidas de segurança. A modalidade não é verificada automaticamente pelo código.
- Definir prazo e procedimento de eliminação para backups, arquivos legados e temporários de processos interrompidos.
- Restringir acesso administrativo e ao banco, usar HTTPS, proteger segredos e aplicar atualizações após testes.
- Estabelecer revisão de conteúdo, atendimento a titulares, resposta a incidentes e responsabilidades de correção. O pacote não implementa um sistema institucional de protocolo ou auditoria persistente.

## Referências oficiais consultadas

- LGPD, especialmente finalidade, necessidade, transparência e dados pessoais de acesso público: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
- Termos da API Gemini (vigência indicada na página consultada: 23/03/2026): https://ai.google.dev/gemini-api/terms
- Referência de geração: https://ai.google.dev/api/generate-content
- Referência de embeddings e truncamento: https://ai.google.dev/api/embeddings

Consulte novamente esses documentos quando for implantar; contratos e disponibilidade podem mudar.
