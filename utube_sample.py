import streamlit as st
import pandas as pd
import pymongo
import mysql.connector as sql
from googleapiclient.discovery import build
import json
from googleapiclient.errors import HttpError
import numpy as np
import datetime
import re

def check_channel_id(channel_id):
    try:
        response = youtube.channels().list(part="snippet", id=channel_id).execute()
        if "items" in response and len(response["items"]) > 0:
            return True
        else:
            return False
    except HttpError as e:
        st.error(f"Error occurred while checking channel ID: {e}")
        return False


def get_channel_info(channel_id):
    try:
        response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()
        if 'items' in response and len(response['items']) > 0:
            channel = response['items'][0]
            channel_name = channel['snippet']['title']
            subscribers_count = channel['statistics']['subscriberCount']
            country = channel['snippet'].get('country', 'N/A')
            total_videos = channel['statistics']['videoCount']
            return channel_name, subscribers_count, country, total_videos
        else:
            return None
    except HttpError as e:
        st.error(f"An error occurred: {e}")


def get_channel_details(channel_id):
    channel_data = []
    response = youtube.channels().list(
        part='snippet,contentDetails,statistics',
        id=channel_id
    ).execute()
    for item in response['items']:
        snippet = item['snippet']
        content_details = item['contentDetails']
        statistics = item['statistics']
        data = {
            'Channel_id': channel_id[:],
            'Channel_name': snippet['title'],
            'Playlist_id': content_details['relatedPlaylists']['uploads'],
            'Subscribers': statistics['subscriberCount'],
            'Views': statistics['viewCount'],
            'Total_videos': statistics['videoCount'],
            'Description': snippet['description'],
            'Country': snippet.get('country')
        }
        channel_data.append(data)
    return channel_data


def get_channel_videos(channel_id):
    video_ids = []
    channel_response = youtube.channels().list(
        id=channel_id,
        part='contentDetails'
    ).execute()
    uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']   
    next_page_token = None    
    while True:
        playlist_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part='snippet',
            maxResults=50,
            pageToken=next_page_token
        ).execute()        
        for item in playlist_response['items']:
            video_ids.append(item['snippet']['resourceId']['videoId'])            
        next_page_token = playlist_response.get('nextPageToken')        
        if next_page_token is None:
            break    
    return video_ids


def get_video_details(v_ids):
    video_stats = []
    video_id_chunks = [v_ids[i:i+50] for i in range(0, len(v_ids), 50)]
    for chunk in video_id_chunks:
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=','.join(chunk)
        ).execute()       
        for video in response['items']:
            published_date = datetime.datetime.strptime(video['snippet']['publishedAt'], '%Y-%m-%dT%H:%M:%SZ')
            formatted_published_date = published_date.strftime('%Y-%m-%d %H:%M:%S')
            
            def convert_duration_to_mysql_format(duration):
                duration_pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
                matches = duration_pattern.match(duration)
                hours = int(matches.group(1)) if matches.group(1) else 0
                minutes = int(matches.group(2)) if matches.group(2) else 0
                seconds = int(matches.group(3)) if matches.group(3) else 0

                # Format the duration as HH:MM:SS
                duration_mysql_format = '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
                return duration_mysql_format

            video_details = {
                'Channel_name': video['snippet']['channelTitle'],
                'Channel_id': video['snippet']['channelId'],
                'Video_id': video['id'],
                'Title': video['snippet']['title'],
                'Tags': video['snippet'].get('tags'),
                'Thumbnail': video['snippet']['thumbnails']['default']['url'],
                'Description': video['snippet']['description'],
                'Published_date': formatted_published_date,
                'Duration': convert_duration_to_mysql_format(video['contentDetails']['duration']),
                'Views': video['statistics']['viewCount'],
                'Likes': video['statistics'].get('likeCount'),
                'Comments': video['statistics'].get('commentCount'),
                'Favorite_count': video['statistics']['favoriteCount'],
                'Definition': video['contentDetails']['definition'],
                'Caption_status': video['contentDetails']['caption']
            }
            video_stats.append(video_details)    
    return video_stats

def convert_datetime_to_mysql_format(datetime_str):
    datetime_obj = datetime.datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%SZ')
    mysql_datetime_str = datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
    return mysql_datetime_str

def get_comments_details(v_id):
    comment_data = []
    next_page_token = None   
    while True:
        try:
            response = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=v_id,
                maxResults=100,
                pageToken=next_page_token
            ).execute()
            for comment_thread in response['items']:
                comment = comment_thread['snippet']['topLevelComment']['snippet']
                data = {
                    'Comment_id': comment_thread['id'],
                    'Video_id': comment['videoId'],
                    'Comment_text': comment['textDisplay'],
                    'Comment_author': comment['authorDisplayName'],
                    'Comment_posted_date': convert_datetime_to_mysql_format(comment['publishedAt']),
                    'Like_count': comment['likeCount'],
                    'Reply_count': comment_thread['snippet']['totalReplyCount']
                }
                comment_data.append(data)
            next_page_token = response.get('nextPageToken')
            if next_page_token is None:
                break
        except Exception as e:
            print(f"An error occurred: {e}")
            break
    return comment_data


