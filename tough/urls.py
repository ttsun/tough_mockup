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
    url(r'^$', 'login.views.login_view'),
    url(r'^about/$',TemplateView.as_view(template_name = "about.html")),
    url(r'^job/$', TemplateView.as_view(template_name = "job_control.html")),
    url(r'^job/job_setup/$',TemplateView.as_view(template_name = "job_setup.html")),
    url(r'^job/job_status/$',TemplateView.as_view(template_name = "job_status.html")),
)
