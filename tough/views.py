# Create your views here.
from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from tough.models import Job, NoahUser, Block, CompSettingsForm, RawInputForm, BlockType, ProjectForm, Project, ImportBlockForm, InfoEditForm
from django.contrib.auth.decorators import login_required
from time import localtime, strftime
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from operator import itemgetter
from django.utils.simplejson import JSONEncoder
import tough.util as util
import json
import re
import os
from datetime import *
from dateutil.tz import *
from django.utils.timezone import utc
import simplejson
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils.html import escape
from tough.templatetags.file_filters import *

def home(request):
    return render_to_response("home.html", {},
                              context_instance=RequestContext(request))


def about(request):
    return render_to_response('about.html', {},
                              context_instance=RequestContext(request))


def report_error(request):
    return render_to_response("report.html", {},
                              context_instance=RequestContext(request))


def submit(request, job_id):
    j = Job.objects.get(id=job_id)
    finalinput = ''
    for block in j.block_set.all():
        if block.blockType != "MESH" and block.blockType != "batch":
            finalinput += block.content + '\n'
    batch = j.block_set.get(blockType="batch")
    mesh = j.block_set.get(blockType="mesh")
    j.put_file("input", finalinput)
    j.put_file("tough.pbs", batch)
    j.put_file("MESH", mesh)
    j.submit()
    return HttpResponse("")


@login_required
def jobs(request):
    u = NoahUser.objects.get(username=request.user)
    username = u.username
    jobs = u.get_all_jobs()

    dirlist = [('scratch', 'My scratch directory'), ('home', 'My home directory'), ('project', 'Project'), ('root', '/')]

    return render_to_response('job_control.html',
                              {'dirlist': dirlist, 'all_jobs': jobs, 'username': username},
                              context_instance=RequestContext(request))

@login_required
def rebuild_job(request, job_id):
    j = get_object_or_404(Job, pk = job_id)
    j.create_dir()
    j.time_last_updated = datetime.utcnow().replace(tzinfo=utc)
    j.save()
    messages.success(request, "%s successfully rebuilt at %s" % (j.jobname, j.jobdir))
    if request.is_ajax():
        return HttpResponse(simplejson.dumps({"success": True, "job_id": j.pk, "redirect": "/job/job_setup/%d/" % j.pk}), content_type="application/json")
    return redirect("/job/job_setup/%d/" % j.pk)


