"""Liste modelos visíveis à chave sem enviar perguntas ou documentos ao Google."""
import config
from infra.gemini_http import ClienteGemini, ErroGemini


def main():
    """Mostre IDs que suportam generateContent para configurar GEMINI_MODELO."""
    cliente = ClienteGemini(config.GEMINI_API_KEY)
    try:
        for modelo in cliente.modelos().get('models', []):
            if 'generateContent' in modelo.get('supportedGenerationMethods', []):
                print(modelo['name'].removeprefix('models/'))
    finally:
        cliente.fechar()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, ErroGemini, TimeoutError) as erro:
        print(f'Falha: {erro}')
        raise SystemExit(1) from None
