"""
ESPN API'den gelen ham JSON yanıtını gösterir
Kullanım: python view_api_response.py
"""

import requests
import json
from datetime import datetime, timedelta

def get_recent_game_id():
    """Son maçın ID'sini bulur"""
    date = datetime.now()
    for _ in range(7):
        date_str = date.strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        try:
            data = requests.get(url, timeout=10).json()
            events = data.get("events", [])
            if events:
                return events[0]["id"], date_str
            date -= timedelta(days=1)
        except:
            date -= timedelta(days=1)
    return None, None

def view_raw_boxscore(game_id):
    """Bir maçın ham boxscore JSON'ını gösterir"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    
    print(f"\n{'='*100}")
    print(f"📡 API REQUEST")
    print(f"{'='*100}")
    print(f"URL: {url}")
    print(f"Game ID: {game_id}\n")
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        print(f"{'='*100}")
        print(f"📊 RESPONSE STRUCTURE")
        print(f"{'='*100}")
        print(f"Status Code: {response.status_code}")
        print(f"Top Level Keys: {list(data.keys())}\n")
        
        # Maç bilgisi
        if "header" in data:
            header = data["header"]
            competitions = header.get("competitions", [{}])[0]
            competitors = competitions.get("competitors", [])
            
            print(f"{'='*100}")
            print(f"🏀 GAME INFO")
            print(f"{'='*100}")
            for comp in competitors:
                team = comp.get("team", {})
                print(f"{team.get('abbreviation', 'N/A'):4s} - {team.get('displayName', 'N/A')}")
            print()
        
        # Boxscore yapısı
        if "boxscore" not in data:
            print("❌ Boxscore bulunamadı!")
            return
        
        boxscore = data["boxscore"]
        print(f"{'='*100}")
        print(f"📦 BOXSCORE STRUCTURE")
        print(f"{'='*100}")
        print(f"Boxscore Keys: {list(boxscore.keys())}")
        print(f"Teams Count: {len(boxscore.get('players', []))}\n")
        
        # Her takım için oyuncular
        for team_idx, team_data in enumerate(boxscore.get("players", [])):
            team_info = team_data.get("team", {})
            print(f"{'='*100}")
            print(f"TEAM {team_idx + 1}: {team_info.get('displayName', 'Unknown')} ({team_info.get('abbreviation', 'N/A')})")
            print(f"{'='*100}")
            
            statistics = team_data.get("statistics", [])
            print(f"Statistics Groups: {len(statistics)}\n")
            
            for stat_group in statistics:
                print(f"  📊 Stat Group: {stat_group.get('name', 'Unknown')}")
                print(f"  Labels: {stat_group.get('labels', [])}")
                
                athletes = stat_group.get("athletes", [])
                print(f"  Athletes: {len(athletes)}\n")
                
                # İlk 3 oyuncuyu göster
                for i, athlete_data in enumerate(athletes[:3]):
                    athlete = athlete_data.get("athlete", {})
                    stats = athlete_data.get("stats", [])
                    
                    print(f"    Player {i+1}: {athlete.get('displayName', 'N/A')}")
                    print(f"    Stats Array: {stats}")
                    
                    # Labels ile eşleştir
                    labels = stat_group.get('labels', [])
                    if labels and stats:
                        stat_dict = dict(zip(labels, stats))
                        print(f"    Parsed Stats: {json.dumps(stat_dict, indent=6)}")
                    print()
                
                # ZACH EDEY'İ ÖZEL OLARAK ARA
                for athlete_data in athletes:
                    athlete = athlete_data.get("athlete", {})
                    player_name = athlete.get('displayName', '')
                    
                    if 'edey' in player_name.lower():
                        print(f"\n{'🎯'*40}")
                        print(f"FOUND: {player_name}")
                        print(f"{'🎯'*40}")
                        
                        stats = athlete_data.get("stats", [])
                        labels = stat_group.get('labels', [])
                        
                        print(f"\n📋 RAW DATA:")
                        print(f"   Athlete Object: {json.dumps(athlete, indent=4)}")
                        print(f"\n   Stats Array: {stats}")
                        print(f"   Labels: {labels}")
                        
                        if labels and stats:
                            stat_dict = dict(zip(labels, stats))
                            print(f"\n📊 PARSED STATS:")
                            for key, val in stat_dict.items():
                                print(f"   {key:15s}: {val}")
                        
                        print(f"\n{'🎯'*40}\n")
                
                print(f"  {'-'*96}\n")
        
        # Tüm JSON'ı dosyaya kaydet (opsiyonel)
        save = input("\n💾 Tüm JSON'ı dosyaya kaydetmek ister misiniz? (y/n): ")
        if save.lower() == 'y':
            filename = f"game_{game_id}_raw.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Kaydedildi: {filename}")
        
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()

def find_edey_games(days=30):
    """Zach Edey'in oynadığı son maçları bulur"""
    print(f"\n{'='*100}")
    print(f"🔍 ZACH EDEY MAÇ ARAMA (Son {days} gün)")
    print(f"{'='*100}\n")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Memphis Grizzlies maçlarını ara (Zach Edey MEM'de oynuyor)
    current_date = start_date
    mem_games = []
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        
        try:
            data = requests.get(url, timeout=10).json()
            for event in data.get("events", []):
                comp = event["competitions"][0]
                competitors = comp.get("competitors", [])
                
                # Memphis maçı mı kontrol et
                for team in competitors:
                    if team["team"]["abbreviation"] == "MEM":
                        mem_games.append({
                            'game_id': event["id"],
                            'date': current_date.strftime("%Y-%m-%d"),
                            'teams': f"{competitors[0]['team']['abbreviation']} vs {competitors[1]['team']['abbreviation']}"
                        })
                        break
        except:
            pass
        
        current_date += timedelta(days=1)
    
    print(f"✓ {len(mem_games)} Memphis Grizzlies maçı bulundu:\n")
    
    for idx, game in enumerate(mem_games[:10], 1):
        print(f"{idx:2d}. {game['date']} - {game['teams']} (Game ID: {game['game_id']})")
    
    if mem_games:
        print(f"\n{'='*100}")
        choice = input(f"Hangi maçı detaylı görmek istersiniz? (1-{min(10, len(mem_games))}, 0=En son maç): ")
        
        try:
            idx = int(choice)
            if idx == 0:
                selected_game = mem_games[0]
            else:
                selected_game = mem_games[idx - 1]
            
            print(f"\n✓ Seçilen maç: {selected_game['date']} - {selected_game['teams']}")
            view_raw_boxscore(selected_game['game_id'])
            
        except (ValueError, IndexError):
            print("❌ Geçersiz seçim!")
    else:
        print("❌ Hiç Memphis maçı bulunamadı!")

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║          ESPN NBA API - RAW RESPONSE VIEWER                   ║
    ║                 Zach Edey Stats Inspector                     ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    print("\nSeçenekler:")
    print("1. Zach Edey'in son maçlarını bul ve detayları gör")
    print("2. Belirli bir Game ID'nin raw JSON'ını gör")
    print("3. En son oynanmış maçı göster")
    
    choice = input("\nSeçiminiz (1-3): ")
    
    if choice == "1":
        find_edey_games(days=60)
    elif choice == "2":
        game_id = input("Game ID girin: ")
        view_raw_boxscore(game_id)
    elif choice == "3":
        game_id, date = get_recent_game_id()
        if game_id:
            print(f"\n✓ En son maç bulundu: {date} (ID: {game_id})")
            view_raw_boxscore(game_id)
        else:
            print("❌ Maç bulunamadı!")
    else:
        print("❌ Geçersiz seçim!")