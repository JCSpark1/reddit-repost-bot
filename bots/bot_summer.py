import os
import datetime as dt
import time
import html
import json
from urllib.parse import urlparse

import tldextract
from bs4 import BeautifulSoup
import feedparser
from pythorhead import Lemmy

def format_and_extract(summary):
    soup = BeautifulSoup(summary, features="html.parser")
    links = soup.find_all("a")

    extracted_url = None
    formatted = ""

    for link in links:
        first_child = next(link.children).strip()
        url = link.get("href")

        if first_child == "[link]":
            extracted_url = url
            text = "Link Shared on Reddit"
        elif first_child == "[comments]":
            text = "Original Reddit Comments"
        elif first_child.startswith("/u/"):
            text = f"Author: {first_child}"
        else:
            if first_child.startswith("["):
                first_child = first_child[1:]
            if first_child.endswith("]"):
                first_child = first_child[:-1]
            text = html.unescape(first_child)

        formatted += f"- [{text}]({url})\n"

    return formatted, extracted_url

def main():
    instance_url = "https://lemmy.ca"
    community_name = 'til'
    subreddit_rss_url = "https://www.reddit.com/r/todayilearned/new/.rss"
    limit_hours = 24
    sleep_time = 5

    username = os.environ["LEMMY_USERNAME"]
    password = os.environ["LEMMY_PASSWORD"]

    ignored_domains = load_ignored_domains()

    lemmy = Lemmy(instance_url)
    lemmy.log_in(username, password)
    community_id = lemmy.discover_community(community_name)

    last_published = get_last_published_time()
    dt_now = dt.datetime.now(dt.timezone.utc)

    published_urls_dict = load_published_urls_dict()
    published_urls_dict = remove_old_url_keys(published_urls_dict, limit_hours=limit_hours)

    entries_to_publish = []

    feed = feedparser.parse(subreddit_rss_url)
    for entry in feed.entries:
        entry_published = dt.datetime.fromisoformat(entry.published)
        time_diff = dt_now - entry_published
        path = urlparse(entry.link).path

        if time_diff > dt.timedelta(hours=limit_hours):
            continue
        elif entry.link in published_urls_dict:
            continue
        else:
            entries_to_publish.append(entry)

        if len(entries_to_publish) >= 3:
            break

    for entry in entries_to_publish:
        path = urlparse(entry.link).path
        formatted, extracted_url = format_and_extract(entry.summary)
        base_domain = find_base_domain(extracted_url)

        if base_domain in ignored_domains:
            continue

        lemmy_response = lemmy.post.create(
            community_id=community_id,
            name=html.unescape(entry.title),
            url=extracted_url,
            body=formatted,
        )

        if lemmy_response and "id" in lemmy_response:
            published_urls_dict[entry.link] = {"published_time": entry.published}

        time.sleep(sleep_time)

    save_published_urls_dict(published_urls_dict)

if __name__ == "__main__":
    main()

