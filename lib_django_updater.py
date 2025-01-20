import logging

log = logging.getLogger(__name__)


def check_for_django_update(incoming_text: str) -> bool:
    """
    Check if incoming text contains a Django version.

    Iterates through lines of incoming text.
    - first strips whitespace from each line
    - then checks if the string '+django==' is in the line
    """
    return_val: bool = False
    incoming_lines: list = incoming_text.split('\n')
    for line in incoming_lines:
        line: str = line.strip()
        if '+django==' in line:
            return_val = True
            break
    log.debug(f'return_val: {return_val}')
    return return_val
