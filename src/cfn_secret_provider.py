import boto3
import hashlib
import logging
import time
import string
import os
from random import choice
from botocore.exceptions import ClientError
from cfn_provider import ResourceProvider

log = logging.getLogger()
log.setLevel(os.environ.get("LOGLEVEL", "INFO"))


class SecretProvider(ResourceProvider):

    def __init__(self):
        super(SecretProvider, self).__init__()
        self._value = None
        self.ssm = boto3.client('ssm')

    @property
    def length(self):
        return int(self.get('Length', 30))

    @property
    def return_secret(self):
        return str(self.get('ReturnSecret', 'false')).lower() == 'true'

    @property
    def key_alias(self):
        return self.get('KeyAlias', 'alias/aws/ssm')

    @property
    def description(self):
        return self.get('Description')

    @property
    def allowed_characters(self):
        return self.get('Alphabet', (string.ascii_letters + string.digits + string.punctuation))

    @property
    def logical_resource_id(self):
        return self.get('LogicalResourceId', '')

    @property
    def name(self):
        return self.get('Name')

    @property
    def allow_overwrite(self):
        return 'PhysicalResourceId' in self.request and self.get('PhysicalResourceId') == self.arn

    @property
    def arn(self):
        return 'arn:aws:ssm:%s:%s:parameter/%s' % (self.region, self.account_id, self.name)

    def is_valid_request(self):
        if self.get('Name') is None:
            self.fail('Name property is required', 'could-not-create')
            return False
        return True

    def create_or_update_secret(self):
        try:
            value = "".join(choice(self.allowed_characters) for x in range(0, self.length))
            self.ssm.put_parameter(Name=self.name, KeyId=self.key_alias,
                                   Type='SecureString', Overwrite=self.allow_overwrite, Value=value)
            self.set_attribute('Arn', self.arn)
            if self.return_secret:
                self.set_attribute('Secret', value)

            self.set_physical_resource_id(self.arn)
            self.success()
        except ClientError as e:
            self.set_physical_resource_id('could-not-create')
            self.fail(str(e))

    def create(self):
        self.create_or_update_secret()
        return self.response

    def update(self):
        self.create_or_update_secret()
        return self.response

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
        return self.response

provider = SecretProvider()


def handler(request, context):
    return provider.handle(request, context)
