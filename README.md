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

### Playlist
Returns a collection of items and metadata of playlists that match the API request parameters.
```python
api.playlist(playlistId=None, continuation_token=None, parseAll=True)
```

### Channel (working)
Returns a collection data of channel resources that match the request criteria.
```python
api.channel(channelId=None, username=None)
```

### Video
Parse the data of the video that matches the video ID.
```python
video = api.video(videoId)

#get the data of the video
video.get_json()
```

### Download Video
Download the video with whatever resolution you want up to 720p.
```python
video = api.video(videoId)
video.download(itag=None, path=".", log_progress=True, chunk_size=4096, callback_func=None)
```

### Captions
Parse captions available for the video.
```python
video = api.video(videoId)

#query containing every available captions of the video
captions = video.captions

#return the caption that matches the language code. Return default language if language code isn't provided
caption = captions.get_caption(language_code='en')

#return all available translation languages if the caption is translatable
available_translation_language = caption.available_translations

#return the translation of the caption if it's translatable
translated_caption = caption.translate_to('zh-Hant')

#return the caption in string format
caption.string

#return the caption in dictionary format with starting time and duration of each text snippet
caption.dict
```

## Version

### 0.0.1 (deleted)
- Not an official release (careless bug found)

### 0.0.2
- Freshly uploaded this package to PyPi

### 0.0.3/0.0.4/0.0.5
- Updated README.md


### 0.1.0
- Video caption feature added

### 0.1.1
- Updated README.md
