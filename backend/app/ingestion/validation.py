def has_unbalanced_punctuation(text: str) -> bool:
    pairs = (("(", ")"), ("[", "]"), ("{", "}"))
    return any(
        text.count(open_char) != text.count(close_char)
        for open_char, close_char in pairs
    )
