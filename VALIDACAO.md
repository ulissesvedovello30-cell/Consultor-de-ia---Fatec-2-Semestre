# Verificação do MVP

Instale as dependências e execute:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

A suíte utiliza arquivos SQLite temporários. Verifica criação e reabertura do banco, chaves estrangeiras, rollback e publicações concorrentes. Também verifica a primeira carga, retomada após falha, ausência de embeddings repetidos no reinício, preservação de exclusões, consulta pública, upload, autenticação com segundo fator e tratamento de falhas do Gemini.

Os testes do fluxo MVP usam os adaptadores Gemini do aplicativo com um transporte HTTP simulado. Não existe um modo offline selecionável no servidor. Substitutos lexicais permanecem apenas nos testes antigos para verificar regras isoladas sem rede.

Para testar a interface automaticamente, use Node.js 22 ou superior. No primeiro terminal, execute `python -m tests.servidor_ui`. No segundo, entre em `tests_front`, execute `npm install` e depois `npm test`. Para cobrir o segundo fator, defina `TESTE_TOTP=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` nos dois terminais. Esse segredo é um vetor público de teste e não deve ser usado em uma conta real. O servidor de testes usa dependências substitutas, porta de loopback e banco temporário.

Para validar o uso real, configure a chave e os modelos Gemini, e-mail, senha e autenticador conforme o LEIA-ME.md. Inicie o servidor, consulte uma pergunta da FAQ e uma pergunta sobre cada curso, confira as fontes e teste a publicação de um documento revisado. Reinicie e verifique a persistência do acervo.

A revisão automatizada foi executada em Python 3.12. A equipe adotou Python 3.15; a instalação e a execução nesse interpretador precisam ser verificadas no ambiente de destino. Os testes não confirmam disponibilidade, cotas ou permissões da conta Gemini, nem medem a qualidade semântica das respostas reais. Não foi aberto um túnel ngrok real. PostgreSQL não está implementado nesta entrega.

O iniciador foi verificado com criação real de uma venv isolada, reutilização, diretório com espaços, preservação de configuração e interrupção após falha de instalação. O teste usa requirements vazios e servidor substituto para não instalar pacotes nem chamar Gemini. O arquivo `.bat` requer validação no Windows; a execução disponível nesta revisão foi Linux.
