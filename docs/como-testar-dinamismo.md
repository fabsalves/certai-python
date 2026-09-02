# Como testar: dinamismo de aulas + turma de teste

**O que mudou:** a aula real desvia do plano — fica incompleta, avança na seguinte, ou fecha a
cauda da anterior. Agora cada encerramento declara o que foi **realmente ministrado**, e é isso
que a Lira explora e que a avaliação cobra. Turma marcada como **teste** pode ser rebobinada, para
repetir o ciclo quantas vezes precisar.

---

## 1. Bateria automatizada

Precisa de Postgres e Redis de pé (Redis é obrigatório: o encerramento enfileira a ingestão no
commit).

```bash
bin/db-reset && bin/verify-dinamismo
```
**28/28** — os três cenários do doc de produto + caminho feliz. Com `--with-ai`: 31/31, e a IA lê
um relato de verdade.

```bash
bin/db-reset && bin/verify-sandbox
```
**24/24** — guardas, desfazer, pendência voltando, zerar preservando cadastro.

Falha em qualquer um → exit 1 e resumo em vermelho.

> `verify-dinamismo` **exige** o `db-reset` antes: ele encerra aulas de verdade, então duas
> rodadas seguidas falham porque as aulas já estão fechadas. Não é instabilidade.
> `verify-sandbox` **não** precisa — cria e remove as próprias turmas.

---

## 2. Preparar (uma vez)

```bash
bin/dev
```
O worker precisa estar de pé: o convite ao aluno só sai **depois** da ingestão do relato.

Como admin (`admin@certai.app` / `admin12345`):

1. **Turmas → Nova turma** — marque **Turma de teste**. A marca só existe na criação; depois vira
   selo somente leitura, de propósito: turma normal nunca poderá ser zerada.
2. Defina o professor de cada módulo.
3. **Alunos** → matricule quem vai testar (em produção, com o WhatsApp real de cada um).

> **Nunca matricule aluno real numa turma de teste** — ele receberia mensagem de teste.

---

## 3. Os quatro cenários

Cada aula pertence a um módulo, e um módulo tem um professor. Os cenários rodam **dentro de um
módulo**. No seed: aulas 1–3 são de um professor, 4–6 de outro.

Encerrar aula: **Turmas → Andamento**, como o professor. Ou, sem trocar de login, como admin em
`/admin/playground`. Rebobinar é sempre **admin**, na aba Andamento.

Digite o relato e espere ~1s. O card **Cobertura desta aula** aparece com a proposta da IA.

| # | Relato para digitar | Esperado |
|---|---|---|
| 1 | *"Fechei todo o conteúdo previsto da aula."* | Card diz **"seguiu o conteúdo planejado"**. Comportamento igual ao de antes do pacote. |
| 2 | *"Hoje só deu tempo do bloco de contexto. Não fechei a análise nem a recomendação."* | Proposta **parcial**, com o pendente separado. Depois de encerrar, a aula em Andamento mostra **"Conteúdo desta aula que ficou pendente"**. |
| 3 | *"Comecei fechando a análise e a recomendação que faltaram da aula anterior, e depois avancei no conteúdo do dia."* | **Dois segmentos**: um da aula anterior, um da aula do dia. A pendência da anterior **desaparece**. |
| 4 | *"A turma rendeu, fechei tudo e ainda adiantei o conceito da próxima aula."* (professor do módulo seguinte) | Segmento na aula seguinte, mas ela **não é liberada** — nenhum convite novo. |

**Ajustar** abre a edição dos segmentos, para o caso de a IA não pegar o cenário.

---

## 4. Rebobinar

Aba **Andamento** da turma de teste, como admin, ao final da página:

| Botão | Efeito |
|---|---|
| **Desfazer último encerramento** | Reabre a última aula. Clicando em sequência, caminha para trás. |
| **Zerar andamento** | Volta a turma ao início. |

Sempre sobrevive: turma, matrículas, professores, divisão de alunos, trilha e custos de IA.

**O caso real:** o testador achou bug no cenário 3, você corrige e sobe, ele clica em **Desfazer
último encerramento** e refaz só aquele passo — sem replay do fluxo.

---

## 5. Onde olhar

| O que | Onde |
|---|---|
| Proposta da IA / ajustar | Formulário de encerramento, entre o relato e o anexo |
| Pendência | Andamento, na aula selecionada |
| Escopo ministrado no contexto da Lira | `/admin/playground` → **"Escopo realmente ministrado"** |
| Bloco literal enviado ao modelo | Mesmo painel → **"Bloco enviado ao modelo"** |
| Custo da chamada nova | `/costs` → **"Cobertura da aula"** |
| Conversar como a Lira (sem WhatsApp) | `/admin/playground` → chat como o aluno |

O playground é o mais informativo: mostra ministrado e planejado lado a lado, e deixa conversar em
seguida para confirmar que a Lira **não cobra o pendente**.

---

## 6. Limitação, não bug

1. **Mensagem de WhatsApp já enviada não volta.** Rebobinar apaga a conversa no banco, não o que
   já chegou no celular. O convite velho fica no histórico.
2. **Rebobinar durante a ingestão** faz a task procurar um relato apagado e falhar no log do
   worker. Nenhum efeito é aplicado.
3. **Sem relato não há proposta** — a cobertura só é sugerida quando há texto.
4. **Se a IA falhar**, aviso discreto e a cobertura cai em "aula do dia, completa". O
   encerramento nunca fica bloqueado.
5. **Adiantar para dentro do módulo de outro professor não é registrável** — isso não é desvio de
   uma turma, é mudança de plano entre dois professores.

## Logins do seed

| Papel | E-mail | Senha |
|---|---|---|
| Admin | `admin@certai.app` | `admin12345` |
| Professor (aulas 1–3) | `prof@certai.app` | `prof12345` |
| Professor (aulas 4–6) | `marcos.ferreira@certai.app` | `prof12345` |
