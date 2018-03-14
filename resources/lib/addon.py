import sys
import json
from datetime import datetime

from resources.lib.kodihelper import KodiHelper
import routing

base_url = sys.argv[0]
handle = int(sys.argv[1])
helper = KodiHelper(base_url, handle)
plugin = routing.Plugin()
info_locale = helper.c.locale.split('_')[0]


def run():
    try:
        if helper.check_for_prerequisites():
            plugin.run()
    except helper.c.CMoreError as error:
        helper.log('C More Error: {error}'.format(error=str(error)))
        if str(error) == 'User is not authenticated':
            helper.login_process()
            plugin.run()
        else:
            helper.dialog('ok', helper.language(30028), str(error))


@plugin.route('/')
def root():
    page_map = {
        'start': {'name': helper.language(30020), 'func': list_carousels},
        'movies': {'name': helper.language(30021), 'func': list_pages},
        'series': {'name': helper.language(30022), 'func': list_carousels},
        'sports': {'name': helper.language(30023), 'func': list_pages},
        'tv': {'name': helper.language(30024), 'func': list_carousels},
        'programs': {'name': helper.language(30025), 'func': list_carousels},
        'kids': {'name': helper.language(30026), 'func': list_carousels}
    }

    for page in helper.c.pages[helper.c.locale]:
        if page in page_map:
            helper.add_item(page_map[page]['name'], plugin.url_for(page_map[page]['func'], page=page))

    helper.add_item(helper.language(30030), plugin.url_for(search))
    helper.eod()


@plugin.route('/list_carousels')
def list_carousels():
    if 'namespace' in plugin.args:
        namespace = plugin.args['namespace'][0]
    else:
        namespace = 'page'
    carousels = helper.c.get_carousels(plugin.args['page'][0], namespace)
    for carousel, params in carousels.items():
        helper.add_item(carousel, plugin.url_for(list_assets, params=json.dumps(params)))
    helper.eod()


@plugin.route('/list_pages')
def list_pages():
    pages_dict = helper.c.get_pages(plugin.args['page'][0])
    for page, data in pages_dict.items():
        helper.add_item(page, plugin.url_for(list_carousels, page=data['page'], namespace=data['namespace']))
    helper.eod()


@plugin.route('/search')
def search():
    search_query = helper.get_user_input(helper.language(30030))
    if search_query:
        params = [{
            'q': search_query,
            'type': 'movie,series'
        }]
        list_assets(params)
    else:
        helper.log('No search query provided.')
        return False


@plugin.route('/assets')
def list_assets(params=[]):
    assets = []
    if not params:
        params = json.loads(plugin.args['params'][0])
    for param in params:
        assets = assets + helper.c.get_assets(param)
    for param in params:
        if 'sort_by' in param:
            if param['sort_by'] == 'episode_number':
                assets = sorted(assets, key=lambda x: x['episode_number'])
                break
            elif param['sort_by'] == 'start_time':
                assets = sorted(assets, key=lambda x: x['events'][0]['start_time'])
                break

    assets_routing = {
        'movie': add_movie,
        'series': add_series,
        'episode': add_episode,
        'unscripted_episode': add_episode,
        'sport': add_sport
    }
    for asset in assets:
        if asset['type'] in assets_routing:
            assets_routing[asset['type']](asset)
        else:
            helper.log('Unsupported asset found: %s' % asset['type'])
    helper.eod()


@plugin.route('/list_seasons')
def list_seasons():
    asset = json.loads(plugin.args['asset'][0])
    seasons = asset['seasons_cmore_{site}'.format(site=helper.c.locale_suffix)]
    if len(seasons) > 1:
        for season in sorted(seasons):
            params = [{
                'brand_ids': asset['brand_id'],
                'season': season,
                'sort_by': 'episode_number'
            }]
            helper.add_item(helper.language(30029).format(season=season),
                            plugin.url_for(list_assets, params=json.dumps(params)))
        helper.eod()
    else:
        params = [{
            'brand_ids': asset['brand_id'],
            'season': seasons[0],
            'sort_by': 'episode_number'
        }]
        list_assets(params)


def add_movie(asset):
    info = {
        'mediatype': 'movie',
        'title': asset['title_{locale}'.format(locale=info_locale)],
        'originaltitle': asset['original_title']['text'],
        'genre': asset['genre_description_{locale}'.format(locale=info_locale)],
        'plot': asset['description_extended_{locale}'.format(locale=info_locale)],
        'plotoutline': asset['description_short_{locale}'.format(locale=info_locale)],
        'country': asset['country'],
        'cast': [x['name'] for x in asset['credits'] if x['function'] == 'actor'],
        'director': [x['name'] for x in asset['credits'] if x['function'] == 'director'],
        'year': int(asset['production_year']),
        'duration': int(asset['duration']),
        'studio': asset['studio']
    }
    helper.add_item(info['title'], plugin.url_for(play, video_id=asset['video_id']), info=info, art=add_art(asset),
                    content='movies', playable=True)


