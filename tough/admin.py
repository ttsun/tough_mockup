from tough.models import Block, BlockType, Job, QualifiedBlockRef
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

class QualifiedBlockRefAdmin(admin.ModelAdmin):
    list_display = ("blockType","name")
admin.site.register(QualifiedBlockRef, QualifiedBlockRefAdmin)
