from django import template

register = template.Library()

@register.filter
def social_format(value):
    try:
        num = float(value)
    except (ValueError, TypeError):
        return value

    if num < 1000:
        return str(int(num))
    
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    
    # Use 'k', 'M', 'B' etc.
    suffix = ['', 'k', 'M', 'B', 'T', 'P'][magnitude]
    
    if num >= 10:
        return f"{int(num)}{suffix}"
    else:
        formatted = f"{num:.1f}"
        if formatted.endswith('.0'):
            return f"{int(num)}{suffix}"
        return f"{formatted}{suffix}"

@register.filter(name='splitlines')
def splitlines_filter(value):
    if not value:
        return []
    return value.splitlines()

@register.filter
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0
