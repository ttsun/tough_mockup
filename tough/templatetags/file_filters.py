from django import template

register = template.Library()


@register.filter(name="size_nice")
def size_nice(value):
    if int(value) < 1000:
        return "%0.0f B" % (float(value))
    if int(value) < 100000:
        return "%0.2f kB" % (float(value)/1000)
    else:
        return "%0.2f MB" % (float(value)/1000000)
