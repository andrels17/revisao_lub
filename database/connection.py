import psycopg2
import streamlit as st

def get_conn():
    url = st.secrets["DATABASE_URL"]

    # normaliza caso venha postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return psycopg2.connect(
        url,
        connect_timeout=10
    )
