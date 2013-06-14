from math import sqrt
from flask import g
from app import app
import ldap
from ldap.filter import escape_filter_chars


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
        filter = '(CN=' + escape_filter_chars(itsc) + ')'
        attrs = ['displayName', 'whenCreated']

        r = conn.search(base_dn, ldap.SCOPE_BASE, filter, attrs)
        type, data = conn.result(r, timeout=10)
        entry_dn, r_attrs = data[0]
        print type(r_attrs)
    except ldap.INVALID_CREDENTIALS:
        pass  # send email here
        return None
    except ldap.LDAPError:
        return None
