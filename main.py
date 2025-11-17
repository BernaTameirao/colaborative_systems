import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import uuid
import tempfile

from typing import Annotated, Sequence, TypedDict, Callable, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, HumanMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langgraph.graph import StateGraph, END
from operator import add as add_messages

USERS = ["Salmaze", "Bernardo", "Rafa4", "Samuel"]

def main():
    load_dotenv()
    ensure_session_state()
    llm = build_llm()

    with st.sidebar:
        st.header("User")
        st.session_state.selected_user = st.selectbox("Active user", USERS, index=USERS.index(st.session_state.selected_user))
        st.caption("Messages sent will be attributed to this user.")
        
        st.header("Data")
        uploaded = st.file_uploader("Upload PDF", type=["pdf"])

        if uploaded is not None:
            if st.button("Build/Update Index", type="primary"):
                with st.spinner("Creating index... "):
                    #a
                    pass
                st.success("Index created.")


    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
        
    prompt = st.chat_input("Say something")
    
    if prompt:
        prompt_extended = create_prompt_history(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": prompt})

        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=prompt_extended),
            HumanMessage(content=prompt), 
        ]

        with st.chat_message("user"):
            st.write(prompt)

        response = call_llm(llm, messages)
        st.session_state.messages.append({"role": "assistant", "content": response.content})

        with st.chat_message("assistant"):
            st.write(response.content)

    
def build_llm(model: str = "llama-3.3-70b-versatile", temperature: float = 0):
    llm = ChatGroq(
        model=model,
        temperature=temperature,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )
    return llm

def build_embeddings(model: str = "text-embedding-3-small"):
    embeddings = HuggingFaceInferenceAPIEmbeddings(
        api_key=os.getenv("HF_TOKEN"),
        model_name="sentence-transformers/all-mpnet-base-v2")
    return embeddings


def build_vectorstore_from_pages(pages, embeddings, persist_directory: str = "./vdb", collection_name: str = "book"):
    if not os.path.exists(persist_directory):
        os.makedirs(persist_directory)

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(pages)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory,
        collection_name=collection_name,
    )
    return vectorstore


def load_pdf_pages(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    return pages


def call_llm(llm, messages):
    return llm.invoke(messages)


def build_retriever(vectorstore, k: int = 7):
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k})


def build_or_update_index(uploaded_pdf_bytes: bytes, filename: str):
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
    base = os.environ.get("RAG_VDB_DIR", "./vdb")
    if not os.path.exists(base):
        os.makedirs(base)
    return base

def ensure_session_state():
    """Initialize all session variables"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []  # list of {role: "user"|"assistant"|"system", content: str}
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "retriever" not in st.session_state:
        st.session_state.retriever = None
    if "selected_user" not in st.session_state:
        st.session_state.selected_user = USERS[0]


def create_prompt_history(messages, length_detailed_history: int = 10):
    n = length_detailed_history
    extended_prompt = []

    for message in messages[-n:]:
        if message["role"] == "user":
            extended_prompt.append(f"The user said: '{message["content"]}'")
        else:
            extended_prompt.append(f"You said: '{message["content"]}'")

    extended_prompt = "\n".join(extended_prompt)    

    return extended_prompt


if __name__ == "__main__":
    main()

def build_agent(retriever, llm):
    
    @tool
    def retriever_tool(query:str) -> str:
        """Search and return relevant chunks from the loaded PDFs"""
        docs = retriever.invoke(query)
        if not docs:
            return "No relevant info was found in the document"
        
        results = []
        for i, doc in enumerate(docs):
            results.append(f"Document {i+1}:\n{doc.page_content}")
        return "\n\n".join(results)

    tools = [retriever_tool]
    llm_with_tools = llm.bind_tools(tools)

    class AgentState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]

    system_prompt = (
    )

    tools_dict = {t.name: t for t in tools}

    def call_llm(state: AgentState) -> AgentState:
        msgs = list(state["messages"])
        msgs = [SystemMessage(content=system_prompt)] + msgs
        message = llm_with_tools.invoke(msgs)
        return {"messages": [message]}

    def take_action(state: AgentState) -> AgentState:
        tool_calls = state["messages"][-1].tool_calls
        results = []
        for t in tool_calls:
            tool_name = t["name"]
            args_query = t["args"].get("query", "")
            if tool_name not in tools_dict:
                result = "Incorrect tool name; select an available tool and try again."
            else:
                result = tools_dict[tool_name].invoke(args_query)
            results.append(ToolMessage(tool_call_id=t["id"], name=tool_name, content=str(result)))
        return {"messages": results}

    #TODO add summarizer
    #TODO add summarizer

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("retriever", take_action)
    graph.add_edge("retriever", "llm")
    graph.set_entry_point("llm")
    return graph.compile()