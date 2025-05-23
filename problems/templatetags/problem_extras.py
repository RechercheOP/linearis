from django import template
from itertools import zip_longest

register = template.Library()

@register.filter
def index(lst, i):
    try:
        return lst[i]
    except:
        return None

@register.filter(name='zip')
def zip_filter(a, b):
    return zip_longest(a, b, fillvalue=None) 