def channels_name():   
    channel_names = []
    for i in db.channels_details.find():
        channel_names.append(i['Channel_name'])
    return channel_names


def insert_into_channels():
    collections = db.channels_details    
    query = """INSERT INTO channels VALUES(%s,%s,%s,%s,%s,%s,%s,%s)"""
    for i in collections.find({"Channel_name" : user_inp},{'_id' : 0}):
        mycursor.execute(query,tuple(i.values()))
        mydb.commit()


def insert_into_videos():
    collections1 = db.videos_details
    query1 = """INSERT INTO videos VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    for i in collections1.find({"Channel_name" : user_inp},{'_id' : 0}):
        tags = ",".join(i.get("Tags", []))[:255] if isinstance(i.get("Tags"), list) else ""
        i["Tags"] = tags
        mycursor.execute(query1,tuple(i.values()))
        mydb.commit()


def insert_into_comments():
    collections1 = db.videos_details
    collections2 = db.comments_details
    query2 = """INSERT INTO comments VALUES(%s,%s,%s,%s,%s,%s,%s)"""
    for vid in collections1.find({"Channel_name" : user_inp},{'_id' : 0}):
        for i in collections2.find({'Video_id': vid['Video_id']},{'_id' : 0}):
            mycursor.execute(query2,tuple(i.values()))
            mydb.commit()


question_list = [
    "What are the names of all the videos and their corresponding channels?",
    "Which channels have the most number of videos, and how many videos do they have?",
    "What are the top 10 most viewed videos and their respective channels?",
    "How many comments were made on each video, and what are their corresponding video names?",
    "Which videos have the highest number of likes, and what are their corresponding channel names?",
    "What is the total number of likes and dislikes for each video, and what are their corresponding video names?",
    "What is the total number of views for each channel, and what are their corresponding channel names?",
    "What are the names of all the channels that have published videos in the year 2022?",
    "What is the average duration of all videos in each channel, and what are their corresponding channel names?",
    "Which videos have the highest number of comments, and what are their corresponding channel names?"
]


def execute_query(question_index):
    if question_index == 0:
        mycursor.execute("""SELECT title AS Video_Title, channel_name AS Channel_Name FROM videos ORDER BY channel_name""")
    elif question_index == 1:
        mycursor.execute("""SELECT channel_name AS Channel_Name, total_videos AS Total_Videos FROM channels ORDER BY total_videos DESC""")
    elif question_index == 2:
        mycursor.execute("""SELECT channel_name AS Channel_Name, title AS Video_Title, views AS Views FROM videos ORDER BY views DESC LIMIT 10""")
    elif question_index == 3:
        mycursor.execute("""SELECT a.video_id AS Video_id, a.title AS Video_Title, b.Total_Comments FROM videos AS a LEFT JOIN (SELECT video_id,COUNT(comment_id) AS Total_Comments FROM comments GROUP BY video_id) AS b ON a.video_id = b.video_id ORDER BY b.Total_Comments DESC""")
    elif question_index == 4:
        mycursor.execute("""SELECT channel_name AS Channel_Name,title AS Title,likes AS Likes_Count  FROM videos ORDER BY likes DESC LIMIT 3""")
    elif question_index == 5:
        mycursor.execute("""SELECT title AS Title, likes AS Likes_Count FROM videos ORDER BY likes DESC""")
    elif question_index == 6:
        mycursor.execute("""SELECT channel_name AS Channel_Name, views AS Views FROM channels ORDER BY views DESC""")
    elif question_index == 7:
        mycursor.execute("""SELECT channel_name AS Channel_Name FROM videos WHERE published_date LIKE '2022%' GROUP BY channel_name ORDER BY channel_name""")
    elif question_index == 8:
        st.warning("We apologize for any inconvenience caused. The problem is being addressed and will be resolved soon. Thank you for your patience.")
        mycursor.execute("""SELECT channel_name AS Channel_Name, AVG(duration)/60 AS "Average_Video_Duration (mins)" FROM videos GROUP BY channel_name ORDER BY AVG(duration)/60 DESC""")
    elif question_index == 9:
        mycursor.execute("""SELECT channel_name AS Channel_Name,video_id AS Video_ID,comments AS Comments FROM videos ORDER BY comments DESC LIMIT 3""")
        
    df = pd.DataFrame(mycursor.fetchall(), columns=mycursor.column_names)
    st.write(df)



#connecting with Youtube API ,MySQL & MongoDB Atlas  
api_key = "your_api_key"
youtube = build('youtube','v3',developerKey=api_key)

mydb = sql.connect(host="host_name",
                   user="user_name",
                   password="your_password",
                   database= "database_name"
                  )
mycursor = mydb.cursor(buffered=True)


client = pymongo.MongoClient("your_MongoDB_atlas_server_ID") #Login to your MongoDB Atlas and click connect option in databases and click drivers and copy the link under title "Add your connection string into your application code"
db = client.Youtube_Data


# Page Configration
st.set_page_config(page_title= "YouTube Data Harvesting and Warehousing",
                   layout= "wide",
                   initial_sidebar_state= "expanded")

selected_menu = st.sidebar.radio("Select a Menu", ("Fetch & Save","Migrate","Analyze data!"))

   
# Fetch & Save page:
channel_details_count = db["channels_details"].count_documents({})
if selected_menu == "Fetch & Save":
    
    st.header("YouTube Data Harvesting and Warehousing using SQL, MongoDB and Streamlit")
    st.subheader("Unleash the Power of MongoDB Atlas: Seamlessly Fetch and Store YouTube Data!")
    with st.expander("See How to fetch the YouTube channel ID"):
        st.info("To fetch the YouTube Channel ID from a desired YouTube channel: Go to the channel\'s webpage --> Press Ctrl+U (or Command+Option+U on Mac) to view the page source --> Press Ctrl+F (or Command+F on Mac) to open the search tab --> Search for '?channel' to find and copy the YouTube Channel ID from the highlighted section")

    channel_id = st.text_input("Enter the YouTube channel ID for data retrieval and saving!")
    if channel_id:
        if check_channel_id(channel_id):
            st.success("The channel ID you have provided is valid!!")
            st.info("You can save a maximum of 10 channels data.As of now the Number of channels Data Saved to MongoDB Atlas: {}. ".format(channel_details_count))
            overview = st.checkbox("Please take a moment to review the overview of the provided channel IDs' data. If the information appears to be correct, you may proceed with fetching and saving the data")
            if overview:
                channel_name, subscribers_count, country, total_videos = get_channel_info(channel_id)
                if channel_name:
                    st.write(f"Fetched Channel Name: {channel_name}")
                    st.write(f"Fetched Subscribers: {subscribers_count}")
                    st.write(f"Fetched Country: {country}")
                    st.write(f"Fetched Total Videos: {total_videos}")
        else:
            st.warning("oops, the channel ID appears to be invalid.")
            

    if st.button("Fetch & Save"):
        if channel_details_count >= 10:
            st.warning("You have already saved the maximum number of channels (10).")
        else:
            channel_details = get_channel_details(channel_id)
            v_ids = get_channel_videos(channel_id)
            vid_details = get_video_details(v_ids)
            merged_data = channel_details + vid_details 
            st.info("Please use the first arrow symbol to minimize and to maximize the JSON file!")
            st.json(json.dumps(merged_data, indent=4))

            with st.spinner('Fetching & saving channels data in MongoDB Atlas...'):
                channel_details = get_channel_details(channel_id)
                v_ids = get_channel_videos(channel_id)
                vid_details = get_video_details(v_ids)                
                
                def get_comments():
                    comment_details = []
                    for video_id in v_ids:
                        comments = get_comments_details(video_id)
                        comment_details.extend(comments)
                    return comment_details

                comm_details = get_comments()

                channel_collection = db.channels_details
                channel_collection.insert_many(channel_details)

                video_collection = db.videos_details
                video_collection.insert_many(vid_details)

                comment_collection = db.comments_details
                comment_collection.insert_many(comm_details)

                channel_details_count = channel_collection.count_documents({})
                st.info("The Number of channels Data Saved to MongoDB Atlas: {}. You can save a maximum of 10 channels data".format(channel_details_count))
                st.success("Data Successfully saved in MongoDB Atlas!!")

# Migrate page:                
if selected_menu == "Migrate":
    st.header("YouTube Data Harvesting and Warehousing using SQL, MongoDB and Streamlit")
    st.subheader("Select a channel to Migrate it's data to MySQL")
        
    channel_names = channels_name()
    user_inp = st.selectbox("Select a channel that needs to be migrated!",options= channel_names)

    progress_bar = st.progress(0)
    st.caption('It may take some time to migrate the data : so sit back and relax until the migration is successful')

    if st.button("Migrate"):        
        progress_bar.progress(0)
        insert_into_channels()
        progress_bar.progress(33, text="30% of the migartion is successful")
        insert_into_videos()
        progress_bar.progress(66, text="70% of the migartion is successful")
        insert_into_comments()
        progress_bar.progress(100)
        st.success("Data migrated from MongoDB Atlas to MySQL successfully!!")


# Analyze page:        
if selected_menu == "Analyze data!":
    st.header("YouTube Data Harvesting and Warehousing using SQL, MongoDB and Streamlit")
    st.subheader("Select a Question to Analyze the data of the migrated channel!")
    
    questions = st.selectbox('Questions', question_list)
    question_index = question_list.index(questions)
    random_selection_expander = st.expander("Will I select a question randomly?")
    with random_selection_expander:
        if st.button("Random Selection"):
            random_number = np.random.randint(0, len(question_list))
            st.write(random_number)
            question_index = random_number
            selected_question = question_list[question_index]
            st.subheader(selected_question)
            execute_query(question_index)

    if st.button("Analyze"):
        execute_query(question_index)
        
#while creating Duration column in MySQL database, if an error occurs then convert it's datatype from INT to VARCHAR(255)
