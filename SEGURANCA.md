# Segurança do consultor

Revisão de 22/10/2026. O pacote mantém a consulta pública sem login. Somente a secretaria autentica para gerenciar documentos. Não existe proteção que torne o site impossível de invadir ou que garanta disponibilidade durante qualquer DDoS.

## Módulo independente de proteção

`seguranca/` concentra os controles novos, sem alterar as tabelas de alunos ou notas. A composição fica em `web/protecao_login.py` e `web/aplicacao.py`. Não há outro servidor ou porta pública para configurar.

| Responsabilidade | Implementação |
|---|---|
| Contrato de persistência e erros de autenticação | `contratos.py`, independente do framework |
| Reservas atômicas, expiração e prevenção de repetição TOTP | `armazenamento.py`, SQLite técnico separado do MySQL do acervo |
| Autenticação e coordenação das políticas | `autenticacao.py`, recebe repositório, relógio e verificador por injeção |
| Algoritmo TOTP | `totp.py`, vetores RFC 6238 testados |
| Estrutura HTTP/JSON, tamanho e prazo do corpo | `entrada.py`, `corpo.py` |
| Limites de tráfego e adaptador ASGI | `trafego.py`, `gateway.py` |
| Inspeção documental e processo de extração | `arquivos.py`, `extracao.py`, `worker_documento.py` |
| Configuração do servidor e confiança no proxy | `servidor.py` |

Essa separação aplica responsabilidade única e inversão de dependência ao login. O contrato pequeno permite substituir o armazenamento sem reescrever autenticação. Não criamos interfaces artificiais para cada função. Validações usam condições; falhas de banco, I/O, rede e parsing usam exceções específicas.

## Login da secretaria

- Senha com scrypt, sem senha padrão e sem credencial de visitante.
- No modo **oficial**, senha e **TOTP de seis dígitos** são obrigatórios. Sem configuração completa, a rota recusa autenticação com 503. Na demonstração, senha basta; se um segredo TOTP estiver configurado, ele também é exigido.
- Limites simultâneos: **5 tentativas por IP/minuto**, **10 por conta declarada/15 minutos**, **30 globais/minuto**. Incluem tentativas bem-sucedidas. Uma requisição bloqueada não prolonga automaticamente sua janela.
- As reservas são transacionais e persistem em `runtime/seguranca.sqlite3`, inclusive após reiniciar. IP e conta são armazenados somente como HMAC com segredo aleatório local estável. HMAC é pseudonimização.
- Há no máximo duas verificações de senha simultâneas, sem fila adicional no serviço de autenticação.
- TOTP aceita o passo atual e ±30 segundos. Depois de usado, o passo não pode autenticar de novo, inclusive após reinício. Aguarde o próximo código para outro login.
- Usuário, senha e TOTP incorretos recebem a mesma mensagem. Erro no armazenamento recusa login, em vez de remover a proteção.
- Após autenticar, o cookie e CSRF são rotacionados; sessão administrativa dura 30 minutos. Cookies são HttpOnly, SameSite=Strict e Secure em HTTPS.

Para configurar, no ambiente virtual:

```text
python preparar_admin.py
python configurar_2fa.py
```

O segundo comando apresenta uma chave manual/URI no terminal local, pede um código do autenticador e só então salva `ADMIN_TOTP_SECRET` no `.env`. Use um autenticador compatível com TOTP SHA-1, seis dígitos e 30 segundos. Não cole a chave no frontend, em chats ou em logs. Mantenha os relógios sincronizados. Reinicie o servidor após qualquer troca de credencial.

Recuperação exige acesso autorizado ao servidor: execute `configurar_2fa.py` novamente, confirme a substituição e reinicie. Não existe rota pública que desligue o segundo fator. O TOTP não é resistente a todo phishing; acesso administrativo por VPN/rede restrita continua relevante.

Limites por conta podem ser explorados para causar indisponibilidade temporária ao administrador. Por isso o exemplo Nginx restringe as rotas administrativas a IPs/VPN, além do segundo fator. Não trate ocultar o endereço do login como proteção.

