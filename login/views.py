from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth.views import login
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from tough.models import NoahUser
import tough.util as util
from datetime import datetime
import logging, re
from dateutil.parser import parse
from dateutil import tz
from django.utils.timezone import utc
from django.template.response import TemplateResponse
import simplejson

logger = logging.getLogger(__name__)

# Create your views here.
# This wraps the default login view and allows us to add session expiry
def login_view(request):
    logger.debug("login")
    # Get response from original login view
    try:
        response = login(request)
    except Exception, ex:
        logging.error(ex)
        raise Exception(ex)
    logger.debug('test is_authenticated: "%s"' %request.user.__class__)
    # If the user was authenticated get the cert expiry time to set session expiry time
    
    if request.user.is_anonymous():
        logger.warning("anonymous user")  
    elif request.user.is_authenticated():
        logger.debug("authenticated user")
        # Expires in 3 hours          
        u = NoahUser.objects.get(username=request.user)
        
        n = simplejson.loads(u.cookie)
        # valid_for=datetime.strptime(expires,'%a, %d-%b-%Y %H:%M:%S %Z')

        # Time in UTC
        exp_time_utc = parse(n["expires"])
        valid_for = exp_time_utc.astimezone(tz.tzlocal()).replace(tzinfo=utc)
 
        request.session.set_expiry(valid_for)
        response.set_cookie('newt_sessionid', 
                            value=n['newt_sessionid'], 
                            max_age=n['max_age'], 
                            expires=n['expires'], 
                            path=n['path'], 
                            domain=n['domain'],
                            secure=n['secure'])
        request.session['newt_sessionid'] = n['newt_sessionid']
    else:
        logger.error('NoahUser failed to authenticate and is not anonymous.')

    return response
    
  
@login_required  
def logout_view(request):
    u=get_object_or_404(NoahUser, username=request.user)

    response, content = util.newt_request('/auth', 'DELETE', cookie_str=u.cookie)
    if response.status_code != 200:
        logger.warning("NEWT logout failed: %s. Continuing NOVA logout"%content)
    

    u.cookie=None
    u.save()

    logout(request)
    logger.debug("logout %s"%request.user)

    # Change this to a default front page
    # Also add a front page mapping as the default target post login
    return redirect(settings.LOGOUT_REDIRECT_URL)
