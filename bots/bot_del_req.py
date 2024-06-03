import requests
import os

LEMMY_API_BASE_URL = "https://lemmy.ca/api/v3"
community_name = "botland"  # Update this to the community name
USERNAME_TO_WATCH = "@partybot"
LEMMY_USERNAME = os.getenv("LEMMY_USERNAME")
LEMMY_PASSWORD = os.getenv("LEMMY_PASSWORD")

# Define a dictionary to track users who have requested deletion for each post
delete_requests = {}

# Define a constant for the timeframe within which duplicate requests are not allowed (in seconds)
TIMEFRAME = 3600  # 1 hour

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
        users_requested_deletion = delete_requests.get(post_id, set())  # Get users who have requested deletion
        for comment_data in comments_data:
            comment = comment_data["comment"]  # Access the nested comment data
            comment_id = comment["id"]
            parent_id = comment["parent_id"]
            comment_content = comment["content"]
            username = comment["username"]
            if comment_content == f"{USERNAME_TO_WATCH} deleteThis!":
                # Check if the user has already requested deletion for this post within the timeframe
                if username in users_requested_deletion:
                    # Reply to the user indicating that others need to vote as well
                    reply_to_duplicate_request(comment_id, parent_id, auth_token)
                else:
                    count += 1
                    # Add the user to the set of users who have requested deletion
                    users_requested_deletion.add(username)
        # Update the delete_requests dictionary
        delete_requests[post_id] = users_requested_deletion
        return count, post_id  # Return post_id along with the count
    
    return 0, None  # Return None if post_id not found

def reply_to_duplicate_request(comment_id, parent_id, auth_token):
    url = f"{LEMMY_API_BASE_URL}/comment"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    data = {
        "parent_id": parent_id,
        "content": f"You've already requested deletion for this post. Others need to vote as well."
}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"Replied to duplicate delete request on comment {parent_id}")
    else:
        print(f"Failed to reply to duplicate delete request on comment {parent_id}: {response.status_code}")

def delete_post(post_id, auth_token):
    url = f"{LEMMY_API_BASE_URL}/post/delete"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    data = {
        "deleted": True,
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

