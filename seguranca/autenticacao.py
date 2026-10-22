"""Autenticação independente do FastAPI, com armazenamento e verificador injetados."""
import hashlib
import hmac
import threading
import time
from seguranca.contratos import ArmazemLogin, CredenciaisInvalidas, LoginIndisponivel
from seguranca.totp import verificar


class AutenticadorSecretaria:
    """Orquestre cotas duráveis, senha e TOTP sem conhecer HTTP ou o acervo."""

    def __init__(self, repositorio: ArmazemLogin, config, segredo, conferir, exigir_2fa, relogio=time.time):
        """Injete persistência, configuração, segredo HMAC e verificador de senha."""
        self.repo, self.config, self.segredo = repositorio, config, segredo
        self.conferir, self.exigir_2fa, self.relogio = conferir, exigir_2fa, relogio
        self.vagas = threading.BoundedSemaphore(2)

    def autenticar(self, ip, usuario, senha, otp):
        """Valide credenciais sob cotas sem confiar em privilégios enviados pelo cliente.

        Args:
            ip: Endereço reconhecido pelo servidor ou pelo proxy confiável.
            usuario: Nome declarado, limitado e validado pelo adaptador HTTP.
            senha: Senha em texto somente para verificação em memória.
            otp: Código TOTP de seis dígitos quando o segundo fator for exigido.

        Returns:
            None quando todos os fatores forem aceitos.

        Raises:
            CredenciaisInvalidas: Conta, senha ou segundo fator inválido.
            LoginIndisponivel: Configuração incompleta ou capacidade ocupada.
            TentativasExcedidas: Cota de autenticação esgotada.
            FalhaSeguranca: Persistência de proteção indisponível.
        """
        self._configurado()
        chaves = (self._chave('ip', ip), self._chave('conta', usuario.casefold()), self._chave('global', 'login'))
        self.repo.reservar(chaves, self.relogio())
        if not self.vagas.acquire(blocking=False):
            raise LoginIndisponivel('Autenticação ocupada.')
        try:
            self._credenciais(usuario, senha, otp)
        finally:
            self.vagas.release()

    def _configurado(self):
        """Recuse administração sem senha ou sem TOTP obrigatório no modo oficial."""
        if not self.config.senha_hash or (self.exigir_2fa and not self.config.totp_segredo):
            raise LoginIndisponivel('Configure senha e segundo fator no servidor.')

    def _credenciais(self, usuario, senha, otp):
        """Verifique senha mesmo para usuário incorreto, sem enumerar contas."""
        valida = self.conferir(senha, self.config.senha_hash)
        conta = hmac.compare_digest(usuario.encode(), self.config.usuario.encode())
        if not (valida and conta):
            raise CredenciaisInvalidas('Credenciais inválidas.')
        if self.exigir_2fa or self.config.totp_segredo:
            self._segundo_fator(otp)

    def _segundo_fator(self, otp):
        """Valide e consuma TOTP, rejeitando repetição de um código já usado."""
        passo = verificar(self.config.totp_segredo, otp, self.relogio())
        chave = self._chave('totp', self.config.usuario + self.config.totp_segredo)
        if passo is None or not self.repo.consumir_codigo(chave, passo):
            raise CredenciaisInvalidas('Credenciais inválidas.')

    def _chave(self, categoria, valor):
        """Pseudonimize identificadores antes da persistência, com separação de domínio."""
        return hmac.new(self.segredo, (categoria + ':' + valor).encode(), hashlib.sha256).hexdigest()
