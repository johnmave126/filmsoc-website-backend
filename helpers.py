from math import sqrt
from ftplib import FTP
import smtplib
import ldap
from ldap.filter import escape_filter_chars
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

from flask import g
import sympa
from app import app

__all__ = [
    'after_this_request',
    'confidence',
    'query_user',
    'get_sympa',
    'update_mailing_list',
    'upload_file',
    'send_email',
]


def after_this_request(f):
    """A function wrapper to register action after this Flask request"""

    if not hasattr(g, 'after_request_callbacks'):
        g.after_request_callbacks = []
    g.after_request_callbacks.append(f)
    return f


@app.after_request
def call_after_request_callbacks(response):
    """Register to Flask after_request for after_this_request"""

    for callback in getattr(g, 'after_request_callbacks', ()):
        response = callback(response)
    return response


def confidence(ups, downs):
    """Return Wilson score confidence interval for a Bernoulli parameter

    :param ups:
        The +1s
    :param downs:
        The -1s

    Note that the calculation is modified so that there is weight to -1s
    The return value is a float number with sign
    """

    n = ups + downs

    if n == 0:
        return 0

    z = 1.0
    phat = float(ups) / n
    phat_volume = (phat + (z * z) / (2 * n) -
                    z * sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / \
                    (1 + z * z / n)
    quat = float(downs) / n
    quat_volume = (quat + (z * z) / (2 * n) -
                    z * sqrt((quat * (1 - quat) + z * z / (4 * n)) / n)) / \
                    (1 + z * z / n)
    return phat_volume - quat_volume / 2


def query_user(itsc, attrs = ['displayName']):
    """Connect to HKUST Active Directory to query relative infomation

    :param itsc:
        The ITSC account of the person queried
    :param attrs:
        The information to query (default ['displayName'])

    Return a dict containing the information
    """
    conn = ldap.initialize(app.config['LDAP_SERVER'])
    conn.set_option(ldap.OPT_REFERRALS, 0)
    conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
    try:
        conn.simple_bind_s('HKUST\\' + app.config['SOCIETY_USERNAME'],
                            app.config['SOCIETY_PASSWORD'])

        base_dn = 'CN=Users,DC=ust,DC=hk'
        Filter = '(CN=' + escape_filter_chars(itsc) + ')'

        r = conn.search(base_dn, ldap.SCOPE_ONELEVEL, Filter, attrs)
        Type, data = conn.result(r, timeout=10)
        if len(data) != 1:
            #  not found or something weird
            return None
        entry_dn, r_attrs = data[0]
        r_dict = {}
        for key, value in r_attrs.iteritems():
            r_dict[key] = value[0]
        conn.unbind()
        return r_dict
    except ldap.INVALID_CREDENTIALS:
        return None
    except ldap.LDAPError, e:
        print e
        return None


def get_sympa():
    """Return a sympa instance for management
    """
    return sympa.Sympa(
        app.config['SOCIETY_USERNAME'],
        app.config['SOCIETY_PASSWORD'],
        app.config['AUTH_SERVER'],
        app.config['SYMPA_SERVER']
    )


def update_mailing_list(new_list):
    """Update the mailing list

    :param new_list:
        The list to replace the present
    """
    sympa_mgmt = get_sympa()
    member_list = map(lambda x: x + "@ust.hk", new_list)
    sympa_mgmt.replace_email(app.config['MAILING_LIST'], member_list)


def upload_file(filename, file_handler):
    """Upload a file to FTP server

    :param filename:
        The name to be stored in FTP
    :param file_handler:
        The file to be uploaded
    """
    conn = FTP('ihome.ust.hk', app.config['SOCIETY_USERNAME'],
                app.config['SOCIETY_PASSWORD'])
    conn.cwd('/asset/upload')
    conn.storbinary("STOR " + filename, file_handler)
    conn.quit()


def send_email(receiver, bcc, subject, body):
    """Send an email

    :param receiver:
        A list of receivers
    :param bcc:
        A list of receivers who will not be shown in to:
    :param subject:
        The subject of the email
    :param body:
        The body of the email
    """
    from_address = app.config['SOCIETY_USERNAME'] + '@ust.hk'

    msg = MIMEMultipart()
    msg['From'] = msg['Reply-To'] = \
        '"Film Society, HKUSTSU"<%s>' % from_address
    msg['To'] = COMMASPACE.join(receiver)
    msg['Subject'] = '[Film Society]' + subject
    msg['Date'] = formatdate(localtime=True)
    msg.attach(MIMEText(body, 'html', 'utf-8'))

    smtp = smtplib.SMTP('smtp.ust.hk')
    smtp.login(app.config['SOCIETY_USERNAME'], app.config['SOCIETY_PASSWORD'])
    to_list = list(set(receiver + bcc))
    smtp.sendmail(from_address, to_list, msg.as_string())
    smtp.quit()
