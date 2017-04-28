import json

import xmltodict
from kodihelper import KodiHelper

helper = KodiHelper()


class Widevine(object):
    license_url = helper.c.config['settings']['drmProxy']

    def get_kid(self, mpd_url):
        # TODO: parse this with ElementTree instead
        mpd_data = helper.c.make_request(mpd_url, 'get')
        mpd_dict = xmltodict.parse(mpd_data)
        for adapt_set in mpd_dict['MPD']['Period']['AdaptationSet']:
            if 'ContentProtection' in adapt_set.keys():
                for cenc in adapt_set['ContentProtection']:
                    if '@cenc:default_KID' in cenc.keys():
                        kid = cenc['@cenc:default_KID']
                        return kid

    def get_license(self, mpd_url, wv_challenge, token):
        post_data = {
            'drm_info': [x for x in bytearray(wv_challenge)],  # convert challenge to a list of bytes
            'kid': self.get_kid(mpd_url),
            'token': token
        }
        license = helper.c.make_request(self.license_url, 'post', payload=json.dumps(post_data))

        return license
