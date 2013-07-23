from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.conf import settings
import httplib2
import requests
import os
from datetime import *
from dateutil.parser import parse
from dateutil.tz import *
import simplejson
import tough.util as util
import logging
from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils.timezone import utc
from django.forms import widgets
import re
from django.utils.dateparse import parse_datetime
import pytz
import simplejson

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

        user = NoahUser(email=MyUserManager.normalize_email(email),
                        date_of_birth=date_of_birth,
                        is_admin=False
                        )

        user.set_password(password)
        user.save()
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
        user.save()
        return user


class NoahUser(AbstractBaseUser):
    """
    Extend Django User Model to include newt cookies
    """

    username = models.CharField(max_length=40, unique=True, db_index=True)
    USERNAME_FIELD = 'username'
    is_admin = models.BooleanField(default=False)
    cookie = models.TextField(null=True, blank=True)

    def is_licensed_user(self):
        #check that they are in the appropriate group
        cookie_str = self.cookie
        checkurl = '/command/hopper/'
        cmd = '/usr/bin/groups %s' % self.username
        response, content = util.newt_request(checkurl, 'POST', params={'executable': cmd}, cookie_str=cookie_str)
        result = simplejson.loads(content)
        if response.status_code != 200:
            raise Exception(content)
        if "osp" in result['output']:
            return True
        else:
            return False

    @property
    def is_staff(self):
        return self.is_admin

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    def get_orphan_jobs(self):
        return self.job_set.filter(project=None)
    
    def get_all_jobs(self):
        """
        Return a list of all jobs
        """
        all_jobs = self.job_set.all().order_by("-time_last_updated", "project__name", "-id")
        # for job in all_jobs:
        #     job.check_exists()

        # get the list of jobs listed in the database as running and update them.
        dbrunning = all_jobs.filter(state__in=['submitted', 'started'])
        for runningjob in dbrunning: runningjob.update();

        # get the updated list 
        all_jobs = self.job_set.all().order_by("-time_last_updated", "project__name", "-id")

        return all_jobs

    def get_recent_jobs(self):
        for job in Job.objects.filter(user=self.id):
            job.check_exists
        jobs_list = Job.objects.filter(user=self.id).exclude(exists=False).order_by('-time_last_updated')[:5]
        return jobs_list

    def get_projects(self):
        return self.project_set.all() | Project.objects.filter(creator=self)

    def set_cookie(self, cookie_str):
        cookie = {}
        for x in cookie_str.split(";"):
            x = x.strip()
            arr = x.split("=", 1)
            arr[0] = arr[0].lower().replace("-", "_")
            if len(arr) == 2:
                cookie.update({str(arr[0]): str(arr[1])})
            elif len(arr) == 1:
                cookie.update({str(arr[0]): "True"})
        self.cookie = simplejson.dumps(cookie)
        self.save()

    def get_cookie(self):
        cookie_dict = simplejson.loads(self.cookie)
        cookies = {}
        for x in cookie_dict:
            cookies.update({str(x): str(cookie_dict[x])})
        return cookies



# Provides a level of organization for users with jobs
class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(NoahUser, related_name='+')
    users = models.ManyToManyField(NoahUser, blank=True)

    def __unicode__(self):
        return self.name


class ProjectForm(forms.ModelForm):
    jobs = forms.ModelMultipleChoiceField(queryset=None, required=False)

    class Meta:
        model = Project
        fields = ('name', 'description')

    def __init__(self, user, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)
        self.fields['jobs'].queryset = user.job_set.filter(project=None)
        self.fields['jobs'].widget.attrs = {"data-placeholder": "Select some jobs..."}
        if kwargs['instance']:
            self.fields['jobs'].queryset = self.fields['jobs'].queryset | kwargs['instance'].job_set.all()

