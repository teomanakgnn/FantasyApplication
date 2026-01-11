import pandas as pd

class TradeAnalyzer:
    def __init__(self, roster_df):
        self.df = roster_df
        self.categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
        self.inverse_cats = ['TO']

    def get_team_roster(self, team_id):
        return self.df[self.df['team_id'] == team_id]

    def calculate_team_aggregates(self, team_df):
        if team_df.empty:
            return {cat: 0.0 for cat in self.categories}
        
        agg_stats = {}
        for cat in self.categories:
            if cat in ['FG%', 'FT%']:
                agg_stats[cat] = team_df[cat].mean()
            else:
                agg_stats[cat] = team_df[cat].sum()
        return agg_stats

    def analyze_trade(self, team_a_id, players_out_ids, team_b_id, players_in_ids):
        # 1. Mevcut Durum
        team_a_roster = self.get_team_roster(team_a_id)
        current_stats = self.calculate_team_aggregates(team_a_roster)
        
        # 2. Takas Sonrası Durum
        # Gidenleri çıkar
        post_trade_roster = team_a_roster[~team_a_roster['player_id'].isin(players_out_ids)]
        
        # Gelenleri bul ve ekle
        if players_in_ids:
            incoming_players = self.df[self.df['player_id'].isin(players_in_ids)]
            post_trade_roster = pd.concat([post_trade_roster, incoming_players])
        
        new_stats = self.calculate_team_aggregates(post_trade_roster)
        
        # 3. Farkları Hesapla
        analysis = {}
        for cat in self.categories:
            diff = new_stats[cat] - current_stats[cat]
            
            is_positive = diff > 0
            if cat in self.inverse_cats: 
                is_positive = diff < 0
            
            # Sıfıra eşitse nötr kalsın
            if abs(diff) < 0.01:
                impact = "neutral"
            else:
                impact = "positive" if is_positive else "negative"

            analysis[cat] = {
                "current": round(current_stats[cat], 2),
                "new": round(new_stats[cat], 2),
                "diff": round(diff, 2),
                "impact": impact
            }
            
        return analysis