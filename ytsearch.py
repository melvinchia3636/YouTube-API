import requests
import json
import itertools
from collections import Counter

class youtubeSearchAPI(requests.Session):
	def __init__(self):
		super().__init__()
		raw = self.get('https://www.youtube.com').text
		self.headers = {'Content-type': 'text/html,application/json', 'accept-language': 'en-US'}
		self.APItoken = self.findSnippet(raw, "innertubeApiKey", ',', (3, 1))
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
		
		self.getThumbnail = lambda videoId: dict(map(lambda i: (i[0], i[1].format(videoId)), self._thumbnailDict.items()))
	
	def searchDict(self, partial, key):
		if isinstance(partial, dict):
			for k, v in partial.items():
				if k == key:
					yield v
				else:
					for o in self.searchDict(v, key):
						yield o
		elif isinstance(partial, list):
			for i in partial:
				for o in self.searchDict(i, key):
					yield o

	@staticmethod
	def findSnippet(text, snippet, end_delimeter, skip=(0, 0)):
		start = text.find(snippet)
		if start == -1: return start
		end = text.find(end_delimeter, start)
		return text[start+len(snippet)+skip[0]:end-skip[1]]

	def parsePlaylistVideos(self, data):
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

	def parseShelfVideos(self, data):
			videos = next(self.searchDict(data, 'items'))
			return self.cleanupData(videos)
	
	def parseVideo(self, data):
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
			'thumbnails': self.getThumbnail(data['videoId'])
		}

	def parseMix(self, data):
		return {
			'type': 'mix',
			'playlist_id': data["playlistId"],
			'title': data['title']['simpleText'],
			'video_count': ''.join(i['text'] for i in data["videoCountShortText"]['runs']),
			'videos': self.parsePlaylistVideos(data),
			'thumbnails': data['thumbnail']['thumbnails']
		}

	def parseShelf(self, data):
		return {
			'type': 'shelf',
			'title': data['title']['simpleText'],
			'videos': self.parseShelfVideos(data)
		}

	def parseLifeStream(self, data):
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
			'thumbnails': self.getThumbnail(data['videoId'])
		}

	def parseChannel(self, data):
		return {
			'type': 'channel',
			'channel_id': data['channelId'],
			'url': data["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
			'name': data['title']['simpleText'],
			'description': ''.join(i['text'] for i in data["descriptionSnippet"]['runs']) if "descriptionSnippet" in data else None,
			'video_count': int(data["videoCountText"]['runs'][0]['text'].split()[0].replace(',', '')),
			'subscriber_count': (int(data["subscriberCountText"]["simpleText"].split()[0]) if data["subscriberCountText"]["simpleText"].split()[0].isdigit() else data["subscriberCountText"]["simpleText"].split()[0]) if "subscriberCountText" in data else None,
			'thumbnails': data['thumbnail']['thumbnails']
		}

	def parsePlaylist(self, data):
		return {
			'type': 'playlist',
			'playlist_id': data["playlistId"],
			'title': data['title']['simpleText'],
			'video_count': int(data["videoCount"]),
			'videos': self.parsePlaylistVideos(data)
		}

	def parseSearchRefinementCard(self, data):
		return {
			'type': 'search_refinement_card',
			'query': ''.join(i['text'] for i in data["query"]['runs']),
			'url': next(self.searchDict(data, "url")),
			'thumbnails': data['thumbnail']['thumbnails']
		}

	def parseHorizontalCardList(self, data):
		title = next(self.searchDict(data["header"], "title"))
		if 'simpleText' in title: title = title['simpleText']
		elif 'runs' in title: title = ''.join(i['text'] for i in title['runs'])
		else: title = None
		return {
			'type': 'card_list',
			'title': title,
			'cards': self.cleanupData(data['cards'])
		}

	def cleanupData(self, data):
		result = []
		for i in data:
			typeOfRenderer = list(i.keys())[0]
			each = i[typeOfRenderer]
			eachFinal = i
			try: typeOfRenderer = 'liveStreamRenderer' if each["badges"][0]["metadataBadgeRenderer"]["label"] == "LIVE NOW" else typeOfRenderer
			except: pass
			if typeOfRenderer == 'videoRenderer':
				eachFinal = self.parseVideo(each)
			elif typeOfRenderer == "radioRenderer":
				eachFinal = self.parseMix(each)
			elif typeOfRenderer == 'shelfRenderer':
				eachFinal = self.parseShelf(each)
			elif typeOfRenderer == 'liveStreamRenderer':
				eachFinal = self.parseLifeStream(each)
			elif typeOfRenderer == "channelRenderer":
				eachFinal = self.parseChannel(each)
			elif typeOfRenderer == "playlistRenderer":
				eachFinal = self.parsePlaylist(each)
			elif typeOfRenderer == "horizontalCardListRenderer":
				eachFinal = self.parseHorizontalCardList(each)
			elif typeOfRenderer == "searchRefinementCardRenderer":
				eachFinal = self.parseSearchRefinementCard(each)
			result.append(eachFinal)
		return result

	def getStatics(self, result):
		return dict(Counter(list(map(lambda i: i['type'], result))))

	def search(self, query):
		html = self.get('https://www.youtube.com/results?reload=9&search_query='+'+'.join(query.split())).text
		response = json.loads(self.findSnippet(html, 'var ytInitialData = ', '</script>', (0, 1)))
		result = {'items': []}
		try: nextCT = next(self.searchDict(response, 'token'))
		except: nextCT = None
		result['continuation_token'] = nextCT
		data = [next(self.searchDict(i, "contents")) for i in self.searchDict(response,"itemSectionRenderer")]
		result['items'] = list(itertools.chain(*[self.cleanupData(i) for i in data]))
		result['statics'] = self.getStatics(result['items'])
		if not result: print(response)
		return result

	def searchWithContinuation(self, continuation_token):
		if not continuation_token: return {}
		self._data['continuation'] = continuation_token

		response = self.post('https://www.youtube.com/youtubei/v1/search?key='+self.APItoken, json=self._data).json()

		result = {'items': []}
		try: nextCT = next(self.searchDict(response, 'token'))
		except: nextCT = None
		result['continuation_token'] = nextCT
		data = next(self.searchDict(response, "contents"))
		result['items'] = self.cleanupData(data)
		result['statics'] = self.getStatics(result['items'])
		if not result: print(response)
		return result

if __name__ == '__main__':
	api = youtubeSearchAPI()
	result = [api.search('ed sheeran photograph')]
	for i in range(10):
		continuation = result[-1]['continuation_token']
		result.append(api.searchWithContinuation(continuation))
		print(i)
	json.dump(result, open('example', 'w'), indent=4)