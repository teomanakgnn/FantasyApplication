"""
Card Connections Game Engine
Handles deck management, game state, connection checking, scoring, and bot AI.
"""
import random
from itertools import combinations
from services.nba_players_data import get_all_players, CONNECTION_TYPES


class CardDeck:
    """Manages the card deck - shuffling, dealing, drawing."""

    def __init__(self):
        self.cards = get_all_players()
        random.shuffle(self.cards)
        self.dealt_indices = set()

    def deal(self, count):
        """Deal 'count' cards from the deck."""
        available = [i for i in range(len(self.cards)) if i not in self.dealt_indices]
        if len(available) < count:
            return []
        chosen = random.sample(available, count)
        self.dealt_indices.update(chosen)
        return [self.cards[i].copy() for i in chosen]

    def draw(self, count):
        """Draw replacement cards."""
        return self.deal(count)

    def remaining(self):
        """How many cards are left in the deck."""
        return len(self.cards) - len(self.dealt_indices)


class ConnectionChecker:
    """Finds connections between pairs of player cards."""

    @staticmethod
    def find_connections(card_a, card_b):
        """
        Find all connections between two player cards.
        Returns a list of connection dicts with type, color, points, label.
        """
        connections = []

        # 1. Same current team (GREEN, 5pts)
        if card_a["current_team"] == card_b["current_team"]:
            ct = CONNECTION_TYPES["current_team"]
            connections.append({
                "type": "current_team",
                "label": ct["label"],
                "detail": card_a["current_team"],
                "color": ct["color"],
                "bg_color": ct["bg_color"],
                "points": ct["points"],
                "icon": ct["icon"],
            })

        # 2. Same country (BLUE, 3pts)
        if card_a["country"] == card_b["country"]:
            ct = CONNECTION_TYPES["country"]
            connections.append({
                "type": "country",
                "label": ct["label"],
                "detail": card_a["country"],
                "color": ct["color"],
                "bg_color": ct["bg_color"],
                "points": ct["points"],
                "icon": ct["icon"],
            })

        # 3. Shared former team (YELLOW, 2pts per shared team)
        a_all_teams = set(card_a.get("former_teams", []))
        b_all_teams = set(card_b.get("former_teams", []))
        # Also include current teams in the "ever played for" set
        a_all_teams.add(card_a["current_team"])
        b_all_teams.add(card_b["current_team"])
        shared_teams = a_all_teams & b_all_teams
        # Remove current team match (already counted above)
        if card_a["current_team"] == card_b["current_team"]:
            shared_teams.discard(card_a["current_team"])
        for team in shared_teams:
            ct = CONNECTION_TYPES["former_team"]
            connections.append({
                "type": "former_team",
                "label": ct["label"],
                "detail": team,
                "color": ct["color"],
                "bg_color": ct["bg_color"],
                "points": ct["points"],
                "icon": ct["icon"],
            })

        # 4. Same draft year (ORANGE, 1pt)
        if card_a["draft_year"] == card_b["draft_year"]:
            ct = CONNECTION_TYPES["draft_year"]
            connections.append({
                "type": "draft_year",
                "label": ct["label"],
                "detail": str(card_a["draft_year"]),
                "color": ct["color"],
                "bg_color": ct["bg_color"],
                "points": ct["points"],
                "icon": ct["icon"],
            })

        return connections

    @staticmethod
    def find_all_connections(hand):
        """
        Find all connections in a hand of cards.
        Returns list of connection results for every pair.
        """
        all_connections = []
        for i, j in combinations(range(len(hand)), 2):
            conns = ConnectionChecker.find_connections(hand[i], hand[j])
            if conns:
                all_connections.append({
                    "card_a_idx": i,
                    "card_b_idx": j,
                    "card_a": hand[i],
                    "card_b": hand[j],
                    "connections": conns,
                })
        return all_connections

    @staticmethod
    def calculate_hand_score(hand):
        """Calculate total score for a hand."""
        all_conns = ConnectionChecker.find_all_connections(hand)
        total = 0
        for pair in all_conns:
            for conn in pair["connections"]:
                total += conn["points"]
        return total, all_conns

    @staticmethod
    def calculate_card_contribution(hand, card_index):
        """Calculate how many points a specific card contributes to the hand."""
        contribution = 0
        for i in range(len(hand)):
            if i == card_index:
                continue
            conns = ConnectionChecker.find_connections(hand[card_index], hand[i])
            for c in conns:
                contribution += c["points"]
        return contribution


