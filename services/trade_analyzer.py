import pandas as pd

class TradeAnalyzer:
    def __init__(self, roster_df):
        """
        Args:
            roster_df (pd.DataFrame): get_all_rosters fonksiyonundan dönen DataFrame
        """
        self.df = roster_df
        # 9-Cat Kategorileri
        self.categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
        # Ters Kategoriler (Düşük olması iyi olanlar)
        self.inverse_cats = ['TO']

    def get_team_roster(self, team_id):
        return self.df[self.df['team_id'] == team_id]

    def calculate_team_aggregates(self, team_df):
        """Bir takımın ortalama istatistiklerini hesaplar (Z-Score veya Basit Toplam)"""
        if team_df.empty:
            return {cat: 0 for cat in self.categories}
        
        # Basitlik adına ortalamaları topluyoruz (Fantasy mantığında bu, takımın haftalık potansiyelini gösterir)
        # FG% ve FT% için ağırlıklı ortalama yapmak daha doğrudur ama şimdilik düz ortalama alalım
        agg_stats = {}
        for cat in self.categories:
            if cat in ['FG%', 'FT%']:
                agg_stats[cat] = team_df[cat].mean() # Yüzdelerin ortalaması
            else:
                agg_stats[cat] = team_df[cat].sum() # Sayısal değerlerin toplamı
                
        return agg_stats

    def analyze_trade(self, team_a_id, players_out_ids, team_b_id, players_in_ids):
        """
        Team A perspektifinden takası analiz eder.
        
        Args:
            team_a_id: Takas yapan takım
            players_out_ids: Gönderilen oyuncu ID'leri (List)
            team_b_id: Karşı takım
            players_in_ids: Alınan oyuncu ID'leri (List)
        """
        
        # 1. Mevcut Durum (Before Trade)
        team_a_roster = self.get_team_roster(team_a_id)
        current_stats = self.calculate_team_aggregates(team_a_roster)
        
        # 2. Takas Sonrası Durum (After Trade)
        # Gidenleri çıkar
        post_trade_roster = team_a_roster[~team_a_roster['player_id'].isin(players_out_ids)]
        
        # Gelenleri bul ve ekle
        incoming_players = self.df[self.df['player_id'].isin(players_in_ids)]
        post_trade_roster = pd.concat([post_trade_roster, incoming_players])
        
        new_stats = self.calculate_team_aggregates(post_trade_roster)
        
        # 3. Farkları Hesapla (Delta)
        analysis = {}
        for cat in self.categories:
            diff = new_stats[cat] - current_stats[cat]
            
            # Renk ve yön belirleme
            is_positive = diff > 0
            if cat in self.inverse_cats: # TO için düşük olması iyidir
                is_positive = diff < 0
                
            analysis[cat] = {
                "current": round(current_stats[cat], 2),
                "new": round(new_stats[cat], 2),
                "diff": round(diff, 2),
                "impact": "positive" if is_positive else "negative"
            }
            
        return analysis