@login_required
def create_job(request, job_id=None, type="new"):
    if request.method == "POST":
        #create new job in database
        u = NoahUser.objects.get(username=request.user)
        #add a timestamp-based directory name to the path that will become jobdir
        folder_name = request.POST['jobname'] + '_TOUGH_' + strftime("%Y%b%d-%H%M%S", localtime())
        jobdir = request.POST['jobdir'] + '/' + folder_name

        if request.POST['setup_type'] == 'new':
            srcdir = None
            oldjob = None
        elif request.POST['setup_type'] == 'import':
            srcdir = request.POST['srcdir']
            oldjob = None
        elif request.POST['setup_type'] == 'copy':
            oldjob = Job.objects.get(id=request.POST['job_id'])
            srcdir = oldjob.jobdir
        elif request.POST['setup_type'] == 'move':
            # Redefine jobdir back to user supplied value - we don't want to create a brand new dir for a move
            jobdir = request.POST['jobdir']
            srcdir = None
            oldjob = None
        else:
            return HttpResponseBadRequest("Invalid Setup Type")

        if request.POST['setup_type'] == 'move':
            j = Job.objects.get(id=request.POST['job_id'])
            j.move_dir(jobdir)
            # Get the NOVA_ directory name without the path
            basename = os.path.basename(j.jobdir.rstrip('/'))
            j.jobdir = os.path.join(jobdir, basename)
            j.save()
            return redirect('tough.views.jobs')
        else:
            j = Job(user=u, jobdir=jobdir, machine=request.POST['machine'], jobname=request.POST['jobname'], dir_name=folder_name)

            #create directory with unique id
            j.create_dir()

            if request.POST.get("project", False):
                j.project = Project.objects.get(pk=request.POST.get("project"))

            # Copy over the files to the new dir, if this is an import or copy
            if srcdir:
                j.import_files(srcdir, filelist=['incon', 'mesh'])
                # Delete any old timestamp files and update directory in batch file
                # running this on imports, too, in case the user imports an old nova directory
                dir_info = j.get_dir()
                filelist = [dirent['name'] for dirent in dir_info]
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
            j.time_last_updated = datetime.utcnow().replace(tzinfo=utc)
            j.save()
            populate_job(j)

            if request.POST.get("setup_type") == "copy" and request.POST.get("job_id"):
                old_job = Job.objects.get(pk=request.POST.get("job_id"))
                j.queue = old_job.queue
                j.numprocs = old_job.numprocs
                j.maxwalltime = old_job.maxwalltime
                j.emailnotifications = old_job.emailnotifications
                j.nodemem = old_job.nodemem
                j.save()
                for block in old_job.block_set.all():
                    temp_block = j.block_set.get(blockType__pk=block.blockType.pk)
                    temp_block.content = block.content
                    temp_block.save()
            #create default vasp files
            #render default setup form
            messages.success(request, "%s successfully created at %s" % (j.jobname, j.jobdir))
            if request.is_ajax():
                return HttpResponse(simplejson.dumps({"success": True, "job_id": j.pk, "redirect": "/job/job_setup/%d/" % j.pk}), content_type="application/json")
            return redirect("/job/job_setup/%d/" % j.pk)
    else:
        if job_id:
            job = get_object_or_404(Job, pk=job_id)
        else:
            job = None
        return render_to_response('job_setup.html', {"job": job, "setup_type": type}, context_instance=RequestContext(request))


def populate_job(job):
    for blocktype in BlockType.objects.all():
        b = Block(blockType=blocktype, job=job)
        b.save()


@login_required
def job_edit(request, job_id):
    j = get_object_or_404(Job, id=int(job_id))
    return render_to_response('job_edit.html',
                              {'job_name': j.jobname, 'job_id': job_id, "mesh_last_uploaded": j.block_set.get(blockType__name='mesh').last_uploaded, "incon_last_uploaded":j.block_set.get(blockType__name='incon').last_uploaded, 'job': j},
                              context_instance=RequestContext(request))

@login_required
def file_upload_view(request, job_id, file_type):
    j = get_object_or_404(Job , pk=job_id)
    if (file_type != 'infile'):
        block = j.block_set.get(blockType__name = file_type)
    else:
        block = None
    return render_to_response('file_upload.html',
                                {'job_name': j.jobname, 'job_id':job_id, 'job': j, 'file_type':file_type, "block":block}, 
                                context_instance=RequestContext(request))

@login_required
def file_upload(request, job_id, file_type):
    j = get_object_or_404(Job, pk=job_id)
    if (file_type == 'infile'):
        file_from = request.FILES['files'].read()
        j.parse_input_file(file_from)
        messages.success(request, "File successfully uploaded and parsed!")
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.job_edit", kwargs={"job_id": j.pk})}), content_type="application/json")
    elif (file_type == 'mesh'):
        response = j.upload_files(request.FILES['files'], filename = file_type)
        messages.success(request, "MESH was successfully uploaded and saved!")
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.job_edit", kwargs={"job_id": j.pk})}), content_type="application/json")
    else:
        response = j.upload_files(request.FILES['files'], filename = file_type)
        messages.success(request, "INCON was successfully uploaded and saved!")
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.job_edit", kwargs={"job_id": j.pk})}), content_type="application/json")
    if request.is_ajax():
        return HttpResponse(response.json(), content_type="application/json")
    return redirect("tough.views.job_edit", j.pk)


