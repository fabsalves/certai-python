# Dinamismo de aulas — regras e operação

Para quem vai testar. Sem código.

---

## O que mudou, em uma frase

Antes o sistema assumia que a aula saiu como planejado. Agora **cada encerramento declara o que
foi realmente dado**, e é isso que a Lira conversa e que a avaliação cobra do aluno.

---

## As regras

**1 · Planejado e ministrado são coisas diferentes.**
O conteúdo cadastrado na aula continua sendo o plano. O que o professor deu é o que vale. Quando os
dois divergem, o ministrado manda.

**2 · Aula incompleta deixa pendência.**
O que não foi dado fica registrado como pendente. A Lira não pergunta, não cobra e não ensina esse
conteúdo. A avaliação não rebaixa o aluno por ele: não é lacuna do aluno, é desvio de operação.

**3 · Aula adiantada é absorvida.**
Se o professor avançou no conteúdo da aula seguinte, isso fica registrado naquela aula. A aula
seguinte **não é liberada** por isso e nenhum convite novo sai. Quando ela for encerrada de verdade,
o sistema já sabe que parte foi dada.

**4 · Aula composta é entendida em blocos.**
Fechar a pendência da aula anterior e avançar no conteúdo do dia é uma sessão só, com os dois blocos
identificados. A pendência da anterior desaparece, e o aluno conversa uma vez, cobrindo os dois.

**5 · A turma continua avançando.**
Aula incompleta não trava a turma. Ela avança, e a pendência fica marcada para ser fechada depois.

**6 · Pendência não expira.**
Se a turma andou duas ou três aulas, a pendência antiga continua podendo ser fechada.

**7 · Avançar para o módulo seguinte depende de quem dá aquela aula.**
Mesmo professor nos dois módulos: registra normal. Professor diferente: **não registra**, e a tela
avisa qual aula é e de quem, para os dois combinarem.

**8 · Aula que saiu como planejado se comporta exatamente como antes.**
Sem desvio, nada de novo entra em jogo.

---

## O professor

Relata a aula como sempre, gravando ou escrevendo em **Relato da aula**.

Cerca de um segundo depois aparece o quadro **Cobertura desta aula**, com o que a IA entendeu do
relato. Cada aula tocada aparece com uma etiqueta:

| Etiqueta | Significa |
|---|---|
| **Aula do dia** | o conteúdo da própria aula sendo encerrada |
| **Pendência da aula anterior** | o que faltou da anterior e foi fechado agora |
| **Adiantado da aula seguinte** | conteúdo da próxima aula, dado antes |

Ao lado de cada uma: **coberta por completo** ou **coberta em parte**, com o texto do que foi dado e,
quando parcial, o que ficou pendente.

O professor **confirma** ou clica em **Ajustar**, onde pode trocar entre completa e em parte, editar
**O que foi dado** e **O que ficou pendente**, e usar **Incluir aula tocada nesta sessão** se a IA
não pegou alguma. Depois é **Encerrar aula e avançar turma**, como sempre.

Se a IA não conseguir ler o relato, aparece um aviso e a cobertura fica como aula do dia coberta por
completo. **O encerramento nunca fica bloqueado.**

---

## O admin

**Vê a pendência.** Na aba **Andamento**, a aula selecionada mostra **Conteúdo desta aula que ficou
pendente**, com o texto do que faltou.

**Tem turma de teste.** Ao criar uma turma, pode marcá-la como **Turma de teste**. Nela, e só nela,
aparecem dois botões no fim do Andamento:

| Botão | O que faz |
|---|---|
| **Desfazer último encerramento** | Reabre a última aula encerrada. Clicando de novo, volta mais uma. |
| **Zerar andamento** | Volta a turma ao início. |

Nos dois casos os alunos, os professores e os custos de IA continuam como estão. Só o andamento
volta atrás.

A marca de **Turma de teste** é definida na criação e não pode ser alterada depois. Uma turma normal
nunca poderá ser zerada.

⚠️ **Nunca matricule aluno real numa turma de teste.** Ele receberia mensagem de teste no WhatsApp.

---

## O aluno

Nada muda na tela dele. Muda o que a Lira sabe: ela conversa sobre o que ele **recebeu**, incluindo
o que veio da aula anterior ou foi dado adiantado, e trata o pendente como conteúdo que ele ainda
vai ver.

---

## O que não mudou

- A ordem das aulas. O professor continua encerrando só a aula atual da turma dele.
- O convite ao aluno, que continua saindo uma vez por aula encerrada.
- A avaliação continua qualitativa, sem nota numérica.
