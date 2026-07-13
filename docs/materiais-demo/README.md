# Materiais de demonstração — Comunicação escrita no trabalho

Arquivos alinhados ao conteúdo do seed (`backend/app/seed.py`) para uso **manual** em testes e apresentações. Não entram no seed nem no banco automaticamente.

## Trilha — material macro

O upload na trilha aceita **PDF ou PPT/PPTX** (não DOCX).

| Arquivo | Formato | Onde usar |
|---------|---------|-----------|
| `trilha-comunicacao-escrita-trabalho.pptx` | PPTX | Editor da trilha → material da trilha (recomendado) |
| `trilha-comunicacao-escrita-trabalho.pdf` | PDF | Alternativa ao PPTX |

Contém visão do programa, sequência das 6 aulas, competência macro e papel da Lira.

## Aula 1 — Leitura crítica de textos (encerramento pelo professor)

| Arquivo | Onde usar |
|---------|-----------|
| `aula-01-leitura-critica-anexo.docx` | Turma → encerrar aula → anexo opcional (DOCX/TXT) |
| `aula-01-relatorio-professor.txt` | Turma → encerrar aula → texto do relato (cole ou adapte) |

O anexo complementa o conteúdo publicado na aula: slides usados em sala, segundo exemplo e confusões comuns. O relato descreve o que aconteceu na turma (gancho para `summary` / `unclear_points` / `knowledge_base` na ingestão).

## Fluxo sugerido

1. `bin/db-reset` (ou seed force) para turma no dia zero.
2. **Designer/admin:** subir `trilha-comunicacao-escrita-trabalho.pptx` (ou `.pdf`) na trilha e aguardar ingestão.
3. **Professor (Ana Paula — Fundamentos):** encerrar aula 1 com relato + anexo.
4. Aguardar `ingestion_status=done` na nota da aula e convite aos alunos.
5. **Aluno:** conversar no playground ou WhatsApp; conferir painel **Contexto IA**.

## Regenerar os arquivos

```bash
cd backend
.venv/bin/pip install fpdf2   # só para gerar o PDF da trilha
.venv/bin/python ../docs/materiais-demo/generate_materiais.py
```

O PPTX da trilha e o DOCX da aula 1 usam dependências já presentes no backend (`python-pptx`, `python-docx`).