@login_required
def ajax_submit(request, job_id):
    #get the data from the ajax request
    j = Job.objects.get(id=job_id)
    filename = j.jobname
    submitted_text = combine_inputs(j)

    #save via newt, then return an okay
    try:
        j.put_file(filename, submitted_text)
    except Exception:
        return HttpResponse(simplejson.dumps({"success": False, "error": "Unable to save input file."}), content_type="application/json")

    batchname = "tough.pbs"
    batch_text = j.block_set.get(blockType__pk=1).content

    try:
        j.put_file(batchname, batch_text)
    except Exception:
        return HttpResponse(simplejson.dumps({"success": False, "error": "Unable to save batch file."}), content_type="application/json")
    
    try:
        j.submit()
    except Exception:
        return HttpResponse(simplejson.dumps({"success": False, "error": "Unable to submit job."}), content_type="application/json")

    return redirect('tough.views.job_view', job_id)


def combine_inputs(job):
    text = ''
    text += job.get_title_block().content
    text += job.get_io_files_block().content
    for block in job.get_req_blocks():
        text += block.content + "\n"
    for block in job.get_op_blocks():
        text += block.content + "\n"
    text += job.get_end_block().content

    return text


@login_required
def job_view(request, job_id):
    j = get_object_or_404(Job, pk=job_id)
    return render_to_response('job_view.html',
                              {"jobname": j.jobname, "job_id": j.pk, "jobdir": j.jobdir, "job": j},
                              context_instance=RequestContext(request))

@login_required
def project_view(request, project_id):
    p = get_object_or_404(Project, pk = project_id)
    return render_to_response('project_edit.html',
                             {"name": p.name,"project_id":p.pk, "project":p},
                             context_instance=RequestContext(request))
# @login_required
# def get_block(request, jobid, blockname):
#     j = get_object_or_404(Job, id=int(jobid))
#     b = j.block_set.get(blockType__name = blockname)
#     content = b.content
#     response = HttpResponse(content, content_type="text/plain")
#     response['Content-Disposition'] = 'attachment; filename=' + filename
#     return response

@login_required
def import_file(request, job_id, file_type):
    j = get_object_or_404(Job, id=job_id)
    form = ImportBlockForm(data=request.POST, user = j.user, job_id=job_id)
    if form.is_valid():
        job_from = form.cleaned_data['jobchoice']
        content_from = job_from.get_file(filename = file_type)
        j.put_file(filename = file_type, contents = content_from)
        messages.success(request, file_type.upper() + " was successfully imported from " + job_from.jobname + " and saved!")
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.job_edit", kwargs={"job_id": j.pk})}), content_type="application/json")
    else:
        messages.error(request, file_type.upper() + "failed to import from " + job_from.jobname)
        return HttpResponse(simplejson.dumps({"success": False, "error": "Something went wrong."}), content_type="application/json")


