import urllib2
from urllib import urlencode, quote
import cookielib
from bs4 import BeautifulSoup

__all__ = [
    "Sympa",
]


class Sympa(object):
    def __init__(self, username, password, cas_server, sympa_root):
        self.sympa_root = sympa_root

        self.setup(username, password, cas_server)

    def setup(self, username, password, cas_server):
        cookie_jar = cookielib.CookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))

        payload = urlencode({
            'action': 'sso_login',
            'auth_service_name': 'Login',
            'action_sso_login': 'Login'
        })
        self.opener.open(self.sympa_root, payload)

        login_url = cas_server + '/cas/login?service=' + quote(self.sympa_root + '/sso_login_succeeded/Login')
        ret = self.opener.open(login_url)

        # first retrieve
        ret_doc = ret.read()
        soup = BeautifulSoup(ret_doc)
        ticket = soup.find("input", {"name": "lt"}).get('value', '')
        execution = soup.find("input", {"name": "execution"}).get('value', '')

        payload = urlencode({
            'username': username,
            'password': password,
            'lt': ticket,
            'execution': execution,
            'warn': True,
            '_eventId': 'submit'
        })
        # log in and leave alone the opener
        ret = self.opener.open(login_url, payload)

    def get_list(self, mailing_list):
        ret = self.opener.open(self.sympa_root + ("/dump/%s/light" % mailing_list))
        return ret.read().split('\n')

    def del_email(self, mailing_list, emails):
        payload = urlencode({
            'list': mailing_list,
            'quiet': 'on',
            'email': emails,
            'action_del': 'Delete selected email addresses'
        }, doseq=True)

        self.opener.open(self.sympa_root, payload)

    def add_email(self, mailing_list, emails):
        payload = urlencode({
            'list': mailing_list,
            'quiet': 'on',
            'dump': '\n'.join(emails),
            'used': 'true',
            'action_add': 'Add subscribers'
        }, doseq=True)

        self.opener.open(self.sympa_root, payload)

    def replace_email(self, mailing_list, emails):
        current_set = set(self.get_list(mailing_list))
        target_set = set(emails)
        self.del_email(mailing_list, list(current_set - target_set))
        self.add_email(mailing_list, list(target_set - current_set))
