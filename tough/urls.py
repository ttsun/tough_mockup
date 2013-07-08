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
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^$', 'tough.views.home'),
    url(r'^home/$', 'tough.views.home'),
    url(r'^about/$', 'tough.views.about'),
    url(r'^login/$', 'login.views.login_view'),
    url(r'^logout/$', 'login.views.logout_view'),
    url(r'^job/$', "tough.views.jobs"),
    url(r'^job/get_tough_files/(?P<jobid>\d+)/$', 'tough.views.ajax_get_tough_files'),
    url(r'^job/job_setup/$', 'tough.views.create_job'),
    url(r'^job/job_setup/(?P<jobid>\d+)/$', 'tough.views.job_edit'),
    url(r'^job/save/(?P<jobid>\d+)/$', 'tough.views.ajax_save'),
    url(r'^job/job_status/$', TemplateView.as_view(template_name="job_status.html")),
)
