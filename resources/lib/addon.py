import sys
import urlparse
import json

from resources.lib.kodihelper import KodiHelper
import xbmc
import routing

base_url = sys.argv[0]
handle = int(sys.argv[1])
helper = KodiHelper(base_url, handle)
plugin = routing.Plugin()


def run():
    try:
        plugin.run()
    except helper.c.CMoreError as error:
        if error == 'User is not authenticated':
            helper.login_process()
            plugin.run()
        else:
            helper.dialog('ok', helper.language(30028), error)


@plugin.route('/')
def root():
    page_map = {
        'start': {'name': helper.language(30020), 'func': carousels},
        'movies': {'name': helper.language(30021), 'func': pages},
        'series': {'name': helper.language(30022), 'func': carousels},
        'sports': {'name': helper.language(30023), 'func': pages},
        'tv': {'name': helper.language(30024), 'func': carousels},
        'programs': {'name': helper.language(30025), 'func': carousels},
        'kids': {'name': helper.language(30026), 'func': carousels}
    }

    for page in helper.c.pages[helper.c.locale]:
        if page in page_map:
            helper.add_item(page_map[page]['name'], plugin.url_for(page_map[page]['func'], page=page))

    helper.add_item(helper.language(30030), plugin.url_for(search))
    helper.eod()


@plugin.route('/carousels')
def carousels():
    if 'namespace' in plugin.args:
        namespace = plugin.args['namespace'][0]
    else:
        namespace = None
    carousels = helper.c.get_carousels(plugin.args['page'][0], namespace)
    for carousel, params in carousels.items():
        helper.add_item(carousel, plugin.url_for(assets, params=json.dumps(params)))
    helper.eod()


@plugin.route('/pages')
def pages():
    pages_dict = helper.c.get_pages(plugin.args['page'][0])
    for page, data in pages_dict.items():
        helper.add_item(page, plugin.url_for(carousels, page=data['page'], namespace=data['namespace']))
    helper.eod()


@plugin.route('/search')
def search():
    search_query = helper.get_user_input(helper.language(30030))
    if search_query:
        params = {
            'q': search_query,
            'type': 'movie,series'
        }
        assets(params)
    else:
        helper.log('No search query provided.')
        return False


@plugin.route('/assets')
def assets(params={}):
    if not params:
        params = json.loads(plugin.args['params'][0])
    assets_data = helper.c.get_assets(params)
    assets_map = {
        'movie': add_movie
    }

    for asset in assets_data:
        if asset['type'] in assets_map:
            assets_map[asset['type']](asset)
        else:
            helper.log('Unsupported asset found: %s' % asset['type'])
    helper.eod()


def add_movie(asset):
    info = {
        'mediatype': 'movie',
        'title': asset['title_{locale}'.format(locale=helper.c.locale.split('_')[0])],
        'originaltitle': asset['original_title']['text'],
        'genre': asset['genre_description_{locale}'.format(locale=helper.c.locale.split('_')[0])],
        'plot': asset['description_extended_{locale}'.format(locale=helper.c.locale.split('_')[0])],
        'plotoutline': asset['description_short_{locale}'.format(locale=helper.c.locale.split('_')[0])],
        'country': asset['country'],
        'cast': [x['name'] for x in asset['credits'] if x['function'] == 'actor'],
        'director': [x['name'] for x in asset['credits'] if x['function'] == 'director'],
        'year': int(asset['production_year']),
        'duration': int(asset['duration']),
        'studio': asset['studio']
    }
    helper.add_item(asset['title_{locale}'.format(locale=helper.c.locale.split('_')[0])], plugin.url_for(assets, data='abc'), info=info, art=add_art(asset), content='movies')


def add_art(asset):
    artwork = {
        'poster': helper.c.image_proxy([x['url'] for x in asset['poster']['localizations'] if x['language'] == helper.c.locale][0]),
        'fanart': helper.c.image_proxy([x['url'] for x in asset['landscape']['localizations'] if x['language'] == helper.c.locale][0]),
        'landscape': helper.c.image_proxy([x['url'] for x in asset['landscape']['localizations'] if x['language'] == helper.c.locale][0]),
    }
    return artwork

