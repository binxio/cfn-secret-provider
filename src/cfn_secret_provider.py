import os
import re
import time
import string
import hashlib
import logging
import boto3
from random import choice
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


request_schema = {
    "type": "object",
            "required": ["Name"],
            "properties": {
                "Name": {"type": "string", "minLength": 1, "pattern": "[a-zA-Z0-9_/]+",
                         "description": "the name of the value in the parameters store"},
                "Description": {"type": "string", "default": "",
                                "description": "the description of the value in the parameter store"},
                "Alphabet": {"type": "string",
                             "default": "abcdfghijklmnopqrstuvwyxzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
                             "description": "the characters from which to generate the secret"},
                "RefreshOnUpdate": {"type": "boolean", "default": False,
                                    "description": "generate a new secret on update"},
                "ReturnSecret": {"type": "boolean",
                                 "default": False,
                                 "description": "return secret as attribute 'Secret'"},
                "KeyAlias": {"type": "string",
                             "default": "alias/aws/ssm",
                             "description": "KMS key to use to encrypt the value"},
                "Length": {"type": "integer",  "minimum": 1, "maximum": 512,
                           "default": 30,
                           "description": "length of the secret"},
                "Version": {"type": "string",  "description": "opaque string to force update"},
                "NoEcho": {"type": "boolean",  "default": True, "description": "the secret as output parameter"}
            }
}


class SecretProvider(ResourceProvider):

    def __init__(self):
        super(SecretProvider, self).__init__()
        self._value = None
        self.request_schema = request_schema
        self.ssm = boto3.client('ssm')
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client('sts')).get_caller_identity()['Account']

    def convert_property_types(self):
        try:
            if 'Length' in self.properties and isinstance(self.properties['Length'], (str, unicode,)):
                self.properties['Length'] = int(self.properties['Length'])
            if 'ReturnSecret' in self.properties and isinstance(self.properties['ReturnSecret'], (str, unicode,)):
                self.properties['ReturnSecret'] = (self.properties['ReturnSecret'] == 'true')
            if 'NoEcho' in self.properties and isinstance(self.properties['NoEcho'], (str, unicode,)):
                self.properties['NoEcho'] = (self.properties['NoEcho'] == 'true')
            if 'RefreshOnUpdate' in self.properties and isinstance(self.properties['RefreshOnUpdate'], (str, unicode,)):
                self.properties['RefreshOnUpdate'] = (self.properties['RefreshOnUpdate'] == 'true')
        except ValueError as e:
            log.error('failed to convert property types %s', e)

    @property
    def allow_overwrite(self):
        return self.physical_resource_id == self.arn

    def name_from_physical_resource_id(self):
        """
        returns the name from the physical_resource_id as returned by self.arn, or None
        """
        arn_regexp = re.compile(r'arn:aws:ssm:(?P<region>[^:]*):(?P<account>[^:]*):parameter/(?P<name>.*)')
        m = re.match(arn_regexp, self.physical_resource_id)
        return m.group('name') if m is not None else None

    @property
    def arn(self):
        return 'arn:aws:ssm:%s:%s:parameter/%s' % (self.region, self.account_id, self.get('Name'))

    def put_parameter(self, overwrite=False, new_secret=True):
        try:
            kwargs = {
                'Name': self.get('Name'),
                'KeyId': self.get('KeyAlias'),
                'Type': 'SecureString',
                'Overwrite': overwrite
            }

            if self.get('Description') != '':
                kwargs['Description'] = self.get('Description')

            if new_secret:
                kwargs['Value'] = "".join(choice(self.get('Alphabet')) for x in range(0, self.get('Length')))
            else:
                kwargs['Value'] = self.get_secret()

            response = self.ssm.put_parameter(**kwargs)
            version = response['Version'] if 'Version' in response else 1

            self.set_attribute('Arn', self.arn)
            self.set_attribute('Hash', hashlib.md5(kwargs['Value']).hexdigest())
            self.set_attribute('Version', version)

            if self.get('ReturnSecret'):
                self.set_attribute('Secret', kwargs['Value'])
            self.no_echo = self.get('NoEcho')

            self.physical_resource_id = self.arn
        except ClientError as e:
            self.physical_resource_id = 'could-not-create'
            self.fail(str(e))

    def get_secret(self):
        response = self.ssm.get_parameter(Name=self.name_from_physical_resource_id(), WithDecryption=True)
        return response['Parameter']['Value']

    def create(self):
        self.put_parameter(overwrite=False, new_secret=True)

    def update(self):
        self.put_parameter(overwrite=(self.physical_resource_id == self.arn), new_secret=self.get('RefreshOnUpdate'))

    def delete(self):
        name = self.physical_resource_id.split('/', 1)
        if len(name) == 2:
            try:
                response = self.ssm.delete_parameter(Name=name[1])
            except ClientError as e:
                if e.response["Error"]["Code"] != 'ParameterNotFound':
                    return self.fail(str(e))

            self.success('System Parameter with the name %s is deleted' % name)
        else:
            self.success('System Parameter with the name %s is ignored' %
                         self.physical_resource_id)

provider = SecretProvider()


def handler(request, context):
    return provider.handle(request, context)
