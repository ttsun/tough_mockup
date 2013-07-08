from models import NoahUser
from django.utils.simplejson import JSONDecoder
import util as util
import logging
logger = logging.getLogger(__name__)

class NEWTBackend:
    """
    Authenticate against NEWT.

    """

    supports_object_permissions = False
    supports_anonymous_user = False
    supports_inactive_user = False

    def authenticate(self, username=None, password=None):
        url="/auth"
        params={'username': username, 'password': password}

        response, content=util.newt_request(url, 'POST', params=params)


        auth_dict=JSONDecoder().decode(content)

        # If the user was logged in:
        if auth_dict['auth']:
            
            try:
                user = NoahUser.objects.get(username=username)
                logger.debug("Got existing user")
                user.cookie = response['set-cookie']
                user.save()
            except NoahUser.DoesNotExist:
                logger.debug("New user")
                # Create a new user.
                try:
                    user = NoahUser(username=username)
                    # TODO: remove once other interfaces are ready
                    user.cookie = response['set-cookie']
                    user.save()
                except Exception, e:
                    logger.warning('NoahUser creation failed: '+str(e))
              
            # TODO: Set the cookie somewhere?
            return user
        
        logger.debug("Auth failed")
        return None

    def get_user(self, user_id):
        try:
            return NoahUser.objects.get(pk=user_id)
        except NoahUser.DoesNotExist:
            return None
