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
import random
from datetime import *
from dateutil.tz import *
from django.utils.timezone import utc
from django.utils.timezone import localtime as djangolocaltime
import simplejson
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils.html import escape
from tough.templatetags.file_filters import *
import settings

def home(request):
    return render_to_response("home.html", {},
                              context_instance=RequestContext(request))


def about(request):
    return render_to_response('about.html', {},
                              context_instance=RequestContext(request))


def report_error(request):
    return render_to_response("report.html", {},
                              context_instance=RequestContext(request))


@login_required
def tail_file(request, job_id, filepath):
    job = get_object_or_404(Job, pk=job_id)
    file_url = job.jobdir + filepath
    if not request.GET.get("curr"):
        return HttpResponse(simplejson.dumps({"success": False}), content_type="application/json")
    current_line = int(request.GET.get("curr"))
    content = job.tail_file(filepath=filepath, fromlinenumber=current_line)
    newcontent = json.loads(content)['output']
    newline = len(newcontent.split('\n')) + current_line - 1
    return HttpResponse(simplejson.dumps({"success": True, "job_id": job.pk, "filepath": filepath, "new_content": newcontent, "current_line": newline}), content_type="application/json")


@login_required
def view_file(request, job_id, filepath):
    job = get_object_or_404(Job, pk=job_id)
    file_url = "/file/hopper" + job.jobdir + "/" + filepath + "?view=read"
    response, content = util.newt_request(file_url, "GET", cookie_str=request.user.cookie)
    content = response.text
    totallines = content.split('\n')
    current_line = len(totallines)
    return render_to_response("tail.html", {"success": True, "job_id": job.pk, "filepath": filepath, "file_content": content, "current_line":current_line, "title": "View file: " + filepath[filepath.rstrip("/").rfind("/")+1:]}, context_instance=RequestContext(request))


@login_required
def view_graph(request, job_id, filepath):
    job = get_object_or_404(Job, pk=job_id)
    file_url = "/file/hopper" + job.jobdir + "/" + filepath + "?view=read"
    content = job.tail_file(filepath = filepath, fromlinenumber = 0)
    newcontent = json.loads(content)['output']
    totallines = newcontent.split('\n')
    if len(totallines) > 2:
        graphable = True
    else:
        graphable = False
    graph_options = simplejson.dumps(totallines[0].split())
    graph_data = []

    line_regex = re.compile("[\d\w\-\+\.]+")
    for index, line in enumerate(newcontent.split("\n")):
        if index == 0:
            continue
        if line == '':
            continue
        row = line_regex.findall(line)
        data = []
        for datum in row:
            data.append(float(datum))
        graph_data.append(data)
    return render_to_response("graph.html", {"success": True, "graphable": graphable, "job_id": job.pk, "filepath": filepath, "file_content": content, "title": "View file: " + filepath[filepath.rstrip("/").rfind("/")+1:], "graph_options": graph_options, "graph_data": graph_data}, context_instance=RequestContext(request))


@login_required
def power_view(request, job_id):
    return render_to_response("power_view.html", {}, context_instance=RequestContext(request))


@login_required
def update_graph(request, job_id, filepath):
    job = get_object_or_404(Job, pk=job_id)
    file_url = job.jobdir + filepath
    if not request.GET.get("curr"):
        return HttpResponse(simplejson.dumps({"success":False}), content_type="application/json")
    current_line = int(request.GET.get("curr"))
    content = job.tail_file(filepath = filepath, fromlinenumber = current_line)
    newcontent = json.loads(content)['output']
    newline = len(newcontent.split('\n')) + current_line - 1
    graph_data = []

    # Files to be graphed are assumed to have columned data split by spaces and line breaks
    # x_col = request.GET.get("x", 0)  # These can be set by get variables if necessary to specify
    # y_col = request.GET.get("y", 1)  # the columns to be graphed
    line_regex = re.compile("[\d\w\-\+\.]+")

    for index, line in enumerate(newcontent.split("\n")):
        if index == 0 and current_line == 1:
            continue
        if line == '':
            continue
        row = line_regex.findall(line)
        data = []
        for datum in row:
            data.append(float(datum))
        graph_data.append(data)
    return HttpResponse(simplejson.dumps({"success": True, "job_id": job.pk, "filepath": filepath, "new_content": newcontent, "current_line": newline, "graph_data": graph_data}), content_type="application/json")

