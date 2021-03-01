import requests
import json
import itertools
from collections import Counter
from bs4 import BeautifulSoup

class YouTubeAPI(requests.Session):
	def __init__(self, debug_level='ERROR'):
		super().__init__()
		self._debug_level = debug_level
		raw = self.get('https://www.youtube.com').text
		self.headers = {
			'Content-type': 'text/html,application/json', 
			'accept-language': 'en-US'
		}
		self._data = {
			"context": {
				"client": {
					"clientName": "WEB",
					"clientVersion": "2.20201220.08.00",
				},
				"user": {
					"lockedSafetyMode": False,
				}
			}
		}
		self._thumbnailDict = {
			"default": 'https://i.ytimg.com/vi/{}/default.jpg',
			"medium": 'https://i.ytimg.com/vi/{}/mqdefault.jpg',
			"high": 'https://i.ytimg.com/vi/{}/hqdefault.jpg',
			"standard": 'https://i.ytimg.com/vi/{}/sddefault.jpg',
			"maxres": 'https://i.ytimg.com/vi/{}/maxresdefault.jpg'
		}
		
		self._getThumbnail = lambda videoId: dict(map(lambda i: (i[0], i[1].format(videoId)), self._thumbnailDict.items()))
		self._getInitialData = lambda html: (self._debug('INFO', 'Start parsing JSON data'), json.loads(self._findSnippet(html, 'var ytInitialData = ', '</script>', (0, 1))), self._debug('SUCCESS', 'JSON data parsed successfully'))[1]
		self._revealRedirectUrl = lambda url: BeautifulSoup(requests.get(url, headers=self.headers).content, 'lxml').find('div', {'id': 'redirect-action-container'}).find('a')['href']
		
		self.DEBUG_LEVEL = dict([i[::-1] for i in enumerate(['INFO', 'SUCCESS', 'WARNING', 'ERROR'])])
		self.API_TOKEN = self._findSnippet(raw, "innertubeApiKey", ',', (3, 1))

		self.SEARCH_BASE_URL = 'https://www.youtube.com/results?search_query='
		self.SEARCH_CONTINUATION_URL = 'https://www.youtube.com/youtubei/v1/search?key='
		self.PLAYLIST_BASE_URL = 'https://www.youtube.com/playlist?list='
		self.PLAYLIST_CONTINUTION_URL = 'https://www.youtube.com/youtubei/v1/browse?key='
		self.CHANNEL_USERNAME_URL = 'https://www.youtube.com/user/'
		self.CHANNEL_ID_URL = 'https://www.youtube.com/channel/'

		self.RENDERER_PARSER = {k:self.logException(v) for k, v in {
				'videoRenderer': self._parseVideo,
				'radioRenderer': self._parseMix,
				'shelfRenderer': self._parseShelf,
				'liveStreamRenderer': self._parseLifeStream,
				'channelRenderer': self._parseChannel,
				'playlistRenderer': self._parsePlaylist,
				'horizontalCardListRenderer': self._parseHorizontalCardList,
				'searchRefinementCardRenderer': self._parseSearchRefinementCard,
				'richItemRenderer': lambda x: self._cleanupData([x['content']])[0],
				'backgroundPromoRenderer': self._parseBackgroundPromo,
				'messageRenderer': self._parseMessage,
				'promotedSparklesTextSearchRenderer': lambda x: self._parsePromotedSparklesTextSearch(x['content']),
				'playlistVideoListRenderer': self._parsePlaylistContent,
				'playlistVideoRenderer': self._parsePlaylistVideo,
				'carouselAdRenderer': self._parseCarouselAds
			}.items()}

	def logException(*outer_args):
		def check(*args, **kwargs):
			try: 
				return outer_args[-1](*args, **kwargs)
			except Exception as e:
				print('[-] ERROR:', e)
		return check

	def _searchDict(self, partial, key):
		if isinstance(partial, dict):
			for k, v in partial.items():
				if k == key:
					yield v
				else:
					for o in self._searchDict(v, key):
						yield o
		elif isinstance(partial, list):
			for i in partial:
				for o in self._searchDict(i, key):
					yield o

	@staticmethod
	def _findSnippet(text, snippet, end_delimeter, skip=(0, 0)):
		start = text.find(snippet)
		if start == -1: return start
		end = text.find(end_delimeter, start)
		return text[start+len(snippet)+skip[0]:end-skip[1]]

	def _parsePlaylistVideos(self, data):
			videos = data['videos']
			result = []
			for i in videos:
				each = i["childVideoRenderer"]
				eachFinal = {
					'type': 'video',
					'video_id': each['videoId'],
					'title': each['title']['simpleText'],
					'length': each["lengthText"]["simpleText"]
				}
				result.append(eachFinal)
			return result

	def _parseShelfVideos(self, data):
			videos = next(self._searchDict(data, 'items'))
			return self._cleanupData(videos)
	
	def _parseVideo(self, data):
		return {
			'type': 'video',
			'video_id': data["videoId"],
			'title': ''.join(i['text'] for i in data['title']['runs']),
			'description': ''.join(i['text'] for i in data["descriptionSnippet"]['runs']) if "descriptionSnippet" in data else None,
			'publish_time': data["publishedTimeText"]["simpleText"] if "publishedTimeText" in data else None,
			'length': data["lengthText"]["simpleText"],
			'views': int(data["viewCountText"]["simpleText"].split()[0].replace(',', '')) if data["viewCountText"]["simpleText"].split()[0].replace(',', '').isdigit() else None,
			'author': {
				'name': data['ownerText']['runs'][0]['text'],
				'url': data['ownerText']['runs'][0]["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
				'channel_id': data['ownerText']['runs'][0]["navigationEndpoint"]["browseEndpoint"]["browseId"]
			},
			'thumbnails': self._getThumbnail(data['videoId'])
		}

	def _parseMix(self, data):
		return {
			'type': 'mix',
			'playlist_id': data["playlistId"],
			'title': data['title']['simpleText'],
			'video_count': ''.join(i['text'] for i in data["videoCountShortText"]['runs']),
			'videos': self._parsePlaylistVideos(data),
			'thumbnails': data['thumbnail']['thumbnails']
		}

	def _parseShelf(self, data):
		return {
			'type': 'shelf',
			'title': data['title']['simpleText'],
			'videos': self._parseShelfVideos(data)
		}

	def _parseLifeStream(self, data):
		return {
			'type': 'live_stream',
			'video_id': data['videoId'],
			'title': ''.join(i['text'] for i in data['title']['runs']),
			'description': ''.join(i['text'] for i in data["descriptionSnippet"]['runs']) if "descriptionSnippet" in data else None,
			'watching_count': int(data["viewCountText"]['runs'][0]['text'].replace(',', '')),
			'author': {
				'name': data['ownerText']['runs'][0]['text'],
				'url': data['ownerText']['runs'][0]["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
				'channel_id': data['ownerText']['runs'][0]["navigationEndpoint"]["browseEndpoint"]["browseId"]
			},
			'thumbnails': self._getThumbnail(data['videoId'])
		}

	def _parseChannel(self, data):
		return {
			'type': 'channel',
			'channel_id': data['channelId'],
			'url': data["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
			'name': data['title']['simpleText'],
			'description': ''.join(i['text'] for i in data["descriptionSnippet"]['runs']) if "descriptionSnippet" in data else None,
			'video_count': int(data["videoCountText"]['runs'][0]['text'].split()[0].replace(',', '')) if "videoCountText" in data else None,
			'subscriber_count': (int(data["subscriberCountText"]["simpleText"].split()[0]) if data["subscriberCountText"]["simpleText"].split()[0].isdigit() else data["subscriberCountText"]["simpleText"].split()[0]) if "subscriberCountText" in data else None,
			'thumbnails': data['thumbnail']['thumbnails']
		}

	def _parsePlaylist(self, data):
		return {
			'type': 'playlist',
			'playlist_id': data["playlistId"],
			'title': data['title']['simpleText'],
			'video_count': int(data["videoCount"]),
			'videos': self._parsePlaylistVideos(data)
		}

	def _parseSearchRefinementCard(self, data):
		return {
			'type': 'search_refinement_card',
			'query': ''.join(i['text'] for i in data["query"]['runs']),
			'url': next(self._searchDict(data, "url")),
			'thumbnails': data['thumbnail']['thumbnails']
		}

	def _parseHorizontalCardList(self, data):
		title = next(self._searchDict(data["header"], "title"))
		if 'simpleText' in title: title = title['simpleText']
		elif 'runs' in title: title = ''.join(i['text'] for i in title['runs'])
		else: title = None
		return {
			'type': 'card_list',
			'title': title,
			'cards': self._cleanupData(data['cards'])
		}
	
	def _parseBackgroundPromo(self, data):
		return {
			'type': 'background_promo',
			'title': ''.join(i['text'] for i in data['title']['runs']),
			'content': ''.join(i['text'] for i in data['bodyText']['runs'])
		}

	def _parseMessage(self, data):
		return {
			'type': 'message',
			'text': ''.join(i['text'] for i in data['text']['runs'])
		}

	def _parsePromotedSparklesTextSearch(self, data):
		return {
			'type': 'promotion',
			'title': data['title']['simpleText'],
			'description': data["descriptionText"]['simpleText'],
			'website': ''.join(i['text'] for i in data["websiteText"]['runs'])
		}

	def _parseCarouselAds(self, data):
		return {
			'type': 'carousel_ads'
		}

	def _parsePlaylistMetadata(self, data):
		self._debug('INFO', 'Start parsing playlist metadata')
		first_data = data['metadata']["playlistMetadataRenderer"]
		second_data = next(self._searchDict(data, "videoOwnerRenderer"))
		video_count, total_views, last_updated = next(self._searchDict(data, "stats"))
		result = {
			'title': first_data['title'],
			'description': first_data['description'] if 'description' in first_data else None,
			'owner': second_data['title']['runs'][0]['text'],
			'video_count': int(video_count['runs'][0]['text'].replace(',', '')),
			'total_views': int(total_views["simpleText"].split()[0].replace(',', '')),
			'last_updated': last_updated['runs'][-1]['text']
		}
		self._debug('INFO', 'Playlist name: {}'.format(result['title']))
		self._debug('INFO', 'Playlist owner: {}'.format(result['owner']))
		self._debug('INFO', 'Playlist description: {}'.format(result['description']))
		self._debug('INFO', 'Playlist videos count: {}'.format(result['video_count']))
		self._debug('INFO', 'Playlist total views: {}'.format(result['total_views']))
		self._debug('INFO', 'Playlist last updated on: {}'.format(result['last_updated']))
		self._debug('SUCCESS', 'Playlist metadata parsed successfully')
		return result

	def _parsePlaylistContent(self, data):
		return self._cleanupData(data['contents'])

	def _parsePlaylistVideo(self, data):
		return {
			'index': int(data['index']['simpleText']),
			'video_id': data['videoId'],
			'title': ''.join(i['text'] for i in data['title']['runs']),
			'length': data["lengthText"]["simpleText"] if 'lengthText' in data else None,
			'author': {
				'name': data["shortBylineText"]['runs'][0]['text'],
				'url': next(self._searchDict(data["shortBylineText"], "url")),
				'channel_id': next(self._searchDict(data["shortBylineText"], "browseId"))
			} if "shortBylineText" in data else None,
			'thumbnails': self._getThumbnail(data['videoId'])
		}

	@logException
	def _parseContinuationToken(self, data):
		try: nextCT = next(self._searchDict(data, 'token')); self._debug('INFO', 'Continuation token found')
		except: nextCT = None; self._debug('INFO', 'Continuation token not found')
		finally: return nextCT

	@logException
	def _cleanupData(self, data):
		result = []
		for i in data:
			try: typeOfRenderer = list(i.keys())[0]
			except: print(data); raise
			each = i[typeOfRenderer]
			eachFinal = i
			try: typeOfRenderer = 'liveStreamRenderer' if each["badges"][0]["metadataBadgeRenderer"]["label"] == "LIVE NOW" else typeOfRenderer
			except: pass
			if typeOfRenderer == "continuationItemRenderer":
				continue
			eachFinal = self.RENDERER_PARSER[typeOfRenderer](each)
			result.append(eachFinal)
		return result

	@logException
	def _cleanupChannelData(self, data, about_data):
			return {
				'metadata': self._getChannelMetadata(data, about_data)
			}

	@logException
	def _getChannelMetadata(self, data, about_data):
		raw_metadata = data["metadata"]["channelMetadataRenderer"]
		raw_header = data['header']
		try: subscriber_count = next(self._searchDict(raw_header, "subscriberCountText"))['simpleText'].split()[0]
		except: subscriber_count = 'No'
		try: banner = next(self._searchDict(raw_header, 'banner'))['thumbnails']
		except: banner = None
		return {
			'channel_id': raw_metadata["externalId"],
			'username': raw_metadata['title'],
			'description': raw_metadata['description'],
			'subscriber_count': int(subscriber_count) if subscriber_count.isdigit() else None if subscriber_count == 'No' else subscriber_count,
			'is_verified': self._getChannelVerificationStatus(raw_header),
			'keywords': raw_metadata['keywords'],
			'channel_url': raw_metadata["channelUrl"],
			'vanity_channel_url': raw_metadata["vanityChannelUrl"],
			'facebook_profile_id': raw_metadata["facebookProfileId"] if "facebookProfileId" in raw_metadata else None,
			'avatar_thumbnail': raw_metadata['avatar']['thumbnails'][0],
			'banner': banner,
			'header_links': self._getChannelHeaderLinks(raw_header)
		}

	@logException
	def _getChannelHeaderLinks(self, raw_header):
		try:
			raw_header_links = next(self._searchDict(raw_header, "channelHeaderLinksRenderer")).values()
			header_links = [{
				'title': i['title']['simpleText'],
				'icon': i['icon']['thumbnails'][0]['url'],
				'url': self._revealRedirectUrl(i["navigationEndpoint"]["urlEndpoint"]["url"])
			} for i in sum(raw_header_links, [])]
			return header_links
		except:
			return None

	@logException
	def _getChannelVerificationStatus(self, data):
		try:
			if next(self._searchDict(data, 'badges'))[0]["metadataBadgeRenderer"]['tooltip'] == 'Verified':
				return True
			return False
		except: return False

	@logException
	def getStatics(self, result):
		self._debug('INFO', 'Retrieving statics')
		try:
			result = dict(Counter(list(map(lambda i: i['type'], result))))
			self._debug('SUCCESS', 'Statics successfully retrieved')
			return result
		except: 
			self._debug('WARNING', 'Some problem occured when retrieving statics')
			return None

	@logException
	def search(self, query=None, continuation_token=None):
		"""Search YouTube video queries without limitations

		Args:

			Must provide either query or continuation token.

			query ([String], optional): 
				Query string that you want to search on YouTube. Defaults to None.
				Example: "Python for Beginner"

			continuation_token ([String], optional): 
				Continuation token that you found in result JSON data of API searching. Defaults to None.
				Example: "EvIDEhNQeXRob24gZm9yIEJlZ2lubmVyGrwDU0JTQ0FRdHlabk5qVmxNd2RuUmlkNElCQzE5MVVYSktNRlJyV214amdnRUxXakZaWkRkMWNGRnpXRm1DQVF0cmNYUkVOV1J3YmpsRE9JSUJJbEJNYzNsbGIySjZWM2hzTjNCdlREbEtWRlo1Ym1STFpUWXlhV1Z2VGkxTldqT0NBUXRYZG1oUmFHbzBialppT0lJQklsQk1iSEo0UkRCSWRHbGxTR2hUT0ZaNmRVMURabEZFTkhWS09YbHVaVEZ0UlRhQ0FRczBSakp0T1RGbFMyMTBjNElCQzFrNFZHdHZNbGxETldoQmdnRUxiV2hrUlhoNmREZEJibFdDQVF0WFIwcEtTWEowYm1ad2E0SUJDMGt5ZDFWU1JIRnBXR1JOZ2dFTE9FUjJlWGR2VjNZMlprbUNBUXR6ZUZSdFNrVTBhekJvYjRJQkN6aGxlSFE1UnpkNGMzQm5nZ0VMYUVWblR6QTBOMGQ0WVZHQ0FRdEtTbTFqVERGT01rdFJjNElCQzJsQk9HeE1kMjEwUzFGTmdnRUxURWhDUlRaUk9WaHNla21DQVF0TWVsbE9WMjFsTVZjMlVRJTNEJTNEygEbGhdodHRwczovL3d3dy55b3V0dWJlLmNvbSIAGIHg6BgiC3NlYXJjaC1mZWVk"

		Returns:
			[Dictionary]: Massive and clean JSON data of search result
		"""		
		if not (query or continuation_token): self._debug('WARNING', 'Please provide query or continuation token'); return {}
		result = {'items': []}
		if query:
			self._debug('INFO', 'Parsing first page data for "{}"'.format(query))
			html = self.get(self.SEARCH_BASE_URL+'+'.join(query.split())).text
			self._debug('SUCCESS', 'html source code parsed successfully')
			response = self._getInitialData(html)
		elif continuation_token:
			self._debug('INFO', 'Start parsing continuation data')
			self._data['continuation'] = continuation_token
			self._debug('INFO', 'Start parsing JSON data')
			response = self.post(self.SEARCH_CONTINUATION_URL+self.API_TOKEN, json=self._data).json()
			self._debug('SUCCESS', 'JSON data parsed successfully')
		nextCT = self._parseContinuationToken(response)
		result['continuation_token'] = nextCT
		self._debug('INFO', 'Start parsing JSON data content')
		if query:
			data = [next(self._searchDict(i, "contents")) for i in self._searchDict(response,"itemSectionRenderer")]
			result['items'] = list(itertools.chain(*[self._cleanupData(i) for i in data]))
		if continuation_token:
			try: data = next(self._searchDict(response, "contents"))
			except: data = next(self._searchDict(response, "continuationItems"))
			result['items'] = self._cleanupData(data)
		self._debug('SUCCESS', 'JSON data content parsing successfully')
		result['statics'] = self.getStatics(result['items'])
		self._debug('SUCCESS', 'Parsing successfully, returning result')
		return result

	@logException
	def playlist(self, playlistId=None, continuation_token=None, parseAll=True):
		"""Parse metadata and items of any YouTube playlist, without limitation

		Args:
			playlistId ([String], optional): 
				ID of playlist. Defaults to None.
				Example: "PLgENJ0iY3XBiJ0jZ53HT8v9Qa3cch7YEV"

			continuation_token ([String], optional): 
				Continuation token that you found in result of API searching. Defaults to None.
				Example: "4qmFsgJhEiRWTFBMZ0VOSjBpWTNYQmlKMGpaNTNIVDh2OVFhM2NjaDdZRVYaFENBRjZCbEJVT2tOSFVRJTNEJTNEmgIiUExnRU5KMGlZM1hCaUowalo1M0hUOHY5UWEzY2NoN1lFVg%3D%3D"

			parseAll ([Bool], optional): Want to parse all items in playlist? Defaults to True.

		Returns:
			[Dictionary]: Massive and clean JSON data of playlist data
		"""		
		if not (playlistId or continuation_token): self._debug('WARNING', 'Please provide playlist ID or continuation token'); return {}
		if playlistId:
			self._debug('INFO', 'Parsing first page data for {}'.format(playlistId))
			self._debug('INFO', 'Start parsing html source code')
			html = self.get(self.PLAYLIST_BASE_URL+playlistId).text
			self._debug('SUCCESS', 'html source code parsed successfully')
			response = self._getInitialData(html)
			result = {'metadata': self._parsePlaylistMetadata(response), 'items': None}
		elif continuation_token:
			if not continuation_token: return {}, None; self._debug('WARNING', 'Please provide continuation token')
			self._debug('INFO', 'Start scraping continuation data')
			self._data['continuation'] = continuation_token
			self._debug('INFO', 'Start parsing JSON data')
			response = self.post(self.PLAYLIST_CONTINUTION_URL+self.API_TOKEN, json=self._data).json()
			result = {'metadata': None, 'items': None}
			self._debug('SUCCESS', 'JSON data parsed successfully')	
		nextCT = self._parseContinuationToken(response)
		self._debug('INFO', 'Start parsing JSON data content')
		if playlistId: data = next(self._searchDict(response,"itemSectionRenderer"))['contents']
		elif continuation_token: data = next(self._searchDict(response, "continuationItems"))
		result['items'] = self._cleanupData(data)
		self._debug('SUCCESS', 'JSON data content parsing successfully')
		if parseAll: 
			if nextCT: self._debug('INFO', 'Parsing more playlist data')
			else: self._debug('INFO', 'No continuation token, no more parsing needed')
			while nextCT:
				response, nextCT = self.playlist(continuation_token = nextCT)
				result['items'].extend(response['items'])
		self._debug('SUCCESS', 'Parsing successfully, returning result')
		if playlistId: return result
		elif continuation_token: return result, nextCT

	@logException
	def channel(self, channelId=None, username=None):
		if not (channelId or username): self._debug('WARNING', 'Please provide channel ID or username'); return {}
		if channelId: url = (
			self.CHANNEL_ID_URL+channelId, 
			self.CHANNEL_ID_URL+channelId+'/about'
		)
		elif username: url = (
			self.CHANNEL_USERNAME_URL+username, 
			self.CHANNEL_USERNAME_URL+username+'/about'
		)
		response = [self.get(i).text for i in url]
		if '404 Not Found' in response[0]:
			self._debug('ERROR', 'Channel not exist')
			return
		data = (self._getInitialData(i) for i in response)
		result = self._cleanupChannelData(*data)
		return result

	@logException
	def _debug(self, level ,text):
		if self.DEBUG_LEVEL[level] >= self.DEBUG_LEVEL[self._debug_level]:
			if level == 'ERROR':
				print('[-] ERROR:', text)
			elif level == 'WARNING':
				print('[!] WARNING:', text)
			elif level == 'INFO':
				print('[*] INFO:', text)
			elif level == 'SUCCESS':
				print('[+] SUCCESS:', text)

if __name__ == '__main__':
	def SearchAPIExample():
		api = YouTubeAPI(debug_level='INFO')
		result = api.search("Python for Beginner")
		json.dump(result, open('search.json', 'w'), indent=4)

	def PlaylistAPIExample():
		api = YouTubeAPI(debug_level='INFO')
		result = api.playlist('PLgENJ0iY3XBiJ0jZ53HT8v9Qa3cch7YEV')
		json.dump(result, open('playlist.json', 'w'), indent=4)

	def ChannelAPIExample():
		api = YouTubeAPI(debug_level='INFO')
		result = api.channel(username='ThatMumboJumbo')
		json.dump(result, open('channel.json', 'w'), indent=4)

	SearchAPIExample()
	PlaylistAPIExample()
	ChannelAPIExample()
