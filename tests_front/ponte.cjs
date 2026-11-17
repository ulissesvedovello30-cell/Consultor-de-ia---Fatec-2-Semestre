'use strict';
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const path = require('node:path');
const fs = require('node:fs');

function abrirPonte(origem) {
  const raiz = path.resolve(__dirname, '..');
  const local = path.join(raiz, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const python = process.env.PYTHON_TESTES || (fs.existsSync(local) ? local : 'python');
  const processo = spawn(python, ['-u', '-m', 'tests.apoio.ponte_http'], {
    cwd: raiz, env: {...process.env, TESTE_ORIGEM: origem}, stdio: ['pipe', 'pipe', 'inherit']
  });
  const pendentes = [];
  let resolverInicio, rejeitarInicio;
  const pronta = new Promise((resolve, reject) => { resolverInicio = resolve; rejeitarInicio = reject; });
  const linhas = createInterface({input: processo.stdout});
  linhas.on('line', (linha) => {
    try {
      const resposta = JSON.parse(linha);
      if (resposta.pronta) resolverInicio();
      else pendentes.shift()?.resolve(resposta);
    } catch (erro) { rejeitarInicio(erro); }
  });
  const falhar = (erro) => { rejeitarInicio(erro); pendentes.splice(0).forEach((p) => p.reject(erro)); };
  processo.on('error', falhar);
  processo.on('exit', (codigo) => { if (codigo) falhar(new Error(`Ponte ASGI encerrada: ${codigo}`)); });
  return {
    pronta,
    async enviar(pedido) {
      await pronta;
      return new Promise((resolve, reject) => {
        pendentes.push({resolve, reject});
        processo.stdin.write(JSON.stringify(pedido) + '\n');
      });
    },
    fechar() { processo.stdin.end(); linhas.close(); }
  };
}
module.exports = {abrirPonte};
