import requests
import os

LEMMY_API_BASE_URL = "https://lemmy.ca/api/v3"
community_name = "botland"  # Update this to the community name
USERNAME_TO_WATCH = "@partybot"
LEMMY_USERNAME = os.getenv("LEMMY_USERNAME")
LEMMY_PASSWORD = os.getenv("LEMMY_PASSWORD")

def authenticate():
    url = f"{LEMMY_API_BASE_URL}/user/login"
    data = {
        "username_or_email": LEMMY_USERNAME,
        "password": LEMMY_PASSWORD
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()["jwt"]
    else:
        print(f"Authentication failed: {response.status_code}")
        return None

def get_recent_posts(auth_token, community_name):
    url = f"{LEMMY_API_BASE_URL}/post/list"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    params = {
        "community_name": community_name,
        "sort": "New",
        "limit": 10,
        "deleted": "false"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()["posts"]
    else:
        print(f"Failed to fetch posts: {response.status_code}, {response.json()}")
        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")
        print(f"Request Params: {params}")
        return []

def check_for_delete_mentions(post, auth_token):
    post_id = post["post"]["id"]
    community_name = post["community"]["name"]
    
    url = f"{LEMMY_API_BASE_URL}/comment/list?post_id={post_id}&community_name={community_name}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        comments_data = response.json()["comments"]
        
        # Check each comment for delete requests
        count = 0
        for comment_data in comments_data:
            comment = comment_data["comment"]  # Access the nested comment data
            comment_id = comment["id"]
            comment_content = comment["content"]
            if comment_content == f"{USERNAME_TO_WATCH} deleteThis!":
                count += 1
        return count, post_id  # Return post_id along with the count
    
    return 0, None  # Return None if post_id not found


def post_confirmation_reply(post_id, remaining, auth_token):
    if post_id:
        url = f"{LEMMY_API_BASE_URL}/comment/create"
        headers = {
            "Authorization": f"Bearer {auth_token}"
        }
        data = {
            "post_id": post_id,
            "content": f"Request to delete received. {remaining} more required to remove the post."
        }
        print(f"Attempting to post confirmation on post {post_id}")
        print("Data sent for comment creation:", data)
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Posted confirmation on post {post_id}")
        else:
            print(f"Failed to post confirmation on post {post_id}: {response.status_code}")
    else:
        print("Post ID not found. Unable to post confirmation.")

def delete_post(post_id, auth_token):
    url = f"{LEMMY_API_BASE_URL}/post/delete"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    data = {
        "post_id": post_id
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"Deleted post {post_id}")
    else:
        print(f"Failed to delete post {post_id}: {response.status_code}")

def monitor_community():
    auth_token = authenticate()
    if auth_token:
        posts = get_recent_posts(auth_token, community_name)
        for post in posts:
            count, post_id = check_for_delete_mentions(post, auth_token)  # Get post_id from check_for_delete_mentions
            if count >= 3:
                delete_post(post_id, auth_token)
            elif count > 0:
                remaining = 3 - count
                post_confirmation_reply(post_id, remaining, auth_token)

if __name__ == "__main__":
    monitor_community()

