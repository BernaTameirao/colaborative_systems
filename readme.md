# Trabalho de  SSC0723 - Sistemas Colaborativos: Fundamentos e Aplicações
--- --
## Alunos:
* Bernardo Rodrigues Tameirão Santos - 12733212
* Lourenço de Salles Roselino - 11796805
* Samuel Figueiredo Veronez - 12542626
--- ---
## Descrição do Cenário Colaborativo

O cenário para o qual o sistema foi desenvolvido foi o de colaboração 
no contexto de escrita criativa. A aplicação consiste em um chat, no qual os usuários
podem descutir decisões para um texto/projeto e podem acionar a llm 
para acessar informações prévias da conversa e recuperar informações de fontes carregadas 
na plataforma.

## Diagrama do Grafo

## Abordagem 3C

1. **Comunicação**:
   * O sistema possibilita a troca de mensagens entre diversos usuários em tempo real e permite que uma LLM seja acionada para
auxiliar a dar ideias, consultar documentos, recapitular e opinar sobre mensagens prévias.

2. **Colaboração**:
   * A colaboração é facilitada através do chat, que permite que os usuários compartilhem e 
contribuam entre sí na ideia desenvolvida,, sendo que a LLM implementada serve de suporte seja 
com novas ideias, seja compilando informações anteriores para facilitar os usuários.
   
3. **Coordenação**:
   * O usuários Administrador pode decidir temas para serem votados pelos membros, que serve para delimitar o 
    contexto do projeto
   * A LLM ajuda a coordenar o contexto das interações, escopo e facilita a cooperação entre os membros.

## Limitações

Devido ao número de tokens diários disponibilizados pelo groq, adicionamos algumas restrições no funcionamento da aplicação,
a exemplo do tamanho do histórico de mensagens enviadas como contexto para a LLM, número máximo de resultados na busca por
embeddings.