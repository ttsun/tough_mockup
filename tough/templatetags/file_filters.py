from django import template

register = template.Library()


@register.filter(name="as_mb")
def as_mb(value):
    return "%0.3f MB" % (float(value)/1000000)
