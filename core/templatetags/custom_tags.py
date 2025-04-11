from django import template
import json

register = template.Library()

@register.filter
def pprint(value):
    """Pretty print JSON data"""
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            # Try to parse the string as JSON
            value = json.loads(value)
        return json.dumps(value, indent=2)
    except:
        # If parsing fails, return the original value
        return value