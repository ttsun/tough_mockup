from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.conf import settings
import httplib2
import os
from datetime import *
from dateutil import parser
from dateutil.tz import *
import simplejson
import tough.util as util
import logging
from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils.timezone import utc
from django.forms import widgets

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
        cookie_str = self.cookie
        checkurl = '/command/hopper/'
        cmd = '/usr/bin/groups %s' % self.username
        response, content = util.newt_request(checkurl, 'POST', params={'executable': cmd}, cookie_str=cookie_str)
        result = simplejson.loads(content)
        if response['status'] != '200':
            raise Exception(content)
        if "osp" in result['output']:
            return True
        else:
            return False


    def get_repos(self):
        """
        Pull down repos for a user
        """
        cookie_str = self.cookie
        url = '/account/user/%s/repos' % self.username
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        if response['status'] != '200':
            raise Exception(content)
            
        repo_dict = simplejson.loads(content)
        
        repo_list = [repo['rname'] for repo in repo_dict['items'] if repo['adminunit_type'] == 'REPO']
            
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


class Job(models.Model):
    """
    Model for Jobs submitted to NEWT
    """

    # Required fields - user, jobdir, machine
    user = models.ForeignKey(NoahUser)
    jobdir = models.CharField(max_length=1024)
    machine = models.CharField(max_length=256)

    # field to keep track of the job's state from Nova's point of view
    NOVA_STATE_CHOICES = (
                         ('toberun', 'to be run but not yet queued'),
                         ('submitted', 'in a queue'),
                         ('started', 'running on a nersc machine'),
                         ('aborted', 'started and no longer running but did not run to completion'),
                         ('completed', 'completed or stopped'),
                         )
    nova_state = models.CharField(max_length=1, choices=NOVA_STATE_CHOICES, default='toberun')

    # Defaults to tough.pbs
    jobfile = models.CharField(max_length=256, blank=True, default="tough.pbs")

    # Input blocks/files
    blocks = {
        'GENER':''
    }
    # Generated by PBS - update() fills in current values 
    pbsjobid = models.CharField(max_length=256, blank=True)
    status = models.CharField(max_length=32, blank=True)
    jobname = models.CharField(max_length=256, blank=True)
    timeuse = models.CharField(max_length=256, blank=True)
    queue = models.CharField(max_length=256, blank=True)
    
    # Useful timestamps
    time_last_updated = models.DateTimeField(null=True, blank=True)
    time_submitted = models.DateTimeField(null=True, blank=True)
    time_started = models.DateTimeField(null=True, blank=True)    
    time_completed = models.DateTimeField(null=True, blank=True)

    

    
    def create_dir(self):
        # TODO: add kwargs for dir
        cookie_str=self.user.cookie
        url = '/command/' + self.machine
        response, content = util.newt_request(url, 'POST', params={'executable': '/bin/mkdir -p ' + self.jobdir}, cookie_str=cookie_str)
        if response['status']!='200':            
            import ipdb; ipdb.set_trace()
            raise Exception(response)
        
        content=simplejson.loads(content)
        if content['error']!="":
            raise Exception(content['error'])
            
        return content

    def save_block(self, blockType, contents):
        b = self.block_set.filter(blockType="blockType")
        b.content = contents
        b.save()

    def put_file(self, filename, contents, *args, **kwargs):
        """
        >>> j.put_file("myfile", "#my contents\nhello world\n")
        
        """
        if contents == '':
            del_file(filename)
        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
            
        cookie_str=self.user.cookie
        url = '/file/%s%s/%s' % (self.machine, path, filename)
        response, content = util.newt_request(url, 'PUT', params=contents, cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(content)
        return simplejson.loads(content)
 
    def upload_file(self, filename, filepath, *args, **kwargs):
        """
        >>> j.upload_file("myfile", "/path/to/myfile")
        
        """
        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
            
        cookie_str=self.user.cookie
        url = '/file/%s%s/%s' % (self.machine, path, filename)
        files={'file': filepath}
        response, content = util.newt_upload_request(url, files, cookie_str=cookie_str) #problem here
        if response['status']!='200':
            raise Exception(response)
        return simplejson.loads(response)
       
    def del_file(self, filename,  *args, **kwargs):
        """
        >>> j.del_file("myfile")
        
        """
        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
            
        cookie_str=self.user.cookie
        url = '/file/%s%s/%s' % (self.machine, path, filename)
        response, content = util.newt_request(url, 'DELETE', cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(content)
        return simplejson.loads(content)        
        
        
    def get_file(self, filename, *args, **kwargs):
        """
        >>> j.get_file("myfile")
        File contents of myfile
        
        """
        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
            
        cookie_str=self.user.cookie
        url = '/file/%s%s/%s?view=read' % (self.machine, path, filename)
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        if response['status']!='200':
            raise IOError(content)
        return content
    
    
    def get_zip(self, *args, **kwargs):
        """
        >>>j.get_zip()
        zip file of entire jobdir directory
        
        """
        #make a zip of the dir on the hpc side
        directory = self.jobdir
        slash = directory.rfind("/")
        zipfilename = directory[slash+1:] + ".zip"
        cookie_str=self.user.cookie
        url = '/command/' + self.machine
        newtcommand = { 'executable': '/usr/bin/zip -rj /tmp/' + zipfilename + ' ' + directory }
        response, content = util.newt_request(url, 'POST', params=newtcommand, cookie_str=cookie_str)
        if response['status']!='200':
            raise IOError(content)
        #fetch the newly created zip
        url = '/file/%s/tmp/%s?view=read' % (self.machine, zipfilename)
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        if response['status']!='200':
            raise IOError(content)
        return content
        
        
    def del_dir(self, *args, **kwargs):
        """
        >>> j.get_dir()
        [{listing1},{listing2},]

        """

        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
        cookie_str=self.user.cookie
        url = '/command/%s/' % (self.machine)    

        response, content=util.newt_request(url, 'POST',  params={'executable': '/bin/bash -c "/bin/rm -rf %s"'%path }, cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(response)        

        content=simplejson.loads(content)
        if content['error']!="":
            raise Exception(content['error'])

        return content

    def get_dir(self, *args, **kwargs):
        """
        >>> j.get_dir()
        [{listing1},{listing2},]

        """

        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
        
        cookie_str=self.user.cookie
        url = '/file/%s%s' % (self.machine, path)
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        if response['status']!='200':
            raise IOError(content)
            
        dir_info=simplejson.loads(content)
        
        return dir_info
        
    def move_dir(self, tgtdir, *args, **kwargs):
        if 'srcdir' in kwargs:
            srcdir=kwargs['srcdir']
        else:
            srcdir=self.jobdir
            
        cookie_str=self.user.cookie
        url = '/command/%s/' % (self.machine)

        response, content=util.newt_request(url, 'POST',  params={'executable': '/bin/bash -c "/bin/mv %s %s"'%(srcdir, tgtdir) }, cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(response)        

        content=simplejson.loads(content)
        if content['error']!="":
            raise Exception(content['error'])

        return content
        
            

        
        
    def is_empty(self, srcdir):
        """
        Takes a directory name and tests if it is empty
        """
        dir_dict=self.get_dir(dir=srcdir)

        
        if len(dir_dict)==2:
            ls=[ dirent['name'] for dirent in dir_dict ]
            if ('.' in ls) and ('..' in ls):
                return True
            
        return False
        
    def import_files(self, src_dir, *args, **kwargs):
        """Move files from src_dir to self.dir
            possible kwargs:
            dir='/target/path'
            filelist=['list','of','files','in','src_dir']
        
        """
        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
            
        if 'filelist' in kwargs:
            filelist=kwargs['filelist']
        else:
            filelist=['*',]
            

        filestr=' '.join([ "%s/%s"%(src_dir,filename) for filename in filelist ])
        
        cookie_str=self.user.cookie
        url = '/command/%s/' % (self.machine)
        
        response, content=util.newt_request(url, 'POST',  params={'executable': '/bin/bash -c "/bin/cp %s %s"'%(filestr, path) }, cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(response)        
        
        content=simplejson.loads(content)
        if content['error']!="":
            # if src dir is empty ignore
            # Make sure we are dealing with a dir cp
            if (not 'filelist' in kwargs) and (self.is_empty(src_dir)):
                return
            #if src dir is target dir, ignore
            if(src_dir  in path):
                return
            
            raise Exception(content['error'])
            
        return content
        
    def get_timestamp(self, filename, *args, **kwargs):
        """
        >>> j.get_timestamp("started")
        datetime object
        
        Get the contents of the file (output of /bin/date -u  +'%a %b %d %H:%M:%S %Z %Y') and parse as a timestamp
        """

        try:
            content=self.get_file(filename, *args, **kwargs)
        except IOError, ex:
            # Can't find the file - just return none
            if(filename != 'completed'): logger.warn("Cannot read file: %s \n. Error %s"%(filename, str(ex)))
            return None
        content=content.strip()
        format_string = '%a %b %d %H:%M:%S %Z %Y'
        ts = datetime.strptime(content, format_string)

        #ts=parser.parse(content)  this approach gave inconsistent datetime objects
        return ts

    def submit(self):
        """
        >>> j=Job(user=request.user, machine="host", jobdir="/path/to/jobdir")
        >>> j.save()
        >>> j.submit()
        """
        cookie_str=self.user.cookie
        url = '/queue/%s/' % self.machine
        executable=os.path.join(self.jobdir, self.jobfile)
        # raise Exception(executable)

        params={'jobfile':executable}

        response, content = util.newt_request(url, 'POST', params=params, cookie_str=cookie_str)
        # raise Exception(content)
        if response['status']!='200':
            raise Exception(content)

        job_info=simplejson.loads(content)

        #check for problem with queue submission detected by newt
        if job_info['status']!='OK':
            raise Exception("Job submission failure: %s"%job_info['error'])
        
        self.pbsjobid=job_info['jobid']
        self.time_submitted=datetime.utcnow().replace(tzinfo=utc)
        #self.time_started=NULL
        #self.time_completed=NULL
        self.nova_state = 'submitted'
        self.save()
        return self
    

    def kill(self, *args, **kwargs):
        cookie_str=self.user.cookie
        url = '/queue/%s/%s' % (self.machine, self.pbsjobid)

        response, content = util.newt_request(url, 'DELETE', cookie_str=cookie_str)
        if response['status']!='200':
            raise Exception(content)

        output=simplejson.loads(content)

        return output
    
    def update(self):
        """
        >>> j=Job.objects.get(id=1)
        >>> j.update()
        """        
        if (self.pbsjobid==''):
            raise Exception("Job must be submitted before you can update")
        
        cookie_str=self.user.cookie
        
        url = '/queue/%s/%s' % (self.machine, self.pbsjobid)
        
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        
        
        if response['status']!='200':
            if response['status']=='404':
                # We should be OK - the job is simply no longer in the Q, so we assume it is complete for nova's purposes
                self.status=u'C'
                self.nova_state='completed'
                if (not self.time_started or self.time_started == None):
                    time_started_obj = self.get_timestamp('started')
                    if time_started_obj != None:
                        self.time_started= time_started_obj
                         
                if (not self.time_completed or self.time_completed == None):
                    time_completed_obj = self.get_timestamp('completed')
                    if time_completed_obj == None: 
                        self.nova_state = 'aborted'
                    else:
                         self.time_completed=time_completed_obj
                 
                if  self.timeuse == '' or self.timeuse == '-' or self.timeuse == '0':
                    try:
                        self.timeuse = str(self.time_completed - self.time_started)
                    except:
                        print 'unable to calculate time use'
                        
                self.save()
                return self
            else:
                # any other error in retrieving the job from the queue - do something reasonable 
                raise Exception(content)

                    
                
        
        # Decode JSON
        job_info=simplejson.loads(content)
        # Set queue, jobname, timeuse, status
        self.queue=job_info['queue']
        self.pbsjobid=job_info['jobid']
        self.timeuse=job_info['timeuse']
        self.status=job_info['status']
        # Set time_last_updated
        self.time_last_updated=datetime.utcnow().replace(tzinfo=utc)
        
        if (self.status in [ 'C', 'E', 'R', 'W', 'S']):
            if (not self.time_started or self.time_started == None): 
                try:
                    self.time_started=self.get_timestamp('started')
                except:
                    print 'started job in queue with no time_started'
            self.nova_state = 'started'  
            
        if (self.status=='C'):
            if (not self.time_completed or self.time_completed == None):
                try:
                    self.time_completed=self.get_timestamp('completed')
                except:
                    print 'completed job in queue with no time_completed, assuming aborted'
            if self.time_completed: 
                self.nova_state = 'completed'
            else:
                self.nova_state = 'aborted'

        self.save()
        return self

    def get_comp_settings_form(self):
        return CompSettingsForm(initial={"queue": "regular",
                                "num_nodes": 1,
                                "max_walltime": time(hour=0, minute=30),
                                "email_notifications": ["notifications_begin", "notifications_end", "notifications_abort"],
                                "nodemem": "first"},)
                                

    def __unicode__(self):
        return "%s,/queue/%s/%s" % (self.id, self.machine, self.pbsjobid)

    def get_raw_input_form(self):
        return RawInputForm(initial={"forminput": ""})


QUEUE_CHOICES = (('regular', 'Regular'),
                ('low', 'Low'),
                ('debug', "Debug"),)

EMAIL_CHOICES = (('notifications_begin', 'On begin'),
                ('notifications_end', 'On end'),
                ('notifications_abort', "On abort"),)

MEM_CHOICES = (('first', 'First Available'),
                ('big', 'Big'),
                ('small', 'Small'),)

class TimeSelectorWidget(widgets.MultiWidget):
    def __init__(self, attrs=None):
        minute = ((x*5, x*5) for x in range(0, 12))
        hour = ((x, x) for x in range(0, 7))
        # create choices for days, months, years
        # example below, the rest snipped for brevity.
        _widgets = (
            widgets.Select(attrs=attrs, choices=hour),
            widgets.Select(attrs=attrs, choices=minute),
        )
        super(TimeSelectorWidget, self).__init__(_widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.hour, value.minute]
        return [None, None]

    def format_output(self, rendered_widgets):
        return rendered_widgets[0] + " Hours " + rendered_widgets[1] + " Minutes "
        # u''.join(rendered_widgets)

    def value_from_datadict(self, data, files, name):
        timelist = [
            widget.value_from_datadict(data, files, name + '_%s' % i)
            for i, widget in enumerate(self.widgets)]
        try:
            T = time(hour=int(timelist[0]), minute=int(timelist[1]), second=0)
        except TypeError:
            return ''
        else:
            return str(T)


class CompSettingsForm(forms.Form):
    queue = forms.ChoiceField(choices=QUEUE_CHOICES)
    num_nodes = forms.IntegerField()
    max_walltime = forms.ChoiceField(widget=TimeSelectorWidget)
    nodemem = forms.ChoiceField(choices=MEM_CHOICES)
    email_notifications = forms.MultipleChoiceField(choices=EMAIL_CHOICES, widget=forms.CheckboxSelectMultiple)


class RawInputForm(forms.Form):
    rawinput = forms.CharField(widget=forms.Textarea(attrs={"cols": 120, "rows": 30}))

# class BlockType(models.Model):
#     blockname = models.CharField(max_length=255)
#     template = models.CharField(max_length=255)


class Block(models.Model):
    blockType = models.CharField(max_length=255)
    job = models.ForeignKey(Job)
    content = models.TextField()
    # blocktype = models.ForeignKey('BlockType')
