from django.conf import settings

def TOUGH_SUBDIRs(context):
	return {'TOUGH_STATIC_SUBDIR': settings.TOUGH_STATIC_SUBDIR, 'TOUGH_SUBDIR': settings.TOUGH_SUBDIR, 'APP_NAME': settings.APP_NAME, 'APP_FILES': settings.APP_FILES}