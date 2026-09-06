"""
Yahoo Fantasy Sports API Service
OAuth 2.0 Authentication ve League Data Fetching
"""

import requests
from requests_oauthlib import OAuth2Session
import json
from typing import Dict, List, Optional
import pandas as pd

class YahooFantasyService:
    """Yahoo Fantasy Sports API entegrasyonu"""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = 'oob'):
        """
        Yahoo Fantasy API servisi başlatır
        
        Args:
            client_id: Yahoo Developer Console'dan alınan Client ID
            client_secret: Yahoo Developer Console'dan alınan Client Secret
            redirect_uri: OAuth callback URI (default: 'oob' for out-of-band)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://fantasysports.yahooapis.com/fantasy/v2"
        self.oauth = None
        self.token = None
        
        # OAuth endpoints
        self.authorization_base_url = 'https://api.login.yahoo.com/oauth2/request_auth'
        self.token_url = 'https://api.login.yahoo.com/oauth2/get_token'
    
    def get_authorization_url(self) -> str:
        """OAuth authorization URL'ini döndürür"""
        self.oauth = OAuth2Session(self.client_id, redirect_uri=self.redirect_uri)
        authorization_url, state = self.oauth.authorization_url(self.authorization_base_url)
        return authorization_url
    
    def fetch_token(self, code: str) -> Dict:
        """
        Authorization code ile access token alır
        
        Args:
            code: Kullanıcının girdiği authorization code (Sadece kod stringi)
        """
        self.oauth = OAuth2Session(self.client_id, redirect_uri=self.redirect_uri)
        
        # authorization_response yerine code parametresini kullanıyoruz
        self.token = self.oauth.fetch_token(
            self.token_url,
            code=code, 
            client_secret=self.client_secret
        )
        return self.token
    
    def set_token(self, token: Dict):
        """Önceden kaydedilmiş token'ı set eder"""
        self.token = token
        self.oauth = OAuth2Session(self.client_id, token=token)
    
    def _make_request(self, endpoint: str) -> Dict:
        """
        Yahoo Fantasy API'sine request gönderir
        """
        if not self.oauth or not self.token:
            raise Exception("OAuth token bulunamadı. Önce authenticate olun.")
        
        # URL'i oluştur
        url = f"{self.base_url}/{endpoint}"
        
        # Yahoo'yu JSON formatına zorlamak için '?format=json' ekle
        if '?' in url:
            url += "&format=json"
        else:
            url += "?format=json"
            
        headers = {'Accept': 'application/json'}
        
        print(f"Requesting: {url}") # Terminalde URL'i görmek için
        
        response = self.oauth.get(url, headers=headers)
        
        # Eğer hata varsa (400, 401, 500 vs.)
        if response.status_code != 200:
            print(f"API Error Status: {response.status_code}")
            print(f"API Error Body: {response.text}")
            
            # Token süresi dolmuş olabilir
            if response.status_code == 401:
                raise Exception("Token expired. Lütfen 'yahoo_token.json' dosyasını silip tekrar giriş yapın.")
            
            raise Exception(f"Yahoo API Error: {response.status_code} - {response.text}")
        
        # JSON parse etmeyi dene
        try:
            return response.json()
        except json.JSONDecodeError:
            print("JSON Decode Error. Raw Response:")
            print(response.text)
            raise Exception("Yahoo API JSON döndürmedi. Terminali kontrol edin.")
    
    def get_user_leagues(self, game_key: str = 'nba') -> List[Dict]:
        """
        Kullanıcının liglerini getirir
        
        Args:
            game_key: Spor türü (nba, nfl, mlb, nhl)
        """
        endpoint = f"users;use_login=1/games;game_keys={game_key}/leagues"
        data = self._make_request(endpoint)
        
        leagues = []
        try:
            leagues_data = data['fantasy_content']['users']['0']['user'][1]['games']['0']['game'][1]['leagues']
            
            for key in leagues_data:
                if key == 'count':
                    continue
                league = leagues_data[key]['league'][0]
                leagues.append({
                    'league_id': league['league_id'],
                    'league_key': league['league_key'],
                    'name': league['name'],
                    'num_teams': league['num_teams'],
                    'scoring_type': league['scoring_type'],
                    'season': league['season']
                })
        except (KeyError, IndexError) as e:
            print(f"Error parsing leagues: {e}")
        
        return leagues
    
    def get_league_standings(self, league_key: str) -> pd.DataFrame:
        """Lig sıralamasını getirir (Düzeltilmiş Versiyon)"""
        endpoint = f"league/{league_key}/standings"
        data = self._make_request(endpoint)
        
        teams = []
        try:
            # Standings yapısını güvenli şekilde al
            league_data = data['fantasy_content']['league']
            # League listesinden standings içeren dictionary'i bul
            standings_wrapper = next((x for x in league_data if isinstance(x, dict) and 'standings' in x), None)
            
            if not standings_wrapper:
                print("Standings verisi JSON içinde bulunamadı.")
                return pd.DataFrame()

            standings = standings_wrapper['standings'][0]['teams']
            
            for key in standings:
                if key == 'count': continue
                
                # Takım verisi bir liste olarak gelir: [[metadata], {stats}, ...]
                team_payload = standings[key]['team']
                
                # 1. Metadata'yı bul (Genellikle listenin ilk elemanı)
                team_metadata = team_payload[0]
                
                # 2. 'team_standings' içeren dictionary'i bul
                stats_payload = next((item for item in team_payload if isinstance(item, dict) and 'team_standings' in item), None)
                
                if not stats_payload:
                    print(f"{key} id'li takım için istatistik bulunamadı.")
                    continue

                ts = stats_payload['team_standings']
                totals = ts.get('outcome_totals', {})
                
                # Managers bilgisini güvenli çek
                manager_name = "Unknown"
                try:
                    # Managers verisi metadata içinde derinlerde olabilir
                    managers_payload = next((item for item in team_payload if isinstance(item, dict) and 'managers' in item), None)
                    if not managers_payload:
                        # Bazen en sonda ayrı bir obje olarak gelir, bazen metadata'nın içinde [19] gibi indekslerdedir
                        # Basit bir fallback yapalım
                        manager_name = team_metadata[2]['name'] # Takım adını kullan
                except:
                    pass

                teams.append({
                    'Rank': ts.get('rank', 0),
                    'Team': team_metadata[2]['name'],
                    # 'Manager': manager_name, # Şimdilik karmaşıklığı azaltmak için kapattım
                    'Wins': totals.get('wins', 0),
                    'Losses': totals.get('losses', 0),
                    'Ties': totals.get('ties', 0),
                    'Win%': totals.get('percentage', '0'),
                    'GB': ts.get('games_back', '-'),
                    'Points For': ts.get('points_for', 0),
                    'Points Against': ts.get('points_against', 0)
                })
                
        except Exception as e:
            print(f"Error parsing standings: {e}")
            # Hata ayıklama için ham veriyi bas (terminalden kontrol edebilirsin)
            import json
            # print(json.dumps(data, indent=2))
        
        return pd.DataFrame(teams)
    
    def get_league_matchups(self, league_key: str, week: Optional[int] = None) -> List[Dict]:
        """Haftalık maç eşleşmelerini getirir (Düzeltilmiş Versiyon)"""
        if week:
            endpoint = f"league/{league_key}/scoreboard;week={week}"
        else:
            endpoint = f"league/{league_key}/scoreboard"
        
        data = self._make_request(endpoint)
        
        matchups = []
        try:
            league_data = data['fantasy_content']['league']
            # Scoreboard'u bul
            scoreboard_wrapper = next((x for x in league_data if isinstance(x, dict) and 'scoreboard' in x), None)
            
            if not scoreboard_wrapper or 'matchups' not in scoreboard_wrapper['scoreboard']['0']:
                print("Matchups verisi bulunamadı veya hafta henüz başlamadı.")
                return []

            scoreboard = scoreboard_wrapper['scoreboard']['0']['matchups']
            
            for key in scoreboard:
                if key == 'count': continue
                
                matchup_root = scoreboard[key]['matchup']
                
                # '0' anahtarı içinde teams var mı kontrol et
                if '0' not in matchup_root or 'teams' not in matchup_root['0']:
                    continue
                    
                teams_data = matchup_root['0']['teams']
                
                # Team 1 (Away) ve Team 2 (Home) verilerini işle
                # Yahoo'da takımlar '0' ve '1' anahtarları altındadır
                parsed_teams = []
                
                for t_key in ['0', '1']:
                    raw_team = teams_data[t_key]['team']
                    
                    # Metadata (isim, key vb.)
                    t_meta = raw_team[0]
                    
                    # Puanlar ve İstatistikler
                    # Listede 'team_points' anahtarına sahip olan sözlüğü bul
                    t_points_data = next((item for item in raw_team if isinstance(item, dict) and 'team_points' in item), None)
                    t_stats_data = next((item for item in raw_team if isinstance(item, dict) and 'team_stats' in item), None)
                    
                    total_points = t_points_data['team_points']['total'] if t_points_data else 0
                    stats = self._parse_team_stats(t_stats_data) if t_stats_data else {}
                    
                    parsed_teams.append({
                        'name': t_meta[2]['name'],
                        'team_key': t_meta[0]['team_key'],
                        'stats': stats,
                        'score': float(total_points),
                        'games': stats.get('GP', 0)
                    })
                
                matchups.append({
                    'week': matchup_root.get('week', week),
                    'away_team': {
                        'name': parsed_teams[0]['name'],
                        'team_key': parsed_teams[0]['team_key'],
                        'stats': parsed_teams[0]['stats'],
                        'weekly_games': parsed_teams[0]['games']
                    },
                    'away_score': parsed_teams[0]['score'],
                    'home_team': {
                        'name': parsed_teams[1]['name'],
                        'team_key': parsed_teams[1]['team_key'],
                        'stats': parsed_teams[1]['stats'],
                        'weekly_games': parsed_teams[1]['games']
                    },
                    'home_score': parsed_teams[1]['score']
                })
                
        except Exception as e:
            print(f"Error parsing matchups: {e}")
            # Hata durumunda yapıyı görmek için açabilirsin:
            # import json
            # print(json.dumps(data, indent=2))
        
        return matchups
    
    def _parse_team_stats(self, stats_data: Dict) -> Dict:
        """Yahoo stats verilerini parse eder (Hem Team hem Player için Universal)"""
        stats = {}
        
        try:
            # 1. Veri 'team_stats' veya 'player_stats' içinde mi diye kontrol et
            if 'team_stats' in stats_data:
                stats_payload = stats_data['team_stats']
            elif 'player_stats' in stats_data:
                stats_payload = stats_data['player_stats']
            else:
                stats_payload = stats_data
                
            # 2. Stats listesini al
            stat_list = stats_payload.get('stats', [])
            
            # Eğer stat_list hala yoksa ve payload'ın kendisi listeyse
            if not stat_list and isinstance(stats_payload, list):
                stat_list = stats_payload

            # Yahoo Stat ID Mapping
            stat_map = {
                '5': 'FG%',      # Field Goal Percentage
                '8': 'FT%',      # Free Throw Percentage
                '10': '3PTM',    # 3-Point Shots Made
                '12': 'PTS',     # Points
                '15': 'REB',     # Total Rebounds
                '16': 'AST',     # Assists
                '17': 'ST',      # Steals
                '18': 'BLK',     # Blocked Shots
                '19': 'TO',      # Turnovers
                '0': 'GP'        # Games Played
            }
            
            for stat in stat_list:
                curr_stat = stat.get('stat', stat)
                stat_id = str(curr_stat.get('stat_id'))
                val_str = str(curr_stat.get('value', '0'))
                
                # Canlı maç işaretlerini temizle
                val_str = val_str.replace('*', '').strip()

                if stat_id in stat_map:
                    stat_name = stat_map[stat_id]
                    final_val = 0.0
                    
                    try:
                        if val_str == '-' or val_str == '':
                            final_val = 0.0
                        elif '/' in val_str:
                            parts = val_str.split('/')
                            if len(parts) == 2:
                                num = float(parts[0])
                                denom = float(parts[1])
                                final_val = (num / denom) if denom > 0 else 0.0
                        else:
                            final_val = float(val_str)
                    except (ValueError, TypeError):
                        final_val = 0.0
                    
                    stats[stat_name] = final_val

        except Exception as e:
            print(f"Error parsing stats details: {e}")
        
        return stats
        
        return stats
    def get_team_roster(self, team_key: str) -> List[Dict]:
        """
        Takım kadrosunu getirir
        
        Args:
            team_key: Yahoo team key
        """
        endpoint = f"team/{team_key}/roster"
        data = self._make_request(endpoint)
        
        players = []
        try:
            roster = data['fantasy_content']['team'][1]['roster']['0']['players']
            
            for key in roster:
                if key == 'count':
                    continue
                
                player = roster[key]['player'][0]
                
                players.append({
                    'name': player[2]['name']['full'],
                    'position': player[9]['display_position'],
                    'team': player[6]['editorial_team_abbr'],
                    'status': player.get(13, {}).get('status', 'Active') if len(player) > 13 else 'Active'
                })
        except (KeyError, IndexError) as e:
            print(f"Error parsing roster: {e}")
        
        return players
    

    # ... (YahooFantasyService sınıfının devamı) ...

    def get_league_rosters(self, league_key: str) -> Dict:
        """
        Ligdeki tüm takımların kadrolarını getirir (Robust/Sağlamlaştırılmış Versiyon).
        """
        endpoint = f"league/{league_key}/teams;out=roster"
        data = self._make_request(endpoint)
        
        rosters = {}
        
        try:
            # League datasına ulaş
            league_data = data['fantasy_content']['league']
            
            # 'teams' anahtarını içeren dictionary'i dinamik olarak bul
            teams_wrapper = next((x for x in league_data if isinstance(x, dict) and 'teams' in x), None)
            
            if not teams_wrapper:
                print("API Yanıtında 'teams' verisi bulunamadı.")
                return {}
            
            league_teams = teams_wrapper['teams']
            
            for key in league_teams:
                if key == 'count': continue
                
                # Takım verisi [metadata, roster, ...] şeklinde gelir
                team_payload = league_teams[key]['team']
                
                # 1. Takım Metadata'sını bul (İsim, Key)
                # Genellikle listenin ilk elemanıdır ama garantiye alalım
                team_meta = team_payload[0]
                # Bazen metadata doğrudan dict olabilir, bazen liste içinde
                # Yahoo genelde: [ {team_key...}, {team_id...}, {name...} ] gönderir
                
                # İsim verisini güvenli çekelim
                team_name = "Unknown Team"
                team_key = ""
                
                # Metadata içindeki 'name' alanını bulmaya çalış
                if isinstance(team_meta, list):
                     for meta_item in team_meta:
                         if isinstance(meta_item, dict) and 'name' in meta_item:
                             team_name = meta_item['name']
                         if isinstance(meta_item, dict) and 'team_key' in meta_item:
                             team_key = meta_item['team_key']
                
                # Eğer yukarıdaki döngü bulamazsa standart indeksi dene
                if team_name == "Unknown Team" and len(team_meta) > 2:
                     try:
                         team_name = team_meta[2]['name']
                         team_key = team_meta[0]['team_key']
                     except: pass
                
                # 2. Roster'ı bul
                roster_wrapper = next((x for x in team_payload if isinstance(x, dict) and 'roster' in x), None)
                
                players = []
                if roster_wrapper:
                    roster_data = roster_wrapper['roster']['0']['players']
                    
                    for p_key in roster_data:
                        if p_key == 'count': continue
                        
                        p_payload = roster_data[p_key]['player']
                        p_meta = p_payload[0] # Oyuncu metadata'sı
                        
                        # Oyuncu ismini bul
                        full_name = "Unknown Player"
                        display_pos = "-"
                        player_key = ""
                        
                        # Metadata listesinde gezin
                        for item in p_meta:
                            if isinstance(item, dict):
                                if 'name' in item:
                                    full_name = item['name']['full']
                                if 'display_position' in item:
                                    display_pos = item['display_position']
                                if 'player_key' in item:
                                    player_key = item['player_key']
                                    
                        players.append({
                            'player_key': player_key,
                            'name': full_name,
                            'position': display_pos
                        })
                
                rosters[team_name] = {'team_key': team_key, 'players': players}
                
        except Exception as e:
            print(f"Error fetching rosters: {e}")
            # Hata ayıklama için JSON yapısını görmek istersen:
            # import json
            # print(json.dumps(data, indent=2))
            
        return rosters

    def get_players_stats(self, league_key: str, player_keys: List[str]) -> List[Dict]:
        """
        Seçilen oyuncuların sezon ortalamalarını (Average Stats) getirir.
        Trade analizi için kullanılır.
        """
        if not player_keys:
            return []
            
        keys_str = ",".join(player_keys)
        # Oyuncuların sezonluk ortalama istatistiklerini (stats=season) isteyelim
        endpoint = f"league/{league_key}/players;player_keys={keys_str}/stats;type=season"
        
        data = self._make_request(endpoint)
        players_stats = []
        
        try:
            # players verisi league altında döner
            league_data = data['fantasy_content']['league']
            
            # 'players' wrapper'ını bul
            players_wrapper_parent = next((item for item in league_data if isinstance(item, dict) and 'players' in item), None)
            
            if not players_wrapper_parent:
                print("Player data wrapper not found.")
                return []
                
            players_wrapper = players_wrapper_parent['players']
            
            for key in players_wrapper:
                if key == 'count': continue
                
                # Player verisi: [ {metadata}, {player_stats}, ... ]
                p_payload = players_wrapper[key]['player']
                
                # 1. Metadata bul (İsim için)
                meta_item = p_payload[0]
                full_name = "Unknown"
                if isinstance(meta_item, list):
                    for m in meta_item:
                         if isinstance(m, dict) and 'name' in m:
                             full_name = m['name']['full']
                
                # 2. İstatistik Wrapper'ını bul ('player_stats' içeren dict)
                stats_data = next((item for item in p_payload if isinstance(item, dict) and 'player_stats' in item), None)
                
                if not stats_data:
                    # Bazen doğrudan 'stats' listesi olarak gelebilir mi? Kontrol edelim
                    print(f"No stats found for {full_name}")
                    parsed_stats = {}
                else:
                    # Parse fonksiyonuna 'player_stats' wrapper'ını gönder
                    parsed_stats = self._parse_team_stats(stats_data)
                
                players_stats.append({
                    'name': full_name,
                    'stats': parsed_stats
                })
                
        except Exception as e:
            print(f"Error fetching player stats: {e}")
            # import json
            # print(json.dumps(data, indent=2))
            
        return players_stats


# ============================
# STREAMLIT INTEGRATION HELPER
# ============================

def save_yahoo_token(token: Dict, filename: str = 'yahoo_token.json'):
    """Yahoo OAuth token'ı dosyaya kaydeder"""
    with open(filename, 'w') as f:
        json.dump(token, f)

def load_yahoo_token(filename: str = 'yahoo_token.json') -> Optional[Dict]:
    """Kaydedilmiş Yahoo token'ı yükler"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None