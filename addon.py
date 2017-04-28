import sys
import urlparse
import json

from resources.lib.kodihelper import KodiHelper

base_url = sys.argv[0]
handle = int(sys.argv[1])
helper = KodiHelper(base_url, handle)

def run():
    try:
        router(sys.argv[2][1:]) # trim the leading '?' from the plugin call paramstring
    except helper.c.CMoreError as error:
        if error.value == 'SESSION_NOT_AUTHENTICATED':
            helper.login_process()
            router(sys.argv[2][1:])
        else:
            helper.dialog('ok', helper.language(30028), error.value)

def list_pages():
    for page in helper.c.pages:
        if page == 'start':
            title = helper.language(30020)
        elif page == 'movies':
            title = helper.language(30021)
        elif page == 'series':
            title = helper.language(30022)
        elif page == 'sports':
            title = helper.language(30023)
        elif page == 'tv':
            title = helper.language(30024)
        elif page == 'programs':
            title = helper.language(30025)
        elif page == 'kids':
            title = helper.language(30026)
        else:
            title = page

        params = {
            'action': 'list_page',
            'page': page,
            'namespace': 'page',
            'main_categories': 'true'
        }

        helper.add_item(title, params=params)
    helper.eod()

def list_page(page, namespace, main_categories):
    if main_categories == 'true':
        main_categories = True
    else:
        main_categories = False
    page = helper.c.parse_page(page, namespace, main_categories)

    for i in page:
        params = {'page': i['id']}
        if 'videoId' in i.keys():
            list_page_items(json.dumps(page))
            return True
        elif 'namespace' in i.keys():
            title = i['headline']
            params['action'] = 'list_page'
            params['namespace'] = i['namespace']
            params['main_categories'] = 'false'
        elif 'item_data' in i.keys():
            headline = i['attributes']['headline'].encode('utf-8')
            if i['attributes'].get('subtitle'):
                subtitle = i['attributes']['subtitle'].encode('utf-8')
                title = '{0}: {1}'.format(subtitle, headline)
            else:
                title = headline
            params['action'] = 'list_page_items'
            params['item_data'] = json.dumps(i['item_data'])
        helper.add_item(title, params)
    helper.eod()


def list_page_items(item_data):
    for i in json.loads(item_data):
        if i['type'] == 'movie':
            list_movie(i)
        elif i['type'] == 'series':
            list_show(i)
    helper.eod()


def list_movie(movie):
    params = {
        'action': 'play',
        'video_id': movie['videoId']
    }

    movie_info = {
        'mediatype': 'movie',
        'title': movie['title'],
        'genre': movie['caption'].split(',')[0],
        'duration': movie['duration'],
        'year': int(movie['caption'].split(', ')[1])
    }

    movie_art = {
        'fanart': helper.c.get_image_url(movie['landscapeImage']) if 'landscapeImage' in movie.keys() else None,
        'thumb': helper.c.get_image_url(movie['posterImage']) if 'posterImage' in movie.keys() else None,
        'banner': helper.c.get_image_url(movie['ultraforgeImage']) if 'ultraforgeImage' in movie.keys() else None,
        'cover': helper.c.get_image_url(movie['landscapeImage']) if 'landscapeImage' in movie.keys() else None,
        'poster': helper.c.get_image_url(movie['posterImage']) if 'posterImage' in movie.keys() else None
    }

    helper.add_item(movie['title'], params=params, info=movie_info, art=movie_art, content='movies', playable=True)


def list_show(show):
    params = {
        'action': 'list_episodes_or_seasons',
        'page_id': show['id']
    }

    show_info = {
        'mediatype': 'tvshow',
        'title': show['title'],
        'genre': show['caption'].split(',')[0],
        'duration': show['duration'],
        'year': int(show['caption'].split(', ')[1])
    }

    show_art = {
        'fanart': helper.c.get_image_url(show['landscapeImage']) if 'landscapeImage' in show.keys() else None,
        'thumb': helper.c.get_image_url(show['posterImage']) if 'posterImage' in show.keys() else None,
        'banner': helper.c.get_image_url(show['ultraforgeImage']) if 'ultraforgeImage' in show.keys() else None,
        'cover': helper.c.get_image_url(show['landscapeImage']) if 'landscapeImage' in show.keys() else None,
        'poster': helper.c.get_image_url(show['posterImage']) if 'posterImage' in show.keys() else None
    }

    helper.add_item(show['title'], params=params, info=show_info, art=show_art, content='tvshows')


