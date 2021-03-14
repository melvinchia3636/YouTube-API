# YouTube-Scraping-API
An easy-to-use YouTube API, without any kind of quota, and download any videos on youtube as much as you like. <br />
I'm still working on it, so stay tuned for more updates to come.

## Documentation

### Installing the API
```sh
pip install youtube-scraping-api
```

### Importing the API
```python
from youtube_scraping_api import YouTubeAPI
api = YouTubeAPI()
```

### Search
Returns a collection of search results that match the query parameters specified in the API request.
```python
api.search(query=None, continuation_token=None)
```
**query**: The query string of your search <br />
**continuation_token**: a token for continuing the search. You will find it at the very end of every search result JSON.

### Playlist
Returns a collection of items and metadata of playlists that match the API request parameters.
```python
api.playlist(playlistId=None, continuation_token=None, parseAll=True)
```
**playlistId**: The ID of playlist you want. You can find it at the url of the playlist page. <br />
**continuation_token**: a token for continuing the search. You will find it at the very end of search result JSON if ```parseAll=False.``` <br />
***parseAll***: Parse all items in the playlist. Default set to True.

### Channel (working)
Returns a collection data of channel resources that match the request criteria.
```python
api.channel(channelId=None, username=None)
```
**channelId**: ID of the channel. <br />
**username**: username of the channel user. <br />

### Video
Returns data of the video that matches the video ID.
```python
api.video(videoId)
```
**videoId**: The ID of the videos

### Download Video
```python
video = api.video(videoId)
video.download(itag=None, path=".", log_progress=True, chunk_size=4096, callback_func=None)
```
**itag**: The itag of the video you want to download. Download the best quality if not specified. <br />
**path**: Destination path of your choice. Downloaded videos will go there. <br />
**log_progress**: Wether to show download progressbar or not. Default to True. <br />
**callback_func**: Feature under development

## Version

### 0.0.1 (deleted)
- Not an official release (careless bug found)

### 0.0.2
- Freshly uploaded this package to PyPi

### 0.0.3/0.0.4/0.0.5
- Updated README.md
