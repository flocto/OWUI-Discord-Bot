from ..log import logger


def do_nothing() -> str:
    """Stay silent and send no response to the Discord channel. Call this when:
    - the message is background chatter not directed at you
    - someone is talking to another person and doesn't need your input
    - an edit or reaction notification doesn't warrant a comment
    - you've already said everything relevant and repeating yourself adds nothing

    Returns:
        str: Confirmation that silence was chosen.
    """
    return "silent"