class Job(models.Model):
    """
    Model for Jobs submitted to NEWT
    """

    # Required fields - user, jobdir, machine
    user = models.ForeignKey(NoahUser)
    jobdir = models.CharField(max_length=1024)
    dir_name = models.CharField(max_length=1024)
    machine = models.CharField(max_length=254)
    exists = models.BooleanField(blank = True, default = True)
    executable = models.CharField(max_length=254, default="t+hydrate-hopper.debug")

    # field to keep track of the job's state from Nova's point of view
    NOVA_STATE_CHOICES = (
                         ('toberun', 'to be run but not yet queued'),
                         ('submitted', 'in a queue'),
                         ('started', 'running on a nersc machine'),
                         ('aborted', 'started and no longer running but did not run to completion'),
                         ('completed', 'completed or stopped'),
                         )
    state = models.CharField(max_length=32, choices=NOVA_STATE_CHOICES, default='toberun')

    # Defaults to tough.pbs
    jobfile = models.CharField(max_length=256, blank=True, default="tough.pbs")

    # Generated by PBS - update() fills in current values 
    pbsjob_id = models.CharField(max_length=256, blank=True)
    status = models.CharField(max_length=2, blank=True)
    jobname = models.CharField(max_length=256, blank=True)
    timeuse = models.CharField(max_length=256, blank=True)

    project = models.ForeignKey(Project, null=True, blank=True, default=None)
   

    # Useful timestamps
    time_last_updated = models.DateTimeField(null=True, blank=True)
    time_submitted = models.DateTimeField(null=True, blank=True)
    time_started = models.DateTimeField(null=True, blank=True)    
    time_completed = models.DateTimeField(null=True, blank=True)

    queue = models.CharField(max_length=256, default = "regular")
    numprocs = models.IntegerField(default = 24)
    maxwalltime = models.TimeField(default = time(hour = 0, minute = 15))
    nodemem = models.CharField(max_length=256, default = "first")
    emailnotifications = models.CharField(max_length = 256, default = "")

    
    def create_dir(self):
        # TODO: add kwargs for dir
        cookie_str=self.user.cookie
        url = '/command/' + self.machine
        response, content = util.newt_request(url, 'POST', params={'executable': '/bin/mkdir -p ' + self.jobdir}, cookie_str=cookie_str)
        if response.status_code != 200:            
            import ipdb; ipdb.set_trace()
            raise Exception(response)
        
        content=simplejson.loads(content)
        if content['error']!="":
            raise Exception(content['error'])
            
        return content

    def save_block(self, blockType, contents):
        b = self.block_set.get(blockType=blockType)
        b.content = contents
        b.save()

    def rebuild(self):
        self.create_dir()
        self.time_last_updated = datetime.utcnow().replace(tzinfo=utc)
        self.state = 'toberun'
        self.pbsjob_id = ""
        self.time_submitted = None
        self.time_started = None
        self.time_completed = None
        self.save()

    def put_file(self, filename, contents, *args, **kwargs):
        """
        >>> j.put_file("myfile", "#my contents\nhello world\n")
        
        """

        if 'dir' in kwargs:
            path=kwargs['dir']
        else:
            path=self.jobdir
            
        cookie_str=self.user.cookie
        url = '/file/%s%s/%s' % (self.machine, path, filename)
        response, content = util.newt_request(url, 'PUT', params=contents, cookie_str=cookie_str)
        if response.status_code != 200:
            raise Exception(content)
        return simplejson.loads(content)
        
       
    def upload_files(self, uploaded_file, filename):
        path = self.jobdir
        cookie_str=self.user.cookie
        url = '/file/%s%s/' % (self.machine, path)
        response = util.upload_request(url=url, uploaded_file=uploaded_file, filename = filename, cookie_str=cookie_str) #problem here
        b = self.block_set.get(blockType__tough_name = filename)
        b.last_uploaded = datetime.now()
        b.save()
        if response.status_code!=200:
            raise Exception(response)
        return response


    def parse_input_file(self, file_from):
        lines = file_from.split("\n")
        block = ""
        infiletitleregex = '(?<=<).+'
        blocktitleregex = '(?<=>>>)\w+'
        rocksblocktitleregex = '(ROCKS)'
        rocksblockendregex = '(!)'
        blockendregex = '(?<=<<<)\w+'
        blocking = False
        blocktype = ""
        blockschanged = []

        unparsed = ""
        for line in lines:
            if(re.search(infiletitleregex, line) != None):
                block += line + '\n'
                b = self.block_set.get(blockType__tough_name = 'title')
                b.content = block
                b.save()
                block = ""
                break
        for line in lines:
            if (re.search(blocktitleregex, line) != None):
                if(blocking == True):
                    return "blockception"
                blocktype = re.search(blocktitleregex, line).group(0).lower()
                blocking = True
            elif (re.search(rocksblocktitleregex, line) != None):
                if(blocking == True):
                    return "rockblockception"
                blocktype = "rocks"
                blocking = True
            if (blocking == True):      
                block += line + '\n'
            if(re.search(blockendregex, line) != None):
                if(blocking == False):
                    return "too many closes"
                b = self.search_block_references(blocktype=blocktype)
                if (b == None):
                    unparsed += block
                else:
                    if (b.blockType.required == 0 or b.blockType.required == 1):
                        b.content = block
                        b.save()
                        blockschanged.append(blocktype)
                blocking = False
                block = ""
            elif (re.match(rocksblockendregex, line) != None and blocktype == "rocks"):
                if(blocking == False):
                    return "too many exclaims"
                b = self.search_block_references(blocktype = blocktype)
                b.content = block
                b.save()
                blockschanged.append(blocktype)
                blocking = False
                block = ""
                blocktype = ""
                
        b = self.block_set.get(blockType__tough_name="extras")
        b.content = unparsed
        b.save()
        return blockschanged

    def search_block_references(self, blocktype):
        if (self.block_set.filter(blockType__tough_name = blocktype).count() != 0):
            b = self.block_set.get(blockType__tough_name = blocktype)
            return b
        elif (QualifiedBlockRef.objects.filter(name = blocktype).count() != 0):
            block_type_name = QualifiedBlockRef.objects.get(name = blocktype).blockType.tough_name
            b = self.block_set.get(blockType__tough_name = block_type_name)
            return b
        else:
            return None

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
        if response.status_code != 200:
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
        if response.status_code != 200:
            raise IOError(content)
        return content
    
    def tail_file(self, filepath, fromlinenumber):
        url = '/command/' + self.machine
        fullpath = self.jobdir + "/" + filepath
        newtcommand = {'executable': '/usr/bin/tail +' + str(fromlinenumber) + " " + fullpath}
        response, content = util.newt_request(url, 'POST', params=newtcommand, cookie_str=self.user.cookie)
        if response.status_code != 200:
            raise IOError(content)
        return response.text

    def get_zip(self, directory, **kwargs):
        """
        >>>j.get_zip()
        zip file of entire jobdir directory
        """
        
        if directory:
            zipfilename = directory[directory.rfind("/")+1:] + ".tar.gz"
        else:
            zipfilename = self.dir_name + ".tar.gz"
        directory = self.jobdir + "/" + directory
        directory = directory.rstrip("/")
        cookie_str = self.user.cookie
        url = '/command/' + self.machine
        newtcommand = {'executable': '/bin/tar -cvzf /tmp/' + zipfilename + " -C " + directory[:directory.rfind("/")] + " " + directory[directory.rfind("/")+1:]}
        response, content = util.newt_request(url, 'POST', params=newtcommand, cookie_str=cookie_str)

        if response.status_code != 200:
            raise IOError(content)
        #fetch the newly created zip
        url = '/file/%s/%s?view=read' % (self.machine, "/tmp/"+zipfilename)
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        if response.status_code != 200:
            raise IOError(content)

        # Removes files created in temp folder
        # Currently doens't do any error checking
        util.newt_request('/command/'+self.machine, "POST", {"executable": "/bin/rm /tmp/"+zipfilename}, cookie_str=cookie_str)

        return content
    
    def get_selected_zip(self, directory, selected_files):
        url = '/command/' + self.machine


    def import_file(self, filename, from_job_id):
        from_job = Job.objects.get(pk = from_job_id)
        url = '/command/' + self.machine
        frompath = from_job.jobdir + "/" + filename
        topath = self.jobdir 
        newtcommand = {'executable': '/bin/cp ' + frompath + " " + topath}
        response, content = util.newt_request(url, 'POST', params=newtcommand, cookie_str=self.user.cookie)
        if response.status_code != 200:
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
        if response.status_code != 200:
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
        # url = '/file/%s%s' % (self.machine, path)
        url = '/command/%s/' % self.machine
        newt_command = "/bin/bash -c 'ls -a --full-time %s'" % path
        # response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        response, content = util.newt_request(url, 'POST', {"executable": newt_command}, cookie_str=cookie_str)
        if response.status_code != 200:
            raise IOError(content)
        temp = response.json()['output'].split("\n")[1:-1]
        dir_info = []
        for line in temp:
            line = line.split()
            dir_info.append({
                "perms": line[0],
                "links": line[1],
                "owner": line[2],
                "group": line[3],
                "size": line[4],
                "date": parse(" ".join(line[5:8])),
                "name": " ".join(line[8:])
            })
        return dir_info
        
    def move_dir(self, tgtdir, *args, **kwargs):
        if 'srcdir' in kwargs:
            srcdir = kwargs['srcdir']
        else:
            srcdir = self.jobdir

        cookie_str = self.user.cookie
        url = '/command/%s/' % (self.machine)

        response, content = util.newt_request(url, 'POST',  params={'executable': '/bin/bash -c "/bin/mv %s %s"'%(srcdir, tgtdir) }, cookie_str=cookie_str)
        if response.status_code != 200:
            raise Exception(response)
        if response.json()['error'] != "":
            raise Exception(response.json()['error'])

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
        if response.status_code != 200:
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
        ts = datetime.strptime(content, format_string).replace(tzinfo=utc)
        #ts=parser.parse(content)  this approach gave inconsistent datetime objects
        return ts

    def submit(self):
        """
        >>> j=Job(user=request.user, machine="host", jobdir="/path/to/jobdir")
        >>> j.save()
        >>> j.submit()
        """
        cookie_str = self.user.cookie
        url = '/queue/%s/' % self.machine
        executable = os.path.join(self.jobdir, self.jobfile)
        # raise Exception(executable)

        params = {'jobfile':executable}

        response, content = util.newt_request(url, 'POST', params=params, cookie_str=cookie_str)
        # raise Exception(content)
        if response.status_code != 200:
            raise Exception(content)

        job_info=simplejson.loads(content)

        #check for problem with queue submission detected by newt
        if job_info['status']!='OK':
            raise Exception("Job submission failure: %s"%job_info['error'])
        
        self.pbsjob_id=job_info['jobid']
        self.time_submitted=datetime.utcnow().replace(tzinfo=utc)
        #self.time_started=NULL
        #self.time_completed=NULL
        self.state = 'submitted'
        self.save()
        return self
    

    def kill(self, *args, **kwargs):
        cookie_str=self.user.cookie
        url = '/queue/%s/%s' % (self.machine, self.pbsjob_id)

        response, content = util.newt_request(url, 'DELETE', cookie_str=cookie_str)
        if response.status_code != 200:
            raise Exception(content)

        output=simplejson.loads(content)

        return output
    
    def check_exists(self):
        
        cookie_str=self.user.cookie
        
        url = '/file/%s/%s' % (self.machine, self.jobdir)
        
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        if (response.status_code != 200):
            self.exists = False
            self.save()
        else:
            self.exists = True
            self.save()

    def update(self):
        """
        >>> j=Job.objects.get(id=1)
        >>> j.update()
        """        
        if (self.pbsjob_id==''):
            raise Exception("Job must be submitted before you can update")
        
        cookie_str=self.user.cookie
        
        url = '/queue/%s/%s' % (self.machine, self.pbsjob_id)
        
        response, content = util.newt_request(url, 'GET', cookie_str=cookie_str)
        # import ipdb; ipdb.set_trace()
        if response.status_code != 200:
            if response.status_code == 404:
                # We should be OK - the job is simply no longer in the Q, so we assume it is complete for nova's purposes
                self.status = u'C'
                self.state = 'completed'
                if (not self.time_started or self.time_started == None):
                    time_started_obj = self.get_timestamp('started')
                    if time_started_obj != None:
                        self.time_started = time_started_obj
                         
                if (not self.time_completed or self.time_completed == None):
                    time_completed_obj = self.get_timestamp('completed')
                    if time_completed_obj == None:
                        self.state = 'aborted'
                    else:
                         self.time_completed = time_completed_obj
                 
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
        job_info = simplejson.loads(content)
        # Set queue, jobname, timeuse, status
        self.queue = job_info['queue']
        self.pbsjob_id = job_info['jobid']
        self.timeuse = job_info['timeuse']
        self.status = job_info['status']
        # Set time_last_updated
        self.time_last_updated = datetime.utcnow().replace(tzinfo=utc)

        if (self.status in ['C', 'E', 'R', 'W', 'S']):
            if (not self.time_started or self.time_started == None): 
                try:
                    self.time_started=self.get_timestamp('started')
                except:
                    print 'started job in queue with no time_started'
            if (self.status == 'C'):
                if (not self.time_completed or self.time_completed == None):
                    try:
                        self.time_completed=self.get_timestamp('completed')
                    except:
                        print 'completed job in queue with no time_completed, assuming aborted'
                if self.time_completed:
                    try:
                        self.timeuse = str(self.time_completed - self.time_started)
                    except:
                        print 'unable to calculate time use'
                    self.state = 'completed'
                else:
                    self.state = 'aborted'
            else:
                self.state = 'started'
                try:
                    delta = str(datetime.utcnow().replace(tzinfo=utc) - self.time_started)
                    self.timeuse = delta[:delta.rfind(".")]
                except Exception:
                    pass

        self.save()
        return self

    def get_comp_settings_form(self):
        return CompSettingsForm(initial={"queue": self.queue, 
                                "num_procs": self.numprocs,
                                "max_walltime": self.maxwalltime,
                                "email_notifications": self.emailnotifications.split(","),
                                "nodemem": self.nodemem,
                                "executable": self.executable})

    def get_file_upload_form(self):
        return FileUploadForm()
    
    # def get_block_array(self):
    #     blockarray = []
    #     for block in self.get_req_blocks():
    #         contentsize = os.stat(block.content)
    #         blockarray.append({"name":block.blockType.name, "size":contentsize.st_size})
    #     for block in self.get_op_blocks():
    #         contentsize = os.stat(block.content)
    #         blockarray.append({"name":block.blockType.name, "size":contentsize.st_size})
    #     return blockarray

    def __unicode__(self):
        return self.jobname

    def get_title_block(self):
        return self.block_set.filter(blockType__tough_name = "title")

    def get_io_files_block(self):
        return self.block_set.get(blockType__tough_name = "io_files")

    def get_end_block(self):
        return self.block_set.get(blockType__tough_name = "endcy")

    def get_req_blocks(self):
        return self.block_set.filter(blockType__required=1).exclude(blockType__tough_name = "title")

    def get_op_blocks(self):
        return self.block_set.filter(blockType__required=0)


