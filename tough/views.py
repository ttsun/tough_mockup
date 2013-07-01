# Create your views here.
from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from nova.main.models import Job, NoahUser
from django.contrib.auth.decorators import login_required
from time import localtime, strftime
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django import forms
from django.core.exceptions import ValidationError
from operator import itemgetter
from django.utils.simplejson import JSONEncoder
from django.utils.simplejson import JSONDecoder
import tough.util as util
import json
import re
import os
import zipfile
from django.core.servers.basehttp import FileWrapper
from datetime import *
from dateutil.tz import *
from django.utils.timezone import utc
from django.conf import settings


def home(request):
    return render_to_response("base.html", {})


@login_required
def index(request):
    #error here - something doesn't have a header?
    u = NoahUser.objects.get(pk=request.user.id)
    username = u.username
    jobs = Job.objects.filter(user=u.id).order_by('-time_last_updated')

    dirlist=[('scratch','My scratch directory'),('home','My home directory'),('project','Project'),('root','/')]
    import_dirlist=[('scratch','My scratch directory'),('home','My home directory'),('project','Project'),('root','/'),('hfo2','Sample: HfO2'),('lialo2','Sample: LiAlO2'),('tio2','Sample: TiO2'),('liquidhg','Sample: Liquid Hg')]
    return render_to_response('main/job_control.html', 
                              {'dirlist':dirlist, 'import_dirlist': import_dirlist, 'all_jobs': jobs}, 
                              context_instance=RequestContext(request))

def about(request):
    return render_to_response('main/about.html', {}, 
                               context_instance=RequestContext(request)) 

@login_required
def jobs(request):
    u = NoahUser.objects.get(username = request.user)
    username = u.username
    jobs=u.get_all_jobs()
    
    dirlist=[('scratch','My scratch directory'),('home','My home directory'),('project','Project'),('root','/')]
    
    return render_to_response('main/jobs.html', 
                              {'dirlist':dirlist, 'all_jobs': jobs, 'username': username}, 
                              context_instance=RequestContext(request))






@login_required
def ajax_joblist(request):
    u = NoahUser.objects.get(username = request.user)
    jobs=u.get_all_jobs()

    return render_to_response('main/job_list.html', 
                              {'all_jobs': jobs})




@login_required
def setup(request, jobid):
    #render setup form
    j = get_object_or_404(Job, id=int(jobid))
    errors=None
    input_files = settings.APP_FILES
    extra_files = []
    #get the list of extra input files if it's present
    try:
        content=j.get_file("input_files")
        jsonDec = json.decoder.JSONDecoder()
        extra_files = jsonDec.decode(content)
    except:
        #no biggie, the file doesn't exist
        extra_files = []
                               
    #check for uploaded file
    if request.FILES != {} and request.FILES != None:
        try:
            thefile = request.FILES['file']
            filename = thefile.name
            thepath = "/tmp/" + filename
            destination = open(thepath, 'wb+')
            for chunk in thefile.chunks():
                destination.write(chunk)
            destination.close()
        except:
            errors = "unable to save the file to the web server"
        
        try:
            #upload from web server to hpc side via newt 
            #this is kind of stupid for now. It should just be a move command if running on nersc global file system.
            #not working at present
            j.upload_file(filename, thepath)
        except Exception, ex:
            errors="unable to save the uploaded file on the hpc side: " + str(ex)
        
        #add the file to the extra_files list here and the input_files list in the job dir
        id_str = filename.strip(' .')
        extra_files.append({'id': id_str, 'longname': filename, 'filename': filename, 'description': 'uploaded file', 'required': 'False'})

        j.put_file("input_files", json.dumps(extra_files))
        
    input_files.extend(extra_files)
    
    #stopped here- need to test this function with an upload and without
            
    u = NoahUser.objects.get(username = request.user)
    
    repos = u.get_repos()
    repo_choices=[ (repo, repo) for repo in  repos ]
    repo_choices.insert(0, ('default', 'Default'))

    return render_to_response('main/job_setup.html', 
                              {'job_name': j.jobname, 'job_id': jobid, 'job_jobdir': j.jobdir,
                               'repo_choices': repo_choices, 'errors':errors}, 
                              context_instance=RequestContext(request))

