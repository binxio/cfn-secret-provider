import re
import logging
import boto3
import base64
import hmac
import hashlib
import string
from cfn_resource_provider import ResourceProvider
from botocore.exceptions import ClientError

log = logging.getLogger()

request_schema = {
    "type": "object",
    "required": ["ParameterPath", "UserName"],
    "properties": {
        "ParameterPath": {
            "type": "string",
            "pattern": "^/[a-zA-Z0-9/.\\-_]*[^/]$",
           "description": "for the credentials in the parameter store"},
        "Description": {
            "type": "string",
            "default": " ",
            "description": "the description of the value in the parameter store"},
        "ReturnSecret": {
            "type": "boolean",
             "default": False,
             "description": "return access id and secret"},
        "ReturnPassword": {
            "type": "boolean",
            "default": False,
            "description": "return access id and smtp password"},
        "KeyAlias": {
            "type": "string",
            "default": "alias/aws/ssm",
            "description": "KMS key to use to encrypt the value"},
        "Serial": {
            "type": "integer",
            "default": 1,
           "description": "version to force update"},
        "Status": {
            "type": "string",
            "default": "Active",
            "enum": ["Active", "Inactive"],
           "description": "status of the key"},
        "UserName": {
            "type": "string",
            "description": "to create the access key for"}
    }
}


