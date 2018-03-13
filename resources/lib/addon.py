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
        if error.value == 'User is not authenticated':
            helper.login_process()
            plugin.run()
        else:
            helper.dialog('ok', helper.language(30028), error.value)


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
    carousels_dict = helper.c.get_carousels(plugin.args['page'][0], namespace)
    for carousel, video_ids in carousels_dict.items():
        helper.add_item(carousel, plugin.url_for(assets, video_ids=video_ids))
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
        pass  # TODO: fix when listing is completed
    else:
        helper.log('No search query provided.')
        return False


@plugin.route('/assets')
def assets():
    pass
