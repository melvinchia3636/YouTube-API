from YouTubeAPI import YouTubeAPI
import json

def SearchAPIExample():
	api = YouTubeAPI(debug_level='INFO')
	result = api.search("你的答案")
	json.dump(result, open('search.json', 'w'), indent=4)

def PlaylistAPIExample():
	api = YouTubeAPI(debug_level='INFO')
	json.dump(api.playlist('PLFm1tTY1NA4eFO89sYmMDVghvH0m2wUmc'), open('MumboJumbo.json', 'w'), indent=4)
	json.dump(api.playlist('PLriprjos26pvLjj5SRhOJPdPBTDcXYHiB'), open('Hypnotizd.json', 'w'), indent=4)
	json.dump(api.playlist('PLaAVDbMg_XAoTkSw42KSc-pl7rG9Hr95v'), open('EthosLab.json', 'w'), indent=4)
	json.dump(api.playlist('PLhSQ4KysKPiiTsUjj3UD-Xpk0MUXHrp3l'), open('VintageBeef.json', 'w'), indent=4)
	json.dump(api.playlist('PL2XncHqN_7yKIafwGT8bIeHjjHlt1MUBx'), open('BdoubleO100.json', 'w'), indent=4)
	json.dump(api.playlist('PLoH7Sjb8-XEga029q9zamdRqt_dncTSTT'), open('Cubfan135.json', 'w'), indent=4)
	json.dump(api.playlist('PLvh8CGg6LWwqd3lUvFStCVP6yO_daqUe-'), open('Docm77.json', 'w'), indent=4)
	json.dump(api.playlist('PLgj0MXHeQpb-XIr_XZVYZQdWRohUntp_x'), open('FalseSymmetry.json', 'w'), indent=4)
	json.dump(api.playlist('PLSCZsQa9VSCfF4L1OfY46sMac8anhsk6D'), open('GoodTimeWithScar.json', 'w'), indent=4)
	json.dump(api.playlist('PLU2851hDb3SE6S9YJFY6n1B4t_Qv26f1m'), open('Grian.json', 'w'), indent=4)
	json.dump(api.playlist('PLE3C4yLnTeeteut9VpnnhJ5HFaoAsY-jF'), open('iJevin.json', 'w'), indent=4)
	json.dump(api.playlist('PL0Z8otuXXj_3paGa74e-CDWLJHcepCV67'), open('ImpulseSV.json', 'w'), indent=4)
	json.dump(api.playlist('PLQDo59MddgIcahwqJoRjKb2BFk0raWHgT'), open('Iskall85.json', 'w'), indent=4)
	json.dump(api.playlist('PL7On8E0_x1tqmoE8Jme8dnvVhwEfRsGXJ'), open('JoeHills.json', 'w'), indent=4)
	json.dump(api.playlist('PLs6cC73V4fpvUrk9VrNv-YUpr5XuHh18N'), open('Keralis.json', 'w'), indent=4)
	json.dump(api.playlist('PL6_PcQuFcLhu3Hdm4FocWMI1JHP5lzPRz'), open('Rendog.json', 'w'), indent=4)
	json.dump(api.playlist('PLFDYDXHl7Us-sTd8L0HUvjnotx-1ePMrM'), open('StressMonster101.json', 'w'), indent=4)
	json.dump(api.playlist('PL8t707flkqpf-LWYZw1LU7XtSL0as2OYG'), open('TangoTek.json', 'w'), indent=4)
	json.dump(api.playlist('PLrp4YiBloNz7_G3gaG8Y-iOyHNw-1ZGLC'), open('TinFoilChef.json', 'w'), indent=4)
	json.dump(api.playlist('PL3e14exB92LIc7GfSBQHqDC3JyopavrH7'), open('Welsknight.json', 'w'), indent=4)
	json.dump(api.playlist('PLmtS5lzk1pBT-lDvSubQEdhmAEIyduTeq'), open('xbCrafted.json', 'w'), indent=4)
	json.dump(api.playlist('PL7VmhWGNRxKgtwHFgDMCnutcmiafoP1c4'), open('XisumaVoid.json', 'w'), indent=4)
	#json.dump(api.playlist('PLVO4L4qtJmBonAKh9Zcb7yyfjVsG4U9CR'), open('ZombieCleo.json', 'w'), indent=4)
	#json.dump(api.playlist('PLgENJ0iY3XBiJ0jZ53HT8v9Qa3cch7YEV'), open('Pixlriffs Minecraft Survival Guide.json', 'w'), indent=4)

def ChannelAPIExample():
	api = YouTubeAPI(debug_level='INFO')
	result = api.channel(username='ThatMumboJumbo')
	json.dump(result, open('channel.json', 'w'), indent=4)

def VideoAPIExample():
	api = YouTubeAPI(debug_level='INFO')
	vid = api.video('_7qp0JMxOTs')
	result = vid.get_json()
	json.dump(result, open('video.json', 'w'), indent=4)
	vid.download()

#SearchAPIExample()
PlaylistAPIExample()
#ChannelAPIExample()
#VideoAPIExample()