@login_required
def preview_input(request, job_id):
    j = Job.objects.get(id=job_id)
    finalinput = combine_inputs(j)
    response = HttpResponse(finalinput, content_type="text/plain")
    response['Content-Disposition'] = 'filename=' + j.jobname + "_preview"
    return response


@login_required
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
    j.rebuild()
    j.block_set.get(blockType__tough_name = "mesh").reset_block_upload_times()
    j.block_set.get(blockType__tough_name = "incon").reset_block_upload_times()
    j.block_set.get(blockType__tough_name = "sinks_sources").reset_block_upload_times()
    messages.success(request, "%s successfully rebuilt at %s" % (j.jobname, j.jobdir))
    if request.is_ajax():
        return HttpResponse(simplejson.dumps({"success": True, "job_id": j.pk, "redirect": "/job/job_setup/%d/" % j.pk}), content_type="application/json")
    return redirect("/job/job_setup/%d/" % j.pk)


@login_required
def batch_move(request):
    if request.method == "POST":
        jobdir = request.POST['jobdir']
        jobs = request.POST['jobs'].split(",")
        for job_id in jobs:
            job = Job.objects.get(pk=int(job_id.strip()))
            job.move_dir(jobdir)
            basename = os.path.basename(job.jobdir.rstrip("/"))
            job.jobdir = os.path.join(jobdir, basename)
            job.save()
            messages.success(request, "%s successfully moved to %s" % (job.jobname, job.jobdir))
        if request.is_ajax():
            return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.jobs")}), content_type="application/json")
        return redirect('tough.views.jobs')
    else:
        return render_to_response('batch_move_form.html', {"setup_type": "move", "jobs": request.GET.get("jobs", "")}, context_instance=RequestContext(request)) 


@login_required
def change_project(request, to_project_id):
    if request.method == 'POST':
        job_ids = simplejson.loads(request.POST.get('job_ids'))
        if int(to_project_id) == 0:
            for job_id in job_ids:
                j = get_object_or_404(Job, pk = job_id)
                if j.project:  
                    j.project.job_set.remove(j)
                j.project = None
                j.save()
        else:
            to_project = get_object_or_404(Project, pk = to_project_id)
            for job_id in job_ids:
                j = get_object_or_404(Job, pk = job_id)
                if j.project:
                    j.project.job_set.remove(j)
                j.project = to_project
                j.save()
    return redirect("tough.views.jobs")

@login_required
def create_job(request, job_id=None, type="new"):
    if request.method == "POST":
        #create new job in database
        u = NoahUser.objects.get(username=request.user)
        #add a timestamp-based directory name to the path that will become jobdir
        folder_name = re.sub(r"\s+", "_", request.POST['jobname']) + '_TOUGH_' + strftime("%Y%b%d-%H%M%S", localtime())
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
            messages.success(request, "%s successfully moved to %s" % (j.jobname, j.jobdir))
            return redirect('tough.views.jobs')
        else:
            j = Job(user=u, jobdir=jobdir, machine=request.POST['machine'], jobname=request.POST['jobname'], dir_name=folder_name, edit_type=request.POST['edit_type'])
            if j.edit_type == 1:
                j.infile = j.jobname
            #create directory with unique id
            j.create_dir()

            if request.POST.get("project", False):
                j.project = Project.objects.get(pk=request.POST.get("project"))

            # Copy over the files to the new dir, if this is an import or copy
            if srcdir:
                if j.edit_type == 1:
                    j.import_files(srcdir, filelist=['incon', 'mesh'])
                else:
                    j.import_files(srcdir)
                # Delete any old timestamp files and update directory in batch file
                # running this on imports, too, in case the user imports an old nova directory
                dir_info = j.get_dir()
                filelist = [dirent['name'] for dirent in dir_info]
                if 'started' in filelist:
                    j.del_file('started')
                if 'completed' in filelist:
                    j.del_file('completed')
                if 'tough.pbs' in filelist:
                    j.put_file('tough.pbs', j.generate_batch())
                j.time_last_updated = datetime.utcnow().replace(tzinfo=utc)
                j.save()
                populate_job(j)
                m = j.block_set.get(blockType__tough_name = "mesh")
                m.last_uploaded = (datetime.utcnow().replace(tzinfo=utc))
                m.save()

                inconblock = j.block_set.get(blockType__tough_name = "incon")
                inconblock.last_uploaded = (datetime.utcnow().replace(tzinfo=utc))
                inconblock.save()
                #note creation time so that sorting works
            else:
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
        b.content = blocktype.default_content
        b.save()


