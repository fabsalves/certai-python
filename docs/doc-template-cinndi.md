Templates de Mensagens

Templates - Visão Geral
Gerencie templates de mensagens para o WhatsApp Business API. Templates são necessários para iniciar conversas com clientes ou enviar mensagens em massa.

Criar
Cadastre novos templates para aprovação do WhatsApp.

Listar
Consulte todos os templates disponíveis e seus status.

Enviar
Envie templates com ou sem variáveis personalizadas.

 Templates de Mensagens
POST
/novo-template/{numero}/{verify_token}
APLICAÇÃO:
WhatsApp
Cadastra um novo template para uso no WhatsApp Cloud. Requer autenticação Bearer.

Parâmetros de Caminho
Nome	Descrição	Tipo	Obrigatório
numero	Número de telefone do bot	string	Sim
verify_token	Token de verificação único por cliente	string	Sim
Variante 1 — Template simples (sem botões)
{
  "nome": "mkt_boas_vindas",
  "idioma": "pt_BR",
  "tipo": "MARKETING",
  "mensagem": "Olá! Seja bem-vindo à nossa loja.\nEstamos à disposição para ajudar.",
  "rodape": "Equipe de atendimento",
  "cabecalho": "Bem-vindo"
}
Variante 2 — Template com botões de resposta rápida
{
  "nome": "mkt_promocao_botoes",
  "idioma": "pt_BR",
  "tipo": "MARKETING",
  "mensagem": "Olá! Confira nossa promoção especial.\nResponda abaixo:",
  "rodape": "Válido por tempo limitado",
  "cabecalho": "Promoção Especial",
  "botoes": [
    "Quero saber mais",
    "Não tenho interesse"
  ]
}
Variante 3 — Template com botão URL estático
{
  "nome": "mkt_visitar_site",
  "idioma": "pt_BR",
  "tipo": "MARKETING",
  "mensagem": "Olá! Acesse nosso site e confira todas as novidades.",
  "rodape": "Disponível 24 horas",
  "botoesURL": {
    "texto": "Visitar Site",
    "url": "https://exemplo.com",
    "dinamico": false
  }
}
Variante 4 — Template com botão URL dinâmico (URL com variável)
{
  "nome": "mkt_acompanhar_pedido",
  "idioma": "pt_BR",
  "tipo": "UTILITY",
  "mensagem": "Olá! Seu pedido foi confirmado.\nClique abaixo para acompanhar.",
  "botoesURL": {
    "texto": "Ver meu pedido",
    "url": "https://loja.com/pedido",
    "dinamico": true
  }
}
No envio do template, o sufixo dinâmico da URL vai no campo `buttons` (string) do `enviar-template`. Use `"dinamico": false` para URL fixa, `true` para sufixo variável por envio.

> **Barra dupla (`//`) — evite no prefixo:** a Meta/Cinndi concatena o sufixo dinâmico como `/{{1}}` após o prefixo. Se `botoesURL.url` terminar com `/`, o template registrado fica `.../pedido//{{1}}` e a URL final quebra rotas como `/voz/:token`. **Prefixo sem barra final:** `https://exemplo.com/voz` → example Meta: `https://exemplo.com/voz/joao123`. O exemplo genérico acima usa `https://loja.com/pedido` (sem `/` no fim) por esse motivo — o doc Cinndi original mostrava barra final e isso causava o quirk em produção (ver `certai_convite_aula_voz` v1 vs v2 em `whatsapp-template-certai_convite_aula.md`).

Variante 5 — Template PIX copia e cola
{
  "nome": "cobranca_pix_simples",
  "idioma": "pt_BR",
  "tipo": "UTILITY",
  "mensagem": "Olá! Segue seu código PIX para pagamento.\nClique no botão abaixo para copiar.",
  "rodape": "Pagamento seguro via PIX",
  "pix": true
}
Não inclua botoes nem botoesURL — o botão "Copiar código PIX" é gerado automaticamente pelo WhatsApp.

Variante 6 — Solicitação de ligação (CALL_PERMISSION)
{
  "nome": "solicitar_ligacao",
  "idioma": "pt_BR",
  "tipo": "CALL_PERMISSION",
  "mensagem": "Olá! Gostaríamos de entrar em contato por ligação.\nAutorize abaixo para podermos ligar."
}
Não inclua botões — o WhatsApp gera automaticamente os botões de Aceitar e Recusar.

Importante: Use apenas botoes OU botoesURL, nunca ambos no mesmo template.

