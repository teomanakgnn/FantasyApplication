import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.helpers import parse_minutes
from services.espn_api import get_historical_boxscores, get_injuries, get_current_team_rosters, get_nba_season_stats_official 

# =================================================================
# TEAM MAPPING (KISALTMALAR -> TAM İSİMLER)
# =================================================================
TEAM_MAP = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'GS': 'Golden State Warriors',
    'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NO': 'New Orleans Pelicans',
    'NYK': 'New York Knicks', 'NY': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic', 
    'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 
    'SAS': 'San Antonio Spurs', 'SA': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'UTAH': 'Utah Jazz', 'WSH': 'Washington Wizards'
}

# =================================================================
# 1. HELPER CALCULATION FUNCTIONS
# =================================================================

def calculate_fantasy_score(stats_dict, weights):
    """
    Calculates fantasy score based on given stats and weights.
    """
    score = 0.0
    for stat, weight in weights.items():
        val = stats_dict.get(stat, 0)
        try:
            score += float(val) * float(weight)
        except (ValueError, TypeError):
            pass
    return score

def get_date_range(period):
    """
    Returns date range based on selected period.
    """
    today = datetime.now()
    if period == "Today":
        return today.date(), today.date()
    elif period == "This Week":
        start = today - timedelta(days=today.weekday())
        return start.date(), today.date()
    elif period == "This Month":
        start = today.replace(day=1)
        return start.date(), today.date()
    elif period == "Season":
        if today.month >= 10:
            season_start = today.replace(month=10, day=22)
        else:
            season_start = today.replace(year=today.year - 1, month=10, day=22)
        return season_start.date(), today.date()
    return today.date(), today.date()

def normalize_player_name(name):
    """Normalizes names for comparison."""
    if not name:
        return ""
    return name.replace(".", "").replace("'", "").replace("-", " ").lower().strip()

def aggregate_player_stats(all_game_data, weights):
    """
    Aggregates historical game data, calculates averages and scores.
    **UPDATE:** Matches player IDs and adds them to the DataFrame.
    """
    # Get current roster info
    try:
        current_rosters = get_current_team_rosters()
        print(f"✓ Roster info received: {len(current_rosters)} players")
    except Exception as e:
        print(f"❌ Roster could not be fetched: {e}")
        current_rosters = {}
    
    # Create normalized roster dictionary
    normalized_rosters = {}
    for player_name, info in current_rosters.items():
        norm_name = normalize_player_name(player_name)
        
        # info can be a dict {'team': 'LAL', 'id': '1234'} or a string
        if isinstance(info, dict):
            team_code = info.get('team')
            p_id = info.get('id')
        else:
            team_code = info
            p_id = None

        normalized_rosters[norm_name] = {
            'team': team_code,
            'id': p_id,
            'original_name': player_name
        }
    
    print(f"✓ Normalized roster: {len(normalized_rosters)} players")
    
    player_totals = {}
    matched_count = 0
    unmatched_count = 0
    
    for game_day in all_game_data:
        players = game_day.get('players', [])
        game_date = game_day.get('date')
        
        for player in players:
            raw_name = player.get('PLAYER')
            if not raw_name:
                continue
            
            # Normalize name
            norm_name = normalize_player_name(raw_name)
            
            # Find player in current roster
            roster_info = normalized_rosters.get(norm_name)
            
            player_id = None # Default no ID

            if roster_info:
                # Found in roster
                display_name = roster_info['original_name']
                current_team = roster_info['team']
                player_id = roster_info['id']
                matched_count += 1
            else:
                # Not in roster - use raw name
                display_name = raw_name
                current_team = player.get('TEAM', 'UNK')
                unmatched_count += 1
                
                # Debug
                if game_date:
                    try:
                        date_diff = (datetime.now() - pd.to_datetime(game_date)).days
                        if date_diff < 7 and unmatched_count <= 5:
                            print(f"⚠️ Not found in roster: {raw_name}")
                    except:
                        pass
            
            # KEY: PLAYER NAME ONLY
            key = display_name
            
            if key not in player_totals:
                player_totals[key] = {
                    'PLAYER': display_name,
                    'PLAYER_ID': player_id,
                    'TEAM': current_team,
                    'GAMES': 0,
                    'MIN_TOTAL': 0,
                    'PTS': 0, 'REB': 0, 'AST': 0, 'STL': 0, 'BLK': 0, 'TO': 0,
                    'FGM': 0, 'FGA': 0, '3Pts': 0, '3PTA': 0, 'FTM': 0, 'FTA': 0,
                    '+/-': 0,
                    'game_logs': [],
                    'teams_played_for': set()
                }
            
            stats = player_totals[key]
            
            # Update ID if found later
            if stats['PLAYER_ID'] is None and player_id is not None:
                stats['PLAYER_ID'] = player_id

            # Update team info (always latest)
            stats['TEAM'] = current_team
            
            # Track teams played for
            game_team = player.get('TEAM', '')
            if game_team:
                stats['teams_played_for'].add(game_team)
            
            # Increment games
            stats['GAMES'] += 1
            
            # Parse minutes
            min_val = parse_minutes(player.get('MIN', '0'))
            stats['MIN_TOTAL'] += min_val
            
            # Sum numeric stats
            numeric_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 
                           'FGM', 'FGA', '3Pts', '3PTA', 'FTM', 'FTA', '+/-']
            
            for stat in numeric_stats:
                val = player.get(stat, 0)
                try: 
                    stats[stat] += float(val)
                except: 
                    pass
            
            # Log game
            game_log = {
                'DATE': game_date,
                'MIN': min_val,
                'TEAM': game_team
            }
            for stat in numeric_stats:
                try:
                    game_log[stat] = float(player.get(stat, 0))
                except:
                    game_log[stat] = 0
            stats['game_logs'].append(game_log)
    
    # Calculate averages
    result = []
    for stats in player_totals.values():
        games = stats['GAMES']
        if games == 0:
            continue
            
        avg_stats = stats.copy()
        
        # Average minutes
        avg_min = stats['MIN_TOTAL'] / games
        avg_stats['MIN'] = f"{int(avg_min)}"
        avg_stats['MIN_INT'] = avg_min
        
        # Other averages
        stats_to_average = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 
                          'FGM', 'FGA', '3Pts', '3PTA', 'FTM', 'FTA', '+/-']
        
        for k in stats_to_average:
            avg_stats[k] = stats[k] / games

        # Calculate Fantasy Score
        avg_stats['USER_SCORE'] = calculate_fantasy_score(avg_stats, weights)
        
        # Formatting shooting
        avg_stats['FG'] = f"{avg_stats['FGM']:.1f}/{avg_stats['FGA']:.1f}"
        avg_stats['3PT'] = f"{avg_stats['3Pts']:.1f}/{avg_stats['3PTA']:.1f}"
        avg_stats['FT'] = f"{avg_stats['FTM']:.1f}/{avg_stats['FTA']:.1f}"
        
        # Trade info
        if len(stats['teams_played_for']) > 1:
            teams_list = sorted(list(stats['teams_played_for']))
            avg_stats['TRADED'] = f"({' → '.join(teams_list)})"
        else:
            avg_stats['TRADED'] = ""
        
        result.append(avg_stats)
    
    df = pd.DataFrame(result)
    
    # Debug summary
    print(f"\n{'='*60}")
    print(f"📊 AGGREGATE SUMMARY")
    print(f"{'='*60}")
    print(f"✓ Total {len(df)} player rows created")
    print(f"✓ Roster match: {matched_count} records")
    print(f"{'='*60}\n")
    
    return df

