"""Verificação e recuperação do instalador sem abrir o servidor."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
import main


class RecuperacaoPip(unittest.TestCase):
    def test_pip_existente_nao_e_reinstalado(self):
        """Preserve o pip que já funciona."""
        with patch.object(main, 'verificar_pip'), patch.object(main, 'executar') as executar:
            main.garantir_pip(Path('python'))
            executar.assert_not_called()

    def test_pip_ausente_e_recuperado_e_conferido(self):
        """Execute ensurepip e confirme a recuperação."""
        falha = subprocess.CalledProcessError(1, ['pip'])
        with patch.object(main, 'verificar_pip', side_effect=[falha, None]) as conferir:
            with patch.object(main, 'executar') as executar:
                main.garantir_pip(Path('python'))
                executar.assert_called_once_with(Path('python'), ['-I', '-m', 'ensurepip', '--upgrade', '--default-pip'])
                self.assertEqual(conferir.call_count, 2)

    def test_recuperacao_falha_nao_prossegue(self):
        """Informe a falha sem esconder que o instalador continua indisponível."""
        falha = subprocess.CalledProcessError(1, ['pip'])
        with patch.object(main, 'verificar_pip', side_effect=falha):
            with patch.object(main, 'executar', side_effect=falha):
                with self.assertRaisesRegex(ValueError, 'Repare o Python'):
                    main.garantir_pip(Path('python'))
