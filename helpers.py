from math import sqrt
from flask import g
from app import app
import ldap
from ldap.filter import escape_filter_chars
import urllib2
import datetime
from urllib import urlencode
from BeautifulSoup import BeautifulStoneSoup


def after_this_request(f):
    if not hasattr(g, 'after_request_callbacks'):
        g.after_request_callbacks = []
    g.after_request_callbacks.append(f)
    return f


@app.after_request
def call_after_request_callbacks(response):
    for callback in getattr(g, 'after_request_callbacks', ()):
        callback(response)
    return response


def confidence(ups, downs):
    n = ups + downs

    if n == 0:
        return 0

    z = 1.0
    phat = float(ups) / n
    return (phat + (z * z) / (2 * n) - z * sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / (1 + z * z / n)


def query_user(itsc):
    conn = ldap.initialize(app.config['LDAP_SERVER'])
    conn.set_option(ldap.OPT_REFERRALS, 0)
    conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
    try:
        conn.simple_bind_s('HKUST\\' + app.config['SOCIETY_USERNAME'], app.config['SOCIETY_PASSWORD'])

        base_dn = 'CN=Users,DC=ust,DC=hk'
        Filter = '(CN=' + escape_filter_chars(itsc) + ')'
        attrs = ['displayName', 'whenCreated']

        r = conn.search(base_dn, ldap.SCOPE_ONELEVEL, Filter, attrs)
        Type, data = conn.result(r, timeout=10)
        if len(data) != 1:
            #  not found or something weird
            return None
        entry_dn, r_attrs = data[0]
        r_dict = {}
        for key, value in r_attrs.iteritems():
            r_dict[key] = value[0]
        return r_dict
    except ldap.INVALID_CREDENTIALS:
        pass  # send email here
        return None
    except ldap.LDAPError:
        return None


def update_mailing_list(new_list):
    auth_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    auth_mgr.add_password(None, "https://lists.ust.hk/cgi-bin/itsc/mailinglist/restricted/", app.config['SOCIETY_USERNAME'], app.config['SOCIETY_PASSWORD'])
    auth_handler = urllib2.HTTPBasicAuthHandler(auth_mgr)

    opener = urllib2.build_opener(auth_handler)

    # get whotime
    url = 'https://lists.ust.hk/cgi-bin/itsc/mailinglist/restricted/listadmin_majorcool'
    payload = {
        'action': 'edit',
        'list': 'su-film-list',
        'view': 'list'
    }
    data = urlencode(payload)
    response = opener.open(url, data).read()
    print response
