from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Template da dict['key'] o'rniga ishlatiladi: dict|get_item:key"""
    return dictionary.get(key)
