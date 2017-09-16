import boto3
import hashlib
import logging
import time
import string
from random import choice
from botocore.exceptions import ClientError

import cfn_resource

log = logging.getLogger()
log.setLevel(logging.DEBUG)

ssm = boto3.client('ssm')
sts = boto3.client('sts')
region = boto3.session.Session().region_name
account_id = sts.get_caller_identity()['Account']

handler = cfn_resource.Resource()


class Secret(dict):

    def __init__(self, event):
        self.update(event)
        self.update(event['ResourceProperties'])
        del self['ResourceProperties']
        self._value = None

    @property
    def length(self):
        return int(self['Length']) if 'Length' in self else 30

    @property
    def key_alias(self):
        return self['KeyAlias'] if 'KeyAlias' in self else 'alias/aws/ssm'

    @property
    def description(self):
        return self['Description'] if 'Description' in self else None

    @property
    def allowed_characters(self):
        return self['Alphabet'] if 'Alphabet' in self else (string.ascii_letters + '!@#$^*+=' + string.digits)

    @property
    def logical_resource_id(self):
        return self['LogicalResourceId'] if 'LogicalResourceId' in self else ''

    @property
    def physical_resource_id(self):
        return self['PhysicalResourceId'] if 'PhysicalResourceId' in self else ''

    @property
    def name(self):
        return self['Name'] if 'Name' in self else None

    @property
    def value(self):
        if self._value is None:
            self._value = "".join(choice(self.allowed_characters) for x in range(0, self.length))
        return self._value

    @property
    def allow_overwrite(self):
        return 'PhysicalResourceId' in self and self.physical_resource_id == self.arn

    @property
    def arn(self):
        return 'arn:aws:ssm:%s:%s:parameter/%s' % (region, account_id, self.name)


class Response(dict):

    def __init__(self, status, reason, resource_id, data={}):
        self['Status'] = status
        self['Reason'] = reason
        self['PhysicalResourceId'] = resource_id
        self['Data'] = data


def create_or_update_secret(event, context):
    secret = Secret(event)
    if secret.name is None:
        return Response('Name property is required', 'could-not-create')

    try:
        ssm.put_parameter(Name=secret.name, KeyId=secret.key_alias,
                          Type='SecureString', Overwrite=secret.allow_overwrite, Value=secret.value)
    except ClientError as e:
        return Response('FAILED', str(e), 'could-not-create')

    return Response('SUCCESS', '', secret.arn, {'Secret': secret.value})


@handler.create
def create_secret(event, context):
    return create_or_update_secret(event, context)


@handler.update
def update_secret(event, context):
    return create_or_update_secret(event, context)


@handler.delete
def delete_secret(event, context):
    response = None
    name = event['PhysicalResourceId'].split('/', 1)
    if len(name) == 2:
        try:
            response = ssm.delete_parameter(Name=name[1])
        except ClientError as e:
            if e.response["Error"]["Code"] != 'ParameterNotFound':
                return Response('FAILED', str(e), event['PhysicalResourceId'])

        reason = 'System Parameter with the name %s is deleted' % name
    else:
        reason = 'System Parameter with the name %s is ignored' % event['PhysicalResourceId']

    return Response('SUCCESS', reason, event['PhysicalResourceId'])
