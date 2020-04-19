import boto3

iam = boto3.client("iam")
ssm = boto3.client("ssm")
for user in iam.list_users()["Users"]:
    username = user["UserName"]
    if username.startswith("test-"):
        for key in iam.list_access_keys(UserName=username)["AccessKeyMetadata"]:
            print(
                "deleting {} access key {} from {}".format(
                    key["Status"], key["AccessKeyId"], username
                )
            )
            iam.delete_access_key(UserName=username, AccessKeyId=key["AccessKeyId"])
        print("deleting user {}".format(username))
        iam.delete_user(UserName=username)

paginator = ssm.get_paginator("describe_parameters")
for page in paginator.paginate():
    for parameter in page["Parameters"]:
        name = parameter["Name"]
        if (
            name.startswith("test-")
            or name.startswith("/test-")
            or name.startswith("/test/")
        ):
            print("deleting parameter {}".format(name))
            ssm.delete_parameter(Name=name)
