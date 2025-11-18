import streamlit as st
import pandas as pd
import os
import tempfile
from dotenv import load_dotenv
import uuid
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, HumanMessage

from agent_rag import (

    build_agent,
    build_llm,
    build_embeddings,
    load_pdf_pages,
    build_vectorstore_from_pages,
    build_retriever
)

USERS = ["Administrador", "Salmaze", "Bernardo", "Rafa4", "Samuel"]

def main():
    load_dotenv()
    ensure_session_state()

    with st.sidebar:
        st.header("Competição de Redação")
        #Usado para simular múltiplos usuários
        st.session_state.selected_user = st.selectbox("Usuários ativos", USERS, index=USERS.index(st.session_state.selected_user))
        st.caption("As mensagens enviadas serão pertencentes ao usuários ativo.")
        
        st.header("Documentos")
        uploaded = st.file_uploader("Upload PDF", type=["pdf"])

        if uploaded is not None:
            if st.button("Enviar", type="primary"):
                with st.spinner("Criando índice... "):
                    st.session_state.retriever = build_or_update_index(uploaded.read(), uploaded.name)
                    st.session_state.agent = build_agent(st.session_state.retriever, st.session_state.llm)
                st.success("Índice criado.")

        st.header("Votação")
        st.selectbox(
            "Temas de Redação",
            st.session_state.themes,
            index=0,
            key="theme_selector"
        )

        if st.button("Votar", disabled=st.session_state.has_voted[st.session_state.selected_user]):
            st.session_state.has_voted[st.session_state.selected_user] = True
            st.session_state.votes[st.session_state.theme_selector] += 1
            st.success("Voto registrado!")

            everyone_voted = all(st.session_state.has_voted.values())
            if everyone_voted:
                
                most_votes = max(st.session_state.votes, key=st.session_state.votes.get)

                if st.session_state.selected_theme is None:

                    st.session_state.selected_theme = most_votes
                    st.session_state.messages.append(
                            {"role": "assistant", "content": f"{st.session_state.selected_theme} foi escolhido como o tema do concurso!"}
                        )
                
                else:

                    st.session_state.messages.append(
                            {"role": "assistant", "content": f"{most_votes} foi o vencedor do concurso! \nSeu texto foi: {st.session_state.user_entry[most_votes]}"}
                        )

            st.rerun()


    st.subheader("Conversa")
    # Carrega e coloca as mensagens anteriores
    for msg in st.session_state.messages:
        author = msg.get("user", "User") if msg["role"] == "user" else "Assistant"
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(f"**{author}**: {msg['content']}")

    if prompt := st.chat_input(f"{st.session_state.selected_user} diz: "):
        # Gera o contexto adicional das mensagens anteriores para servir de "memória" da LLM em relação ao chat

        # Constrói mensagens LangChain
        messages = [
            SystemMessage(content=f"""
            Você é um assistente gentil. Sua principal tarefa é ajudar os usuários com escrita criativa, dado um tema decidido por eles.\n
            Leve em consideração que esta é uma conversa com múltiplas pessoas e lembre-se dos nomes de quem te perguntou.\n
            Se o tema "{st.session_state.selected_theme}" for diferente de vazio, leve-o em conta toda vez que for responder alguma pergunta.\n 
            Só chame as tools bindadas caso o usuário explicitamente mencione uma busca em arquivo indexado ou outra ferramenta.\n
            """
            ),
            # Gera o contexto adicional das mensagens anteriores para servir de "memória" da LLM em relação ao chat
            HumanMessage(content=f"{create_prompt_history(st.session_state.messages)}"),
            # Mensagem do Usuário
            HumanMessage(content=f"{st.session_state.selected_user} disse: {prompt}"),
        ]

        # Adiciona ao histórico local (apenas para UI)
        st.session_state.messages.append({"user": st.session_state.selected_user, "role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(f"**{st.session_state.selected_user}**: {prompt}")

        # Verifica se o usuário digitou um comando válido
        prompt_separated = prompt.split(" ")
        prefix = prompt_separated[0]


        # Comandos para as funções do chat
        if prefix == "@llm":
            llm_response(messages)

        elif prefix == "@entry":
            entry = " ".join(prompt_separated[1:])
            add_entry(entry)  

        if prefix in ["@add","@begin_contest"] :
            if st.session_state.selected_user == USERS[0]:
                if prefix == "@add":
                    theme = " ".join(prompt_separated[1:])
                    add_theme(theme)

                if prefix == "@begin_contest":
                    start_contest()
            else:
                st.session_state.messages.append({"role": "assistant", "content": f"{st.session_state.selected_user} não tem acesso ao comando {prefix}, contate o usuário Administrador."})


        st.rerun()

def llm_response(messages):
    """Função chamada pelos usuários para pedir informações ou conversar com a LLM. Utiliza as últimas mensagens como contexto. O agente também pode recuperar informação 
    de PDF's indexados."""    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = st.session_state.agent.invoke({"messages": messages})

                if not isinstance(result, dict) or "messages" not in result:
                    st.error("Agent returned unexpected result.")
                else:
                    last_msg = result["messages"][-1]
                    content = getattr(last_msg, "content", str(last_msg))
                    st.markdown(content)

                    st.session_state.messages.append({"role": "assistant", "content": content})
            except Exception as e:
                st.error(f"Agent error: {e}")     


def add_theme(theme:str):
    """Função chamada pelo Administrador para adicionar um tema para competição a ser votado."""

    if theme not in st.session_state.themes:
        st.session_state.themes.append(theme)
        st.session_state.votes[theme] = 0

        st.session_state.messages.append(
            {"role": "assistant", "content": f"{theme} foi adicionado como um novo tema!"}
        )

    else:
        st.session_state.messages.append(
            {"role":"assistant", "content": f"{theme} já existe como tema!"}
        )


def add_entry(entry:str):
    """Função chamada pelos usuários para adicionar sua participação à competição."""
    if st.session_state.user_entry[st.session_state.selected_user] is None:
        st.session_state.user_entry[st.session_state.selected_user] = entry
        st.session_state.votes[st.session_state.selected_user] = 0
        st.session_state.themes.append(st.session_state.selected_user)

        st.session_state.messages.append({"role": "assistant", "content": f"{st.session_state.selected_user} está participando da competição!"})
    
    else:
        st.session_state.messages.append({"role": "assistant", "content": f"{st.session_state.selected_user}, você já enviou a sua entry."})


def start_contest():
    """Função chamada pelo Administrador para começar uma competição."""
    if st.session_state.selected_theme is not None:

        st.session_state.has_voted = {user: False for user in USERS}
        st.session_state.votes = {}
        st.session_state.themes = []

        st.session_state.messages.append({"role": "assistant", "content": f"Um novo concurso foi iniciado com o tema {st.session_state.selected_theme}."})

        messages = [
                    SystemMessage(content=f"""
                    Você é um assistente gentil. Sua principal tarefa é ajudar os usuários com redação, dado um tema decidido por eles.\n
                    Leve em consideração que esta é uma conversa com múltiplas pessoas e lembre-se dos nomes de quem te perguntou.\n
                    Se o tema "{st.session_state.selected_theme}" for diferente de vazio, leve-o em conta toda vez que for responder alguma pergunta.\n 
                    Só chame as tools bindadas caso o usuário explicitamente mencione uma busca em arquivo indexado ou outra ferramenta.\n
                    Envie apenas o que for necessário, vá direto ao ponto.
                    """
                    ),  # opcional mas recomendado
                    HumanMessage(content=f"{create_prompt_history(st.session_state.messages)}"),
                    HumanMessage(content=f"Crie 5 prompts para concursos de redação usando o tema {st.session_state.selected_theme}!"),
                ]

        llm_response(messages)

    else:
        st.session_state.messages.append({"role": "assistant", "content": "Nenhum tema foi definido."})

def ensure_session_state():
    """Inicializa todas as variáveis de estado da sessão"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = [] 
    if "retriever" not in st.session_state:
        st.session_state.retriever = None
    if "llm" not in st.session_state:
        st.session_state.llm = build_llm()
    if "agent" not in st.session_state:
        st.session_state.agent = build_agent(st.session_state.retriever, st.session_state.llm)
    if "selected_user" not in st.session_state:
        st.session_state.selected_user = USERS[0]
    if "themes" not in st.session_state:
        st.session_state.themes = []
    if "selected_theme" not in st.session_state:
        st.session_state.selected_theme = None
    if "has_voted" not in st.session_state:
        st.session_state.has_voted = {user: False for user in USERS}
    if "votes" not in st.session_state:
        st.session_state.votes = {theme: 0 for theme in st.session_state.themes}
    if "user_entry" not in st.session_state:
        st.session_state.user_entry = {user: None for user in USERS} 


def create_prompt_history(messages, length_detailed_history: int = 10):
    """ Retorna um texto contendo as últimas 'lenght_detailed_history' mensagens anteriores do chat, utilizado para o contexto da LLM"""
    n = length_detailed_history
    extended_prompt = []

    for message in messages[-n:]:
        if message["role"] == "user":
            extended_prompt.append(f"{message.get("user")} disse: '{message.get("content")}'")
        else:
            extended_prompt.append(f"Assistente disse: '{message.get("content")}'")

    extended_prompt = "\n".join(extended_prompt)    

    return extended_prompt

def build_or_update_index(uploaded_pdf_bytes: bytes, filename: str = "temp.pdf"):
    """Constrói ou atualiza o índice de busca para o retriever"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        tmp.write(uploaded_pdf_bytes)
        tmp_path = tmp.name

    embeddings = build_embeddings()
    pages = load_pdf_pages(tmp_path)
    vectorstore = build_vectorstore_from_pages(
        pages,
        embeddings,
        persist_directory=get_shared_vectorstore_dir(),
        collection_name="book",
    )
    retriever = build_retriever(vectorstore)
    os.unlink(tmp_path)
    return retriever

def get_shared_vectorstore_dir() -> str:
    """Retorna o path do diretório do vectorstore"""

    base = os.environ.get("RAG_VDB_DIR", "./vdb")
    if not os.path.exists(base):
        os.makedirs(base)
    return base

if __name__ == "__main__":
    main()