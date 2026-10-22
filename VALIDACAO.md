# Validação desta entrega

Concluída em 22/10/2026.

## Executado

- **225 testes Python passaram**. A suíte verifica persistência SQLite via SQLAlchemy, substituição atômica, remoção de versões e vetores, recarga do índice, vigência, ambiguidades, limites, timeout/cancelamento, autenticação administrativa, rotação de sessão, CSRF, uploads inválidos, privacidade e respostas sem evidência.
- Transporte HTTP Gemini simulado: corpo de requisição, separação de systemInstruction, tipos de embedding, dimensão, normalização, truncamento desativado, resposta estruturada, HTTP 400/401/403/404/429/500/503, conexão, timeout, JSON malformado, bloqueio de segurança, geração incompleta e vetores inválidos.
- JavaScript executado em **jsdom contra a API HTTP real em localhost**: chat sem login, fontes, limpeza, login, upload, listagem, exclusão, saída XSS exibida como texto, links perigosos recusados, falha de rede, JSON inválido e remoção de sessão.
- Análise AST: **278 funções de execução com docstrings e no máximo dez linhas não vazias de lógica**. Assinaturas, comentários e docstrings não entram na contagem. Testes não são submetidos ao limite de tamanho de funções.
- A integração JavaScript foi executada duas vezes: demonstração com senha e demonstração com segundo fator configurado. Foi verificada a exibição do campo TOTP, envio e limpeza do código após login.
- Novos testes: cotas persistentes por IP/conta/global, reservas concorrentes atômicas, TOTP com seis vetores RFC 6238 e rejeição de replay após reinício, indisponibilidade do banco de segurança, X-Forwarded-For falso, cookies/JSON forjados, duplicação de campos/cabeçalhos, limites de bytes e tempo, saturação das vagas, DOCX ativo, PDF com JavaScript e extração real em subprocessos.
- Frontend servido pela mesma origem do backend, sem CDN ou JavaScript com chave de API.
- ZIP conferido para excluir `.env`, bases SQLite, caches, diretórios temporários e dependências instaladas.

Comando Python: `python -m pytest -q` (dependências em `requirements-dev.txt`). Houve avisos de depreciação da integração Starlette/HTTPX e do método pypdf usado para construir o PDF malicioso de teste; não houve falha de teste. As versões diretas do ambiente validado estão fixadas em `requirements.txt`.

## Limites da validação

- **Não houve pentest externo nem ataque DDoS real**. Os testes exercitam localmente as barreiras e as falhas controladas. Não provam ausência de vulnerabilidades nem capacidade contra ataques volumétricos.
- **Nginx não foi executado**: o ambiente não tinha o binário. O exemplo precisa de domínio, TLS e allowlist reais e de `nginx -t` na implantação. CDN/WAF e firewall não foram instalados.
- Não foi executada auditoria de CVEs das dependências nesta revisão.

- **Não houve chamada real ao Gemini**: nenhuma chave do usuário foi fornecida. Os testes validam os contratos e falhas simuladas, não a disponibilidade/cota da sua conta nem a qualidade semântica dos embeddings reais.
- **Não houve execução contra MySQL real**: os testes de persistência usam SQLite. O esquema MySQL é entregue para execução no banco existente. Valide conexão, permissões, charset e comportamento transacional no ambiente de destino.
- **Não houve teste gráfico em um navegador completo**, nem execução no Windows ou na interface do VS Code. O teste jsdom verifica lógica do DOM e integração HTTP, não renderização visual, layout ou todos os comportamentos de um navegador.
- Filtros de dados pessoais, escopo e prompt injection são preventivos e incompletos. A validação extrativa prova correspondência textual, não veracidade, atualidade ou relevância da fonte.
- Conformidade institucional com a LGPD e condições contratuais do provedor dependem das decisões descritas em `PRIVACIDADE.md`.

## Verificação no computador de destino

1. Abra o modo 1 e teste uma pergunta sobre a prova de Banco de Dados.
2. Crie o administrador; configure TOTP com `python configurar_2fa.py` para testar o segundo fator e antes de usar o modo oficial. Publique um TXT fictício; confirme a fonte no chat.
3. Reenvie o mesmo nome com outra data; confira que as consultas novas usam a atualização.
4. Exclua o documento; confirme a retirada das fontes.
5. Configure o modo 2 com MySQL e Gemini e repita os fluxos usando documentos públicos revisados.
6. Avalie perguntas sem resposta, conflitos de turma/ano, perguntas em inglês e entradas fora do escopo antes de atender alunos.
