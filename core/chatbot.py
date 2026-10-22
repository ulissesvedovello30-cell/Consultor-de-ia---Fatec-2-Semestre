import logging
import re
import time
from servicos.politica import validar_pergunta, EntradaRecusada
from core.limitador import LimitadorTaxa
from dominio.erros import ErroGeracaoResposta, ErroBusca, ErroBancoDeDados, ErroOcupado, ErroPrazo
from dominio.resposta_chatbot import RespostaChatbot

logger = logging.getLogger(__name__)
ERROS = {
    EntradaRecusada: ('Entrada recusada. Use apenas informações institucionais públicas, sem dados pessoais.', 'invalida'),
    ErroBusca: ('Não consegui consultar os documentos. Tente novamente.', 'indisponivel'),
    ErroBancoDeDados: ('Acervo indisponível. Tente novamente.', 'indisponivel'),
    ErroGeracaoResposta: ('Não consegui gerar a resposta agora. Tente novamente.', 'indisponivel'),
    ErroOcupado: ('Atendimento ocupado. Tente novamente em instantes.', 'ocupado'),
    ErroPrazo: ('O atendimento excedeu o tempo disponível. Tente novamente.', 'prazo'),
}


class Chatbot:
    AJUDA = ('Olá! Consulte informações públicas da faculdade, como calendário, provas e secretaria. '
             'Não envie RA, CPF, senhas ou outros dados pessoais. Use /ajuda ou /limpar. '
             'Confira as fontes; respostas por IA podem conter erros.')
    MAX_CARACTERES = 1500
    SEGUNDOS_DE_CONTEXTO = 600
    _SAUDACAO = re.compile(r'(oi+|ol[aá]|e a[ií]|bom dia|boa tarde|boa noite|hello|hey)[\s!.?]*', re.I)
    _REFERE_ANTERIOR = re.compile(r'\b(isso|disso|esse|essa|desse|dessa|nele|nela)\b', re.I)

    def __init__(self, consultor, limitador=None, max_simultaneos=2, relogio=time.monotonic):
        """Inicialize dependências e estado da instância com os parâmetros fornecidos."""
        self._consultor = consultor
        self._limitador = limitador or LimitadorTaxa(6, 60)
        self._max_simultaneos, self._relogio = max_simultaneos, relogio
        self._em_atendimento = 0
        self._ultima_pergunta = {}
        self._pendentes = {}

    async def processar_mensagem(self, conversa_id, texto):
        """Processe comandos ou consulta pública e controle a retenção temporária.
        
        Args:
            conversa_id: Identificador opaco da sessão, sem cadastro do aluno.
            texto: Texto de entrada ou passagem documental.
        
        Returns:
            RespostaChatbot com texto, fontes e estado de atendimento.
        """
        pronta = self._validar(conversa_id, texto := texto.strip())
        if pronta is not None:
            return pronta
        identificador = self._pendentes[conversa_id] = object()
        try:
            resposta = await self._consultar(self._com_contexto(conversa_id, texto))
            self._memorizar(conversa_id, texto, identificador, resposta)
            return resposta
        finally:
            self._concluir(conversa_id, identificador)

    def _memorizar(self, conversa_id, texto, identificador, resposta):
        """Guarde somente pergunta respondida cuja operação ainda não foi apagada."""
        if resposta.sucesso and self._pendentes.get(conversa_id) is identificador:
            self._ultima_pergunta[conversa_id] = (self._relogio(), texto)

    def _validar(self, conversa_id, texto):
        """Valide tamanho e comandos antes de iniciar a consulta."""
        if not texto or len(texto) > self.MAX_CARACTERES:
            return RespostaChatbot('Envie entre 1 e 1500 caracteres.', False, 0, estado='invalida')
        comando = texto.split()[0].lower().split('@')[0]
        if comando in {'/start', '/ajuda'} or self._SAUDACAO.fullmatch(texto):
            return RespostaChatbot(self.AJUDA, True, 0)
        if comando == '/limpar':
            self.limpar(conversa_id)
            return RespostaChatbot('Conversa limpa.', True, 0)
        return self._validar_comando(conversa_id, comando)

    def _limites(self, conversa_id):
        """Retorne aviso de saturação ou excesso de perguntas; retorne None se permitido."""
        if self._em_atendimento >= self._max_simultaneos:
            return RespostaChatbot('Atendimento ocupado. Tente novamente.', False, 0, estado='ocupado')
        if not self._limitador.permitir(conversa_id):
            return RespostaChatbot('Limite de perguntas por minuto. Aguarde.', False, 0, estado='limite')
        return None

    async def _consultar(self, texto):
        """Valide a política de entrada e converta falhas do consultor em resposta segura."""
        self._em_atendimento += 1
        try:
            validar_pergunta(texto)
            resposta = await self._consultor.responder(texto)
            return self._converter(resposta)
        except tuple(ERROS) as erro:
            return converter_erro(erro)
        finally:
            self._em_atendimento -= 1

    def _converter(self, resposta):
        """Converta resposta RAG em resultado de atendimento com fontes estruturadas."""
        score = max(0, min(1, resposta.melhor_similaridade))
        estado = 'respondida' if resposta.encontrou else 'sem_resposta'
        return RespostaChatbot(resposta.texto_com_fontes(), resposta.encontrou,
                              score, resposta.fontes, estado)

    def _com_contexto(self, conversa_id, texto):
        """Preserve pergunta atual e acrescente referência anterior limitada quando necessária."""
        self.expirar()
        anterior = self._ultima_pergunta.get(conversa_id)
        if anterior and self._REFERE_ANTERIOR.search(texto):
            return f'Pergunta atual: {texto}\nPergunta anterior (referência): {anterior[1][:500]}'
        return texto

    def limpar(self, conversa_id):
        """Remova o contexto temporário da conversa solicitante."""
        self._ultima_pergunta.pop(conversa_id, None)
        self._pendentes.pop(conversa_id, None)

    def expirar(self):
        """Remova registros temporários cujo prazo de retenção terminou."""
        agora = self._relogio()
        self._ultima_pergunta = {c: v for c, v in self._ultima_pergunta.items()
                                 if agora - v[0] < self.SEGUNDOS_DE_CONTEXTO}

    def _concluir(self, conversa_id, identificador):
        """Retire somente a operação pendente que ainda pertence a esta requisição."""
        if self._pendentes.get(conversa_id) is identificador:
            self._pendentes.pop(conversa_id, None)

    def _validar_comando(self, conversa_id, comando):
        """Recuse comandos desconhecidos ou aplique limites de uso."""
        if comando.startswith('/'):
            return RespostaChatbot('Comando desconhecido. Use /ajuda.', False, 0)
        return self._limites(conversa_id)


def converter_erro(erro):
    """Converta exceção conhecida em resposta sanitizada e registre apenas sua classe."""
    logger.warning('Falha controlada: %s', type(erro).__name__)
    mensagem, estado = ERROS[type(erro)]
    if isinstance(erro, EntradaRecusada):
        mensagem = str(erro)
    return RespostaChatbot(mensagem, False, 0, estado=estado)
