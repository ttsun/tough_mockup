from django import template

register = template.Library()

@register.filter(name = 'get_vars')
def return_vars_for_name_list(name_list,block):
    from tough.models import *
    return block.blockType.get_name_list_dict()[name_list] 