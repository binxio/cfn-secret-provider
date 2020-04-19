import base64
import boto3
import hashlib
import hmac
import logging
import re
from botocore.exceptions import ClientError
from cfn_resource_provider import ResourceProvider

log = logging.getLogger(__name__)

request_schema = {
    "type": "object",
    "required": ["ParameterPath", "UserName"],
    "properties": {
        "ParameterPath": {
            "type": "string",
            "pattern": "^/[a-zA-Z0-9/.\\-_]*[^/]$",
            "description": "for the credentials in the parameter store",
        },
        "Description": {
            "type": "string",
            "default": " ",
            "description": "the description of the value in the parameter store",
        },
        "ReturnSecret": {
            "type": "boolean",
            "default": False,
            "description": "return access id and secret",
        },
        "ReturnPassword": {
            "type": "boolean",
            "default": False,
            "description": "return access id and smtp password",
        },
        "KeyAlias": {
            "type": "string",
            "default": "alias/aws/ssm",
            "description": "KMS key to use to encrypt the value",
        },
        "Serial": {
            "type": "integer",
            "default": 1,
            "description": "version to force update",
        },
        "Status": {
            "type": "string",
            "default": "Active",
            "enum": ["Active", "Inactive"],
            "description": "status of the key",
        },
        "UserName": {"type": "string", "description": "to create the access key for"},
        "NoEcho": {
            "type": "boolean",
            "default": True,
            "description": "the secrets as output parameter",
        },
    },
}