class BotAI:
    """Bot player AI for Card Connections."""

    def __init__(self, difficulty="normal"):
        """
        difficulty: 'easy' (random), 'normal' (70% optimal), 'hard' (90% optimal)
        """
        self.difficulty = difficulty
        self.accuracy = {"easy": 0.4, "normal": 0.7, "hard": 0.9}.get(difficulty, 0.7)

    def choose_discard(self, hand, max_discard=3):
        """
        Decide which cards to discard from the hand.
        Returns list of card indices to discard.
        """
        # Calculate contribution of each card
        contributions = []
        for i in range(len(hand)):
            contrib = ConnectionChecker.calculate_card_contribution(hand, i)
            contributions.append((i, contrib))

        # Sort by contribution (lowest first = best to discard)
        contributions.sort(key=lambda x: x[1])

        # Decide how many to discard (1-max_discard, biased towards 2-3)
        num_discard = random.choices(
            list(range(1, max_discard + 1)),
            weights=[1, 3, 2],  # bias towards 2
            k=1
        )[0]

        # Apply accuracy: sometimes make non-optimal choices
        if random.random() > self.accuracy:
            # Make a random choice instead
            return random.sample(range(len(hand)), min(num_discard, len(hand)))

        # Pick the lowest-contribution cards
        to_discard = [idx for idx, _ in contributions[:num_discard]]
        return to_discard

    def should_use_discard(self, hand, discards_remaining):
        """Decide whether to use a discard or keep current hand."""
        if discards_remaining <= 0:
            return False

        score, _ = ConnectionChecker.calculate_hand_score(hand)
        # Calculate average contribution
        total_cards = len(hand)
        if total_cards == 0:
            return False

        # If score is low relative to hand size, discard
        avg_score_per_pair = score / max(1, total_cards * (total_cards - 1) / 2)

        # More likely to discard if score is low
        if avg_score_per_pair < 1.0:
            return random.random() < 0.85  # Very likely
        elif avg_score_per_pair < 2.0:
            return random.random() < 0.5   # Maybe
        else:
            return random.random() < 0.2   # Unlikely, hand is good