def list_episodes_or_seasons(page_id):
    series = helper.c.get_contentdetails('series', page_id)
    if len(series['availableSeasons']) > 1:
        list_seasons(series)
    else:
        list_episodes(series_data=series)

def list_seasons(series):
    for season in series['availableSeasons']:
        title = '{0} {1}'.format(helper.language(30029), str(season))
        params = {
            'action': 'list_episodes',
            'page_id': series['id'],
            'season': str(season)
        }
        helper.add_item(title, params)
    helper.eod()


def list_episodes(page_id=None, season=None, series_data=None):
    if page_id:
        series = helper.c.get_contentdetails('series', page_id, season)
    else:
        series = series_data

    for e in series['capiAssets']:
        params = {
            'action': 'play',
            'video_id': e['videoId']
        }

        episode_info = {
            'mediatype': 'episode',
            'tvshowtitle': e['seriesTitle'] if 'seriesTitle' in e.keys() else e['title'].replace(': ', ''),
            'title': e['title'].replace(': ', '').encode('utf-8'),
            'plot': e['description'] if 'description' in e.keys() else None,
            'year': int(e['year']) if 'year' in e.keys() else None,
            'season': int(e['season']) if 'season' in e.keys() else None,
            'episode': int(e['episode']) if 'episode' in e.keys() else None,
            'genre': ', '.join(e['subCategories']),
            'cast': e['actors'] if 'actors' in e.keys() else [],
            'duration': e['duration']
        }

        episode_info['title'] = add_season_episode_to_title(episode_info['title'], episode_info['season'], episode_info['episode'])

        episode_art = {
            'fanart': helper.c.get_image_url(e['landscapeImage']) if 'landscapeImage' in e.keys() else None,
            'thumb': helper.c.get_image_url(e['landscapeImage']) if 'landscapeImage' in e.keys() else None,
            'banner': helper.c.get_image_url(e['ultraforgeImage']) if 'ultraforgeImage' in e.keys() else None,
            'cover': helper.c.get_image_url(e['landscapeImage']) if 'landscapeImage' in e.keys() else None,
            'poster': helper.c.get_image_url(e['posterImage']) if 'posterImage' in e.keys() else None
        }

        helper.add_item(episode_info['title'], params=params, info=episode_info, art=episode_art, content='episodes', playable=True)
    helper.eod()


def add_season_episode_to_title(title, season, episode):
    if season and episode:
        if int(season) <= 9:
            season_format = '0' + str(season)
        else:
            season_format = str(season)
        if int(episode) <= 9:
            episode_format = '0' + str(episode)
        else:
            episode_format = str(episode)

        return '[B]S{0}E{1}[/B] {2}'.format(season_format, episode_format, title)
    else:
        helper.log('No season/episode information found.')
        return title


def router(paramstring):
    """Router function that calls other functions depending on the provided paramstring."""
    params = dict(urlparse.parse_qsl(paramstring))
    if params:
        if 'setting' in params:
            if params['setting'] == 'get_operator':
                helper.get_operator()
            elif params['setting'] == 'get_country':
                helper.get_country()
            elif params['setting'] == 'reset_credentials':
                helper.reset_credentials()
        elif 'action' in params:
            if helper.check_for_prerequisites():
                if params['action'] == 'play':
                    helper.play_item(params['video_id'])
                elif params['action'] == 'list_page':
                    list_page(params['page'], params['namespace'], params['main_categories'])
                elif params['action'] == 'list_page_items':
                    list_page_items(params['item_data'])
                elif params['action'] == 'list_episodes_or_seasons':
                    list_episodes_or_seasons(params['page_id'])
                elif params['action'] == 'list_episodes':
                    list_episodes(page_id=params['page_id'], season=params['season'])
    else:
        if helper.check_for_prerequisites():
            list_pages()
