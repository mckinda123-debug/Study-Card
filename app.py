import streamlit as st
import json
import random
from pypdf import PdfReader
from pptx import Presentation
from groq import Groq

st.set_page_config(page_title="StudyCard Studio ✨", page_icon="📚", layout="centered")

# Initialize persistent memory for stacked chapters and quiz mode
if "master_deck" not in st.session_state:
    st.session_state["master_deck"] = []
if "quiz_index" not in st.session_state:
    st.session_state["quiz_index"] = 0
if "show_answer" not in st.session_state:
    st.session_state["show_answer"] = False

st.title("📚 StudyCard Studio")
st.caption("Upload your chapters to build your master MCQ exam deck, then test yourself in Quiz Mode.")

api_key = st.secrets.get("GROQ_API_KEY")

tab_create, tab_quiz, tab_export = st.tabs(["➕ Add Chapters", "🎯 Practice Quiz", "📥 Master Export"])

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

# --- TAB 1: ADD CHAPTERS ---
with tab_create:
    st.subheader("Add Study Material")
    uploaded_file = st.file_uploader("Upload Chapter Slides (.pptx) or PDF (.pdf)", type=["pdf", "pptx"])
    pasted_notes = st.text_area("Or paste chapter notes:", height=100, placeholder="Paste notes here...")
    
    col1, col2 = st.columns(2)
    with col1:
        num_cards = st.slider("MCQ Cards to generate for this chapter:", min_value=5, max_value=35, value=15)
    with col2:
        chapter_tag = st.text_input("Chapter Name / Tag:", placeholder="e.g., Chapter 1")

    if st.button("✨ Generate & Add to Master Deck", type="primary", use_container_width=True):
        if not api_key:
            st.error("API Key missing. Please add GROQ_API_KEY to your Streamlit Secrets.")
        else:
            combined_text = ""
            if uploaded_file:
                combined_text += extract_text(uploaded_file)
            if pasted_notes:
                combined_text += "\n" + pasted_notes

            if len(combined_text.strip()) < 30:
                st.warning("Please upload a file or enter readable notes.")
            else:
                with st.spinner("Crafting multiple-choice questions with Groq..."):
                    try:
                        client = Groq(api_key=api_key.strip())
                        
                        # Dynamically find the best active Groq model
                        available = [m.id for m in client.models.list().data]
                        chat_models = [
                            m for m in available 
                            if not any(x in m.lower() for x in ["whisper", "guard", "embed", "safeguard"])
                        ]

                        chosen_model = None
                        for pref in ["llama-3.3", "llama-3.1", "llama3", "mixtral", "gemma"]:
                            for m in chat_models:
                                if pref in m.lower():
                                    chosen_model = m
                                    break
                            if chosen_model:
                                break

                        if not chosen_model:
                            chosen_model = chat_models[0] if chat_models else "llama3-8b-8192"

                        prompt = f"""
                        You are an expert exam tutor. Create exactly {num_cards} high-yield multiple-choice exam questions based on this material.
                        Focus on conceptual application and cause/effect mechanisms.
                        Every card MUST have 4 distinct choices labeled A, B, C, D. The answer must be strictly one letter (A, B, C, or D).

                        Respond ONLY with a JSON object in this exact schema:
                        {{
                          "cards": [
                            {{
                              "question": "Question stem here?",
                              "option_a": "First choice description",
                              "option_b": "Second choice description",
                              "option_c": "Third choice description",
                              "option_d": "Fourth choice description",
                              "answer": "A",
                              "explanation": "Clear explanation of why this answer is correct."
                            }}
                          ]
                        }}

                        Material:
                        {combined_text[:35000]}
                        """

                        completion = client.chat.completions.create(
                            model=chosen_model,
                            messages=[
                                {"role": "system", "content": "You are a professional exam creator that outputs strictly valid JSON for multiple choice questions."},
                                {"role": "user", "content": prompt}
                            ],
                            response_format={"type": "json_object"}
                        )

                        parsed = json.loads(completion.choices[0].message.content)
                        new_cards = parsed.get("cards", [])

                        tag = chapter_tag.strip() if chapter_tag.strip() else f"Ch {len(st.session_state['master_deck'])//10 + 1}"
                        for card in new_cards:
                            card["tag"] = tag

                        st.session_state["master_deck"].extend(new_cards)
                        st.session_state["quiz_index"] = 0
                        st.session_state["show_answer"] = False
                        st.success(f"Generated {len(new_cards)} MCQs! Total in Master Deck: {len(st.session_state['master_deck'])}.")
                    except Exception as e:
                        st.error(f"Generation error: {e}")

    # Deck status and reset
    if st.session_state["master_deck"]:
        st.divider()
        col_info, col_clear = st.columns([3, 1])
        with col_info:
            st.info(f"**Current Master Deck:** {len(st.session_state['master_deck'])} MCQs ready.")
        with col_clear:
            if st.button("🗑️ Reset Deck", help="Clear all cards and start a new exam deck"):
                st.session_state["master_deck"] = []
                st.session_state["quiz_index"] = 0
                st.rerun()

