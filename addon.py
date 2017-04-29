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
    for page in helper.c.pages[helper.c.locale]:
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
            'root_page': 'true'
        }

        helper.add_item(title, params=params)
    helper.add_item(helper.language(30030), params={'action': 'search'})  # search
    helper.eod()


def list_page(page=None, namespace=None, root_page=False, page_data=None, search=False):
    if page_data:
        if not isinstance(page_data, list):  # we supply the data as a list for search queries
            page = json.loads(page_data)
        else:
            page = page_data
    else:
        page = helper.c.parse_page(page, namespace, helper.get_as_bool(root_page))

    for i in page:
        page = i.get('id')
        # search queries doesn't include the videoId in response
        if i.get('videoId') or search:
            if i.get('type') == 'movie':
                list_movie(i)
            elif i.get('type') == 'series':
                list_show(i)
            elif i.get('type') == 'live_event':
                list_live_event(i)
        elif 'displayableDate' in i.keys():
            list_event_date(i)
        elif 'channel' in i.keys():
            list_channel(i)
        elif 'namespace' in i.keys():  # theme pages
            list_genres(i, page)
        elif 'page_data' in i.keys():  # parsed containers
            list_containers(i)
    helper.eod()

def list_genres(i, page):
    params = {
        'action': 'list_page',
        'namespace': i['namespace'],
        'page': page,
        'root_page': 'false'
    }

    helper.add_item(i['headline'], params)

def list_channel(i):
    params = {
        'action': 'play',
        'video_id': i['channel']['videoId']
    }

    program_info = {
        'mediatype': 'video',
        'title': i['programs'][0]['title'],
        'genre': i['programs'][0].get('mainCategory'),
        'plot': i['programs'][0].get('description')
    }

    channel_art = {
        'fanart': helper.c.get_image_url(i['programs'][0].get('landscapeImage')),
        'thumb': helper.c.get_image_url(i['programs'][0].get('landscapeImage')),
        'cover': helper.c.get_image_url(i['programs'][0].get('landscapeImage')),
        'icon': helper.c.get_image_url(i['channel']['logoUrl'])
    }

    channel_colored = coloring(i['channel']['title'], 'live').encode('utf-8')
    time_colored = coloring(i['programs'][0]['caption'], 'live').encode('utf-8')
    program_title = i['programs'][0]['title'].encode('utf-8')
    list_title = '[B]{0} {1}[/B]: {2}'.format(channel_colored, time_colored, program_title)

    helper.add_item(list_title, params=params, info=program_info, art=channel_art, content='episodes', playable=True)


def list_containers(i):
    headline = i['attributes']['headline'].encode('utf-8')
    if i['attributes'].get('subtitle'):
        subtitle = i['attributes']['subtitle'].encode('utf-8')
        title = '{0}: {1}'.format(subtitle, headline)
    else:
        title = headline

    params = {
        'action': 'list_page_with_page_data',
        'page_data': json.dumps(i['page_data'])
    }

    helper.add_item(title, params)


def list_event_date(date):
    params = {
        'action': 'list_page_with_page_data',
        'page_data': json.dumps(date['events'])
    }

    helper.add_item(date['displayableDate'], params)


def coloring(text, meaning):
    """Return the text wrapped in appropriate color markup."""
    if meaning == 'live':
        color = 'FF03F12F'
    elif meaning == 'upcoming':
        color = 'FFF16C00'

    colored_text = '[COLOR=%s]%s[/COLOR]' % (color, text)

    return colored_text


def list_live_event(event):
    if event.get('commentators'):
        if ',' in event.get('commentators'):
            commentators = event.get('commentators').split(',')
        else:
            commentators = [event['commentators']]
    else:
        commentators = []

    if helper.c.parse_datetime(event['startTime']) > helper.c.get_current_time():
        event_status = 'upcoming'
        params = {'action': 'noop'}
        playable = False
    else:
        event_status = 'live'
        params = {
            'action': 'play',
            'video_id': event['videoId']
        }
        playable = True

    list_title = '[B]{0}:[/B] {1}'.format(coloring(event['displayableStartTime'].encode('utf-8'), event_status), event['title'].encode('utf-8'))

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

    helper.add_item(list_title, params=params, info=event_info, art=event_art, content='episodes', playable=playable)


def list_movie(movie):
    params = {
        'action': 'play',
        'video_id': movie['videoId']
    }

    movie_info = {
        'mediatype': 'movie',
        'title': movie['title'],
        'plot': movie.get('description'),
        'cast': movie.get('actors') if movie.get('actors') else [],
        'genre': extract_genre_year(movie.get('caption'), 'genre'),
        'duration': movie.get('duration'),
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
        'plot': show.get('description'),
        'cast': show.get('actors') if show.get('actors') else [],
        'genre': extract_genre_year(show.get('caption'), 'genre'),
        'duration': show.get('duration'),
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
            'duration': i.get('duration')
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

def search():
    query = helper.get_user_input(helper.language(30030))
    if query:
        list_page(page_data=helper.c.get_search_data(query), search=True)
    else:
        helper.log('No search query provided.')
        return False


def router(paramstring):
    """Router function that calls other functions depending on the provided paramstring."""
    params = dict(urlparse.parse_qsl(paramstring))
    if 'setting' in params:
        if params['setting'] == 'get_operator':
            helper.get_operator()
        elif params['setting'] == 'set_locale':
            helper.set_locale()
        elif params['setting'] == 'reset_credentials':
            helper.reset_credentials()
    elif 'action' in params:
        if helper.check_for_prerequisites():
            if params['action'] == 'noop':
                pass
            elif params['action'] == 'play':
                helper.play_item(params['video_id'])
            elif params['action'] == 'list_page':
                list_page(params['page'], params['namespace'], params['root_page'])
            elif params['action'] == 'list_page_with_page_data':
                list_page(page_data=params['page_data'])
            elif params['action'] == 'list_episodes_or_seasons':
                list_episodes_or_seasons(params['page_id'])
            elif params['action'] == 'list_episodes':
                list_episodes(page_id=params['page_id'], season=params['season'])
            elif params['action'] == 'search':
                search()
    else:
        if helper.check_for_prerequisites():
            list_pages()
