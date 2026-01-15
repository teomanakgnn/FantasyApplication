import streamlit as st
from services.database import db
import pandas as pd
from datetime import datetime

def render_watchlist_page():
    """PRO Feature: Player Watchlist with Performance Tracking"""
    
    st.title("⭐ My Watchlist")
    st.caption("Track your favorite players and monitor their performance")
    
    user_id = st.session_state.user['id']
    
    # Custom CSS for watchlist
    st.markdown("""
        <style>
        .player-card {
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            border-left: 4px solid #667eea;
            padding: 1rem;
            border-radius: 8px;
            margin: 0.5rem 0;
        }
        .player-name {
            font-size: 1.3rem;
            font-weight: 700;
            color: #667eea;
        }
        .player-meta {
            font-size: 0.85rem;
            color: #6b7280;
            margin-top: 0.3rem;
        }
        .player-notes {
            background-color: #f9fafb;
            padding: 0.8rem;
            border-radius: 6px;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }
        @media (prefers-color-scheme: dark) {
            .player-notes { background-color: #1f2937; }
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Add player section
    with st.expander("➕ Add New Player to Watchlist", expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            player_name = st.text_input(
                "Player Name", 
                placeholder="e.g., LeBron James, Stephen Curry",
                help="Enter the full name as it appears in game stats"
            )
        
        notes = st.text_area(
            "Notes (optional)", 
            placeholder="Why are you tracking this player? Trade target? Injury watch? Hot streak?",
            help="Add personal notes about why you're tracking this player"
        )
        
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            if st.button("➕ Add to Watchlist", type="primary", use_container_width=True):
                if player_name:
                    # Check if already exists
                    watchlist = db.get_watchlist(user_id)
                    if any(w['player_name'].lower() == player_name.lower() for w in watchlist):
                        st.warning(f"⚠️ {player_name} is already in your watchlist!")
                    else:
                        success = db.add_to_watchlist(user_id, player_name, notes)
                        if success:
                            st.success(f"✅ {player_name} added to watchlist!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("Failed to add player")
                else:
                    st.warning("Please enter a player name")
    
    st.markdown("---")
    
    # Display watchlist
    watchlist = db.get_watchlist(user_id)
    
    if not watchlist:
        # Empty state
        st.markdown("""
            <div style='text-align: center; padding: 3rem; background-color: #f9fafb; border-radius: 12px; margin: 2rem 0;'>
                <div style='font-size: 3rem; margin-bottom: 1rem;'>📝</div>
                <h3>Your Watchlist is Empty</h3>
                <p style='color: #6b7280; font-size: 1.1rem;'>
                    Start tracking players to monitor their performance and stay updated!
                </p>
                <p style='color: #9ca3af; font-size: 0.9rem; margin-top: 1rem;'>
                    💡 Tip: You can add players from box scores or the daily stats table
                </p>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Header with stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Players", len(watchlist))
        with col2:
            with_notes = sum(1 for w in watchlist if w.get('notes'))
            st.metric("With Notes", with_notes)
        with col3:
            # Most recent addition
            latest = max(watchlist, key=lambda x: x['created_at'])
            days_ago = (datetime.now() - latest['created_at']).days
            st.metric("Last Added", f"{days_ago} days ago")
        
        st.markdown("---")
        
        # Filter and sort options
        col_filter, col_sort = st.columns([2, 1])
        with col_filter:
            search = st.text_input("🔍 Search players", placeholder="Type to filter...")
        with col_sort:
            sort_by = st.selectbox("Sort by", ["Recently Added", "Alphabetical", "With Notes First"])
        
        # Apply filters
        filtered_watchlist = watchlist
        if search:
            filtered_watchlist = [
                w for w in watchlist 
                if search.lower() in w['player_name'].lower()
            ]
        
        # Apply sorting
        if sort_by == "Recently Added":
            filtered_watchlist = sorted(filtered_watchlist, key=lambda x: x['created_at'], reverse=True)
        elif sort_by == "Alphabetical":
            filtered_watchlist = sorted(filtered_watchlist, key=lambda x: x['player_name'])
        elif sort_by == "With Notes First":
            filtered_watchlist = sorted(filtered_watchlist, key=lambda x: (bool(x.get('notes')), x['player_name']), reverse=True)
        
        st.subheader(f"Tracking {len(filtered_watchlist)} Player{'s' if len(filtered_watchlist) != 1 else ''}")
        
        # Display as enhanced cards
        for idx, item in enumerate(filtered_watchlist):
            st.markdown(f"""
                <div class="player-card">
                    <div class="player-name">🏀 {item['player_name']}</div>
                    <div class="player-meta">
                        Added on {item['created_at'].strftime('%B %d, %Y at %I:%M %p')}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Notes and actions in columns
            col_notes, col_actions = st.columns([4, 1])
            
            with col_notes:
                if item.get('notes'):
                    st.markdown(f"""
                        <div class="player-notes">
                            <strong>📌 Notes:</strong><br>
                            {item['notes']}
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.caption("_No notes added_")
            
            with col_actions:
                # Edit notes
                if st.button("✏️", key=f"edit_{item['id']}", help="Edit notes"):
                    st.session_state[f"editing_{item['id']}"] = True
                    st.rerun()
                
                # Remove
                if st.button("🗑️", key=f"del_{item['id']}", help="Remove from watchlist"):
                    if db.remove_from_watchlist(item['id']):
                        st.success(f"Removed {item['player_name']}!")
                        st.rerun()
            
            # Edit dialog
            if st.session_state.get(f"editing_{item['id']}", False):
                with st.container(border=True):
                    new_notes = st.text_area(
                        "Update notes",
                        value=item.get('notes', ''),
                        key=f"notes_edit_{item['id']}"
                    )
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Save", key=f"save_{item['id']}", use_container_width=True):
                            if db.update_watchlist_notes(item['id'], new_notes):
                                st.session_state[f"editing_{item['id']}"] = False
                                st.success("Notes updated!")
                                st.rerun()
                            else:
                                st.error("Failed to update notes")
                    with col_cancel:
                        if st.button("❌ Cancel", key=f"cancel_{item['id']}", use_container_width=True):
                            st.session_state[f"editing_{item['id']}"] = False
                            st.rerun()
            
            st.markdown("---")
        
        # Bulk actions
        if len(filtered_watchlist) > 0:
            st.markdown("### Bulk Actions")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Export watchlist
                if st.button("📥 Export to CSV", use_container_width=True):
                    df = pd.DataFrame(filtered_watchlist)
                    df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    csv = df[['player_name', 'notes', 'created_at']].to_csv(index=False)
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv,
                        file_name=f"watchlist_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            with col2:
                # Clear all
                if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
                    st.session_state.confirm_clear = True
            
            if st.session_state.get("confirm_clear", False):
                st.warning("⚠️ Are you sure you want to remove all players from your watchlist?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("Yes, clear all", type="primary"):
                        for item in watchlist:
                            db.remove_from_watchlist(item['id'])
                        st.success("Watchlist cleared!")
                        st.session_state.confirm_clear = False
                        st.rerun()
                with col_no:
                    if st.button("No, keep them"):
                        st.session_state.confirm_clear = False
                        st.rerun()
    
    # Back button
    st.markdown("---")
    col_back, col_space = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Back to Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()