class AccessKeyProvider(ResourceProvider):
    def __init__(self):
        super(AccessKeyProvider, self).__init__()
        self.request_schema = request_schema
        self.region = boto3.session.Session().region_name
        self.account_id = (boto3.client("sts")).get_caller_identity()["Account"]
        self.iam = boto3.client("iam")
        self.ssm = boto3.client("ssm")

    def convert_property_types(self):
        self.heuristic_convert_property_types(self.properties)
        self.heuristic_convert_property_types(self.old_properties)

    def hash_secret(self, key):
        message = b"SendRawEmail"
        result = bytearray(b"\x02")
        result.extend(
            hmac.new(key.encode("utf-8"), message, digestmod=hashlib.sha256).digest()
        )
        return base64.b64encode(result).decode("ascii")

    def delete_access_key(self, access_key):
        try:
            self.iam.delete_access_key(
                UserName=access_key["UserName"], AccessKeyId=access_key["AccessKeyId"]
            )
        except self.iam.exceptions.NoSuchEntityException:
            log.info(
                "no access key {AccessKeyId} was found for user {UserName}".format(
                    **access_key
                )
            )
        except ClientError as e:
            self.fail("failed to delete access key, {}".format(e))

    def create_access_key(self):
        access_key = None
        user_name = self.get("UserName")
        try:
            response = self.iam.create_access_key(UserName=user_name)
            access_key = response["AccessKey"]
            self.iam.update_access_key(
                UserName=user_name,
                AccessKeyId=access_key["AccessKeyId"],
                Status=self.get("Status"),
            )
        except ClientError:
            if access_key is not None:
                self.delete_access_key(access_key)
            self.fail(
                "failed to create access key for user {}\n{}".format(
                    user_name, self.reason
                )
            )
        return access_key

    @property
    def parameter_path(self):
        return self.get("ParameterPath").rstrip("/ \t")

    @property
    def old_parameter_path(self):
        return self.get_old("ParameterPath", self.get("ParameterPath")).rstrip("/ \t")

    def check_parameter_path_exists(self):
        for suffix in [
            "/aws_access_key_id",
            "/aws_secret_access_key",
            "/smtp_password",
        ]:
            try:
                name = f"{self.parameter_path}{suffix}"
                self.ssm.get_parameter(Name=name)
                self.fail("parameter {} already exists.".format(name))
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] != "ParameterNotFound":
                    raise

        return False

    def put_in_parameter_store(self, access_key):
        self.ssm.put_parameter(
            Name="{}/aws_access_key_id".format(self.parameter_path),
            Value=access_key["AccessKeyId"],
            Type="SecureString",
            Overwrite=True,
            KeyId=self.get("KeyAlias"),
            Description="{} access id".format(self.get("Description")),
        )

        self.ssm.put_parameter(
            Name="{}/aws_secret_access_key".format(self.parameter_path),
            Value=access_key["SecretAccessKey"],
            Type="SecureString",
            Overwrite=True,
            KeyId=self.get("KeyAlias"),
            Description="{} secret key".format(self.get("Description")),
        )

        self.ssm.put_parameter(
            Name="{}/smtp_password".format(self.parameter_path),
            Value=self.hash_secret(access_key["SecretAccessKey"]),
            Type="SecureString",
            Overwrite=True,
            KeyId=self.get("KeyAlias"),
            Description="{} smtp password".format(self.get("Description")),
        )

    def remove_from_parameter_store(self, parameter_path):
        name = None
        for suffix in [
            "/aws_access_key_id",
            "/aws_secret_access_key",
            "/smtp_password",
        ]:
            try:
                name = "{}{}".format(parameter_path, suffix)
                self.ssm.delete_parameter(Name=name)
            except ClientError as e:
                if e.response["Error"]["Code"] != "ParameterNotFound":
                    msg = "failed to delete parameter {}, {}\n".format(name, e)
                    self.reason = "{}{}".format(self.reason, msg)

    def get_from_parameter_store(self, parameter_path=None) -> dict:
        if parameter_path is None:
            parameter_path = self.parameter_path

        try:
            result = {}
            response = self.ssm.get_parameter(
                Name="{}/aws_access_key_id".format(parameter_path), WithDecryption=True
            )
            result["AccessKeyId"] = response["Parameter"]["Value"]
            response = self.ssm.get_parameter(
                Name="{}/aws_secret_access_key".format(parameter_path),
                WithDecryption=True,
            )
            result["SecretAccessKey"] = response["Parameter"]["Value"]
            response = self.ssm.get_parameter(
                Name="{}/smtp_password".format(parameter_path), WithDecryption=True
            )
            result["SMTPPassword"] = response["Parameter"]["Value"]
            return result
        except self.ssm.exceptions.ParameterNotFound as e:
            log.error("%s", e)
            return None

    def set_result_attributes(self, access_key):
        self.physical_resource_id = access_key["AccessKeyId"]
        self.put_in_parameter_store(access_key)

        if self.get("ReturnSecret"):
            self.set_attribute("SecretAccessKey", access_key["SecretAccessKey"])

        if self.get("ReturnPassword"):
            self.set_attribute(
                "SMTPPassword", self.hash_secret(access_key["SecretAccessKey"])
            )
        self.no_echo = self.get("NoEcho")

    def create(self):
        if not self.check_parameter_path_exists():
            access_key = self.create_access_key()
            if access_key is not None:
                self.set_result_attributes(access_key)
            else:
                self.physical_resource_id = "could-not-create"
        else:
            self.physical_resource_id = "could-not-create"

    @property
    def update_requires_new_key(self):
        log.debug("new %s", self.properties)
        log.debug("old %s", self.old_properties)
        if self.get("Serial", 1) != self.get_old("Serial", 1):
            log.info("forcing new key due to higher serial number\n")
            return True

        if self.get("UserName") != self.get_old("UserName", self.get("UserName")):
            log.info("forcing new key due to new username\n")
            return True

        log.info("keeping existing key\n")
        return False

    def update(self):
        if self.parameter_path != self.old_parameter_path:
            if self.check_parameter_path_exists():
                return

        if self.update_requires_new_key:
            access_key = self.create_access_key()
            if access_key is not None:
                self.set_result_attributes(access_key)
        else:
            try:
                self.iam.update_access_key(
                    UserName=self.get("UserName"),
                    AccessKeyId=self.physical_resource_id,
                    Status=self.get("Status"),
                )
            except ClientError as e:
                self.fail("failed to update access key, {}".format(e))

            old_access_key = self.get_from_parameter_store(self.old_parameter_path)
            if old_access_key is not None:
                self.set_result_attributes(old_access_key)
            else:
                self.fail(
                    "access key was not found under {}.".format(self.old_parameter_path)
                )
                return

            if self.parameter_path != self.old_parameter_path:
                self.put_in_parameter_store(old_access_key)
                self.remove_from_parameter_store(self.old_parameter_path)

    def delete(self):
        if self.physical_resource_id == "could-not-create":
            return

        if not re.match(r"^[A-Z0-9]+$", self.physical_resource_id):
            self.success("physical resource id is not an access key id.")
            return

        access_key = {
            "AccessKeyId": self.physical_resource_id,
            "UserName": self.get("UserName"),
        }
        self.delete_access_key(access_key)

        old_access_key = self.get_from_parameter_store()
        if (
            old_access_key is not None
            and old_access_key["AccessKeyId"] == self.physical_resource_id
        ):
            self.remove_from_parameter_store(self.parameter_path)
        elif old_access_key is not None:
            msg = "keeping parameters as the access key has changed."
            self.response["Reason"] = "{}{}".format(self.reason, msg)
        else:
            msg = "no access key found under {}.".format(self.parameter_path)
            self.response["Reason"] = "{}{}".format(self.reason, msg)


provider = AccessKeyProvider()


def handler(request, context):
    return provider.handle(request, context)
