from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, css_class):
    """
    Adds a CSS class to a form widget.
    Usage: {{ field|add_class:"my-css-class" }}
    """
    # Ensure the widget has an attrs dictionary
    if hasattr(value, 'field') and hasattr(value.field, 'widget'):
         attrs = value.field.widget.attrs
         # If the 'class' key exists, append the new class
         if 'class' in attrs:
              # Avoid adding duplicate classes if not desired, but simple append is common
              current_classes = attrs['class'].split()
              if css_class not in current_classes:
                   attrs['class'] = f"{attrs['class']} {css_class}"
         else:
              # If 'class' key does not exist, set it
              attrs['class'] = css_class
         return value.as_widget(attrs=attrs)
    else:
        # Return the original value if it's not a form field or widget
        return value

# You can add other custom filters here if needed