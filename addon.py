import sys
import urlparse
import json

from resources.lib.kodihelper import KodiHelper

base_url = sys.argv[0]
handle = int(sys.argv[1])
helper = KodiHelper(base_url, handle)


def run():
    try:
        router(sys.argv[2][1:])  # trim the leading '?' from the plugin call paramstring
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
        params = {'page': i.get('id')}
        if 'videoId' in i.keys() or 'displayableDate' in i.keys():
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
        if i.get('type') == 'movie':
            list_movie(i)
        elif i.get('type') == 'series':
            list_show(i)
        elif i.get('type') == 'live_event':
            list_live_event(i)
        elif 'displayableDate' in i.keys():
            list_event_date(i)
    helper.eod()


def list_event_date(date):
    params = {
        'action': 'list_page_items',
        'item_data': json.dumps(date['events'])
    }

    helper.add_item(date['displayableDate'], params)


def list_live_event(event):
    params = {
        'action': 'play',
        'video_id': event['videoId']
    }

    if event.get('commentators'):
        if ',' in event.get('commentators'):
            commentators = event.get('commentators').split(',')
        else:
            commentators = [event['commentators']]
    else:
        commentators = []

    event_info = {
        'mediatype': 'video',
        'plot': event.get('description'),
        'plotoutline': event.get('caption'),
        'year': int(event['year']) if event.get('year') else None,
        'genre': ', '.join(event['subCategories']) if event.get('subCategories') else None,
        'cast': commentators
    }

    event_art = {
        'fanart': helper.c.get_image_url(event.get('landscapeImage')),
        'thumb': helper.c.get_image_url(event.get('landscapeImage')),
        'banner': helper.c.get_image_url(event.get('ultraforgeImage')),
        'cover': helper.c.get_image_url(event.get('landscapeImage')),
        'icon': helper.c.get_image_url(event.get('categoryIcon'))
    }

    helper.add_item(event['title'], params=params, info=event_info, art=event_art, content='episodes', playable=True)


def list_movie(movie):
    params = {
        'action': 'play',
        'video_id': movie['videoId']
    }

    movie_info = {
        'mediatype': 'movie',
        'title': movie['title'],
        'genre': extract_genre_year(movie.get('caption'), 'genre'),
        'duration': movie['duration'],
        'year': int(extract_genre_year(movie.get('caption'), 'year'))
    }

    movie_art = {
        'fanart': helper.c.get_image_url(movie.get('landscapeImage')),
        'thumb': helper.c.get_image_url(movie.get('posterImage')),
        'banner': helper.c.get_image_url(movie.get('ultraforgeImage')),
        'cover': helper.c.get_image_url(movie.get('landscapeImage')),
        'poster': helper.c.get_image_url(movie.get('posterImage'))
    }

    helper.add_item(movie['title'], params=params, info=movie_info, art=movie_art, content='movies', playable=True)


def extract_genre_year(caption, what_to_extract):
    """Try to extract the genre or year from the caption."""
    if what_to_extract == 'year':
        list_index = 1
    else:
        list_index = 0

    if caption:
        try:
            return caption.split(', ')[list_index]
        except IndexError:
            pass

    return None


def list_show(show):
    params = {
        'action': 'list_episodes_or_seasons',
        'page_id': show['id']
    }

    show_info = {
        'mediatype': 'tvshow',
        'title': show['title'],
        'genre': extract_genre_year(show.get('caption'), 'genre'),
        'duration': show['duration'],
        'year': extract_genre_year(show.get('caption'), 'year')
    }

    show_art = {
        'fanart': helper.c.get_image_url(show.get('landscapeImage')),
        'thumb': helper.c.get_image_url(show.get('posterImage')),
        'banner': helper.c.get_image_url(show.get('ultraforgeImage')),
        'cover': helper.c.get_image_url(show.get('landscapeImage')),
        'poster': helper.c.get_image_url(show.get('posterImage'))
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

    for i in series['capiAssets']:
        params = {
            'action': 'play',
            'video_id': i['videoId']
        }

        title = i['title'].replace(': ', '').encode('utf-8')

        episode_info = {
            'mediatype': 'episode',
            'tvshowtitle': i['seriesTitle'] if i.get('seriesTitle') else title,
            'plot': i.get('description'),
            'year': int(i['year']) if i.get('year') else None,
            'season': int(i['season']) if i.get('season') else None,
            'episode': int(i['episode']) if i.get('episode') else None,
            'genre': ', '.join(i['subCategories']) if i.get('subCategories') else None,
            'cast': i.get('actors') if i.get('actors') else [],
            'duration': i['duration']
        }

        episode_info['title'] = add_season_episode_to_title(title, episode_info['season'], episode_info['episode'])

        episode_art = {
            'fanart': helper.c.get_image_url(i.get('landscapeImage')),
            'thumb': helper.c.get_image_url(i.get('landscapeImage')),
            'banner': helper.c.get_image_url(i.get('ultraforgeImage')),
            'cover': helper.c.get_image_url(i.get('landscapeImage')),
            'poster': helper.c.get_image_url(i.get('posterImage'))
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
            elif params['setting'] == 'set_country':
                helper.set_country()
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