## JSON alterado e requisições fabricadas

Qualquer pessoa consegue criar um cliente HTTP próprio. O servidor decide o que ele pode fazer: não confia no JavaScript nem aceita `admin: true` como autorização.

- Modelos de chat e login rejeitam campos desconhecidos, tipos coercíveis e strings Unicode inválidas.
- JSON exige objeto UTF-8, sem chaves duplicadas, NaN/Infinity ou aninhamento excessivo; corpo limitado a 8 KiB.
- Metadados desconhecidos/duplicados na URL, cabeçalhos críticos duplicados, CL+TE, compressão de corpo e enquadramento inválido são recusados. O parser HTTP do Uvicorn e o proxy também participam dessa fronteira.
- Cookies forjados não criam sessões válidas. Escritas exigem CSRF e origem compatível; documentos exigem autorização administrativa no backend.
- SQL usa parâmetros; entradas do usuário não viram nomes de tabelas ou comandos. Respostas do modelo são exibidas como texto. CSP, nosniff e demais cabeçalhos continuam ativos; HTTPS recebe HSTS.
- Cabeçalhos `X-Forwarded-For` enviados pelo visitante são ignorados por padrão. Só habilite confiança no proxy conforme a implantação abaixo.
- Erros não devolvem senha, payload, SQL, traceback ou credenciais internas.

Não usamos uma chave de assinatura no JavaScript: ela seria pública e não distinguiria um atacante de um navegador legítimo. Integridade no transporte depende de HTTPS; autorização depende da sessão no servidor.

## Tráfego e disponibilidade

O aplicativo limita **120 requisições/IP/minuto**, **600 globais/minuto** e **24 requisições em atendimento**, além dos limites específicos de conversa, sessão e upload já existentes. Também cobre URLs inexistentes. Ao exceder volume retorna 429 com `Retry-After`; capacidade ocupada retorna 503. O Uvicorn tem limite de concorrência/conexões e keep-alive curto. JSON tem até cinco segundos de leitura; upload tem até 60 segundos de leitura total, até 25 MiB, e apenas um documento é processado por vez.

Os prazos do aplicativo medem a leitura no backend. Com buffering no proxy, o Nginx recebe antes o upload; seu `client_body_timeout` limita inatividade entre leituras, não a duração total do envio na internet.

Esses valores são pontos de partida conservadores. Uma rede de faculdade pode compartilhar um único IP: calibre cotas com uso legítimo e monitore recusas. O limite é por conexão/IP reconhecido pelo servidor, não uma identidade pessoal.

**Isso não absorve ataques volumétricos que saturem o link, o provedor, TLS ou as conexões antes da aplicação.** Para publicar, contrate/configure proteção DDoS na infraestrutura, CDN/WAF conforme o ambiente, firewall e monitoramento. Não há CDN/WAF contratado ou instalado automaticamente neste ZIP. Também não há teste de DDoS real nesta entrega.

## Uploads

Nomes com caminhos, caracteres de controle/invisíveis e dispositivos reservados são recusados. DOCX tem limites de expansão/quantidade e rejeita caminhos suspeitos, entradas duplicadas, macros, objetos incorporados, relações externas e DTD/entidades. Um DOCX com hyperlink externo também pode ser recusado: remova o vínculo ou exporte como TXT/PDF.

PDF rejeita ações, JavaScript, formulários e anexos, além dos limites de páginas/texto anteriores. A extração PDF/DOCX roda em subprocesso descartável com prazo de 20 segundos. Em POSIX há limites adicionais de memória, CPU, arquivos abertos e tamanho da saída; no Windows, o prazo é aplicado pelo processo pai. Credenciais do ambiente não são copiadas para o worker.

