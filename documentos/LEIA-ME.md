# Documentos públicos do acervo

Coloque aqui os documentos que o consultor deve conhecer: **PDF, DOCX, TXT ou XLSX** (até 25 MB cada).

- **Demonstração (sem Gemini):** tudo o que estiver nesta pasta é indexado automaticamente a cada início do servidor.
- **Modo oficial (MySQL + Gemini):** nada é indexado sozinho. Publique pelo painel de administração ou rode, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe indexar_pdfs.py documentos
```

Só publique documentos públicos e revisados: nada de CPF, RA, telefone, e-mail ou outros dados pessoais (o sistema recusa os padrões mais comuns, mas não detecta tudo).

Documentos atuais:

- `Calendário Acadêmico 2026 completo.pdf` — calendário mensal; cada evento vira uma frase com dia, mês, ano e dia da semana.
- `Horario Curso Inteligência Artificial.xlsx` — horário do curso por semestre; cada aula vira uma frase com dia, horário, disciplina e professor.

Este arquivo é `.md` de propósito: formatos `.txt` desta pasta seriam indexados como documento.
