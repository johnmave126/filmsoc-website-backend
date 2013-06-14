from math import sqrt
from flask import g
from app import app
import ldap


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
        conn.start_tls_s()
        print conn.simple_bind_s('HKUST\\' + app.config['SOCIETY_USERNAME'], app.config['SOCIETY_PASSWORD'])
    except ldap.LDAPError, e:
        print e
        return None