def add_series(asset):
    info = {
        'mediatype': 'tvshow',
        'title': asset['title_{locale}'.format(locale=info_locale)],
        'tvshowtitle': asset['title_{locale}'.format(locale=info_locale)],
        'genre': asset['genre_description_{locale}'.format(locale=info_locale)],
        'plot': asset['description_extended_{locale}'.format(locale=info_locale)],
        'plotoutline': asset['description_short_{locale}'.format(locale=info_locale)],
        'country': asset['country'],
        'cast': [x['name'] for x in asset['credits'] if x['function'] == 'actor'],
        'director': [x['name'] for x in asset['credits'] if x['function'] == 'director'],
        'year': int(asset['production_year']),
        'studio': asset['studio'],
        'season': len(asset['seasons_cmore_{site}'.format(site=helper.c.locale_suffix)])
    }
    helper.add_item(info['title'], plugin.url_for(list_seasons, asset=json.dumps(asset)), info=info, art=add_art(asset),
                    content='tvshows')


def add_sport(asset):
    asset_date = helper.c.parse_datetime(asset['events'][0]['start_time'])
    if datetime.now().date() == asset_date.date():
        start_time = helper.language(30035).format(asset_date.strftime('%H:%M'))
    else:
        start_time = asset_date.strftime('%Y-%m-%d %H:%M')

    if asset_date > datetime.now():
        event_status = 'upcoming'
        playable = False
        plugin_url = plugin.url_for(dialog, dialog_type='ok',
                                    heading=helper.language(30017),
                                    message=helper.language(30036).format(start_time))
    else:
        if 'live_event_end' in asset:
            event_status = 'archive'
        else:
            event_status = 'live'
        playable = True
        plugin_url = plugin.url_for(play, video_id=asset['video_id'])

    info = {
        'mediatype': 'video',
        'originaltitle': asset['original_title']['text'],
        'title': asset['title_{locale}'.format(locale=info_locale)],
        'genre': asset['league_{locale}'.format(locale=info_locale)],
        'plot': asset['description_short_{locale}'.format(locale=info_locale)],
        'year': int(asset['production_year'])
    }

    list_title = '[B]{0}:[/B] {1}'.format(coloring(start_time, event_status).encode('utf-8'),
                                          info['title'].encode('utf-8'))
    helper.add_item(list_title, plugin_url, info=info, art=add_art(asset), content='tvshows', playable=playable)


def add_episode(asset):
    info = {
        'mediatype': 'episode',
        'title': asset['title_{locale}'.format(locale=info_locale)],
        'tvshowtitle': asset['brand']['title_{locale}'.format(locale=info_locale)],
        'genre': asset['genre_description_{locale}'.format(locale=info_locale)],
        'plot': asset['description_extended_{locale}'.format(locale=info_locale)],
        'country': asset['country'],
        'cast': [x['name'] for x in asset['credits'] if x['function'] == 'actor'],
        'director': [x['name'] for x in asset['credits'] if x['function'] == 'director'],
        'year': int(asset['production_year']),
        'duration': int(asset['duration']),
        'studio': asset['brand']['studio'],
        'season': asset['season']['season_number'],
        'episode': asset['episode_number']
    }

    helper.add_item(episode_list_title(asset), plugin.url_for(play, video_id=asset['video_id']), info=info,
                    art=add_art(asset),
                    content='episodes', playable=True)


def episode_list_title(asset):
    season = asset['season']['season_number']
    episode = asset['episode_number']
    title = asset['title_{locale}'.format(locale=info_locale)].replace(':', '')
    if int(season) <= 9:
        season_format = '0' + str(season)
    else:
        season_format = str(season)
    if int(episode) <= 9:
        episode_format = '0' + str(episode)
    else:
        episode_format = str(episode)

    return '[B]S{season_format}E{episode_format}[/B]: {title}'.format(season_format=season_format,
                                                                      episode_format=episode_format,
                                                                      title=title)


def add_art(asset):
    poster = None
    fanart = None

    if asset['poster']['localizations']:
        try:
            poster = [x['url'] for x in asset['poster']['localizations'] if x['language'] == helper.c.locale][0]
        except IndexError:
            poster = asset['poster']['localizations'][0]['url']
    if not poster:
        poster = asset['poster']['url']

    if asset['poster']['localizations']:
        try:
            fanart = [x['url'] for x in asset['landscape']['localizations'] if x['language'] == helper.c.locale][0]
        except IndexError:
            fanart = asset['landscape']['localizations'][0]['url']

    if not fanart:
        fanart = asset['landscape']['url']
    if asset['type'] == 'movie':
        thumbnail = poster
    else:
        thumbnail = fanart

    artwork = {
        'poster': poster,
        'fanart': fanart,
        'landscape': fanart,
        'thumb': thumbnail
    }
    for art, url in artwork.items():
        if 'aspx' not in url:  # filmnet cdn can't be proxied for some reason
            artwork[art] = helper.c.image_proxy(url)

    return artwork


def coloring(text, meaning):
    """Return the text wrapped in appropriate color markup."""
    if meaning == 'live':
        color = 'FF03F12F'
    elif meaning == 'archive':
        color = 'FFFF0EE0'
    elif meaning == 'upcoming':
        color = 'FFF16C00'

    colored_text = '[COLOR=%s]%s[/COLOR]' % (color, text)
    return colored_text


@plugin.route('/ia_settings')
def ia_settings():
    helper.ia_settings()


@plugin.route('/set_locale')
def ia_settings():
    helper.set_locale()


@plugin.route('reset_credentials')
def reset_credentials():
    helper.reset_credentials()


@plugin.route('/play')
def play():
    helper.play(plugin.args['video_id'][0])


@plugin.route('/dialog')
def dialog():
    helper.dialog(dialog_type=plugin.args['dialog_type'][0],
                  heading=plugin.args['heading'][0],
                  message=plugin.args['message'][0])