# =================================================================
# 2. PLAYER ANALYSIS MODAL (REFRESHED PRO UI & ANALYSIS)
# =================================================================
@st.dialog("Player Insights", width="large")
def show_player_analysis(player_row, weights):
    st.session_state.active_dialog = 'player_analysis'
    """
    Gelişmiş oyuncu analizi - Akıllı yorumlar ve temiz tasarım
    """
    
    # ======================================================
    # A. DATA PREPARATION & CONTEXT DETECTION
    # ======================================================
    name = player_row["PLAYER"]
    raw_team = player_row["TEAM"]
    
    # Team handling
    if isinstance(raw_team, dict):
        team_abbr = raw_team.get('team', 'UNK')
    else:
        team_abbr = str(raw_team) if raw_team else "UNK"
    
    team = TEAM_MAP.get(team_abbr.upper(), team_abbr)
    
    # CONTEXT DETECTION: Tek maç mı, yoksa ortalama mı?
    is_single_game = player_row.get("GAMES", 1) == 1
    games = int(player_row.get("GAMES", 1))
    
    # Basic Stats
    score = float(player_row["USER_SCORE"])
    mins = float(player_row.get("MIN_INT", 0))

    # Detailed Stats
    def get_val(key): return float(player_row.get(key, 0))
    
    fgm, fga = get_val("FGM"), get_val("FGA")
    ftm, fta = get_val("FTM"), get_val("FTA")
    three_pm, three_pa = get_val("3Pts"), get_val("3PTA")
    pts, reb, ast = get_val("PTS"), get_val("REB"), get_val("AST")
    stl, blk, to = get_val("STL"), get_val("BLK"), get_val("TO")
    plus_minus = get_val("+/-")

    # Advanced Metrics
    stocks = stl + blk
    fp_min = score / mins if mins > 0 else 0
    
    # Shooting Efficiency
    fg_pct = (fgm / fga * 100) if fga > 0 else 0
    ft_pct = (ftm / fta * 100) if fta > 0 else 0
    three_pct = (three_pm / three_pa * 100) if three_pa > 0 else 0
    
    # True Shooting %
    ts_attempts = fga + (0.44 * fta)
    ts_pct = (pts / (2 * ts_attempts) * 100) if ts_attempts > 0 else 0
    
    # Usage & Efficiency
    usage_proxy = fga + (0.44 * fta) + to
    ast_to_ratio = ast / to if to > 0 else ast
    
    # Game Impact Score
    game_impact = pts + reb + ast + stl + blk - to
    
    traded_info = player_row.get("TRADED", "")
    
    # Player Image
    player_id = player_row.get("PLAYER_ID")
    if player_id and str(player_id).isdigit():
        player_img_url = f"https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/{player_id}.png&w=500&h=364"
    else:
        player_img_url = f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&size=400&background=667eea&color=fff&bold=true"

    # ======================================================
    # B. INTELLIGENT ANALYSIS ENGINE
    # ======================================================
    
    def generate_performance_analysis():
        """Akıllı performans analizi oluşturur"""
        analysis = []
        
        # 1. EFFICIENCY ANALYSIS
        if fp_min >= 1.5:
            analysis.append({
                'type': 'positive',
                'title': 'Elite Efficiency',
                'text': f'{fp_min:.2f} fantasy points per minute is elite territory. This level of production in limited time shows true impact.'
            })
        elif fp_min >= 1.2:
            analysis.append({
                'type': 'positive', 
                'title': 'Strong Efficiency',
                'text': f'Producing {fp_min:.2f} FP/min is well above league average. Solid fantasy contributor.'
            })
        elif fp_min < 0.8 and mins > 20:
            analysis.append({
                'type': 'negative',
                'title': 'Inefficient Performance',
                'text': f'Only {fp_min:.2f} FP/min despite {mins:.0f} minutes is concerning. Poor fantasy value relative to opportunity.'
            })
        
        # 2. SCORING ANALYSIS
        if pts >= 30:
            analysis.append({
                'type': 'positive',
                'title': 'Dominant Scoring',
                'text': f'{pts:.1f} points {"in this game" if is_single_game else "per game"} - carrying the offensive load as the clear first option.'
            })
        elif pts >= 20 and fg_pct >= 50:
            analysis.append({
                'type': 'positive',
                'title': 'Efficient Scoring',
                'text': f'{pts:.1f} points on {fg_pct:.1f}% shooting. Quality over quantity - taking smart shots and converting.'
            })
        elif pts >= 20 and fg_pct < 40:
            analysis.append({
                'type': 'warning',
                'title': 'Volume Scorer',
                'text': f'{pts:.1f} points but only {fg_pct:.1f}% FG%. High usage but forcing the issue - efficiency needs improvement.'
            })
        elif fga >= 15 and pts < 15:
            analysis.append({
                'type': 'negative',
                'title': 'Shot Selection Issues',
                'text': f'{fga:.0f} field goal attempts but only {pts:.1f} points. Empty possessions hurting the team and fantasy value.'
            })
        
        # 3. PLAYMAKING ANALYSIS
        if ast >= 10 and ast_to_ratio >= 2.5:
            analysis.append({
                'type': 'positive',
                'title': 'Elite Playmaking',
                'text': f'{ast:.1f} assists with {ast_to_ratio:.1f} AST/TO ratio. Orchestrating the offense with exceptional decision-making.'
            })
        elif ast >= 7:
            analysis.append({
                'type': 'positive',
                'title': 'Strong Facilitator',
                'text': f'{ast:.1f} assists shows excellent court vision. Creating quality scoring opportunities for teammates.'
            })
        elif ast >= 5 and to > ast:
            analysis.append({
                'type': 'warning',
                'title': 'Turnover Issues',
                'text': f'{to:.1f} turnovers vs {ast:.1f} assists. Ball security needs improvement - giving away too many possessions.'
            })
        
        # 4. REBOUNDING ANALYSIS
        if reb >= 15:
            analysis.append({
                'type': 'positive',
                'title': 'Dominant on the Glass',
                'text': f'{reb:.1f} rebounds - controlling the paint and creating extra possessions for the team.'
            })
        elif reb >= 10:
            analysis.append({
                'type': 'positive',
                'title': 'Strong Rebounder',
                'text': f'{reb:.1f} rebounds showing excellent positioning and effort. Crashing the boards consistently.'
            })
        
        # 5. DEFENSIVE IMPACT
        if stocks >= 5:
            analysis.append({
                'type': 'positive',
                'title': 'Defensive Menace',
                'text': f'{stl:.1f} steals + {blk:.1f} blocks = {stocks:.1f} stocks. Wreaking havoc on defense and creating turnovers.'
            })
        elif stocks >= 3:
            analysis.append({
                'type': 'positive',
                'title': 'Solid Defender',
                'text': f'{stocks:.1f} stocks shows active hands and good timing. Contributing beyond the box score.'
            })
        
        # 6. SHOOTING ANALYSIS
        if ts_pct >= 65:
            analysis.append({
                'type': 'positive',
                'title': 'Exceptional Shooting',
                'text': f'{ts_pct:.1f}% True Shooting is elite. Getting quality looks and converting at a high rate.'
            })
        elif ts_pct < 50 and fga >= 12:
            analysis.append({
                'type': 'negative',
                'title': 'Poor Shot Selection',
                'text': f'{ts_pct:.1f}% TS% on {fga:.0f} attempts. Taking too many low-percentage shots - needs to be more selective.'
            })
        
        # 7. THREE-POINT SHOOTING
        if three_pm >= 5:
            analysis.append({
                'type': 'positive',
                'title': 'Sharpshooting Display',
                'text': f'{three_pm:.0f} three-pointers made. Stretching the floor and punishing defenses from deep.'
            })
        elif three_pa >= 8 and three_pct < 30:
            analysis.append({
                'type': 'warning',
                'title': 'Cold from Three',
                'text': f'Only {three_pm:.0f}/{three_pa:.0f} from three ({three_pct:.1f}%). Needs to find rhythm or attack the basket more.'
            })
        
        # 8. MINUTES & OPPORTUNITY
        if mins >= 38 and is_single_game:
            analysis.append({
                'type': 'info',
                'title': 'Heavy Minutes',
                'text': f'{mins:.0f} minutes is a massive workload. Coach clearly trusts them in crunch time.'
            })
        elif mins < 20 and score >= 25:
            analysis.append({
                'type': 'positive',
                'title': 'Ultra-Efficient',
                'text': f'{score:.1f} fantasy points in only {mins:.0f} minutes. Maximizing every second on the floor.'
            })
        elif mins < 15 and is_single_game:
            analysis.append({
                'type': 'warning',
                'title': 'Limited Opportunity',
                'text': f'Only {mins:.0f} minutes suggests limited role or foul trouble. Hard to produce with this little playing time.'
            })
        
        # 9. OVERALL IMPACT
        if plus_minus >= 15:
            analysis.append({
                'type': 'positive',
                'title': 'Game Changer',
                'text': f'+{plus_minus:.0f} plus/minus. Team dominated when they were on the floor.'
            })
        elif plus_minus <= -10:
            analysis.append({
                'type': 'negative',
                'title': 'Negative Impact',
                'text': f'{plus_minus:.0f} plus/minus. Team struggled with them on the court - defense or chemistry issues.'
            })
        
        return analysis
    
    def generate_fantasy_outlook():
        """Fantasy için akıllı öneri oluşturur - İyileştirilmiş"""
        if is_single_game:
            # Tek maç için değerlendirme
            if score >= 60:
                return {
                    'rating': 'elite',
                    'title': '🔥 Historic Performance',
                    'text': f'{score:.1f} fantasy points is an absolute monster game. Generational performance that wins you the week.'
                }
            elif score >= 45:
                return {
                    'rating': 'elite',
                    'title': '⭐ Elite Production',
                    'text': f'{score:.1f} fantasy points is elite-tier output. When healthy and involved, this player can carry your team.'
                }
            elif score >= 35:
                return {
                    'rating': 'good',
                    'title': '✅ Strong Performance',
                    'text': f'{score:.1f} fantasy points is exactly what you want from a starter. Consistent production at this level makes them reliable.'
                }
            elif score >= 25:
                return {
                    'rating': 'good',
                    'title': '👍 Solid Contributor',
                    'text': f'{score:.1f} fantasy points is solid production. Dependable role player who provides steady value.'
                }
            elif score >= 18:
                return {
                    'rating': 'neutral',
                    'title': '⚖️ Decent Output',
                    'text': f'{score:.1f} fantasy points is acceptable. Streaming option or flex play in deeper leagues.'
                }
            elif score >= 10:
                return {
                    'rating': 'warning',
                    'title': '⚠️ Below Expectations',
                    'text': f'{score:.1f} fantasy points is underwhelming. Only valuable if this is an off-game and they typically produce more.'
                }
            else:
                return {
                    'rating': 'poor',
                    'title': '❌ Poor Output',
                    'text': f'Only {score:.1f} fantasy points. Not rosterable unless circumstances drastically change.'
                }
        else:
            # Sezon ortalaması için değerlendirme
            if score >= 50:
                return {
                    'rating': 'elite',
                    'title': '🏆 MVP Caliber',
                    'text': f'{score:.1f} FP per game over {games} games is MVP-level production. First round talent and centerpiece of any fantasy team.'
                }
            elif score >= 40:
                return {
                    'rating': 'elite',
                    'title': '🌟 All-Star Level',
                    'text': f'{score:.1f} FP per game is elite consistency. Top-20 player who delivers night in and night out.'
                }
            elif score >= 32:
                return {
                    'rating': 'good',
                    'title': '💪 High-End Starter',
                    'text': f'{score:.1f} FP average over {games} games is strong production. Reliable starter who rarely disappoints.'
                }
            elif score >= 25:
                return {
                    'rating': 'good',
                    'title': '✅ Solid Starter',
                    'text': f'{score:.1f} FP per game shows consistent value. Safe option who provides a stable floor with upside.'
                }
            elif score >= 18:
                return {
                    'rating': 'neutral',
                    'title': '🔄 Flex/Streamer',
                    'text': f'{score:.1f} FP average is useful in 12+ team leagues. Good for streaming or as injury replacement.'
                }
            elif score >= 12:
                return {
                    'rating': 'warning',
                    'title': '📉 Deep League Only',
                    'text': f'{score:.1f} FP average has limited appeal. Only relevant in 14+ team formats or desperate times.'
                }
            else:
                return {
                    'rating': 'poor',
                    'title': '🚫 Not Fantasy Relevant',
                    'text': f'{score:.1f} FP per game is not enough. Waiver wire fodder in all but the deepest leagues.'
                }

    # ======================================================
    # C. MINIMAL CSS - CLEAN DESIGN
    # ======================================================
    st.markdown("""
    <style>
    .player-image-container {
        width: 280px;
        height: 280px;
        display: flex;
        align-items: flex-end;
        justify-content: center;
        margin: 0 auto;
        position: relative;
        overflow: hidden;
    }

    .player-image {
        max-width: 100%;
        max-height: 100%;
        width: auto;
        height: auto;
        object-fit: contain;
        object-position: bottom center;
        display: block;
    }

    .big-player-name {
        font-size: 3.2rem;
        font-weight: 900;
        line-height: 1.1;
        margin-bottom: 8px;
    }

    .big-team-info {
        font-size: 1.4rem;
        font-weight: 500;
        color: #6c757d;
        margin-bottom: 10px;
    }

    .main-score { 
        font-size: 6.5rem; 
        font-weight: 900; 
        line-height: 1;
    }

    .score-label {
        font-size: 1.2rem;
        font-weight: 600;
        color: #868e96;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 8px;
    }

    .kpi-box { 
        text-align: center; 
        padding: 16px; 
        border-radius: 10px; 
        background: #f8f9fa;
        border: 2px solid #dee2e6;
    }

    .kpi-label { 
        font-size: 0.75rem; 
        color: #6c757d; 
        font-weight: 600; 
        text-transform: uppercase;
        margin-bottom: 4px;
    }

    .kpi-value { 
        font-size: 1.8rem; 
        font-weight: 800;
        margin-top: 4px;
    }

    .insight-box {
        padding: 16px;
        border-radius: 8px;
        margin: 12px 0;
        border-left: 4px solid;
    }

    .insight-positive {
        background: #d1fae5;
        border-color: #10b981;
    }

    .insight-negative {
        background: #fee2e2;
        border-color: #ef4444;
    }

    .insight-warning {
        background: #fef3c7;
        border-color: #f59e0b;
    }

    .insight-info {
        background: #dbeafe;
        border-color: #3b82f6;
    }

    .insight-title {
        font-weight: 700;
        font-size: 1rem;
        margin-bottom: 6px;
    }

    .insight-text {
        font-size: 0.9rem;
        line-height: 1.5;
    }

    @media (prefers-color-scheme: dark) {
        .big-team-info { color: #b0b0b0; }
        .score-label { color: #9ca3af; }
        .kpi-box { background: #1f2937; border-color: #374151; }
        .kpi-label { color: #9ca3af; }
        .insight-positive { background: #064e3b; border-color: #10b981; }
        .insight-negative { background: #7f1d1d; border-color: #ef4444; }
        .insight-warning { background: #78350f; border-color: #f59e0b; }
        .insight-info { background: #1e3a8a; border-color: #3b82f6; }
    }
    </style>
    """, unsafe_allow_html=True)

    # ======================================================
    # D. HEADER SECTION
    # ======================================================
    header_col1, header_col2, header_col3 = st.columns([1.5, 2, 1.2])
    
    with header_col1:
        st.markdown(f"""
            <div style='text-align: center;'>
                <img src='{player_img_url}' class='player-image' 
                     onerror="this.src='https://ui-avatars.com/api/?name={name.replace(' ', '+')}&size=400'">
            </div>
        """, unsafe_allow_html=True)
    
    with header_col2:
        st.markdown(f"""
            <div style='display: flex; flex-direction: column; justify-content: center; height: 100%;'>
                <div class='big-player-name'>{name}</div>
                <div class='big-team-info'>{team} {traded_info if traded_info else ''}</div>
            </div>
        """, unsafe_allow_html=True)
        
        if not is_single_game:
            st.caption(f"📊 Stats averaged over {games} games")
    
    with header_col3:
        st.markdown(f"""
            <div style='text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100%;'>
                <div class='main-score'>{int(score)}</div>
                <div class='score-label'>Fantasy Points</div>
            </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ======================================================
    # E. KEY METRICS
    # ======================================================
    k1, k2, k3, k4, k5 = st.columns(5)
    
    with k1:
        st.markdown(f"<div class='kpi-box'><div class='kpi-label'>FP / Min</div><div class='kpi-value'>{fp_min:.2f}</div></div>", unsafe_allow_html=True)
    
    with k2:
        st.markdown(f"<div class='kpi-box'><div class='kpi-label'>TS%</div><div class='kpi-value'>{ts_pct:.1f}%</div></div>", unsafe_allow_html=True)
    
    with k3:
        st.markdown(f"<div class='kpi-box'><div class='kpi-label'>Impact</div><div class='kpi-value'>{int(game_impact)}</div></div>", unsafe_allow_html=True)
    
    with k4:
        st.markdown(f"<div class='kpi-box'><div class='kpi-label'>AST/TO</div><div class='kpi-value'>{ast_to_ratio:.1f}</div></div>", unsafe_allow_html=True)
    
    with k5:
        st.markdown(f"<div class='kpi-box'><div class='kpi-label'>+/-</div><div class='kpi-value'>{plus_minus:+.0f}</div></div>", unsafe_allow_html=True)

    st.divider()

    # ======================================================
    # F. INTELLIGENT INSIGHTS
    # ======================================================
    
    col_left, col_right = st.columns([1.4, 1])
    
    with col_left:
        st.markdown("### 📊 Performance Analysis")
        
        insights = generate_performance_analysis()
        
        if insights:
            for insight in insights[:5]:  # En önemli 5 insight
                insight_type = insight['type']
                st.markdown(f"""
                <div class='insight-box insight-{insight_type}'>
                    <div class='insight-title'>{insight['title']}</div>
                    <div class='insight-text'>{insight['text']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Standard performance - no significant highlights.")
        
        # INJURY CONTEXT
        st.markdown("### 🩺 Team Context")
        all_injuries = get_injuries()
        team_injuries = [
            inj for inj in all_injuries 
            if inj.get("team", "").upper() == team_abbr.upper() and "Out" in inj.get("status", "")
        ]
        
        if team_injuries:
            missing_names = [inj.get('player', 'Unknown') for inj in team_injuries[:3]]
            st.warning(f"**{len(team_injuries)} teammates out:** {', '.join(missing_names)}")
            
            if fga >= 15 or usage_proxy >= 20:
                st.markdown("""
                <div class='insight-box insight-info'>
                    <div class='insight-title'>Elevated Opportunity</div>
                    <div class='insight-text'>Increased usage due to missing teammates. This workload may not be sustainable when the roster is healthy.</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ Team at full strength - role is established")

    with col_right:
        st.markdown("###  Box Score")
        
        # Clean stats display
        st.markdown(f"""
        **Scoring**
        - Points: **{pts:.1f}**
        - FG: {fgm:.1f}/{fga:.1f} ({fg_pct:.1f}%)
        - 3PT: {three_pm:.1f}/{three_pa:.1f} ({three_pct:.1f}%)
        - FT: {ftm:.1f}/{fta:.1f} ({ft_pct:.1f}%)
        
        **Other Stats**
        - Rebounds: **{reb:.1f}**
        - Assists: **{ast:.1f}**
        - Steals: **{stl:.1f}**
        - Blocks: **{blk:.1f}**
        - Turnovers: **{to:.1f}**
        
        **Time & Impact**
        - Minutes: **{mins:.0f}**
        - Plus/Minus: **{plus_minus:+.1f}**
        """)
        
        st.markdown("---")
        
        st.markdown("### 🔮 Fantasy Outlook")
        
        outlook = generate_fantasy_outlook()
        
        if outlook['rating'] == 'elite':
            st.success(f"**{outlook['title']}**\n\n{outlook['text']}")
        elif outlook['rating'] == 'good':
            st.info(f"**{outlook['title']}**\n\n{outlook['text']}")
        elif outlook['rating'] == 'neutral':
            st.warning(f"**{outlook['title']}**\n\n{outlook['text']}")
        else:
            st.error(f"**{outlook['title']}**\n\n{outlook['text']}")


# =================================================================
# 3. MAIN TABLE FUNCTION
# =================================================================

def render_tables(today_df, weights, default_period="Today"):
    """
    Renders the main table.
    Uses different data sources based on period selection (Today, Season, Week).
    """
    
    # Initialize Session State
    if "stats_period" not in st.session_state:
        st.session_state.stats_period = default_period
        
    # --- PERIOD SELECTION BUTTONS ---
    st.markdown("### Time Period")
    cols = st.columns(4)
    periods = ["Today", "This Week", "This Month", "Season"]
    
    for i, p in enumerate(periods):
        style = "primary" if st.session_state.stats_period == p else "secondary"
        if cols[i].button(p, key=f"btn_{p}", type=style, use_container_width=True):
            st.session_state.stats_period = p
            st.rerun()
            
    current_period = st.session_state.stats_period
    active_df = pd.DataFrame()
    
    # =================================================================
    # DATA PREPARATION (DATA FETCHING STRATEGY)
    # =================================================================
    
    # --- CASE 1: SEASON (Official API - Single Request) ---
    if current_period == "Season":
        with st.spinner("Fetching official NBA Season Leaders..."):
            # 2026 Season (2025-26)
            season_df = get_nba_season_stats_official(season_year=2026)
            
            if not season_df.empty:
                # Calculate Fantasy Score
                season_df["USER_SCORE"] = season_df.apply(lambda x: calculate_fantasy_score(x, weights), axis=1)
                
                # Store and format MIN value
                season_df["MIN_INT"] = season_df["MIN"] # Numeric copy
                season_df["MIN"] = season_df["MIN"].apply(lambda x: f"{x:.1f}")
                
                # Check and fix +/- value
                if "+/-" in season_df.columns:
                    season_df["+/-"] = pd.to_numeric(season_df["+/-"], errors='coerce').fillna(0)
                else:
                    season_df["+/-"] = 0.0
                
                # Convert shooting percentages to string format
                season_df["FG"] = season_df.apply(lambda x: f"{x['FGM']:.1f}/{x['FGA']:.1f}", axis=1)
                season_df["3PT"] = season_df.apply(lambda x: f"{x['3Pts']:.1f}/{x['3PTA']:.1f}", axis=1)
                season_df["FT"] = season_df.apply(lambda x: f"{x['FTM']:.1f}/{x['FTA']:.1f}", axis=1)
                
                # IMPORTANT: Fetch current roster info and match
                try:
                    current_rosters = get_current_team_rosters()
                    
                    # Create normalized roster dictionary
                    normalized_rosters = {}
                    for player_name, info in current_rosters.items():
                        norm_name = normalize_player_name(player_name)
                        
                        # info check: dict or str
                        if isinstance(info, dict):
                            team_code = info.get('team')
                            p_id = info.get('id')
                        else:
                            team_code = info
                            p_id = None
                            
                        normalized_rosters[norm_name] = {
                            'team': team_code,
                            'id': p_id, # Store ID
                            'original_name': player_name
                        }
                    
                    # Match each player with roster to update TEAM and PLAYER_ID
                    def update_player_info(row):
                        player_name = row.get('PLAYER', '')
                        norm_name = normalize_player_name(player_name)
                        roster_info = normalized_rosters.get(norm_name)
                        
                        current_team = row.get('TEAM', 'FA') # Default
                        p_id = None
                        
                        if roster_info:
                            current_team = roster_info['team']
                            p_id = roster_info['id']
                        
                        return pd.Series([current_team, p_id])
                    
                    # Update TEAM and PLAYER_ID columns at once
                    season_df[['TEAM', 'PLAYER_ID']] = season_df.apply(update_player_info, axis=1)
                    
                    print(f"✓ {len(season_df)} player team and ID info updated")
                    
                except Exception as e:
                    print(f"⚠️ Error in roster matching: {e}")
                    if 'TEAM' not in season_df.columns:
                        season_df['TEAM'] = 'UNK'
                    season_df['PLAYER_ID'] = None # Pass empty on error
                
                # Add DATE column for MVP/LVP
                season_start = datetime(2025, 10, 22)
                season_df["DATE"] = season_start
                
                active_df = season_df.copy()
                
                # Create daily format data for MVP/LVP widget (Simulation)
                mvp_df = season_df.copy()
                if 'GAMES' in mvp_df.columns or 'GP' in mvp_df.columns:
                    gp_col = 'GAMES' if 'GAMES' in mvp_df.columns else 'GP'
                    
                    expanded_rows = []
                    for _, player_row in mvp_df.iterrows():
                        games_played = int(player_row[gp_col])
                        if games_played == 0: continue
                        
                        for game_num in range(min(games_played, 82)):
                            game_date = season_start + timedelta(days=game_num * 2)
                            
                            # Create dict instead of copying row (for performance)
                            game_row = player_row.to_dict()
                            game_row['DATE'] = game_date
                            expanded_rows.append(game_row)
                    
                    if expanded_rows:
                        period_df = pd.DataFrame(expanded_rows)
                        period_df['DATE'] = pd.to_datetime(period_df['DATE'])
                        st.session_state["period_df"] = period_df
                    else:
                        st.session_state["period_df"] = pd.DataFrame()
                else:
                    st.session_state["period_df"] = season_df.copy()

    # --- CASE 2: TODAY (Live Data) ---
    elif current_period == "Today":
        active_df = today_df.copy()
        if not active_df.empty:
            active_df["USER_SCORE"] = active_df.apply(lambda x: calculate_fantasy_score(x, weights), axis=1)
            active_df["DATE"] = datetime.now().date()
            
            if "MIN_INT" not in active_df.columns:
                active_df["MIN_INT"] = active_df["MIN"].apply(parse_minutes)
            
            # Today ID adding logic (If not in today_df)
            if "PLAYER_ID" not in active_df.columns:
                # Simple roster matching
                try:
                    current_rosters = get_current_team_rosters()
                    normalized_rosters = {normalize_player_name(k): v for k, v in current_rosters.items()}
                    
                    def get_id_today(name):
                        norm = normalize_player_name(name)
                        info = normalized_rosters.get(norm)
                        if isinstance(info, dict):
                            return info.get('id')
                        return None
                        
                    active_df["PLAYER_ID"] = active_df["PLAYER"].apply(get_id_today)
                except:
                    active_df["PLAYER_ID"] = None

            st.session_state["period_df"] = active_df.copy()

    # --- CASE 3: WEEKLY / MONTHLY (Historical Game Collection) ---
    else:
        start_date, end_date = get_date_range(current_period)
        with st.spinner(f"Fetching stats for {current_period}..."):
            historical_data = get_historical_boxscores(start_date, end_date)
            
            if historical_data:
                # 1. Aggregate Data for Table (ID is added here)
                active_df = aggregate_player_stats(historical_data, weights)
                
                # 2. Daily Data for Charts
                all_daily_records = []
                for game_day in historical_data:
                    game_date = game_day.get('date')
                    players = game_day.get('players', [])
                    for player in players:
                        try:
                            rec = player.copy()
                            rec['DATE'] = pd.to_datetime(game_date) if game_date else pd.Timestamp.now()
                            
                            numeric_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'FGM', 'FGA', '3Pts', 'FTM', 'FTA']
                            for stat in numeric_stats:
                                rec[stat] = float(player.get(stat, 0))
                            
                            rec['MIN'] = parse_minutes(player.get('MIN', 0))
                            if not rec.get('PLAYER'): continue
                            
                            all_daily_records.append(rec)
                        except Exception:
                            continue
                
                if all_daily_records:
                    daily_df = pd.DataFrame(all_daily_records)
                    daily_df["USER_SCORE"] = daily_df.apply(lambda x: calculate_fantasy_score(x, weights), axis=1)
                    st.session_state["period_df"] = daily_df
                else:
                    st.session_state["period_df"] = pd.DataFrame()

    # --- DATA CHECK ---
    if active_df.empty:
        st.warning(f"No data available for {current_period}")
        return

    # --- TABLE FORMATTING SETTINGS ---
    if "USER_SCORE" in active_df.columns:
        active_df["USER_SCORE"] = active_df["USER_SCORE"].astype(float).round(2)
    
    if "+/-" in active_df.columns:
         active_df["+/-"] = pd.to_numeric(active_df["+/-"], errors='coerce').fillna(0)

    is_today = (current_period == "Today")
    stat_fmt = "%d" if is_today else "%.1f"
    
    stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "+/-"]
    for col in stat_cols:
        if col in active_df.columns:
            if is_today:
                active_df[col] = active_df[col].fillna(0).astype(int)
            else:
                active_df[col] = active_df[col].astype(float).round(1)

    column_order = ["PLAYER", "TEAM", "USER_SCORE", "MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "STL", "BLK", "TO", "+/-"]
    
    if not is_today:
        column_order.insert(2, "GAMES")
        if "GP" in active_df.columns:
            active_df = active_df.rename(columns={"GP": "GAMES"})
        
    available_cols = [c for c in column_order if c in active_df.columns]

    col_config = {
        "PLAYER": st.column_config.TextColumn("Player", width="medium"),
        "TEAM": st.column_config.TextColumn("Team", width="small"),
        "GAMES": st.column_config.NumberColumn("GP", format="%d", width="small"),
        "USER_SCORE": st.column_config.NumberColumn("Score", format="%.2f", width="small"),
        "MIN": st.column_config.TextColumn("Min", width="small"),
        "PTS": st.column_config.NumberColumn("PTS", format=stat_fmt, width="small"),
        "REB": st.column_config.NumberColumn("REB", format=stat_fmt, width="small"),
        "AST": st.column_config.NumberColumn("AST", format=stat_fmt, width="small"),
        "STL": st.column_config.NumberColumn("STL", format=stat_fmt, width="small"),
        "BLK": st.column_config.NumberColumn("BLK", format=stat_fmt, width="small"),
        "TO": st.column_config.NumberColumn("TO", format=stat_fmt, width="small"),
        "+/-": st.column_config.NumberColumn("+/-", format=stat_fmt, width="small"),
    }

    st.markdown("---")
    st.caption("💡 **Tip:** Click on a player row to see **Context & Injury Analysis**.")

    # --- 1. TOP 10 PERFORMANCES ---
    st.markdown(f"## Top 10 Performances ({current_period})")
    top_df = active_df.sort_values("USER_SCORE", ascending=False).head(10)
    
    event_top = st.dataframe(
        top_df[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        height=380,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    if len(event_top.selection.rows) > 0:
        selected_index = event_top.selection.rows[0]
        selected_row = top_df.iloc[selected_index]
        show_player_analysis(selected_row, weights)

    # --- 2. LOWEST 10 PERFORMANCES ---
    st.markdown(f"## Lowest 10 Performances ({current_period})")
    
    min_minutes = 20 if not is_today else 15
    if "MIN_INT" in active_df.columns:
        filtered_low = active_df[active_df["MIN_INT"] >= min_minutes]
        if len(filtered_low) < 5: 
            filtered_low = active_df[active_df["MIN_INT"] >= 5]
    else:
        filtered_low = active_df

    low_df = filtered_low.sort_values("USER_SCORE", ascending=True).head(10)
    
    event_low = st.dataframe(
        low_df[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        height=380,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(event_low.selection.rows) > 0:
        selected_index = event_low.selection.rows[0]
        selected_row = low_df.iloc[selected_index]
        show_player_analysis(selected_row, weights)

    # --- 3. FULL LIST (EXPANDER) ---
    with st.expander(f" Full Player List ({len(active_df)} players)"):
        full_sorted_df = active_df.sort_values("USER_SCORE", ascending=False).reset_index(drop=True)
        full_sorted_df.insert(0, '#', full_sorted_df.index + 1)
        cols_with_rank = ['#'] + available_cols
        full_col_config = col_config.copy()
        full_col_config['#'] = st.column_config.NumberColumn("#", format="%d", width="40px")

        st.dataframe(
            full_sorted_df[cols_with_rank], 
            use_container_width=True, 
            hide_index=True, 
            column_config=full_col_config
        )