Variante 7 — Template com cabeçalho de imagem
{
  "nome": "mkt_promocao_imagem",
  "idioma": "pt_BR",
  "tipo": "MARKETING",
  "mensagem": "Olá {{1}}, confira nossa promoção especial! \nAproveite {{2}}% de desconto.",
  "rodape": "Promoção válida até amanhã",
  "cabecalhoTipo": "IMAGE",
  "cabecalhoUrl": "https://arquivos-cinndi.nyc3.digitaloceanspaces.com/production/abacaxi-na-praia.jpeg",
  "botoes": [
    "Quero aproveitar",
    "Não tenho interesse"
  ]
}
Variante 8 — Template com cabeçalho de vídeo
{
  "nome": "mkt_video_promocional",
  "idioma": "pt_BR",
  "tipo": "MARKETING",
  "mensagem": "Olá {{1}}, assista nosso vídeo exclusivo! \nNão perca esta oportunidade.",
  "rodape": "Oferta por tempo limitado",
  "cabecalhoTipo": "VIDEO",
  "cabecalhoUrl": "https://arquivos-cinndi.nyc3.cdn.digitaloceanspaces.com/production/video.mp4",
  "botoes": [
    "Tenho interesse",
    "Mais informações"
  ]
}
Variante 9 — Template com cabeçalho de documento (PDF)
{
  "nome": "mkt_pdf_promocional",
  "idioma": "pt_BR",
  "tipo": "MARKETING",
  "mensagem": "Olá {{1}}, segue o material em PDF para sua análise.",
  "rodape": "Documento em anexo",
  "cabecalhoTipo": "DOCUMENT",
  "cabecalhoUrl": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
  "botoes": [
    "Recebi"
  ]
}
Variante 10 — Template de autenticação (OTP / código de verificação)
{
  "name": "auth_codigo_verificacao",
  "language": "pt_BR",
  "category": "AUTHENTICATION",
  "components": [
    {
      "type": "BODY",
      "add_security_recommendation": true
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "OTP",
          "otp_type": "COPY_CODE",
          "text": "Copiar código"
        }
      ]
    }
  ]
}
Template de autenticação usa o formato nativo da Meta API. O campo add_security_recommendation no BODY ativa a recomendação de segurança exibida abaixo do código. O botão OTP com otp_type: COPY_CODE gera o botão "Copiar código" automaticamente. Não é necessário definir o texto do BODY — a Meta gera automaticamente a mensagem no formato "{{1}} é seu código de verificação" quando o template é enviado com o código.

Requisitos de Mídia para Header
Imagem: Formato JPEG ou PNG, tamanho máximo 5MB, resolução recomendada 800x418 pixels.

Vídeo: Formato MP4, tamanho máximo 16MB, duração máxima 60 segundos.

Documento: Formato PDF, tamanho máximo 100MB.

A URL deve ser pública e acessível pela Meta para aprovação do template.

Parâmetros do Corpo
Nome	Descrição	Tipo	Obrigatório
name	Nome do template (apenas letras minúsculas, números e underscore, sem espaços)	string	Sim
language	Código do idioma (ex: pt_BR para Brasil)	string	Sim
category	Categoria do template: MARKETING | UTILITY | AUTHENTICATION	string	Sim
components	Array de componentes do template (HEADER, BODY, FOOTER, BUTTONS). Para AUTHENTICATION: BODY com add_security_recommendation: true + BUTTONS com botão OTP.	array	Sim
components[].type	Tipo do componente: HEADER | BODY | FOOTER | BUTTONS	string	Sim
components[BODY].add_security_recommendation	Se true, exibe recomendação de segurança abaixo do código (apenas AUTHENTICATION). NÃO inclua o campo text no BODY para AUTHENTICATION — a Meta rejeita com erro se text estiver presente neste tipo.	boolean	Não
components[BUTTONS].buttons[].type	Tipo do botão: QUICK_REPLY | URL | PHONE_NUMBER | OTP (apenas AUTHENTICATION)	string	Sim
components[BUTTONS].buttons[].otp_type	Subtipo do botão OTP: COPY_CODE (apenas quando type=OTP)	string	Sim (OTP)
components[BUTTONS].buttons[].text	Texto exibido no botão OTP (ex: "Copiar código")	string	Sim (OTP)
Respostas
200 Template cadastrado com sucesso

{
  "status": "PENDING",
  "id": "772594681476845",
  "category": "MARKETING"
}
POST
/listar-template/{numero}/{verify_token}
APLICAÇÃO:
WhatsApp
Retorna a lista de templates associados ao número fornecido.

Parâmetros de Caminho
Nome	Descrição	Tipo	Obrigatório
numero	Número de telefone do bot	string	Sim
verify_token	Token de verificação único por cliente	string	Sim
Corpo da Requisição
{}
Respostas
200 Lista de templates retornada com sucesso