class InfoEditForm(forms.ModelForm):

    class Meta:
        model = Job
        fields = ("jobname", "project", "jobdir")

    def __init__(self, job, *args, **kwargs):
        super(InfoEditForm, self).__init__(*args, **kwargs)
        self.fields['project'].queryset = Project.objects.filter(creator=job.user) | job.user.project_set.all()


QUEUE_CHOICES = (('regular', 'Regular'),
                ('low', 'Low'),
                ('debug', "Debug"),)

EMAIL_CHOICES = (('b', 'On begin'),
                ('e', 'On end'),
                ('a', "On abort"),)

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
            T = time(hour=int(timelist[0]), minute=int(timelist[1]))
        except ValueError:
            return ''
        else:
            return str(T)


class TimeSelectorField(forms.Field):
    def __init__(self, required=True, label="Max Walltime", initial="", widget=TimeSelectorWidget, help_text=""):
        super(TimeSelectorField, self).__init__(required=required, label=label, initial=initial, widget=widget, help_text=help_text)

    def to_python(self, value):
        if not value:
            return []
        return value.split(":")

    def validate(self, value):
        for x in value:
            try:
                x = int(x)
            except ValueError:
                raise ValidationError("Invalid value: %d" % x)
        return value

EXE_CHOICES = (
    ("t+hydrate-hopper.debug", "Regular"),
    ("t+hydrate-hopper.debug", "Debug"),
    ("t+hydrate-hopper.debug", "Optimized"),
    ("t+hydrate-hopper.debug", "Magical"),
)


