from django.conf import settings
import httplib2
import requests
import urllib, logging
import string
import mimetypes
import random
from django.utils import encoding as encoding
from django.core.files import File
import re


# Get an instance of a logger
logger = logging.getLogger(__name__)

def newt_request(url, req_method, params=None, cookie_str=None):
    newt_base_url=getattr(settings, 'NEWT_BASE_URL')

    full_url = newt_base_url+url
    conn = httplib2.Http(disable_ssl_certificate_validation=True)

    # Massage inputs
    if cookie_str:
        headers={'Cookie': cookie_str}
    else:
        headers=None

    if type(params) is dict:
        body=urllib.urlencode(params)
    elif (type(params) is str) or (type(params) is unicode):
        body=params
    else:
        body=None
    logger.debug("NEWT: %s %s"%(req_method,full_url))
    response, content = conn.request(full_url, req_method, body=body, headers=headers)
    # raise Exception(response)

    logger.debug("NEWT response: %s"%response.status)
    
    # TODO: Do we JSON decode content
    return (response, content)


def random_string(length):
    return ''.join(random.choice(string.letters) for ii in range(length + 1))


def encode_multipart_data(files, data=None):
    boundary = random_string(30)

    def get_content_type(filename):
        return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    def encode_field(field_name):
        return ('--' + boundary,
                'Content-Disposition: form-data; name="%s"' % field_name,
                '', str(data[field_name]))

    def encode_file(field_name):
        filename = encoding.iri_to_uri(files[field_name])
        return ('--' + boundary,
                'Content-Disposition: form-data; name="%s"; filename="%s"' % (field_name, filename),
                'Content-Type: %s' % get_content_type(filename),
                '', open(filename, 'rb').read())

    lines = []
    if data != None:
        for name in data:
            lines.extend(encode_field (name))
    for name in files:
        lines.extend(encode_file (name))
    lines.extend(('--%s--' % boundary, ''))
    body = '\r\n'.join (lines)

    headers = {'content-type': 'multipart/form-data; boundary=' + boundary,
               'content-length': str(len(body))}

    return body, headers

def upload_request(url, uploaded_file, filename, cookie_str=None):
    newt_base_url=getattr(settings, 'NEWT_BASE_URL')
    newtcookie = NewtCookie(cookie_str).__dict__
    cookies = {
        "newt_sessionid": newtcookie['newt_sessionid'].__str__(),
        "expires": newtcookie['expires'].__str__(),
        "domain": newtcookie['domain'].__str__(),
        "max_age": newtcookie['max_age'].__str__(),
        "path": newtcookie['path'].__str__(),
        "secure": newtcookie['secure'].__str__()
    }
    full_url = newt_base_url+url
    response = requests.post(full_url, cookies=cookies, files={"file": (filename, File(uploaded_file).read())})
    return response

def newt_upload_request(url, files, params=None, cookie_str=None):
    body, headers = encode_multipart_data(files, params)
    newt_base_url = getattr(settings, 'NEWT_BASE_URL')
    req_method = "POST"

    full_url = newt_base_url+url
    conn = httplib2.Http(disable_ssl_certificate_validation=True)

    # Massage inputs
    if cookie_str:
        headers.update({'Cookie': cookie_str})

    logger.debug("NEWT: %s %s" % (req_method, full_url))
    response, content = conn.request(full_url, req_method, body=body, headers=headers)

    logger.debug("NEWT response: %s" % response.status)

    # TODO: Do we JSON decode content
    return (response, content)


class NewtCookie:
    """
    Class to serialize NEWT cookie into an object. Makes it easier to set a cookie on the user response

    for k=v pairs, k becomes an attribute of the object with value v
    for singleton keys k, k becomes an attrubute of the object with value True  

    >>> n=NewtCookie('newt_sessionid=1234; expires=2010-10-10; secure')
    >>> n.sessionid
    1234
    >>> n.secure
    True
    """
    newt_sessionid=None
    expires=None
    domain=None
    max_age=None
    path=None
    secure=None

    def __init__(self, cookiestr):        
        cookie_array=cookiestr.split(';')
        for keyval in cookie_array:
            kvarray=keyval.split('=',1)
            
            # Ugh - ugly unicode hack
            if type(kvarray[0]) is unicode:
                tt={ord(u'-'): u'_'}
            else:
                tt=string.maketrans('-','_')
            
            key=kvarray[0].strip().lower().translate(tt)
            
            if len(kvarray)==2:
                self.__dict__[key]=kvarray[1]
            elif len(kvarray)==1:
                self.__dict__[key]=True

def parse_file_for_block_vars(input_file):
    from tough.models import BlockVariable, BlockType, QualifiedBlockRef
    lines = input_file.split("\n")
    var_name = ""
    blockType = ""
    var_val = ""
    varnameregex = '(?<=\s{2})\w+'
    blocktitleregex = '(?<=>>>)\w+'
    blockendregex = '(?<=<<<)\w+'
    # varvalregex = '(?<=[=]).+(?=[,\s{1}])'
    blocking = False
    for line in lines:
        if(re.search(blocktitleregex, line) != None):
            blockType = re.search(blocktitleregex, line).group(0).lower()
            b = QualifiedBlockRef.objects.get(name = blockType).blockType
            blocking = True
        if(blocking == True and (b.required==0 or b.required==1)):
            if(re.search(varnameregex, line) != None):
                var_name = re.search(varnameregex,line).group(0).lower()
                block_var = BlockVariable(blockType = b, var_name = var_name)
                block_var.save()
        if(re.search(blockendregex,line) != None):
            blocking = False


