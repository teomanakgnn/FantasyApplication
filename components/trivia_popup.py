"""
Trivia pop-up komponenti
components/trivia_popup.py olarak kaydedin
"""
import streamlit as st
from datetime import date

def should_show_trivia():
    """Bugün trivia gösterilmeli mi?"""
    today = date.today().isoformat()
    
    # Session state'te bugünün tarihini kontrol et
    if 'last_trivia_date' not in st.session_state:
        st.session_state.last_trivia_date = None
    
    # Eğer bugün zaten gösterilmediyse
    if st.session_state.last_trivia_date != today:
        return True
    
    return False

def mark_trivia_shown():
    """Trivia gösterildi olarak işaretle"""
    today = date.today().isoformat()
    st.session_state.last_trivia_date = today

@st.dialog("🏀 Daily NBA Trivia", width="large")
def show_trivia_popup(trivia_data, user_id, db):
    """Trivia pop-up'ını göster"""
    
    # Stil
    st.markdown("""
        <style>
        .trivia-container {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 15px;
            margin-bottom: 1.5rem;
            color: white;
        }
        .trivia-question {
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 1rem;
            line-height: 1.5;
        }
        .difficulty-badge {
            display: inline-block;
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }
        .easy { background-color: #10b981; }
        .medium { background-color: #f59e0b; }
        .hard { background-color: #ef4444; }
        </style>
    """, unsafe_allow_html=True)
    
    trivia_id = trivia_data['id']
    
    # Kullanıcı zaten cevapladı mı kontrol et
    already_answered = db.has_user_answered_today(user_id, trivia_id) if user_id else False
    
    if already_answered:
        st.success("✅ You've already answered today's trivia!")
        
        # İstatistikleri göster
        if user_id:
            stats = db.get_user_trivia_stats(user_id)
            if stats:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Answered", stats['total_answered'])
                with col2:
                    st.metric("Correct", stats['correct_count'])
                with col3:
                    st.metric("Accuracy", f"{stats['accuracy']:.1f}%")
        
        if st.button("Close", use_container_width=True):
            mark_trivia_shown()
            st.rerun()
        return
    
    # Difficulty badge
    difficulty_colors = {
        'easy': 'easy',
        'medium': 'medium',
        'hard': 'hard'
    }
    difficulty_class = difficulty_colors.get(trivia_data['difficulty'].lower(), 'medium')
    
    # Soru göster
    st.markdown(f"""
        <div class="trivia-container">
            <div class="difficulty-badge {difficulty_class}">
                {trivia_data['difficulty'].upper()}
            </div>
            <div class="trivia-question">
                {trivia_data['question']}
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Cevap seçenekleri
    st.markdown("### Select your answer:")
    
    options = {
        'A': trivia_data['option_a'],
        'B': trivia_data['option_b'],
        'C': trivia_data['option_c'],
        'D': trivia_data['option_d']
    }
    
    selected = st.radio(
        "Choose one:",
        options.keys(),
        format_func=lambda x: f"{x}) {options[x]}",
        key="trivia_answer"
    )
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("✅ Submit Answer", use_container_width=True, type="primary"):
            is_correct = selected == trivia_data['correct_answer']
            
            # Cevabı kaydet (user_id varsa)
            if user_id:
                db.save_trivia_answer(user_id, trivia_id, selected, is_correct)
            
            # Session state'e sonucu kaydet
            st.session_state.trivia_result = {
                'selected': selected,
                'correct': trivia_data['correct_answer'],
                'is_correct': is_correct,
                'explanation': trivia_data['explanation']
            }
            
            mark_trivia_shown()
            st.rerun()
    
    with col2:
        if st.button("Skip", use_container_width=True, type="secondary"):
            mark_trivia_shown()
            st.rerun()
    
    # Eğer cevap verilmişse sonucu göster
    if 'trivia_result' in st.session_state:
        result = st.session_state.trivia_result
        
        st.markdown("---")
        
        if result['is_correct']:
            st.success("🎉 Correct! Well done!")
        else:
            st.error(f"❌ Incorrect. The correct answer was: {result['correct']}) {options[result['correct']]}")
        
        if result['explanation']:
            st.info(f"💡 **Explanation:** {result['explanation']}")
        
        # İstatistikleri göster
        if user_id:
            stats = db.get_user_trivia_stats(user_id)
            if stats:
                st.markdown("### Your Stats")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total", stats['total_answered'])
                with col2:
                    st.metric("Correct", stats['correct_count'])
                with col3:
                    st.metric("Accuracy", f"{stats['accuracy']:.1f}%")
                with col4:
                    st.metric("Streak", stats['days_played'])
        
        if st.button("Close", use_container_width=True):
            if 'trivia_result' in st.session_state:
                del st.session_state.trivia_result
            st.rerun()

def render_trivia_if_needed(user, db):
    """Gerekirse trivia'yı göster"""
    
    # Trivia gösterilmeli mi kontrol et
    if not should_show_trivia():
        return
    
    # Bugünün trivia'sını al
    trivia = db.get_today_trivia()
    
    if not trivia:
        # Trivia yok, gösterme
        mark_trivia_shown()
        return
    
    # User ID'yi al (login olmuşsa)
    user_id = user.get('id') if user else None
    
    # Pop-up'ı göster
    show_trivia_popup(trivia, user_id, db)