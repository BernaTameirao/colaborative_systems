import streamlit as st
import os
from dotenv import load_dotenv
import uuid
import tempfile

from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, HumanMessage

from agent_rag import(
    build_embeddings,
    load_pdf_pages,
    build_vectorstore_from_pages,
    build_retriever,
    get_agent,

)

USERS = ["Salmaze", "Bernardo", "Rafa4", "Samuel"]

def main():
    load_dotenv()
    ensure_session_state()
    agent = get_agent()

    with (st.sidebar):
        st.header("User")
        st.session_state.selected_user = st.selectbox(
            "Active user",
            USERS,
            index=USERS.index(st.session_state.selected_user))

        st.caption("Messages sent will be attributed to this user.")
        
        st.header("Data")
        uploaded = st.file_uploader("Upload PDF", type=["pdf"])

        if uploaded is not None:
            if st.button("Build/Update Index", type="primary"):
                with st.spinner("Creating index... "):
                    build_or_update_index(uploaded.read(), st.session_state.selected_user)
                    pass
                st.success("Index created.")


    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
        
    prompt = st.chat_input("Say something")
    
    if prompt:
        st.session_state.messages.append(
            {
                "role": "user","name":st.session_state.selected_user,"content": prompt
            }
        )
        prompt_extended = create_prompt_history(st.session_state.messages)

        messages = [
            HumanMessage(content= f"{st.session_state.selected_user} said:" + prompt
                         + "\n\nThe last messages were:" + prompt_extended),
        ]

        with st.chat_message("user"):
            st.write(prompt)

        response = agent.invoke({"messages": messages})

        response_message = response["messages"][-1].content
        st.session_state.messages.append({"role": "assistant", "content": response_message})
        with st.chat_message("assistant"):
            pass
            st.write(response_message)




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
    print(pages)
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
            user = st.session_state.selected_user
            extended_prompt.append(f"The user {user} said: '{message["content"]}'")
            print(extended_prompt)
        else:
            extended_prompt.append(f"You said: '{message["content"]}'")

    extended_prompt = "\n".join(extended_prompt)
    return extended_prompt

if __name__ == "__main__":
    main()
