from tough.models import Block, BlockType, Job
from django.contrib import admin


class BlockTypeAdmin(admin.ModelAdmin):
    list_display = ("ordering", "name")
admin.site.register(BlockType, BlockTypeAdmin)

class JobAdmin(admin.ModelAdmin):
    pass
admin.site.register(Job, JobAdmin)

class BlockAdmin(admin.ModelAdmin):
    pass
admin.site.register(Block, BlockAdmin)
