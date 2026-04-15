"""ArXiv cs.AI RSS 수집기. RSSCollector의 특수화 버전으로 ArXiv만 가져온다."""
from src.collector.rss import RSSCollector

ARXIV_SOURCE = [("ArXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI")]


class ArXivCollector(RSSCollector):
    def __init__(self) -> None:
        super().__init__(sources=ARXIV_SOURCE)
