import os


REDDIT_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) "
    "Gecko/20100101 Firefox/149.0"
)


def get_reddit_user_agent() -> str:
    return os.getenv("REDDIT_USER_AGENT", REDDIT_DEFAULT_USER_AGENT)