# --- TAB 2: PRACTICE QUIZ ---
with tab_quiz:
    deck = st.session_state["master_deck"]
    if not deck:
        st.info("No cards in the deck yet. Upload a chapter in the first tab to begin!")
    else:
        st.subheader("🎯 Multiple Choice Exam Mode")
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("🔀 Shuffle Deck"):
                random.shuffle(st.session_state["master_deck"])
                st.session_state["quiz_index"] = 0
                st.session_state["show_answer"] = False
                st.rerun()
        with c2:
            st.write(f"Question **{st.session_state['quiz_index'] + 1}** of **{len(deck)}**")
        with c3:
            current_tag = deck[st.session_state['quiz_index']].get("tag", "")
            if current_tag:
                st.caption(f"🏷️ {current_tag}")

        card = deck[st.session_state["quiz_index"]]

        # Front of Card: Multiple Choice Question & Options
        st.markdown(
            f"""
            <div style="background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; border-radius: 12px; padding: 22px; margin: 15px 0;">
                <h4 style="color: #93c5fd; margin-top: 0;">Question:</h4>
                <p style="font-size: 1.15rem; font-weight: 600; line-height: 1.5;">{card.get('question', '')}</p>
                <hr style="border: 0; border-top: 1px solid #334155; margin: 15px 0;">
                <div style="font-size: 1.05rem; line-height: 1.8;">
                    <p><strong>A)</strong> {card.get('option_a', '')}</p>
                    <p><strong>B)</strong> {card.get('option_b', '')}</p>
                    <p><strong>C)</strong> {card.get('option_c', '')}</p>
                    <p><strong>D)</strong> {card.get('option_d', '')}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Back of Card: Reveal Answer (A, B, C, or D) + Explanation
        if st.session_state["show_answer"]:
            ans_letter = card.get('answer', '').strip().upper()
            st.markdown(
                f"""
                <div style="background-color: #064e3b; color: #ecfdf5; border: 2px solid #059669; border-radius: 12px; padding: 22px; margin-bottom: 20px;">
                    <h3 style="color: #6ee7b7; margin: 0 0 10px 0;">✅ Correct Answer: {ans_letter}</h3>
                    <p style="font-size: 1.05rem; line-height: 1.5; color: #d1fae5;">{card.get('explanation', '')}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("🙈 Hide Answer"):
                st.session_state["show_answer"] = False
                st.rerun()
        else:
            if st.button("👀 Reveal Answer (A, B, C, D)", type="secondary", use_container_width=True):
                st.session_state["show_answer"] = True
                st.rerun()

        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.button("⬅️ Previous Question", use_container_width=True):
                if st.session_state["quiz_index"] > 0:
                    st.session_state["quiz_index"] -= 1
                    st.session_state["show_answer"] = False
                    st.rerun()
        with col_next:
            if st.button("Next Question ➡️", type="primary", use_container_width=True):
                if st.session_state["quiz_index"] < len(deck) - 1:
                    st.session_state["quiz_index"] += 1
                    st.session_state["show_answer"] = False
                    st.rerun()
                else:
                    st.balloons()
                    st.success("🎉 You've completed all MCQs in this deck!")

# --- TAB 3: MASTER EXPORT ---
with tab_export:
    deck = st.session_state["master_deck"]
    if not deck:
        st.info("No cards generated yet.")
    else:
        st.subheader("📥 Export Cumulative MCQs")
        st.caption("Formatted for direct copy-paste into Quizlet or Anki:")
        
        lines = []
        for c in deck:
            tag = c.get('tag', 'Exam')
            front = f"[{tag}] {c.get('question','')} | A) {c.get('option_a','')} | B) {c.get('option_b','')} | C) {c.get('option_c','')} | D) {c.get('option_d','')}"
            back = f"Answer: {c.get('answer','')} — {c.get('explanation','')}"
            lines.append(f"{front}\t{back}")

        formatted_export = "\n".join(lines)
        st.text_area("Tab-separated text:", value=formatted_export, height=220)
