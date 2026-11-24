'use strict';
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const path = require('node:path');

function arquivoPdf(w) {
  const python = process.env.PYTHON_TESTES || 'python';
  const programa = "import sys; from tests.apoio.pdf_publico import criar_pdf; sys.stdout.buffer.write(criar_pdf('O Laboratorio de Cartografia da Fatec fica na sala 42 do bloco norte.'))";
  const resultado = spawnSync(python, ['-c', programa], {cwd: path.resolve(__dirname, '..')});
  assert.equal(resultado.status, 0, resultado.stderr.toString());
  return new w.File([resultado.stdout], 'laboratorio-interface.pdf', {type: 'application/pdf'});
}

function arrastar(w, arquivos) {
  const evento = new w.Event('drop', {bubbles: true, cancelable: true});
  Object.defineProperty(evento, 'dataTransfer', {value: {files: arquivos, types: ['Files']}});
  w.document.getElementById('drop-zone').dispatchEvent(evento);
  assert.equal(evento.defaultPrevented, true);
}

function selecionar(w, arquivos) {
  const entrada = w.document.getElementById('files');
  Object.defineProperty(entrada, 'files', {value: arquivos, configurable: true});
  entrada.dispatchEvent(new w.Event('change', {bubbles: true}));
}

async function enviar(w) {
  w.document.getElementById('public-check').checked = true;
  w.document.getElementById('upload-form').dispatchEvent(new w.Event('submit', {bubbles: true, cancelable: true}));
  assert.equal(w.document.getElementById('upload').disabled, true);
  for (let i = 0; i < 500; i++) {
    if (!w.document.getElementById('upload').disabled) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error('O upload não concluiu dentro do prazo de teste.');
}

async function testarPublicacao(w) {
  arrastar(w, [new w.File(['invalido'], 'programa.exe')]);
  assert.match(w.document.getElementById('upload-status').textContent, /Envie PDF/);
  assert.equal(w.document.querySelectorAll('#upload-queue li').length, 0);
  const pdf = arquivoPdf(w);
  selecionar(w, [pdf]);
  assert.equal(w.document.querySelectorAll('#upload-queue li').length, 1);
  assert.equal(w.document.getElementById('files').required, false);
  w.document.querySelector('#upload-queue button').click();
  assert.equal(w.document.querySelectorAll('#upload-queue li').length, 0);
  arrastar(w, [pdf, pdf]);
  assert.equal(w.document.querySelectorAll('#upload-queue li').length, 1);
  assert.ok(!(await w.request('/api/admin/documentos')).some((d) => d.nome === pdf.name));
  await enviar(w);
  assert.match(w.document.getElementById('upload-status').textContent, /Disponível no chatbot/);
  assert.equal(w.document.querySelectorAll('#upload-queue li').length, 0);
  assert.match(w.document.getElementById('documents').textContent, /laboratorio-interface.pdf/);
  await w.show('chat');
  w.document.getElementById('question').value = 'Onde fica o Laboratorio de Cartografia da Fatec?';
  await w.send({preventDefault(){}});
  assert.match(w.document.getElementById('messages').textContent, /sala 42/);
  await w.show('admin');
  arrastar(w, [new w.File(['%PDF-falso'], 'invalido.pdf', {type:'application/pdf'})]);
  await enviar(w);
  assert.doesNotMatch(w.document.getElementById('upload-status').textContent, /Disponível no chatbot/);
  assert.equal(w.document.querySelectorAll('#upload-queue li').length, 1);
  assert.ok(!(await w.request('/api/admin/documentos')).some((d) => d.nome === 'invalido.pdf'));
  console.log('OK: seleção, arraste, remoção, deduplicação, publicação PDF e consulta pelo chat');
  console.log('OK: PDF inválido fica na fila para correção e não entra no acervo');
}

module.exports = {testarPublicacao};
