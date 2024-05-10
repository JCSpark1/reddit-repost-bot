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

def format_and_extract(summary):
    soup = BeautifulSoup(summary, features="html.parser")
    
    # Extract title
    title = None
    title_tag = soup.find("a", {"title": True})
    if title_tag:
        title = html.unescape(title_tag["title"])
    
    # Extract author
    author = None
    author_tag = soup.find("a", href=True)
    if author_tag:
        author_href = author_tag["href"]
        if author_href.startswith("/user/"):
            author = author_href[6:]  # Remove '/user/' to get the author's username
    
    # Extract image URL
    image_url = None
    image_tag = soup.find("img", src=True)
    if image_tag:
        image_url = image_tag["src"]
    
    # Extract original post URL and comments URL
    original_post_url = None
    comments_url = None
    link_elements = soup.find_all("a", href=True)
    for link in link_elements:
        if link.text == "[link]":
            original_post_url = link["href"]
        elif link.text == "[comments]":
            comments_url = link["href"]
    
    # Format Lemmy post body
    post_body = ""
    if title:
        post_body += f"{html.unescape(title)}\n\n"
    if author:
        post_body += f"- Submitted by [u/{author}](https://old.reddit.com/user/{author})\n"
    if original_post_url:
        post_body += f"- [Original Post]({original_post_url})\n"
    if comments_url:
        post_body += f"- [Comments]({comments_url})\n"
    if image_url:
        post_body += f"![Image]({image_url})\n"
    
    return title, post_body

def get_last_published_time(
    path="last_date_published.txt", offset=dt.timedelta(minutes=10, seconds=45)
):
    try:
        with open(path, "r") as f:
            last_published_str = f.read().strip()
            last_published = dt.datetime.fromisoformat(last_published_str)
    except FileNotFoundError:
        dt_now = dt.datetime.now(dt.timezone.utc)
        last_published = dt_now - offset
    return last_published

def load_published_urls_dict(path="published_urls.json"):
    try:
        with open(path, "r") as f:
            published_urls_dict = json.load(f)
    except FileNotFoundError:
        published_urls_dict = {}

    return published_urls_dict

def save_published_urls_dict(published_urls_dict, path="published_urls.json"):
    with open(path, "w") as f:
        json.dump(published_urls_dict, f, indent=2)

def remove_old_url_keys(url_dict, limit_hours=24):
    """
    Remove entries that are older than `limit_hours` hours
    """

    new_entries = {}

    dt_now = dt.datetime.now(dt.timezone.utc)

    for url, entry in url_dict.items():
        entry_published = dt.datetime.fromisoformat(entry["published_time"])
        time_diff = dt_now - entry_published

        if time_diff < dt.timedelta(hours=limit_hours):
            new_entries[url] = entry

    return new_entries

def find_base_domain(extracted_url):
    try:
        url_parsed = tldextract.extract(extracted_url)
        base_domain = f"{url_parsed.domain}.{url_parsed.suffix}"
    except:
        base_domain = None
    
    return base_domain

def load_ignored_domains(path="ignored.txt", as_set=True):
    with open(path) as f:
        lines = [l.strip() for l in f.readlines()]
    lines = [l for l in lines if not l.startswith("#") and l != ""]
    if as_set is True:
        lines = set(lines)

    return lines

def main():
    instance_url = "https://lemmy.ca"
    community_name = 'botland'
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

        # Scrape and extract data from the Reddit RSS entry
        title, post_body = format_and_extract(entry.summary)

        # Check if the base domain is in the ignored list
        extracted_url = entry.link
        base_domain = find_base_domain(extracted_url)
        if base_domain in ignored_domains:
            continue

        # Post to Lemmy community
        lemmy_response = lemmy.post.create(
            community_id=community_id,
            name=title,
            url=entry.link,
            body=post_body,
        )

        if lemmy_response and "id" in lemmy_response:
            published_urls_dict[entry.link] = {"published_time": entry.published}

        time.sleep(sleep_time)

    save_published_urls_dict(published_urls_dict)

if __name__ == "__main__":
    main()

