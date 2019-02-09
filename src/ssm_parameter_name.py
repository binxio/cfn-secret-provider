"""
utility functions to create SSM Parameter Arns and extract the name from an Arn.
"""
import re


def to_arn(region, account_id, name):
    """
    returns the arn of an SSM parameter with specified, region, account_id and name. If the name
    starts with a '/', it does not show up in the Arn as AWS seems to store it that way.
    """
    return 'arn:aws:ssm:%s:%s:parameter/%s' % (region, account_id, name if name[0] != '/' else name[1:])


def from_arn(arn):
    """
    Returns the parameter name from a parameter name Arn, or None if not found.

    """
    m = re.match(arn_regexp, arn)
    name = m.group('name') if m else None
    return name if not name or '/' not in name or name[0] == '/' else '/{}'.format(name)


arn_regexp = re.compile(r'arn:aws:ssm:(?P<region>[^:]*):(?P<account>[^:]*):parameter/(?P<name>.*)')