class GameState:
    """Manages the full game state."""

    HAND_SIZE = 10
    MAX_DISCARDS = 3

    # Game phases
    PHASE_LOBBY = "lobby"
    PHASE_DEALING = "dealing"
    PHASE_PLAYER_TURN = "player_turn"
    PHASE_BOT_TURN = "bot_turn"
    PHASE_REVEAL = "reveal"
    PHASE_FINISHED = "finished"

    def __init__(self, bot_difficulty="normal"):
        self.deck = CardDeck()
        self.player_hand = []
        self.bot_hand = []
        self.player_discards_left = self.MAX_DISCARDS
        self.bot_discards_left = self.MAX_DISCARDS
        self.phase = self.PHASE_LOBBY
        self.player_score = 0
        self.bot_score = 0
        self.player_connections = []
        self.bot_connections = []
        self.bot_ai = BotAI(bot_difficulty)
        self.round_number = 0
        self.message = ""
        self.bot_difficulty = bot_difficulty

    def start_game(self):
        """Deal cards to both players and start the game."""
        self.deck = CardDeck()
        self.player_hand = self.deck.deal(self.HAND_SIZE)
        self.bot_hand = self.deck.deal(self.HAND_SIZE)
        self.player_discards_left = self.MAX_DISCARDS
        self.bot_discards_left = self.MAX_DISCARDS
        self.phase = self.PHASE_PLAYER_TURN
        self.round_number = 1
        self.player_score = 0
        self.bot_score = 0
        self.player_connections = []
        self.bot_connections = []
        self.message = "Your turn! Select cards to discard or lock in your hand."

    def player_discard(self, card_indices):
        """
        Player discards selected cards and draws replacements.
        Returns True if successful.
        """
        if self.phase != self.PHASE_PLAYER_TURN:
            return False
        if self.player_discards_left <= 0:
            return False
        if not card_indices:
            return False
        if len(card_indices) > len(self.player_hand):
            return False

        # Remove selected cards (in reverse order to maintain indices)
        removed_count = 0
        for idx in sorted(card_indices, reverse=True):
            if 0 <= idx < len(self.player_hand):
                self.player_hand.pop(idx)
                removed_count += 1

        # Draw new cards
        new_cards = self.deck.draw(removed_count)
        self.player_hand.extend(new_cards)
        self.player_discards_left -= 1

        self.message = f"Discarded {removed_count} card(s), drew {len(new_cards)} new. "
        self.message += f"{self.player_discards_left} discard(s) remaining."

        return True

    def player_lock_in(self):
        """Player locks in their hand, moves to bot turn."""
        if self.phase != self.PHASE_PLAYER_TURN:
            return False

        self.phase = self.PHASE_BOT_TURN
        self._bot_take_turns()
        self._calculate_final_scores()
        self.phase = self.PHASE_REVEAL
        return True

    def _bot_take_turns(self):
        """Bot uses its discard opportunities."""
        while self.bot_discards_left > 0:
            if not self.bot_ai.should_use_discard(self.bot_hand, self.bot_discards_left):
                break

            discard_indices = self.bot_ai.choose_discard(self.bot_hand)
            if not discard_indices:
                break

            # Remove and redraw
            for idx in sorted(discard_indices, reverse=True):
                if 0 <= idx < len(self.bot_hand):
                    self.bot_hand.pop(idx)

            new_cards = self.deck.draw(len(discard_indices))
            self.bot_hand.extend(new_cards)
            self.bot_discards_left -= 1

    def _calculate_final_scores(self):
        """Calculate final scores for both hands."""
        self.player_score, self.player_connections = ConnectionChecker.calculate_hand_score(self.player_hand)
        self.bot_score, self.bot_connections = ConnectionChecker.calculate_hand_score(self.bot_hand)

        if self.player_score > self.bot_score:
            self.message = "You win!"
        elif self.bot_score > self.player_score:
            self.message = "Bot wins!"
        else:
            self.message = "It's a tie!"

    def get_winner(self):
        """Get the winner. Returns 'player', 'bot', or 'tie'."""
        if self.phase not in [self.PHASE_REVEAL, self.PHASE_FINISHED]:
            return None
        if self.player_score > self.bot_score:
            return "player"
        elif self.bot_score > self.player_score:
            return "bot"
        return "tie"

    def get_current_player_score_preview(self):
        """Preview the current player score (before locking in)."""
        return ConnectionChecker.calculate_hand_score(self.player_hand)

    def to_dict(self):
        """Serialize game state for session storage."""
        return {
            "player_hand": self.player_hand,
            "bot_hand": self.bot_hand,
            "player_discards_left": self.player_discards_left,
            "bot_discards_left": self.bot_discards_left,
            "phase": self.phase,
            "player_score": self.player_score,
            "bot_score": self.bot_score,
            "player_connections": self.player_connections,
            "bot_connections": self.bot_connections,
            "round_number": self.round_number,
            "message": self.message,
            "bot_difficulty": self.bot_difficulty,
        }

    @classmethod
    def from_dict(cls, data):
        """Restore game state from session storage."""
        game = cls(data.get("bot_difficulty", "normal"))
        game.player_hand = data["player_hand"]
        game.bot_hand = data["bot_hand"]
        game.player_discards_left = data["player_discards_left"]
        game.bot_discards_left = data["bot_discards_left"]
        game.phase = data["phase"]
        game.player_score = data["player_score"]
        game.bot_score = data["bot_score"]
        game.player_connections = data.get("player_connections", [])
        game.bot_connections = data.get("bot_connections", [])
        game.round_number = data.get("round_number", 1)
        game.message = data.get("message", "")
        # Deck is not preserved, but not needed after dealing
        return game
