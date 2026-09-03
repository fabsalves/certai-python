# Dinamismo de aulas — regras e operação

Para quem vai testar. Sem código.

---

## O que mudou, em uma frase

Antes o sistema assumia que a aula saiu como planejado. Agora **cada encerramento declara o que
foi realmente dado**, e é isso que a Lira conversa e que a avaliação cobra do aluno.

---

## As regras novas

**1 · Planejado e ministrado são coisas diferentes.**
O conteúdo cadastrado na aula continua sendo o plano. O que o professor deu é o que vale. Quando
os dois divergem, o ministrado manda.

**2 · Aula incompleta deixa pendência.**
O que não foi dado fica registrado como pendente. A Lira não pergunta, não cobra e não ensina esse
conteúdo. A avaliação não rebaixa o aluno por ele — não é lacuna do aluno, é desvio de operação.

**3 · Aula adiantada é absorvida.**
Se o professor avançou no conteúdo da aula seguinte, isso é registrado naquela aula. A aula seguinte
**não é liberada** por isso e nenhum convite novo sai. Quando ela for encerrada de verdade, o
sistema já sabe que parte foi dada.

**4 · Aula composta é entendida em blocos.**
Fechar a pendência da aula anterior e avançar no conteúdo do dia é uma sessão só, com dois blocos
identificados. A pendência da anterior desaparece, e o aluno conversa uma vez, cobrindo os dois.

**5 · A turma continua avançando.**
Aula incompleta não trava a turma. Ela avança, e a pendência fica marcada para ser fechada depois.

**6 · Adiantar para o módulo seguinte depende de quem dá aquela aula.**
Mesmo professor nos dois módulos: registra normal. Professor diferente: **não registra**, e a tela
avisa qual aula é e de quem, para os dois combinarem. O professor sempre fica sabendo.

**7 · Pendência não expira.**
Se a turma andou duas ou três aulas, a pendência antiga continua fechável.

---

## O que o professor faz

Nada de novo. Ele relata a aula como sempre — gravando ou escrevendo.

Cerca de um segundo depois, aparece um card **Cobertura desta aula** com o que a IA entendeu do
relato: quais aulas foram tocadas, o que foi dado e o que ficou pendente. Ele **confirma** ou clica
em **Ajustar** para corrigir.

Depois encerra normalmente.

Se a IA não conseguir ler o relato, aparece um aviso discreto e a cobertura fica como "aula do dia,
completa". **O encerramento nunca fica bloqueado.**

---

## O que o admin faz

**Vê a pendência.** Na aba Andamento, a aula mostra o conteúdo que ficou pendente. É o dado de
operação que antes se perdia.

**Tem turma de teste.** Ao criar uma turma, pode marcá-la como turma de teste. Nela, e só nela,
aparecem dois botões no fim do Andamento:

| Botão | O que faz |
|---|---|
| **Desfazer último encerramento** | Reabre a última aula encerrada. Clicando de novo, volta mais uma. |
| **Zerar andamento** | Volta a turma ao início. |

Nos dois casos, **alunos, professores e custos continuam como estão**. Só o andamento volta.

**A marca de turma de teste é definida na criação e não pode ser alterada depois.** Uma turma normal
nunca poderá ser zerada — não existe caminho para isso.

⚠️ **Nunca matricule aluno real numa turma de teste.** Ele receberia mensagem de teste no WhatsApp.

---

## O que o aluno vê

Nada diferente. O que muda é o que a Lira sabe: ela conversa sobre o que ele **recebeu**, incluindo
a cauda da aula anterior ou o que foi adiantado, e trata o pendente como conteúdo futuro.

---

## O que não mudou

- A ordem das aulas. O professor continua encerrando só a aula atual da turma dele.
- O convite ao aluno, que continua saindo uma vez por aula encerrada.
- A avaliação continua qualitativa, sem nota numérica.
- **Aula que saiu como planejado se comporta exatamente como antes.** Sem desvio, nada de novo
  entra em jogo.

---

## Parece bug e não é

**A avaliação da aula aparece sem o aluno ter conversado.** Quando a turma avança, a aula anterior
é fechada e avaliada. Sem conversa, o resultado é "sem evidência" — nunca uma nota inventada, e
nunca uma nota baixa por isso.

**Mensagem de WhatsApp já enviada não volta ao rebobinar.** O sistema apaga a conversa, não o que
já chegou no celular. O convite velho fica no histórico.

**A trilha mostra o título de aulas que o aluno ainda não viu.** Isso é de propósito: permite a Lira
dizer "isso você vê na aula 4" sem ensinar. O conteúdo daquela aula não entra.

**Sem relato não aparece proposta de cobertura.** Ela só é sugerida quando há texto.

**Um conteúdo confirmado pode não ser registrado.** Se o professor do módulo foi trocado entre a
proposta e o encerramento, a aula encerra e um aviso diz qual conteúdo não entrou. Nada se perde
calado.

---

## O que reportar como bug

- A Lira perguntar, cobrar ou **ensinar** conteúdo marcado como pendente.
- A avaliação rebaixar o aluno por conteúdo que ele não recebeu.
- Uma pendência que não desaparece depois de o professor fechá-la numa aula seguinte.
- Uma aula ser liberada só porque o professor adiantou parte dela.
- O card de cobertura não aparecer depois de escrever o relato.
- Qualquer conteúdo de aula futura aparecendo na conversa com o aluno.
