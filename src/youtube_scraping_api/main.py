import requests
import json
import itertools
from collections import Counter
from bs4 import BeautifulSoup
import os
import string
from urllib.parse import parse_qs
import re
from itertools import chain
from tqdm import tqdm
import sys
import copy

def _logException(*outer_args):
        def check(*args, **kwargs):
            try: 
                return outer_args[-1](*args, **kwargs)
            except Exception as e:
                print("[-] ERROR:", e)
                sys.exit()
        return check

class Cipher:
    def __init__(self, js):
        self.transform_plan = self.get_transform_plan(js)
        var, _ = self.transform_plan[0].split(".")
        self.transform_map = self.get_transform_map(js, var)
        self.js_func_regex = re.compile(r"\w+\.(\w+)\(\w,(\d+)\)")

    def get_signature(self, ciphered_signature):
        signature = list(ciphered_signature)

        for js_func in self.transform_plan:
            name, argument = self.parse_function(js_func)  # type: ignore
            signature = self.transform_map[name](signature, argument)
        return "".join(signature)

    def parse_function(self, js_func: str):
        parse_match = self.js_func_regex.search(js_func)
        if not parse_match:
            raise Exception
        fn_name, fn_arg = parse_match.groups()
        return fn_name, int(fn_arg)

    def regex_search(self, pattern, string, group):
        regex = re.compile(pattern)
        results = regex.search(string)
        if not results:
            raise Exception
        return results.group(group)

    def get_initial_function_name(self, js):
        function_patterns = [
            r"\b[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*encodeURIComponent\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
            r"\b[a-zA-Z0-9]+\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*encodeURIComponent\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
            r'(?:\b|[^a-zA-Z0-9$])(?P<sig>[a-zA-Z0-9$]{2})\s*=\s*function\(\s*a\s*\)\s*{\s*a\s*=\s*a\.split\(\s*""\s*\)',  # noqa: E501
            r'(?P<sig>[a-zA-Z0-9$]+)\s*=\s*function\(\s*a\s*\)\s*{\s*a\s*=\s*a\.split\(\s*""\s*\)',  # noqa: E501
            r'(["\'])signature\1\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(',
            r"\.sig\|\|(?P<sig>[a-zA-Z0-9$]+)\(",
            r"yt\.akamaized\.net/\)\s*\|\|\s*.*?\s*[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*(?:encodeURIComponent\s*\()?\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
            r"\b[cs]\s*&&\s*[adf]\.set\([^,]+\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
            r"\b[a-zA-Z0-9]+\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
            r"\bc\s*&&\s*a\.set\([^,]+\s*,\s*\([^)]*\)\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
            r"\bc\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*\([^)]*\)\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
            r"\bc\s*&&\s*[a-zA-Z0-9]+\.set\([^,]+\s*,\s*\([^)]*\)\s*\(\s*(?P<sig>[a-zA-Z0-9$]+)\(",  # noqa: E501
        ]
        for pattern in function_patterns:
            regex = re.compile(pattern)
            function_match = regex.search(js)
            if function_match:
                return function_match.group(1)
        raise Exception

    def get_transform_plan(self, js):
        name = re.escape(self.get_initial_function_name(js))
        pattern = r"%s=function\(\w\){[a-z=\.\(\"\)]*;(.*);(?:.+)}" % name
        return self.regex_search(pattern, js, group=1).split(";")

    def get_transform_object(self, js, var):
        pattern = r"var %s={(.*?)};" % re.escape(var)
        regex = re.compile(pattern, flags=re.DOTALL)
        transform_match = regex.search(js)
        if not transform_match:
            raise Exception
        return transform_match.group(1).replace("\n", " ").split(", ")

    def get_transform_map(self, js, var):
        transform_object = self.get_transform_object(js, var)
        mapper = {}
        for obj in transform_object:
            # AJ:function(a){a.reverse()} => AJ, function(a){a.reverse()}
            name, function = obj.split(":", 1)
            fn = self.map_functions(function)
            mapper[name] = fn
        return mapper

    def reverse(self, arr, _):
        return arr[::-1]

    def splice(self, arr, b):
        return arr[b:]

    def swap(self, arr, b):
        r = b % len(arr)
        return list(chain([arr[r]], arr[1:r], [arr[0]], arr[r + 1 :]))

    def map_functions(self, js_func):
        mapper = (
            # function(a){a.reverse()}
            (r"{\w\.reverse\(\)}", self.reverse),
            # function(a,b){a.splice(0,b)}
            (r"{\w\.splice\(0,\w\)}", self.splice),
            # function(a,b){var c=a[0];a[0]=a[b%a.length];a[b]=c}
            (r"{var\s\w=\w\[0\];\w\[0\]=\w\[\w\%\w.length\];\w\[\w\]=\w}", self.swap),
            # function(a,b){var c=a[0];a[0]=a[b%a.length];a[b%a.length]=c}
            (
                r"{var\s\w=\w\[0\];\w\[0\]=\w\[\w\%\w.length\];\w\[\w\%\w.length\]=\w}",
                self.swap,
            ),
        )

        for pattern, fn in mapper:
            if re.search(pattern, js_func):
                return fn
        raise Exception

