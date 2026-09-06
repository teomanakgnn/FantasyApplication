"""
NBA Players Data for Card Connections Game
Each player has: name, current_team, country, former_teams, draft_year, position, jersey, headshot_url
"""

NBA_PLAYERS = [
    # --- Los Angeles Lakers ---
    {
        "name": "LeBron James",
        "current_team": "Los Angeles Lakers",
        "country": "USA",
        "former_teams": ["Cleveland Cavaliers", "Miami Heat"],
        "draft_year": 2003,
        "position": "SF",
        "jersey": 23,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png"
    },
    {
        "name": "Anthony Davis",
        "current_team": "Los Angeles Lakers",
        "country": "USA",
        "former_teams": ["New Orleans Pelicans"],
        "draft_year": 2012,
        "position": "PF",
        "jersey": 3,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203076.png"
    },
    {
        "name": "Austin Reaves",
        "current_team": "Los Angeles Lakers",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2021,
        "position": "SG",
        "jersey": 15,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630559.png"
    },
    # --- Boston Celtics ---
    {
        "name": "Jayson Tatum",
        "current_team": "Boston Celtics",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2017,
        "position": "SF",
        "jersey": 0,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628369.png"
    },
    {
        "name": "Jaylen Brown",
        "current_team": "Boston Celtics",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2016,
        "position": "SG",
        "jersey": 7,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1627759.png"
    },
    {
        "name": "Derrick White",
        "current_team": "Boston Celtics",
        "country": "USA",
        "former_teams": ["San Antonio Spurs"],
        "draft_year": 2017,
        "position": "PG",
        "jersey": 9,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628401.png"
    },
    # --- Golden State Warriors ---
    {
        "name": "Stephen Curry",
        "current_team": "Golden State Warriors",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2009,
        "position": "PG",
        "jersey": 30,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/201939.png"
    },
    {
        "name": "Draymond Green",
        "current_team": "Golden State Warriors",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2012,
        "position": "PF",
        "jersey": 23,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203110.png"
    },
    {
        "name": "Andrew Wiggins",
        "current_team": "Golden State Warriors",
        "country": "Canada",
        "former_teams": ["Minnesota Timberwolves"],
        "draft_year": 2014,
        "position": "SF",
        "jersey": 22,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203952.png"
    },
    # --- Milwaukee Bucks ---
    {
        "name": "Giannis Antetokounmpo",
        "current_team": "Milwaukee Bucks",
        "country": "Greece",
        "former_teams": [],
        "draft_year": 2013,
        "position": "PF",
        "jersey": 34,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203507.png"
    },
    {
        "name": "Damian Lillard",
        "current_team": "Milwaukee Bucks",
        "country": "USA",
        "former_teams": ["Portland Trail Blazers"],
        "draft_year": 2012,
        "position": "PG",
        "jersey": 0,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203081.png"
    },
    {
        "name": "Khris Middleton",
        "current_team": "Milwaukee Bucks",
        "country": "USA",
        "former_teams": ["Detroit Pistons"],
        "draft_year": 2012,
        "position": "SF",
        "jersey": 22,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203114.png"
    },
    # --- Denver Nuggets ---
    {
        "name": "Nikola Jokic",
        "current_team": "Denver Nuggets",
        "country": "Serbia",
        "former_teams": [],
        "draft_year": 2014,
        "position": "C",
        "jersey": 15,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203999.png"
    },
    {
        "name": "Jamal Murray",
        "current_team": "Denver Nuggets",
        "country": "Canada",
        "former_teams": [],
        "draft_year": 2016,
        "position": "PG",
        "jersey": 27,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1627750.png"
    },
    {
        "name": "Michael Porter Jr.",
        "current_team": "Denver Nuggets",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2018,
        "position": "SF",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629008.png"
    },
    # --- Phoenix Suns ---
    {
        "name": "Kevin Durant",
        "current_team": "Phoenix Suns",
        "country": "USA",
        "former_teams": ["Oklahoma City Thunder", "Golden State Warriors", "Brooklyn Nets"],
        "draft_year": 2007,
        "position": "SF",
        "jersey": 35,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/201142.png"
    },
    {
        "name": "Devin Booker",
        "current_team": "Phoenix Suns",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2015,
        "position": "SG",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1626164.png"
    },
    {
        "name": "Bradley Beal",
        "current_team": "Phoenix Suns",
        "country": "USA",
        "former_teams": ["Washington Wizards"],
        "draft_year": 2012,
        "position": "SG",
        "jersey": 3,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203078.png"
    },
    # --- Dallas Mavericks ---
    {
        "name": "Luka Doncic",
        "current_team": "Dallas Mavericks",
        "country": "Slovenia",
        "former_teams": [],
        "draft_year": 2018,
        "position": "PG",
        "jersey": 77,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629029.png"
    },
    {
        "name": "Kyrie Irving",
        "current_team": "Dallas Mavericks",
        "country": "Australia",
        "former_teams": ["Cleveland Cavaliers", "Boston Celtics", "Brooklyn Nets"],
        "draft_year": 2011,
        "position": "PG",
        "jersey": 11,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/202681.png"
    },
    # --- Philadelphia 76ers ---
    {
        "name": "Joel Embiid",
        "current_team": "Philadelphia 76ers",
        "country": "Cameroon",
        "former_teams": [],
        "draft_year": 2014,
        "position": "C",
        "jersey": 21,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203954.png"
    },
    {
        "name": "Tyrese Maxey",
        "current_team": "Philadelphia 76ers",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2020,
        "position": "PG",
        "jersey": 0,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630178.png"
    },
    # --- Miami Heat ---
    {
        "name": "Jimmy Butler",
        "current_team": "Miami Heat",
        "country": "USA",
        "former_teams": ["Chicago Bulls", "Minnesota Timberwolves", "Philadelphia 76ers"],
        "draft_year": 2011,
        "position": "SF",
        "jersey": 22,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/202710.png"
    },
    {
        "name": "Bam Adebayo",
        "current_team": "Miami Heat",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2017,
        "position": "C",
        "jersey": 13,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628389.png"
    },
    {
        "name": "Tyler Herro",
        "current_team": "Miami Heat",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2019,
        "position": "SG",
        "jersey": 14,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629639.png"
    },
    # --- Oklahoma City Thunder ---
    {
        "name": "Shai Gilgeous-Alexander",
        "current_team": "Oklahoma City Thunder",
        "country": "Canada",
        "former_teams": ["Los Angeles Clippers"],
        "draft_year": 2018,
        "position": "PG",
        "jersey": 2,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628983.png"
    },
    {
        "name": "Chet Holmgren",
        "current_team": "Oklahoma City Thunder",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2022,
        "position": "C",
        "jersey": 7,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1631096.png"
    },
    {
        "name": "Jalen Williams",
        "current_team": "Oklahoma City Thunder",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2022,
        "position": "SG",
        "jersey": 8,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1631114.png"
    },
    # --- Minnesota Timberwolves ---
    {
        "name": "Anthony Edwards",
        "current_team": "Minnesota Timberwolves",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2020,
        "position": "SG",
        "jersey": 5,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630162.png"
    },
    {
        "name": "Karl-Anthony Towns",
        "current_team": "New York Knicks",
        "country": "USA",
        "former_teams": ["Minnesota Timberwolves"],
        "draft_year": 2015,
        "position": "C",
        "jersey": 32,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1626157.png"
    },
    {
        "name": "Rudy Gobert",
        "current_team": "Minnesota Timberwolves",
        "country": "France",
        "former_teams": ["Utah Jazz"],
        "draft_year": 2013,
        "position": "C",
        "jersey": 27,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203497.png"
    },
    # --- New York Knicks ---
    {
        "name": "Jalen Brunson",
        "current_team": "New York Knicks",
        "country": "USA",
        "former_teams": ["Dallas Mavericks"],
        "draft_year": 2018,
        "position": "PG",
        "jersey": 11,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628973.png"
    },
    {
        "name": "Julius Randle",
        "current_team": "Minnesota Timberwolves",
        "country": "USA",
        "former_teams": ["Los Angeles Lakers", "New Orleans Pelicans", "New York Knicks"],
        "draft_year": 2014,
        "position": "PF",
        "jersey": 30,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203944.png"
    },
    {
        "name": "OG Anunoby",
        "current_team": "New York Knicks",
        "country": "UK",
        "former_teams": ["Toronto Raptors"],
        "draft_year": 2017,
        "position": "SF",
        "jersey": 8,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628384.png"
    },
    # --- Cleveland Cavaliers ---
    {
        "name": "Donovan Mitchell",
        "current_team": "Cleveland Cavaliers",
        "country": "USA",
        "former_teams": ["Utah Jazz"],
        "draft_year": 2017,
        "position": "SG",
        "jersey": 45,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628378.png"
    },
    {
        "name": "Darius Garland",
        "current_team": "Cleveland Cavaliers",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2019,
        "position": "PG",
        "jersey": 10,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629636.png"
    },
    {
        "name": "Evan Mobley",
        "current_team": "Cleveland Cavaliers",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2021,
        "position": "C",
        "jersey": 4,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630596.png"
    },
    {
        "name": "Jarrett Allen",
        "current_team": "Cleveland Cavaliers",
        "country": "USA",
        "former_teams": ["Brooklyn Nets"],
        "draft_year": 2017,
        "position": "C",
        "jersey": 31,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628386.png"
    },
    # --- Sacramento Kings ---
    {
        "name": "De'Aaron Fox",
        "current_team": "Sacramento Kings",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2017,
        "position": "PG",
        "jersey": 5,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628368.png"
    },
    {
        "name": "Domantas Sabonis",
        "current_team": "Sacramento Kings",
        "country": "Lithuania",
        "former_teams": ["Oklahoma City Thunder", "Indiana Pacers"],
        "draft_year": 2016,
        "position": "C",
        "jersey": 10,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1627734.png"
    },
    # --- Indiana Pacers ---
    {
        "name": "Tyrese Haliburton",
        "current_team": "Indiana Pacers",
        "country": "USA",
        "former_teams": ["Sacramento Kings"],
        "draft_year": 2020,
        "position": "PG",
        "jersey": 0,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630169.png"
    },
    {
        "name": "Pascal Siakam",
        "current_team": "Indiana Pacers",
        "country": "Cameroon",
        "former_teams": ["Toronto Raptors"],
        "draft_year": 2016,
        "position": "PF",
        "jersey": 43,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1627783.png"
    },
    # --- Los Angeles Clippers ---
    {
        "name": "Kawhi Leonard",
        "current_team": "Los Angeles Clippers",
        "country": "USA",
        "former_teams": ["San Antonio Spurs", "Toronto Raptors"],
        "draft_year": 2011,
        "position": "SF",
        "jersey": 2,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/202695.png"
    },
    {
        "name": "Paul George",
        "current_team": "Philadelphia 76ers",
        "country": "USA",
        "former_teams": ["Indiana Pacers", "Oklahoma City Thunder", "Los Angeles Clippers"],
        "draft_year": 2010,
        "position": "SF",
        "jersey": 8,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/202331.png"
    },
    {
        "name": "James Harden",
        "current_team": "Los Angeles Clippers",
        "country": "USA",
        "former_teams": ["Oklahoma City Thunder", "Houston Rockets", "Brooklyn Nets", "Philadelphia 76ers"],
        "draft_year": 2009,
        "position": "SG",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/201935.png"
    },
    # --- Toronto Raptors ---
    {
        "name": "Scottie Barnes",
        "current_team": "Toronto Raptors",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2021,
        "position": "PF",
        "jersey": 4,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630567.png"
    },
    {
        "name": "RJ Barrett",
        "current_team": "Toronto Raptors",
        "country": "Canada",
        "former_teams": ["New York Knicks"],
        "draft_year": 2019,
        "position": "SG",
        "jersey": 9,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629628.png"
    },
    # --- Chicago Bulls ---
    {
        "name": "Zach LaVine",
        "current_team": "Chicago Bulls",
        "country": "USA",
        "former_teams": ["Minnesota Timberwolves"],
        "draft_year": 2014,
        "position": "SG",
        "jersey": 8,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203897.png"
    },
    {
        "name": "DeMar DeRozan",
        "current_team": "Sacramento Kings",
        "country": "USA",
        "former_teams": ["Toronto Raptors", "San Antonio Spurs", "Chicago Bulls"],
        "draft_year": 2009,
        "position": "SG",
        "jersey": 10,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/201942.png"
    },
    # --- Atlanta Hawks ---
    {
        "name": "Trae Young",
        "current_team": "Atlanta Hawks",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2018,
        "position": "PG",
        "jersey": 11,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629027.png"
    },
    # --- Memphis Grizzlies ---
    {
        "name": "Ja Morant",
        "current_team": "Memphis Grizzlies",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2019,
        "position": "PG",
        "jersey": 12,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629630.png"
    },
    {
        "name": "Jaren Jackson Jr.",
        "current_team": "Memphis Grizzlies",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2018,
        "position": "PF",
        "jersey": 13,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628991.png"
    },
    # --- New Orleans Pelicans ---
    {
        "name": "Zion Williamson",
        "current_team": "New Orleans Pelicans",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2019,
        "position": "PF",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629627.png"
    },
    {
        "name": "Brandon Ingram",
        "current_team": "New Orleans Pelicans",
        "country": "USA",
        "former_teams": ["Los Angeles Lakers"],
        "draft_year": 2016,
        "position": "SF",
        "jersey": 14,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1627742.png"
    },
    {
        "name": "CJ McCollum",
        "current_team": "New Orleans Pelicans",
        "country": "USA",
        "former_teams": ["Portland Trail Blazers"],
        "draft_year": 2013,
        "position": "SG",
        "jersey": 3,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203468.png"
    },
    # --- San Antonio Spurs ---
    {
        "name": "Victor Wembanyama",
        "current_team": "San Antonio Spurs",
        "country": "France",
        "former_teams": [],
        "draft_year": 2023,
        "position": "C",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1641705.png"
    },
    # --- Houston Rockets ---
    {
        "name": "Jalen Green",
        "current_team": "Houston Rockets",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2021,
        "position": "SG",
        "jersey": 4,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630224.png"
    },
    {
        "name": "Alperen Sengun",
        "current_team": "Houston Rockets",
        "country": "Turkey",
        "former_teams": [],
        "draft_year": 2021,
        "position": "C",
        "jersey": 28,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630578.png"
    },
    # --- Brooklyn Nets ---
    {
        "name": "Mikal Bridges",
        "current_team": "New York Knicks",
        "country": "USA",
        "former_teams": ["Phoenix Suns", "Brooklyn Nets"],
        "draft_year": 2018,
        "position": "SF",
        "jersey": 25,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628969.png"
    },
    # --- Charlotte Hornets ---
    {
        "name": "LaMelo Ball",
        "current_team": "Charlotte Hornets",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2020,
        "position": "PG",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630163.png"
    },
    # --- Portland Trail Blazers ---
    {
        "name": "Anfernee Simons",
        "current_team": "Portland Trail Blazers",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2018,
        "position": "SG",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629014.png"
    },
    # --- Utah Jazz ---
    {
        "name": "Lauri Markkanen",
        "current_team": "Utah Jazz",
        "country": "Finland",
        "former_teams": ["Chicago Bulls", "Cleveland Cavaliers"],
        "draft_year": 2017,
        "position": "PF",
        "jersey": 23,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628374.png"
    },
    # --- Washington Wizards ---
    {
        "name": "Kyle Kuzma",
        "current_team": "Washington Wizards",
        "country": "USA",
        "former_teams": ["Los Angeles Lakers"],
        "draft_year": 2017,
        "position": "PF",
        "jersey": 33,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1628398.png"
    },
    # --- Detroit Pistons ---
    {
        "name": "Cade Cunningham",
        "current_team": "Detroit Pistons",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2021,
        "position": "PG",
        "jersey": 2,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630595.png"
    },
    # --- Orlando Magic ---
    {
        "name": "Paolo Banchero",
        "current_team": "Orlando Magic",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2022,
        "position": "PF",
        "jersey": 5,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1631094.png"
    },
    {
        "name": "Franz Wagner",
        "current_team": "Orlando Magic",
        "country": "Germany",
        "former_teams": [],
        "draft_year": 2021,
        "position": "SF",
        "jersey": 22,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630532.png"
    },
    # --- Extra International Stars ---
    {
        "name": "Luka Garza",
        "current_team": "Minnesota Timberwolves",
        "country": "USA",
        "former_teams": ["Detroit Pistons"],
        "draft_year": 2021,
        "position": "C",
        "jersey": 55,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1630568.png"
    },
    {
        "name": "Chris Paul",
        "current_team": "San Antonio Spurs",
        "country": "USA",
        "former_teams": ["New Orleans Pelicans", "Los Angeles Clippers", "Houston Rockets", "Oklahoma City Thunder", "Phoenix Suns", "Golden State Warriors"],
        "draft_year": 2005,
        "position": "PG",
        "jersey": 3,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/101108.png"
    },
    {
        "name": "Russell Westbrook",
        "current_team": "Denver Nuggets",
        "country": "USA",
        "former_teams": ["Oklahoma City Thunder", "Houston Rockets", "Washington Wizards", "Los Angeles Lakers", "Los Angeles Clippers"],
        "draft_year": 2008,
        "position": "PG",
        "jersey": 4,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/201566.png"
    },
    {
        "name": "Nikola Vucevic",
        "current_team": "Chicago Bulls",
        "country": "Montenegro",
        "former_teams": ["Philadelphia 76ers", "Orlando Magic"],
        "draft_year": 2011,
        "position": "C",
        "jersey": 9,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/202696.png"
    },
    {
        "name": "Jonas Valanciunas",
        "current_team": "Washington Wizards",
        "country": "Lithuania",
        "former_teams": ["Toronto Raptors", "Memphis Grizzlies", "New Orleans Pelicans"],
        "draft_year": 2011,
        "position": "C",
        "jersey": 17,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/202685.png"
    },
    {
        "name": "Dennis Schroder",
        "current_team": "Brooklyn Nets",
        "country": "Germany",
        "former_teams": ["Atlanta Hawks", "Oklahoma City Thunder", "Los Angeles Lakers", "Boston Celtics", "Houston Rockets", "Toronto Raptors"],
        "draft_year": 2013,
        "position": "PG",
        "jersey": 17,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203471.png"
    },
    {
        "name": "Bogdan Bogdanovic",
        "current_team": "Atlanta Hawks",
        "country": "Serbia",
        "former_teams": ["Sacramento Kings"],
        "draft_year": 2014,
        "position": "SG",
        "jersey": 13,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203992.png"
    },
    {
        "name": "Rui Hachimura",
        "current_team": "Los Angeles Lakers",
        "country": "Japan",
        "former_teams": ["Washington Wizards"],
        "draft_year": 2019,
        "position": "PF",
        "jersey": 28,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1629060.png"
    },
    {
        "name": "Kristaps Porzingis",
        "current_team": "Boston Celtics",
        "country": "Latvia",
        "former_teams": ["New York Knicks", "Dallas Mavericks", "Washington Wizards"],
        "draft_year": 2015,
        "position": "C",
        "jersey": 8,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/204001.png"
    },
    {
        "name": "Clint Capela",
        "current_team": "Atlanta Hawks",
        "country": "Switzerland",
        "former_teams": ["Houston Rockets"],
        "draft_year": 2014,
        "position": "C",
        "jersey": 15,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/203991.png"
    },
    {
        "name": "Al Horford",
        "current_team": "Boston Celtics",
        "country": "Dominican Republic",
        "former_teams": ["Atlanta Hawks", "Philadelphia 76ers", "Oklahoma City Thunder"],
        "draft_year": 2007,
        "position": "C",
        "jersey": 42,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/201143.png"
    },
    # --- More stars for richer connections ---
    {
        "name": "Dejounte Murray",
        "current_team": "New Orleans Pelicans",
        "country": "USA",
        "former_teams": ["San Antonio Spurs", "Atlanta Hawks"],
        "draft_year": 2016,
        "position": "PG",
        "jersey": 5,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1627749.png"
    },
    {
        "name": "Myles Turner",
        "current_team": "Indiana Pacers",
        "country": "USA",
        "former_teams": [],
        "draft_year": 2015,
        "position": "C",
        "jersey": 33,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1626167.png"
    },
    {
        "name": "Fred VanVleet",
        "current_team": "Houston Rockets",
        "country": "USA",
        "former_teams": ["Toronto Raptors"],
        "draft_year": 2016,
        "position": "PG",
        "jersey": 5,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1627832.png"
    },
    {
        "name": "Terry Rozier",
        "current_team": "Miami Heat",
        "country": "USA",
        "former_teams": ["Boston Celtics", "Charlotte Hornets"],
        "draft_year": 2015,
        "position": "PG",
        "jersey": 2,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1626179.png"
    },
    {
        "name": "D'Angelo Russell",
        "current_team": "Los Angeles Lakers",
        "country": "USA",
        "former_teams": ["Brooklyn Nets", "Golden State Warriors", "Minnesota Timberwolves"],
        "draft_year": 2015,
        "position": "PG",
        "jersey": 1,
        "headshot_url": "https://cdn.nba.com/headshots/nba/latest/1040x760/1626156.png"
    },
]


