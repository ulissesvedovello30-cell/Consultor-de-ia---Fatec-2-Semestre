'use strict';

class PainelUploads {
  constructor({requisitar, parametros, atualizar, autorizado}) {
    this.requisitar = requisitar; this.parametros = parametros;
    this.atualizar = atualizar; this.autorizado = autorizado;
    this.fila = new Map(); this.ocupado = false;
    this.zona = document.getElementById('drop-zone');
    this.entrada = document.getElementById('files');
    this.ligar();
  }

  ligar() {
    this.entrada.addEventListener('change', () => this.selecionar(this.entrada.files));
    this.zona.addEventListener('dragover', (evento) => this.destacar(evento));
    this.zona.addEventListener('dragleave', (evento) => {
      if (!evento.relatedTarget || !this.zona.contains(evento.relatedTarget)) this.zona.classList.remove('dragging');
    });
    this.zona.addEventListener('drop', (evento) => this.receberArrasto(evento));
    for (const tipo of ['dragover', 'drop']) {
      document.addEventListener(tipo, (evento) => this.impedirAbertura(evento));
    }
    this.renderizar();
  }

  impedirAbertura(evento) {
    const arquivos = Array.from(evento.dataTransfer?.types || []).includes('Files');
    if (arquivos && !document.getElementById('admin').hidden) evento.preventDefault();
  }

  destacar(evento) {
    evento.preventDefault();
    if (!this.ocupado) this.zona.classList.add('dragging');
    if (evento.dataTransfer) evento.dataTransfer.dropEffect = this.ocupado ? 'none' : 'copy';
  }

  receberArrasto(evento) {
    evento.preventDefault(); evento.stopPropagation();
    this.zona.classList.remove('dragging');
    this.selecionar(evento.dataTransfer?.files || []);
  }

  selecionar(arquivos) {
    if (this.ocupado || !this.autorizado()) return;
    const erros = [];
    for (const arquivo of Array.from(arquivos)) {
      try { this.validar(arquivo); this.fila.set(this.chave(arquivo), arquivo); }
      catch (erro) { erros.push(`${arquivo.name}: ${erro.message}`); }
    }
    this.entrada.value = ''; this.renderizar();
    this.informar(erros.join('\n') || 'Confira os arquivos e clique em Publicar no acervo.');
  }

  validar(arquivo) {
    if (!/\.(pdf|docx|txt)$/i.test(arquivo.name)) throw new Error('Envie PDF, DOCX ou TXT.');
    if (arquivo.size === 0) throw new Error('O arquivo está vazio.');
    if (arquivo.size > 25 * 1024 * 1024) throw new Error('O arquivo excede 25 MB.');
  }

  chave(arquivo) {
    return arquivo.name.normalize('NFC').toLocaleLowerCase('pt-BR');
  }

  informar(texto) {
    document.getElementById('upload-status').textContent = texto;
  }

  renderizar() {
    const lista = document.getElementById('upload-queue'); lista.replaceChildren();
    for (const [chave, arquivo] of this.fila) lista.append(this.linha(chave, arquivo));
    const total = this.fila.size;
    document.getElementById('upload-count').textContent = total ? `${total} arquivo(s) selecionado(s).` : 'Nenhum arquivo selecionado.';
  }

  linha(chave, arquivo) {
    const linha = document.createElement('li');
    const nome = document.createElement('span');
    nome.textContent = `${arquivo.name} · ${(arquivo.size / 1024).toFixed(1)} KB`;
    const remover = document.createElement('button'); remover.type = 'button';
    remover.textContent = 'Remover'; remover.disabled = this.ocupado;
    remover.setAttribute('aria-label', `Remover ${arquivo.name}`);
    remover.addEventListener('click', () => this.remover(chave));
    linha.append(nome, remover); return linha;
  }

  remover(chave) {
    if (this.ocupado) return;
    this.fila.delete(chave); this.renderizar();
  }

  ocupar(ocupado) {
    this.ocupado = ocupado;
    document.getElementById('upload-form').setAttribute('aria-busy', String(ocupado));
    for (const campo of document.querySelectorAll('#upload-form input, #upload-form button')) campo.disabled = ocupado;
    this.zona.classList.toggle('busy', ocupado);
    document.getElementById('upload').textContent = ocupado ? 'Publicando…' : 'Publicar no acervo';
  }

  conferirEnvio() {
    if (!this.autorizado()) throw new Error('Entre na administração para publicar.');
    if (!this.fila.size) throw new Error('Arraste ou selecione pelo menos um arquivo.');
    if (!document.getElementById('public-check').checked) throw new Error('Confirme a revisão pública dos arquivos.');
  }

  async enviar() {
    if (this.ocupado) return;
    try {
      this.conferirEnvio(); this.ocupar(true); await this.enviarFila();
    } catch (erro) { this.informar(erro.message); }
    finally { this.ocupar(false); this.renderizar(); }
  }

  async enviarFila() {
    const arquivos = Array.from(this.fila.entries()); const resultados = [];
    this.progresso(0, arquivos.length);
    for (const [chave, arquivo] of arquivos) {
      if (!this.autorizado()) break;
      this.informar(`Enviando e indexando ${arquivo.name}… Aguarde a confirmação.`);
      resultados.push(await this.publicarDaFila(chave, arquivo));
      this.progresso(resultados.length, arquivos.length);
    }
    if (this.autorizado()) { this.informar(resultados.join('\n')); await this.atualizar(); }
  }

  async publicarDaFila(chave, arquivo) {
    try {
      const dados = await this.publicar(arquivo); this.fila.delete(chave);
      return `${arquivo.name}: ${dados.trechos} trechos publicados. Disponível no chatbot.`;
    } catch (erro) { return `${arquivo.name}: ${erro.message}`; }
  }

  async publicar(arquivo) {
    this.validar(arquivo);
    const dados = await this.requisitar(`/api/admin/documentos?${this.parametros(arquivo)}`, {
      method: 'POST', body: arquivo, timeout: 310000,
    });
    if (dados.estado !== 'indexado' || !Number.isInteger(dados.trechos) || dados.trechos < 1) {
      throw new Error('Indexação não confirmada. Confira o acervo antes de repetir.');
    }
    return dados;
  }

  progresso(concluidos, total) {
    const barra = document.getElementById('upload-progress');
    barra.hidden = false; barra.max = total; barra.value = concluidos;
    barra.textContent = `${concluidos} de ${total} arquivo(s) processado(s)`;
  }

  limpar() {
    this.fila.clear(); this.entrada.value = ''; this.renderizar();
    document.getElementById('public-check').checked = false;
    for (const id of ['course', 'period', 'year', 'source-url', 'valid-from', 'valid-until']) {
      const campo = document.getElementById(id);
      if (campo) campo.value = '';
    }
    document.getElementById('upload-progress').hidden = true;
    this.informar('');
  }
}

window.PainelUploads = PainelUploads;