class YouTubeAPI(requests.Session):
    @_logException
    def __init__(self, debug_level="ERROR"):
        super().__init__()
        self._debug_level = debug_level
        try: raw = self.get("https://www.youtube.com").text
        except: raise RuntimeError("Please check your internet connection")
        self.headers = {
            "Content-type": "text/html,application/json", 
            "accept-language": "en-US"
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
            "default": "https://i.ytimg.com/vi/{}/default.jpg",
            "medium": "https://i.ytimg.com/vi/{}/mqdefault.jpg",
            "high": "https://i.ytimg.com/vi/{}/hqdefault.jpg",
            "standard": "https://i.ytimg.com/vi/{}/sddefault.jpg",
            "maxres": "https://i.ytimg.com/vi/{}/maxresdefault.jpg"
        }
        
        self._getThumbnail = lambda videoId: dict(map(lambda i: (i[0], i[1].format(videoId)), self._thumbnailDict.items()))
        self._getInitialData = lambda html: (self._debug("INFO", "Start parsing JSON data"), json.loads(self._findSnippet(html, "var ytInitialData = ", "</script>", (0, 1))), self._debug("SUCCESS", "JSON data parsed successfully"))[1]
        self._getInitialPlayerResponse = lambda html: (self._debug("INFO", "Start parsing JSON data"), json.loads(self._findSnippet(html, "var ytInitialPlayerResponse = ", ";</script>", (0, 1))+"}", strict=False), self._debug("SUCCESS", "JSON data parsed successfully"))[1]
        self._revealRedirectUrl = lambda url: BeautifulSoup(requests.get(url, headers=self.headers).content, "lxml").find("div", {"id": "redirect-action-container"}).find("a")["href"]
        
        self.DEBUG_LEVEL = dict([i[::-1] for i in enumerate(["INFO", "SUCCESS", "WARNING", "ERROR"])])
        self.API_TOKEN = self._findSnippet(raw, "innertubeApiKey", ",", (3, 1))

        self.BASE_URL = "https://www.youtube.com"
        self.SEARCH_BASE_URL = "https://www.youtube.com/results?search_query="
        self.SEARCH_CONTINUATION_URL = "https://www.youtube.com/youtubei/v1/search?key="
        self.PLAYLIST_BASE_URL = "https://www.youtube.com/playlist?list="
        self.PLAYLIST_CONTINUTION_URL = "https://www.youtube.com/youtubei/v1/browse?key="
        self.CHANNEL_USERNAME_URL = "https://www.youtube.com/user/"
        self.CHANNEL_ID_URL = "https://www.youtube.com/channel/"
        self.VIDEO_PLAYER_URL = "https://www.youtube.com/watch?v="
        self.COMMENT_AJAX_URL = 'https://www.youtube.com/comment_service_ajax'

        self.RENDERER_PARSER = {k:_logException(v) for k, v in {
                "videoRenderer": self._parseVideo,
                "radioRenderer": self._parseMix,
                "shelfRenderer": self._parseShelf,
                "liveStreamRenderer": self._parseLifeStream,
                "channelRenderer": self._parseChannel,
                "playlistRenderer": self._parsePlaylist,
                "horizontalCardListRenderer": self._parseHorizontalCardList,
                "searchRefinementCardRenderer": self._parseSearchRefinementCard,
                "richItemRenderer": lambda x: self._cleanupData([x["content"]])[0],
                "backgroundPromoRenderer": self._parseBackgroundPromo,
                "messageRenderer": self._parseMessage,
                "promotedSparklesTextSearchRenderer": lambda x: self._parsePromotedSparklesTextSearch(x["content"]),
                "playlistVideoListRenderer": self._parsePlaylistContent,
                "playlistVideoRenderer": self._parsePlaylistVideo,
                "carouselAdRenderer": self._parseCarouselAds,
                "showingResultsForRenderer": lambda x: None
            }.items()}

        self.video = lambda videoId: _Video(videoId, debug_level = self._debug_level)

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
            videos = data["videos"]
            result = []
            for i in videos:
                each = i["childVideoRenderer"]
                eachFinal = {
                    "type": "video",
                    "video_id": each["videoId"],
                    "title": each["title"]["simpleText"],
                    "length": each["lengthText"]["simpleText"]
                }
                result.append(eachFinal)
            return result

    def _parseShelfVideos(self, data):
            videos = next(self._searchDict(data, "items"))
            return self._cleanupData(videos)
    
    def _parseVideo(self, data):
        return {
            "type": "video",
            "video_id": data["videoId"],
            "title": "".join(i["text"] for i in data["title"]["runs"]),
            "description": "".join(i["text"] for i in data["descriptionSnippet"]["runs"]) if "descriptionSnippet" in data else None,
            "publish_time": data["publishedTimeText"]["simpleText"] if "publishedTimeText" in data else None,
            "length": data["lengthText"]["simpleText"],
            "views": int(data["viewCountText"]["simpleText"].split()[0].replace(",", "")) if data["viewCountText"]["simpleText"].split()[0].replace(",", "").isdigit() else None,
            "author": {
                "name": data["ownerText"]["runs"][0]["text"],
                "url": data["ownerText"]["runs"][0]["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
                "channel_id": data["ownerText"]["runs"][0]["navigationEndpoint"]["browseEndpoint"]["browseId"]
            },
            "thumbnails": self._getThumbnail(data["videoId"])
        }

    def _parseMix(self, data):
        return {
            "type": "mix",
            "playlist_id": data["playlistId"],
            "title": data["title"]["simpleText"],
            "video_count": "".join(i["text"] for i in data["videoCountShortText"]["runs"]),
            "videos": self._parsePlaylistVideos(data),
            "thumbnails": data["thumbnail"]["thumbnails"]
        }

    def _parseShelf(self, data):
        return {
            "type": "shelf",
            "title": data["title"]["simpleText"],
            "videos": self._parseShelfVideos(data)
        }

    def _parseLifeStream(self, data):
        return {
            "type": "live_stream",
            "video_id": data["videoId"],
            "title": "".join(i["text"] for i in data["title"]["runs"]),
            "description": "".join(i["text"] for i in data["descriptionSnippet"]["runs"]) if "descriptionSnippet" in data else None,
            "watching_count": int(data["viewCountText"]["runs"][0]["text"].replace(",", "")),
            "author": {
                "name": data["ownerText"]["runs"][0]["text"],
                "url": data["ownerText"]["runs"][0]["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
                "channel_id": data["ownerText"]["runs"][0]["navigationEndpoint"]["browseEndpoint"]["browseId"]
            },
            "thumbnails": self._getThumbnail(data["videoId"])
        }

    def _parseChannel(self, data):
        return {
            "type": "channel",
            "channel_id": data["channelId"],
            "url": data["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
            "name": data["title"]["simpleText"],
            "description": "".join(i["text"] for i in data["descriptionSnippet"]["runs"]) if "descriptionSnippet" in data else None,
            "video_count": int(data["videoCountText"]["runs"][0]["text"].split()[0].replace(",", "")) if "videoCountText" in data else None,
            "subscriber_count": (int(data["subscriberCountText"]["simpleText"].split()[0]) if data["subscriberCountText"]["simpleText"].split()[0].isdigit() else data["subscriberCountText"]["simpleText"].split()[0]) if "subscriberCountText" in data else None,
            "thumbnails": data["thumbnail"]["thumbnails"]
        }

    def _parsePlaylist(self, data):
        return {
            "type": "playlist",
            "playlist_id": data["playlistId"],
            "title": data["title"]["simpleText"],
            "video_count": int(data["videoCount"]),
            "videos": self._parsePlaylistVideos(data)
        }

    def _parseSearchRefinementCard(self, data):
        return {
            "type": "search_refinement_card",
            "query": "".join(i["text"] for i in data["query"]["runs"]),
            "url": next(self._searchDict(data, "url")),
            "thumbnails": data["thumbnail"]["thumbnails"]
        }

    def _parseHorizontalCardList(self, data):
        title = next(self._searchDict(data["header"], "title"))
        if "simpleText" in title: title = title["simpleText"]
        elif "runs" in title: title = "".join(i["text"] for i in title["runs"])
        else: title = None
        return {
            "type": "card_list",
            "title": title,
            "cards": self._cleanupData(data["cards"])
        }
    
    def _parseBackgroundPromo(self, data):
        return {
            "type": "background_promo",
            "title": "".join(i["text"] for i in data["title"]["runs"]),
            "content": "".join(i["text"] for i in data["bodyText"]["runs"])
        }

    def _parseMessage(self, data):
        return {
            "type": "message",
            "text": "".join(i["text"] for i in data["text"]["runs"])
        }

    def _parsePromotedSparklesTextSearch(self, data):
        return {
            "type": "promotion",
            "title": data["title"]["simpleText"],
            "description": data["descriptionText"]["simpleText"],
            "website": "".join(i["text"] for i in data["websiteText"]["runs"])
        }

    def _parseCarouselAds(self, data):
        return {
            "type": "carousel_ads"
        }

    def _parsePlaylistMetadata(self, data):
        self._debug("INFO", "Start parsing playlist metadata")
        first_data = data["metadata"]["playlistMetadataRenderer"]
        second_data = next(self._searchDict(data, "videoOwnerRenderer"))
        video_count, total_views, last_updated = next(self._searchDict(data, "stats"))
        last_updated = "".join(i["text"] for i in last_updated["runs"])
        if "Last updated on" in last_updated: last_updated = " ".join(last_updated.split()[3:])
        if "Updated" in last_updated: last_updated = " ".join(last_updated.split()[1:])
        result = {
            "title": first_data["title"],
            "description": first_data["description"] if "description" in first_data else None,
            "owner": second_data["title"]["runs"][0]["text"],
            "video_count": int(video_count["runs"][0]["text"].replace(",", "")),
            "total_views": int(total_views["simpleText"].split()[0].replace(",", "")),
            "last_updated": last_updated
        }
        self._debug("INFO", "Playlist name: {}".format(result["title"]))
        self._debug("INFO", "Playlist owner: {}".format(result["owner"]))
        self._debug("INFO", "Playlist description: {}".format(result["description"]))
        self._debug("INFO", "Playlist videos count: {}".format(result["video_count"]))
        self._debug("INFO", "Playlist total views: {}".format(result["total_views"]))
        self._debug("INFO", "Playlist last updated on: {}".format(result["last_updated"]))
        self._debug("SUCCESS", "Playlist metadata parsed successfully")
        return result

    def _parsePlaylistContent(self, data):
        return self._cleanupData(data["contents"])

    def _parsePlaylistVideo(self, data):
        return {
            "index": int(data["index"]["simpleText"]),
            "video_id": data["videoId"],
            "title": "".join(i["text"] for i in data["title"]["runs"]),
            "length": data["lengthText"]["simpleText"] if "lengthText" in data else None,
            "author": {
                "name": data["shortBylineText"]["runs"][0]["text"],
                "url": next(self._searchDict(data["shortBylineText"], "url")),
                "channel_id": next(self._searchDict(data["shortBylineText"], "browseId"))
            } if "shortBylineText" in data else None,
            "thumbnails": self._getThumbnail(data["videoId"])
        }

    @_logException
    def _parseContinuationToken(self, data):
        try: nextCT = next(self._searchDict(data, "token")); self._debug("INFO", "Continuation token found")
        except: nextCT = None; self._debug("INFO", "Continuation token not found")
        finally: return nextCT

    @_logException
    def _cleanupData(self, data):
        result = []
        for i in data:
            try: typeOfRenderer = list(i.keys())[0]
            except: raise
            each = i[typeOfRenderer]
            eachFinal = i
            try: typeOfRenderer = "liveStreamRenderer" if each["badges"][0]["metadataBadgeRenderer"]["label"] == "LIVE NOW" else typeOfRenderer
            except: pass
            if typeOfRenderer == "continuationItemRenderer":
                continue
            eachFinal = self.RENDERER_PARSER[typeOfRenderer](each)
            result.append(eachFinal)
        return result

    @_logException
    def _cleanupChannelData(self, data, about_data):
            return {
                "metadata": self._getChannelMetadata(data, about_data)
            }

    @_logException
    def _getChannelMetadata(self, data, about_data):
        raw_metadata = data["metadata"]["channelMetadataRenderer"]
        raw_header = data["header"]
        try: subscriber_count = next(self._searchDict(raw_header, "subscriberCountText"))["simpleText"].split()[0]
        except: subscriber_count = "No"
        try: banner = next(self._searchDict(raw_header, "banner"))["thumbnails"]
        except: banner = None
        return {
            "channel_id": raw_metadata["externalId"],
            "username": raw_metadata["title"],
            "description": raw_metadata["description"],
            "subscriber_count": int(subscriber_count) if subscriber_count.isdigit() else None if subscriber_count == "No" else subscriber_count,
            "is_verified": self._getChannelVerificationStatus(raw_header),
            "keywords": raw_metadata["keywords"] if "keywords" in raw_metadata else None,
            "channel_url": raw_metadata["channelUrl"],
            "vanity_channel_url": raw_metadata["vanityChannelUrl"],
            "facebook_profile_id": raw_metadata["facebookProfileId"] if "facebookProfileId" in raw_metadata else None,
            "avatar_thumbnail": raw_metadata["avatar"]["thumbnails"][0],
            "banner": banner,
            "header_links": self._getChannelHeaderLinks(raw_header)
        }

    @_logException
    def _getChannelHeaderLinks(self, raw_header):
        try:
            raw_header_links = next(self._searchDict(raw_header, "channelHeaderLinksRenderer")).values()
            header_links = [{
                "title": i["title"]["simpleText"],
                "icon": i["icon"]["thumbnails"][0]["url"],
                "url": self._revealRedirectUrl(i["navigationEndpoint"]["urlEndpoint"]["url"])
            } for i in sum(raw_header_links, [])]
            return header_links
        except:
            return None

    @_logException
    def _getChannelVerificationStatus(self, data):
        try:
            if next(self._searchDict(data, "badges"))[0]["metadataBadgeRenderer"]["tooltip"] == "Verified":
                return True
            return False
        except: return False

    @_logException
    def getStatics(self, result):
        self._debug("INFO", "Retrieving statics")
        try:
            result = dict(Counter(list(map(lambda i: i["type"], result))))
            self._debug("SUCCESS", "Statics successfully retrieved")
            return result
        except: 
            self._debug("WARNING", "Some problem occured when retrieving statics")
            return None

    @_logException
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
        if not (query or continuation_token): self._debug("WARNING", "Please provide query or continuation token"); return {}
        result = {"items": []}
        if query:
            self._debug("INFO", "Parsing first page data for \"{}\"".format(query))
            html = self.get(self.SEARCH_BASE_URL+"+".join(query.split())).text
            self._debug("SUCCESS", "html source code parsed successfully")
            response = self._getInitialData(html)
        elif continuation_token:
            self._debug("INFO", "Start parsing continuation data")
            self._data["continuation"] = continuation_token
            self._debug("INFO", "Start parsing JSON data")
            response = self.post(self.SEARCH_CONTINUATION_URL+self.API_TOKEN, json=self._data).json()
            self._debug("SUCCESS", "JSON data parsed successfully")
        nextCT = self._parseContinuationToken(response)
        result["continuation_token"] = nextCT
        self._debug("INFO", "Start parsing JSON data content")
        if query:
            data = [next(self._searchDict(i, "contents")) for i in self._searchDict(response,"itemSectionRenderer")]
            result["items"] = list(itertools.chain(*[self._cleanupData(i) for i in data]))
        if continuation_token:
            try: data = next(self._searchDict(response, "contents"))
            except: data = next(self._searchDict(response, "continuationItems"))
            result["items"] = self._cleanupData(data)
        self._debug("SUCCESS", "JSON data content parsing successfully")
        result["statics"] = self.getStatics(result["items"])
        self._debug("SUCCESS", "Parsing successfully, returning result")
        return result

    @_logException
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
        if not (playlistId or continuation_token): self._debug("WARNING", "Please provide playlist ID or continuation token"); return {}
        if playlistId:
            self._debug("INFO", "Parsing first page data for {}".format(playlistId))
            self._debug("INFO", "Start parsing html source code")
            html = self.get(self.PLAYLIST_BASE_URL+playlistId).text
            self._debug("SUCCESS", "html source code parsed successfully")
            response = self._getInitialData(html)
            result = {"metadata": self._parsePlaylistMetadata(response), "items": None}
        elif continuation_token:
            if not continuation_token: return {}, None; self._debug("WARNING", "Please provide continuation token")
            self._debug("INFO", "Start scraping continuation data")
            self._data["continuation"] = continuation_token
            self._debug("INFO", "Start parsing JSON data")
            response = self.post(self.PLAYLIST_CONTINUTION_URL+self.API_TOKEN, json=self._data).json()
            result = {"metadata": None, "items": None}
            self._debug("SUCCESS", "JSON data parsed successfully")	
        nextCT = self._parseContinuationToken(response)
        self._debug("INFO", "Start parsing JSON data content")
        if playlistId: data = next(self._searchDict(response,"itemSectionRenderer"))["contents"]
        elif continuation_token: data = next(self._searchDict(response, "continuationItems"))
        result["items"] = self._cleanupData(data)
        self._debug("SUCCESS", "JSON data content parsing successfully")
        if parseAll: 
            if nextCT: self._debug("INFO", "Parsing more playlist data")
            else: self._debug("INFO", "No continuation token, no more parsing needed")
            while nextCT:
                response, nextCT = self.playlist(continuation_token = nextCT)
                result["items"].extend(response["items"])
        self._debug("SUCCESS", "Parsing successfully, returning result")
        if playlistId: return result
        elif continuation_token: return result, nextCT

    @_logException
    def channel(self, channelId=None, username=None):
        if not (channelId or username): self._debug("WARNING", "Please provide channel ID or username"); return {}
        if channelId: url = (
            self.CHANNEL_ID_URL+channelId, 
            self.CHANNEL_ID_URL+channelId+"/about"
        )
        elif username: url = (
            self.CHANNEL_USERNAME_URL+username, 
            self.CHANNEL_USERNAME_URL+username+"/about"
        )
        response = [self.get(i).text for i in url]
        if "404 Not Found" in response[0]:
            self._debug("ERROR", "Channel not exist")
            return
        data = (self._getInitialData(i) for i in response)
        result = self._cleanupChannelData(*data)
        return result

    @_logException
    def _debug(self, level ,text):
        if self.DEBUG_LEVEL[level] >= self.DEBUG_LEVEL[self._debug_level]:
            if level == "ERROR":
                print("[-] ERROR:", text)
            elif level == "WARNING":
                print("[!] WARNING:", text)
            elif level == "INFO":
                print("[*] INFO:", text)
            elif level == "SUCCESS":
                print("[+] SUCCESS:", text)

class _Video(YouTubeAPI):
    @_logException
    def __init__(self, videoId, debug_level="ERROR"):
        super().__init__(debug_level=debug_level)
        self.headers = {
            "x-youtube-client-name": "1",
            "x-youtube-client-version": "2.20210310.12.01",
            "accept-language": "en-US"
        }
        self._videoId = videoId
        self._debug('INFO', 'Start parsing raw data')
        self._raw = self.get(self.VIDEO_PLAYER_URL+self._videoId).text
        self._player_data = self._getInitialPlayerResponse(self._raw)
        self._init_data = self._getInitialData(self._raw)
        self._result = None
        self._debug('SUCCESS', 'Raw data parsed successfully')

    @_logException
    def _getSignatureUrl(self, url):
        base_url = self._findSnippet(self._raw, "jsUrl", ",", (3, 1))
        js_url = self.BASE_URL+base_url
        js_content = self.get(js_url).text
        cipher = Cipher(js_content)
        s, sp, url = [i[0] for i in parse_qs(url).values()]
        return url + "&sig=" + cipher.get_signature(s)
    
    @_logException
    def _getCommentCount(self):
        continuation = next(self._searchDict(self._init_data, 'nextContinuationData'))['continuation'].replace('%3D', '=')
        xsrf_token = self._findSnippet(self._raw, 'XSRF_TOKEN', ",", (3, 1)).replace(r'\u003d', '\u003d')
        params = {
            'action_get_comments': 1,
            'pbj': 1,
            'ctoken': continuation,
            'continuation': continuation,
            'type': 'next'
        }
        data  = self.post(self.COMMENT_AJAX_URL, data={'session_token': xsrf_token}, params=params, headers=self.headers).json()
        comment_count = int(next(self._searchDict(data, 'countText'))['runs'][0]['text'].replace(',', ''))
        return comment_count

    @_logException
    def getSupertitle(self, primary_info):
        if not "superTitleLink" in primary_info: return None
        supertitle = [{
            'text': i['text'].strip(),
            'url': next(self._searchDict(i, 'url'))
        } for i in primary_info["superTitleLink"]["runs"] if i['text'].strip()]
        return supertitle

    @_logException
    def _cleanupVideoData(self):
        self._debug('INFO', 'Cleaning up raw data')
        primary_info = next(self._searchDict(self._init_data, "videoPrimaryInfoRenderer"))
        secondary_info = next(self._searchDict(self._init_data, "videoSecondaryInfoRenderer"))
        player_info = self._player_data["videoDetails"]
        cleaned_data = {
            "video_id": player_info["videoId"],
            "type": (t:="livestream" if "isLive" in primary_info["viewCount"]["videoViewCountRenderer"] and primary_info["viewCount"]["videoViewCountRenderer"]["isLive"] else "video"),
            "title": "".join(i["text"] for i in primary_info["title"]["runs"]),
            "supertitle": self.getSupertitle(primary_info),
            "description": "".join(i["text"] for i in secondary_info["description"]["runs"]) if "description" in secondary_info else None,
            "tags": player_info["keywords"] if "keywords" in player_info else None,
            "publish_time": primary_info["dateText"]["simpleText"],
            "author": {
                "name": player_info["author"],
                "url": secondary_info["owner"]["videoOwnerRenderer"]["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"],
                "channel_id": player_info["channelId"]
            },
            "length_seconds": int(player_info["lengthSeconds"]),
            "thumbnails": self._getThumbnail(player_info["videoId"]),
            "statistics": {
                "view_count": int(player_info["viewCount"]),
                **dict(zip(["like_count", "unlike_count"], map(lambda i: int(i.replace(",", "")), primary_info["sentimentBar"]["sentimentBarRenderer"]["tooltip"].split(" / ")))),
                "comment_count": self._getCommentCount()
            },
            "itags": dict([(i["itag"], {
                "url": i["url"] if "url" in i else self._getSignatureUrl(i["signatureCipher"]),
                "mime_type": i["mimeType"],
                "bitrate": i["bitrate"],
                "width": i["width"] if "width" in i else None,
                "height": i["height"] if "height" in i else None,
                "size": i["contentLength"] if "contentLength" in i else None,
                "fps": i["fps"] if "fps" in i else None,
                "quality": i["quality"],
                "quality_label": i["qualityLabel"] if "qualityLabel" in i else None,
                "duration": i["approxDurationMs"] if "approxDurationMs" in i else None
            }) for i in self._player_data["streamingData"]["formats"]+self._player_data["streamingData"]["adaptiveFormats"]]) if t!="livestream" else None
        }
        self._debug('SUCCESS', 'Data cleaned successfully')
        return cleaned_data

    @_logException
    def _convertValidFilename(self, s):
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        return "".join(c for c in s if c in valid_chars)

    @_logException
    def _getFileSize(self, url):
        return int(self.get(url, stream=True).headers.get('content-length', 0))

    @_logException
    def _stream(self, url, chunk_size=4096):
        file_size: int = self._getFileSize(url)
        downloaded = 0
        while downloaded < file_size:
            stop_pos = file_size - 1
            range_header = f"bytes={downloaded}-{stop_pos}"
            response = requests.get(url, headers={"Range": range_header}, stream=True)
            for chunk in response.iter_content(chunk_size):
                if not chunk: break
                downloaded += len(chunk)
                yield chunk
        return

    @_logException
    def get_json(self, include_download_link=False):
        if not self._result: self._result = self._cleanupVideoData()
        _result = copy.deepcopy(self._result)
        if not include_download_link: 
            del _result['itags']
        return _result

    @_logException
    def download(self, itag=None, path=".", log_progress=True, chunk_size=4096, callback_func=None):
        if not self._result: self._result = self._cleanupVideoData()
        _result = self._result
        self._debug('INFO', 'Start downloading video')
        if itag:
            if itag in _result["itags"].keys():
                target = _result["itags"][itag]
            else:
                raise RuntimeError('Itag not exist!')
        else:
            target = list(_result["itags"].values())[0]
        name = self._convertValidFilename(_result["title"])
        extension = target["mime_type"].split(";")[0].split("/")[-1]
        if log_progress: progress_bar = tqdm(total=self._getFileSize(target['url']), unit='iB', unit_scale=True)
        with open(os.path.join(path, f"{name}.{extension}"), "wb") as f:
            for chunk in self._stream(target['url'], chunk_size=chunk_size):
                if log_progress: progress_bar.update(len(chunk))
                f.write(chunk)
