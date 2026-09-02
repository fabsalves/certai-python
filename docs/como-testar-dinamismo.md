# Como testar: dinamismo de aulas + turma de teste

O que validar, em que ordem, e onde olhar. Cobre os dois pacotes:

- **Dinamismo de aulas** — a sessão declara o que foi realmente ministrado.
- **Turma de teste** — o andamento pode ser rebobinado, para repetir o ciclo.

---

## Parte 1 — Bateria automatizada (2 comandos)

Precisa de Postgres e Redis de pé. Redis é obrigatório: o encerramento enfileira a ingestão no
commit, e sem broker o commit estoura.

```bash
bin/db-reset && bin/verify-dinamismo
```

**26/26.** Roda os três cenários do doc de produto mais o caminho feliz, e imprime o que ficou
registrado em cada um. Com `--with-ai` sobem para 29/29 e a IA lê um relato de verdade (consome
`OPENAI_API_KEY`).

> Precisa de `bin/db-reset` antes: o script encerra aulas de verdade, então rodar duas vezes
> seguidas falha porque as aulas já estão fechadas. Não é instabilidade — é o script operando no
> fluxo real.

```bash
bin/db-reset && bin/verify-sandbox
```

**22/22.** Verifica que turma real recusa as duas ações, que o desfazer restaura o estado
anterior, que a pendência volta sozinha, e que zerar preserva cadastro e custos.

> Este **não** precisa de reset entre execuções: ele cria a própria turma de teste e a remove no
> fim. Pode rodar em sequência.

Falha em qualquer um → sai com código 1 e o resumo final em vermelho.

---

## Parte 2 — Preparar a turma de teste (uma vez)

```bash
bin/dev
```

O worker precisa estar de pé: o convite ao aluno só sai **depois** da ingestão do relato.

1. Entre como admin (`admin@certai.app` / `admin12345`).
2. **Turmas → Nova turma.** Nome à escolha, mesma trilha, e marque **Turma de teste**.
   - A marca só aparece na criação. Depois vira um selo somente leitura — de propósito: uma
     turma normal nunca poderá ser zerada.
3. Defina o professor de cada módulo (pode usar os mesmos do seed).
4. **Alunos →** matricule quem vai testar. Em produção, com o WhatsApp real de cada um.

> **Nunca matricule aluno real numa turma de teste.** Ele receberia mensagem de teste.

A partir daqui, todo cenário é repetível: rode, observe, rebobine, repita.

---

## Parte 3 — Os quatro cenários

Cada aula pertence a um módulo, e um módulo tem um professor. Os cenários rodam **dentro de um
módulo** — é como o professor real vive. No seed: aulas 1–3 são de um professor, 4–6 de outro.

Duas formas de encerrar aula:

| Caminho | Como | Quando usar |
|---|---|---|
| **Realista** | Professor entra e encerra em Turmas → Andamento | Validar o que o professor real vê |
| **Rápido** | Admin encerra pelo `/admin/playground` como o professor | Iterar sem trocar de login |

O rebobinar é sempre **admin**, na aba Andamento.

### 1 · Caminho feliz — confirmar que nada mudou

Relato: *"Fechei todo o conteúdo previsto da aula."*

Espere ~1s depois de parar de digitar. O card **Cobertura desta aula** deve dizer *"A aula seguiu
o conteúdo planejado"*. Encerre.

**Esperado:** comportamento idêntico ao de antes do pacote. É o ponto — sem desvio, nada de novo
entra em jogo.

### 2 · Aula incompleta

Relato: *"Hoje só deu tempo do bloco de contexto. Não fechei a análise nem a recomendação."*

**Esperado:**
- a IA propõe **parcial**, com o pendente separado;
- **Ajustar** abre a edição; mexer em qualquer campo marca o segmento como ajustado pelo professor;
- depois de encerrar, volte na aula em Andamento: aparece **"Conteúdo desta aula que ficou
  pendente"** com o texto do que faltou.