@login_required

def ajax_get_tough_files(request, jobid):
    j = get_object_or_404(Job, id=int(jobid))
    tough_files={
        # "POTCAR" : "",
        # "POSCAR" : "",
        # "INCAR" : "",
        "batch": "",
        # "GENER": "",
        "RAWTOUGH": ""
    }
    # Get various files

    # TODO: if job is new, don't bother
    for (key, val) in tough_files.iteritems():
        try:
            if key == "batch": tough_files[key] = j.get_file("tough.pbs")
            else: tough_files[key]=j.get_file(key)
# Annette's version
# def ajax_get_job_files(request, jobid):
#     j = get_object_or_404(Job, id=int(jobid))
#     # Get various files
#     job_files={}
#     appfiles = settings.APP_FILES
#     # get input_files from job dir to see if there are extra ones
#     input_files = ""
#     try:
#         input_files = j.get_file("input_files")
#     except:
#         #we should be okay, the file just isn't there
#         print("an attempt to get input_files returned nothing")
        
#     if input_files != "":
#         jsonDec = json.decoder.JSONDecoder()
#         extra_files = jsonDec.decode(input_files)
#         if len(extra_files) > 0:
#             for extra in extra_files:
#                 appfiles.append(extra)
        
#     for appfile in appfiles:
#         try:
#             job_files[appfile["id"]]=j.get_file(appfile["filename"])

        except IOError:
            # This is OK - we never saved file so just set to blank
            # commented out, probably works
            # if "default" in appfile:
            #     #set default INCAR settings, so that the GUI defaults are in agreement
            #     tough_files[key] = "SYSTEM = " + j.jobname + "\nPREC = Normal\nENCUT = 300\nLREAL = .FALSE.\nISMEAR = 1"
            # else: 
            tough_files[key]=""
            
    content = json.dumps(tough_files)
    #             Annette's version
    #             job_files[appfile["id"]] = appfile["default"]
    #         else: job_files[appfile["id"]]=""
            
    # content = json.dumps(job_files)
    return HttpResponse(content, content_type='application/json')

@login_required
def ajax_save(request, jobid):
    #get the data from the ajax request
    j=Job.objects.get(id=jobid)
    filename = request.POST['filename']
    submitted_text = request.POST['content']
    #save via newt, then return an okay
    try:
        j.put_file(filename, submitted_text)
    except:
        return HttpResponse("Unable to save the file")
    return HttpResponse("okay")

"""
@login_required
def ajax_upload(request, jobid):
    #get the file from the ajax request
    j=Job.objects.get(id=jobid)
    print(request.FILES)
    thefile = request.FILES['file']
    filename = thefile.name
    #save via newt, then return the file content, unless it's huge (>2.5MB is Django's default)
    try:
        thepath = thefile.temporary_file_path
        response, content = util.newt_request('/command/carver', 'POST', params={'executable': 'cp ' + thepath + " " + j.jobdir + "/" + filename}, cookie_str=cookie_str)
        if thefile.multiple_chunks(): 
            return HttpResponse("okay")
        else:
            filecontent = thefile.read()
            fileobj = {"filename": filename, "content": filecontent}
            return HttpResponse(json.dumps(fileobj), content_type='application/json')

    except:
        return HttpResponse("Unable to save the file")
"""

@login_required
def stopjob(request, jobid):
    #get the data from the ajax request
    j=Job.objects.get(id=jobid)
    filename = 'STOPCAR'
    
    kill = request.POST['kill']
    submitted_text = request.POST['content']
    
    if kill=="true":
        #save via newt, then return an okay
        try:
            j.kill()
        except:
            return HttpResponse("Unable to kill the job")
    else:
        #save via newt, then return an okay
        try:
            j.put_file(filename, submitted_text)
        except:
            return HttpResponse("Unable to save the file")
    return HttpResponse("okay")

    
