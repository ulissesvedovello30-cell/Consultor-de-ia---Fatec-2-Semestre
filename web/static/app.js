'use strict';
const $ = (id) => document.getElementById(id);
const state = {csrf: '', admin: false, chatEpoch: 0, pending: false};
const status = (id, message = '') => { $(id).textContent = message; };

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeout || 185000);
  try {
    return await fetchJson(path, options, controller.signal);
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Tempo de espera excedido. Confira o estado antes de repetir.');
    throw error instanceof TypeError ? new Error('Não foi possível conectar ao servidor.') : error;
  } finally { clearTimeout(timer); }
}
async function fetchJson(path, options, signal) {
  const headers = {'X-CSRF-Token': state.csrf, ...options.headers};
  const response = await fetch(path, {...options, headers, signal, credentials: 'same-origin'});
  const data = await parseJson(response);
  if (response.status === 401) { state.admin = false; renderAdmin(); }
  if (!response.ok) throw new Error(data.detail || data.texto || `Falha na requisição (${response.status}).`);
  return data;
}
async function parseJson(response) {
  try { return await response.json(); }
  catch { throw new Error('O servidor devolveu uma resposta inválida. Tente novamente.'); }
}
const jsonOptions = (data) => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
async function session() {
  const data = await request('/api/sessao');
  state.csrf = data.csrf; state.admin = data.admin;
  $('otp-label').hidden = !data.exige_2fa; $('otp').required = !!data.exige_2fa;
  renderAdmin();
}
async function show(view) {
  ['home', 'chat', 'admin', 'privacy'].forEach((id) => { $(id).hidden = id !== view; });
  if (view === 'admin') await refreshAdmin();
}
function renderAdmin() {
  $('login-form').hidden = state.admin;
  $('admin-panel').hidden = !state.admin;
  if (!state.admin) $('documents').replaceChildren();
}
async function refreshAdmin() {
  try { await session(); if (state.admin) await listDocuments(); }
  catch (error) { status('login-status', error.message); }
}
function message(role, text, sources = []) {
  const block = document.createElement('div');
  block.className = `message ${role}`;
  const label = document.createElement('strong'); label.textContent = role === 'user' ? 'VOCÊ' : 'CONSULTOR';
  block.append(label, document.createTextNode(text));
  addSources(block, sources);
  $('messages').append(block); $('messages').scrollTop = $('messages').scrollHeight;
}
function safeSource(url) {
  const parsed = new URL(url, location.origin);
  if (parsed.origin !== location.origin || !parsed.pathname.startsWith('/api/fontes/')) throw new Error('Fonte inválida.');
  return parsed.href;
}
function addSources(block, sources) {
  const container = document.createElement('div'); container.className = 'sources';
  for (const source of sources) {
    try {
      const link = document.createElement('a'); link.href = safeSource(source.url);
      link.textContent = `${source.arquivo}${source.pagina ? ` · p. ${source.pagina}` : ''}`;
      link.target = '_blank'; link.rel = 'noopener noreferrer'; container.append(link);
    } catch { /* Uma fonte inválida não é convertida em link executável. */ }
  }
  block.append(container);
}
async function send(event) {
  event.preventDefault();
  if (state.pending) return;
  const text = $('question').value.trim();
  if (!text) return;
  const epoch = state.chatEpoch; state.pending = true; $('send').disabled = true;
  message('user', text); $('question').value = ''; status('chat-status', 'Consultando os documentos…');
  try { await sendQuestion(text, epoch); }
  catch (error) { if (epoch === state.chatEpoch) status('chat-status', error.message); }
  finally { state.pending = false; $('send').disabled = false; }
}
async function sendQuestion(text, epoch) {
  await session();
  const data = await request('/api/chat', jsonOptions({texto: text}));
  if (typeof data.texto !== 'string' || !Array.isArray(data.fontes)) throw new Error('Resposta do chat inválida.');
  if (epoch !== state.chatEpoch) return;
  message('bot', data.texto, data.fontes); status('chat-status');
}
async function clearChat() {
  try {
    await session(); await request('/api/conversa', {method: 'DELETE'});
    state.chatEpoch++; $('messages').replaceChildren(); status('chat-status', 'Conversa apagada do aplicativo.');
  } catch (error) { status('chat-status', error.message); }
}
async function login(event) {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { await authenticate(); }
  catch (error) { status('login-status', error.message); }
  finally { $('password').value = ''; $('otp').value = ''; button.disabled = false; }
}
async function authenticate() {
  await session();
  const data = await request('/api/admin/login', jsonOptions({usuario: $('username').value, senha: $('password').value, otp: $('otp').value}));
  state.csrf = data.csrf; state.admin = data.admin; renderAdmin(); status('login-status');
  await listDocuments();
}
async function logout() {
  try { await request('/api/admin/logout', {method: 'POST'}); state.admin = false; renderAdmin(); await session(); }
  catch (error) { status('docs-status', error.message); }
}
async function listDocuments() {
  try {
    const documents = await request('/api/admin/documentos');
    if (!Array.isArray(documents)) throw new Error('Lista de documentos inválida.');
    $('documents').replaceChildren(); documents.forEach(renderDocument);
    status('docs-status', documents.length ? `${documents.length} documento(s).` : 'Nenhum documento publicado.');
  } catch (error) { status('docs-status', error.message); }
}
function renderDocument(doc) {
  const row = document.createElement('article'); row.className = 'doc';
  const title = document.createElement('h3'); title.textContent = doc.nome;
  const info = document.createElement('p'); info.className = 'muted';
  info.textContent = [doc.curso, doc.periodo, doc.ano, doc.fim && `Válido até ${doc.fim}`].filter(Boolean).join(' · ') || 'Sem filtros de turma ou vigência';
  const button = document.createElement('button'); button.textContent = 'Excluir definitivamente';
  button.addEventListener('click', () => removeDocument(doc, button));
  row.append(title, info, button); $('documents').append(row);
}
async function removeDocument(doc, button) {
  if (!confirm(`Apagar textos e vetores de “${doc.nome}”? Esta ação não pode ser desfeita pelo painel.`)) return;
  button.disabled = true;
  try { await request(`/api/admin/documentos/${encodeURIComponent(doc.id)}`, {method: 'DELETE'}); await listDocuments(); }
  catch (error) { status('docs-status', error.message); button.disabled = false; }
}
function uploadParameters(file) {
  const params = new URLSearchParams({nome: file.name, publico: 'true'});
  const fields = {curso: 'course', periodo: 'period', ano: 'year', inicio: 'valid-from', fim: 'valid-until', url_oficial: 'source-url'};
  Object.entries(fields).forEach(([key, id]) => { if ($(id).value) params.set(key, $(id).value); });
  return params;
}
async function upload(event) {
  event.preventDefault(); $('upload').disabled = true;
  try { await uploadFiles(); }
  catch (error) { status('upload-status', error.message); }
  finally { $('upload').disabled = false; await listDocuments(); }
}
async function uploadFiles() {
  const files = Array.from($('files').files); const results = [];
  for (const file of files) {
    status('upload-status', `Processando ${file.name}… aguarde a confirmação.`);
    results.push(await uploadOne(file));
  }
  status('upload-status', results.join('\n'));
}
async function uploadOne(file) {
  try {
    if (file.size > 25 * 1024 * 1024) throw new Error('Arquivo excede 25 MB.');
    const data = await request(`/api/admin/documentos?${uploadParameters(file)}`, {method: 'POST', body: file, timeout: 310000});
    if (data.estado !== 'indexado') throw new Error('Indexação não confirmada.');
    return `${file.name}: ${data.trechos} trechos publicados.`;
  } catch (error) { return `${file.name}: ${error.message}`; }
}
async function forget() {
  try {
    await session(); await request('/api/sessao', {method: 'DELETE'});
    state.csrf = ''; state.admin = false; state.chatEpoch++;
    $('messages').replaceChildren(); renderAdmin(); status('privacy-status', 'Sessão e contexto removidos do aplicativo.');
  } catch (error) { status('privacy-status', error.message); }
}
async function serviceInfo() {
  const info = await request('/api/info');
  $('mode').textContent = info.modo === 'debug' ? 'DEMONSTRAÇÃO · dados fictícios · sem Gemini' : 'GEMINI · acervo público';
  $('privacy-contact').textContent = `${info.responsavel} — ${info.contato}`;
  const health = await request('/api/health');
  if (!health.pronto) throw new Error('Serviço indisponível.');
}
function bind() {
  document.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => show(b.dataset.view)));
  document.querySelectorAll('[data-question]').forEach((b) => b.addEventListener('click', () => { $('question').value = b.dataset.question; $('question').focus(); }));
  $('chat-form').addEventListener('submit', send); $('login-form').addEventListener('submit', login);
  $('upload-form').addEventListener('submit', upload); $('clear').addEventListener('click', clearChat);
  $('logout').addEventListener('click', logout); $('refresh').addEventListener('click', listDocuments);
  $('forget').addEventListener('click', forget);
}
async function start() {
  bind();
  try { await session(); await serviceInfo(); }
  catch (error) { status('global-status', error.message); $('mode').textContent = 'Serviço não confirmado'; }
}
start();
