from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.conf import settings
import httplib2
import os
from datetime import *
from dateutil import parser
from dateutil.tz import *
from django.utils.simplejson import JSONDecoder
import tough.util as util
import logging 
from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils.timezone import utc
import json

logger = logging.getLogger(__name__)
logger.setLevel(getattr(settings, 'LOG_LEVEL', logging.DEBUG))

class MyUserManager(BaseUserManager):
    def create_user(self, email, date_of_birth, password=None):
        """
        Creates and saves a NoahUser with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=MyUserManager.normalize_email(email),
            date_of_birth=date_of_birth,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, date_of_birth, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(email,
            password=password,
            date_of_birth=date_of_birth
        )
        user.is_admin = True
        user.save(using=self._db)
        return user

class NoahUser(AbstractBaseUser):
    """
    Extend NoahUser Model to include newt cookies
    """    
    # class Meta:
    #     proxy = True

    # TODO: Move this out of model and just pass back to user

    username = models.CharField(max_length=40, unique=True, db_index=True)
    USERNAME_FIELD = 'username'
    # username = models.CharField(max_length = 200)
    cookie = models.TextField(null=True, blank=True)

    def is_licensed_user(self):
        #check that they are in the appropriate group
        cookie_str=self.user.cookie
        checkurl = '/command/hopper/'
        cmd = '/usr/bin/groups %s' % self.username
        response, content = util.newt_request(checkurl, 'POST', params={'executable': cmd}, cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(content)
        result =JSONDecoder().decode(content)
        #replace "vasp" here with the appropriate group name
        if "vasp" in result['output']:
            return True
        else:
            return False


    def get_repos(self):
        """
        Pull down repos for a user
        """
        cookie_str=self.cookie
        url = '/account/user/%s/repos' % self.username
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(content)
            
        repo_dict=JSONDecoder().decode(content)
        
        repo_list=[ repo['rname'] for repo in repo_dict['items'] if repo['adminunit_type']=='REPO' ]
            
        return repo_list
    
    def get_all_jobs(self):
        """
        Return a list of all jobs
        """
        #get the list of jobs listed in the database as running and update them.
        dbrunning = Job.objects.filter(user=self.id).filter(nova_state__in=['submitted', 'started'])
        for runningjob in dbrunning: runningjob.update();
        #get the updated list 
        all_jobs = Job.objects.filter(user=self.id).order_by('-time_last_updated')
        return all_jobs
        
    def get_jobs(self):
        #appears to be only used in tests.py
        """
        Return a dict with jobs
        {
          {'toberun': [], 'running':[], 'complete': []}
        }
        
        """
        toberun = Job.objects.filter(user=self.id, nova_state='toberun')
        #get the list of jobs listed in the database as running and update them.
        dbrunning = Job.objects.filter(user=self.id).filter(nova_state__in=['submitted', 'started'])
        for runningjob in dbrunning: runningjob.update();
        #get the updated list of running jobs
        running = Job.objects.filter(user=self.id).filter(nova_state__in=['submitted', 'started'])
        #get completed and aborted and sort together by time submitted
        complete = Job.objects.filter(user=self.id).filter(nova_state__in=['completed', 'aborted']).order_by('time_submitted').reverse()[:5]

        return {'toberun': toberun, 'running':running, 'complete': complete}    