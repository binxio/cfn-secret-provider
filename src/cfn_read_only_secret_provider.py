import hashlib
import logging
import os

import boto3
from cfn_resource_provider import ResourceProvider

import ssm_parameter_name

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


request_schema = {
    "type": "object",
    "required": ["Name"],
    "properties": {
        "Name": {
            "type": "string",
            "minLength": 1,
            "pattern": "[a-zA-Z0-9_/]+",
            "description": "the name of the value in the parameters store",
        },
        "Region": {
            "type": "string",
            "pattern": "[a-z0-9\\-]+",
            "description": "of the parameter store",
        },
        "NoEcho": {
            "type": "boolean",
            "default": True,
            "description": "the secret as output parameter",
        },
    },
}


class ReadOnlySecretProvider(ResourceProvider):
    def __init__(self):
        super(ReadOnlySecretProvider, self).__init__()
        self._value = None
        self.request_schema = request_schema
        self.default_region = boto3.session.Session().region_name
        self.account_id = (boto3.client("sts")).get_caller_identity()["Account"]

    @property
    def region(self):
        return self.get("Region", self.default_region)

    @property
    def ssm(self):
        return boto3.client("ssm", region_name=self.region)

    @property
    def arn(self):
        return ssm_parameter_name.to_arn(self.region, self.account_id, self.get("Name"))

    def get_secret(self):
        response = self.ssm.get_parameter(Name=self.get("Name"), WithDecryption=True)
        value = response["Parameter"]["Value"]
        self.set_attribute("Secret", value)
        self.set_attribute("Version", response["Parameter"]["Version"])
        self.set_attribute("Hash", hashlib.md5(value.encode("utf8")).hexdigest())
        self.set_attribute("Arn", self.arn)
        self.physical_resource_id = self.arn
        self.set_attribute("ParameterName", ssm_parameter_name.from_arn(self.arn))
        self.no_echo = True

    def create(self):
        self.get_secret()

    def update(self):
        self.get_secret()

    def delete(self):
        pass


provider = ReadOnlySecretProvider()


def handler(request, context):
    return provider.handle(request, context)