# Connection types configuration
CONNECTION_TYPES = {
    "current_team": {
        "label": "Teammates",
        "color": "#10b981",       # green
        "bg_color": "rgba(16, 185, 129, 0.15)",
        "points": 5,
        "icon": "🟢",
        "description": "Same current NBA team"
    },
    "country": {
        "label": "Countrymen",
        "color": "#3b82f6",       # blue
        "bg_color": "rgba(59, 130, 246, 0.15)",
        "points": 3,
        "icon": "🔵",
        "description": "Same nationality"
    },
    "former_team": {
        "label": "Former Teammates",
        "color": "#f59e0b",       # yellow/amber
        "bg_color": "rgba(245, 158, 11, 0.15)",
        "points": 2,
        "icon": "🟡",
        "description": "Shared a former team"
    },
    "draft_year": {
        "label": "Draft Class",
        "color": "#f97316",       # orange
        "bg_color": "rgba(249, 115, 22, 0.15)",
        "points": 1,
        "icon": "🟠",
        "description": "Same draft year"
    },
}


# Kadro kisaltmasi -> kart oyununda kullanilan tam takim adi
_ABBR_TO_TEAM = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GS": "Golden State Warriors", "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies", "MIA": "Miami Heat", "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves", "NO": "New Orleans Pelicans",
    "NOP": "New Orleans Pelicans", "NY": "New York Knicks", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings",
    "SA": "San Antonio Spurs", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "UTAH": "Utah Jazz",
    "WSH": "Washington Wizards",
}


