import pandas as pd

def calculate_scores(df, w):
    df["USER_SCORE"] = (
        df["PTS"] * w["PTS"] +
        df["REB"] * w["REB"] +
        df["AST"] * w["AST"] +
        df["STL"] * w["STL"] +
        df["BLK"] * w["BLK"] +
        df["FGA"] * w["FGA"] +
        df["FGM"] * w["FGM"] +
        df["FTA"] * w["FTA"] +
        df["FTM"] * w["FTM"] +
        df["3Pts"] * w["3Pts"] +
        df["TO"]  * w["TO"] 
    )

    return df.sort_values("USER_SCORE", ascending=False)
