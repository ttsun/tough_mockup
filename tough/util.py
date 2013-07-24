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
import simplejson


# Get an instance of a logger
logger = logging.getLogger(__name__)


def newt_request(url, req_method, params=None, cookie_str=None):
    newt_base_url = getattr(settings, "NEWT_BASE_URL")
    full_url = str(newt_base_url + url.replace("//", "/").strip())
    if cookie_str:
        cookies = simplejson.loads(cookie_str)
    else:
        cookies = None
    response = requests.request(req_method, full_url, data=params, cookies=cookies)
    return (response, response.content)


def upload_request(url, uploaded_file, filename, cookie_str=None):
    newt_base_url = getattr(settings, "NEWT_BASE_URL")
    full_url = str(newt_base_url + url.replace("//", "/").strip())
    if cookie_str:
        cookies = simplejson.loads(cookie_str)
    else:
        cookies = None
    response = requests.post(full_url, cookies=cookies, files={"file": (filename, File(uploaded_file).read())})
    return response


def parse_file_for_block_vars(input_file):
    from tough.models import BlockVariable, BlockType, QualifiedBlockRef
    lines = input_file.split("\n")
    var_name = ""
    blockType = ""
    name_list = ""
    commented = False
    varnameregex = '(?<=\s{2})[(\!\s)\w\(\)\d]+(?==)'
    multiplevarregex = '(?<=\()[0-9](?=\))'
    blocktitleregex = '(?<=>>>)\w+'
    blockendregex = '(?<=<<<)\w+'
    namelistregex = '(?<=&)\w+(?=\s)'
    blocking = False
    for line in lines:
        if(re.search(blocktitleregex, line) != None):
            blockType = re.search(blocktitleregex, line).group(0).lower()
            b = QualifiedBlockRef.objects.get(name = blockType).blockType
            blocking = True
        if(blocking == True and (b.required==0 or b.required==1)):
            if(re.search(namelistregex,line) != None):
                name_list = re.search(namelistregex,line).group(0).lower()
            if(re.search(varnameregex, line) != None):
                commented = False
                var_name = re.search(varnameregex,line).group(0).lower()
                if(re.search("!",re.search('.+(?==)',line).group(0)) != None):
                    commented = True
                var_name = var_name.strip("! ")
                if(re.search(multiplevarregex,var_name) != None):
                    numvars = int(re.search(multiplevarregex,var_name).group(0)) + 1
                    for x in range(numvars):
                        var_name = var_name[:-3] + "(" + str(x) + ")"
                        block_var = BlockVariable(blockType = b, var_name = var_name, name_list = name_list, commented = commented)
                        block_var.save()
                else: 
                    block_var = BlockVariable(blockType = b, var_name = var_name, name_list = name_list, commented = commented)
                    block_var.save()
        if(re.search(blockendregex,line) != None):
            blocking = False


