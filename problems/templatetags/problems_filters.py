from django import template
import json

register = template.Library()

@register.filter(name='index')
def index(list_obj, i):
    return list_obj[i]

@register.filter
def get_range_from_num_vars_for_slacks(value, arg=None):
    try:
        num_vars = int(value)
        return range(1, num_vars + 1)
    except (ValueError, TypeError):
        return range(1)

@register.filter
def get_range_from_num_constraints_for_slacks(value, arg=None):
    try:
        num_constraints = int(value)
        return range(1, num_constraints + 1)
    except (ValueError, TypeError):
        return range(1)

@register.filter
def get_range_from_num_vars(value, arg=None):
    try:
        num_vars = int(value)
        return range(num_vars)
    except (ValueError, TypeError):
        return range(1)

@register.filter
def get_range_from_num_constraints(value, arg=None):
    try:
        num_constraints = int(value)
        return range(num_constraints)
    except (ValueError, TypeError):
        return range(1)