### 3 · Aula composta

Relato: *"Comecei fechando a análise e a recomendação que faltaram da aula anterior, e depois
avancei no conteúdo do dia."*

**Esperado:**
- a IA devolve **dois segmentos**: um da aula anterior (fechando a pendência) e um da aula do dia;
- depois de encerrar, a pendência da aula anterior **desapareceu** — resolvida sem UPDATE, por
  uma linha nova de cobertura.

### 4 · Aula adiantada

Troque para o professor do módulo seguinte. Relato: *"A turma rendeu, fechei tudo e ainda adiantei
o conceito da próxima aula."*

**Esperado:**
- a IA propõe um segmento na aula seguinte;
- a aula seguinte **não foi liberada** — nenhum convite novo saiu. O excedente ficou guardado no
  lugar certo, para quando aquela aula for encerrada.

---

## Parte 4 — Rebobinar

Na aba **Andamento** da turma de teste, como admin, ao final da página:

| Botão | Efeito |
|---|---|
| **Desfazer último encerramento** | Reabre a última aula encerrada. Clicando em sequência, caminha para trás. |
| **Zerar andamento** | Volta a turma ao início. |

O que sempre sobrevive: a turma, matrículas, professores, a divisão de alunos, a trilha, e os
custos de IA.

**O caso que isso resolve:** o testador achou um bug no cenário 3. Você corrige e sobe. Ele clica
em **Desfazer último encerramento** e refaz só aquele passo — sem replay do fluxo inteiro.

Se o desfazer não der conta, **Zerar andamento** e começar do zero.

---

## Parte 5 — Onde olhar cada peça

| O que | Onde |
|---|---|
| Proposta da IA, confirmar/ajustar | Formulário de encerramento, entre o relato e o anexo |
| Pendência como dado de operação | Andamento, na aula selecionada |
| Escopo ministrado no contexto da Lira | `/admin/playground` → turma/aluno → **"Escopo realmente ministrado"** |
| Bloco literal enviado ao modelo | Mesmo painel → **"Bloco enviado ao modelo"** (colapsado) |
| Custo da chamada nova | `/costs` → operação **"Cobertura da aula"** |
| Conversa com a Lira (local, sem WhatsApp) | `/admin/playground` → chat como o aluno |

O playground é o ponto mais informativo: mostra o escopo ministrado e o conteúdo planejado lado a
lado, e permite conversar como a Lira em seguida para checar que ela **não cobra o pendente**.

Localmente, sem celular: `./bin/send-message 'texto'` simula inbound de WhatsApp — mas exige que a
aula já tenha sido encerrada (é o que cria a conversa).

---

## O que é limitação, não bug

1. **A mensagem de WhatsApp já enviada não volta.** Rebobinar apaga a conversa no banco, mas não
   desenvia o template do celular. O convite velho fica no histórico.
2. **Rebobinar durante a ingestão** faz a task procurar um relato apagado e falhar no log do
   worker. Nenhum efeito é aplicado — é ruído.
3. **Sem relato não há proposta.** A cobertura só é sugerida quando há texto (digitado ou
   transcrito de áudio).
4. **Se a chamada de IA falhar**, aparece um aviso discreto e a cobertura cai no padrão
   "aula do dia, completa". O encerramento nunca fica bloqueado por isso.
5. **Adiantar para dentro do módulo de outro professor não é registrável.** Isso não é desvio de
   uma turma, é mudança de plano entre dois professores.

## Logins do seed

| Papel | E-mail | Senha |
|---|---|---|
| Admin | `admin@certai.app` | `admin12345` |
| Professor (aulas 1–3) | `prof@certai.app` | `prof12345` |
| Professor (aulas 4–6) | `marcos.ferreira@certai.app` | `prof12345` |
| Aluno | `aluno@certai.app` | `aluno12345` |