def _live_team_map():
    """
    ESPN kadrolarindan {oyuncu adi: tam takim adi} haritasi.

    Bu dosyadaki NBA_PLAYERS listesi elle yazilmis ve bayatliyor: olculdu,
    82 oyuncunun 39'unun takimi artik yanlisti (Luka Doncic kartta Dallas
    yaziyordu, gercekte Lakers). Bu sadece gorsel bir sorun degil -
    "Teammates" baglantisi 5 puan ve current_team uzerinden hesaplaniyor,
    yani skor da yanlis cikiyordu.

    Ag yoksa bos donuyor ve statik veri oldugu gibi kullaniliyor.
    """
    try:
        from services.espn_api import get_current_team_rosters
        rosters = get_current_team_rosters()
    except Exception as exc:
        print(f"⚠️ Kart oyunu icin canli kadro alinamadi: {exc}")
        return {}

    out = {}
    for name, info in (rosters or {}).items():
        abbr = info.get("team") if isinstance(info, dict) else info
        team = _ABBR_TO_TEAM.get(abbr)
        if team:
            out[name] = team
    return out


def get_all_players():
    """
    Oyuncu listesini dondurur; guncel takimlar canli kadrodan tazelenir.

    Statik veri yedek olarak kalir (ag yoksa oyun yine calisir).
    """
    live = _live_team_map()
    players = []
    duzeltilen = 0

    for p in NBA_PLAYERS:
        card = p.copy()
        gercek = live.get(card["name"])
        if gercek and gercek != card["current_team"]:
            eski = card["current_team"]
            card["current_team"] = gercek
            # Oyuncu eski takimina geri donmus olabilir; ayni takim hem
            # guncel hem "eski takim" olarak gorunmesin.
            formers = [t for t in card.get("former_teams", []) if t != gercek]
            # Birakti oldugu takim artik gecmisi sayilir.
            if eski and eski not in formers:
                formers.append(eski)
            card["former_teams"] = formers
            duzeltilen += 1
        players.append(card)

    if duzeltilen:
        print(f"✓ Kart oyunu: {duzeltilen} oyuncunun takimi canli kadrodan güncellendi")
    return players


def get_player_count():
    """Get total number of players in database."""
    return len(NBA_PLAYERS)
