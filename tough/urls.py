from django.conf.urls import *
from django.views.generic import TemplateView
from django.conf import settings
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'TOUGH.views.home', name='home'),
    # url(r'^TOUGH/', include('TOUGH.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', 'tough.views.home'),
    url(r'^home/$', 'tough.views.home'),
    url(r'^about/$', 'tough.views.about'),
    url(r'^login/$', 'login.views.login_view'),
    url(r'^logout/$', 'login.views.logout_view'),
    url(r'^job/$', "tough.views.jobs"),
    url(r'^job/status/(?P<job_id>\d+)/$', 'tough.views.job_view'),
    url(r'^job/status/(?P<job_id>\d+)/refresh/$', 'tough.views.ajax_get_job_info'),
    url(r'^job/status/(?P<job_id>\d+)/download/(?P<filename>.+)/$', 'tough.views.get_file'),
    url(r'^job/status/(?P<job_id>\d+)/tail/(?P<filepath>.+)/$', 'tough.views.tail_file'),
    url(r'^job/(?P<job_id>\d+)/view/(?P<filepath>.+)/$', 'tough.views.view_file'),
    url(r'^job/(?P<job_id>\d+)/graph/(?P<filepath>.+)/$', 'tough.views.view_graph'),
    url(r'^job/status/(?P<job_id>\d+)/graph/(?P<filepath>.+)/$', 'tough.views.update_graph'),
    url(r'^job/job_setup/file_upload_view/(?P<job_id>\d+)/(?P<file_type>\w+)/$', 'tough.views.file_upload_view'),
    url(r'^job/job_setup/file_upload/(?P<job_id>\d+)/(?P<file_type>\w+)/$', 'tough.views.file_upload'),
    url(r'^job/job_setup/file_import/(?P<job_id>\d+)/(?P<file_type>\w+)/$', 'tough.views.import_file'),
    # url(r'^job/status/(?P<jobid>\d+)/download/(?P<blockname>.+)/$', 'tough.views.get_block'),
    url(r'^job/new/$', 'tough.views.create_job'),
    url(r'^job/(?P<job_id>\d+)/rebuild/$', 'tough.views.rebuild_job'),
    url(r'^job/(?P<type>copy)/(?P<job_id>\d+)/$', 'tough.views.create_job'),
    url(r'^job/(?P<type>move)/(?P<job_id>\d+)/$', 'tough.views.create_job'),
    url(r'^job/changeproject/(?P<to_project_id>\d+)/$', 'tough.views.change_project'),
    url(r'^job/del/(?P<job_id>\d+)/$', 'tough.views.delete_job'),
    url(r'^job/del/selected/$', 'tough.views.delete_jobs_selected'),
    url(r'^job/job_setup/(?P<job_id>\d+)/$', 'tough.views.job_edit'),
    url(r'^job/save/(?P<job_id>\d+)/(?P<input_type>\w+)/$', 'tough.views.ajax_save'),
    url(r'^job/submit/(?P<job_id>\d+)/$', 'tough.views.ajax_submit'),
    url(r'^job/preview/(?P<job_id>\d+)/$', 'tough.views.preview_input'),
    url(r'^job/(?P<job_id>\d+)/file/(?P<filename>.+)/$', 'tough.views.get_file'),
    url(r'^job/(?P<job_id>\d+)/zip/$', 'tough.views.ajax_get_zip'),
    url(r'^job/(?P<job_id>\d+)/zip/(?P<directory>.+)/$', 'tough.views.ajax_get_zip'),
    url(r'^project/new/$', 'tough.views.create_project'),
    url(r'^job/info_edit/(?P<job_id>\d+)/$', 'tough.views.info_edit'),
    url(r'^project/edit/(?P<project_id>\d+)/$', 'tough.views.edit_project'),
    url(r'^error/$', 'tough.views.report_error'),
    url(r'^project/(?P<project_id>\d+)/$','tough.views.project_view'),
    url(r'^project/(?P<project_id>\d+)/delete', 'tough.views.delete_project'),
    url(r'^ajax/job/(?P<job_id>\d+)/file/(?P<directory>.+)/$', 'tough.views.ajax_get_job_dir'),
    url(r'^ajax/job/(?P<job_id>\d+)/file/$', 'tough.views.ajax_get_job_dir'),
    url(r'^ajax/move/$', 'tough.views.batch_move'),
)
if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^404/$', TemplateView.as_view(template_name="404.html")),
    )
