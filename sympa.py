import urllib2
from urllib import urlencode, quote
import cookielib
from bs4 import BeautifulSoup

__all__ = [
    "Sympa",
]


class Sympa(object):
    """An interface to manipulate Sympa mailing list since the SOAP
    API is disabled.

    The class simulates the access from browser and manipulate the
    mailing list through web interface of sympa.

    :param username:
        The account name
    :param password:
        The account password
    :param cas_server:
        The CAS server to go for ticket
    :param sympa_root:
        The root of sympa web interface
    """
    def __init__(self, username, password, cas_server, sympa_root):
        self.sympa_root = sympa_root

        self.setup(username, password, cas_server)

    def setup(self, username, password, cas_server):
        """Set up the class. Construct request container for later use
        """

        # Request container
        cookie_jar = cookielib.CookieJar()
        self.opener = urllib2.build_opener(
            urllib2.HTTPCookieProcessor(cookie_jar))

        # Contact Sympa to acquire first cookie
        payload = urlencode({
            'action': 'sso_login',
            'auth_service_name': 'Login',
            'action_sso_login': 'Login'
        })
        self.opener.open(self.sympa_root, payload)

        # Contact CAS to get ticket
        login_url = '%s/cas/login?service=%s' % \
            (cas_server, quote(self.sympa_root + '/sso_login_succeeded/Login'))
        ret = self.opener.open(login_url)

        # first retrieve
        # acquire tokens from page
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
        """Return the list of emails from mailing list

        :param mailing_list:
            The mailing list to retrieve
        """
        ret = self.opener.open("%s/dump/%s/light" %
            (self.sympa_root, mailing_list))
        return filter(None, ret.read().split('\n'))

    def del_email(self, mailing_list, emails):
        """Delete subscribers from mailing list

        :param mailing_list:
            The mailing list to manipulate
        :param emails:
            Emails to delete from the list
        """
        if len(emails) == 0:
            return

        payload = urlencode({
            'list': mailing_list,
            'quiet': 'on',
            'email': emails,
            'action_del': 'Delete selected email addresses'
        }, doseq=True)

        self.opener.open(self.sympa_root, payload)

    def add_email(self, mailing_list, emails):
        """Add subscribers to mailing list

        :param mailing_list:
            The mailing list to manipulate
        :param emails:
            The email accounts to add
        """
        if len(emails) == 0:
            return

        payload = urlencode({
            'list': mailing_list,
            'quiet': 'on',
            'dump': '\n'.join(emails),
            'used': 'true',
            'action_add': 'Add subscribers'
        }, doseq=True)

        self.opener.open(self.sympa_root, payload)

    def replace_email(self, mailing_list, emails):
        """Replace the subscribers

        :param mailing_list:
            The mailing list to manipulate
        :param emails:
            The accounts to replace current ones
        """
        current_set = set(self.get_list(mailing_list))
        target_set = set(emails)
        self.del_email(mailing_list, list(current_set - target_set))
        self.add_email(mailing_list, list(target_set - current_set))