@login_required
def save_potcar(request, jobid):
    
    j=Job.objects.get(id=jobid)
    form_data = {'potentials': request.POST['potentials'], 'elements': request.POST['elements'], 'pot_type': request.POST['type'], 'functional': request.POST['functional']}
    """
    form_data =PotentialData(potentials=request.POST['potentials'], elements=request.POST['elements'], pot_type=request.POST['type'], functional=request.POST['functional'])
    form_data.save()
    j.potential_data = form_data
    j.save()
    """
    try:
        content = j.get_potcars(form_data)
        
    except:
        return HttpResponse("Could not get the POTCAR settings as a file")

    return HttpResponse(content, content_type="text/plain")



@login_required
def get_file(request, jobid, filename):
    j=Job.objects.get(id=jobid)
    try:
        content=j.get_file(filename)
    except IOError, ex:
        return HttpResponseBadRequest("Could not read file: %s"%str(ex))
        
    return HttpResponse(content, content_type="text/plain")
    
        
@login_required
def view_job(request, jobid, do_run=False, *args, **kwargs):
    #do_run indicates whether or not to submit the job via an ajax call from the returned web page
    j=Job.objects.get(id=jobid)
    try:
        dir_info=j.get_dir(j.jobdir)
    except IOError, ex:
        return HttpResponseBadRequest("File Not Found: %s"%str(ex))
    
    # sort by filename
    dir_info=sorted(dir_info,key=itemgetter('name'))
    
    state_map = {'toberun': 'Editing', 'submitted': 'Queued', 'started': 'Running', 'aborted': 'Aborted', 'completed': 'Completed'}
    
    return render_to_response('main/job_view.html', 
                              {'job_name': j.jobname, 'job_id': jobid, 'job_jobdir': j.jobdir, 'dir_info' : dir_info, 'pbs_id': j.pbsjobid, 'machine':j.machine, 'nova_state': j.nova_state, 'readable_state': state_map[j.nova_state], 'time_use': j.timeuse, 'do_run': do_run}, 
                              context_instance=RequestContext(request))
    
@login_required
def ajax_getoszicar(request, jobid):
    j=Job.objects.get(id=jobid)
    j.update()
    out = {"nova_state": j.nova_state, "time_use": j.timeuse, "oszicar": {}}
    try:
        lines=j.get_file('OSZICAR')
    except IOError, ex:
        print("Attempt to retrieve OSZICAR file that does not exist") 
        lines = ""
    oszicar=Oszicar.load(lines.split('\n')) 
    content_type='application/json'
    if len(oszicar.steps) > 0:
        out["oszicar"]=oszicar.to_db()
    content = json.dumps(out)
    return HttpResponse(content, content_type=content_type)
    

@login_required
def ajax_getdir(request, machine, directory):
    u = NoahUser.objects.get(username = request.user)
    try:
        dir_info=Job(user=u, machine=machine).get_dir(dir=directory)
    except IOError, ex:
        return HttpResponseBadRequest("File Not Found: %s"%str(ex))

    dir_info=sorted(dir_info,key=itemgetter('name'))
    content = JSONEncoder().encode(dir_info)
    content_type='application/json'
    return HttpResponse(content, content_type=content_type)
    
@login_required
def ajax_mkdir(request, machine, directory):
    cookie_str=request.user.cookie
    response, content = util.newt_request('/command/'+machine, 'POST', params={'executable': '/bin/mkdir -p ' + directory}, cookie_str=cookie_str)
    if response['status']!='200':
        raise Exception(response)
    
    contentjson=JSONDecoder().decode(content)
    if contentjson['error']!="":
        raise Exception(contentjson['error'])
        
    return HttpResponse(content, content_type='application/json')

    