class AccessKeyProvider(ResourceProvider):

    def __init__(self):
        super(AccessKeyProvider, self).__init__()
        self.request_schema = request_schema
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client('sts')).get_caller_identity()['Account']
        self.iam = boto3.client('iam')
        self.ssm = boto3.client('ssm')

    def hash_secret(self, key):
        message = "SendRawEmail"
        version = '\x02'
        h = hmac.new(key.encode('utf-8'), message, digestmod=hashlib.sha256)
        return base64.b64encode("{0}{1}".format(version, h.digest()))


    def delete_access_key(self, access_key):
        try:
            self.iam.delete_access_key(UserName=access_key['UserName'], AccessKeyId=access_key['AccessKeyId'])
        except self.iam.exceptions.NoSuchEntityException as e:
            log.info('no access key {AccessKeyId} was found for user {UserName}'.format(**access_key))
        except ClientError as e:
            self.fail('failed to delete access key, {}'.format(e))

    def create_access_key(self):
        access_key = None
        try:
            user_name = self.get('UserName')
            response = self.iam.create_access_key(UserName=user_name)
            access_key = response['AccessKey']
            self.iam.update_access_key(
                    UserName=user_name,
                    AccessKeyId=access_key['AccessKeyId'],
                    Status=self.get('Status'))
        except ClientError as e:
            if access_key is not None:
                self.delete_access_key(access_key)
            self.fail('failed to create access key for user {}\n{}'.format(user_name, self.reason))
        return access_key


    @property
    def parameter_path(self):
        return string.rstrip(self.get('ParameterPath'), '/ \t')

    @property
    def old_parameter_path(self):
        return string.rstrip(self.get_old('ParameterPath', self.get('ParameterPath')), '/ \t')

    @property
    def arn(self):
        return 'arn:aws:ssm:%s:%s:parameter/%s' % (self.region, self.account_id, self.parameter_path)

    @property
    def name_from_physical_resource_id(self):
        """
        returns the name from the physical_resource_id as returned by self.arn, or None
        """
        arn_regexp = re.compile(r'arn:aws:ssm:(?P<region>[^:]*):(?P<account>[^:]*):parameter/(?P<name>.*)')
        m = re.match(arn_regexp, self.physical_resource_id)
        return m.group('name') if m is not None else None

    def check_parameter_path_exists(self):
        try:
            name = '{}'.format(self.get('ParameterPath'))
            response = self.ssm.get_parameter(Name=name)
            self.fail('parameter {} already exists.'.format(name))
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != 'ParameterNotFound':
                raise

        try:
            name = '{}/aws_access_key_id'.format(self.get('ParameterPath'))
            response = self.ssm.get_parameter(Name=name)
            self.fail('parameter {} already exists.'.format(name))
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != 'ParameterNotFound':
                raise

        return False

    def put_in_parameter_store(self, access_key):
        self.ssm.put_parameter(Name='{}/aws_access_key_id'.format(self.parameter_path),
                               Value=access_key['AccessKeyId'],
                               Type='SecureString', Overwrite=True, KeyId=self.get('KeyAlias'),
                               Description='{} access id'.format(self.get('Description')))

        self.ssm.put_parameter(Name='{}/aws_secret_access_key'.format(self.parameter_path),
                               Value=access_key['SecretAccessKey'],
                               Type='SecureString', Overwrite=True, KeyId=self.get('KeyAlias'),
                               Description='{} secret key'.format(self.get('Description')))

        self.ssm.put_parameter(Name='{}/smtp_password'.format(self.parameter_path),
                               Value=self.hash_secret(access_key['SecretAccessKey']),
                               Type='SecureString', Overwrite=True, KeyId=self.get('KeyAlias'),
                               Description='{} smtp password'.format(self.get('Description')))

    def remove_from_parameter_store(self, parameter_path):
        name = None
        for suffix in [ '/aws_access_key_id', '/aws_secret_access_key', '/smtp_password']:
            try:
                name = '{}{}'.format(parameter_path, suffix)
                self.ssm.delete_parameter(Name=name)
            except ClientError as e:
                if e.response["Error"]["Code"] != 'ParameterNotFound':
                    msg = 'failed to delete parameter {}, {}\n'.format(name, e)
                    self.reason = '{}{}'.format(self.reason, msg)

    def get_from_parameter_store(self, parameter_path=None):
        if parameter_path is None:
            parameter_path = self.parameter_path

        result = {}
        response = self.ssm.get_parameter(Name='{}/aws_access_key_id'.format(parameter_path), WithDecryption=True)
        result['AccessKeyId'] = response['Parameter']['Value']
        response = self.ssm.get_parameter(Name='{}/aws_secret_access_key'.format(parameter_path), WithDecryption=True)
        result['SecretAccessKey'] = response['Parameter']['Value']
        response = self.ssm.get_parameter(Name='{}/smtp_password'.format(parameter_path), WithDecryption=True)
        result['SMTPPassword'] = response['Parameter']['Value']

        return result

    def set_result_attributes(self, access_key):
        self.physical_resource_id = self.arn
        self.put_in_parameter_store(access_key)

        if self.get('ReturnSecret'):
           self.set_attribute('AccessKeyId', access_key['AccessKeyId'])
           self.set_attribute('SecretAccessKey', access_key['SecretAccessKey'])

        if self.get('ReturnPassword'):
           self.set_attribute('AccessKeyId', access_key['AccessKeyId'])
           self.set_attribute('SMTPPassword', self.hash_secret(access_key['SecretAccessKey']))

    def create(self):
        if not self.check_parameter_path_exists():
            access_key = self.create_access_key()
            if access_key is not None:
                self.set_result_attributes(access_key)
            else:
                self.physical_resource_id = 'could-not-create'
        else:
            self.physical_resource_id = 'could-not-create'


    @property
    def update_requires_new_key(self):
        if self.get('Serial', 1) > self.get_old('Serial', 1):
            return True

        if self.get('UserName') != self.get_old('UserName', self.get('UserName')):
            return True

        if self.get('ParameterPath') != self.get_old('ParameterPath', self.get('ParameterPath')):
            return True

        return False

    def update(self):
        if self.get_old('ParameterPath', self.get('ParameterPath')) != self.get('ParameterPath'):
            if self.check_parameter_path_exists():
                return

        old_access_key = self.get_from_parameter_store(self.old_parameter_path)
        old_access_key['UserName'] = self.get_old('UserName', self.get('UserName'))

        if self.update_requires_new_key:
            access_key = self.create_access_key()
            if access_key is not None:
                self.set_result_attributes(access_key)
                self.delete_access_key(old_access_key)
        else:
            try:
                self.iam.update_access_key(
                    UserName=self.get('UserName'),
                    AccessKeyId=old_access_key['AccessKeyId'],
                    Status=self.get('Status'))
                self.set_result_attributes(old_access_key)
            except ClientError as e:
                self.fail('failed to update access key, {}'.format(e))

    def delete(self):
        parameter_path = self.name_from_physical_resource_id
        if parameter_path is not None:
            access_key = self.get_from_parameter_store(parameter_path)
            access_key['UserName'] = self.get('UserName')
            self.delete_access_key(access_key)
            self.remove_from_parameter_store(parameter_path)
        else:
            self.success('ignoring invalid physical resource id, {}'.format(self.physical_resource_id))

provider = AccessKeyProvider()


def handler(request, context):
    return provider.handle(request, context)
