# YouTube-API
An easy-to-use YouTube API, without any kind of quota.

## Documentation

### Importing The API
```python
from YouTubeAPI import YouTubeAPI
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
**playlistId**: The ID of playlist you want. You can find it at the url of the playlist page. https://www.youtube.com/playlist?list=[Playlist_ID] <br />
**continuation_token**: a token for continuing the search. You will find it at the very end of search result JSON if ```parseAll=False.``` <br />
***parseAll***: Parse all items in the playlist. Default set to True.

### Channel (working)
Returns a collection data of channel resources that match the request criteria.
```python
api.channel(channelId=None, username=None)
```
**channelId**: The ID of channel. <br />
**username**: The username of channel user. <br />