@login_required
def ajax_save(request, job_id, input_type):
    #get the data from the ajax request
    j = get_object_or_404(Job, id=job_id)
    blocktype = BlockType.objects.get(pk=request.POST['blockType'])
    if request.method == 'POST':
        # If the block is a batch block (pk=1)
        if blocktype.pk == 1:
            form = CompSettingsForm(data=request.POST)
        else:
            if input_type == "raw":
                form = RawInputForm(data=request.POST)
            elif input_type == "import":
                form = ImportBlockForm(data=request.POST, user = j.user, job_id = job_id)
            else:
                form = RawInputForm(data=request.POST)

        if form.is_valid():
            # If the block is a batch block (pk=1)
            if blocktype.pk == 1:
                content = ''
                content += '#PBS -N tough\n'
                content += '#PBS -q ' + form.cleaned_data['queue'] + '\n'
                j.queue = form.cleaned_data['queue']
                content += '#PBS -l mppwidth=%d\n' % (form.cleaned_data['num_procs'])

                j.numprocs = int(form.cleaned_data['num_procs'])

                content += '#PBS -l walltime=' + form.cleaned_data["max_walltime"][0] + ':' + form.cleaned_data["max_walltime"][1] + ':00\n'
                j.maxwalltime = time(hour=int(form.cleaned_data["max_walltime"][0]), minute=int(form.cleaned_data["max_walltime"][1]))
                j.emailnotifications = ",".join(form.cleaned_data['email_notifications'])
                mail = "".join(form.cleaned_data['email_notifications'])
                if not mail:
                    mail = 'n'
                content += '#PBS -m %s \n' % mail
                content += '#PBS -j oe\n'
                content += '#PBS -d ' + j.jobdir + '\n'
                content += '#PBS -V\n\n'
                content += 'cd $PBS_O_WORKDIR\n\n'
                content += "/bin/date -u  +'%a %b %d %H:%M:%S %Z %Y' > started\n"
                content += "aprun -n %d /global/common/hopper2/osp/tough/esd-ptoughplusv2-science-gateway/t+hydrate-hopper.debug %s \n" %(j.numprocs, j.jobname)
                content += "/bin/date -u  +'%a %b %d %H:%M:%S %Z %Y' > completed\n"
                j.save()
            elif input_type == 'raw':
                content = form.cleaned_data['rawinput']
            else:
                content = form.cleaned_data['jobchoice'].block_set.get(blockType=blocktype).content
            try:
                j.save_block(blocktype, content)
                j.time_last_updated = datetime.utcnow().replace(tzinfo=utc)
                j.save()
                return HttpResponse(simplejson.dumps({"success": True, "content": content}), content_type="application/json")
            except Exception:
                return HttpResponse(simplejson.dumps({"success": False, "error": "Unable to save file."}), content_type="application/json")
    return HttpResponse(simplejson.dumps({"success": False, "error": "Something went wrong."}), content_type="application/json")

def edit_project(request, project_id):
    p = Project.objects.get(pk = project_id)
    if request.method == "POST":
        form = ProjectForm(data=request.POST, user=request.user, instance = p)
        if form.is_valid():
            p = form.save(commit=False)
            p.save()
            for j in p.job_set.all():
                j.project = None
                j.save()
            for job in form.cleaned_data['jobs']:
                job.project = p
                job.save()
            messages.success(request, "Project successfully updated!")
            if request.is_ajax():
                return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.project_view", kwargs={"project_id": project_id})}), content_type="application/json")
            return redirect("tough.views.jobs")
    else:
        form = ProjectForm(user=request.user, instance = p, initial = {"jobs":p.job_set.all()})
    return render_to_response("popup_form_base.html", {"form": form, "form_action": reverse("tough.views.edit_project", kwargs={"project_id": project_id}), "form_title": "Edit Project"}, context_instance=RequestContext(request))

def create_project(request):
    if request.method == "POST":
        form = ProjectForm(data=request.POST, user=request.user, instance = None)
        if form.is_valid():
            project = form.save(commit=False)
            project.creator = request.user
            project.save()
            for job in form.cleaned_data['jobs']:
                job.project = project
                job.save()
            if request.is_ajax():
                return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.jobs")}), content_type="application/json")
            return redirect("tough.views.jobs")
    else:
        form = ProjectForm(user=request.user, instance = None)
    return render_to_response("popup_form_base.html", {"form": form, "form_action": reverse("tough.views.create_project"), "form_title": "Create Project"}, context_instance=RequestContext(request))