@login_required
def job_edit(request, job_id):
    j = get_object_or_404(Job, id=int(job_id))
    if j.edit_type != 1:
        return render_to_response('unguided_job_edit.html',
                                  {'job_name': j.jobname, 'job_id': job_id, 'job': j},
                                  context_instance=RequestContext(request))
    else:
        return render_to_response('job_edit.html',
                                  {'job_name': j.jobname, 'job_id': job_id, "mesh_last_uploaded": j.block_set.get(blockType__tough_name='mesh').last_uploaded, "incon_last_uploaded":j.block_set.get(blockType__tough_name='incon').last_uploaded, "sinks_sources_last_uploaded":j.block_set.get(blockType__tough_name='sinks_sources').last_uploaded, 'job': j},
                                  context_instance=RequestContext(request))

@login_required
def file_upload_view(request, job_id, file_type):
    j = get_object_or_404(Job , pk=job_id)
    if (file_type != 'infile' and file_type != "file"):
        block = j.block_set.get(blockType__tough_name = file_type)
    else:
        block = None
    return render_to_response('file_upload.html',
                                {'job_name': j.jobname, 'job_id':job_id, 'job': j, 'file_type':file_type, "block":block}, 
                                context_instance=RequestContext(request))

@login_required
def file_upload(request, job_id, file_type):
    j = get_object_or_404(Job, pk=job_id)
    if j.edit_type == 1 and file_type == 'infile':
        file_from = request.FILES['files'].read()
        j.parse_input_file(file_from)
        messages.success(request, "File successfully uploaded and parsed!")
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.job_edit", kwargs={"job_id": j.pk})}), content_type="application/json")
    else:
        if file_type == "file":
            filename = request.FILES['files'].name
            response = j.upload_files(request.FILES['files'], filename=filename, is_block=False)
            return HttpResponse(simplejson.dumps({"success": True, "filename": filename}), content_type="application/json")
        elif j.edit_type != 1 and file_type == "infile":
            filename = request.FILES['files'].name
            j.infile = filename
            j.save()
            response = j.upload_files(request.FILES['files'], filename=filename, is_block=False)
            j.save_block(BlockType.objects.get(pk=1), j.generate_batch())
            j.put_file(j.jobfile, j.block_set.get(blockType__pk=1).content)
            return HttpResponse(simplejson.dumps({"success": True, "filename": filename}), content_type="application/json")
        else:
            filename = file_type
            response = j.upload_files(request.FILES['files'], filename=filename)
            filename = filename.upper()
        messages.success(request, filename + " was successfully uploaded and saved!")
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.job_edit", kwargs={"job_id": j.pk})}), content_type="application/json")
    if request.is_ajax():
        return HttpResponse(response.json(), content_type="application/json")
    return redirect("tough.views.job_edit", j.pk)


