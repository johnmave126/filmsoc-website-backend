# adapt from pycas
# Thanks to Jon Rifkin

#  Copyright 2013 John TAN
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

# Name field for pycas cookie
FLASK_CAS_NAME = "cas_auth"

# CAS Staus Codes:  returned to calling program by login() function.
CAS_OK = 0  # CAS authentication successful.
CAS_COOKIE_INVALID = 1  # PYCAS cookie is invalid (probably corrupted).
CAS_TICKET_INVALID = 2  # CAS server ticket invalid.


#  Status codes returned internally by function get_cookie_status().
COOKIE_AUTH = 0  # PYCAS cookie is valid.
COOKIE_NONE = 1  # No PYCAS cookie found.
COOKIE_INVALID = 2  # Invalid PYCAS cookie found.

# Status codes returned internally by function get_ticket_status().
TICKET_OK = 0  # Valid CAS server ticket found.
TICKET_NONE = 1  # No CAS server ticket found.
TICKET_INVALID = 2  # Invalid CAS server ticket found.

CAS_MSG = (
    "CAS authentication successful.",
    "PYCAS cookie is invalid (probably corrupted).",
    "CAS server ticket invalid.",
    "CAS server returned without ticket while in gateway mode.",
)

from app import app
from flask import request
import md5
import time
import urllib
import urlparse


#  Used for parsing xml.  Search str for first occurance of
#  <tag>.....</tag> and return text (striped of leading and
#  trailing whitespace) between tags.  Return "" if tag not
#  found.
def parse_tag(str, tag):
    tag1_pos1 = str.find("<" + tag)
    #  No tag found, return empty string.
    if tag1_pos1 == -1:
        return ""
    tag1_pos2 = str.find(">", tag1_pos1)
    if tag1_pos2 == -1:
        return ""
    tag2_pos1 = str.find("</" + tag, tag1_pos2)
    if tag2_pos1 == -1:
        return ""
    return str[tag1_pos2 + 1: tag2_pos1].strip()


#  Split string in exactly two pieces, return '' for missing pieces.
def split2(str, sep):
    parts = str.split(sep, 1) + ["", ""]
    return parts[0], parts[1]


#  Use hash and secret to encrypt string.
def makehash(str):
    m = md5.new()
    m.update(str)
    m.update(app.config['SECRET_KEY'])
    return m.hexdigest()[0: 8]


#  Validate ticket using cas 1.0 protocol
def validate_cas_1(cas_host, service_url, ticket):
    #  Second Call to CAS server: Ticket found, verify it.
    cas_validate = cas_host + "/cas/validate?ticket=" + ticket + "&service=" + service_url
    f_validate = urllib.urlopen(cas_validate)
    #  Get first line - should be yes or no
    response = f_validate.readline()
    #  Ticket does not validate, return error
    if response == "no\n":
        f_validate.close()
        return TICKET_INVALID, ""
    #  Ticket validates
    else:
        #  Get id
        id = f_validate.readline()
        f_validate.close()
        id = id.strip()
        return TICKET_OK, id


#  Validate ticket using cas 2.0 protocol
#    The 2.0 protocol allows the use of the mutually exclusive "renew" and "gateway" options.
def validate_cas_2(cas_host, service_url, ticket, opt):
    #  Second Call to CAS server: Ticket found, verify it.
    cas_validate = cas_host + "/cas/serviceValidate?ticket=" + ticket + "&service=" + service_url
    if opt:
        cas_validate += "&%s=true" % opt
    f_validate = urllib.urlopen(cas_validate)
    #  Get first line - should be yes or no
    response = f_validate.read()
    id = parse_tag(response, "cas:user")
    #  Ticket does not validate, return error
    if id == "":
        return TICKET_INVALID, ""
    #  Ticket validates
    else:
        return TICKET_OK, id


#  Check pycas cookie
def get_cookie_status():
    cookie_val = request.cookies.get('FLASK_CAS_NAME', None)

    if not cookie_val:
        return COOKIE_NONE, ""

    old_hash = cookie_val[0: 8]
    time_str, username = split2(cookie_val[8:], ':')
    if old_hash == makehash(cookie_val[8:]):
        return COOKIE_AUTH, username
    else:
        return COOKIE_INVALID, ""


def get_ticket_status(cas_host, service_url, protocol, opt):
    if request.args.get('ticket') is not None:
        ticket = request.args.get('ticket')
        if protocol == 1:
            ticket_status, id = validate_cas_1(cas_host, service_url, ticket, opt)
        else:
            ticket_status, id = validate_cas_2(cas_host, service_url, ticket, opt)
        #  Make cookie and return id
        if ticket_status == TICKET_OK:
            return TICKET_OK, id
        #  Return error status
        else:
            return ticket_status, ""
    else:
        return TICKET_NONE, ""


#-----------------------------------------------------------------------
#  Exported functions
#-----------------------------------------------------------------------

#  Login to cas and return user id.
#
#   Returns status, id, pycas_cookie.
#
def login(cas_host, service_url, protocol=2, opt=""):

    #  Check cookie for previous pycas state, with is either
    #     COOKIE_AUTH    - client already authenticated by pycas.
    #     COOKIE_GATEWAY - client returning from CAS_SERVER with gateway option set.
    #  Other cookie status are
    #     COOKIE_NONE    - no cookie found.
    #     COOKIE_INVALID - invalid cookie found.
    cookie_status, id = get_cookie_status()

    if cookie_status == COOKIE_AUTH:
        return CAS_OK, id, ""

    if cookie_status == COOKIE_INVALID:
        return CAS_COOKIE_INVALID, "", ""

    #  Check ticket ticket returned by CAS server, ticket status can be
    #     TICKET_OK      - a valid authentication ticket from CAS server
    #     TICKET_INVALID - an invalid authentication ticket.
    #     TICKET_NONE    - no ticket found.
    #  If ticket is ok, then user has authenticated, return id and
    #  a pycas cookie for calling program to send to web browser.
    ticket_status, id = get_ticket_status(cas_host, service_url, protocol, opt)

    if ticket_status == TICKET_OK:
        timestr = str(int(time.time()))
        hash = makehash(timestr + ":" + id)
        cookie_val = hash + timestr + ":" + id
        return CAS_OK, id, cookie_val

    else:
        return CAS_TICKET_INVALID, "", ""

def logout(cas_host, service_url):
    return cas_host + '/cas/logout?url=' + service_url
