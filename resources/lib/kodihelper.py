import re

from .cmore import CMore

import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import inputstreamhelper
from xbmcaddon import Addon


class KodiHelper(object):
    def __init__(self, base_url=None, handle=None):
        addon = self.get_addon()
        self.base_url = base_url
        self.handle = handle
        self.addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
        self.addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
        self.addon_name = addon.getAddonInfo('id')
        self.addon_version = addon.getAddonInfo('version')
        self.language = addon.getLocalizedString
        self.logging_prefix = '[{n}-{v}]'.format(n=self.addon_name,
                                                 v=self.addon_version)
        if not xbmcvfs.exists(self.addon_profile):
            xbmcvfs.mkdir(self.addon_profile)
        self.c = CMore(self.addon_profile, self.get_setting('locale'), True)

    def get_addon(self):
        """Returns a fresh addon instance."""
        return Addon()

    def get_setting(self, setting_id):
        addon = self.get_addon()
        setting = addon.getSetting(setting_id)
        if setting == 'true':
            return True
        elif setting == 'false':
            return False
        else:
            return setting

    def set_setting(self, key, value):
        return self.get_addon().setSetting(key, value)

    def ia_settings(self):
        """Open InputStream Adaptive settings."""
        ia_addon = Addon('inputstream.adaptive')
        ia_addon.openSettings()

    def log(self, string):
        msg = '{p}: {s}'.format(p=self.logging_prefix, s=string)
        xbmc.log(msg=msg.encode('utf-8'), level=xbmc.LOGDEBUG)

    def dialog(self, dialog_type, heading, message=None, options=None, nolabel=None, yeslabel=None):
        dialog = xbmcgui.Dialog()
        if dialog_type == 'ok':
            dialog.ok(heading, message)
        elif dialog_type == 'yesno':
            return dialog.yesno(heading, message, nolabel=nolabel, yeslabel=yeslabel)
        elif dialog_type == 'select':
            ret = dialog.select(heading, options)
            if ret > -1:
                return ret
            else:
                return None

    def get_user_input(self, heading, hidden=False):
        keyboard = xbmc.Keyboard('', heading, hidden)
        keyboard.doModal()
        if keyboard.isConfirmed():
            # FIXME: Not compatible with Python 2.X!
            query = keyboard.getText()
            self.log('User input string: {q}'.format(q=query))
        else:
            query = None

        if query and len(query) > 0:
            return query
        else:
            return None

    def get_numeric_input(self, heading):
        dialog = xbmcgui.Dialog()
        numeric_input = dialog.numeric(0, heading)

        if len(numeric_input) > 0:
            return str(numeric_input)
        else:
            return None

    def set_login_credentials(self):
        username = self.get_setting('username')
        password = self.get_setting('password')

        if self.get_setting('tv_provider_login'):
            operator = self.get_operator(self.get_setting('operator'))
            if not operator:
                return False
        else:
            operator = None
            self.set_setting('operator_title', '')
            self.set_setting('operator', '')

        if not username or not password:
            if operator:
                return self.set_tv_provider_credentials()
            else:
                self.dialog('ok', self.language(30017), self.language(30018))
                self.get_addon().openSettings()
                return False
        else:
            return True

    def get_token(self):
        if not self.get_setting('username') or not self.get_setting('password'):
            self.set_login_credentials()
        username = self.get_setting('username')
        password = self.get_setting('password')
        operator = self.get_setting('operator')
        login_data = self.c.login(username, password, operator)
        if 'data' in login_data and 'login' in login_data['data']:
            self.set_setting('login_token', login_data['data']['login']['session']['token'])
            return login_data['data']['login']['session']['token']
        else:
            return ''

    def set_tv_provider_credentials(self):
        operator = self.get_setting('operator')
        operators = self.c.get_operators()
        for i in operators:
            if operator == i['name']:
                username_type = i['username']
                password_type = i['password']
                info_message = re.sub('<[^<]+?>', '', i['login'])  # strip html tags
                break
        self.dialog('ok', self.get_setting('operator_title'), message=info_message)
        username = self.get_user_input(username_type)
        password = self.get_user_input(password_type, hidden=True)

        if username and password:
            self.set_setting('username', username)
            self.set_setting('password', password)
            return True
        else:
            return False

    def set_locale(self, locale=None):
        countries = ['sv_SE', 'da_DK', 'nb_NO']
        if not locale:
            options = [self.language(30013), self.language(30014), self.language(30015)]
            selected_locale = self.dialog('select', self.language(30012), options=options)
            if selected_locale is None:
                selected_locale = 0  # default to .se
            self.set_setting('locale_title', options[selected_locale])
            self.set_setting('locale', countries[selected_locale])
            self.set_setting('login_token', '')  # reset token when locale is changed

        return True

    def get_operator(self, operator=None):
        if not operator:
            self.set_setting('tv_provider_login', 'true')
            operators = self.c.get_operators()
            options = [x['title'] for x in operators]

            selected_operator = self.dialog('select', self.language(30010), options=options)
            if selected_operator is not None:
                operator = operators[selected_operator]['name']
                operator_title = operators[selected_operator]['title']
                self.set_setting('operator', operator)
                self.set_setting('operator_title', operator_title)

        return self.get_setting('operator')

    def reset_login(self):
        self.set_setting('operator', '')
        self.set_setting('operator_title', '')
        self.set_setting('username', '')
        self.set_setting('password', '')
        self.set_setting('login_token', '')

    def add_item(self, title, url, folder=True, playable=False, info=None, art=None, content=False):
        addon = self.get_addon()
        listitem = xbmcgui.ListItem(label=title)

        if playable:
            listitem.setProperty('IsPlayable', 'true')
            folder = False
        if art:
            listitem.setArt(art)
        else:
            art = {
                'icon': addon.getAddonInfo('icon'),
                'fanart': addon.getAddonInfo('fanart')
            }
            listitem.setArt(art)
        if info:
            listitem.setInfo('video', info)
        if content:
            xbmcplugin.setContent(self.handle, content)

        xbmcplugin.addDirectoryItem(self.handle, url, listitem, folder)

    def eod(self):
        """Tell Kodi that the end of the directory listing is reached."""
        xbmcplugin.endOfDirectory(self.handle)

    def play(self, video_id):
        login_token = self.get_setting('login_token')
        if not login_token:
            login_token = self.get_token()
        try:
            stream = self.c.get_stream(video_id, login_token=login_token)
        except self.c.CMoreError as error:
            if str(error) == 'User is not authenticated':
                self.log('We have no valid session. Login needed.')
                login_token = self.get_token()
                stream = self.c.get_stream(video_id, login_token)
            else:
                self.dialog('ok', self.language(30028), str(error))
                return

        if stream['type'] == 'hls':
            protocol = 'hls'
        else:
            protocol = 'mpd'
        if 'license' in stream:
            drm = 'widevine'
        else:
            drm = None

        ia_helper = inputstreamhelper.Helper(protocol, drm=drm)
        if ia_helper.check_inputstream():
            playitem = xbmcgui.ListItem(path=stream['manifestUrl'])
            playitem.setProperty('inputstreamaddon', 'inputstream.adaptive')
            playitem.setProperty('inputstream.adaptive.manifest_type',
                                 protocol)
            if drm:
                playitem.setProperty('inputstream.adaptive.license_type',
                                     'com.widevine.alpha')
                license_server = stream['license']['castlabsServer']
                license_header = '&'.join(['Content-Type=',
                                           'x-dt-auth-token=' +
                                           stream['license']['castlabsToken']])
                license_key = '{s}|{h}|{data}|'.format(s=license_server,
                                                       h=license_header,
                                                       data='R{SSM}')
                playitem.setProperty('inputstream.adaptive.license_key', license_key)
            xbmcplugin.setResolvedUrl(self.handle, True, listitem=playitem)

    def get_as_bool(self, string):
        if string == 'true':
            return True
        else:
            return False