@login_required
def ajax_submit(request, job_id):
    #get the data from the ajax request
    j = Job.objects.get(id=job_id)

    # Combines the blocks into an input file and
    # The batch file into the batch file
    # Only if the view is guided
    if j.edit_type == 1:
        filename = j.infile
        submitted_text = combine_inputs(j)

        #save via newt, then return an okay
        try:
            j.put_file(filename, submitted_text)
        except Exception:
            return HttpResponse(simplejson.dumps({"success": False, "error": "Unable to save input file."}), content_type="application/json")

        batch_text = j.block_set.get(blockType__pk=1).content

        try:
            j.put_file(j.jobfile, batch_text)
        except Exception:
            return HttpResponse(simplejson.dumps({"success": False, "error": "Unable to save batch file."}), content_type="application/json")
    try:
        j.submit()
    except Exception:
        return HttpResponse(simplejson.dumps({"success": False, "error": "Unable to submit job."}), content_type="application/json")

    return redirect('tough.views.job_view', job_id)


def combine_inputs(job):
    text = ''
    for block in job.get_title_block():
        text += block.content + "\n"
    text += job.get_io_files_block().content + "\n"
    for block in job.get_req_blocks():
        text += block.content + "\n"
    for block in job.get_op_blocks():
        text += block.content + "\n"
    text += job.get_end_block().content

    return text


@login_required
def job_view(request, job_id):
    j = get_object_or_404(Job, pk=job_id)
    if j.state and j.state not in ['completed', 'aborted', 'toberun']:
        j.update()
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
        j.import_file(filename = file_type, from_job_id = job_from.pk)
        b = j.block_set.get(blockType__tough_name = file_type)
        b.last_uploaded = datetime.utcnow().replace(tzinfo=utc)
        b.save()
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
                j.queue = form.cleaned_data['queue']
                j.numprocs = int(form.cleaned_data['num_procs'])
                j.maxwalltime = time(hour=int(form.cleaned_data["max_walltime"][0]), minute=int(form.cleaned_data["max_walltime"][1]))
                
                mail = "".join(form.cleaned_data['email_notifications'])
                if not mail:
                    mail = 'n'
                j.emailnotifications = ",".join(mail)
                
                j.executable = form.cleaned_data['executable']
                j.save()
                content = j.generate_batch()
            elif input_type == 'raw':
                content = form.cleaned_data['rawinput']
            else:
                content = form.cleaned_data['jobchoice'].block_set.get(blockType=blocktype).content
            try:
                j.save_block(blocktype, content)
                j.time_last_updated = datetime.utcnow().replace(tzinfo=utc)
                j.save()
                if j.edit_type != 1:
                    batch_text = j.block_set.get(blockType__pk=1).content
                    j.put_file(j.jobfile, batch_text)
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
    return render_to_response("popup_form_base.html", {"form": form, "form_action": reverse("tough.views.create_project"), "form_title": "Create Project", "msg_success":"Project successfully created!"}, context_instance=RequestContext(request))

def delete_project(request, project_id):
    project = get_object_or_404(Project, pk = project_id)
    if request.POST.get('deljobs', False):
        for job in project.job_set.all():
            job.delete()
            job.del_dir()
    else:
        for job in project.job_set.all():
            job.project = None
    project.delete()
    return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.jobs")}), content_type="application/json")


def ajax_file_delete(request, job_id, path):
    job = get_object_or_404(Job, pk=job_id)
    try:
        job.del_dir(dir=job.jobdir+"/"+path.strip("/"))
    except Exception, e:
        return HttpResponse(simplejson.dumps({"success":False, "error": str(e), "path": job.jobdir + "/" + path.strip("/")}),content_type="application/json")
    return HttpResponse(simplejson.dumps({"success": True, "path": job.jobdir + "/" + path.strip("/")}), content_type="application/json")


