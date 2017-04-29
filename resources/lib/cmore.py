# -*- coding: utf-8 -*-
"""
A Kodi-agnostic library for C More
"""
import os
import json
import codecs
import cookielib
import time
from datetime import datetime

import requests


class CMore(object):
    def __init__(self, settings_folder, country, debug=False):
        self.debug = debug
        self.country = country
        self.domain_suffix = self.country.split('_')[1].lower()
        self.http_session = requests.Session()
        self.settings_folder = settings_folder
        self.cookie_jar = cookielib.LWPCookieJar(os.path.join(self.settings_folder, 'cookie_file'))
        self.credentials_file = os.path.join(settings_folder, 'credentials')
        self.base_url = 'https://cmore-mobile-bff.b17g.services'
        self.config_path = os.path.join(self.settings_folder, 'configuration.json')
        self.config_version = '3.1.4'
        self.config = self.get_config()
        self.client = 'cmore-android'
        # hopefully, this can be acquired dynamically in the future
        self.pages = {
            'sv_SE': ['start', 'movies', 'series', 'sports', 'tv', 'programs', 'kids'],
            'da_DK': ['start', 'movies', 'series', 'sports', 'tv', 'kids'],
            'nb_NO': ['start', 'movies', 'series', 'tv', 'kids'],
            'fi_FI': ['start', 'movies', 'series', 'tv', 'kids']
        }
        try:
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except IOError:
            pass
        self.http_session.cookies = self.cookie_jar

    class CMoreError(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    def log(self, string):
        if self.debug:
            try:
                print '[C More]: %s' % string
            except UnicodeEncodeError:
                # we can't anticipate everything in unicode they might throw at
                # us, but we can handle a simple BOM
                bom = unicode(codecs.BOM_UTF8, 'utf8')
                print '[C More]: %s' % string.replace(bom, '')
            except:
                pass

    def make_request(self, url, method, params=None, payload=None, headers=None):
        """Make an HTTP request. Return the response."""
        self.log('Request URL: %s' % url)
        self.log('Method: %s' % method)
        self.log('Params: %s' % params)
        self.log('Payload: %s' % payload)
        self.log('Headers: %s' % headers)
        try:
            if method == 'get':
                req = self.http_session.get(url, params=params, headers=headers)
            elif method == 'put':
                req = self.http_session.put(url, params=params, data=payload, headers=headers)
            else:  # post
                req = self.http_session.post(url, params=params, data=payload, headers=headers)
            self.log('Response code: %s' % req.status_code)
            self.log('Response: %s' % req.content)
            self.cookie_jar.save(ignore_discard=True, ignore_expires=False)
            self.raise_cmore_error(req.content)
            return req.content

        except requests.exceptions.ConnectionError as error:
            self.log('Connection Error: - %s' % error.message)
            raise
        except requests.exceptions.RequestException as error:
            self.log('Error: - %s' % error.value)
            raise

    def raise_cmore_error(self, response):
        try:
            error = json.loads(response)['error']
            if isinstance(error, dict):
                if 'message' in error.keys():
                    raise self.CMoreError(error['message'])
                elif 'code' in error.keys():
                    raise self.CMoreError(error['code'])
            elif isinstance(error, str):
                raise self.CMoreError(error)

            raise self.CMoreError('Error')  # generic error message

        except KeyError:
            pass
        except ValueError:  # when response is not in json
            pass

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
        if config_version != version_to_use or config_lang != self.country:
            self.download_config()
            config = json.load(open(self.config_path))['data']

        return config

    def download_config(self):
        """Download the C More app configuration."""
        url = self.base_url + '/configuration'
        params = {
            'device': 'android_tab',
            'locale': self.country
        }
        config_data = self.make_request(url, 'get', params=params)
        with open(self.config_path, 'w') as fh_config:
            fh_config.write(config_data)

    def save_credentials(self, credentials):
        credentials_dict = json.loads(credentials)['data']
        if self.get_credentials().get('remember_me'):
            credentials_dict['remember_me'] = {}
            credentials_dict['remember_me']['token'] = self.get_credentials()['remember_me']['token']  # resave token
        with open(self.credentials_file, 'w') as fh_credentials:
            fh_credentials.write(json.dumps(credentials_dict))

    def reset_credentials(self):
        credentials = {}
        with open(self.credentials_file, 'w') as fh_credentials:
            fh_credentials.write(json.dumps(credentials))

    def get_credentials(self):
        try:
            with open(self.credentials_file, 'r') as fh_credentials:
                credentials_dict = json.loads(fh_credentials.read())
                return credentials_dict
        except IOError:
            self.reset_credentials()
            with open(self.credentials_file, 'r') as fh_credentials:
                return json.loads(fh_credentials.read())

    def get_operators(self):
        url = self.config['links']['accountAPI'] + 'operators'
        params = {
            'client': self.client,
            'country_code': self.domain_suffix
        }
        data = self.make_request(url, 'get', params=params)

        return json.loads(data)['data']['operators']

    def login(self, username=None, password=None, operator=None):
        url = self.config['links']['accountAPI'] + 'session'
        params = {
            'client': self.client,
            'legacy': 'true'
        }

        if self.get_credentials().get('remember_me'):  # TODO: find out when token expires
            method = 'put'
            payload = {
                'locale': self.country,
                'remember_me': self.get_credentials()['remember_me']['token']
            }
        else:
            method = 'post'
            payload = {
                'username': username,
                'password': password
            }
            if operator:
                payload['country_code'] = self.domain_suffix
                payload['operator'] = operator


        credentials = self.make_request(url, method, params=params, payload=payload)
        self.save_credentials(credentials)

    def get_page(self, page_id, namespace='page'):
        url = self.config['links']['pageAPI'] + page_id
        params = {
            'locale': self.country,
            'namespace': namespace
        }
        headers = {'Authorization': 'Bearer {0}'.format(self.get_credentials().get('jwt_token'))}
        data = self.make_request(url, 'get', params=params, headers=headers)

        return json.loads(data)['data']

    def get_contentdetails(self, page_type, page_id, season=None, size='999', page='1'):
        url = self.config['links']['contentDetailsAPI'] + '{0}/{1}'.format(page_type, page_id)
        params = {'locale': self.country}
        if season:
            params['season'] = season
            params['size'] = size
            params['page'] = page

        headers = {'Authorization': 'Bearer {0}'.format(self.get_credentials().get('jwt_token'))}
        data = self.make_request(url, 'get', params=params, headers=headers)

        return json.loads(data)['data']

    def parse_page(self, page_id, namespace='page', root_page=False):
        page = self.get_page(page_id, namespace)
        if 'targets' in page.keys():
            return page['targets']  # movie/series items on theme-pages
        elif 'nowPlaying' in page.keys():
            return page['nowPlaying']  # tv channels/program info
        elif 'scheduledEvents' in page.keys():
            return page['scheduledEvents']  # sports events
        elif page.get('containers'):
            if 'genre_containers' in page['containers'].keys():
                return self.parse_containers(page['containers']['genre_containers'])
            elif 'section_containers' in page['containers'].keys():
                return self.parse_containers(page['containers']['section_containers'])
            elif page['containers']['page_link_container']['pageLinks'] and root_page:
                # no parsing needed as it's already in the 'correct' format
                return page['containers']['page_link_container']['pageLinks']
        else:
            self.log('Failed to parse page.')
            return False

    def parse_containers(self, containers):
        parsed_containers = []
        for i in containers:
            if i['pageLink']['id']:
                parsed_containers.append(i['pageLink'])
            else:
                container = {
                    'id': i['id'],
                    'attributes': i['attributes'],
                    'page_data': i['targets']

                }
                parsed_containers.append(container)

        return parsed_containers


    def get_unfinished_assets(self, limit=200):
        url = self.config['links']['personalizationAPI'] + 'unfinished_assets'
        params = {
            'limit': limit,
            'locale': self.country
        }
        headers = {'Authorization': 'Bearer {0}'.format(self.get_credentials().get('jwt_token'))}
        data = self.make_request(url, 'get', params=params, headers=headers)

        return json.loads(data)['data']

    def get_stream(self, video_id):
        stream = {}
        allowed_formats = ['ism', 'mpd']
        url = self.config['links']['vimondRestAPI'] + 'api/tve_web/asset/{0}/play.json'.format(video_id)
        params = {'protocol': 'VUDASH'}
        headers = {'Authorization': 'Bearer {0}'.format(self.get_credentials().get('vimond_token'))}
        data_dict = json.loads(self.make_request(url, 'get', params=params, headers=headers))['playback']
        stream['drm_protected'] = data_dict['drmProtected']

        if isinstance(data_dict['items']['item'], list):
            for i in data_dict['items']['item']:
                if i['mediaFormat'] in allowed_formats:
                    stream['mpd_url'] = i['url']
                    if stream['drm_protected']:
                        stream['license_url'] = i['license']['@uri']
                        stream['drm_type'] = i['license']['@name']
                    break
        else:
            stream['mpd_url'] = data_dict['items']['item']['url']
            if stream['drm_protected']:
                stream['license_url'] = data_dict['items']['item']['license']['@uri']
                stream['drm_type'] = data_dict['items']['item']['license']['@name']

        return stream

    def get_image_url(self, image_url):
        """Request the image from their image proxy. Can be extended to resize/add image effects automatically.
        See https://imageproxy.b17g.services/docs for more information."""
        if image_url:
            return '{0}?source={1}'.format(self.config['links']['imageProxy'], image_url)
        else:
            return None

    def parse_datetime(self, event_date):
        """Parse date string to datetime object."""
        date_time_format = '%Y-%m-%dT%H:%M:%S+02:00'
        datetime_obj = datetime(*(time.strptime(event_date, date_time_format)[0:6]))
        return datetime_obj

    def get_current_time(self):
        """Return the current local time."""
        return datetime.now()