@login_required
def setup_new(request):
    #create new job in database
    u = NoahUser.objects.get(username = request.user)
    #add a timestamp-based directory name to the path that will become jobdir
    jobdir = request.POST['jobdir'] + '/NOVA_' + strftime("%Y%b%d-%H%M%S", localtime())

    if request.POST['setup_type']=='new':
        srcdir=None
        oldjob=None
    elif request.POST['setup_type']=='import':
        srcdir = request.POST['srcdir']
        oldjob=None    
    elif request.POST['setup_type']=='copy':
        oldjob=Job.objects.get(id=request.POST['jobid'])
        srcdir=oldjob.jobdir
    elif request.POST['setup_type']=='move':
        # Redefine jobdir back to user supplied value - we don't want to create a brand new dir for a move
        jobdir = request.POST['jobdir']
        srcdir=None
        oldjob=None
    else:
        return HttpResponseBadRequest("Invalid Setup Type")
        
                
                
    if request.POST['setup_type']=='move':
        j=Job.objects.get(id=request.POST['jobid'])
        j.move_dir(jobdir)
        # Get the NOVA_ directory name without the path
        basename=os.path.basename(j.jobdir.rstrip('/'))        
        j.jobdir=os.path.join(jobdir, basename)
        j.save()
        return redirect('nova.main.views.index')
        
    else:
        j = Job(user=u, jobdir=jobdir, machine=request.POST['machine'], jobname=request.POST['jobname'])
        #create directory with unique id
        j.create_dir()

        # Copy over the files to the new dir, if this is an import or copy
        if srcdir:
            j.import_files(srcdir)
            # Delete any old timestamp files and update directory in batch file
            # running this on imports, too, in case the user imports an old nova directory   
            dir_info = j.get_dir()
            filelist=[ dirent['name'] for dirent in dir_info ]
            if 'started' in filelist:
                j.del_file('started')
            if 'completed' in filelist:
                j.del_file('completed')
            if 'tough.pbs' in filelist:
                batch_string = j.get_file('tough.pbs')
                d_repl = "#PBS -d " + jobdir + '\n'
                cd_repl = "cd " + jobdir + '\n'
                batch_string = re.sub(r'#PBS -d \S+\n', d_repl, batch_string)
                batch_string = re.sub(r'cd \S+\n', cd_repl, batch_string)
                j.put_file('tough.pbs', batch_string)
                
        #note creation time so that sorting works
        j.time_last_updated=datetime.utcnow().replace(tzinfo=utc)
        j.save()

        #create default vasp files
        #render default setup form
        return redirect('nova.main.views.setup', jobid=j.id)
    

@login_required
def delete_job(request):
    jobid=int(request.POST['del_jobid'])
    j=Job.objects.get(id=jobid)
    if request.POST['del_type']=='nova_and_files':
        j.del_dir()
    j.delete()
    return redirect('nova.main.views.index')
    
@login_required
def rename_job(request):
    jobid=int(request.POST['rename_jobid'])
    j=Job.objects.get(id=jobid)
    j.jobname = request.POST['new_name'];
    j.save();
    return redirect('nova.main.views.view_job', jobid=j.id)
    
    
@login_required
def ajax_get_zip(request, jobid):
    j=Job.objects.get(id=jobid)
    zip = j.get_zip()
    directory = j.jobdir
    slash = directory.rfind("/")
    zipfilename = directory[slash+1:] + ".zip"
        
    response = HttpResponse(zip, content_type='application/x-zip-compressed')
    response['Content-Disposition'] = 'attachment; filename=' + zipfilename
    return response

@login_required
def run_job(request, jobid):
    return view_job(request, jobid, True)
    
@login_required
def ajax_run_job(request, jobid):
    j=Job.objects.get(id=jobid)
    # Run the job
    if j.nova_state == 'toberun':
        # import pdb;pdb.set_trace()
        try:
            j.submit()
            content = 'okay'
            return HttpResponse(content, content_type='text/plain')
        except Exception, ex:
            errors=str(ex)
            raise Exception(errors)

    else:
        content = 'job already submitted'
        return HttpResponse(content, content_type='text/plain')

"""
#for checking user licenses by NERSC group
>>>>>>> remotes/jren13/noa-james2/noa
@login_required
def check_license(request):
    u = NoahUser.objects.get(username = request.user)
    username = u.username    
    licensed_user = u.is_licensed_user()
    return render_to_response('main/license.html', 
                              {'username': username, 'licensed_user': licensed_user}, 
                              context_instance=RequestContext(request))
"""

