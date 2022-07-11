import base64
import binascii
import hashlib
import logging
import os

import boto3
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider
from past.builtins import basestring

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
        "Description": {
            "type": "string",
            "default": "",
            "description": "the description of the value in the parameter store",
        },
        "Length": {
            "type": "integer",
            "description": "length of the random string in bytes",
            "minimum": 1,
            "maximum": 512,
            "default": 8,
        },
        "RefreshOnUpdate": {
            "type": "boolean",
            "default": False,
            "description": "generate a new secret on update",
        },
        "ReturnSecret": {
            "type": "boolean",
            "default": False,
            "description": "return secret as attribute 'Secret'",
        },
        "KeyAlias": {
            "type": "string",
            "default": "alias/aws/ssm",
            "description": "KMS key to use to encrypt the value",
        },
        "Version": {"type": "string", "description": "opaque string to force update"},
        "NoEcho": {
            "type": "boolean",
            "default": True,
            "description": "the secret as output parameter",
        },
    },
}


class RandomBytesProvider(ResourceProvider):
    def __init__(self):
        super(RandomBytesProvider, self).__init__()
        self._value = None
        self.request_schema = request_schema
        self.ssm = boto3.client("ssm")
        self.kms = boto3.client("kms")
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client("sts")).get_caller_identity()["Account"]

    def convert_property_types(self):
        try:
            if "Length" in self.properties and isinstance(
                self.properties["Length"], basestring
            ):
                self.properties["Length"] = int(self.properties["Length"])
            if "ReturnSecret" in self.properties and isinstance(
                self.properties["ReturnSecret"], basestring
            ):
                self.properties["ReturnSecret"] = (
                    self.properties["ReturnSecret"] == "true"
                )
            if "NoEcho" in self.properties and isinstance(
                self.properties["NoEcho"], basestring
            ):
                self.properties["NoEcho"] = self.properties["NoEcho"] == "true"
            if "RefreshOnUpdate" in self.properties and isinstance(
                self.properties["RefreshOnUpdate"], basestring
            ):
                self.properties["RefreshOnUpdate"] = (
                    self.properties["RefreshOnUpdate"] == "true"
                )
        except (binascii.Error, ValueError) as e:
            log.error("failed to convert property types %s", e)

    def name_from_physical_resource_id(self):
        return ssm_parameter_name.from_arn(self.physical_resource_id)

    @property
    def allow_overwrite(self):
        return ssm_parameter_name.equals(self.physical_resource_id, self.arn)

    @property
    def arn(self):
        return ssm_parameter_name.to_arn(self.region, self.account_id, self.get("Name"))

    def get_content(self):
        return base64.b64encode(os.urandom(self.get("Length"))).decode("ascii")

    def put_parameter(self, overwrite=False, new_secret=True):
        try:
            kwargs = {
                "Name": self.get("Name"),
                "KeyId": self.get("KeyAlias"),
                "Type": "SecureString",
                "Overwrite": overwrite,
            }

            if self.get("Description") != "":
                kwargs["Description"] = self.get("Description")

            if new_secret:
                kwargs["Value"] = self.get_content()
            else:
                kwargs["Value"] = self.get_secret()

            response = self.ssm.put_parameter(**kwargs)
            version = response["Version"] if "Version" in response else 1

            self.set_attribute("Arn", self.arn)
            self.set_attribute(
                "Hash", hashlib.md5(kwargs["Value"].encode("utf8")).hexdigest()
            )
            self.set_attribute("Version", version)

            if self.get("ReturnSecret"):
                self.set_attribute("Secret", kwargs["Value"])
            self.no_echo = self.get("NoEcho")

            if not ssm_parameter_name.equals(self.physical_resource_id, self.arn):
                # prevent CFN deleting a resource with identical Arns in different formats.
                self.physical_resource_id = self.arn

            self.set_attribute("ParameterName", self.name_from_physical_resource_id())

        except (TypeError, ClientError) as e:
            if self.request_type == "Create":
                self.physical_resource_id = "could-not-create"
            self.fail(str(e))

    def get_secret(self):
        response = self.ssm.get_parameter(
            Name=self.name_from_physical_resource_id(), WithDecryption=True
        )
        return response["Parameter"]["Value"]

    def create(self):
        self.put_parameter(overwrite=False, new_secret=True)

    @property
    def refresh_on_update(self) -> bool:
        return self.get("RefreshOnUpdate")

    def update(self):
        self.put_parameter(
            overwrite=self.allow_overwrite,
            new_secret=self.refresh_on_update,
        )

    def delete(self):
        name = self.physical_resource_id.split("/", 1)
        if len(name) == 2:
            try:
                self.ssm.delete_parameter(Name=name[1])
            except ClientError as e:
                if e.response["Error"]["Code"] != "ParameterNotFound":
                    return self.fail(str(e))

            self.success("System Parameter with the name %s is deleted" % name)
        else:
            self.success(
                "System Parameter with the name %s is ignored"
                % self.physical_resource_id
            )


provider = RandomBytesProvider()


def handler(request, context):
    return provider.handle(request, context)