{
  "status": 200,
  "lista": [
    {
      "id": "2718283405005173",
      "nome": "teste_novo_template_5",
      "status": "APPROVED",
      "idioma": "pt_BR",
      "categoria": "MARKETING",
      "componentes": [
        {
          "type": "BODY",
          "text": "Aqui a mensagem do template"
        }
      ]
    }
  ]
}
POST
/excluir-template/{numero}/{verify_token}
APLICAÇÃO:
WhatsApp
Exclui um template específico. Requer autenticação Bearer.

Parâmetros de Caminho
Nome	Descrição	Tipo	Obrigatório
numero	Número de telefone do bot	string	Sim
verify_token	Token de verificação único por cliente	string	Sim
Corpo da Requisição
{
  "nome": "sample_issue_resolution",
  "apagar": "sim"
}
Parâmetros do Corpo
Nome	Descrição	Tipo	Obrigatório
nome	Nome do template a ser excluído	string	Sim
apagar	Confirmação para apagar (deve ser "sim")	string	Sim
Respostas
200 Template excluído com sucesso

{
  "status": 200,
  "valid": {
    "success": true
  }
}
POST
/enviar-template/{numero}/{verify_token}
APLICAÇÃO:
WhatsApp
Envia uma mensagem template simples ou com variáveis no WhatsApp Cloud. Para envio de template simples envie body como array vazio, header, footer e buttons vazio.

Parâmetros de Caminho
Nome	Descrição	Tipo	Obrigatório
numero	Número de telefone do bot	string	Sim
verify_token	Token de verificação único por cliente	string	Sim
Corpo da Requisição - Com Variáveis
{
  "para": "5512984788194",
  "name": "mkt_bom_dia",
  "code": "pt_BR",
  "header": "",
  "body": [
    "Alexandre",
    "17/01/2024",
    "12:00"
  ],
  "buttons": "valor"
}
Corpo da Requisição - Sem Variáveis
{
  "para": "5512984788194",
  "name": "mkt_bom_dia",
  "code": "pt_BR",
  "header": "",
  "body": [],
  "buttons": ""
}
Corpo da Requisição - Com Header de Imagem
{
  "para": "5512984788194",
  "name": "mkt_promocao_imagem",
  "code": "pt_BR",
  "header": "https://arquivos-cinndi.nyc3.digitaloceanspaces.com/production/abacaxi-na-praia.jpeg",
  "body": [
    "João",
    "20"
  ],
  "buttons": ""
}
Corpo da Requisição - Com Header de Vídeo
{
  "para": "5512984788194",
  "name": "mkt_video_promocional",
  "code": "pt_BR",
  "header": "https://arquivos-cinndi.nyc3.cdn.digitaloceanspaces.com/production/video.mp4",
  "body": [
    "Maria"
  ],
  "buttons": ""
}
Templates com Header de Mídia
Para templates que possuem header de IMAGEM, VÍDEO ou DOCUMENTO, o campo header deve conter a URL pública da mídia.

A URL deve ser acessível publicamente e o tipo de mídia deve corresponder ao tipo definido no template (imagem para IMAGE, vídeo para VIDEO, PDF para DOCUMENT).

Parâmetros do Corpo
Nome	Descrição	Tipo	Obrigatório
para	Número de destino	string	Sim
name	Nome do template	string	Sim
code	Código do idioma (padrão pt_BR)	string	Sim
header	Cabeçalho do template (opcional, pode ser URL de mídia)	string	Não
body	Variáveis do corpo do template. Usar array.	array	Sim
buttons	Valor dos botões (opcional se o tipo botão for DINAMICO APENAS)	string	Não
Respostas
201 Template enviado com sucesso

{
  "status": 201,
  "id": "true_5512984788194@c.us_3EB089EB6669CA98312496"
}
POST
/enviar-template-autenticacao/{numero}/{verify_token}
APLICAÇÃO:
WhatsApp
Envia um template do tipo AUTHENTICATION (OTP / código de verificação) para um número. Passe no campo codigo a chave/código gerado para aquela sessão. O botão "Copiar código" é exibido automaticamente pelo WhatsApp.

Parâmetros de Caminho
Nome	Descrição	Tipo	Obrigatório
numero	Número de telefone do bot	string	Sim
verify_token	Token de verificação único por cliente	string	Sim
Corpo da Requisição
{
  "para": "5512999999999",
  "name": "auth_codigo_verificacao",
  "code": "pt_BR",
  "codigo": "748392"
}
Parâmetros do Corpo
Nome	Descrição	Tipo	Obrigatório
para	Número de destino (com DDI)	string	Sim
name	Nome do template de autenticação criado	string	Sim
code	Código do idioma (padrão pt_BR)	string	Sim
codigo	O código OTP gerado para esta sessão (ex: "748392")	string	Sim
Respostas
201 Template enviado com sucesso

{
  "status": 201,
  "id": "true_5512999999999@c.us_3EB089EB6669CA98312496"
}