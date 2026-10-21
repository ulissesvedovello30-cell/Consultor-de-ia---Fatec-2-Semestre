import threading
import time


class GeradorLocal:
    """Gera texto com um modelo de chat do Hugging Face rodando na própria máquina."""

    def __init__(
        self,
        nome_modelo: str,
        max_novos_tokens: int = 512,
        penalidade_repeticao: float = 1.08,
        tempo_limite: float = 120.0,
        max_contexto: int = 4096,
    ):
        if max_novos_tokens <= 0 or tempo_limite <= 0 or max_contexto <= max_novos_tokens:
            raise ValueError("Configuração inválida do gerador: confira tokens, tempo limite e contexto.")
        self.nome_modelo = nome_modelo
        self._max_novos_tokens = max_novos_tokens
        self._penalidade_repeticao = penalidade_repeticao
        self._tempo_limite = tempo_limite
        self._max_contexto = max_contexto
        self._tokenizer = None
        self._modelo = None
        # Uma geração por vez: o modelo ocupa muita memória e gerações em paralelo
        # só brigariam pela mesma CPU/GPU.
        self._trava = threading.Lock()

    def carregar(self) -> None:
        """Carrega o modelo agora. Chame na inicialização para falhar cedo, não na 1ª pergunta."""
        with self._trava:
            self._garantir_modelo()

    def gerar(self, mensagens: list[dict[str, str]]) -> str:
        """`mensagens` no formato de chat: [{"role": "system"|"user", "content": "..."}]."""
        with self._trava:
            tokenizer, modelo = self._garantir_modelo()
            from transformers import StoppingCriteria, StoppingCriteriaList

            fim = time.monotonic() + self._tempo_limite

            class Prazo(StoppingCriteria):
                """Para a geração quando o tempo acaba; sem isso, CPU lenta travaria o bot."""

                def __call__(self, input_ids, scores, **kwargs):
                    import torch

                    estourou = time.monotonic() >= fim
                    return torch.full((input_ids.shape[0],), estourou, dtype=torch.bool, device=input_ids.device)

            prompt = tokenizer.apply_chat_template(mensagens, tokenize=False, add_generation_prompt=True)
            entradas = tokenizer(prompt, return_tensors="pt").to(modelo.device)
            tamanho_prompt = entradas["input_ids"].shape[-1]
            if tamanho_prompt + self._max_novos_tokens > self._max_contexto:
                raise ValueError("O contexto enviado ao modelo passa do limite configurado.")

            saida = modelo.generate(
                **entradas,
                max_new_tokens=self._max_novos_tokens,
                do_sample=False,  # sem sorteio: a mesma pergunta dá a mesma resposta
                repetition_penalty=self._penalidade_repeticao,
                pad_token_id=tokenizer.eos_token_id,
                stopping_criteria=StoppingCriteriaList([Prazo()]),
            )
            if time.monotonic() >= fim:
                raise TimeoutError("Tempo de geração excedido.")

        # `generate` devolve prompt + resposta; só os tokens novos interessam.
        texto = tokenizer.decode(saida[0][tamanho_prompt:], skip_special_tokens=True).strip()
        if not texto:
            raise ValueError("O modelo devolveu uma resposta vazia.")
        return texto

    def _garantir_modelo(self):
        if self._modelo is None:
            # import tardio: carregar torch/transformers leva segundos
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.nome_modelo)
            self._modelo = AutoModelForCausalLM.from_pretrained(
                self.nome_modelo,
                dtype="auto",
                device_map="auto",  # usa GPU se houver, senão CPU
            )
        return self._tokenizer, self._modelo