def info_edit(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if request.method == "POST":
        form = InfoEditForm(data=request.POST, job=job, instance=job)
        if form.is_valid():
            form.save()
            if request.is_ajax():
                return HttpResponse(simplejson.dumps({"success": True, "redirect":reverse("tough.views.job_edit", kwargs={"job_id": job.pk}),"info": {"name": job.jobname, "project": job.project.name if job.project else ""}}), content_type="application/json")
            return redirect("tough.views.job_edit", job_id=job.pk)
    else:
        form = InfoEditForm(instance=job, job=job)
    return render_to_response("popup_form_base.html", {"form_title": "Edit Job Information", "form_action": reverse("tough.views.info_edit", kwargs={"job_id": job.pk}), "form": form}, context_instance=RequestContext(request))

"""
@login_required
def ajax_upload(request, job_id):
    #get the file from the ajax request
    j=Job.objects.get(id=job_id)
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
def stopjob(request, job_id):
    #get the data from the ajax request
    j = Job.objects.get(id=job_id)
    filename = 'STOPCAR'

    kill = request.POST['kill']
    submitted_text = request.POST['content']

    if kill == "true":
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
def get_file(request, job_id, filename):
    j = Job.objects.get(id=job_id)
    try:
        content = j.get_file(filename)
    except IOError, ex:
        return HttpResponseBadRequest("Could not read file: %s" % str(ex))
    response = HttpResponse(content, content_type="text/plain")
    response['Content-Disposition'] = 'attachment; filename=' + filename
    return response


@login_required
def ajax_get_job_dir(request, job_id, directory=""):
    job = get_object_or_404(Job, pk=job_id)
    try:
        ls = job.get_dir(dir=job.jobdir+"/"+directory)
    except IOError, ex:
        return HttpResponseBadRequest("Directory not found %s" % str(ex))
    s = sorted(ls, key=lambda f: f['perms'][0])
    ls = sorted(s, key=lambda f: f['name'].lower())
    listing = []
    for f in ls:
        if not (directory == "" and (f['name'] == "." or f['name'] == "..")) and f['name']!=".":
            listing.append({
                "name": f['name'],
                "size": size_nice(f['size']),
                "date": f['date'],
                "is_folder": f['perms'][0] == "d"
            })
    listing = sorted(listing, key=lambda f: f['name'].lower())
    listing = sorted(listing, key=lambda f: f['is_folder'], reverse=True)
    return HttpResponse(simplejson.dumps({"success": True, "listing": listing}), content_type="application/json")


@login_required
def ajax_mkdir(request, machine, directory):
    cookie_str = request.user.cookie
    response, content = util.newt_request('/command/'+machine, 'POST', params={'executable': '/bin/mkdir -p ' + directory}, cookie_str=cookie_str)
    if response['status'] != '200':
        raise Exception(response)

    contentjson = JSONDecoder().decode(content)
    if contentjson['error'] != "":
        raise Exception(contentjson['error'])

    return HttpResponse(content, content_type='application/json')


@login_required
def delete_job(request, job_id):
    j = get_object_or_404(Job, pk=job_id)
    if request.POST.get("files", False):
        j.del_dir()
    j.delete()
    if request.is_ajax():
        return HttpResponse(simplejson.dumps({"success": True}))
    else:
        return redirect("tough.views.jobs")


@login_required
def rename_job(request, job_id):
    j = get_object_or_404(Job, pk=job_id)
    j.jobname = request.POST['new_name']
    j.save()
    return redirect('tough.views.view_job', job_id=j.id)


@login_required
def ajax_get_zip(request, job_id):
    j=Job.objects.get(id=job_id)
    zip = j.get_zip()

    response = HttpResponse(zip, content_type='application/x-zip-compressed')
    response['Content-Disposition'] = 'attachment; filename=' + j.dir_name + ".tar.gz"
    return response


@login_required
def run_job(request, job_id):
    return view_job(request, job_id, True)


@login_required
def ajax_run_job(request, job_id):
    j = Job.objects.get(id=job_id)
    # Run the job
    if j.nova_state == 'toberun':
        # import pdb;pdb.set_trace()
        try:
            j.submit()
            content = 'okay'
            return HttpResponse(content, content_type='text/plain')
        except Exception, ex:
            errors = str(ex)
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
    return render_to_response('main/license.html,
                              {'username': username, 'licensed_user': licensed_user},
                              context_instance=RequestContext(request))
"""
