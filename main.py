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
    get_agent
)

USERS = ["Salmaze", "Bernardo", "Rafa4", "Samuel"]

PFP = {
    "Salmaze":"imgs/salmas.png",
    "Bernardo":"imgs/Berna.jpg",
    "Rafa4":"imgs/R4.jpg",
    "Samuel":"imgs/Samuel.jpg"
}

def ensure_session_state():
    """Initialize all session variables"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        #list of {role: "user"|"assistant"|"system", content: str}
        load_dotenv()
        st.session_state.messages = []

    if "agent" not in st.session_state:
        st.session_state.agent = get_agent()

    if "selected_user" not in st.session_state:
        st.session_state.selected_user = USERS[0]

def main():
    ensure_session_state()
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
                    build_or_update_index(uploaded.read(), uploaded.name)
                st.success("Index created.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with (st.chat_message(msg["role"],avatar=msg["avatar"])):
            st.write(msg["content"])
        
    prompt = st.chat_input("Say something")
    
    if prompt:
        st.session_state.messages.append(
            {
                "name": st.session_state.selected_user,
                "role": "user",
                "avatar": PFP[st.session_state.selected_user],
                "content": prompt,
            }
        )
        prompt_extended = create_prompt_history(st.session_state.messages)

        messages = [
            HumanMessage(content= f"{st.session_state.selected_user} said:" + prompt
                         + "\n\nThe last messages were:" + prompt_extended),
        ]

        with st.chat_message("user", avatar=PFP[st.session_state.selected_user]):
            st.write(prompt)

        response = st.session_state.agent.invoke({"messages": messages})

        response_message = response["messages"][-1].content

        st.session_state.messages.append(
            {
                "name":"assistant",
                "role": "assistant",
                "avatar": None,
                "content": response_message
            }
        )

        with st.chat_message("assistant"):
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
    st.session_state.retriever = build_retriever(vectorstore)
    os.unlink(tmp_path)
    return st.session_state.retriever


def get_shared_vectorstore_dir() -> str:
    base = os.environ.get("RAG_VDB_DIR", "./vdb")
    if not os.path.exists(base):
        os.makedirs(base)
    return base


def create_prompt_history(messages, length_detailed_history: int = 10):
    n = length_detailed_history
    extended_prompt = []

    for message in messages[-n:]:
        if message["role"] == "user":
            extended_prompt.append(f"The {message.get("name","SOMEONE")} user said: '{message["content"]}'")
            print(extended_prompt)
        else:
            extended_prompt.append(f"You said: '{message["content"]}'")

    extended_prompt = "\n".join(extended_prompt)
    return extended_prompt


if __name__ == "__main__":
    main()
