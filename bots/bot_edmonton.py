"""
Note: Unfortunately, at the moment, GitHub has no easy way to persist artifacts across
multiple runs, which means this script will try to load a last_date_published.txt file
that will never exist, thus fall back to the default `offset` value. In the future, an
improvement would be to find a way to persist this last_date_published.txt file (or an
environment variable that holds this value), maybe using the github actions workflow or 
some other method.
"""
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


def get_last_published_time(
    path="last_date_published.txt", offset=dt.timedelta(minutes=10, seconds=45)
):
    try:
        with open(path, "r") as f:
            last_published_str = f.read().strip()
            last_published = dt.datetime.fromisoformat(last_published_str)
    except FileNotFoundError:
        # If last_date_published.txt does not exist, set an initial last_published
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

def write_last_published_time(dt_now, path="last_date_published.txt"):
    with open(path, "w") as f:
        f.write(dt_now.isoformat())


def load_ignored_domains(path="ignored.txt", as_set=True):
    with open(path) as f:
        lines = [l.strip() for l in f.readlines()]
    lines = [l for l in lines if not l.startswith("#") and l != ""]
    if as_set is True:
        lines = set(lines)

    return lines

def find_base_domain(extracted_url):
    try:
        url_parsed = tldextract.extract(extracted_url)
        base_domain = f"{url_parsed.domain}.{url_parsed.suffix}"
    except:
        base_domain = -1
    
    return base_domain

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

def remove_old_entries(entries, limit_hours=24):
    """
    Remove entries that are older than `limit_hours` hours
    """

    new_entries = []

    dt_now = dt.datetime.now(dt.timezone.utc)

    for entry in entries:
        entry_published = dt.datetime.fromisoformat(entry.published)
        time_diff = dt_now - entry_published

        if time_diff < dt.timedelta(hours=limit_hours):
            new_entries.append(entry)

    return new_entries

def main():
    limit_hours = 24
    instance_url = "https://lemmy.ca"
    community_name = 'botland'
    subreddit_rss_url = "https://www.reddit.com/r/edmonton/new/.rss"
    sleep_time = 5

    username = os.environ["LEMMY_USERNAME"]
    password = os.environ["LEMMY_PASSWORD"]

    ignored_domains = load_ignored_domains()

    # Read the last published date from last_date_published.txt
    lemmy = Lemmy(instance_url)
    lemmy.log_in(username, password)

    last_published = get_last_published_time()
    print("Fetched last published date:", last_published)

    community_id = lemmy.discover_community(community_name)
    feed = feedparser.parse(subreddit_rss_url)

    print("Total number of feed entries:", len(feed.entries))
    dt_now = dt.datetime.now(dt.timezone.utc)
    write_last_published_time(dt_now)
    print("Written last published time as:", dt_now)
    
    published_urls_dict = load_published_urls_dict()
    published_urls_dict = remove_old_url_keys(published_urls_dict, limit_hours=limit_hours)
    print(f"Found {len(published_urls_dict)} URLs from reddit that was published to lemmy in the last {limit_hours} hours")

    entries_to_publish = []
    for entry in feed.entries:
        entry_published = dt.datetime.fromisoformat(entry.published)
        time_diff = dt_now - entry_published
        path = urlparse(entry.link).path

        if "General Discussion - Daily Thread" in entry.title:
            print(f"Skip Reddit Discussion Thread: {path}")
        
        elif time_diff > dt.timedelta(hours=limit_hours):
            print(f"Skip entry published >{limit_hours}h ago: {path}")
        elif entry.link in published_urls_dict:
            print(f"Skip entry already published:  {path}")
        else:
            entries_to_publish.append(entry)
        # Limit the number of entries to be published to 3
        if len(entries_to_publish) >= 3:
            break

    print("\nNumber of entries to be published to lemmy:", len(entries_to_publish))

    for entry in entries_to_publish:
        # Publish the summary to lemmy and sleep for a bit
        path = urlparse(entry.link).path
        formatted, extracted_url = format_and_extract(entry.summary)
        base_domain = find_base_domain(extracted_url)

        if base_domain in ignored_domains:
            print(
                f"Ignore post with link matched to '{base_domain}' in ignore list: {path}"
            )
                
        else:
            print(f"Publishing post: {path}")
            lemmy.post.create(
                community_id=community_id,
                name=html.unescape(entry.title),
                url=extracted_url,
                body=formatted,
            )
            time.sleep(sleep_time)

            # Now, add this to list of published files
            published_urls_dict[entry.link] = {"published_time": entry.published}


    save_published_urls_dict(published_urls_dict)

if __name__ == "__main__":
    main()
