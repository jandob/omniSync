import re


def camelize(string, upper_camel_case=True):
    """
    Convert strings to CamelCase.
    Args:
        upper_camel_case (bool):
            If `True`: UpperCamelCase. Else: lowerCamelCase.
            Default: `True`.
    """
    if upper_camel_case:
        return re.sub(r"(?:^|_)(.)", lambda m: m.group(1).upper(), string)
    else:
        return string[0].lower() + camelize(string)[1:]


def underscore(word):
    """
    Convert string to underscored (and lowercase).
    """
    word = re.sub(r"([A-Z]+)([A-Z][a-z])", r'\1_\2', word)
    word = re.sub(r"([a-z\d])([A-Z])", r'\1_\2', word)
    word = word.replace("-", "_")
    return word.lower()
