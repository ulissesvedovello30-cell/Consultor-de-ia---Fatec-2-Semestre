'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const base = 'http://127.0.0.1:8767';
const staticDir = path.join(__dirname, '../web/static');
const html = fs.readFileSync(path.join(staticDir, 'index.html'), 'utf8');
const dom = new JSDOM(html, {url: base, runScripts: 'outside-only', pretendToBeVisual: true});
const w = dom.window;
let cookie = '';
let requests = [];
w.AbortController = AbortController;
w.confirm = () => true;
w.fetch = async (url, options = {}) => {
  const headers = {...options.headers, Origin: base};
  if (cookie) headers.Cookie = cookie;
  let body = options.body;
  if (body instanceof w.File) {
    body = await new Promise((resolve, reject) => {
      const reader = new w.FileReader();
      reader.onload = () => resolve(Buffer.from(reader.result));
      reader.onerror = reject;
      reader.readAsArrayBuffer(body);
    });
  }
  requests.push(String(url));
  const response = await fetch(new URL(url, base), {...options, headers, body});
  const set = response.headers.get('set-cookie');
  if (set) cookie = set.split(';')[0];
  return response;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function ready() {
  for (let i = 0; i < 100; i++) {
    if (w.document.getElementById('mode').textContent.includes('DEMONSTRAÇÃO')) return;
    await sleep(30);
  }
  throw new Error('Inicialização não concluída: ' + w.document.getElementById('global-status').textContent);
}
function testOtp() {
  // Segredo fictício correspondente ao vetor RFC usado exclusivamente pelo servidor de testes.
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = crypto.createHmac('sha1', Buffer.from('12345678901234567890')).update(counter).digest();
  const number = (digest.readUInt32BE(digest[19] & 15) & 0x7fffffff) % 1000000;
  return String(number).padStart(6, '0');
}
async function run() {
  w.eval(fs.readFileSync(path.join(staticDir, 'app.js'), 'utf8') + '\nObject.assign(window, {show, send, clearChat, login, uploadOne, listDocuments, request, removeDocument, message, forget});');
  await ready();
  assert.equal(w.document.querySelectorAll('input[type=password]').length, 1);
  await w.show('chat');
  w.document.getElementById('question').value = 'Quando é a prova de Banco de Dados?';
  await w.send({preventDefault(){}});
  assert.match(w.document.getElementById('messages').textContent, /11 de novembro/);
  assert.equal(w.document.getElementById('send').disabled, false);
  assert.ok(w.document.querySelector('.sources a').href.startsWith(base + '/api/fontes/'));
  console.log('OK: chat público e fontes reais pela API');
  await w.clearChat();
  assert.equal(w.document.querySelectorAll('.message').length, 0);
  console.log('OK: limpeza no frontend e backend');
  await w.show('admin');
  w.document.getElementById('username').value = 'admin';
  w.document.getElementById('password').value = 'senha-teste-interface-123';
  assert.equal(w.document.getElementById('otp-label').hidden, !process.env.TESTE_TOTP);
  if (process.env.TESTE_TOTP) w.document.getElementById('otp').value = testOtp();
  const button = w.document.querySelector('#login-form button');
  await w.login({preventDefault(){}, submitter:button});
  assert.equal(w.document.getElementById('admin-panel').hidden, false);
  assert.equal(w.document.getElementById('password').value, '');
  assert.equal(w.document.getElementById('otp').value, '');
  const file = new w.File(['Prova de Redes dia 17 na sala 7.'], 'teste-interface.txt', {type:'text/plain'});
  assert.match(await w.uploadOne(file), /publicados/);
  await w.listDocuments();
  assert.match(w.document.getElementById('documents').textContent, /teste-interface.txt/);
  console.log('OK: login, upload e listagem reais');
  const list = await w.request('/api/admin/documentos');
  const doc = list.find((d) => d.nome === 'teste-interface.txt');
  await w.removeDocument(doc, w.document.createElement('button'));
  assert.ok(!w.document.getElementById('documents').textContent.includes('teste-interface.txt'));
  console.log('OK: exclusão real');
  w.message('bot', '<img src=x onerror=alert(1)>', [{arquivo:'<script>x</script>',url:'javascript:alert(1)'}]);
  assert.equal(w.document.querySelectorAll('#messages img, #messages script').length,0);
  assert.equal(w.document.querySelectorAll('#messages a').length,0);
  console.log('OK: XSS renderizado como texto e URL perigosa recusada');
  const originalFetch = w.fetch;
  w.fetch = async () => { throw new w.TypeError('NetworkError'); };
  w.document.getElementById('question').value = 'Quando é a prova?';
  await w.send({preventDefault(){}});
  assert.match(w.document.getElementById('chat-status').textContent, /conectar/);
  assert.equal(w.document.getElementById('send').disabled,false);
  w.fetch = async () => ({ok:true,status:200,json:async()=>{throw new SyntaxError('json')}});
  await assert.rejects(w.request('/invalid'), /resposta inválida/);
  w.fetch = originalFetch;
  console.log('OK: falha de rede e JSON inválido');
  await w.forget();
  assert.equal(w.document.getElementById('admin-panel').hidden,true);
  assert.equal(w.document.querySelectorAll('.message').length,0);
  console.log('OK: remoção de sessão e contexto');
  dom.window.close();
}
run().catch((error) => {console.error(error);dom.window.close();process.exitCode=1;});
