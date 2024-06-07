import requests
import os
from datetime import datetime, timedelta

LEMMY_API_BASE_URL = "https://lemmy.ca/api/v3"
community_name = "botland"  # Update this to the community name
USERNAME_TO_WATCH = "@partybot"
LEMMY_USERNAME = os.getenv("LEMMY_USERNAME")
LEMMY_PASSWORD = os.getenv("LEMMY_PASSWORD")

# Dictionary to track delete requests from users
delete_requests = {}

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
            creator_id = comment["creator_id"]  # Access the ID of the comment creator
            
            if comment_content == f"{USERNAME_TO_WATCH} deleteThis!":
                # Check if user has already requested to delete within the last hour
                if creator_id not in delete_requests or datetime.now() - delete_requests[creator_id] > timedelta(hours=1):
                    delete_requests[creator_id] = datetime.now()
                    count += 1
                    user_info = get_user_info(auth_token, creator_id)
                    if user_info:
                        post_confirmation_reply(post_id, remaining=0, auth_token=auth_token, user_id=creator_id, user_name=user_info.get("name"), already_requested=True)
                else:
                    # If user has already requested, reply with a message indicating so
                    user_info = get_user_info(auth_token, creator_id)
                    if user_info:
                        post_confirmation_reply(post_id, remaining=0, auth_token=auth_token, user_id=creator_id, user_name=user_info.get("name"), already_requested=True)
        return count, post_id  # Return post_id along with the count
    
    return 0, None  # Return None if post_id not found

def post_confirmation_reply(post_id, remaining, auth_token, user_id, user_name, already_requested=False):
    if post_id:
        url = f"{LEMMY_API_BASE_URL}/comment"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        if already_requested:
            content = f"User {user_name} has already requested to delete this post. Others need to reply as well to remove the post."
        else:
            content = f"Request to delete received. {remaining} more required to remove the post."
        
        data = {
            "post_id": post_id,
            "content": content
        }
        
        print("Data sent for comment creation:", data)  # Print out the request data
        response = requests.post(url, headers=headers, json=data)
        print("Response content:", response.content)  # Print out the response content
        
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
        "deleted": True,
        "post_id": post_id
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"Deleted post {post_id}")
    else:
        print(f"Failed to delete post {post_id}: {response.status_code}")

def get_user_info(auth_token, user_id):
    url = f"{LEMMY_API_BASE_URL}/user/byId/{user_id}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("user")
    else:
        print(f"Failed to fetch user info for user ID {user_id}: {response.status_code}")
        return None

def monitor_community():
    auth_token = authenticate()
    if auth_token:
        posts = get_recent_posts(auth_token, community_name)
        for post in posts:
            count, post_id = check_for_delete_mentions(post, auth_token)  # Get post_id from check_for_delete_mentions
            if isinstance(count, int):  # Check if count is an integer (i.e., not an error message)
                if count >= 3:
                    delete_post(post_id, auth_token)
                elif count > 0:
                    remaining = 3 - count
                    post_confirmation_reply(post_id, remaining, auth_token)
            else:
                print("Error occurred while processing delete requests:", count)

if __name__ == "__main__":
    monitor_community()



