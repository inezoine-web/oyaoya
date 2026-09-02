"""Collect the public fund terms published on the official product list."""
from __future__ import annotations

import argparse
import csv
import re
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE_URL = "https://www.minnadeooyasan.com/fund_list/"
FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")


@dataclass
class Node:
    tag: str = ""
    attrs: dict[str, str] = field(default_factory=dict)
    parent: "Node | None" = None
    children: list["Node | str"] = field(default_factory=list)

    def text(self) -> str:
        return "".join(child if isinstance(child, str) else child.text() for child in self.children)

    def find(self, tag: str | None = None, class_name: str | None = None) -> list["Node"]:
        matched = []
        classes = self.attrs.get("class", "").split()
        if (tag is None or self.tag == tag) and (class_name is None or class_name in classes):
            matched.append(self)
        for child in self.children:
            if isinstance(child, Node):
                matched.extend(child.find(tag, class_name))
        return matched


class TreeParser(HTMLParser):
    VOID_TAGS = {"br", "hr", "img", "input", "link", "meta", "source"}

    def __init__(self) -> None:
        super().__init__()
        self.root = Node()
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.current)
        self.current.children.append(node)
        if tag not in self.VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, dict(attrs), self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root:
            if node.tag == tag:
                self.current = node.parent or self.root
                return
            node = node.parent or self.root

    def handle_data(self, data):
        self.current.children.append(data)


def parse_html(html: str) -> Node:
    parser = TreeParser()
    parser.feed(html)
    return parser.root


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value.translate(FULLWIDTH))


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "oyaoya-public-data-research/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def iso(groups: tuple[str, str, str]) -> str:
    return date(*(int(part) for part in groups)).isoformat()


def add_years(start: date, years: int) -> date:
    try:
        return start.replace(year=start.year + years) - timedelta(days=1)
    except ValueError:  # February 29
        return start.replace(year=start.year + years, day=28) - timedelta(days=1)


def collect(base_url: str = BASE_URL, delay: float = 0.05) -> tuple[list[dict[str, str]], list[str]]:
    root = parse_html(fetch(base_url))
    rows, skipped = [], []
    for card in root.find("div", "fund_list-item"):
        titles = card.find("h2", "fund_list__title")
        links = [node.attrs.get("href", "") for node in card.find("a") if node.attrs.get("href")]
        if not titles or not links:
            continue
        name, card_text = compact(titles[0].text()), compact(card.text())
        url = urljoin(base_url, links[0])
        count_match = re.search(r"募集総口数([\d,]+)口", card_text)
        yield_match = re.search(r"想定利回り([\d.]+)%", card_text)
        if not count_match or not yield_match:
            skipped.append(name)
            continue

        detail = compact(parse_html(fetch(url)).text())
        periods = re.findall(r"(20\d\d)/(\d\d)/(\d\d)[～~](20\d\d)/(\d\d)/(\d\d)", detail)
        starts = [date(int(y), int(m), int(d)) for y, m, d, *_ in periods]
        ends = [date(int(y), int(m), int(d)) for *_, y, m, d in periods]
        start_match = re.search(r"初計算期間(20\d\d)年(\d{1,2})月(\d{1,2})日から", detail)
        end_match = re.search(r"当初満了日(20\d\d)年(\d{1,2})月(\d{1,2})日", detail)
        start = date.fromisoformat(iso(start_match.groups())) if start_match else (min(starts) if starts else None)
        end = date.fromisoformat(iso(end_match.groups())) if end_match else (max(ends) if ends else None)
        images = card.find("img")
        stable = any(node.attrs.get("alt") == "安定運用中" for node in images)
        duration = re.search(r"運用期間(?:約)?(\d+)年", card_text)
        if start and not end_match and duration:
            end = add_years(start, int(duration.group(1)))
        if start is None or end is None:
            skipped.append(name)
            continue
        count = int(count_match.group(1).replace(",", ""))
        frequency = "bimonthly" if "年6回" in detail else ("monthly" if "毎月" in detail else "unknown")
        rows.append({
            "fund_name": name.removeprefix("シリーズ"), "sales_start": "",
            "operation_start": start.isoformat(), "operation_end": end.isoformat(), "actual_end": "",
            "target_amount": str(count * 1_000_000), "subscribed_amount": "",
            "annual_yield": str(float(yield_match.group(1)) / 100),
            "distribution_frequency": frequency, "redemption_status": "運用中" if stable else "不明",
            "source_url": url, "source_date": date.today().isoformat(), "confidence": "confirmed",
            "notes": "公式商品ページの募集総口数×1口100万円を募集予定額として収録。実際の出資額ではない。",
        })
        time.sleep(delay)
    return rows, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/funds.csv")
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()
    rows, skipped = collect(delay=args.delay)
    output = Path(args.output)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"collected={len(rows)} skipped={len(skipped)}: {', '.join(skipped)}")


if __name__ == "__main__":
    main()
