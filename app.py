import streamlit as st
import json
from pypdf import PdfReader
from pptx import Presentation
from google import genai
from google.genai import types

st.set_page_config(page_title="StudyCard Studio ✨", page_icon="📚", layout="centered")

st.title("📚 StudyCard Studio")
st.write("Upload your slides, PDFs, or lecture notes to generate exam-ready quiz cards instantly.")

api_key = st.secrets.get("GEMINI_API_KEY")

uploaded_file = st.file_uploader("Upload Slides (.pptx) or Readings (.pdf)", type=["pdf", "pptx"])
pasted_notes = st.text_area("Or paste notes / study guides directly:", height=130, placeholder="Paste lecture notes or chapter outlines here...")

num_cards = st.slider("Number of flashcards to generate:", min_value=5, max_value=30, value=12)

def extract_text(file):
    text = ""
    if file.name.endswith(".pdf"):
        reader = PdfReader(file)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
    elif file.name.endswith(".pptx"):
        prs = Presentation(file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    text += shape.text + "\n"
    return text

if st.button("✨ Generate Quiz Cards", type="primary", use_container_width=True):
    if not api_key:
        st.error("API Key not found. Please add GEMINI_API_KEY to your Streamlit App Secrets.")
    else:
        combined_text = ""
        if uploaded_file:
            combined_text += extract_text(uploaded_file)
        if pasted_notes:
            combined_text += "\n" + pasted_notes

        if len(combined_text.strip()) < 30:
            st.warning("Please upload a file with readable text or paste your study notes.")
        else:
            with st.spinner("Writing exam-style flashcards..."):
                client = genai.Client(api_key=api_key)
                prompt = f"""
                You are an expert exam tutor. Create exactly {num_cards} high-yield, exam-style flashcards based on the material below.
                Focus on:
                1. Application and scenarios (not simple vocabulary definitions).
                2. Comparing and contrasting easily confused concepts.
                3. Cause-and-effect mechanisms.
                
                Return JSON format only:
                [
                  {{"question": "Exam-style question here", "answer": "Clear, direct explanation here"}}
                ]

                Material:
                {combined_text[:30000]}
                """
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                    cards = json.loads(response.text)
                    st.session_state["cards"] = cards
                    st.success(f"Created {len(cards)} exam-ready cards!")
                except Exception as e:
                    st.error(f"Error generating cards: {e}")

if "cards" in st.session_state and st.session_state["cards"]:
    st.divider()
    st.subheader("Your Study Deck")
    for i, card in enumerate(st.session_state["cards"]):
        with st.expander(f"Card {i+1}: {card['question']}"):
            st.markdown(f"Answer:")

    st.divider()
    quizlet_export = "\n".join([f"{c['question']}\t{c['answer']}" for c in st.session_state["cards"]])
    st.markdown("### 📋 Export to Quizlet / Anki")
    st.caption("Copy this text and paste it directly into Quizlet's 'Import' tab to create a permanent deck instantly:")
    st.text_area("Export string (Tab separated)", value=quizlet_export, height=100)
