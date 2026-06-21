"""Minimal Streamlit test — proves Streamlit can render in frozen mode."""
import streamlit as st
st.set_page_config(page_title="Test", layout="wide")
st.title("QuantSage Test")
st.write("If you can see this, Streamlit is working!")
st.write("This is a minimal test page.")
