import binascii
import hashlib
import logging
import os
import string
from base64 import b64decode
from random import choice


import boto3
from botocore.exceptions import ClientError
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
        "Description": {
            "type": "string",
            "default": "",
            "description": "the description of the value in the parameter store",
        },
        "Alphabet": {
            "type": "string",
            "default": string.ascii_letters + string.digits + "_",
            "description": "the characters from which to generate the secret",
        },
        "Required": {
            "type": "array",
            "description": "characters in the alphabet",
            "items": {
                "type": "object",
                "required": ["Count", "Alphabet"],
                "properties": {
                    "Count": {"type": "integer", "minimum": 1, "default": 1},
                    "Alphabet": {"type": "string"},
                },
            },
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
        "Content": {
            "type": "string",
            "description": "Plain text secret, to be stored as is.",
        },
        "EncryptedContent": {
            "type": "string",
            "description": "base64 encoded KMS encrypted secret, decrypted before stored",
        },
        "Length": {
            "type": "integer",
            "default": 30,
            "minimum": 1,
            "maximum": 512,
            "description": "length of the secret",
        },
        "Version": {"type": "string", "description": "opaque string to force update"},
        "NoEcho": {
            "type": "boolean",
            "default": True,
            "description": "the secret as output parameter",
        },
    },
}


class SecretProvider(ResourceProvider):
    def __init__(self):
        super(SecretProvider, self).__init__()
        self._value = None
        self.request_schema = request_schema
        self.ssm = boto3.client("ssm")
        self.kms = boto3.client("kms")
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client("sts")).get_caller_identity()["Account"]

    def is_valid_request(self):
        result = super(SecretProvider, self).is_valid_request()
        if (
            result
            and "Content" in self.properties
            and "EncryptedContent" in self.properties
        ):
            self.fail('Specify either "Content" or "EncryptedContent"')
            result = False

        if "EncryptedContent" in self.properties:
            try:
                b64decode(self.get("EncryptedContent"))
            except binascii.Error as e:
                self.fail("EncryptedContent is not base64 encoded, {}".format(e))
                result = False

        if result and "Required" in self.properties:
            required_characters = sum(map(lambda r: r["Count"], self.get("Required")))
            if required_characters > self.get("Length"):
                self.fail(
                    f"the length should at least exceed the {required_characters} required characters"
                )
                result = False

        return result

    def convert_property_types(self):
        try:
            if "Length" in self.properties and isinstance(
                self.properties["Length"], str
            ):
                self.properties["Length"] = int(self.properties["Length"])
            if "ReturnSecret" in self.properties and isinstance(
                self.properties["ReturnSecret"], str
            ):
                self.properties["ReturnSecret"] = (
                    self.properties["ReturnSecret"] == "true"
                )
            if "NoEcho" in self.properties and isinstance(
                self.properties["NoEcho"], str
            ):
                self.properties["NoEcho"] = self.properties["NoEcho"] == "true"
            if "RefreshOnUpdate" in self.properties and isinstance(
                self.properties["RefreshOnUpdate"], str
            ):
                self.properties["RefreshOnUpdate"] = (
                    self.properties["RefreshOnUpdate"] == "true"
                )
            for a in self.properties.get("Required", []):
                a["Count"] = int(a["Count"])
        except (binascii.Error, ValueError) as e:
            log.error("failed to convert property types %s", e)

    @property
    def allow_overwrite(self):
        return self.physical_resource_id == self.arn

    def name_from_physical_resource_id(self):
        return ssm_parameter_name.from_arn(self.physical_resource_id)

    @property
    def arn(self):
        return ssm_parameter_name.to_arn(self.region, self.account_id, self.get("Name"))

    def generate_password(self):
        if not self.get("Required"):
            return "".join(
                choice(self.get("Alphabet")) for _ in range(0, self.get("Length"))
            )

        result = []
        for r in self.get("Required", []):
            for c in range(r["Count"]):
                result.append(choice(r["Alphabet"]))

        to_append = self.get("Length") - len(result)
        result.extend(choice(self.get("Alphabet")) for _ in range(0, to_append))

        return "".join(result)

    def get_content(self):
        if "EncryptedContent" in self.properties:
            result = self.kms.decrypt(
                CiphertextBlob=b64decode(self.get("EncryptedContent"))
            )
            result = result["Plaintext"].decode("utf8")
        elif "Content" in self.properties:
            result = self.get("Content")
        else:
            result = self.generate_password()

        return result

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
        return self.get("RefreshOnUpdate") or self.get("EncryptedContent")

    def update(self):
        self.put_parameter(
            overwrite=ssm_parameter_name.equals(self.physical_resource_id, self.arn),
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


provider = SecretProvider()


def handler(request, context):
    return provider.handle(request, context)