class CompSettingsForm(forms.Form):
    executable = forms.ChoiceField(choices=EXE_CHOICES)
    queue = forms.ChoiceField(choices=QUEUE_CHOICES)
    num_procs = forms.IntegerField()
    max_walltime = TimeSelectorField()
    email_notifications = forms.MultipleChoiceField(choices=EMAIL_CHOICES, widget=forms.CheckboxSelectMultiple(), required=False)


class RawInputForm(forms.Form):
    rawinput = forms.CharField(required=False, widget=forms.Textarea(attrs={"cols": 120, "rows": 30}))

class FileUploadForm(forms.Form):
    files = forms.FileField()

class ImportBlockForm(forms.Form):
    user = models.ForeignKey(NoahUser)
    jobchoice = forms.ModelChoiceField(queryset=None, empty_label="No job selected")

    def __init__(self, user, job_id, *args, **kwargs):
        super(ImportBlockForm, self).__init__(*args, **kwargs)
        self.fields['jobchoice'].queryset = user.job_set.all().exclude(pk = job_id).exclude(exists = False)


class BlockType(models.Model):
    name = models.CharField(max_length=255)
    tough_name = models.CharField(max_length=255)
    description = models.CharField(max_length=2000)
    # 0 - Not Required
    # 1 - Required
    # 2 - Batch - changeable through form, and uploaded files
    # 3 - Unchangeable files (io, etc.)
    required = models.IntegerField(default=0)
    default_content = models.TextField(default="", blank=True)
    ordering = models.IntegerField()

    class Meta:
        ordering = ['ordering', 'id']

    def __unicode__(self):
        return "%s: %s" % (self.tough_name.upper(), self.name)

    def get_name_list_dict(self):
        var_dict = {}
        for var in self.blockvariable_set.all():
            if not var_dict.has_key(var.name_list):
                var_dict.update({var.name_list:[]})
            var_dict[var.name_list].append(var)
        return var_dict

class Block(models.Model):
    blockType = models.ForeignKey(BlockType)
    job = models.ForeignKey(Job)
    content = models.TextField(blank=True)
    last_uploaded = models.DateTimeField(null = True, default = None)

    class Meta:
        ordering = ['blockType__ordering', 'blockType__id']

    def get_raw_input_form(self):
        return RawInputForm(data={"rawinput": self.content})

    def get_import_form(self):
        return ImportBlockForm(user = self.job.user, job_id = self.job.pk)

    def is_empty(self):
        return len(self.content) <= 0

    def reset_block_upload_times(self):
        self.last_uploaded = None
        self.save()
        return

class QualifiedBlockRef(models.Model):
    blockType = models.ForeignKey(BlockType)
    name = models.CharField(max_length=255)

class BlockVariable(models.Model):
    blockType = models.ForeignKey(BlockType)
    var_name = models.CharField(max_length=255)
    name_list = models.TextField(max_length=255)
