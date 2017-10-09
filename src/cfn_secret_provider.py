import boto3
import hashlib
import logging
import time
import string
import os
from random import choice
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider

log = logging.getLogger()
log.setLevel(os.environ.get("LOGLEVEL", "INFO"))


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
                "ReturnSecret": {"type": "boolean",
                                 "default": False,
                                 "description": "return secret as attribute 'Secret'"},
                "KeyAlias": {"type": "string",
                             "default": "alias/aws/ssm",
                             "description": "KMS key to use to encrypt the value"},
                "Length": {"type": "integer",  "minimum": 1, "maximum": 512,
                           "default": 30,
                           "description": "length of the secret"}
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
        except ValueError as e:
            log.error('failed to convert property types %s', e)

    @property
    def allow_overwrite(self):
        return self.physical_resource_id == self.arn

    @property
    def arn(self):
        return 'arn:aws:ssm:%s:%s:parameter/%s' % (self.region, self.account_id, self.get('Name'))

    def create_or_update_secret(self):
        try:
            kwargs = {
                'Name': self.get('Name'),
                'KeyId': self.get('KeyAlias'),
                'Type': 'SecureString',
                'Overwrite': self.allow_overwrite,
                'Value': "".join(choice(self.get('Alphabet')) for x in range(0, self.get('Length'))),
            }
            if self.get('Description') != '':
                kwargs['Description'] = self.get('Description')

            self.ssm.put_parameter(**kwargs)

            self.set_attribute('Arn', self.arn)
            if self.get('ReturnSecret'):
                self.set_attribute('Secret', kwargs['Value'])

            self.physical_resource_id = self.arn
        except ClientError as e:
            self.physical_resource_id = 'could-not-create'
            self.fail(str(e))

    def create(self):
        self.create_or_update_secret()

    def update(self):
        self.create_or_update_secret()

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