O subprocesso é isolamento de falha/consumo, **não uma sandbox completa do sistema operacional**: ainda roda com o mesmo usuário e suas permissões de arquivos/rede. Filtros não são um antivírus nem eliminam vulnerabilidades desconhecidas dos parsers. Em produção use conta de serviço sem privilégios, filesystem mínimo e isolamento/antivírus conforme a política institucional. Atualize dependências após testes.

Os filtros de prompt injection e dados pessoais, instrução de sistema e validação extrativa do RAG permanecem. O Gemini não tem ferramentas para executar código, SQL ou navegar. Nenhum filtro garante detectar toda manipulação de instruções ou todo dado pessoal.

## Publicar com Nginx

1. Configure MySQL, Gemini, senha, TOTP e contato de privacidade conforme `LEIA-ME.md`.
2. Use `APP_ORIGIN=https://seu-dominio`, `APP_PORT=8000` e `TRUSTED_PROXIES=127.0.0.1`. O Python continua restrito a `127.0.0.1`.
3. Adapte `deploy/nginx.conf.example`: domínio, caminhos de certificado TLS e caminhos de includes. É um exemplo completo, não sobrescreva a configuração existente de outros sites sem integrá-la.
4. Instale/adapte `deploy/admin-allowlist.conf.example` no caminho indicado. Libere o IP de saída real da secretaria ou da VPN. O padrão nega administração externa, deliberadamente. O chat permanece público.
5. Valide a configuração com `nginx -t` antes de recarregar o Nginx. O binário Nginx não estava disponível para essa validação nesta entrega.
6. Use firewall para expor somente as portas necessárias do proxy; mantenha MySQL e Python sem acesso direto da internet. Restrinja permissões de `.env`, diretório `runtime` e temporários, inclusive ACLs no Windows.
7. Teste o acesso pelo domínio: consulta pública, login com TOTP, rejeição fora da rede administrativa, upload permitido, limite 429 e falhas controladas. Configure observabilidade sem registrar perguntas, cookies, senhas ou códigos.

O exemplo sobrescreve `X-Forwarded-For` com o endereço da conexão e aplica cotas antes de encaminhar ao Python, além de limites de conexão, corpo, tempo e TLS. Não confia em um endereço fornecido livremente pelo visitante. Para adicionar CDN/load balancer, configure separadamente as redes confiáveis e a restauração do IP real no Nginx; não mude para confiar em `*`. Sem isso, todos os clientes podem compartilhar a cota do proxy/CDN e a allowlist pode bloquear a secretaria.

## Persistência e operação

Mantenha **um worker**: sessões e cotas gerais continuam em memória. O SQLite técnico coordena cotas de autenticação entre processos locais, mas isso não torna a aplicação inteira compatível com múltiplos workers/servidores. Para escalar, substitua também sessões e cotas por infraestrutura compartilhada e teste atomicidade.

`SEGURANCA_DB` aceita caminho absoluto para volume persistente privado. Use disco local, não compartilhamento de rede. Não apague essa base em reinícios/deploys: isso apagaria cotas, segredo HMAC e prevenção de repetição. Mantenha proteção contra modificações por usuários não autorizados.

Tentativas expiram após 15 minutos, com limpeza periódica a cada 30 segundos e na próxima reserva. Com o programa desligado não há limpeza; ela ocorre ao retomar. SQLite/WAL, backups e snapshots podem reter bytes antigos: expiração lógica não é garantia de apagamento forense. O último passo TOTP por identidade de configuração permanece para prevenir replay, sem guardar o código em claro. Revisões de retenção/backups devem incluir essa base técnica.

A disponibilidade, relógio e integridade do host ainda são premissas. Não foram realizados pentest externo, auditoria de CVEs das dependências ou certificação de conformidade. As evidências reproduzíveis estão em `VALIDACAO.md` e nos testes.

## Referências técnicas

- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP REST Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- RFC 6238 (TOTP): https://www.rfc-editor.org/rfc/rfc6238
- Nginx limit_req: https://nginx.org/en/docs/http/ngx_http_limit_req_module.html
- Nginx HTTP core: https://nginx.org/en/docs/http/ngx_http_core_module.html
