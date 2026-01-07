def parse_minutes(min_str):
    """
    '18:34' -> 18
    '12' -> 12
    None / '' -> 0
    """
    if not min_str:
        return 0

    if isinstance(min_str, str) and ":" in min_str:
        return int(min_str.split(":")[0])

    try:
        return int(float(min_str))
    except:
        return 0
