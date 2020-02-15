# -*- coding: utf-8 -*-
"""
A Kodi-agnostic library for C More
"""
import os
import json
import codecs
import calendar
import time
from collections import OrderedDict
from datetime import datetime, timedelta

import requests
import iso8601


class CMore(object):
    base_url = 'https://cmore-mobile-bff.b17g.services'
    # hopefully, this can be acquired dynamically in the future
    pages = {
        'sv_SE': ['start', 'movies', 'series', 'sports', 'tv', 'programs', 'kids'],
        'da_DK': ['start', 'movies', 'series', 'sports', 'tv', 'kids'],
        'nb_NO': ['start', 'movies', 'series', 'tv', 'kids']
    }

    def __init__(self, settings_folder, locale, debug=False):
        self.debug = debug
        self.locale = locale
        self.locale_suffix = self.locale.split('_')[1].lower()
        self.http_session = requests.Session()
        self.settings_folder = settings_folder
        self.config_path = os.path.join(self.settings_folder, 'configuration.json')
        self.config_version = '3.14.1'
        self.config = self.get_config()
        self.client = 'cmore-kodi'

    class CMoreError(Exception):
        pass

    def log(self, string):
        """C More class log method."""
        if self.debug:
            try:
                print('[C More]: %s') % string
            except UnicodeEncodeError:
                # we can't anticipate everything in unicode they might throw at
                # us, but we can handle a simple BOM
                bom = unicode(codecs.BOM_UTF8, 'utf8')
                print('[C More]: %s' % string.replace(bom, ''))
            except:
                pass

    def make_request(self, url, method, params=None, payload=None, headers=None):
        """Make an HTTP request. Return the response."""
        self.log('Request URL: %s' % url)
        self.log('Method: %s' % method)
        if params:
            self.log('Params: %s' % params)
        if payload:
            self.log('Payload: %s' % payload)
        if headers:
            self.log('Headers: %s' % headers)

        if method == 'get':
            req = self.http_session.get(url, params=params, headers=headers)
        elif method == 'put':
            req = self.http_session.put(url, params=params, data=payload, headers=headers)
        else:  # post
            req = self.http_session.post(url, params=params, data=payload, headers=headers)
        self.log('Response code: %s' % req.status_code)
        self.log('Response: %s' % req.content)

        return self.parse_response(req.content)

    def parse_response(self, response):
        """Try to load JSON data into dict and raise potential API errors."""
        try:
            response = json.loads(response)
            if 'error' in response:
                error_keys = ['message', 'description', 'code']
                for error in error_keys:
                    if error in response['error']:
                        raise self.CMoreError(response['error'][error])
            elif 'errors' in response:
                raise self.CMoreError(response['errors'][0]['message'])
            elif 'errorCode' in response:
                raise self.CMoreError(response['message'])

        except ValueError:  # when response is not in json
            pass

        return response

    def get_config(self):
        """Return the config in a dict. Re-download if the config version doesn't match self.config_version."""
        try:
            config = json.load(open(self.config_path))['data']
        except IOError:
            self.download_config()
            config = json.load(open(self.config_path))['data']

        config_version = int(str(config['settings']['currentAppVersion']).replace('.', ''))
        version_to_use = int(str(self.config_version).replace('.', ''))
        config_lang = config['bootstrap']['suggested_site']['locale']
        if version_to_use > config_version or config_lang != self.locale:
            self.download_config()
            config = json.load(open(self.config_path))['data']

        return config

    def download_config(self):
        """Download the C More app configuration."""
        url = self.base_url + '/configuration'
        params = {
            'device': 'android_tab',
            'locale': self.locale
        }
        config_data = self.make_request(url, 'get', params=params)
        with open(self.config_path, 'w') as fh_config:
            fh_config.write(json.dumps(config_data))

    def get_operators(self):
        """Return a list of TV operators supported by the C More login system."""
        url = self.config['links']['tveAPI'] + 'country/{0}/operator'.format(self.locale_suffix)
        params = {'client': self.client}
        data = self.make_request(url, 'get', params=params)

        return data['data']['operators']

    def login(self, username=None, password=None, operator=None):
        """Complete login process for C More."""
        if operator:
            url = self.config['links']['accountJune']
        else:
            url = self.config['links']['accountDelta']
        params = {'client': self.client}
        headers = {'content-type': 'application/json'}

        method = 'post'
        payload = {
            'query': 'mutation($username: String!, $password: String, $site: String) {\n  login(credentials: {username: $username, password: $password}, site: $site) {\n    user {\n      ...UserFields\n    }\n    session {\n      token\n      vimondToken\n    }\n  }\n}\nfragment UserFields on User {\n    acceptedCmoreTerms\n    acceptedPlayTerms\n    countryCode\n    email\n    firstName\n    genericAds\n    lastName\n    tv4UserDataComplete\n    userId\n    username\n    yearOfBirth\n    zipCode\n}\n',
            'variables': {
            'username': username,
            'password': password,
            'site': 'CMORE_{locale_suffix}'.format(locale_suffix=self.locale_suffix.upper())
                }
            }
        if operator:
            payload['query'] = '\n    mutation loginTve($operatorName: String!, $username: String!, $password: String, $countryCode: String!) {\n      login(tveCredentials: {\n        operator: $operatorName,\n        username: $username,\n        password: $password,\n        countryCode: $countryCode\n      }) {\n        session{\n          token\n        }\n      }\n    }'
            payload['variables']['countryCode'] = self.locale_suffix
            payload['variables']['operatorName'] = operator

        credentials = self.make_request(url, method, params=params, payload=json.dumps(payload), headers=headers)
        return credentials

    def get_stream(self, video_id, login_token):
        """Return stream data in a dict for a specified video ID."""
        init_data = self.get_playback_init()
        asset = self.get_playback_asset(video_id, init_data)
        url = '{playback_api}{media_uri}'.format(playback_api=init_data['envPlaybackApi'], media_uri=asset['mediaUri'])
        headers = {'x-jwt': 'Bearer {login_token}'.format(login_token=login_token)}
        stream = self.make_request(url, 'get', headers=headers)['playbackItem']
        return stream

    def get_playback_init(self):
        """Get playback init data (API URL:s and request variables etc)"""
        self.log('Getting playback init.')
        url = 'https://bonnier-player-android-prod.b17g.net/init'
        params = {
            'domain': 'cmore.{locale_suffix}'.format(locale_suffix=self.locale_suffix)
        }
        data = self.make_request(url, 'get', params=params)['config']
        return data

    def get_playback_asset(self, video_id, init_data):
        """Get playback metadata needed to complete the stream request."""
        self.log('Getting playback asset for video id {video_id}'.format(video_id=video_id))
        url = '{playback_api}/asset/{video_id}'.format(playback_api=init_data['envPlaybackApi'], video_id=video_id)
        params = {
            'service': 'cmore.{locale_suffix}'.format(locale_suffix=self.locale_suffix),
            'device': init_data['envPlaybackDevice'],
            'protocol': init_data['envPlaybackProtocol'],
            'drm': init_data['envPlaybackDrm']
        }
        asset = self.make_request(url, 'get', params=params)
        return asset

    def image_proxy(self, image_url):
        """Request the image from C More's image proxy. Can be extended to resize/add image effects automatically.
        See https://imageproxy.b17g.services/docs for more information."""
        if image_url:
            return '{0}?source={1}'.format(self.config['links']['imageProxy'], image_url)
        else:
            return None

    def get_carousels(self, page, namespace='page'):
        carousels = OrderedDict()
        known_containers = ['section_containers', 'genre_containers']
        url = self.config['links']['pageAPI'] + page
        params = {
            'locale': self.locale,
            'namespace': namespace
        }
        data = self.make_request(url, 'get', params=params)['data']

        if 'showcase' in data['containers']:
            params = [{'video_ids': ','.join([x['targets'][0]['videoId'] for x in data['containers']['showcase']['items']])}]
            carousels['Showcase'] = params
        if 'scheduledEvents' in data:
            for event in data['scheduledEvents']:
                carousels[event['displayableDate']] = [{
                    'video_ids': ','.join([x['videoId'] for x in event['events']]),
                    'sort_by': 'start_time'
                }]
        for container in known_containers:
            if container in data['containers']:
                for carousel in data['containers'][container]:
                    brand_ids = [x['id'] for x in carousel['targets'] if x['type'] == 'series']
                    video_ids = [x['videoId'] for x in carousel['targets'] if x['type'] != 'series']
                    req_params = []
                    if brand_ids:
                        req_params.append({
                            'brand_ids': ','.join(brand_ids),
                            'type': 'series'
                        })
                    if video_ids:
                        req_params.append({'video_ids': ','.join(video_ids)})
                    carousels[carousel['attributes']['headline']] = req_params

        return carousels

    def get_pages(self, page, namespace='page'):
        pages = OrderedDict()
        url = self.config['links']['pageAPI'] + page
        params = {
            'locale': self.locale,
            'namespace': namespace
        }
        page_links = self.make_request(url, 'get', params=params)['data']['containers']['page_link_container']['pageLinks']
        for page in page_links:
            pages[page['headline']] = {'page': page['id'], 'namespace': page['namespace']}

        return pages

    def get_channels(self):
        url = self.config['links']['graphqlAPI']
        params = {'country': self.locale_suffix}
        payload = {
            'operationName': 'EpgQuery',
            'variables': {
                'date': datetime.now().strftime('%Y-%m-%d')
            },
            'query': 'query EpgQuery($date: String!) {\n  epg(date: $date) {\n    days {\n      channels {\n        asset {\n          id\n          __typename\n        }\n        channelId\n        name\n        title\n        schedules {\n          scheduleId\n          assetId\n          asset {\n            title\n            urlToCDP\n            type\n            __typename\n          }\n          nextStart\n          calendarDate\n          isPremiere\n          isLive\n          program {\n            programId\n            title\n            seasonNumber\n            episodeNumber\n            duration\n            category\n            shortSynopsis\n            imageId\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n'
        }
        headers = {'content-type': 'application/json'}
        data = self.make_request(url, 'post', params=params, payload=json.dumps(payload), headers=headers)['data']
        return data['epg']['days'][0]['channels']

    def get_assets(self, params):
        url = self.config['links']['bbSearchAPI'] + '/search'
        req_params = {
            'site': 'cmore.{locale_suffix}'.format(locale_suffix=self.locale_suffix),
            'client': self.client,
            'page_size': '100'
        }
        if params:
            req_params.update(params)

        assets = self.make_request(url, 'get', params=req_params)['assets']
        return assets

    def parse_datetime(self, event_date, localize=True):
        """Parse date string to datetime object."""
        if 'Z' in event_date:
            datetime_obj = iso8601.parse_date(event_date)
            if localize:
                datetime_obj = self.utc_to_local(datetime_obj)
        else:
            date_time_format = '%Y-%m-%dT%H:%M:%S+' + event_date.split('+')[1]  # summer/winter time changes format
            datetime_obj = datetime(*(time.strptime(event_date, date_time_format)[0:6]))
        return datetime_obj

    @staticmethod
    def utc_to_local(utc_dt):
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)