def info_edit(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if request.method == "POST":
        form = InfoEditForm(data=request.POST, job=job, instance=job)
        if form.is_valid():
            if Job.objects.get(pk=job.pk).jobdir != form.cleaned_data['jobdir']:
                try:
                    Job.objects.get(pk=job.pk).move_dir(tgtdir=form.cleaned_data['jobdir'])
                    form.save()
                except Exception:
                    messages.error(request, "Failed to move current job to '%s'" % form.cleaned_data['jobdir'])
            else:
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
    # import ipdb; ipdb.set_trace()
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
                "date": djangolocaltime(f['date']).strftime("%b %d, %Y, %I:%M %p"),
                "is_folder": f['perms'][0] == "d"
            })
    listing = sorted(listing, key=lambda f: f['name'].lower())
    listing = sorted(listing, key=lambda f: f['is_folder'], reverse=True)
    return HttpResponse(simplejson.dumps({"success": True, "listing": listing}), content_type="application/json")


@login_required
def ajax_get_job_info(request, job_id):
    j = get_object_or_404(Job, pk=job_id)
    time_completed = djangolocaltime(j.time_completed).strftime("%b %d, %Y, %I:%M %p") if j.time_completed else None
    time_submitted = djangolocaltime(j.time_submitted).strftime("%b %d, %Y, %I:%M %p") if j.time_submitted else None
    time_started = djangolocaltime(j.time_started).strftime("%b %d, %Y, %I:%M %p") if j.time_started else None
    if j.state == 'completed':
        timeuse = str(j.time_completed-j.time_started)
        jobdone = True
    elif j.state == 'started':
        jobdone = False
        timeuse = datetime(datetime.utcnow().replace(tzinfo = utc) - j.time_submitted).strftime("%I:%M:%S")
    else:
        if j.state == 'aborted':
            jobdone = True
        else:
            jobdone = False
        timeuse = None
    return HttpResponse(simplejson.dumps({"success":True, "job_done": jobdone, "time_submitted": time_submitted, "time_started": time_started, "time_completed": time_completed, "time_used": timeuse}), content_type="application/json")

@login_required
def ajax_mkdir(request, machine, directory):
    cookie_str = request.user.cookie
    response, content = util.newt_request('/command/'+machine, 'POST', params={'executable': '/bin/mkdir -p ' + directory}, cookie_str=cookie_str)
    if response.status_code != 200:
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
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.jobs")}), content_type="application/json")
    else:
        return redirect("tough.views.jobs")

@login_required
def delete_jobs_selected(request):
    job_idslist = simplejson.loads(request.POST['job_ids'])
    if request.POST.get("files", False):
        for job_id in job_idslist:
            job = get_object_or_404(Job, pk = job_id)
            job.del_dir()
            job.delete()
    else:
        for job_id in job_idslist:
            job = get_object_or_404(Job, pk = job_id)
            job.delete()
    if request.is_ajax():
        return HttpResponse(simplejson.dumps({"success": True, "redirect": reverse("tough.views.jobs")}), content_type="application/json")
    else:
        return redirect("tough.views.jobs")

@login_required
def rename_job(request, job_id):
    j = get_object_or_404(Job, pk=job_id)
    j.jobname = request.POST['new_name']
    j.save()
    return redirect('tough.views.view_job', job_id=j.id)

@login_required
def ajax_get_zip_selected(request, job_id):
    files = request.GET.get['files']

@login_required
def ajax_get_zip(request, job_id, directory=""):
    j=Job.objects.get(id=job_id)
    zip = j.get_zip(directory=directory)
    if directory:
        filename = directory[directory.rfind("/")+1:] + ".tar.gz"
    else:
        filename = j.dir_name + ".tar.gz"
    response = HttpResponse(zip, content_type='application/x-zip-compressed')
    response['Content-Disposition'] = 'attachment; filename=' + filename
    return response


@login_required
def run_job(request, job_id):
    return view_job(request, job_id, True)


@login_required
def ajax_run_job(request, job_id):
    j = Job.objects.get(id=job_id)
    # Run the job
    if j.state == 'toberun':
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
