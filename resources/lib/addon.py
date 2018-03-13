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
    page_names = {
        'start': helper.language(30020),
        'movies': helper.language(30021),
        'series': helper.language(30022),
        'sports': helper.language(30023),
        'tv': helper.language(30024),
        'programs': helper.language(30025),
        'kids': helper.language(30026)
    }

    for page in helper.c.pages[helper.c.locale]:
        if page in page_names:
            helper.add_item(page_names[page], plugin.url_for(carousels, page=page))

    helper.add_item(helper.language(30030), plugin.url_for(search))
    helper.eod()


@plugin.route('/carousels')
def carousels():
    pass


@plugin.route('/search')
def search():
    search_query = helper.get_user_input(helper.language(30030))
    if search_query:
        pass  # TODO: fix when listing is completed
    else:
        helper.log('No search query provided.')
        return False
